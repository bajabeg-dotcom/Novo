from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from collections import Counter, defaultdict, deque
from pathlib import Path
from zipfile import ZipFile

from midi_enhancer import MidiAnalyzer, MidiError, decode_text
from style_loader import MidiFileModel, StandardMidiLoader, sha256_path

FACTORY_ARCHIVE = Path("prism-uploads/Split Factory Styles.zip")
FACTORY_SHA256 = "ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e"


def vlq(value: int) -> bytes:
    result = [value & 0x7F]
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))


def track(events: list[bytes], *, end_of_track: bool = True) -> bytes:
    body = b"".join(events)
    if end_of_track:
        body += vlq(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def midi(
    tracks: list[bytes], *, format_number: int = 1, division: int = 480,
    declared_tracks: int | None = None,
) -> bytes:
    count = len(tracks) if declared_tracks is None else declared_tracks
    return (
        b"MThd" + struct.pack(">IHHH", 6, format_number, count, division)
        + b"".join(tracks)
    )


def event_rich_midi() -> bytes:
    conductor = track([
        vlq(0) + b"\xff\x03\x09Conductor",
        vlq(0) + b"\xff\x51\x03\x07\xa1\x20",
        vlq(0) + b"\xff\x58\x04\x04\x02\x18\x08",
        vlq(0) + b"\xff\x59\x02\xff\x01",
        vlq(0) + b"\xf0\x05\x7e\x7f\x09\x01\xf7",
    ])
    musical = track([
        vlq(0) + b"\xff\x03\x04Part",
        vlq(0) + b"\xb0\x00\x79",
        vlq(0) + b"\x20\x00",  # running-status CC32
        vlq(0) + b"\xc0\x21",
        vlq(0) + b"\x90\x3c\x64",
        vlq(0) + b"\x40\x50",  # running-status Note On
        vlq(0) + b"\xa0\x3c\x20",
        vlq(0) + b"\xb0\x40\x7f",
        vlq(0) + b"\xe0\x00\x40",
        vlq(0) + b"\xd0\x20",
        vlq(240) + b"\x80\x3c\x00",
        vlq(0) + b"\x40\x00",  # running-status Note Off
        vlq(0) + b"\x90\x41\x00",  # Note On zero is Note Off semantics
    ])
    return midi([conductor, musical])


def model_note_analysis(
    model: MidiFileModel,
) -> tuple[list[tuple[int, int, int, int, int, int]], int]:
    """Derive the analyzer's closed/synthetic-note view from preserved events."""
    result: list[tuple[int, int, int, int, int, int]] = []
    unterminated = 0
    for track_model in model.tracks:
        active: dict[tuple[int, int], deque[tuple[int, int]]] = defaultdict(deque)
        for event in track_model.events:
            if event.channel is None or len(event.data) < 2:
                continue
            pitch, value = event.data[:2]
            key = (event.channel, pitch)
            if event.kind == "note_on" and value > 0:
                active[key].append((event.absolute_tick, value))
            elif event.kind == "note_off" or (event.kind == "note_on" and value == 0):
                if active[key]:
                    start, velocity = active[key].popleft()
                    result.append(
                        (track_model.index, event.channel, pitch, velocity, start, event.absolute_tick)
                    )
        end_tick = track_model.events[-1].absolute_tick if track_model.events else 0
        for (channel, pitch), starts in active.items():
            for start, velocity in starts:
                result.append(
                    (track_model.index, channel, pitch, velocity, start, end_tick)
                )
                unterminated += 1
    return sorted(result), unterminated


def model_notes(model: MidiFileModel) -> list[tuple[int, int, int, int, int, int]]:
    return model_note_analysis(model)[0]


def model_fingerprint(model: MidiFileModel) -> dict[str, object]:
    events = [event for track_model in model.tracks for event in track_model.events]
    notes, unterminated = model_note_analysis(model)
    event_counts = Counter(event.kind for event in events)
    if unterminated:
        event_counts["unterminated_notes"] = unterminated
    tempos = [
        (event.absolute_tick, int.from_bytes(event.payload, "big"))
        for event in events if event.kind == "meta" and event.meta_type == 0x51 and len(event.payload) == 3
    ]
    meters = [
        (event.absolute_tick, event.payload[0], 2 ** event.payload[1])
        for event in events if event.kind == "meta" and event.meta_type == 0x58 and len(event.payload) >= 2
    ]
    keys = []
    for event in events:
        if event.kind == "meta" and event.meta_type == 0x59 and len(event.payload) == 2:
            sf = event.payload[0] if event.payload[0] < 128 else event.payload[0] - 256
            keys.append((event.absolute_tick, sf, "minor" if event.payload[1] else "major"))
    return {
        "format": model.format,
        "tracks": model.declared_track_count,
        "division": model.division,
        "sha256": model.sha256,
        "end_ticks": [track_model.events[-1].absolute_tick for track_model in model.tracks],
        "event_counts": event_counts,
        "notes": notes,
        "tempos": sorted(tempos),
        "meters": sorted(meters),
        "keys": sorted(keys),
        "track_names": {
            track_model.index: decode_text(event.payload)
            for track_model in model.tracks
            for event in track_model.events
            if event.kind == "meta" and event.meta_type == 0x03
        },
        "programs": Counter(
            (event.track_index, event.channel, event.data[0])
            for event in events if event.kind == "program_change"
        ),
        "controllers": Counter(
            (event.channel, event.data[0])
            for event in events if event.kind == "control_change"
        ),
        "pitch_bends": Counter(
            event.channel for event in events if event.kind == "pitch_bend"
        ),
    }


def analyzer_fingerprint(analyzer: MidiAnalyzer) -> dict[str, object]:
    return {
        "format": analyzer.format,
        "tracks": analyzer.track_count,
        "division": analyzer.division,
        "sha256": analyzer.file_hash,
        "end_ticks": [analyzer.track_end_ticks[index] for index in range(analyzer.track_count)],
        "event_counts": Counter(analyzer.event_counts),
        "notes": sorted(
            (note.track, note.channel, note.pitch, note.velocity, note.start_tick, note.end_tick)
            for note in analyzer.notes
        ),
        "tempos": sorted(analyzer.tempos),
        "meters": sorted(analyzer.time_signatures),
        "keys": sorted(analyzer.key_signatures),
        "track_names": dict(analyzer.track_names),
        "programs": Counter(analyzer.track_programs),
        "controllers": Counter(analyzer.control_changes),
        "pitch_bends": Counter(analyzer.pitch_bends),
    }


class ParserParityTests(unittest.TestCase):
    def parse_both(self, source: bytes) -> tuple[MidiAnalyzer, MidiFileModel, Path]:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name) / "parity.mid"
        path.write_bytes(source)
        analyzer = MidiAnalyzer(path)
        analyzer.load()
        model = StandardMidiLoader().load_bytes(source, source_name="parity.mid")
        return analyzer, model, path

    def acceptance(self, source: bytes) -> tuple[bool, bool]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.mid"
            path.write_bytes(source)
            try:
                MidiAnalyzer(path).load()
                analyzer_accepts = True
            except (MidiError, OSError):
                analyzer_accepts = False
        try:
            StandardMidiLoader().load_bytes(source, source_name="case.mid")
            loader_accepts = True
        except (MidiError, OSError):
            loader_accepts = False
        return analyzer_accepts, loader_accepts

    def test_valid_event_rich_file_has_same_core_fingerprint(self) -> None:
        source = event_rich_midi()
        analyzer, model, path = self.parse_both(source)
        expected = model_fingerprint(model)
        actual = analyzer_fingerprint(analyzer)

        self.assertEqual(actual, expected)
        self.assertEqual(path.read_bytes(), source)
        self.assertEqual(actual["sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(
            [b"".join(event.raw for event in item.events) for item in model.tracks],
            [item.body for item in model.tracks],
        )

    def test_malformed_acceptance_matrix_matches_and_rejects(self) -> None:
        eot = track([])
        cases = {
            "bad_header": b"NOPE" + event_rich_midi()[4:],
            "zero_tracks": midi([], declared_tracks=0),
            "format_zero_two_tracks": midi([eot, eot], format_number=0),
            "zero_ppq": midi([eot], format_number=0, division=0),
            "bad_smpte_fps": midi([eot], format_number=0, division=(0xE6 << 8) | 40),
            "zero_smpte_ticks": midi([eot], format_number=0, division=(0xE8 << 8)),
            "truncated_track": b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk\x00\x00\x00\x08\x00\x90",
            "invalid_vlq": midi([b"MTrk\x00\x00\x00\x05\x81\x80\x80\x80\x00"], format_number=0),
            "running_without_status": midi([track([b"\x00\x3c\x40"])], format_number=0),
            "truncated_sysex": midi([b"MTrk\x00\x00\x00\x04\x00\xf0\x05\x01"], format_number=0),
            "unsupported_system_status": midi([track([b"\x00\xf1\x00\x00"])], format_number=0),
            "invalid_data_byte": midi([track([b"\x00\x90\x3c\x80"])], format_number=0),
        }
        for name, source in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.acceptance(source), (False, False))

    def test_missing_end_of_track_is_accepted_but_reported_by_both(self) -> None:
        source = midi([
            track([
                vlq(0) + b"\x90\x3c\x64",
                vlq(120) + b"\x80\x3c\x00",
            ], end_of_track=False)
        ], format_number=0)
        analyzer, model, _path = self.parse_both(source)
        self.assertTrue(any("End-of-Track" in warning for warning in analyzer.warnings))
        self.assertTrue(any("End-of-Track" in warning for warning in model.tracks[0].warnings))
        self.assertEqual(model_notes(model), analyzer_fingerprint(analyzer)["notes"])

    @unittest.skipUnless(FACTORY_ARCHIVE.is_file(), "Factory corpus nije dostupan")
    def test_full_factory_corpus_has_core_parser_parity(self) -> None:
        before = sha256_path(FACTORY_ARCHIVE)
        self.assertEqual(before, FACTORY_SHA256)
        checked = 0
        with tempfile.TemporaryDirectory() as directory, ZipFile(FACTORY_ARCHIVE) as archive:
            path = Path(directory) / "member.mid"
            for info in archive.infolist():
                if info.is_dir() or not info.filename.lower().endswith((".mid", ".midi")):
                    continue
                source = archive.read(info)
                model = StandardMidiLoader().load_bytes(source, source_name=info.filename)
                path.write_bytes(source)
                analyzer = MidiAnalyzer(path)
                analyzer.load()
                with self.subTest(member=info.filename):
                    self.assertEqual(analyzer_fingerprint(analyzer), model_fingerprint(model))
                    self.assertEqual(path.read_bytes(), source)
                checked += 1
        self.assertEqual(checked, 3211)
        self.assertEqual(sha256_path(FACTORY_ARCHIVE), before)

    def test_valid_smpte_division_agrees(self) -> None:
        division = (0xE7 << 8) | 40  # -25 fps, 40 ticks/frame
        source = midi([track([])], format_number=0, division=division)
        analyzer, model, _path = self.parse_both(source)
        self.assertEqual(analyzer.smpte, {"frames_per_second": 25, "ticks_per_frame": 40})
        self.assertEqual(model.smpte, (25, 40))
        self.assertIsNone(analyzer.ticks_per_beat)
        self.assertIsNone(model.ticks_per_beat)


if __name__ == "__main__":
    unittest.main()
