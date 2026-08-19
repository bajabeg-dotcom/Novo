from __future__ import annotations

import json
import os
import struct
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from gui_change_workflow import GuiChangeWorkflow
from midi_enhancer import MidiAnalyzer
from midi_gui import MidiEnhancerApp


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


def midi(format_number: int, tracks: list[bytes]) -> bytes:
    return b"MThd" + struct.pack(">IHHH", 6, format_number, len(tracks), 480) + b"".join(tracks)


def format_zero_file() -> bytes:
    return midi(0, [track([
        vlq(0) + b"\xff\x51\x03\x07\xa1\x20",
        vlq(0) + b"\xc0\x00",
        vlq(0) + b"\x90\x3c\x64",
        vlq(480) + b"\x80\x3c\x00",
    ])])


def format_zero_factory_file() -> bytes:
    return midi(0, [track([
        vlq(0) + b"\xff\x51\x03\x07\xa1\x20",
        vlq(0) + b"\xb0\x00\x79",
        vlq(0) + b"\xb0\x20\x00",
        vlq(0) + b"\xc0\x21",
        vlq(0) + b"\x90\x3c\x64",
        vlq(480) + b"\x80\x3c\x00",
    ])])


def format_two_file() -> bytes:
    first = track([
        vlq(0) + b"\xff\x51\x03\x07\xa1\x20",
        vlq(0) + b"\x90\x3c\x64",
        vlq(480) + b"\x80\x3c\x00",
    ])
    second = track([
        vlq(0) + b"\xff\x51\x03\x0f\x42\x40",
        vlq(0) + b"\x91\x43\x5a",
        vlq(480) + b"\x81\x43\x00",
    ])
    return midi(2, [first, second])


@unittest.skipUnless(os.environ.get("DISPLAY"), "GUI runtime test zahtijeva X display")
class GuiRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.app = MidiEnhancerApp(self.root)
        self.root.update_idletasks()

    def tearDown(self) -> None:
        if self.root.winfo_exists():
            self.root.destroy()

    def analyze(self, path: Path) -> dict:
        analyzer = MidiAnalyzer(path)
        analyzer.load()
        return analyzer.analysis()

    def test_window_renders_format_zero_and_exports_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gui.mid"
            output = Path(directory) / "gui_analysis.json"
            path.write_bytes(format_zero_file())
            result = self.analyze(path)
            self.app._show_result(path, result)
            self.root.update_idletasks()

            self.assertEqual(self.root.title(), "Prism MIDI Enhancer")
            self.assertEqual(len(self.app.cards), 16)
            self.assertEqual(self.app.summary_vars["format"].get(), "FORMAT 0")
            self.assertEqual(self.app.summary_vars["tracks"].get(), "1")
            self.assertEqual(self.app.summary_vars["notes"].get(), "1")
            self.assertEqual(self.app.summary_vars["status"].get(), "READY")
            self.assertIn("channels mapped", self.app.mapping_label.cget("text"))
            self.assertEqual(self.app.cards[0].data["source"], "Channel 1")
            self.assertEqual(self.app.cards[0].data["notes"], 1)

            with patch("midi_gui.filedialog.asksaveasfilename", return_value=str(output)), patch(
                "midi_gui.messagebox.showinfo"
            ) as showinfo:
                self.app.export_json()
            exported = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exported["original_sha256"], result["original_sha256"])
            self.assertEqual(exported["notes"], 1)
            showinfo.assert_called_once()
            self.assertEqual(path.read_bytes(), format_zero_file())

    def test_window_marks_format_two_as_per_sequence_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gui-format2.mid"
            path.write_bytes(format_two_file())
            result = self.analyze(path)
            self.app._show_result(path, result)
            self.root.update_idletasks()

            self.assertEqual(self.app.summary_vars["format"].get(), "FORMAT 2")
            self.assertEqual(self.app.summary_vars["duration"].get(), "PER SEQUENCE")
            self.assertEqual(self.app.summary_vars["tempo"].get(), "PER SEQUENCE")
            self.assertEqual(self.app.summary_vars["status"].get(), "PARTIAL / READ-ONLY")
            self.assertIn("independent sequences", self.app.mapping_label.cget("text"))
            self.assertEqual(self.app.cards[0].data["source"], "Sequence 1")
            self.assertEqual(self.app.cards[1].data["source"], "Sequence 2")
            self.assertEqual(path.read_bytes(), format_two_file())

    def test_factory_dialog_preview_verify_save_and_rollback(self) -> None:
        source_bytes = format_zero_factory_file()
        with tempfile.TemporaryDirectory() as directory:
            root_dir = Path(directory)
            path = root_dir / "factory.mid"
            output = root_dir / "factory_enhanced.mid"
            path.write_bytes(source_bytes)
            result = self.analyze(path)
            workflow = GuiChangeWorkflow(path)
            self.app._show_result(path, result, workflow)
            self.root.update_idletasks()

            self.assertEqual(str(self.app.factory_button["state"]), "normal")
            self.app.open_factory_replacement()
            dialog = self.app.replacement_dialog
            self.assertIsNotNone(dialog)
            dialog.window.update_idletasks()
            target_label = next(
                label for label, item in dialog.target_by_label.items()
                if item.address == "121.0.34"
            )
            dialog.target_var.set(target_label)
            dialog.preview_change()
            dialog.window.update_idletasks()
            self.assertIn("EXACT ALLOWED DIFFERENCES", dialog.preview_text.get("1.0", "end"))
            self.assertEqual(str(dialog.approve_button["state"]), "normal")

            with patch("midi_gui.messagebox.askyesno", return_value=True):
                dialog.approve_and_verify()
            self.assertEqual(str(dialog.save_button["state"]), "normal")
            self.assertIn("Verifier PASS", dialog.status_var.get())

            with patch("midi_gui.filedialog.asksaveasfilename", return_value=str(output)), patch(
                "midi_gui.messagebox.showinfo"
            ):
                dialog.save_verified()
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".json").is_file())
            self.assertEqual(str(dialog.rollback_button["state"]), "normal")
            self.assertEqual(path.read_bytes(), source_bytes)

            with patch("midi_gui.messagebox.askyesno", return_value=True):
                dialog.rollback_saved()
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".json").exists())
            self.assertEqual(path.read_bytes(), source_bytes)
            dialog.window.destroy()


if __name__ == "__main__":
    unittest.main()
