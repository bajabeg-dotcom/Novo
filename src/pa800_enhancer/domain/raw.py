from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .song import Song


@dataclass(frozen=True, slots=True)
class RawSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("invalid raw byte span")

    @property
    def length(self) -> int:
        return self.end - self.start

    def slice(self, data: bytes) -> bytes:
        return data[self.start : self.end]


@dataclass(frozen=True, slots=True)
class RawChunk:
    chunk_id: bytes
    full_span: RawSpan
    header_span: RawSpan
    data_span: RawSpan
    declared_length: int
    track_index: int | None = None

    @property
    def is_known(self) -> bool:
        return self.chunk_id in (b"MThd", b"MTrk")


EventSnapshot = tuple[str, int, int, int, str, bytes, int | None]


@dataclass(frozen=True, slots=True)
class RawDocument:
    source_bytes: bytes
    chunks: tuple[RawChunk, ...]
    header_snapshot: tuple[int, int, int]
    event_snapshots: tuple[tuple[EventSnapshot, ...], ...]
    trailing_span: RawSpan | None = None

    @property
    def unknown_chunks(self) -> tuple[RawChunk, ...]:
        return tuple(chunk for chunk in self.chunks if not chunk.is_known)

    def matches(self, song: "Song") -> bool:
        header = (song.header.format_type, len(song.tracks), song.header.division)
        if header != self.header_snapshot or len(song.tracks) != len(self.event_snapshots):
            return False
        snapshots = tuple(
            tuple(
                (
                    event.event_id,
                    event.absolute_tick,
                    event.order,
                    event.status,
                    event.kind.value,
                    event.data,
                    event.meta_type,
                )
                for event in track.events
            )
            for track in song.tracks
        )
        return snapshots == self.event_snapshots


def snapshot_song(song: "Song") -> tuple[tuple[EventSnapshot, ...], ...]:
    return tuple(
        tuple(
            (
                event.event_id,
                event.absolute_tick,
                event.order,
                event.status,
                event.kind.value,
                event.data,
                event.meta_type,
            )
            for event in track.events
        )
        for track in song.tracks
    )
