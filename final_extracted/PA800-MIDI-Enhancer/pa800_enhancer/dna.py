from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from .analysis.notes import Note, pair_notes
from .domain.changes import Change, ChangeSet, RiskLevel
from .domain.song import Song
from .optimize.velocity import detect_trill_note_ids


DNA_SCHEMA_VERSION = 1
ROLE_ORDER = ("solo", "accompaniment", "bass", "drums", "guitar")


@dataclass(frozen=True, slots=True)
class RoleFingerprint:
    role: str
    note_count: int
    density_per_quarter: float
    pitch_mean: float
    pitch_std: float
    pitch_min: int
    pitch_max: int
    velocity_mean: float
    velocity_std: float
    duration_mean_quarters: float
    duration_std_quarters: float
    short_ratio: float
    chord_ratio: float
    syncopation_ratio: float
    repetition_ratio: float
    trill_ratio: float
    onset_grid: tuple[float, ...]
    pitch_classes: tuple[float, ...]
    drum_classes: tuple[float, ...]

    def vector(self) -> tuple[float, ...]:
        return (
            math.log1p(self.density_per_quarter) / 5.0,
            self.pitch_mean / 127.0,
            self.pitch_std / 48.0,
            self.velocity_mean / 127.0,
            self.velocity_std / 48.0,
            self.duration_mean_quarters / 4.0,
            self.duration_std_quarters / 4.0,
            self.short_ratio,
            self.chord_ratio,
            self.syncopation_ratio,
            self.repetition_ratio,
            self.trill_ratio,
            *self.onset_grid,
            *self.pitch_classes,
            *self.drum_classes,
        )


@dataclass(frozen=True, slots=True)
class SongFingerprint:
    schema_version: int
    fingerprint_id: str
    source_sha256: str
    ppq: int
    end_tick: int
    roles: tuple[RoleFingerprint, ...]

    def dumps(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True, slots=True)
class DnaMatch:
    fingerprint_id: str
    source_locator: str
    corpus_kind: str
    role: str
    distance: float
    fingerprint: RoleFingerprint


@dataclass(frozen=True, slots=True)
class DnaCorrectionResult:
    changes: ChangeSet
    matches: tuple[DnaMatch, ...]
    protected_notes: int


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    center = _mean(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / len(values))


def _programs(song: Song) -> dict[int, int]:
    result: dict[int, int] = defaultdict(int)
    for track in song.tracks:
        for event in sorted(track.events, key=lambda item: (item.absolute_tick, item.order)):
            if event.channel and event.message_type == 0xC0 and event.data:
                result[event.channel] = event.data[0]
    return result


def classify_note_roles(song: Song, notes: list[Note] | None = None) -> dict[str, str]:
    """Separate performance melody from backing, drums and guitar gestures."""
    notes = notes if notes is not None else pair_notes(song)[0]
    by_channel: dict[int, list[Note]] = defaultdict(list)
    for note in notes:
        by_channel[note.channel].append(note)
    programs = _programs(song)
    melodic_candidates: list[tuple[float, int]] = []
    for channel, channel_notes in by_channel.items():
        if channel == 10 or 24 <= programs.get(channel, 0) <= 39:
            continue
        onset_counts = Counter(note.start_tick for note in channel_notes)
        monophony = sum(count == 1 for count in onset_counts.values()) / max(1, len(onset_counts))
        pitch = _mean([float(note.note) for note in channel_notes])
        melodic_candidates.append((pitch + 18.0 * monophony, channel))
    solo_channel = max(melodic_candidates, default=(0.0, -1))[1]
    roles: dict[str, str] = {}
    for note in notes:
        program = programs.get(note.channel, 0)
        role = (
            "drums" if note.channel == 10
            else "guitar" if 24 <= program <= 31
            else "bass" if 32 <= program <= 39
            else "solo" if note.channel == solo_channel
            else "accompaniment"
        )
        roles[note.on_event_id] = role
    return roles


