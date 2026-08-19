from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction

from ..domain.song import Song


@dataclass(frozen=True, slots=True)
class TempoChange:
    tick: int
    microseconds_per_quarter: int

    @property
    def bpm(self) -> Fraction:
        return Fraction(60_000_000, self.microseconds_per_quarter)


class TempoMap:
    def __init__(self, song: Song) -> None:
        self.header = song.header
        changes = [
            TempoChange(event.absolute_tick, int.from_bytes(event.data, "big"))
            for track in song.tracks
            for event in track.events
            if event.meta_type == 0x51 and len(event.data) == 3 and int.from_bytes(event.data, "big") > 0
        ]
        changes.sort(key=lambda item: item.tick)
        collapsed: list[TempoChange] = []
        for change in changes:
            if collapsed and collapsed[-1].tick == change.tick:
                collapsed[-1] = change
            else:
                collapsed.append(change)
        if not collapsed or collapsed[0].tick != 0:
            collapsed.insert(0, TempoChange(0, 500_000))
        self.changes = tuple(collapsed)
        self._ticks = tuple(item.tick for item in self.changes)
        self._segment_microseconds = self._build_segment_offsets()

    def _build_segment_offsets(self) -> tuple[Fraction, ...]:
        if self.header.uses_smpte:
            return tuple(Fraction(0) for _ in self.changes)
        ppq = self.header.ppq
        if not ppq:
            raise ValueError("invalid PPQ time division")
        offsets: list[Fraction] = [Fraction(0)]
        for previous, current in zip(self.changes, self.changes[1:]):
            duration = current.tick - previous.tick
            offsets.append(offsets[-1] + Fraction(duration * previous.microseconds_per_quarter, ppq))
        return tuple(offsets)

    def tick_to_microseconds(self, tick: int) -> Fraction:
        if tick < 0:
            raise ValueError("tick must be non-negative")
        if self.header.uses_smpte:
            fps = self.header.smpte_frames_per_second
            ticks_per_frame = self.header.smpte_ticks_per_frame
            if not fps or not ticks_per_frame:
                raise ValueError("unsupported SMPTE time division")
            return Fraction(tick * 1_000_000, 1) / (fps * ticks_per_frame)
        index = max(0, bisect_right(self._ticks, tick) - 1)
        change = self.changes[index]
        return self._segment_microseconds[index] + Fraction((tick - change.tick) * change.microseconds_per_quarter, self.header.ppq)

    def tick_to_seconds(self, tick: int) -> Fraction:
        return self.tick_to_microseconds(tick) / 1_000_000

    def microseconds_to_tick(self, microseconds: int | Fraction) -> Fraction:
        value = Fraction(microseconds)
        if value < 0:
            raise ValueError("microseconds must be non-negative")
        if self.header.uses_smpte:
            fps = self.header.smpte_frames_per_second
            ticks_per_frame = self.header.smpte_ticks_per_frame
            if not fps or not ticks_per_frame:
                raise ValueError("unsupported SMPTE time division")
            return value * fps * ticks_per_frame / 1_000_000
        index = max(0, bisect_right(self._segment_microseconds, value) - 1)
        change = self.changes[index]
        elapsed = value - self._segment_microseconds[index]
        return Fraction(change.tick, 1) + elapsed * self.header.ppq / change.microseconds_per_quarter

    def seconds_to_tick(self, seconds: int | Fraction) -> Fraction:
        return self.microseconds_to_tick(Fraction(seconds) * 1_000_000)
