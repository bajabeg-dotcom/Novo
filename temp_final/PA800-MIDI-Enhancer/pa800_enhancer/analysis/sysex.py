from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..domain.events import EventKind
from ..domain.song import Song


class SysexClassification(str, Enum):
    GM1_SYSTEM_ON = "gm1_system_on"
    GM_SYSTEM_OFF = "gm_system_off"
    GM2_SYSTEM_ON = "gm2_system_on"
    GS_RESET = "gs_reset"
    XG_SYSTEM_ON = "xg_system_on"
    UNKNOWN = "unknown"
    INCOMPLETE = "incomplete"
    MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class SysexMessage:
    event_ids: tuple[str, ...]
    track_index: int
    start_tick: int
    end_tick: int
    payload: bytes
    complete: bool
    classification: SysexClassification
    manufacturer_id: tuple[int, ...] | None
    manufacturer_name: str | None
    device_id: int | None
    description: str


@dataclass(frozen=True, slots=True)
class SysexIssue:
    code: str
    message: str
    track_index: int
    absolute_tick: int
    event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SysexAnalysis:
    messages: tuple[SysexMessage, ...]
    issues: tuple[SysexIssue, ...]

    @property
    def recognized_resets(self) -> tuple[SysexMessage, ...]:
        recognized = {
            SysexClassification.GM1_SYSTEM_ON,
            SysexClassification.GM_SYSTEM_OFF,
            SysexClassification.GM2_SYSTEM_ON,
            SysexClassification.GS_RESET,
            SysexClassification.XG_SYSTEM_ON,
        }
        return tuple(item for item in self.messages if item.classification in recognized)


@dataclass(slots=True)
class _Pending:
    event_ids: list[str]
    track_index: int
    start_tick: int
    end_tick: int
    payload: bytearray


def analyze_sysex(song: Song) -> SysexAnalysis:
    messages: list[SysexMessage] = []
    issues: list[SysexIssue] = []
    for track in song.tracks:
        pending: _Pending | None = None
        for event in track.events:
            if event.kind is not EventKind.SYSEX:
                continue
            if event.status == 0xF0:
                if pending is not None:
                    messages.append(_finish(pending, False))
                    issues.append(
                        SysexIssue(
                            "interrupted_sysex",
                            "a new F0 event starts before the previous SysEx message terminated",
                            track.index,
                            event.absolute_tick,
                            tuple(pending.event_ids),
                        )
                    )
                pending = _Pending(
                    [event.event_id],
                    track.index,
                    event.absolute_tick,
                    event.absolute_tick,
                    bytearray(event.data),
                )
                if _terminated(event.data):
                    messages.append(_finish(pending, True))
                    pending = None
            else:
                if pending is None:
                    message = _classify(
                        (event.event_id,),
                        track.index,
                        event.absolute_tick,
                        event.absolute_tick,
                        event.data,
                        _terminated(event.data),
                    )
                    messages.append(message)
                    issues.append(
                        SysexIssue(
                            "standalone_f7_escape",
                            "F7 escape event has no preceding unterminated F0 message",
                            track.index,
                            event.absolute_tick,
                            (event.event_id,),
                        )
                    )
                    continue
                pending.event_ids.append(event.event_id)
                pending.end_tick = event.absolute_tick
                pending.payload.extend(event.data)
                if _terminated(event.data):
                    messages.append(_finish(pending, True))
                    pending = None
        if pending is not None:
            messages.append(_finish(pending, False))
            issues.append(
                SysexIssue(
                    "unterminated_sysex",
                    "SysEx message reaches the end of its track without F7 termination",
                    track.index,
                    pending.end_tick,
                    tuple(pending.event_ids),
                )
            )

    for message in messages:
        invalid = [byte for byte in _body(message.payload) if byte > 0x7F]
        if invalid:
            issues.append(
                SysexIssue(
                    "invalid_sysex_data_byte",
                    "SysEx data contains a byte above 0x7F",
                    message.track_index,
                    message.start_tick,
                    message.event_ids,
                )
            )
        elif message.classification is SysexClassification.MALFORMED:
            issues.append(
                SysexIssue(
                    "malformed_known_sysex",
                    message.description,
                    message.track_index,
                    message.start_tick,
                    message.event_ids,
                )
            )
    return SysexAnalysis(tuple(messages), tuple(issues))


def _finish(pending: _Pending, complete: bool) -> SysexMessage:
    return _classify(
        tuple(pending.event_ids),
        pending.track_index,
        pending.start_tick,
        pending.end_tick,
        bytes(pending.payload),
        complete,
    )


def _classify(
    event_ids: tuple[str, ...],
    track_index: int,
    start_tick: int,
    end_tick: int,
    payload: bytes,
    complete: bool,
) -> SysexMessage:
    body = _body(payload)
    manufacturer_id, manufacturer_name = _manufacturer(body)
    device_id: int | None = None
    classification = SysexClassification.UNKNOWN
    description = "unknown SysEx preserved verbatim"

    if not complete:
        classification = SysexClassification.INCOMPLETE
        description = "unterminated SysEx preserved verbatim"
    elif any(byte > 0x7F for byte in body):
        classification = SysexClassification.MALFORMED
        description = "SysEx contains an invalid data byte and is preserved verbatim"
    elif len(body) == 4 and body[0] == 0x7E and body[2] == 0x09:
        device_id = body[1]
        universal = {
            0x01: (SysexClassification.GM1_SYSTEM_ON, "General MIDI Level 1 System On"),
            0x02: (SysexClassification.GM_SYSTEM_OFF, "General MIDI System Off"),
            0x03: (SysexClassification.GM2_SYSTEM_ON, "General MIDI Level 2 System On"),
        }.get(body[3])
        if universal is not None:
            classification, description = universal
    elif (
        len(body) == 7
        and body[0] == 0x43
        and 0x10 <= body[1] <= 0x1F
        and body[2:] == bytes.fromhex("4c00007e00")
    ):
        device_id = body[1] & 0x0F
        classification = SysexClassification.XG_SYSTEM_ON
        description = "Yamaha XG System On"
    elif (
        len(body) == 9
        and body[0] == 0x41
        and (0x10 <= body[1] <= 0x1F or body[1] == 0x7F)
        and body[2:8] == bytes.fromhex("421240007f00")
    ):
        device_id = body[1]
        if sum(body[4:9]) % 128 == 0:
            classification = SysexClassification.GS_RESET
            description = "Roland GS Reset"
        else:
            classification = SysexClassification.MALFORMED
            description = "GS Reset-shaped message has an invalid Roland checksum"

    return SysexMessage(
        event_ids,
        track_index,
        start_tick,
        end_tick,
        payload,
        complete,
        classification,
        manufacturer_id,
        manufacturer_name,
        device_id,
        description,
    )


def _body(payload: bytes) -> bytes:
    return payload[:-1] if payload.endswith(b"\xF7") else payload


def _terminated(payload: bytes) -> bool:
    return payload.endswith(b"\xF7")


def _manufacturer(body: bytes) -> tuple[tuple[int, ...] | None, str | None]:
    if not body:
        return None, None
    first = body[0]
    if first == 0x7E:
        return (first,), "Universal Non-Real Time"
    if first == 0x7F:
        return (first,), "Universal Real Time"
    if first == 0x00:
        if len(body) < 3:
            return None, None
        return tuple(body[:3]), None
    names = {0x41: "Roland", 0x42: "Korg", 0x43: "Yamaha"}
    return (first,), names.get(first)