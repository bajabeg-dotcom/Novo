from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from midi_enhancer import MidiError
from style_loader import StandardMidiLoader, StyleWorksLoader, collection_report


ARCHIVE = Path("prism-uploads/Split Factory Styles.zip")


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


def midi(tracks: list[bytes], *, format_number: int = 1, division: int = 192) -> bytes:
    return b"MThd" + struct.pack(">IHHH", 6, format_number, len(tracks), division) + b"".join(tracks)


class StandardMidiLoaderTests(unittest.TestCase):
    def test_rejects_truncated_track_without_mutating_source(self) -> None:
        source = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192) + b"MTrk" + struct.pack(">I", 8) + b"\x00\x90"
        snapshot = bytes(source)
        with self.assertRaises(MidiError):
            StandardMidiLoader().load_bytes(source, source_name="broken.mid")
        self.assertEqual(source, snapshot)

    def test_preserves_running_status_and_raw_events(self) -> None:
        source = midi([track([
            vlq(0) + b"\x90\x3c\x64",
            vlq(96) + b"\x40\x50",
            vlq(96) + b"\x80\x3c\x00",
            vlq(0) + b"\x40\x00",
        ])], format_number=0)
        model = StandardMidiLoader().load_bytes(source, source_name="running.mid")
        events = model.tracks[0].events

        self.assertEqual(model.sha256, hashlib.sha256(source).hexdigest())
        self.assertTrue(events[0].status_explicit)
        self.assertFalse(events[1].status_explicit)
        self.assertEqual(events[1].status, 0x90)
        self.assertEqual(b"".join(event.raw for event in events), model.tracks[0].body)

    def test_style_window_excludes_trailing_content(self) -> None:
        conductor = track([vlq(0) + b"\xff\x58\x04\x04\x02\x18\x08"])
        musical = track([
            vlq(0) + b"\xff\x01\x07Intro 1",
            vlq(0) + b"\xff\x01\x06\x31 Bars",
            vlq(0) + b"\xb9\x00\x78",
            vlq(0) + b"\xb9\x20\x00",
            vlq(0) + b"\xc9\x29",
            vlq(0) + b"\x99\x24\x64",
            vlq(768) + b"\x89\x24\x00",
            vlq(1) + b"\x99\x26\x70",
            vlq(24) + b"\x89\x26\x00",
        ])
        model = StyleWorksLoader().load_element_bytes(
            midi([conductor, musical]), member_name="Styles/Test/Test_Intro1.mid"
        )
        slice_model = model.tracks[1]

        self.assertEqual(model.valid_end_tick, 768)
        self.assertEqual(slice_model.note_on_count, 1)
        self.assertGreater(len(slice_model.trailing_event_indexes), 0)
        self.assertEqual(slice_model.instrument_selections[0].address, "120.0.41")


@unittest.skipUnless(ARCHIVE.is_file(), "Factory Style arhiv nije dostupan")
class FactoryStyleCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.loader = StyleWorksLoader()
        cls.summary = cls.loader.inspect_archive(ARCHIVE)
        cls.report = collection_report(cls.summary)

    def test_full_archive_structure_and_preservation(self) -> None:
        self.assertTrue(self.summary.original_preserved)
        self.assertEqual(
            self.summary.sha256_before,
            "ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e",
        )
        self.assertEqual(self.summary.midi_file_count, 3211)
        self.assertEqual(len(self.summary.styles), 252)
        self.assertEqual(self.summary.complete_style_count, 230)
        self.assertEqual(len(self.summary.invalid_members), 0)
        self.assertEqual(self.report["formats"], {1: 3211})
        self.assertEqual(self.report["divisions"], {192: 3211})
        self.assertEqual(self.report["analysis_blocked_elements"], 1)
        self.assertEqual(self.report["element_warning_count"], 1)

    def test_pilot_style_and_declared_window(self) -> None:
        fox = next(style for style in self.summary.styles if style.style_name == "50's  Fox")
        self.assertTrue(fox.complete)
        variation = next(element for element in fox.elements if element.element == "VARIATION_1")
        self.assertEqual(variation.declared_bars, 2)
        self.assertEqual(variation.meter, (2, 4))
        self.assertEqual(variation.valid_end_tick, 768)

        kool = self.loader.load_archive_element(
            ARCHIVE, "Workspace_Styles/Kool Beat/Kool Beat_Intro1.mid"
        )
        self.assertEqual(kool.declared_bars, 4)
        self.assertEqual(kool.meter, (4, 4))
        self.assertEqual(kool.valid_end_tick, 3072)
        self.assertGreater(sum(len(item.trailing_event_indexes) for item in kool.tracks), 0)

        conflict = self.loader.load_archive_element(
            ARCHIVE, "Workspace_Styles/Fox Shuffle 1/Fox Shuffle 1_Break.mid"
        )
        self.assertIsNone(conflict.valid_end_tick)
        self.assertIn("Konflikt deklariranog broja taktova", conflict.warnings[0])
        self.assertEqual(sum(item.note_on_count for item in conflict.tracks), 0)


if __name__ == "__main__":
    unittest.main()