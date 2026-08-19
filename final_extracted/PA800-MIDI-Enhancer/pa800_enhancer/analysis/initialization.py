from dataclasses import dataclass
from fractions import Fraction

from ..domain.events import EventKind, MidiEvent
from ..domain.song import Song
from .meter_map import MeterMap
from .sysex import SysexClassification, analyze_sysex


ROLE_RANK = {
    "bank_msb": 10,
    "bank_lsb": 20,
    "program": 30,
    "volume": 40,
    "pan": 50,
    "expression": 60,
    "effect_send": 70,
}
CONTROLLER_ROLES = {
    0: "bank_msb",
    32: "bank_lsb",
    7: "volume",
    10: "pan",
    11: "expression",
    91: "effect_send",
    92: "effect_send",
    93: "effect_send",
    94: "effect_send",
    95: "effect_send",
}
RESET_CLASSES = {
    SysexClassification.GM1_SYSTEM_ON,
    SysexClassification.GM_SYSTEM_OFF,
    SysexClassification.GM2_SYSTEM_ON,
    SysexClassification.GS_RESET,
    SysexClassification.XG_SYSTEM_ON,
}


@dataclass(frozen=True, slots=True)
class InitializationEvent:
    event_id: str
    absolute_tick: int
    track_index: int
    order: int
    channel: int | None
    role: str
    controller: int | None = None


@dataclass(frozen=True, slots=True)
class InitializationSequence:
    channel: int
    event_ids: tuple[str, ...]
    roles: tuple[str, ...]
    violations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InitializationAnalysis:
    status: str
    first_bar_end_tick: int | None
    first_note_tick: int | None
    music_starts_on_second_bar: bool
    initialization_events: tuple[InitializationEvent, ...]
    sequences: tuple[InitializationSequence, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def has_initialization_bar_candidate(self) -> bool:
        return self.status in {"possible", "probable"}


def analyze_initialization_bar(song: Song) -> InitializationAnalysis:
    if song.header.uses_smpte:
        return InitializationAnalysis(
            "unsupported",
            None,
            _first_note_tick(song),
            False,
            (),
            (),
            ("initialization-bar detection requires PPQ time division",),
            (),
            (),
        )

    meter_map = MeterMap(song)
    first_bar = meter_map.ticks_per_bar(meter_map.changes[0])
    first_bar_end = _ceil_fraction(first_bar)
    first_note = _first_note_tick(song)
    starts_on_second_bar = first_note == first_bar_end
    blockers: list[str] = []
    warnings: list[str] = []
    reasons: list[str] = []

    if first_note is None:
        blockers.append("song has no Note On event, so the musical start is unknown")
    elif first_note < first_bar_end:
        blockers.append("a note starts inside the first bar")
    elif first_note > first_bar_end:
        warnings.append("music starts after the second-bar boundary; this may be an intentional rest")
    else:
        reasons.append("the first note starts exactly at the second-bar boundary")

    reset_event_ids: set[str] = set()
    unknown_sysex_ids: set[str] = set()
    for message in analyze_sysex(song).messages:
        if message.start_tick >= first_bar_end:
            continue
        if message.classification in RESET_CLASSES:
            reset_event_ids.update(message.event_ids)
        elif message.classification in {
            SysexClassification.UNKNOWN,
            SysexClassification.INCOMPLETE,
            SysexClassification.MALFORMED,
        }:
            unknown_sysex_ids.update(message.event_ids)

    initialization: list[InitializationEvent] = []
    unexpected: list[MidiEvent] = []
    for event in _ordered_events(song):
        if event.absolute_tick >= first_bar_end:
            continue
        role = _initialization_role(event, reset_event_ids)
        if role is not None:
            initialization.append(
                InitializationEvent(
                    event.event_id,
                    event.absolute_tick,
                    event.track_index,
                    event.order,
                    event.channel,
                    role,
                    event.data[0]
                    if event.kind is EventKind.CHANNEL
                    and event.message_type == 0xB0
                    and len(event.data) == 2
                    else None,
                )
            )
        elif event.kind is EventKind.CHANNEL:
            # Note events are already handled through the musical-start test.
            if not event.is_note_on and not event.is_note_off:
                unexpected.append(event)

    if initialization:
        reasons.append(f"found {len(initialization)} recognized initialization events in the first bar")
    else:
        warnings.append("the first bar contains no recognized reset, bank, program or mix initialization")
    if reset_event_ids:
        reasons.append("found a recognized reset message before the musical start")
    if unknown_sysex_ids:
        blockers.append("unknown, incomplete or malformed SysEx appears in the candidate bar")
    if unexpected:
        blockers.append("non-initialization channel messages appear before the musical start")

    sequences = _build_sequences(initialization)
    violations = [violation for sequence in sequences for violation in sequence.violations]
    if violations:
        blockers.extend(violations)
    if any(len(sequence.event_ids) > 1 for sequence in sequences):
        reasons.append("recognized channel initialization follows a reviewable sequence")

    if blockers:
        status = "ambiguous" if first_note is None or first_note >= first_bar_end else "not_present"
    elif first_note is None or first_note < first_bar_end or not initialization:
        status = "not_present"
    elif starts_on_second_bar:
        status = "probable"
    else:
        status = "possible"

    return InitializationAnalysis(
        status,
        first_bar_end,
        first_note,
        starts_on_second_bar,
        tuple(initialization),
        sequences,
        tuple(blockers),
        tuple(warnings),
        tuple(reasons),
    )


def _build_sequences(events: list[InitializationEvent]) -> tuple[InitializationSequence, ...]:
    by_channel: dict[int, list[InitializationEvent]] = {}
    for event in events:
        if event.channel is not None:
            by_channel.setdefault(event.channel, []).append(event)
    result: list[InitializationSequence] = []
    for channel, channel_events in sorted(by_channel.items()):
        ordered = sorted(channel_events, key=lambda item: (item.absolute_tick, item.track_index, item.order))
        violations: list[str] = []
        previous_rank = -1
        previous_role = ""
        tracks = {event.track_index for event in ordered}
        if len(tracks) > 1:
            violations.append(f"channel {channel} initialization spans multiple tracks")
        for event in ordered:
            rank = ROLE_RANK[event.role]
            if rank < previous_rank:
                violations.append(
                    f"channel {channel} initialization order moves backward from {previous_role} to {event.role}"
                )
            previous_rank = max(previous_rank, rank)
            previous_role = event.role
        result.append(
            InitializationSequence(
                channel,
                tuple(event.event_id for event in ordered),
                tuple(event.role for event in ordered),
                tuple(violations),
            )
        )
    return tuple(result)


def _initialization_role(event: MidiEvent, reset_event_ids: set[str]) -> str | None:
    if event.event_id in reset_event_ids:
        return "reset"
    if event.kind is not EventKind.CHANNEL:
        return None
    if event.message_type == 0xC0 and len(event.data) == 1:
        return "program"
    if event.message_type == 0xB0 and len(event.data) == 2:
        return CONTROLLER_ROLES.get(event.data[0])
    return None


def _ordered_events(song: Song) -> list[MidiEvent]:
    return sorted(
        (event for track in song.tracks for event in track.events),
        key=lambda event: (event.absolute_tick, event.track_index, event.order),
    )


def _first_note_tick(song: Song) -> int | None:
    return min(
        (event.absolute_tick for event in _ordered_events(song) if event.is_note_on),
        default=None,
    )


def _ceil_fraction(value: Fraction) -> int:
    return (value.numerator + value.denominator - 1) // value.denominator