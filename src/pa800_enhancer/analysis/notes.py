from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

from ..domain.events import MidiEvent
from ..domain.song import Song


class NotePairingPolicy(str, Enum):
    FIFO = "fifo"
    LIFO = "lifo"


@dataclass(frozen=True, slots=True)
class Note:
    channel: int
    note: int
    start_tick: int
    end_tick: int
    audible_end_tick: int
    velocity: int
    release_velocity: int
    on_event_id: str
    off_event_id: str
    sustained: bool = False
    sustain_pedal: bool = False
    sostenuto_pedal: bool = False
    sustained_to_end: bool = False
    ambiguous_pairing: bool = False


@dataclass(slots=True)
class _PendingNote:
    start: MidiEvent
    end: MidiEvent
    held_by_sustain: bool
    held_by_sostenuto: bool
    used_sustain: bool
    used_sostenuto: bool
    ambiguous: bool


def _make_note(
    start: MidiEvent,
    end: MidiEvent,
    audible_end_tick: int,
    *,
    used_sustain: bool = False,
    used_sostenuto: bool = False,
    sustained_to_end: bool = False,
    ambiguous: bool = False,
) -> Note:
    release_velocity = end.data[1] if end.is_note_off and len(end.data) == 2 else 0
    return Note(
        channel=start.channel or 1,
        note=start.data[0],
        start_tick=start.absolute_tick,
        end_tick=end.absolute_tick,
        audible_end_tick=max(end.absolute_tick, audible_end_tick),
        velocity=start.data[1],
        release_velocity=release_velocity,
        on_event_id=start.event_id,
        off_event_id=end.event_id,
        sustained=used_sustain or used_sostenuto,
        sustain_pedal=used_sustain,
        sostenuto_pedal=used_sostenuto,
        sustained_to_end=sustained_to_end,
        ambiguous_pairing=ambiguous,
    )


def pair_notes(song: Song, policy: NotePairingPolicy = NotePairingPolicy.FIFO) -> tuple[list[Note], list[MidiEvent]]:
    active: dict[tuple[int, int], deque[MidiEvent]] = defaultdict(deque)
    pending: dict[int, list[_PendingNote]] = defaultdict(list)
    sustain: dict[int, bool] = defaultdict(bool)
    sostenuto: dict[int, bool] = defaultdict(bool)
    sostenuto_captured: dict[int, set[str]] = defaultdict(set)
    ambiguous_on_ids: set[str] = set()
    notes: list[Note] = []
    unmatched: list[MidiEvent] = []

    def release_pending(channel: int, tick: int, pedal: str) -> None:
        remaining: list[_PendingNote] = []
        for item in pending[channel]:
            if pedal == "sustain":
                item.held_by_sustain = False
            elif pedal == "sostenuto":
                item.held_by_sostenuto = False
            if item.held_by_sustain or item.held_by_sostenuto:
                remaining.append(item)
            else:
                notes.append(
                    _make_note(
                        item.start,
                        item.end,
                        tick,
                        used_sustain=item.used_sustain,
                        used_sostenuto=item.used_sostenuto,
                        ambiguous=item.ambiguous,
                    )
                )
        pending[channel] = remaining

    events = sorted(
        (event for track in song.tracks for event in track.events),
        key=lambda event: (event.absolute_tick, event.track_index, event.order),
    )
    for event in events:
        channel = event.channel
        if channel is None:
            continue
        if event.message_type == 0xB0 and len(event.data) == 2:
            controller, value = event.data
            if controller == 64:
                was_down = sustain[channel]
                sustain[channel] = value >= 64
                if was_down and not sustain[channel]:
                    release_pending(channel, event.absolute_tick, "sustain")
                continue
            if controller == 66:
                was_down = sostenuto[channel]
                sostenuto[channel] = value >= 64
                if not was_down and sostenuto[channel]:
                    sostenuto_captured[channel] = {
                        active_event.event_id
                        for (active_channel, _), queue in active.items()
                        if active_channel == channel
                        for active_event in queue
                    }
                elif was_down and not sostenuto[channel]:
                    release_pending(channel, event.absolute_tick, "sostenuto")
                    sostenuto_captured[channel].clear()
                continue
            if controller == 121:
                if sustain[channel]:
                    sustain[channel] = False
                    release_pending(channel, event.absolute_tick, "sustain")
                if sostenuto[channel]:
                    sostenuto[channel] = False
                    release_pending(channel, event.absolute_tick, "sostenuto")
                    sostenuto_captured[channel].clear()
                continue
        if len(event.data) < 2:
            continue
        key = (channel, event.data[0])
        if event.is_note_on:
            if active[key]:
                ambiguous_on_ids.update(item.event_id for item in active[key])
                ambiguous_on_ids.add(event.event_id)
            active[key].append(event)
        elif event.is_note_off:
            if not active[key]:
                unmatched.append(event)
                continue
            start = active[key].popleft() if policy is NotePairingPolicy.FIFO else active[key].pop()
            held_sustain = sustain[channel]
            held_sostenuto = sostenuto[channel] and start.event_id in sostenuto_captured[channel]
            ambiguous = start.event_id in ambiguous_on_ids
            if held_sustain or held_sostenuto:
                pending[channel].append(
                    _PendingNote(start, event, held_sustain, held_sostenuto, held_sustain, held_sostenuto, ambiguous)
                )
            else:
                notes.append(_make_note(start, event, event.absolute_tick, ambiguous=ambiguous))
    unmatched.extend(event for queue in active.values() for event in queue)
    for channel_pending in pending.values():
        notes.extend(
            _make_note(
                item.start,
                item.end,
                song.end_tick,
                used_sustain=item.used_sustain,
                used_sostenuto=item.used_sostenuto,
                sustained_to_end=True,
                ambiguous=item.ambiguous,
            )
            for item in channel_pending
        )
    notes.sort(key=lambda note: (note.start_tick, note.channel, note.note, note.end_tick))
    return notes, unmatched


def maximum_polyphony(notes: list[Note]) -> int:
    boundaries: list[tuple[int, int]] = []
    for note in notes:
        boundaries.append((note.start_tick, 1))
        boundaries.append((note.audible_end_tick, -1))
    active = peak = 0
    for _, delta in sorted(boundaries, key=lambda item: (item[0], item[1])):
        active += delta
        peak = max(peak, active)
    return peak