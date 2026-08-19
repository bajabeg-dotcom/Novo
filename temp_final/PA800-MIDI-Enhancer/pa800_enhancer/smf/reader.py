import hashlib
from pathlib import Path

from ..domain.events import EventKind, MidiEvent
from ..domain.raw import RawChunk, RawDocument, RawSpan, snapshot_song
from ..domain.song import SmfHeader, Song, Track
from .errors import SmfStructureError
from .vlq import decode_vlq


_DATA_LENGTH = {
    0x80: 2,
    0x90: 2,
    0xA0: 2,
    0xB0: 2,
    0xC0: 1,
    0xD0: 1,
    0xE0: 2,
}


class SmfReader:
    def __init__(
        self,
        max_file_size: int = 64 * 1024 * 1024,
        max_tracks: int = 1024,
        max_chunks: int = 4096,
        max_chunk_size: int = 32 * 1024 * 1024,
        max_events_per_track: int = 2_000_000,
    ) -> None:
        self.max_file_size = max_file_size
        self.max_tracks = max_tracks
        self.max_chunks = max_chunks
        self.max_chunk_size = max_chunk_size
        self.max_events_per_track = max_events_per_track

    def read(self, path: Path) -> Song:
        size = path.stat().st_size
        if size > self.max_file_size:
            raise SmfStructureError("file exceeds configured size limit", offset=size)
        with path.open("rb") as stream:
            data = stream.read(self.max_file_size + 1)
        if len(data) > self.max_file_size:
            raise SmfStructureError("file exceeds configured size limit", offset=len(data))
        song = self.parse(data)
        song.source_path = path
        return song

    def parse(self, data: bytes) -> Song:
        if len(data) > self.max_file_size:
            raise SmfStructureError("file exceeds configured size limit", offset=len(data))
        if len(data) < 8 or data[:4] != b"MThd":
            raise SmfStructureError("missing MThd header", offset=0)
        header_length = int.from_bytes(data[4:8], "big")
        header_end = 8 + header_length
        if header_length < 6 or header_end > len(data):
            raise SmfStructureError("invalid MThd length", offset=4, context="MThd")
        format_type = int.from_bytes(data[8:10], "big")
        track_count = int.from_bytes(data[10:12], "big")
        division = int.from_bytes(data[12:14], "big")
        if format_type not in (0, 1, 2):
            raise SmfStructureError(f"unsupported SMF format {format_type}", offset=8, context="MThd")
        if track_count > self.max_tracks:
            raise SmfStructureError("declared track count exceeds configured limit", offset=10, context="MThd")

        chunks: list[RawChunk] = [
            RawChunk(
                b"MThd",
                RawSpan(0, header_end),
                RawSpan(0, 8),
                RawSpan(8, header_end),
                header_length,
            )
        ]
        tracks: list[Track] = []
        offset = header_end
        trailing_span: RawSpan | None = None

        while offset < len(data) and len(tracks) < track_count:
            if len(chunks) >= self.max_chunks:
                raise SmfStructureError("chunk count exceeds configured limit", offset=offset)
            if offset + 8 > len(data):
                trailing_span = RawSpan(offset, len(data))
                break
            chunk_id = data[offset : offset + 4]
            length = int.from_bytes(data[offset + 4 : offset + 8], "big")
            if length > self.max_chunk_size:
                raise SmfStructureError("chunk exceeds configured size limit", offset=offset + 4, context=chunk_id.decode("latin1"))
            payload_start = offset + 8
            chunk_end = payload_start + length
            if chunk_end > len(data):
                raise SmfStructureError("truncated chunk payload", offset=offset + 4, context=chunk_id.decode("latin1"))
            track_index = len(tracks) if chunk_id == b"MTrk" else None
            chunks.append(
                RawChunk(
                    chunk_id,
                    RawSpan(offset, chunk_end),
                    RawSpan(offset, payload_start),
                    RawSpan(payload_start, chunk_end),
                    length,
                    track_index,
                )
            )
            if chunk_id == b"MTrk":
                tracks.append(self._parse_track(data[payload_start:chunk_end], track_index, payload_start))
            offset = chunk_end

        if len(tracks) != track_count:
            raise SmfStructureError(
                f"expected {track_count} MTrk chunks, found {len(tracks)}",
                offset=offset,
            )

        while offset + 8 <= len(data):
            if len(chunks) >= self.max_chunks:
                raise SmfStructureError("chunk count exceeds configured limit", offset=offset)
            chunk_id = data[offset : offset + 4]
            length = int.from_bytes(data[offset + 4 : offset + 8], "big")
            if length > self.max_chunk_size:
                raise SmfStructureError("chunk exceeds configured size limit", offset=offset + 4, context=chunk_id.decode("latin1"))
            payload_start = offset + 8
            chunk_end = payload_start + length
            if chunk_end > len(data):
                trailing_span = RawSpan(offset, len(data))
                offset = len(data)
                break
            chunks.append(
                RawChunk(
                    chunk_id,
                    RawSpan(offset, chunk_end),
                    RawSpan(offset, payload_start),
                    RawSpan(payload_start, chunk_end),
                    length,
                )
            )
            offset = chunk_end
        if offset < len(data) and trailing_span is None:
            trailing_span = RawSpan(offset, len(data))

        header = SmfHeader(format_type, track_count, division)
        song = Song(
            header=header,
            tracks=tracks,
            source_sha256=hashlib.sha256(data).hexdigest(),
        )
        song.raw_document = RawDocument(
            source_bytes=data,
            chunks=tuple(chunks),
            header_snapshot=(format_type, track_count, division),
            event_snapshots=snapshot_song(song),
            trailing_span=trailing_span,
        )
        return song

    def _decode_vlq(self, data: bytes, offset: int, base_offset: int, context: str) -> tuple[int, int]:
        try:
            return decode_vlq(data, offset)
        except SmfStructureError as error:
            raise SmfStructureError(error.message, offset=base_offset + offset, context=context) from error

    def _parse_track(self, data: bytes, track_index: int, base_offset: int) -> Track:
        events: list[MidiEvent] = []
        offset = 0
        tick = 0
        running_status: int | None = None
        order = 0
        while offset < len(data):
            if order >= self.max_events_per_track:
                raise SmfStructureError("event count exceeds configured per-track limit", offset=base_offset + offset, context=f"track {track_index}")
            event_start = offset
            delta, offset = self._decode_vlq(data, offset, base_offset, f"track {track_index} delta-time")
            message_start = offset
            tick += delta
            if offset >= len(data):
                raise SmfStructureError("event missing after delta-time", offset=base_offset + offset, context=f"track {track_index}")
            first = data[offset]
            if first < 0x80:
                if running_status is None:
                    raise SmfStructureError("running status without prior status", offset=base_offset + offset, context=f"track {track_index}")
                status = running_status
            else:
                status = first
                offset += 1
            event_id = f"t{track_index}:e{order}"
            kind: EventKind
            payload: bytes
            meta_type: int | None = None
            if status == 0xFF:
                kind = EventKind.META
                running_status = None
                if offset >= len(data):
                    raise SmfStructureError("truncated meta event", offset=base_offset + offset, context=f"track {track_index}")
                meta_type = data[offset]
                length, payload_start = self._decode_vlq(data, offset + 1, base_offset, f"track {track_index} meta length")
                payload_end = payload_start + length
                if payload_end > len(data):
                    raise SmfStructureError("truncated meta payload", offset=base_offset + payload_start, context=f"track {track_index}")
                payload = data[payload_start:payload_end]
                offset = payload_end
            elif status in (0xF0, 0xF7):
                kind = EventKind.SYSEX
                running_status = None
                length, payload_start = self._decode_vlq(data, offset, base_offset, f"track {track_index} SysEx length")
                payload_end = payload_start + length
                if payload_end > len(data):
                    raise SmfStructureError("truncated SysEx payload", offset=base_offset + payload_start, context=f"track {track_index}")
                payload = data[payload_start:payload_end]
                offset = payload_end
            elif 0x80 <= status <= 0xEF:
                kind = EventKind.CHANNEL
                running_status = status
                length = _DATA_LENGTH[status & 0xF0]
                event_end = offset + length
                if event_end > len(data):
                    raise SmfStructureError("truncated channel event", offset=base_offset + offset, context=f"track {track_index}")
                payload = data[offset:event_end]
                if any(byte > 0x7F for byte in payload):
                    raise SmfStructureError("channel data byte exceeds 127", offset=base_offset + offset, context=f"track {track_index}")
                offset = event_end
            else:
                raise SmfStructureError(f"unsupported status byte 0x{status:02X}", offset=base_offset + offset - 1, context=f"track {track_index}")
            events.append(
                MidiEvent(
                    event_id=event_id,
                    kind=kind,
                    absolute_tick=tick,
                    track_index=track_index,
                    order=order,
                    status=status,
                    data=payload,
                    meta_type=meta_type,
                    original_delta_time=delta,
                    raw_span=RawSpan(base_offset + event_start, base_offset + offset),
                    raw_delta_span=RawSpan(base_offset + event_start, base_offset + message_start),
                    raw_message_span=RawSpan(base_offset + message_start, base_offset + offset),
                )
            )
            order += 1
        return Track(index=track_index, events=events)