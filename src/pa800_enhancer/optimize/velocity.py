import hashlib
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.meter_map import MeterMap
from ..analysis.notes import Note, pair_notes
from ..domain.changes import Change, ChangeSet, RiskLevel
from .base import OptimizationContext

if TYPE_CHECKING:  # pragma: no cover
    from .rx_guard import RxVelocityGuard
    from ..profiles.rx import RxSoundProfile


@dataclass(frozen=True, slots=True)
class InstrumentVelocityProfile:
    family: str
    minimum: int
    maximum: int
    center: int
    primary_accent: int
    secondary_accent: int
    short_note_adjustment: int
    chord_inner_adjustment: int
    phrase_depth: int
    humanize: int
    key_range: tuple[int, int] = (0, 127)
    trill_center: int | None = None


INSTRUMENT_VELOCITY_PROFILES = {
    "piano": InstrumentVelocityProfile("piano", 28, 122, 78, 16, 8, 4, -5, 10, 3),
    "electric_piano": InstrumentVelocityProfile("electric_piano", 35, 116, 76, 12, 6, 2, -4, 7, 2),
    "mallet": InstrumentVelocityProfile("mallet", 38, 120, 82, 14, 7, 5, -3, 6, 2, trill_center=86),
    "organ": InstrumentVelocityProfile("organ", 52, 112, 78, 7, 3, -2, -2, 3, 1, trill_center=80),
    "guitar": InstrumentVelocityProfile("guitar", 34, 120, 82, 14, 7, 5, -3, 8, 3),
    "bass": InstrumentVelocityProfile("bass", 48, 118, 88, 13, 6, 2, -2, 5, 2),
    "strings": InstrumentVelocityProfile("strings", 38, 112, 72, 8, 4, -5, -4, 9, 2, trill_center=78),
    "woodwind": InstrumentVelocityProfile("woodwind", 42, 116, 78, 11, 5, 3, -3, 8, 2, trill_center=84),
    "brass": InstrumentVelocityProfile("brass", 52, 124, 88, 16, 8, 5, -4, 7, 2, trill_center=92),
    "lead": InstrumentVelocityProfile("lead", 48, 120, 86, 12, 6, 4, -3, 6, 2, trill_center=90),
    "pad": InstrumentVelocityProfile("pad", 36, 104, 68, 5, 2, -6, -3, 7, 1),
    "choir": InstrumentVelocityProfile("choir", 40, 108, 70, 6, 3, -5, -4, 8, 1),
    "ethnic": InstrumentVelocityProfile("ethnic", 38, 120, 82, 13, 6, 4, -3, 8, 3, trill_center=86),
    "percussion": InstrumentVelocityProfile("percussion", 42, 127, 90, 18, 9, 5, 0, 4, 3),
    "effects": InstrumentVelocityProfile("effects", 44, 112, 76, 6, 3, -3, -2, 4, 1),
    "drums": InstrumentVelocityProfile("drums", 24, 127, 86, 18, 9, 3, 0, 4, 4),
}


@dataclass(frozen=True, slots=True)
class VelocityShapeResult:
    changes: ChangeSet
    note_count: int
    changed_count: int
    protected_out_of_range: int
    trill_note_count: int


@dataclass(frozen=True, slots=True)
class AutomaticVelocityResult:
    changes: ChangeSet
    segments: tuple[dict[str, object], ...]
    unmatched_addresses: tuple[str, ...]


