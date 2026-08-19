from dataclasses import dataclass, replace
from enum import Enum

from .raw import RawSpan


class EventKind(str, Enum):
    CHANNEL = "channel"
    META = "meta"
    SYSEX = "sysex"


@dataclass(frozen=True, slots=True)
class MidiEvent:
    event_id: str
    kind: EventKind
    absolute_tick: int
    track_index: int
    order: int
    status: int
    data: bytes = b""
    meta_type: int | None = None
    original_delta_time: int = 0
    raw_span: RawSpan | None = None
    raw_delta_span: RawSpan | None = None
    raw_message_span: RawSpan | None = None

    @property
    def channel(self) -> int | None:
        return (self.status & 0x0F) + 1 if self.kind is EventKind.CHANNEL else None

    @property
    def message_type(self) -> int:
        return self.status & 0xF0

    @property
    def is_note_on(self) -> bool:
        return self.message_type == 0x90 and len(self.data) == 2 and self.data[1] > 0

    @property
    def is_note_off(self) -> bool:
        return self.message_type == 0x80 or (
            self.message_type == 0x90 and len(self.data) == 2 and self.data[1] == 0
        )

    def moved(self, absolute_tick: int) -> "MidiEvent":
        if absolute_tick < 0:
            raise ValueError("absolute_tick must be non-negative")
        return replace(self, absolute_tick=absolute_tick)