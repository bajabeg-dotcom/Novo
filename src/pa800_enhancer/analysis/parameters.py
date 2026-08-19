from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from ..domain.song import Song
from .controllers import ControllerEvent, controller_events


class ParameterKind(str, Enum):
    NRPN = "nrpn"
    RPN = "rpn"


class ParameterOperation(str, Enum):
    DATA_ENTRY = "data_entry"
    INCREMENT = "increment"
    DECREMENT = "decrement"


@dataclass(frozen=True, slots=True)
class ParameterChange:
    kind: ParameterKind
    operation: ParameterOperation
    channel: int
    parameter_msb: int
    parameter_lsb: int
    value_msb: int | None
    value_lsb: int | None
    amount: int | None
    start_tick: int
    end_tick: int
    event_ids: tuple[str, ...]
    track_indices: tuple[int, ...]
    ambiguous: bool = False

    @property
    def parameter_number(self) -> int:
        return (self.parameter_msb << 7) | self.parameter_lsb

    @property
    def value_14bit(self) -> int | None:
        if self.value_msb is None:
            return None
        return (self.value_msb << 7) | (self.value_lsb or 0)


@dataclass(frozen=True, slots=True)
class ParameterIssue:
    code: str
    message: str
    channel: int
    absolute_tick: int
    event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParameterAnalysis:
    changes: tuple[ParameterChange, ...]
    issues: tuple[ParameterIssue, ...]


@dataclass(slots=True)
class _Selection:
    kind: ParameterKind
    msb: int | None = None
    lsb: int | None = None
    msb_event: ControllerEvent | None = None
    lsb_event: ControllerEvent | None = None
    used: bool = True
    ambiguous: bool = False

    @property
    def events(self) -> tuple[ControllerEvent, ...]:
        return tuple(
            sorted(
                (item for item in (self.msb_event, self.lsb_event) if item is not None),
                key=lambda item: (item.absolute_tick, item.track_index, item.order),
            )
        )

    @property
    def complete(self) -> bool:
        return self.msb is not None and self.lsb is not None

    @property
    def is_null(self) -> bool:
        return self.complete and self.msb == 127 and self.lsb == 127


@dataclass(slots=True)
class _ChannelState:
    selections: dict[ParameterKind, _Selection] | None = None
    active_kind: ParameterKind | None = None
    pending_data_index: int | None = None

    def __post_init__(self) -> None:
        if self.selections is None:
            self.selections = {
                ParameterKind.NRPN: _Selection(ParameterKind.NRPN),
                ParameterKind.RPN: _Selection(ParameterKind.RPN),
            }

    @property
    def selection(self) -> _Selection | None:
        return self.selections.get(self.active_kind) if self.active_kind is not None else None


SELECTORS = {
    99: (ParameterKind.NRPN, "msb"),
    98: (ParameterKind.NRPN, "lsb"),
    101: (ParameterKind.RPN, "msb"),
    100: (ParameterKind.RPN, "lsb"),
}


