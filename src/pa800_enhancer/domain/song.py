from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from .events import MidiEvent
from .raw import RawDocument


@dataclass(frozen=True, slots=True)
class SmfHeader:
    format_type: int
    track_count: int
    division: int

    @property
    def uses_smpte(self) -> bool:
        return bool(self.division & 0x8000)

    @property
    def ppq(self) -> int | None:
        return None if self.uses_smpte else self.division

    @property
    def smpte_fps_code(self) -> int | None:
        if not self.uses_smpte:
            return None
        unsigned = (self.division >> 8) & 0xFF
        return unsigned - 256 if unsigned >= 128 else unsigned

    @property
    def smpte_ticks_per_frame(self) -> int | None:
        return self.division & 0xFF if self.uses_smpte else None

    @property
    def smpte_frames_per_second(self) -> Fraction | None:
        code = self.smpte_fps_code
        if code is None:
            return None
        if code == -29:
            return Fraction(30_000, 1_001)
        if code in (-24, -25, -30):
            return Fraction(-code, 1)
        return None


@dataclass(slots=True)
class Track:
    index: int
    events: list[MidiEvent] = field(default_factory=list)

    @property
    def end_tick(self) -> int:
        return max((event.absolute_tick for event in self.events), default=0)


@dataclass(slots=True)
class Song:
    header: SmfHeader
    tracks: list[Track]
    source_path: Path | None = None
    source_sha256: str | None = None
    raw_document: RawDocument | None = None

    @property
    def event_count(self) -> int:
        return sum(len(track.events) for track in self.tracks)

    @property
    def end_tick(self) -> int:
        return max((track.end_tick for track in self.tracks), default=0)
