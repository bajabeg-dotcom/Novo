#!/usr/bin/env python3
"""Analyze a Standard MIDI File without changing the original.

The built-in parser is always available. NumPy, Mido, pretty_midi and music21
are used automatically when installed, but are not required for basic work.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from midi_instruments import build_display_tracks

try:
    import numpy as np
except ImportError:  # The analyzer remains usable in a minimal Python install.
    np = None


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
OPTIONAL_LIBRARIES = {
    "numpy": "statistika velocity vrijednosti",
    "mido": "dodatna validacija MIDI strukture",
    "pretty_midi": "visokonivojska analiza instrumenata i tempa",
    "music21": "napredna analiza tonaliteta",
}


class MidiError(ValueError):
    """Raised when the input is not a supported or valid MIDI file."""


@dataclass
class Note:
    track: int
    channel: int
    pitch: int
    velocity: int
    start_tick: int
    end_tick: int

    @property
    def duration_ticks(self) -> int:
        return self.end_tick - self.start_tick


def read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise MidiError("Neocekivani kraj MIDI datoteke.")
    return data


def read_vlq(data: bytes, offset: int) -> tuple[int, int]:
    """Read a MIDI variable-length quantity from bytes."""
    value = 0
    for _ in range(4):
        if offset >= len(data):
            raise MidiError("Nepotpuna variable-length vrijednost u tracku.")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset
    raise MidiError("Neispravna variable-length vrijednost.")


def note_name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


def decode_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip("\x00")


def library_status() -> dict[str, dict[str, str | bool | None]]:
    status = {}
    for name, purpose in OPTIONAL_LIBRARIES.items():
        available = importlib.util.find_spec(name) is not None
        version = None
        if available:
            module = importlib.import_module(name)
            version = getattr(module, "__version__", None)
        status[name] = {"available": available, "version": version, "purpose": purpose}
    return status


def apply_library_integrations(path: Path, result: dict, advanced: bool = False) -> None:
    """Enrich a result with optional libraries while keeping failures non-fatal."""
    status = library_status()
    result["libraries"] = status
    external: dict[str, dict] = {}

    if status["mido"]["available"]:
        try:
            mido = importlib.import_module("mido")
            midi = mido.MidiFile(path)
            external["mido"] = {
                "validated": True,
                "tracks": len(midi.tracks),
                "messages": sum(len(track) for track in midi.tracks),
            }
        except Exception as error:  # Third-party validation must not hide core results.
            external["mido"] = {"validated": False, "error": str(error)}

    if result.get("format") == 2:
        if status["pretty_midi"]["available"]:
            external["pretty_midi"] = {
                "skipped": True,
                "reason": "SMF Format 2 nema jednu globalnu tempo/beat vremensku liniju.",
            }
        if advanced and status["music21"]["available"]:
            external["music21"] = {
                "skipped": True,
                "reason": "SMF Format 2 sekvence ne analiziraju se kao jedna harmonijska cjelina.",
            }
    else:
        if status["pretty_midi"]["available"]:
            try:
                pretty_midi = importlib.import_module("pretty_midi")
                midi = pretty_midi.PrettyMIDI(str(path))
                external["pretty_midi"] = {
                    "instruments": len(midi.instruments),
                    "estimated_tempo": round(float(midi.estimate_tempo()), 3) if result["notes"] else None,
                    "beats": len(midi.get_beats()),
                }
            except Exception as error:
                external["pretty_midi"] = {"error": str(error)}

        if advanced and status["music21"]["available"]:
            try:
                converter = importlib.import_module("music21.converter")
                score = converter.parse(str(path))
                key = score.analyze("key")
                external["music21"] = {
                    "estimated_key": str(key),
                    "confidence": round(float(key.correlationCoefficient), 4),
                }
            except Exception as error:
                external["music21"] = {"error": str(error)}

    result["external_analysis"] = external


class MidiAnalyzer:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.format = 0
        self.track_count = 0
        self.division = 0
        self.ticks_per_beat: int | None = None
        self.smpte: dict[str, int] | None = None
        self.notes: list[Note] = []
        self.tempos: list[tuple[int, int]] = []
        self.track_tempos: dict[int, list[tuple[int, int]]] = defaultdict(list)
        self.track_end_ticks: dict[int, int] = {}
        self.time_signatures: list[tuple[int, int, int]] = []
        self.key_signatures: list[tuple[int, int, str]] = []
        self.track_names: dict[int, str] = {}
        self.programs: dict[int, set[int]] = defaultdict(set)
        self.track_programs: Counter[tuple[int, int, int]] = Counter()
        self.track_meta_counts: Counter[int] = Counter()
        self.control_changes: Counter[tuple[int, int]] = Counter()
        self.pitch_bends: Counter[int] = Counter()
        self.track_pitch_bends: Counter[int] = Counter()
        self.event_counts: Counter[str] = Counter()
        self.warnings: list[str] = []
        self.max_tick = 0
        self.file_hash = ""

    def load(self) -> None:
        if not self.path.is_file():
            raise MidiError(f"Datoteka ne postoji: {self.path}")
        if self.path.suffix.lower() not in {".mid", ".midi"}:
            self.warnings.append("Ekstenzija datoteke nije .mid ili .midi.")

        self.file_hash = self._sha256()

        with self.path.open("rb") as stream:
            if read_exact(stream, 4) != b"MThd":
                raise MidiError("Datoteka nema valjano MThd MIDI zaglavlje.")
            header_size = struct.unpack(">I", read_exact(stream, 4))[0]
            if header_size < 6:
                raise MidiError("MIDI zaglavlje je prekratko.")
            header = read_exact(stream, header_size)
            self.format, self.track_count, self.division = struct.unpack(">HHH", header[:6])
            if self.format not in (0, 1, 2):
                raise MidiError(f"Nepodrzani MIDI format: {self.format}")
            if self.track_count == 0:
                raise MidiError("SMF mora deklarirati najmanje jedan track.")
            if self.format == 0 and self.track_count != 1:
                raise MidiError("SMF Format 0 mora deklarirati tocno jedan track.")
            self._parse_division()

            for track_index in range(self.track_count):
                if read_exact(stream, 4) != b"MTrk":
                    raise MidiError(f"Nedostaje MTrk zaglavlje za track {track_index + 1}.")
                size = struct.unpack(">I", read_exact(stream, 4))[0]
                self._parse_track(read_exact(stream, size), track_index)

            if stream.read(1):
                self.warnings.append("Datoteka sadrzi podatke nakon posljednjeg MIDI tracka.")

        if self._sha256() != self.file_hash:
            raise MidiError("Originalna MIDI datoteka promijenjena je tijekom analize.")
        self._validate()

    def _sha256(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for block in iter(lambda: stream.read(65_536), b""):
                digest.update(block)
        return digest.hexdigest()

    def _parse_division(self) -> None:
        if self.division & 0x8000:
            fps_byte = (self.division >> 8) & 0xFF
            fps_code = fps_byte - 256
            ticks_per_frame = self.division & 0xFF
            if fps_code not in (-24, -25, -29, -30):
                raise MidiError(f"Neispravan SMPTE frame code: {fps_code}.")
            if ticks_per_frame == 0:
                raise MidiError("SMPTE ticks-per-frame ne smije biti nula.")
            self.smpte = {
                "frames_per_second": -fps_code,
                "ticks_per_frame": ticks_per_frame,
            }
        else:
            if self.division == 0:
                raise MidiError("PPQ division ne smije biti nula.")
            self.ticks_per_beat = self.division

    def _parse_track(self, data: bytes, track_index: int) -> None:
        offset = 0
        tick = 0
        running_status: int | None = None
        end_of_track_seen = False
        active: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)

        while offset < len(data):
            delta, offset = read_vlq(data, offset)
            tick += delta
            self.max_tick = max(self.max_tick, tick)
            if offset >= len(data):
                raise MidiError(f"Track {track_index + 1} zavrsava usred eventa.")

            first = data[offset]
            if first & 0x80:
                status = first
                offset += 1
                if status < 0xF0:
                    running_status = status
            elif running_status is not None:
                status = running_status
            else:
                raise MidiError(f"Running status bez prethodnog statusa u tracku {track_index + 1}.")

            if status == 0xFF:
                if offset >= len(data):
                    raise MidiError("Nepotpun meta event.")
                meta_type = data[offset]
                offset += 1
                length, offset = read_vlq(data, offset)
                payload = data[offset : offset + length]
                if len(payload) != length:
                    raise MidiError("Nepotpun payload meta eventa.")
                offset += length
                self._meta_event(meta_type, payload, tick, track_index)
                running_status = None
                if meta_type == 0x2F:
                    end_of_track_seen = True
                    if offset < len(data):
                        self.warnings.append(
                            f"Track {track_index + 1} sadrzi {len(data) - offset} "
                            "bajtova nakon End-of-Track dogadjaja."
                        )
                    break
                continue

            if status in (0xF0, 0xF7):
                length, offset = read_vlq(data, offset)
                offset += length
                if offset > len(data):
                    raise MidiError("Nepotpun SysEx event.")
                self.event_counts["sysex"] += 1
                running_status = None
                continue

            event_type = status & 0xF0
            channel = status & 0x0F
            data_size = 1 if event_type in (0xC0, 0xD0) else 2
            payload = data[offset : offset + data_size]
            if len(payload) != data_size:
                raise MidiError("Nepotpun channel event.")
            if any(byte & 0x80 for byte in payload):
                raise MidiError("Neispravan data byte u channel eventu.")
            offset += data_size

            names = {
                0x80: "note_off", 0x90: "note_on", 0xA0: "poly_aftertouch",
                0xB0: "control_change", 0xC0: "program_change",
                0xD0: "channel_aftertouch", 0xE0: "pitch_bend",
            }
            if event_type not in names:
                raise MidiError(f"Nepoznat MIDI status 0x{status:02X}.")
            self.event_counts[names[event_type]] += 1

            if event_type == 0x90 and payload[1] > 0:
                active[(channel, payload[0])].append((tick, payload[1]))
            elif event_type == 0x80 or (event_type == 0x90 and payload[1] == 0):
                key = (channel, payload[0])
                if active[key]:
                    start, velocity = active[key].pop(0)
                    self.notes.append(Note(track_index, channel, payload[0], velocity, start, tick))
            elif event_type == 0xC0:
                self.programs[channel].add(payload[0])
                self.track_programs[(track_index, channel, payload[0])] += 1
            elif event_type == 0xB0:
                self.control_changes[(channel, payload[0])] += 1
            elif event_type == 0xE0:
                self.pitch_bends[channel] += 1
                self.track_pitch_bends[track_index] += 1

        if not end_of_track_seen:
            self.warnings.append(
                f"Track {track_index + 1} nema End-of-Track meta dogadjaj."
            )
        self.track_end_ticks[track_index] = tick

        # Keep hanging notes visible in the analysis rather than silently losing them.
        for (channel, pitch), starts in active.items():
            for start, velocity in starts:
                self.notes.append(Note(track_index, channel, pitch, velocity, start, tick))
                self.event_counts["unterminated_notes"] += 1

    def _meta_event(self, kind: int, payload: bytes, tick: int, track: int) -> None:
        self.event_counts["meta"] += 1
        self.track_meta_counts[track] += 1
        if kind == 0x03:
            self.track_names[track] = decode_text(payload)
        elif kind == 0x51 and len(payload) == 3:
            tempo = int.from_bytes(payload, "big")
            self.tempos.append((tick, tempo))
            self.track_tempos[track].append((tick, tempo))
        elif kind == 0x58 and len(payload) >= 2:
            self.time_signatures.append((tick, payload[0], 2 ** payload[1]))
        elif kind == 0x59 and len(payload) == 2:
            sf = payload[0] if payload[0] < 128 else payload[0] - 256
            self.key_signatures.append((tick, sf, "minor" if payload[1] else "major"))

    def _validate(self) -> None:
        if not self.notes:
            self.warnings.append("MIDI datoteka ne sadrzi zavrsene note.")
        if self.event_counts["unterminated_notes"]:
            count = self.event_counts["unterminated_notes"]
            self.warnings.append(f"Pronadjeno je nezatvorenih nota: {count}.")
        if self.format == 2:
            self.warnings.append(
                "SMF Format 2 sadrzi neovisne sekvence; globalni tempo i trajanje "
                "ne tumace se kao jedna pjesma."
            )
        elif not self.tempos and self.ticks_per_beat:
            self.warnings.append("Tempo nije zapisan; za analizu se koristi 120 BPM.")

    @staticmethod
    def maximum_polyphony(notes: list[Note]) -> int:
        events = []
        for note in notes:
            events.append((note.start_tick, 1))
            events.append((note.end_tick, -1))
        active = maximum = 0
        # Note-offs at a tick are processed before note-ons at the same tick.
        for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
            active += delta
            maximum = max(maximum, active)
        return maximum

    def _polyphony_by_track(self) -> dict[str, int]:
        return {
            str(track + 1): self.maximum_polyphony(
                [note for note in self.notes if note.track == track]
            )
            for track in range(self.track_count)
        }

    def _ticks_to_seconds(
        self, target_tick: int, tempos: list[tuple[int, int]]
    ) -> float | None:
        if not self.ticks_per_beat:
            if not self.smpte:
                return None
            rate = self.smpte["frames_per_second"] * self.smpte["ticks_per_frame"]
            return target_tick / rate

        timeline = sorted(tempos or [(0, 500_000)])
        if timeline[0][0] != 0:
            timeline.insert(0, (0, 500_000))
        seconds = 0.0
        previous_tick = 0
        tempo = timeline[0][1]
        for change_tick, new_tempo in timeline[1:]:
            if change_tick >= target_tick:
                break
            seconds += (change_tick - previous_tick) * tempo / 1_000_000 / self.ticks_per_beat
            previous_tick, tempo = change_tick, new_tempo
        seconds += (target_tick - previous_tick) * tempo / 1_000_000 / self.ticks_per_beat
        return seconds

    def tick_to_seconds(self, target_tick: int) -> float | None:
        return self._ticks_to_seconds(target_tick, self.tempos)

    def _format_two_sequences(self) -> list[dict[str, object]]:
        sequences: list[dict[str, object]] = []
        for track in range(self.track_count):
            tempos = sorted(self.track_tempos.get(track, []))
            initial_tempo = next(
                (tempo for tick, tempo in tempos if tick == 0), 500_000
            )
            end_tick = self.track_end_ticks.get(track, 0)
            duration = self._ticks_to_seconds(end_tick, tempos)
            notes = [note for note in self.notes if note.track == track]
            sequences.append({
                "sequence": track + 1,
                "name": self.track_names.get(track),
                "end_tick": end_tick,
                "duration_seconds": round(duration, 3) if duration is not None else None,
                "initial_bpm": round(60_000_000 / initial_tempo, 3),
                "tempo_changes": len(tempos),
                "notes": len(notes),
                "channels": sorted({note.channel + 1 for note in notes}),
                "status": "DERIVED",
            })
        return sequences

    def analysis(self) -> dict:
        pitches = Counter(note.pitch for note in self.notes)
        channels = Counter(note.channel + 1 for note in self.notes)
        velocities = [note.velocity for note in self.notes]
        format_two = self.format == 2
        duration = None if format_two else self.tick_to_seconds(self.max_tick)
        initial_tempo = 500_000
        for tick, tempo in sorted(self.tempos):
            if tick != 0:
                break
            initial_tempo = tempo

        velocity_stats = None
        if velocities:
            if np is not None:
                values = np.asarray(velocities, dtype=float)
                velocity_stats = {
                    "minimum": int(values.min()),
                    "maximum": int(values.max()),
                    "mean": round(float(values.mean()), 2),
                    "median": round(float(np.median(values)), 2),
                    "standard_deviation": round(float(values.std()), 2),
                }
            else:
                velocity_stats = {
                    "minimum": min(velocities),
                    "maximum": max(velocities),
                    "mean": round(sum(velocities) / len(velocities), 2),
                }

        result = {
            "file": str(self.path),
            "original_sha256": self.file_hash,
            "original_preserved": True,
            "format": self.format,
            "analysis_status": "PARTIAL" if format_two else "READY",
            "timeline_semantics": (
                "INDEPENDENT_SEQUENCES" if format_two else "SINGLE_TIMELINE"
            ),
            "tracks": self.track_count,
            "track_names": {str(index + 1): name for index, name in self.track_names.items()},
            "timing": self.ticks_per_beat or self.smpte,
            "duration_ticks": None if format_two else self.max_tick,
            "duration_seconds": round(duration, 3) if duration is not None else None,
            "initial_bpm": None if format_two else round(60_000_000 / initial_tempo, 3),
            "tempo_changes": None if format_two else len(self.tempos),
            "sequences": self._format_two_sequences() if format_two else [],
            "time_signatures": [
                {"tick": tick, "signature": f"{top}/{bottom}"}
                for tick, top, bottom in sorted(self.time_signatures)
            ],
            "key_signatures": [
                {"tick": tick, "sharps_flats": sf, "mode": mode}
                for tick, sf, mode in sorted(self.key_signatures)
            ],
            "notes": len(self.notes),
            "pitch_range": (
                {"lowest": note_name(min(pitches)), "highest": note_name(max(pitches))}
                if pitches else None
            ),
            "most_common_notes": [
                {"note": note_name(pitch), "count": count}
                for pitch, count in pitches.most_common(10)
            ],
            "average_velocity": velocity_stats["mean"] if velocity_stats else None,
            "velocity": velocity_stats,
            "notes_per_channel": dict(sorted(channels.items())),
            "maximum_polyphony_per_track": self._polyphony_by_track(),
            "percussion_notes": sum(note.channel == 9 for note in self.notes),
            "programs_per_channel": {
                str(channel + 1): sorted(program + 1 for program in programs)
                for channel, programs in sorted(self.programs.items())
            },
            "control_changes": {
                f"channel_{channel + 1}_cc_{controller}": count
                for (channel, controller), count in sorted(self.control_changes.items())
            },
            "sustain_events": sum(
                count for (channel, controller), count in self.control_changes.items()
                if controller == 64
            ),
            "pitch_bend_events_per_channel": {
                str(channel + 1): count for channel, count in sorted(self.pitch_bends.items())
            },
            "events": dict(self.event_counts),
            "warnings": self.warnings,
        }
        result["display_tracks"] = build_display_tracks(self)
        return result


def human_report(result: dict) -> str:
    duration = result["duration_seconds"]
    if result["format"] == 2:
        duration_line = "Trajanje: nema jedinstvene globalne vrijednosti (neovisne sekvence)"
        tempo_line = "Tempo: zaseban po sekvenci"
    else:
        duration_line = (
            f"Trajanje: {duration:.3f} s ({result['duration_ticks']} tickova)"
            if duration is not None else f"Trajanje: {result['duration_ticks']} tickova"
        )
        tempo_line = (
            f"Pocetni tempo: {result['initial_bpm']} BPM | "
            f"Promjene tempa: {result['tempo_changes']}"
        )
    lines = [
        f"MIDI: {result['file']}",
        f"Format: {result['format']} | Trackovi: {result['tracks']} | Timing: {result['timing']}",
        duration_line,
        tempo_line,
        f"Broj nota: {result['notes']} | Prosjecni velocity: {result['average_velocity']}",
    ]
    for sequence in result.get("sequences", []):
        lines.append(
            "Sekvenca {sequence}: {duration} s, {bpm} BPM, {notes} nota".format(
                sequence=sequence["sequence"],
                duration=sequence["duration_seconds"],
                bpm=sequence["initial_bpm"],
                notes=sequence["notes"],
            )
        )
    if result["pitch_range"]:
        pitch_range = result["pitch_range"]
        lines.append(f"Raspon: {pitch_range['lowest']} - {pitch_range['highest']}")
    if result["most_common_notes"]:
        common = ", ".join(f"{item['note']} ({item['count']})" for item in result["most_common_notes"])
        lines.append(f"Najcesce note: {common}")
    if result["notes_per_channel"]:
        channels = ", ".join(f"ch {ch}: {count}" for ch, count in result["notes_per_channel"].items())
        lines.append(f"Note po kanalima: {channels}")
    if result["track_names"]:
        names = ", ".join(f"{track}: {name}" for track, name in result["track_names"].items())
        lines.append(f"Trackovi: {names}")
    if result.get("libraries"):
        active = [name for name, info in result["libraries"].items() if info["available"]]
        lines.append(f"Aktivne biblioteke: {', '.join(active) if active else 'ugradjeni parser'}")
    for warning in result.get("warnings", []):
        lines.append(f"UPOZORENJE: {warning}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ucitaj i analiziraj Standard MIDI datoteku.")
    parser.add_argument("midi_file", help="Putanja do .mid ili .midi datoteke")
    parser.add_argument("--json", action="store_true", help="Ispisi rezultat kao JSON")
    parser.add_argument(
        "--advanced", action="store_true",
        help="Ako je dostupan music21, ukljuci sporiju analizu tonaliteta",
    )
    parser.add_argument(
        "--json-output", metavar="DATOTEKA",
        help="Spremi potpuni JSON izvjestaj u novu datoteku",
    )
    args = parser.parse_args()

    try:
        analyzer = MidiAnalyzer(args.midi_file)
        analyzer.load()
        result = analyzer.analysis()
        apply_library_integrations(analyzer.path, result, advanced=args.advanced)
    except (OSError, MidiError) as error:
        parser.error(str(error))

    if args.json_output:
        output = Path(args.json_output)
        if output.resolve() == analyzer.path.resolve():
            parser.error("JSON izvjestaj ne smije prepisati originalnu MIDI datoteku.")
        if output.exists():
            parser.error(f"Izlazna datoteka vec postoji: {output}")
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else human_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())