def _stable_jitter(event_id: str, seed: int, amount: int) -> int:
    if amount <= 0:
        return 0
    digest = hashlib.sha256(f"{seed}:{event_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % (amount * 2 + 1) - amount


def detect_trill_note_ids(notes: list[Note], ppq: int) -> frozenset[str]:
    """Detect short alternating semitone/tone figures without inserting notes."""
    ordered = sorted(notes, key=lambda item: (item.channel, item.start_tick, item.note))
    onset_counts: dict[tuple[int, int], int] = {}
    for note in ordered:
        key = (note.channel, note.start_tick)
        onset_counts[key] = onset_counts.get(key, 0) + 1
    found: set[str] = set()
    for start in range(len(ordered)):
        if onset_counts[(ordered[start].channel, ordered[start].start_tick)] != 1:
            continue
        run = [ordered[start]]
        for candidate in ordered[start + 1 :]:
            previous = run[-1]
            if candidate.channel != previous.channel:
                break
            if candidate.start_tick <= previous.start_tick:
                break
            if onset_counts[(candidate.channel, candidate.start_tick)] != 1:
                break
            if candidate.start_tick - previous.start_tick > max(1, ppq // 2):
                break
            if abs(candidate.note - previous.note) not in (1, 2):
                break
            if len(run) >= 2 and candidate.note != run[-2].note:
                break
            if candidate.end_tick - candidate.start_tick > max(1, ppq // 2):
                break
            run.append(candidate)
        if len(run) >= 4 and len({item.note for item in run}) == 2:
            found.update(item.on_event_id for item in run)
    return frozenset(found)


def shape_instrument_velocity(
    context: OptimizationContext,
    profile: InstrumentVelocityProfile,
    *,
    allowed_event_ids: frozenset[str] | None = None,
) -> VelocityShapeResult:
    """Rebuild Note On velocity from musical context, never from source velocity."""
    song = context.song
    if not song.header.ppq:
        raise ValueError("instrument velocity shaping requires PPQ time division")
    meter = MeterMap(song)
    notes, _ = pair_notes(song)
    trill_ids = detect_trill_note_ids(notes, song.header.ppq)
    event_map = {event.event_id: event for track in song.tracks for event in track.events}
    chord_groups: dict[tuple[int, int], list[Note]] = {}
    for note in notes:
        if allowed_event_ids is not None and note.on_event_id not in allowed_event_ids:
            continue
        chord_groups.setdefault((note.channel, note.start_tick), []).append(note)
    song_length = max(1, song.end_tick)
    changes: list[Change] = []
    protected = 0
    trill_count = 0
    for note in notes:
        if allowed_event_ids is not None and note.on_event_id not in allowed_event_ids:
            continue
        if not profile.key_range[0] <= note.note <= profile.key_range[1]:
            protected += 1
            continue
        event = event_map[note.on_event_id]
        position = meter.position(note.start_tick)
        target = profile.center
        if position.tick_in_beat == 0:
            target += profile.primary_accent if position.beat == 1 else profile.secondary_accent
        phrase_phase = min(1.0, max(0.0, note.start_tick / song_length))
        target += round(math.sin(math.pi * phrase_phase) * profile.phrase_depth)
        duration = note.end_tick - note.start_tick
        if duration <= max(1, song.header.ppq // 4):
            target += profile.short_note_adjustment
        chord = chord_groups[(note.channel, note.start_tick)]
        if len(chord) > 1 and note.note not in (min(item.note for item in chord), max(item.note for item in chord)):
            target += profile.chord_inner_adjustment
        if note.on_event_id in trill_ids:
            trill_count += 1
            target = profile.trill_center if profile.trill_center is not None else profile.center
            target += profile.secondary_accent if len(changes) % 2 == 0 else 0
        target += _stable_jitter(event.event_id, context.seed, profile.humanize)
        target = min(profile.maximum, max(profile.minimum, target))
        source = event.data[1]
        if target != source:
            changes.append(
                Change(
                    f"instrument-velocity:{event.event_id}",
                    "instrument_velocity",
                    f"rebuild velocity for {profile.family} from meter, phrase, duration and articulation",
                    RiskLevel.MEDIUM,
                    event.event_id,
                    "velocity",
                    source,
                    target,
                )
            )
    return VelocityShapeResult(ChangeSet(changes), len(notes), len(changes), protected, trill_count)


def classify_program_family(program: int, channel: int) -> str:
    if channel == 10:
        return "drums"
    if 0 <= program <= 15:
        return "piano" if program <= 7 else "mallet"
    if 16 <= program <= 23:
        return "organ"
    if 24 <= program <= 31:
        return "guitar"
    if 32 <= program <= 39:
        return "bass"
    if 40 <= program <= 51:
        return "strings"
    if 52 <= program <= 55:
        return "choir"
    if 56 <= program <= 63:
        return "brass"
    if 64 <= program <= 79:
        return "woodwind"
    if 80 <= program <= 87:
        return "lead"
    if 88 <= program <= 103:
        return "pad"
    if 104 <= program <= 111:
        return "ethnic"
    if 112 <= program <= 119:
        return "percussion"
    return "effects"


def resolve_note_addresses(song) -> dict[str, str]:
    resolved: dict[str, str] = {}
    state: dict[tuple[int, int], list[int]] = {}
    for track in song.tracks:
        for event in sorted(track.events, key=lambda item: (item.absolute_tick, item.order)):
            if event.channel is None:
                continue
            key = (track.index, event.channel)
            values = state.setdefault(key, [0, 0, 0])
            if event.message_type == 0xB0 and len(event.data) == 2:
                if event.data[0] == 0:
                    values[0] = event.data[1]
                elif event.data[0] == 32:
                    values[1] = event.data[1]
            elif event.message_type == 0xC0 and event.data:
                values[2] = event.data[0]
            elif event.is_note_on:
                resolved[event.event_id] = f"{values[0]}:{values[1]}:{values[2]}:ch{event.channel}"
    return resolved


def shape_velocity_automatically(context: OptimizationContext, catalog) -> AutomaticVelocityResult:
    address_by_event = resolve_note_addresses(context.song)
    event_ids_by_address: dict[str, set[str]] = {}
    for event_id, address in address_by_event.items():
        event_ids_by_address.setdefault(address, set()).add(event_id)
    learned_by_address = {item.address: item for item in catalog.profiles}
    changes: list[Change] = []
    segments: list[dict[str, object]] = []
    unmatched: list[str] = []
    for address in sorted(event_ids_by_address):
        learned = learned_by_address.get(address)
        if learned is None:
            unmatched.append(address)
            continue
        family = classify_program_family(learned.program, learned.channel)
        profile = INSTRUMENT_VELOCITY_PROFILES[family]
        if learned.factory_key_range:
            from dataclasses import replace
            profile = replace(profile, key_range=learned.factory_key_range)
        if learned.factory_velocity_p10_p90:
            from dataclasses import replace
            low, high = learned.factory_velocity_p10_p90
            profile = replace(profile, minimum=max(1, low), maximum=min(127, high), center=(low + high) // 2)
        result = shape_instrument_velocity(
            context, profile, allowed_event_ids=frozenset(event_ids_by_address[address])
        )
        changes.extend(result.changes.changes)
        segments.append({
            "address": address,
            "family": family,
            "notes": len(event_ids_by_address[address]),
            "changes": result.changed_count,
            "key_range": list(profile.key_range),
            "velocity_range": [profile.minimum, profile.maximum],
            "gold_trill_ratio": learned.gold_trill_note_ratio,
        })
    return AutomaticVelocityResult(ChangeSet(changes), tuple(segments), tuple(unmatched))


class VelocityRangeModule:
    """Ogranici velocity na odobreni opseg, uz postovanje RX oscilatora.

    RX-aware ponasanje (stavka 2.2 iz spiska nedovrsenog): na Pa800 RX
    zvuku velocity bira oscilator, tj. artikulaciju. Kada je poznat RX
    profil, prijedlog prolazi kroz `RxVelocityGuard`, pa se izmjena koja bi
    presla u drugi oscilator skrati na granicu zone ili odbaci. Note u
    apsolutnoj trigger zoni (C7-G9) se nikada ne diraju.

    Bez RX profila ponasanje je nepromijenjeno u odnosu na raniju verziju.
    """

    name = "velocity"

    def __init__(
        self,
        minimum: int = 1,
        maximum: int = 127,
        *,
        rx_guard: "RxVelocityGuard | None" = None,
        rx_profile: "RxSoundProfile | None" = None,
        role_by_channel: dict[int, str] | None = None,
    ) -> None:
        if not 1 <= minimum <= maximum <= 127:
            raise ValueError("invalid velocity range")
        self.minimum = minimum
        self.maximum = maximum
        self.rx_guard = rx_guard
        self.rx_profile = rx_profile
        self.role_by_channel = role_by_channel or {}

    def suggest(self, context: OptimizationContext) -> ChangeSet:
        from .rx_guard import RxVelocityGuard, VelocityProposal

        guard = self.rx_guard
        if guard is None and self.rx_profile is not None:
            guard = RxVelocityGuard()

        changes: list[Change] = []
        for track in context.song.tracks:
            for event in track.events:
                if not event.is_note_on:
                    continue
                velocity = event.data[1]
                target = min(self.maximum, max(self.minimum, velocity))
                if target == velocity:
                    continue

                if guard is not None:
                    decision = guard.review_one(
                        VelocityProposal(
                            event_id=event.event_id,
                            note=event.data[0],
                            old_velocity=velocity,
                            new_velocity=target,
                            channel=event.channel,
                            role=self.role_by_channel.get(
                                event.channel or -1, "unknown"
                            ),
                        ),
                        self.rx_profile,
                    )
                    if not decision.is_change:
                        continue
                    target = decision.applied_velocity

                changes.append(
                    Change(
                        f"velocity:{event.event_id}",
                        self.name,
                        "clamp velocity to approved profile range",
                        RiskLevel.MEDIUM,
                        event.event_id,
                        "velocity",
                        velocity,
                        target,
                    )
                )
        return ChangeSet(changes)
