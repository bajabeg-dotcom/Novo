"""Nezavisan, dependency-free SMF čitač za forenziku.

Namjerno NE koristi pa800_enhancer kod: forenzika mora biti nezavisna od
sistema koji provjerava. Ako se oba slože, nalaz je jači; ako se ne slože,
to je samo po sebi nalaz.

Vraća sirove činjenice, bez interpretacije.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Any


class SmfError(Exception):
    """Strukturna greška u SMF datoteci."""


@dataclass
class TrackFacts:
    index: int
    byte_length: int
    event_count: int
    note_on: int = 0
    note_off: int = 0
    running_status_events: int = 0
    channels: set[int] = field(default_factory=set)
    programs: set[int] = field(default_factory=set)
    controllers: dict[int, int] = field(default_factory=dict)
    cc0_values: set[int] = field(default_factory=set)
    cc32_values: set[int] = field(default_factory=set)
    pitch_bend: int = 0
    sysex_count: int = 0
    sysex_bytes: int = 0
    meta_types: dict[int, int] = field(default_factory=dict)
    text_meta: list[str] = field(default_factory=list)
    end_tick: int = 0
    has_eot: bool = False
    trailing_bytes: int = 0
    velocities: list[int] = field(default_factory=list)
    note_numbers: list[int] = field(default_factory=list)
    zero_velocity_note_on: int = 0
    tempos: list[tuple[int, int]] = field(default_factory=list)
    meters: list[tuple[int, int, int]] = field(default_factory=list)
    key_sigs: list[tuple[int, int, int]] = field(default_factory=list)


@dataclass
class MidiFacts:
    path: str
    size: int
    sha256: str
    fmt: int
    declared_tracks: int
    actual_tracks: int
    division_raw: int
    ppq: int | None
    smpte: tuple[int, int] | None
    tracks: list[TrackFacts]
    warnings: list[str] = field(default_factory=list)
    header_extra_bytes: int = 0
    trailing_file_bytes: int = 0

    @property
    def end_tick(self) -> int:
        return max((t.end_tick for t in self.tracks), default=0)

    @property
    def note_on(self) -> int:
        return sum(t.note_on for t in self.tracks)

    @property
    def channels(self) -> set[int]:
        out: set[int] = set()
        for t in self.tracks:
            out |= t.channels
        return out


def _vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    start = pos
    while True:
        if pos >= len(data):
            raise SmfError(f"VLQ prelazi kraj podataka na {start}")
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos
        if pos - start > 4:
            raise SmfError(f"VLQ duži od 4 bajta na {start}")


_CHANNEL_LEN = {0x80: 2, 0x90: 2, 0xA0: 2, 0xB0: 2, 0xC0: 1, 0xD0: 1, 0xE0: 2}


def _parse_track(data: bytes, index: int, warnings: list[str]) -> TrackFacts:
    facts = TrackFacts(index=index, byte_length=len(data), event_count=0)
    pos = 0
    tick = 0
    status = 0

    while pos < len(data):
        try:
            delta, pos = _vlq(data, pos)
        except SmfError as exc:
            warnings.append(f"track{index}: {exc}")
            break
        tick += delta

        if pos >= len(data):
            warnings.append(f"track{index}: nedostaje status bajt na kraju")
            break

        byte = data[pos]
        if byte & 0x80:
            status = byte
            pos += 1
        else:
            if not status:
                warnings.append(f"track{index}: running status bez prethodnog statusa")
                break
            facts.running_status_events += 1

        facts.event_count += 1

        if status == 0xFF:
            if pos >= len(data):
                warnings.append(f"track{index}: skraćen meta event")
                break
            meta_type = data[pos]
            pos += 1
            try:
                length, pos = _vlq(data, pos)
            except SmfError as exc:
                warnings.append(f"track{index}: meta VLQ {exc}")
                break
            payload = data[pos : pos + length]
            if len(payload) != length:
                warnings.append(f"track{index}: meta payload skraćen")
                break
            pos += length
            facts.meta_types[meta_type] = facts.meta_types.get(meta_type, 0) + 1

            if meta_type == 0x2F:
                facts.has_eot = True
                facts.end_tick = tick
                if pos < len(data):
                    facts.trailing_bytes = len(data) - pos
                break
            if meta_type == 0x51 and length == 3:
                facts.tempos.append((tick, int.from_bytes(payload, "big")))
            elif meta_type == 0x58 and length >= 2:
                facts.meters.append((tick, payload[0], 1 << payload[1]))
            elif meta_type == 0x59 and length == 2:
                facts.key_sigs.append(
                    (tick, struct.unpack("b", payload[0:1])[0], payload[1])
                )
            elif meta_type in (0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
                try:
                    text = payload.decode("utf-8")
                except UnicodeDecodeError:
                    text = payload.decode("latin-1", "replace")
                text = text.strip()
                if text:
                    facts.text_meta.append(f"{meta_type:02X}:{text[:120]}")

        elif status in (0xF0, 0xF7):
            try:
                length, pos = _vlq(data, pos)
            except SmfError as exc:
                warnings.append(f"track{index}: sysex VLQ {exc}")
                break
            pos += length
            facts.sysex_count += 1
            facts.sysex_bytes += length

        elif status >= 0x80:
            high = status & 0xF0
            channel = (status & 0x0F) + 1
            need = _CHANNEL_LEN.get(high)
            if need is None:
                warnings.append(f"track{index}: nepoznat status 0x{status:02X}")
                break
            if pos + need > len(data):
                warnings.append(f"track{index}: skraćena kanalna poruka")
                break
            d1 = data[pos]
            d2 = data[pos + 1] if need == 2 else 0
            pos += need
            facts.channels.add(channel)

            if high == 0x90:
                if d2 == 0:
                    facts.note_off += 1
                    facts.zero_velocity_note_on += 1
                else:
                    facts.note_on += 1
                    facts.velocities.append(d2)
                    facts.note_numbers.append(d1)
            elif high == 0x80:
                facts.note_off += 1
            elif high == 0xB0:
                facts.controllers[d1] = facts.controllers.get(d1, 0) + 1
                if d1 == 0:
                    facts.cc0_values.add(d2)
                elif d1 == 32:
                    facts.cc32_values.add(d2)
            elif high == 0xC0:
                facts.programs.add(d1)
            elif high == 0xE0:
                facts.pitch_bend += 1
        else:
            warnings.append(f"track{index}: nevažeći status 0x{status:02X}")
            break

    if not facts.has_eot:
        facts.end_tick = tick
    return facts


def probe(path: str) -> MidiFacts:
    with open(path, "rb") as handle:
        raw = handle.read()

    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) < 14:
        raise SmfError("datoteka kraća od SMF zaglavlja")
    if raw[0:4] != b"MThd":
        raise SmfError(f"nedostaje MThd (nađeno {raw[0:4]!r})")

    header_len = int.from_bytes(raw[4:8], "big")
    if header_len < 6:
        raise SmfError(f"MThd dužina {header_len} < 6")

    fmt, declared, division = struct.unpack(">HHH", raw[8:14])
    warnings: list[str] = []
    header_extra = header_len - 6
    if header_extra:
        warnings.append(f"MThd ima {header_extra} dodatnih bajtova")

    ppq: int | None = None
    smpte: tuple[int, int] | None = None
    if division & 0x8000:
        frames = 256 - (division >> 8)
        smpte = (frames, division & 0xFF)
    else:
        ppq = division
        if ppq == 0:
            warnings.append("PPQ je 0")

    pos = 8 + header_len
    tracks: list[TrackFacts] = []
    index = 0
    while pos + 8 <= len(raw):
        chunk_id = raw[pos : pos + 4]
        chunk_len = int.from_bytes(raw[pos + 4 : pos + 8], "big")
        body = raw[pos + 8 : pos + 8 + chunk_len]
        if len(body) != chunk_len:
            warnings.append(f"chunk {chunk_id!r} skraćen: {len(body)}/{chunk_len}")
        pos += 8 + chunk_len
        if chunk_id == b"MTrk":
            tracks.append(_parse_track(body, index, warnings))
            index += 1
        else:
            warnings.append(f"nepoznat chunk {chunk_id!r} ({chunk_len} B) — preskočen")

    trailing = len(raw) - pos
    if trailing > 0:
        warnings.append(f"{trailing} bajtova iza zadnjeg chunka")

    if declared != len(tracks):
        warnings.append(f"deklarisano {declared} trackova, nađeno {len(tracks)}")
    if fmt == 0 and len(tracks) > 1:
        warnings.append(f"format 0 ima {len(tracks)} trackova")

    return MidiFacts(
        path=path,
        size=len(raw),
        sha256=digest,
        fmt=fmt,
        declared_tracks=declared,
        actual_tracks=len(tracks),
        division_raw=division,
        ppq=ppq,
        smpte=smpte,
        tracks=tracks,
        warnings=warnings,
        header_extra_bytes=max(0, header_extra),
        trailing_file_bytes=max(0, trailing),
    )


def summarize(facts: MidiFacts) -> dict[str, Any]:
    velocities: list[int] = []
    notes: list[int] = []
    controllers: dict[int, int] = {}
    meta: dict[int, int] = {}
    for t in facts.tracks:
        velocities.extend(t.velocities)
        notes.extend(t.note_numbers)
        for cc, n in t.controllers.items():
            controllers[cc] = controllers.get(cc, 0) + n
        for mt, n in t.meta_types.items():
            meta[mt] = meta.get(mt, 0) + n

    tempos = [bpm for t in facts.tracks for _, bpm in t.tempos]
    meters = [(n, d) for t in facts.tracks for _, n, d in t.meters]

    return {
        "path": facts.path,
        "sha256": facts.sha256,
        "size": facts.size,
        "format": facts.fmt,
        "tracks": facts.actual_tracks,
        "ppq": facts.ppq,
        "smpte": facts.smpte,
        "end_tick": facts.end_tick,
        "note_on": facts.note_on,
        "note_off": sum(t.note_off for t in facts.tracks),
        "zero_velocity_note_on": sum(t.zero_velocity_note_on for t in facts.tracks),
        "channels": sorted(facts.channels),
        "programs": sorted({p for t in facts.tracks for p in t.programs}),
        "cc0": sorted({v for t in facts.tracks for v in t.cc0_values}),
        "cc32": sorted({v for t in facts.tracks for v in t.cc32_values}),
        "controllers": dict(sorted(controllers.items())),
        "meta_types": dict(sorted(meta.items())),
        "sysex_count": sum(t.sysex_count for t in facts.tracks),
        "sysex_bytes": sum(t.sysex_bytes for t in facts.tracks),
        "pitch_bend": sum(t.pitch_bend for t in facts.tracks),
        "running_status_events": sum(t.running_status_events for t in facts.tracks),
        "tempo_us": tempos,
        "meters": meters,
        "velocity_min": min(velocities) if velocities else None,
        "velocity_max": max(velocities) if velocities else None,
        "velocity_mean": (sum(velocities) / len(velocities)) if velocities else None,
        "note_min": min(notes) if notes else None,
        "note_max": max(notes) if notes else None,
        "text_meta": [s for t in facts.tracks for s in t.text_meta][:20],
        "warnings": facts.warnings,
        "tracks_without_eot": sum(1 for t in facts.tracks if not t.has_eot),
        "trailing_file_bytes": facts.trailing_file_bytes,
    }
