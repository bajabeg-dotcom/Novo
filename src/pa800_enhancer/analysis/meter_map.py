from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction

from ..domain.song import Song


@dataclass(frozen=True, slots=True)
class MeterChange:
    tick: int
    numerator: int
    denominator: int
    clocks_per_click: int = 24
    notated_32nds_per_quarter: int = 8


@dataclass(frozen=True, slots=True)
class MusicalPosition:
    bar: int
    beat: int
    tick_in_beat: Fraction
    numerator: int
    denominator: int


class MeterMap:
    def __init__(self, song: Song) -> None:
        ppq = song.header.ppq
        if not ppq:
            raise ValueError("meter position requires PPQ time division")
        self.ppq = ppq
        changes = [
            MeterChange(event.absolute_tick, event.data[0], 1 << event.data[1], event.data[2], event.data[3])
            for track in song.tracks
            for event in track.events
            if event.meta_type == 0x58 and len(event.data) == 4 and event.data[0] > 0
        ]
        changes.sort(key=lambda item: item.tick)
        collapsed: list[MeterChange] = []
        for change in changes:
            if collapsed and collapsed[-1].tick == change.tick:
                collapsed[-1] = change
            else:
                collapsed.append(change)
        if not collapsed or collapsed[0].tick != 0:
            collapsed.insert(0, MeterChange(0, 4, 4))
        self.changes = tuple(collapsed)
        self._ticks = tuple(change.tick for change in self.changes)
        self._start_bars = self._build_start_bars()

    def ticks_per_beat(self, change: MeterChange) -> Fraction:
        return Fraction(self.ppq * 4, change.denominator)

    def ticks_per_bar(self, change: MeterChange) -> Fraction:
        return self.ticks_per_beat(change) * change.numerator

    def _build_start_bars(self) -> tuple[int, ...]:
        starts = [1]
        for previous, current in zip(self.changes, self.changes[1:]):
            span = Fraction(current.tick - previous.tick, 1)
            bar_length = self.ticks_per_bar(previous)
            completed = int(span // bar_length)
            if span % bar_length:
                completed += 1
            starts.append(starts[-1] + completed)
        return tuple(starts)

    def position(self, tick: int) -> MusicalPosition:
        if tick < 0:
            raise ValueError("tick must be non-negative")
        index = max(0, bisect_right(self._ticks, tick) - 1)
        change = self.changes[index]
        relative = Fraction(tick - change.tick, 1)
        beat_length = self.ticks_per_beat(change)
        bar_length = self.ticks_per_bar(change)
        bar_offset = int(relative // bar_length)
        within_bar = relative - bar_offset * bar_length
        beat_offset = int(within_bar // beat_length)
        tick_in_beat = within_bar - beat_offset * beat_length
        return MusicalPosition(self._start_bars[index] + bar_offset, beat_offset + 1, tick_in_beat, change.numerator, change.denominator)
