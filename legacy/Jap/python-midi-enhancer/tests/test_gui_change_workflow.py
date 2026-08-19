from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from change_verifier import VerificationStatus
from gui_change_workflow import GuiChangeWorkflow, GuiWorkflowError
from verified_writer import WriteStatus


def midi(
    *, cc00: int = 121, cc32: int = 0, pc: int = 33,
    second_program: int | None = None,
) -> bytes:
    events = [
        bytes([0, 0xB0, 0, cc00]),
        bytes([0, 0xB0, 32, cc32]),
        bytes([0, 0xC0, pc]),
        b"\x00\x90\x3c\x5a",
        b"\x60\x80\x3c\x00",
    ]
    if second_program is not None:
        events.extend([
            bytes([0, 0xC0, second_program]),
            b"\x00\x90\x3e\x5a",
            b"\x60\x80\x3e\x00",
        ])
    events.append(b"\x00\xff\x2f\x00")
    body = b"".join(events)
    return (
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192)
        + b"MTrk" + struct.pack(">I", len(body)) + body
    )


class GuiChangeWorkflowTests(unittest.TestCase):
    def make_workflow(self, root: Path, source_bytes: bytes) -> tuple[Path, GuiChangeWorkflow]:
        source = root / "song.mid"
        source.write_bytes(source_bytes)
        return source, GuiChangeWorkflow(source)

    def test_load_lists_eligible_segment_and_compatible_factory_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, workflow = self.make_workflow(Path(directory), midi())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), workflow.model.sha256)
            self.assertEqual(len(workflow.segment_options), 1)
            segment = workflow.segment_options[0]
            self.assertEqual(segment.requested_address, "121.0.33")
            self.assertEqual(segment.official_name, "Finger Bass GM")
            self.assertEqual(segment.item_kind, "FACTORY_SOUND")
            targets = workflow.target_options(segment.ordinal)
            self.assertEqual(len(targets), 1006)
            self.assertTrue(all(item.kind == "FACTORY_SOUND" for item in targets))
            self.assertTrue(any(item.address == "121.0.34" for item in targets))

    def test_preview_approval_verify_save_and_rollback_full_gui_backend(self) -> None:
        source_bytes = midi()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, workflow = self.make_workflow(root, source_bytes)
            preview = workflow.create_preview(
                segment_ordinal=1,
                target_address="121.0.34",
                user_selected=True,
            )
            self.assertEqual(preview.segment.requested_address, "121.0.33")
            self.assertEqual(preview.target.address, "121.0.34")
            self.assertEqual(preview.risk, "MEDIUM")
            self.assertEqual(len(preview.mutation_lines), 1)
            self.assertIn("program_change", preview.mutation_lines[0])
            self.assertFalse(preview.plan.apply_authorized)

            verification = workflow.approve_and_verify(
                decision_time="2026-08-14T16:00:00+02:00",
                execution_time="2026-08-14T16:01:00+02:00",
                user_confirmed=True,
            )
            self.assertEqual(verification.status, VerificationStatus.PASS)
            self.assertTrue(verification.save_authorized)
            self.assertEqual(source.read_bytes(), source_bytes)

            output = root / "song_enhanced.mid"
            saved = workflow.save(
                output_midi_path=output,
                saved_at="2026-08-14T16:02:00+02:00",
            )
            self.assertEqual(saved.status, WriteStatus.SAVED)
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".json").is_file())
            self.assertEqual(source.read_bytes(), source_bytes)

            rolled_back = workflow.rollback_saved(user_confirmed=True)
            self.assertEqual(rolled_back.status, WriteStatus.ROLLED_BACK)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".json").exists())
            self.assertEqual(source.read_bytes(), source_bytes)

    def test_stage_order_and_explicit_user_confirmations_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _source, workflow = self.make_workflow(root, midi())
            with self.assertRaisesRegex(GuiWorkflowError, "preview"):
                workflow.approve_and_verify(
                    decision_time="2026-08-14T16:00:00+02:00",
                    execution_time="2026-08-14T16:01:00+02:00",
                    user_confirmed=True,
                )
            with self.assertRaisesRegex(GuiWorkflowError, "explicitly selected"):
                workflow.create_preview(
                    segment_ordinal=1,
                    target_address="121.0.34",
                    user_selected=False,
                )
            workflow.create_preview(
                segment_ordinal=1,
                target_address="121.0.34",
                user_selected=True,
            )
            with self.assertRaisesRegex(GuiWorkflowError, "confirmation"):
                workflow.approve_and_verify(
                    decision_time="2026-08-14T16:00:00+02:00",
                    execution_time="2026-08-14T16:01:00+02:00",
                    user_confirmed=False,
                )
            with self.assertRaisesRegex(GuiWorkflowError, "Verifier PASS"):
                workflow.save(
                    output_midi_path=root / "song_enhanced.mid",
                    saved_at="2026-08-14T16:02:00+02:00",
                )
            with self.assertRaisesRegex(GuiWorkflowError, "confirmation"):
                workflow.rollback_saved(user_confirmed=False)

    def test_unknown_segment_is_not_exposed_as_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _source, workflow = self.make_workflow(Path(directory), midi(cc00=122, pc=1))
            self.assertEqual(workflow.segment_options, ())
            with self.assertRaisesRegex(GuiWorkflowError, "not eligible"):
                workflow.create_preview(
                    segment_ordinal=1,
                    target_address="121.0.34",
                    user_selected=True,
                )

    def test_shared_bank_change_error_is_exposed_without_source_change(self) -> None:
        source_bytes = midi(second_program=34)
        with tempfile.TemporaryDirectory() as directory:
            source, workflow = self.make_workflow(Path(directory), source_bytes)
            self.assertEqual(len(workflow.segment_options), 2)
            with self.assertRaisesRegex(GuiWorkflowError, "shared"):
                workflow.create_preview(
                    segment_ordinal=1,
                    target_address="121.1.33",
                    user_selected=True,
                )
            self.assertEqual(source.read_bytes(), source_bytes)


if __name__ == "__main__":
    unittest.main()
