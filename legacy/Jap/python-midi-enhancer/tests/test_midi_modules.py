from __future__ import annotations

import struct
import tempfile
import unittest
import importlib.util
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from midi_enhancer import MidiAnalyzer
from midi_instruments import infer_role


def vlq(value: int) -> bytes:
    result = [value & 0x7F]
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))


def midi_track(events: list[bytes]) -> bytes:
    body = b"".join(events + [vlq(0) + b"\xff\x2f\x00"])
    return b"MTrk" + struct.pack(">I", len(body)) + body


def midi_file(format_number: int, tracks: list[bytes]) -> bytes:
    header = b"MThd" + struct.pack(">IHHH", 6, format_number, len(tracks), 480)
    return header + b"".join(tracks)


def note(pitch: int, start: int, duration: int = 240) -> SimpleNamespace:
    return SimpleNamespace(
        pitch=pitch,
        start_tick=start,
        end_tick=start + duration,
        duration_ticks=duration,
    )


class MidiModuleTests(unittest.TestCase):
    def test_format_zero_and_one(self) -> None:
        format_zero_track = midi_track([
            vlq(0) + b"\xc0\x00",
            vlq(0) + b"\x90\x3c\x64",
            vlq(480) + b"\x80\x3c\x00",
            vlq(0) + b"\x99\x24\x70",
            vlq(120) + b"\x89\x24\x00",
        ])
        conductor = midi_track([vlq(0) + b"\xff\x51\x03\x07\xa1\x20"])
        piano = midi_track([
            vlq(0) + b"\xc0\x00",
            vlq(0) + b"\x90\x3c\x64",
            vlq(480) + b"\x80\x3c\x00",
        ])

        with tempfile.TemporaryDirectory() as directory:
            format_zero_path = Path(directory) / "format0.mid"
            format_one_path = Path(directory) / "format1.mid"
            format_zero_path.write_bytes(midi_file(0, [format_zero_track]))
            format_one_path.write_bytes(midi_file(1, [conductor, piano]))

            format_zero = MidiAnalyzer(format_zero_path)
            format_zero.load()
            result_zero = format_zero.analysis()
            self.assertEqual(len(result_zero["display_tracks"]), 16)
            self.assertEqual(result_zero["display_tracks"][0]["source"], "Channel 1")
            self.assertEqual(result_zero["display_tracks"][9]["role"], "Drum / percussion groove")

            format_one = MidiAnalyzer(format_one_path)
            format_one.load()
            result_one = format_one.analysis()
            self.assertEqual(len(result_one["display_tracks"]), 16)
            self.assertEqual(result_one["display_tracks"][0]["role"], "Conductor / structure")
            self.assertEqual(result_one["display_tracks"][1]["instrument"], "Acoustic Grand Piano")

    def test_guitar_roles(self) -> None:
        common = {
            "name": "Guitar",
            "programs": Counter({30: 1}),
            "channels": Counter({0: 1}),
            "ticks_per_beat": 480,
        }
        power_notes = [note(40, 0), note(47, 0), note(43, 480), note(50, 480)]
        rhythm_notes = [
            note(pitch, start)
            for start, chord in ((0, (48, 52, 55)), (480, (53, 57, 60)))
            for pitch in chord
        ]
        solo_notes = [note(64, 0), note(67, 240), note(71, 480)]

        power = infer_role(notes=power_notes, maximum_polyphony=2, pitch_bends=0, **common)
        rhythm = infer_role(notes=rhythm_notes, maximum_polyphony=3, pitch_bends=0, **common)
        solo = infer_role(notes=solo_notes, maximum_polyphony=1, pitch_bends=2, **common)

        self.assertEqual(power["role"], "Power-chord guitar")
        self.assertEqual(rhythm["role"], "Rhythm guitar")
        self.assertEqual(solo["role"], "Solo guitar")

    @unittest.skipUnless(importlib.util.find_spec("tkinter"), "tkinter nije dostupan u workspaceu")
    def test_gui_module_imports(self) -> None:
        import midi_gui

        self.assertTrue(hasattr(midi_gui, "MidiEnhancerApp"))


if __name__ == "__main__":
    unittest.main()