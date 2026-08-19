from __future__ import annotations

from dataclasses import dataclass

from ..analysis.notes import Note, pair_notes
from ..domain.changes import Change, ChangeSet, RiskLevel
from .base import OptimizationContext
from .velocity import classify_program_family, detect_trill_note_ids, resolve_note_addresses


@dataclass(frozen=True, slots=True)
class ArticulationProfile:
    family: str
    grace_velocity: int
    trill_velocity: int
    repeated_velocity_drop: int
    legato_gap_divisor: int
    staccato_gate: float


ARTICULATION_PROFILES = {
    "piano": ArticulationProfile("piano", 54, 78, 3, 24, 0.58),
    "mallet": ArticulationProfile("mallet", 58, 84, 3, 32, 0.48),
    "organ": ArticulationProfile("organ", 66, 78, 1, 12, 0.82),
    "guitar": ArticulationProfile("guitar", 52, 84, 4, 20, 0.54),
    "bass": ArticulationProfile("bass", 62, 86, 3, 24, 0.62),
    "strings": ArticulationProfile("strings", 50, 80, 2, 12, 0.76),
    "choir": ArticulationProfile("choir", 48, 76, 1, 10, 0.84),
    "brass": ArticulationProfile("brass", 62, 92, 4, 20, 0.58),
    "woodwind": ArticulationProfile("woodwind", 54, 86, 3, 12, 0.70),
    "lead": ArticulationProfile("lead", 58, 88, 2, 12, 0.72),
    "pad": ArticulationProfile("pad", 46, 72, 1, 8, 0.90),
    "ethnic": ArticulationProfile("ethnic", 52, 88, 4, 18, 0.58),
    "percussion": ArticulationProfile("percussion", 58, 90, 5, 32, 0.45),
    "drums": ArticulationProfile("drums", 46, 88, 6, 32, 0.40),
    "effects": ArticulationProfile("effects", 54, 78, 2, 10, 0.86),
}


@dataclass(frozen=True, slots=True)
class ArticulationFinding:
    kind: str
    event_ids: tuple[str, ...]
    channel: int
    start_tick: int
    confidence: float


@dataclass(frozen=True, slots=True)
class AutomaticArticulationResult:
    changes: ChangeSet
    findings: tuple[ArticulationFinding, ...]
    processed_addresses: tuple[str, ...]
    unmatched_addresses: tuple[str, ...]


def _next_notes(notes: list[Note]) -> dict[str, Note]:
    result: dict[str, Note] = {}
    by_channel: dict[int, list[Note]] = {}
    for note in notes:
        by_channel.setdefault(note.channel, []).append(note)
    for channel_notes in by_channel.values():
        by_onset: dict[int, list[Note]] = {}
        for note in channel_notes:
            by_onset.setdefault(note.start_tick, []).append(note)
        onsets = sorted(by_onset)
        for current_tick, following_tick in zip(onsets, onsets[1:]):
            current = by_onset[current_tick]
            following = by_onset[following_tick]
            if len(current) == 1 and len(following) == 1:
                result[current[0].on_event_id] = following[0]
    return result


def plan_articulations(context: OptimizationContext, catalog) -> AutomaticArticulationResult:
    song = context.song
    if not song.header.ppq:
        raise ValueError("articulation planning requires PPQ time division")
    ppq = song.header.ppq
    notes, _ = pair_notes(song)
    event_map = {event.event_id: event for track in song.tracks for event in track.events}
    address_by_event = resolve_note_addresses(song)
    learned = {item.address: item for item in catalog.profiles}
    trill_ids = detect_trill_note_ids(notes, ppq)
    following = _next_notes(notes)
    findings: list[ArticulationFinding] = []
    changes: list[Change] = []
    unmatched: set[str] = set()
    processed: set[str] = set()
    repeated_run: dict[tuple[int, int], int] = {}

    for note in sorted(notes, key=lambda item: (item.start_tick, item.channel, item.note)):
        address = address_by_event.get(note.on_event_id)
        if address is None or address not in learned:
            if address:
                unmatched.add(address)
            continue
        entry = learned[address]
        if entry.factory_key_range and not entry.factory_key_range[0] <= note.note <= entry.factory_key_range[1]:
            continue
        processed.add(address)
        family = classify_program_family(entry.program, entry.channel)
        profile = ARTICULATION_PROFILES[family]
        next_note = following.get(note.on_event_id)
        duration = note.end_tick - note.start_tick
        on_event = event_map[note.on_event_id]

        if note.on_event_id in trill_ids:
            findings.append(ArticulationFinding("trill", (note.on_event_id, note.off_event_id), note.channel, note.start_tick, 0.90))
            target = min(127, max(1, profile.trill_velocity))
            if on_event.data[1] != target:
                changes.append(Change(
                    f"articulation:trill:{note.on_event_id}", "articulation", "instrument-specific trill attack",
                    RiskLevel.MEDIUM, note.on_event_id, "velocity", on_event.data[1], target,
                ))
            continue

        is_grace = (
            next_note is not None
            and duration <= max(1, ppq // 8)
            and 0 <= next_note.start_tick - note.end_tick <= max(1, ppq // 4)
            and abs(next_note.note - note.note) <= 12
        )
        if is_grace:
            findings.append(ArticulationFinding("grace", (note.on_event_id, note.off_event_id), note.channel, note.start_tick, 0.82))
            target = min(127, max(1, profile.grace_velocity))
            if on_event.data[1] != target:
                changes.append(Change(
                    f"articulation:grace:{note.on_event_id}", "articulation", "instrument-specific grace-note attack",
                    RiskLevel.MEDIUM, note.on_event_id, "velocity", on_event.data[1], target,
                ))
            continue

        repeat_key = (note.channel, note.note)
        repeat_index = repeated_run.get(repeat_key, 0)
        if next_note and next_note.note == note.note and next_note.start_tick - note.start_tick <= ppq // 2:
            repeated_run[repeat_key] = repeat_index + 1
            findings.append(ArticulationFinding("repetition", (note.on_event_id, note.off_event_id), note.channel, note.start_tick, 0.78))
            target = max(1, on_event.data[1] - (repeat_index % 2) * profile.repeated_velocity_drop)
            if target != on_event.data[1]:
                changes.append(Change(
                    f"articulation:repeat:{note.on_event_id}", "articulation", "alternate repeated-note attack",
                    RiskLevel.MEDIUM, note.on_event_id, "velocity", on_event.data[1], target,
                ))
            continue
        repeated_run[repeat_key] = 0

        if next_note and next_note.start_tick > note.end_tick:
            gap = next_note.start_tick - note.end_tick
            if gap <= max(1, ppq // profile.legato_gap_divisor) and abs(next_note.note - note.note) <= 12:
                findings.append(ArticulationFinding("legato", (note.off_event_id, next_note.on_event_id), note.channel, note.start_tick, 0.76))
                changes.append(Change(
                    f"articulation:legato:{note.off_event_id}", "articulation", "close a small melodic legato gap",
                    RiskLevel.MEDIUM, note.off_event_id, "absolute_tick", note.end_tick, next_note.start_tick,
                ))
                continue

        if duration <= ppq // 2:
            findings.append(ArticulationFinding("staccato", (note.on_event_id, note.off_event_id), note.channel, note.start_tick, 0.70))

    return AutomaticArticulationResult(
        ChangeSet(changes), tuple(findings), tuple(sorted(processed)), tuple(sorted(unmatched))
    )
