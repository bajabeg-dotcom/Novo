#!/usr/bin/env python3
"""Read-only Standard MIDI and Style Works collection loader.

This module deliberately stops before musical classification or optimization.
It validates bytes, preserves each event's original representation and builds
an immutable source model that later analyzer/engine modules can consume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import BinaryIO, Iterable, Mapping
from zipfile import ZipFile

from midi_enhancer import MidiError, read_vlq


STYLE_ELEMENT_SUFFIXES: Mapping[str, str] = MappingProxyType({
    "Var1": "VARIATION_1",
    "Var2": "VARIATION_2",
    "Var3": "VARIATION_3",
    "Var4": "VARIATION_4",
    "Intro1": "INTRO_1",
    "Intro2": "INTRO_2",
    "Intro3": "INTRO_3",
    "Fill1": "FILL_1",
    "Fill2": "FILL_2",
    "Break": "FILL_3_BREAK",
    "End1": "ENDING_1",
    "End2": "ENDING_2",
    "End3": "ENDING_3",
})

EXPECTED_STYLE_ELEMENTS = frozenset(STYLE_ELEMENT_SUFFIXES.values())
STYLE_CHANNEL_ROLES: Mapping[int, str] = MappingProxyType({
    9: "BASS",
    10: "DRUM",
    11: "PERC",
    12: "ACC1",
    13: "ACC2",
    14: "ACC3",
    15: "ACC4",
    16: "ACC5",
})

_BAR_TEXT = re.compile(r"^(\d+)\s+Bars?$", re.IGNORECASE)
_TRACK_ROLE = re.compile(r"\b(DRUMS?|PERC(?:USSION)?|BASS|ACC[1-5])\s+CV([1-6])\b", re.IGNORECASE)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65_536), b""):
            digest.update(block)
    return digest.hexdigest()


def decode_midi_text(payload: bytes) -> str:
    """Decode display text without altering the preserved payload bytes."""
    try:
        return payload.decode("utf-8").strip("\x00 ")
    except UnicodeDecodeError:
        return payload.decode("latin-1").strip("\x00 ")


@dataclass(frozen=True, slots=True)
class MidiEvent:
    track_index: int
    event_index: int
    delta_tick: int
    absolute_tick: int
    kind: str
    status: int
    status_explicit: bool
    channel: int | None
    data: tuple[int, ...]
    meta_type: int | None
    payload: bytes
    raw: bytes
    byte_start: int
    byte_end: int

    @property
    def is_note_on(self) -> bool:
        return self.kind == "note_on" and len(self.data) == 2 and self.data[1] > 0

    @property
    def is_end_of_track(self) -> bool:
        return self.kind == "meta" and self.meta_type == 0x2F


@dataclass(frozen=True, slots=True)
class MidiTrackModel:
    index: int
    body: bytes
    events: tuple[MidiEvent, ...]
    end_tick: int
    warnings: tuple[str, ...]

    def text_events(self, *, include_track_name: bool = True) -> tuple[tuple[int, int, str], ...]:
        kinds = {0x01, 0x04}
        if include_track_name:
            kinds.add(0x03)
        return tuple(
            (event.absolute_tick, event.meta_type or 0, decode_midi_text(event.payload))
            for event in self.events
            if event.kind == "meta" and event.meta_type in kinds
        )


@dataclass(frozen=True, slots=True)
class MidiFileModel:
    source_name: str
    sha256: str
    format: int
    declared_track_count: int
    division: int
    ticks_per_beat: int | None
    smpte: tuple[int, int] | None
    header_extra: bytes
    tracks: tuple[MidiTrackModel, ...]
    trailing_bytes: bytes
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InstrumentSelection:
    tick: int
    channel: int
    bank_msb: int | None
    bank_lsb: int | None
    program: int

    @property
    def complete(self) -> bool:
        return self.bank_msb is not None and self.bank_lsb is not None

    @property
    def address(self) -> str | None:
        if not self.complete:
            return None
        return f"{self.bank_msb}.{self.bank_lsb}.{self.program}"


@dataclass(frozen=True, slots=True)
class StyleTrackSlice:
    physical_track: int
    cv: int | None
    role: str | None
    channel: int | None
    track_name: str | None
    sound_text: str | None
    valid_event_indexes: tuple[int, ...]
    trailing_event_indexes: tuple[int, ...]
    note_on_count: int
    instrument_selections: tuple[InstrumentSelection, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StyleElementModel:
    member_name: str
    style_name: str
    element: str
    midi: MidiFileModel
    meter: tuple[int, int] | None
    declared_bars: int | None
    valid_end_tick: int | None
    tracks: tuple[StyleTrackSlice, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StyleElementSummary:
    member_name: str
    element: str
    format: int
    division: int
    meter: tuple[int, int] | None
    declared_bars: int | None
    valid_end_tick: int | None
    track_slices: int
    active_slices: int
    note_on_count: int
    complete_instrument_selections: int
    incomplete_instrument_selections: int
    trailing_event_count: int
    analysis_blocked: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StyleSetSummary:
    style_name: str
    folder: str
    elements: tuple[StyleElementSummary, ...]
    missing_elements: tuple[str, ...]
    duplicate_elements: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing_elements and not self.duplicate_elements


@dataclass(frozen=True, slots=True)
class StyleCollectionSummary:
    source_name: str
    sha256_before: str
    sha256_after: str
    archive_member_count: int
    midi_file_count: int
    styles: tuple[StyleSetSummary, ...]
    invalid_members: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...]

    @property
    def original_preserved(self) -> bool:
        return self.sha256_before == self.sha256_after

    @property
    def complete_style_count(self) -> int:
        return sum(style.complete for style in self.styles)


def _read_exact_bytes(data: bytes, offset: int, size: int, message: str) -> tuple[bytes, int]:
    payload = data[offset : offset + size]
    if len(payload) != size:
        raise MidiError(message)
    return payload, offset + size


class StandardMidiLoader:
    """Parse MIDI bytes into an immutable, byte-preserving model."""

    def load_path(self, path: str | Path) -> MidiFileModel:
        source = Path(path)
        if not source.is_file():
            raise MidiError(f"Datoteka ne postoji: {source}")
        before = sha256_path(source)
        data = source.read_bytes()
        model = self.load_bytes(data, source_name=str(source))
        after = sha256_path(source)
        if before != after or before != model.sha256:
            raise MidiError("Originalna MIDI datoteka promijenjena je tijekom učitavanja.")
        return model

    def load_bytes(self, data: bytes, *, source_name: str = "<memory>") -> MidiFileModel:
        digest = hashlib.sha256(data).hexdigest()
        offset = 0
        chunk, offset = _read_exact_bytes(data, offset, 4, "Nedostaje MIDI zaglavlje.")
        if chunk != b"MThd":
            raise MidiError("Datoteka nema valjano MThd MIDI zaglavlje.")
        raw_size, offset = _read_exact_bytes(data, offset, 4, "Nepotpuna duljina MIDI zaglavlja.")
        header_size = struct.unpack(">I", raw_size)[0]
        if header_size < 6:
            raise MidiError("MIDI zaglavlje je prekratko.")
        header, offset = _read_exact_bytes(data, offset, header_size, "Nepotpuno MIDI zaglavlje.")
        format_number, track_count, division = struct.unpack(">HHH", header[:6])
        if format_number not in (0, 1, 2):
            raise MidiError(f"Nepodrzani MIDI format: {format_number}")
        if track_count == 0:
            raise MidiError("SMF mora deklarirati najmanje jedan track.")
        if format_number == 0 and track_count != 1:
            raise MidiError("SMF Format 0 mora deklarirati tocno jedan track.")

        if division & 0x8000:
            fps_byte = (division >> 8) & 0xFF
            fps_code = fps_byte - 256
            ticks_per_frame = division & 0xFF
            if fps_code not in (-24, -25, -29, -30):
                raise MidiError(f"Neispravan SMPTE frame code: {fps_code}.")
            if ticks_per_frame == 0:
                raise MidiError("SMPTE ticks-per-frame ne smije biti nula.")
            smpte = (-fps_code, ticks_per_frame)
            ticks_per_beat = None
        else:
            smpte = None
            ticks_per_beat = division
            if ticks_per_beat == 0:
                raise MidiError("PPQ division ne smije biti nula.")

        tracks: list[MidiTrackModel] = []
        warnings: list[str] = []
        for track_index in range(track_count):
            marker, offset = _read_exact_bytes(
                data, offset, 4, f"Nedostaje MTrk zaglavlje za track {track_index + 1}."
            )
            if marker != b"MTrk":
                raise MidiError(f"Neispravno MTrk zaglavlje za track {track_index + 1}.")
            raw_length, offset = _read_exact_bytes(
                data, offset, 4, f"Nepotpuna duljina tracka {track_index + 1}."
            )
            length = struct.unpack(">I", raw_length)[0]
            body, offset = _read_exact_bytes(
                data, offset, length, f"Track {track_index + 1} izlazi iz granice datoteke."
            )
            tracks.append(self._parse_track(body, track_index))

        trailing = data[offset:]
        if trailing:
            warnings.append(f"Podaci nakon posljednjeg deklariranog tracka: {len(trailing)} bajtova.")
        return MidiFileModel(
            source_name=source_name,
            sha256=digest,
            format=format_number,
            declared_track_count=track_count,
            division=division,
            ticks_per_beat=ticks_per_beat,
            smpte=smpte,
            header_extra=header[6:],
            tracks=tuple(tracks),
            trailing_bytes=trailing,
            warnings=tuple(warnings),
        )

    def _parse_track(self, body: bytes, track_index: int) -> MidiTrackModel:
        offset = 0
        tick = 0
        running_status: int | None = None
        events: list[MidiEvent] = []
        warnings: list[str] = []
        end_of_track_indexes: list[int] = []

        while offset < len(body):
            event_start = offset
            delta, offset = read_vlq(body, offset)
            tick += delta
            if offset >= len(body):
                raise MidiError(f"Track {track_index + 1} zavrsava usred eventa.")

            first = body[offset]
            explicit = bool(first & 0x80)
            if explicit:
                status = first
                offset += 1
                if status < 0xF0:
                    running_status = status
            elif running_status is not None:
                status = running_status
            else:
                raise MidiError(f"Running status bez prethodnog statusa u tracku {track_index + 1}.")

            channel: int | None = None
            data_bytes: tuple[int, ...] = ()
            meta_type: int | None = None
            payload = b""

            if status == 0xFF:
                if offset >= len(body):
                    raise MidiError("Nepotpun meta event.")
                meta_type = body[offset]
                offset += 1
                length, offset = read_vlq(body, offset)
                payload, offset = _read_exact_bytes(body, offset, length, "Nepotpun payload meta eventa.")
                kind = "meta"
                running_status = None
                if meta_type == 0x2F:
                    end_of_track_indexes.append(len(events))
            elif status in (0xF0, 0xF7):
                length, offset = read_vlq(body, offset)
                payload, offset = _read_exact_bytes(body, offset, length, "Nepotpun SysEx event.")
                kind = "sysex"
                running_status = None
            elif status < 0xF0:
                event_type = status & 0xF0
                channel = status & 0x0F
                sizes = {0x80: 2, 0x90: 2, 0xA0: 2, 0xB0: 2, 0xC0: 1, 0xD0: 1, 0xE0: 2}
                names = {
                    0x80: "note_off",
                    0x90: "note_on",
                    0xA0: "poly_aftertouch",
                    0xB0: "control_change",
                    0xC0: "program_change",
                    0xD0: "channel_aftertouch",
                    0xE0: "pitch_bend",
                }
                if event_type not in sizes:
                    raise MidiError(f"Nepoznat MIDI status 0x{status:02X}.")
                raw_data, offset = _read_exact_bytes(body, offset, sizes[event_type], "Nepotpun channel event.")
                if any(byte & 0x80 for byte in raw_data):
                    raise MidiError("Neispravan data byte u channel eventu.")
                data_bytes = tuple(raw_data)
                kind = names[event_type]
            else:
                raise MidiError(f"Nepodrzan system status 0x{status:02X} u MIDI tracku.")

            event = MidiEvent(
                track_index=track_index,
                event_index=len(events),
                delta_tick=delta,
                absolute_tick=tick,
                kind=kind,
                status=status,
                status_explicit=explicit,
                channel=channel,
                data=data_bytes,
                meta_type=meta_type,
                payload=payload,
                raw=body[event_start:offset],
                byte_start=event_start,
                byte_end=offset,
            )
            events.append(event)

        if not end_of_track_indexes:
            warnings.append("Track nema End-of-Track meta event.")
        elif len(end_of_track_indexes) > 1:
            warnings.append(f"Track ima vise End-of-Track događaja: {len(end_of_track_indexes)}.")
        if end_of_track_indexes and end_of_track_indexes[-1] != len(events) - 1:
            warnings.append("Track sadrzi događaje nakon End-of-Track meta eventa.")
        return MidiTrackModel(track_index, body, tuple(events), tick, tuple(warnings))


def _style_identity(member_name: str) -> tuple[str, str, str]:
    path = PurePosixPath(member_name)
    stem = path.stem
    for suffix, element in STYLE_ELEMENT_SUFFIXES.items():
        marker = f"_{suffix}"
        if stem.endswith(marker):
            return stem[: -len(marker)], element, str(path.parent)
    raise MidiError(f"Naziv Style Works datoteke nema podrzan element: {member_name}")


def _meta_texts(midi: MidiFileModel, *, tick: int | None = None) -> list[tuple[int, int, str]]:
    result: list[tuple[int, int, str]] = []
    for track in midi.tracks:
        for event in track.events:
            if event.kind != "meta" or event.meta_type not in {0x01, 0x03, 0x04}:
                continue
            if tick is None or event.absolute_tick == tick:
                result.append((event.absolute_tick, event.meta_type, decode_midi_text(event.payload)))
    return result


def _meter_at_zero(midi: MidiFileModel) -> tuple[int, int] | None:
    meters = {
        (event.payload[0], 2 ** event.payload[1])
        for track in midi.tracks
        for event in track.events
        if event.kind == "meta"
        and event.meta_type == 0x58
        and event.absolute_tick == 0
        and len(event.payload) >= 2
    }
    if len(meters) == 1:
        return next(iter(meters))
    return None


def _declared_bars(midi: MidiFileModel) -> tuple[int | None, tuple[str, ...]]:
    values = {
        int(match.group(1))
        for _, meta_type, text in _meta_texts(midi, tick=0)
        if meta_type == 0x01 and (match := _BAR_TEXT.fullmatch(text))
    }
    if len(values) == 1:
        return next(iter(values)), ()
    if not values:
        return None, ("Nedostaje deklarirani broj taktova na ticku 0.",)
    return None, (f"Konflikt deklariranog broja taktova: {sorted(values)}.",)


def _track_name(track: MidiTrackModel) -> str | None:
    names = [
        decode_midi_text(event.payload)
        for event in track.events
        if event.kind == "meta" and event.meta_type == 0x03
    ]
    return names[0] if names else None


def _sound_text(track: MidiTrackModel) -> str | None:
    texts = [
        decode_midi_text(event.payload)
        for event in track.events
        if event.kind == "meta" and event.meta_type in {0x01, 0x04} and event.absolute_tick == 0
    ]
    for text in texts:
        if _BAR_TEXT.fullmatch(text):
            continue
        if re.fullmatch(r"(?:Variation|Intro|Ending|Fill)\s*\d*|Break", text, re.IGNORECASE):
            continue
        if text.startswith("SN:"):
            continue
        return text or None
    return None


def _role_from_track_name(name: str | None) -> tuple[str | None, int | None]:
    if not name or not (match := _TRACK_ROLE.search(name)):
        return None, None
    label = match.group(1).upper()
    role = "DRUM" if label.startswith("DRUM") else "PERC" if label.startswith("PERC") else label
    return role, int(match.group(2))


class StyleWorksLoader:
    """Inspect split Style Works MIDI exports without altering the archive."""

    def __init__(self) -> None:
        self.midi_loader = StandardMidiLoader()

    def load_element_bytes(self, data: bytes, *, member_name: str) -> StyleElementModel:
        style_name, element, _folder = _style_identity(member_name)
        midi = self.midi_loader.load_bytes(data, source_name=member_name)
        meter = _meter_at_zero(midi)
        bars, bar_warnings = _declared_bars(midi)
        warnings = list(bar_warnings)
        if meter is None:
            warnings.append("Nedostaje ili je konfliktna oznaka takta na ticku 0.")
        if midi.ticks_per_beat is None:
            warnings.append("Style Works element koristi SMPTE division; PPQ prozor nije izracunat.")
        valid_end_tick = None
        if bars is not None and meter is not None and midi.ticks_per_beat is not None:
            numerator, denominator = meter
            valid_end_tick = bars * numerator * midi.ticks_per_beat * 4 // denominator

        slices = tuple(self._build_slice(track, valid_end_tick) for track in midi.tracks)
        return StyleElementModel(
            member_name=member_name,
            style_name=style_name,
            element=element,
            midi=midi,
            meter=meter,
            declared_bars=bars,
            valid_end_tick=valid_end_tick,
            tracks=slices,
            warnings=tuple(warnings),
        )

    def load_archive_element(self, archive: str | Path, member_name: str) -> StyleElementModel:
        path = Path(archive)
        before = sha256_path(path)
        with ZipFile(path) as source:
            data = source.read(member_name)
        after = sha256_path(path)
        if before != after:
            raise MidiError("ZIP arhiv promijenjen je tijekom učitavanja elementa.")
        return self.load_element_bytes(data, member_name=member_name)

    def inspect_archive(self, archive: str | Path) -> StyleCollectionSummary:
        path = Path(archive)
        if not path.is_file():
            raise MidiError(f"ZIP arhiv ne postoji: {path}")
        before = sha256_path(path)
        grouped: dict[tuple[str, str], list[StyleElementSummary]] = defaultdict(list)
        invalid: list[tuple[str, str]] = []
        archive_members = 0
        midi_files = 0

        with ZipFile(path) as source:
            archive_members = len(source.infolist())
            for info in source.infolist():
                if info.is_dir() or not info.filename.lower().endswith((".mid", ".midi")):
                    continue
                midi_files += 1
                try:
                    style_name, _element, folder = _style_identity(info.filename)
                    model = self.load_element_bytes(source.read(info), member_name=info.filename)
                    grouped[(folder, style_name)].append(self._summary(model))
                except (MidiError, OSError, ValueError) as error:
                    invalid.append((info.filename, str(error)))

        styles: list[StyleSetSummary] = []
        for (folder, style_name), elements in sorted(grouped.items()):
            counts = Counter(item.element for item in elements)
            missing = tuple(sorted(EXPECTED_STYLE_ELEMENTS - counts.keys()))
            duplicates = tuple(sorted(element for element, count in counts.items() if count > 1))
            styles.append(StyleSetSummary(
                style_name=style_name,
                folder=folder,
                elements=tuple(sorted(elements, key=lambda item: (item.element, item.member_name))),
                missing_elements=missing,
                duplicate_elements=duplicates,
            ))

        after = sha256_path(path)
        warnings: list[str] = []
        if invalid:
            warnings.append(f"Nevaljanih MIDI clanova: {len(invalid)}.")
        if before != after:
            raise MidiError("ZIP arhiv promijenjen je tijekom inspekcije.")
        return StyleCollectionSummary(
            source_name=str(path),
            sha256_before=before,
            sha256_after=after,
            archive_member_count=archive_members,
            midi_file_count=midi_files,
            styles=tuple(styles),
            invalid_members=tuple(invalid),
            warnings=tuple(warnings),
        )

    def _build_slice(self, track: MidiTrackModel, valid_end_tick: int | None) -> StyleTrackSlice:
        valid: list[int] = []
        trailing: list[int] = []
        channel_counts: Counter[int] = Counter()
        note_ons = 0
        warnings: list[str] = list(track.warnings)

        if valid_end_tick is None:
            warnings.append("Valjani vremenski prozor nije potvrđen; događaji nisu uključeni u analizu.")

        for event in track.events:
            if event.is_end_of_track:
                valid.append(event.event_index)
            elif valid_end_tick is not None and event.absolute_tick < valid_end_tick:
                valid.append(event.event_index)
                if event.channel is not None:
                    channel_counts[event.channel + 1] += 1
                if event.is_note_on:
                    note_ons += 1
            else:
                trailing.append(event.event_index)

        channel = channel_counts.most_common(1)[0][0] if channel_counts else None
        role = STYLE_CHANNEL_ROLES.get(channel) if channel is not None else None
        cv = (track.index - 1) // 8 + 1 if track.index > 0 else None
        name = _track_name(track)
        name_role, name_cv = _role_from_track_name(name)
        if role and name_role and role != name_role:
            warnings.append(f"Konflikt uloge: kanal={role}, naziv={name_role}.")
        if name_cv is not None and cv is not None and name_cv != cv:
            warnings.append(f"Konflikt CV-a: pozicija={cv}, naziv={name_cv}.")
        if role is None:
            role = name_role
        if cv is None:
            cv = name_cv

        selections = self._instrument_selections(track.events, valid_end_tick)
        return StyleTrackSlice(
            physical_track=track.index + 1,
            cv=cv,
            role=role,
            channel=channel,
            track_name=name,
            sound_text=_sound_text(track),
            valid_event_indexes=tuple(valid),
            trailing_event_indexes=tuple(trailing),
            note_on_count=note_ons,
            instrument_selections=selections,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _instrument_selections(
        events: Iterable[MidiEvent], valid_end_tick: int | None
    ) -> tuple[InstrumentSelection, ...]:
        banks: dict[int, dict[int, int | None]] = defaultdict(lambda: {0: None, 32: None})
        selections: list[InstrumentSelection] = []
        for event in events:
            if valid_end_tick is not None and event.absolute_tick >= valid_end_tick:
                continue
            if event.channel is None:
                continue
            if event.kind == "control_change" and len(event.data) == 2 and event.data[0] in (0, 32):
                banks[event.channel][event.data[0]] = event.data[1]
            elif event.kind == "program_change" and event.data:
                selections.append(InstrumentSelection(
                    tick=event.absolute_tick,
                    channel=event.channel + 1,
                    bank_msb=banks[event.channel][0],
                    bank_lsb=banks[event.channel][32],
                    program=event.data[0],
                ))
        return tuple(selections)

    @staticmethod
    def _summary(model: StyleElementModel) -> StyleElementSummary:
        selections = [item for track in model.tracks for item in track.instrument_selections]
        return StyleElementSummary(
            member_name=model.member_name,
            element=model.element,
            format=model.midi.format,
            division=model.midi.division,
            meter=model.meter,
            declared_bars=model.declared_bars,
            valid_end_tick=model.valid_end_tick,
            track_slices=len(model.tracks),
            active_slices=sum(track.note_on_count > 0 for track in model.tracks),
            note_on_count=sum(track.note_on_count for track in model.tracks),
            complete_instrument_selections=sum(item.complete for item in selections),
            incomplete_instrument_selections=sum(not item.complete for item in selections),
            trailing_event_count=sum(len(track.trailing_event_indexes) for track in model.tracks),
            analysis_blocked=model.valid_end_tick is None,
            warnings=model.warnings,
        )


def collection_report(summary: StyleCollectionSummary) -> dict[str, object]:
    """Return a stable JSON-ready report without serializing raw MIDI events."""
    all_elements = [element for style in summary.styles for element in style.elements]
    return {
        "source": summary.source_name,
        "sha256": summary.sha256_before,
        "original_preserved": summary.original_preserved,
        "archive_members": summary.archive_member_count,
        "midi_files": summary.midi_file_count,
        "styles": len(summary.styles),
        "complete_styles": summary.complete_style_count,
        "incomplete_styles": len(summary.styles) - summary.complete_style_count,
        "invalid_members": [
            {"member": member, "error": error} for member, error in summary.invalid_members
        ],
        "formats": dict(sorted(Counter(element.format for element in all_elements).items())),
        "divisions": dict(sorted(Counter(element.division for element in all_elements).items())),
        "active_track_slices": sum(element.active_slices for element in all_elements),
        "note_on_events": sum(element.note_on_count for element in all_elements),
        "complete_instrument_selections": sum(
            element.complete_instrument_selections for element in all_elements
        ),
        "incomplete_instrument_selections": sum(
            element.incomplete_instrument_selections for element in all_elements
        ),
        "analysis_blocked_elements": sum(element.analysis_blocked for element in all_elements),
        "element_warning_count": sum(len(element.warnings) for element in all_elements),
        "trailing_events_outside_declared_window": sum(
            element.trailing_event_count for element in all_elements
        ),
        "warnings": list(summary.warnings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only pregled Style Works ZIP kolekcije."
    )
    parser.add_argument("archive", help="Putanja do Style Works ZIP arhiva.")
    parser.add_argument(
        "--json-output",
        help="Opcionalna nova JSON datoteka za zbirni izvjestaj.",
    )
    arguments = parser.parse_args()

    summary = StyleWorksLoader().inspect_archive(arguments.archive)
    report = collection_report(summary)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if arguments.json_output:
        output = Path(arguments.json_output)
        if output.resolve() == Path(arguments.archive).resolve():
            raise MidiError("JSON izlaz ne smije prepisati izvorni ZIP arhiv.")
        output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())