def extract_fingerprint(song: Song) -> SongFingerprint:
    if not song.header.ppq:
        raise ValueError("DNA fingerprint requires PPQ time division")
    ppq = song.header.ppq
    notes, _ = pair_notes(song)
    role_by_id = classify_note_roles(song, notes)
    trill_ids = detect_trill_note_ids(notes, ppq)
    grouped: dict[str, list[Note]] = defaultdict(list)
    for note in notes:
        grouped[role_by_id[note.on_event_id]].append(note)
    roles: list[RoleFingerprint] = []
    total_quarters = max(1.0, song.end_tick / ppq)
    for role in ROLE_ORDER:
        selected = grouped.get(role, [])
        if not selected:
            continue
        pitches = [float(note.note) for note in selected]
        velocities = [float(note.velocity) for note in selected]
        durations = [max(0.0, (note.end_tick - note.start_tick) / ppq) for note in selected]
        onset_counts = Counter(note.start_tick for note in selected)
        grid = [0] * 16
        pitch_classes = [0] * 12
        drum_classes = [0] * 8
        repetitions = 0
        previous: dict[int, int] = {}
        for note in selected:
            grid[round((note.start_tick % (ppq * 4)) / (ppq * 4) * 16) % 16] += 1
            pitch_classes[note.note % 12] += 1
            if previous.get(note.channel) == note.note:
                repetitions += 1
            previous[note.channel] = note.note
            if role == "drums":
                bucket = 0 if note.note in (35, 36) else 1 if note.note in (38, 40) else 2 if note.note in (42, 44) else 3 if note.note in (46, 49, 51, 52, 55, 57, 59) else 4 if note.note in (41, 43, 45, 47, 48, 50) else 5 if note.note in (37, 39) else 6 if note.note in (53, 54, 56, 58) else 7
                drum_classes[bucket] += 1
        count = len(selected)
        normalize = lambda values: tuple(round(value / count, 6) for value in values)
        roles.append(RoleFingerprint(
            role, count, round(count / total_quarters, 6), round(_mean(pitches), 6),
            round(_std(pitches), 6), int(min(pitches)), int(max(pitches)),
            round(_mean(velocities), 6), round(_std(velocities), 6),
            round(_mean(durations), 6), round(_std(durations), 6),
            round(sum(value <= 0.25 for value in durations) / count, 6),
            round(sum(value > 1 for value in onset_counts.values()) / max(1, len(onset_counts)), 6),
            round(sum((note.start_tick % max(1, ppq // 2)) != 0 for note in selected) / count, 6),
            round(repetitions / count, 6), round(sum(note.on_event_id in trill_ids for note in selected) / count, 6),
            normalize(grid), normalize(pitch_classes), normalize(drum_classes),
        ))
    payload = json.dumps([asdict(role) for role in roles], sort_keys=True, separators=(",", ":"))
    source_hash = song.source_sha256 or hashlib.sha256(payload.encode()).hexdigest()
    fingerprint_id = hashlib.sha256(f"{DNA_SCHEMA_VERSION}:{source_hash}:{payload}".encode()).hexdigest()
    return SongFingerprint(DNA_SCHEMA_VERSION, fingerprint_id, source_hash, ppq, song.end_tick, tuple(roles))


def role_distance(left: RoleFingerprint, right: RoleFingerprint) -> float:
    a, b = left.vector(), right.vector()
    norm_a = math.sqrt(sum(value * value for value in a))
    norm_b = math.sqrt(sum(value * value for value in b))
    return 1.0 if not norm_a or not norm_b else max(0.0, 1.0 - sum(x * y for x, y in zip(a, b)) / (norm_a * norm_b))


def plan_dna_correction(song: Song, matches: tuple[DnaMatch, ...], *, strength: float = 0.65,
                        maximum_distance: float = 0.12) -> DnaCorrectionResult:
    if not 0.0 <= strength <= 1.0:
        raise ValueError("strength must be in range 0..1")
    notes, _ = pair_notes(song)
    role_by_id = classify_note_roles(song, notes)
    targets = {match.role: match.fingerprint for match in matches if match.distance <= maximum_distance}
    event_map = {event.event_id: event for track in song.tracks for event in track.events}
    notes_by_role: dict[str, list[Note]] = defaultdict(list)
    for item in notes:
        notes_by_role[role_by_id[item.on_event_id]].append(item)
    source_stats = {
        role: (
            _mean([float(item.velocity) for item in selected]),
            _std([float(item.velocity) for item in selected]),
            _mean([max(1.0, float(item.end_tick - item.start_tick)) for item in selected]),
        )
        for role, selected in notes_by_role.items()
    }
    track_ends = {
        track.index: min(
            (event.absolute_tick for event in track.events if event.meta_type == 0x2F),
            default=track.end_tick,
        )
        for track in song.tracks
    }
    changes: list[Change] = []
    protected = 0
    for note in notes:
        target = targets.get(role_by_id[note.on_event_id])
        if target is None or note.ambiguous_pairing:
            protected += 1
            continue
        on = event_map[note.on_event_id]
        source_mean, source_std, source_duration = source_stats[target.role]
        expressive_position = (on.data[1] - source_mean) / source_std if source_std >= 1.0 else 0.0
        gold_velocity = target.velocity_mean + expressive_position * target.velocity_std
        velocity = max(1, min(127, round(on.data[1] * (1.0 - strength) + gold_velocity * strength)))
        if abs(velocity - on.data[1]) >= 2:
            changes.append(Change(f"dna:velocity:{on.event_id}", "dna_velocity", f"match {target.role} Gold velocity fingerprint", RiskLevel.MEDIUM, on.event_id, "velocity", on.data[1], velocity))
        if target.role == "drums":
            continue
        duration = note.end_tick - note.start_tick
        target_duration = target.duration_mean_quarters * (song.header.ppq or 96)
        ratio = max(0.85, min(1.15, target_duration / max(1.0, source_duration)))
        new_duration = max(1, round(duration * (1.0 + (ratio - 1.0) * strength)))
        off = event_map[note.off_event_id]
        new_tick = min(track_ends.get(off.track_index, song.end_tick), note.start_tick + new_duration)
        if abs(new_tick - off.absolute_tick) >= max(2, (song.header.ppq or 96) // 32):
            changes.append(Change(f"dna:duration:{off.event_id}", "dna_articulation", f"match {target.role} Gold duration fingerprint", RiskLevel.MEDIUM, off.event_id, "absolute_tick", off.absolute_tick, new_tick))
    return DnaCorrectionResult(ChangeSet(changes), matches, protected)
