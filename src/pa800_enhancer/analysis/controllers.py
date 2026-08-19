from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..domain.events import EventKind, MidiEvent
from ..domain.song import Song


CHANNEL_MODE_NAMES = {
    120: "all_sound_off",
    121: "reset_all_controllers",
    122: "local_control",
    123: "all_notes_off",
    124: "omni_mode_off",
    125: "omni_mode_on",
    126: "mono_mode_on",
    127: "poly_mode_on",
}


@dataclass(frozen=True, slots=True)
class ControllerEvent:
    event_id: str
    absolute_tick: int
    track_index: int
    order: int
    channel: int
    controller: int
    value: int

    @property
    def is_channel_mode(self) -> bool:
        return self.controller in CHANNEL_MODE_NAMES

    @property
    def channel_mode_name(self) -> str | None:
        return CHANNEL_MODE_NAMES.get(self.controller)


@dataclass(frozen=True, slots=True)
class ControllerValue:
    channel: int
    controller: int
    value: int
    event_id: str
    absolute_tick: int


@dataclass(frozen=True, slots=True)
class ControllerAnalysis:
    events: tuple[ControllerEvent, ...]
    final_values: tuple[ControllerValue, ...]
    counts: dict[int, int]
    channel_mode_events: tuple[ControllerEvent, ...]


def controller_events(song: Song) -> tuple[ControllerEvent, ...]:
    events: list[ControllerEvent] = []
    for track in song.tracks:
        for event in track.events:
            if not _is_control_change(event):
                continue
            channel = event.channel
            if channel is None:
                continue
            events.append(
                ControllerEvent(
                    event.event_id,
                    event.absolute_tick,
                    event.track_index,
                    event.order,
                    channel,
                    event.data[0],
                    event.data[1],
                )
            )
    return tuple(
        sorted(events, key=lambda item: (item.absolute_tick, item.track_index, item.order))
    )


def analyze_controllers(song: Song) -> ControllerAnalysis:
    events = controller_events(song)
    latest: dict[tuple[int, int], ControllerEvent] = {}
    counts: Counter[int] = Counter()
    modes: list[ControllerEvent] = []
    for event in events:
        latest[(event.channel, event.controller)] = event
        counts[event.controller] += 1
        if event.is_channel_mode:
            modes.append(event)
    final_values = tuple(
        ControllerValue(
            event.channel,
            event.controller,
            event.value,
            event.event_id,
            event.absolute_tick,
        )
        for _key, event in sorted(latest.items())
    )
    return ControllerAnalysis(events, final_values, dict(sorted(counts.items())), tuple(modes))


def _is_control_change(event: MidiEvent) -> bool:
    return (
        event.kind is EventKind.CHANNEL
        and event.message_type == 0xB0
        and len(event.data) == 2
    )
