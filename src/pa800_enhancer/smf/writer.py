from pathlib import Path

from ..domain.events import EventKind, MidiEvent
from ..domain.song import Song, Track
from .errors import PreserveMismatchError
from .vlq import encode_vlq


class SmfWriter:
    def write(self, song: Song, path: Path) -> None:
        payload = self.serialize(song)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def serialize(self, song: Song) -> bytes:
        header = (
            b"MThd"
            + (6).to_bytes(4, "big")
            + song.header.format_type.to_bytes(2, "big")
            + len(song.tracks).to_bytes(2, "big")
            + song.header.division.to_bytes(2, "big")
        )
        return header + b"".join(self._serialize_track(track) for track in song.tracks)

    def _serialize_track(self, track: Track) -> bytes:
        body = bytearray()
        last_tick = 0
        events = sorted(track.events, key=lambda event: (event.absolute_tick, event.order))
        for event in events:
            if event.absolute_tick < last_tick:
                raise ValueError("events are not monotonic")
            body.extend(encode_vlq(event.absolute_tick - last_tick))
            body.extend(self._serialize_event(event))
            last_tick = event.absolute_tick
        payload = bytes(body)
        return b"MTrk" + len(payload).to_bytes(4, "big") + payload

    @staticmethod
    def _serialize_event(event: MidiEvent) -> bytes:
        if event.kind is EventKind.CHANNEL:
            return bytes([event.status]) + event.data
        if event.kind is EventKind.SYSEX:
            return bytes([event.status]) + encode_vlq(len(event.data)) + event.data
        if event.kind is EventKind.META and event.meta_type is not None:
            return b"\xFF" + bytes([event.meta_type]) + encode_vlq(len(event.data)) + event.data
        raise ValueError(f"cannot serialize event {event.event_id}")


class PreserveWriter:
    """Writes the exact imported bytes only while the semantic model is unchanged."""

    def write(self, song: Song, path: Path) -> None:
        payload = self.serialize(song)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    @staticmethod
    def serialize(song: Song) -> bytes:
        raw = song.raw_document
        if raw is None:
            raise PreserveMismatchError("song has no imported raw document")
        if not raw.matches(song):
            raise PreserveMismatchError("song differs from the imported semantic snapshot")
        return raw.source_bytes


class SegmentPreserveWriter:
    """Rebuilds changed tracks while preserving every reusable original segment."""

    def write(self, song: Song, path: Path) -> None:
        payload = self.serialize(song)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def serialize(self, song: Song) -> bytes:
        raw = song.raw_document
        if raw is None:
            raise PreserveMismatchError("song has no imported raw document")
        header = (song.header.format_type, len(song.tracks), song.header.division)
        if header != raw.header_snapshot:
            raise PreserveMismatchError("SMF header differs from imported document")
        if len(song.tracks) != len(raw.event_snapshots):
            raise PreserveMismatchError("track structure differs from imported document")
        for track, snapshots in zip(song.tracks, raw.event_snapshots, strict=True):
            if len(track.events) != len(snapshots):
                raise PreserveMismatchError("event count differs from imported document")
            if tuple(event.event_id for event in track.events) != tuple(item[0] for item in snapshots):
                raise PreserveMismatchError("event identity/order differs from imported document")

        output = bytearray()
        for chunk in raw.chunks:
            if chunk.chunk_id == b"MTrk" and chunk.track_index is not None:
                output.extend(self._serialize_track(song.tracks[chunk.track_index], raw.source_bytes, raw.event_snapshots[chunk.track_index]))
            else:
                output.extend(chunk.full_span.slice(raw.source_bytes))
        if raw.trailing_span:
            output.extend(raw.trailing_span.slice(raw.source_bytes))
        return bytes(output)

    def _serialize_track(self, track: Track, source: bytes, snapshots: tuple) -> bytes:
        body = bytearray()
        previous_tick = 0
        running_status: int | None = None
        for event, snapshot in zip(track.events, snapshots, strict=True):
            if event.absolute_tick < previous_tick:
                raise PreserveMismatchError("changed events are not monotonic")
            body.extend(encode_vlq(event.absolute_tick - previous_tick))
            message_unchanged = (
                event.status == snapshot[3]
                and event.kind.value == snapshot[4]
                and event.data == snapshot[5]
                and event.meta_type == snapshot[6]
            )
            raw_message = event.raw_message_span.slice(source) if message_unchanged and event.raw_message_span else None
            if raw_message is not None:
                if event.kind is EventKind.CHANNEL and raw_message and raw_message[0] < 0x80 and running_status != event.status:
                    raw_message = None
            message = raw_message if raw_message is not None else SmfWriter._serialize_event(event)
            body.extend(message)
            if event.kind is EventKind.CHANNEL:
                running_status = event.status
            else:
                running_status = None
            previous_tick = event.absolute_tick
        payload = bytes(body)
        return b"MTrk" + len(payload).to_bytes(4, "big") + payload


CanonicalWriter = SmfWriter