def analyze_parameters(song: Song) -> ParameterAnalysis:
    changes: list[ParameterChange] = []
    issues: list[ParameterIssue] = []
    states = {channel: _ChannelState() for channel in range(1, 17)}

    for event in controller_events(song):
        state = states[event.channel]
        if event.controller in SELECTORS:
            _select(event, state, issues)
            continue
        if event.controller not in (6, 38, 96, 97):
            continue
        selection = state.selection
        if selection is None or not selection.complete or selection.is_null:
            issues.append(
                ParameterIssue(
                    "parameter_data_without_selection",
                    f"CC{event.controller} has no complete active NRPN/RPN selection",
                    event.channel,
                    event.absolute_tick,
                    (event.event_id,),
                )
            )
            state.pending_data_index = None
            continue

        if event.controller == 38:
            if state.pending_data_index is None:
                issues.append(
                    ParameterIssue(
                        "data_entry_lsb_without_msb",
                        "Data Entry LSB appears without a preceding Data Entry MSB",
                        event.channel,
                        event.absolute_tick,
                        tuple(item.event_id for item in selection.events) + (event.event_id,),
                    )
                )
                continue
            previous = changes[state.pending_data_index]
            changes[state.pending_data_index] = replace(
                previous,
                value_lsb=event.value,
                end_tick=event.absolute_tick,
                event_ids=previous.event_ids + (event.event_id,),
                track_indices=tuple(sorted(set(previous.track_indices + (event.track_index,)))),
            )
            state.pending_data_index = None
            continue

        operation = {
            6: ParameterOperation.DATA_ENTRY,
            96: ParameterOperation.INCREMENT,
            97: ParameterOperation.DECREMENT,
        }[event.controller]
        logical_events = tuple(item.event_id for item in selection.events) + (event.event_id,)
        tracks = tuple(sorted({item.track_index for item in selection.events} | {event.track_index}))
        change = ParameterChange(
            selection.kind,
            operation,
            event.channel,
            selection.msb,
            selection.lsb,
            event.value if operation is ParameterOperation.DATA_ENTRY else None,
            None,
            event.value if operation is not ParameterOperation.DATA_ENTRY else None,
            selection.events[0].absolute_tick,
            event.absolute_tick,
            logical_events,
            tracks,
            selection.ambiguous or len(tracks) > 1,
        )
        changes.append(change)
        selection.used = True
        state.pending_data_index = len(changes) - 1 if event.controller == 6 else None
        if len(tracks) > 1:
            issues.append(
                ParameterIssue(
                    "parameter_sequence_spans_tracks",
                    "NRPN/RPN selection and data entry span multiple tracks",
                    event.channel,
                    event.absolute_tick,
                    logical_events,
                )
            )

    for channel, state in states.items():
        for selection in state.selections.values():
            if not selection.events or selection.is_null or selection.used:
                continue
            code = "incomplete_parameter_selection" if not selection.complete else "selection_without_data"
            message = (
                "NRPN/RPN selection is missing MSB or LSB"
                if not selection.complete
                else "NRPN/RPN parameter was selected but no data operation followed"
            )
            issues.append(
                ParameterIssue(
                    code,
                    message,
                    channel,
                    selection.events[-1].absolute_tick,
                    tuple(item.event_id for item in selection.events),
                )
            )
    return ParameterAnalysis(tuple(changes), tuple(issues))


def _select(
    event: ControllerEvent,
    state: _ChannelState,
    issues: list[ParameterIssue],
) -> None:
    kind, component = SELECTORS[event.controller]
    current = state.selections[kind]
    previous_active = state.selection
    state.pending_data_index = None
    if state.active_kind is not None and state.active_kind is not kind:
        ambiguous = (
            previous_active is not None
            and bool(previous_active.events)
            and not previous_active.is_null
            and not previous_active.used
        )
        if ambiguous and previous_active is not None:
            issues.append(
                ParameterIssue(
                    "interleaved_parameter_selection",
                    f"{kind.value.upper()} selection interrupts an active {previous_active.kind.value.upper()} selection",
                    event.channel,
                    event.absolute_tick,
                    tuple(item.event_id for item in previous_active.events) + (event.event_id,),
                )
            )
            current.ambiguous = True
    state.active_kind = kind

    component_event = getattr(current, f"{component}_event")
    if component_event is not None and not current.used:
        issues.append(
            ParameterIssue(
                "restarted_parameter_selection",
                f"{kind.value.upper()} {component.upper()} was replaced before a data operation",
                event.channel,
                event.absolute_tick,
                tuple(item.event_id for item in current.events) + (event.event_id,),
            )
        )
        current.ambiguous = True
    setattr(current, component, event.value)
    setattr(current, f"{component}_event", event)
    current.used = False
    if current.is_null:
        current.used = True
