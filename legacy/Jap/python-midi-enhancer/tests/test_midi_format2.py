from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from midi_enhancer import MidiAnalyzer, apply_library_integrations, human_report
from style_loader import StandardMidiLoader


def vlq(value: int) -> bytes:
    result = [value & 0x7F]
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))


def track(events: list[bytes]) -> bytes:
    body = b"".join(events + [vlq(0) + b"\xff\x2f\x00"])
    return b"MTrk" + struct.pack(">I", len(body)) + body


def format_two_file() -> bytes:
    sequence_one = track([
        vlq(0) + b"\xff\x03\x05First",
        vlq(0) + b"\xff\x51\x03\x07\xa1\x20",  # 120 BPM
        vlq(0) + b"\xc0\x00",
        vlq(0) + b"\x90\x3c\x64",
        vlq(960) + b"\x80\x3c\x00",
    ])
    sequence_two = track([
        vlq(0) + b"\xff\x03\x06Second",
        vlq(0) + b"\xff\x51\x03\x0f\x42\x40",  # 60 BPM
        vlq(0) + b"\xc1\x28",
        vlq(0) + b"\x91\x43\x5a",
        vlq(480) + b"\x81\x43\x00",
    ])
    header = b"MThd" + struct.pack(">IHHH", 6, 2, 2, 480)
    return header + sequence_one + sequence_two


class MidiFormatTwoTests(unittest.TestCase):
    def test_independent_sequences_do_not_create_false_global_timeline(self) -> None:
        source = format_two_file()
        digest = hashlib.sha256(source).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "independent.mid"
            path.write_bytes(source)
            analyzer = MidiAnalyzer(path)
            analyzer.load()
            result = analyzer.analysis()

            self.assertEqual(path.read_bytes(), source)
            self.assertEqual(result["original_sha256"], digest)
            self.assertTrue(result["original_preserved"])
            self.assertEqual(result["format"], 2)
            self.assertEqual(result["analysis_status"], "PARTIAL")
            self.assertEqual(result["timeline_semantics"], "INDEPENDENT_SEQUENCES")
            self.assertIsNone(result["duration_ticks"])
            self.assertIsNone(result["duration_seconds"])
            self.assertIsNone(result["initial_bpm"])
            self.assertIsNone(result["tempo_changes"])
            self.assertIn("neovisne sekvence", " ".join(result["warnings"]))

            self.assertEqual(len(result["sequences"]), 2)
            first, second = result["sequences"]
            self.assertEqual(
                (first["end_tick"], first["duration_seconds"], first["initial_bpm"]),
                (960, 1.0, 120.0),
            )
            self.assertEqual(
                (second["end_tick"], second["duration_seconds"], second["initial_bpm"]),
                (480, 1.0, 60.0),
            )
            self.assertEqual(first["notes"], 1)
            self.assertEqual(second["notes"], 1)

    def test_format_two_display_keeps_sequences_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "display.mid"
            path.write_bytes(format_two_file())
            analyzer = MidiAnalyzer(path)
            analyzer.load()
            result = analyzer.analysis()

        self.assertEqual(len(result["display_tracks"]), 16)
        self.assertEqual(result["display_tracks"][0]["source"], "Sequence 1")
        self.assertEqual(result["display_tracks"][1]["source"], "Sequence 2")
        self.assertEqual(result["display_tracks"][0]["notes"], 1)
        self.assertEqual(result["display_tracks"][1]["notes"], 1)
        self.assertEqual(result["display_tracks"][2]["notes"], 0)
        self.assertIn("nema jedinstvene globalne vrijednosti", human_report(result))

    def test_global_optional_analyzers_are_skipped_for_format_two(self) -> None:
        statuses = {
            "numpy": {"available": True, "version": None, "purpose": "statistics"},
            "mido": {"available": False, "version": None, "purpose": "validation"},
            "pretty_midi": {"available": True, "version": None, "purpose": "tempo"},
            "music21": {"available": True, "version": None, "purpose": "harmony"},
        }
        result = {"format": 2, "notes": 2}
        with patch("midi_enhancer.library_status", return_value=statuses), patch(
            "midi_enhancer.importlib.import_module",
            side_effect=AssertionError("global analyzer must not be imported"),
        ):
            apply_library_integrations(Path("unused.mid"), result, advanced=True)

        self.assertTrue(result["external_analysis"]["pretty_midi"]["skipped"])
        self.assertTrue(result["external_analysis"]["music21"]["skipped"])

    def test_both_parsers_agree_on_format_two_structure(self) -> None:
        source = format_two_file()
        model = StandardMidiLoader().load_bytes(source, source_name="format2.mid")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "format2.mid"
            path.write_bytes(source)
            analyzer = MidiAnalyzer(path)
            analyzer.load()

        self.assertEqual(model.format, analyzer.format)
        self.assertEqual(model.declared_track_count, analyzer.track_count)
        self.assertEqual(model.division, analyzer.division)
        self.assertEqual(model.sha256, analyzer.file_hash)
        self.assertEqual(
            [track.events[-1].absolute_tick for track in model.tracks],
            [analyzer.track_end_ticks[index] for index in range(analyzer.track_count)],
        )
        self.assertEqual(
            [b"".join(event.raw for event in track.events) for track in model.tracks],
            [track.body for track in model.tracks],
        )


if __name__ == "__main__":
    unittest.main()
