"""Normalized MIDI event model derived from a raw import.

This module defines the track/event shape consumed by Vertical B and C
-- see docs/VERTICAL_DECOMPOSITION.md "cross-vertical data contracts".

Design: rather than re-inventing a parallel dataclass per MIDI message
type, each ``NormalizedEvent`` wraps the actual ``mido.Message`` /
``mido.MetaMessage`` object with just an absolute tick. This guarantees
zero information loss for every message type mido supports (Note
On/Off with velocity, CC, Pitch Bend, Program Change, Bank Select [=
CC0/CC32, no special-casing needed], Channel/Poly Aftertouch, SysEx,
all meta events) without a second model that could silently drop a
field. NRPN/RPN are not first-class MIDI message types -- they are a
convention built from a sequence of plain Control Change messages, so
preserving every CC losslessly preserves NRPN/RPN sequences for free;
semantic interpretation of what a given sequence *means* is deferred to
Vertical C (mapping/, rx/, Phase 7-8). See docs/MIDI_MODEL.md.

Owning vertical: A.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import mido

SUPPORTED_FORMATS = (0, 1)


@dataclass(frozen=True)
class NormalizedEvent:
    """One MIDI event at an absolute tick position within its track."""

    abs_tick: int
    message: mido.Message | mido.MetaMessage


@dataclass
class NormalizedTrack:
    index: int
    name: str | None
    events: list[NormalizedEvent] = field(default_factory=list)


@dataclass
class TempoMapEntry:
    abs_tick: int
    tempo: int  # microseconds per quarter note


@dataclass
class TimeSignatureEntry:
    abs_tick: int
    numerator: int
    denominator: int


@dataclass
class NormalizedMidiFile:
    format: int  # 0 or 1; format 2 is explicitly unsupported
    ppq: int  # ticks_per_beat
    tracks: list[NormalizedTrack]
    tempo_map: list[TempoMapEntry]
    time_signature_map: list[TimeSignatureEntry]
    source_file_id: int | None = None

    @classmethod
    def from_mido(
        cls, midi_file: mido.MidiFile, *, source_file_id: int | None = None
    ) -> "NormalizedMidiFile":
        if midi_file.type not in SUPPORTED_FORMATS:
            raise ValueError(
                f"unsupported MIDI format {midi_file.type} "
                f"(only {SUPPORTED_FORMATS} are supported)"
            )

        tracks: list[NormalizedTrack] = []
        tempo_map: list[TempoMapEntry] = []
        time_signature_map: list[TimeSignatureEntry] = []

        for track_index, mido_track in enumerate(midi_file.tracks):
            name: str | None = None
            events: list[NormalizedEvent] = []
            abs_tick = 0
            for msg in mido_track:
                abs_tick += msg.time
                if msg.is_meta and msg.type == "track_name" and name is None:
                    name = msg.name
                if msg.is_meta and msg.type == "set_tempo":
                    tempo_map.append(TempoMapEntry(abs_tick=abs_tick, tempo=msg.tempo))
                if msg.is_meta and msg.type == "time_signature":
                    time_signature_map.append(
                        TimeSignatureEntry(
                            abs_tick=abs_tick,
                            numerator=msg.numerator,
                            denominator=msg.denominator,
                        )
                    )
                events.append(NormalizedEvent(abs_tick=abs_tick, message=msg))
            tracks.append(NormalizedTrack(index=track_index, name=name, events=events))

        tempo_map.sort(key=lambda e: e.abs_tick)
        time_signature_map.sort(key=lambda e: e.abs_tick)

        return cls(
            format=midi_file.type,
            ppq=midi_file.ticks_per_beat,
            tracks=tracks,
            tempo_map=tempo_map,
            time_signature_map=time_signature_map,
            source_file_id=source_file_id,
        )

    @classmethod
    def from_file(
        cls, path: str | Path, *, source_file_id: int | None = None
    ) -> "NormalizedMidiFile":
        midi_file = mido.MidiFile(str(path))
        return cls.from_mido(midi_file, source_file_id=source_file_id)
