from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from change_engine import BytePreservingChangeEngine, create_execution_request
from change_plan import UserDecision
from change_verifier import IndependentChangeVerifier, VerificationStatus
from instrument_identity_resolver import InstrumentIdentityResolver
from instrument_segmenter import InstrumentSegmenter, SegmentationInput
from k03_sound_replacement import K03SoundReplacementBuilder
from style_loader import StandardMidiLoader
from verified_writer import AtomicVerifiedWriter, VerifiedWriterError, WriteStatus


def midi() -> bytes:
    body = b"".join([
        b"\x00\xb0\x00\x79",
        b"\x00\xb0\x20\x00",
        b"\x00\xc0\x21",
        b"\x00\x90\x3c\x5a",
        b"\x60\x80\x3c\x00",
        b"\x00\xff\x2f\x00",
    ])
    return (
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192)
        + b"MTrk" + struct.pack(">I", len(body)) + body
    )


def verified_chain(source: bytes):
    model = StandardMidiLoader().load_bytes(source, source_name="writer.mid")
    events = model.tracks[0].events
    segmentation = InstrumentSegmenter().segment(SegmentationInput(
        model.sha256, events, model.ticks_per_beat, window_end_tick=384
    ))
    identities = InstrumentIdentityResolver().resolve(segmentation)
    plan = K03SoundReplacementBuilder().build_plan(
        segmentation=segmentation,
        identities=identities,
        events=events,
        segment_ordinal=1,
        target_address="121.1.34",
        user_selected=True,
    )
    plan = plan.record_decision(
        plan.proposals[0].proposal_id,
        UserDecision.APPROVE,
        decided_at="2026-08-14T15:00:00+02:00",
    )
    request = create_execution_request(
        plan, requested_at="2026-08-14T15:01:00+02:00"
    )
    execution = BytePreservingChangeEngine().execute(
        plan=plan, request=request, source_bytes=source
    )
    verification = IndependentChangeVerifier().verify(plan=plan, result=execution)
    if verification.status is not VerificationStatus.PASS:
        raise AssertionError(verification.reasons)
    return plan, execution, verification


class VerifiedWriterTests(unittest.TestCase):
    def test_passed_bytes_are_atomically_saved_as_new_midi_and_json(self) -> None:
        source_bytes = midi()
        plan, execution, verification = verified_chain(source_bytes)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "song.mid"
            output = root / "song_enhanced.mid"
            report = root / "song_enhanced.json"
            source.write_bytes(source_bytes)

            result = AtomicVerifiedWriter().write(
                source_path=source,
                output_midi_path=output,
                output_report_path=report,
                plan=plan,
                execution=execution,
                verification=verification,
                saved_at="2026-08-14T15:02:00+02:00",
            )

            self.assertEqual(result.status, WriteStatus.SAVED)
            self.assertTrue(result.rollback_available)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(output.read_bytes(), verification.verified_bytes)
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), result.output_sha256)
            parsed = StandardMidiLoader().load_path(output)
            self.assertEqual(parsed.sha256, verification.output_sha256)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "PASS")
            self.assertEqual(data["plan"]["plan_id"], plan.plan_id)
            self.assertFalse(data["plan"]["apply_authorized_field"])
            self.assertTrue(data["verification"]["save_authorized"])
            self.assertEqual(data["verification"]["mutation_count"], 2)
            self.assertFalse(data["safety"]["source_overwritten"])
            self.assertEqual(hashlib.sha256(report.read_bytes()).hexdigest(), result.report_sha256)
            self.assertFalse(list(root.glob(".*.tmp")))

    def test_existing_output_or_report_is_never_overwritten(self) -> None:
        source_bytes = midi()
        plan, execution, verification = verified_chain(source_bytes)
        for occupied in ("midi", "report"):
            with self.subTest(occupied=occupied), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "song.mid"
                output = root / "song_enhanced.mid"
                report = root / "song_enhanced.json"
                source.write_bytes(source_bytes)
                target = output if occupied == "midi" else report
                target.write_bytes(b"DO NOT OVERWRITE")
                with self.assertRaisesRegex(VerifiedWriterError, "already exists"):
                    AtomicVerifiedWriter().write(
                        source_path=source,
                        output_midi_path=output,
                        output_report_path=report,
                        plan=plan,
                        execution=execution,
                        verification=verification,
                        saved_at="2026-08-14T15:02:00+02:00",
                    )
                self.assertEqual(target.read_bytes(), b"DO NOT OVERWRITE")
                self.assertEqual(source.read_bytes(), source_bytes)

    def test_source_change_bad_name_and_failed_verifier_block_save(self) -> None:
        source_bytes = midi()
        plan, execution, verification = verified_chain(source_bytes)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "song.mid"
            source.write_bytes(source_bytes + b"X")
            with self.assertRaisesRegex(VerifiedWriterError, "SHA-256 changed"):
                AtomicVerifiedWriter().write(
                    source_path=source,
                    output_midi_path=root / "song_enhanced.mid",
                    output_report_path=root / "song_enhanced.json",
                    plan=plan,
                    execution=execution,
                    verification=verification,
                    saved_at="2026-08-14T15:02:00+02:00",
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "song.mid"
            source.write_bytes(source_bytes)
            with self.assertRaisesRegex(VerifiedWriterError, "end with _enhanced"):
                AtomicVerifiedWriter().write(
                    source_path=source,
                    output_midi_path=root / "song-copy.mid",
                    output_report_path=root / "song-copy.json",
                    plan=plan,
                    execution=execution,
                    verification=verification,
                    saved_at="2026-08-14T15:02:00+02:00",
                )
            failed = replace(
                verification,
                status=VerificationStatus.FAIL,
                reasons=("forced",),
                verified_bytes=None,
                save_authorized=False,
            )
            with self.assertRaisesRegex(VerifiedWriterError, "Verifier PASS"):
                AtomicVerifiedWriter().write(
                    source_path=source,
                    output_midi_path=root / "song_enhanced.mid",
                    output_report_path=root / "song_enhanced.json",
                    plan=plan,
                    execution=execution,
                    verification=failed,
                    saved_at="2026-08-14T15:02:00+02:00",
                )

    def test_second_atomic_publish_failure_removes_midi_and_temporaries(self) -> None:
        source_bytes = midi()
        plan, execution, verification = verified_chain(source_bytes)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "song.mid"
            output = root / "song_enhanced.mid"
            report = root / "song_enhanced.json"
            source.write_bytes(source_bytes)
            real_link = os.link
            calls = 0

            def flaky_link(src, dst):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated report publication failure")
                return real_link(src, dst)

            with patch("verified_writer.os.link", side_effect=flaky_link):
                with self.assertRaisesRegex(VerifiedWriterError, "atomic save failed"):
                    AtomicVerifiedWriter().write(
                        source_path=source,
                        output_midi_path=output,
                        output_report_path=report,
                        plan=plan,
                        execution=execution,
                        verification=verification,
                        saved_at="2026-08-14T15:02:00+02:00",
                    )
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())
            self.assertFalse(list(root.glob(".*.tmp")))
            self.assertEqual(source.read_bytes(), source_bytes)

    def test_filesystem_rollback_deletes_only_untampered_writer_outputs(self) -> None:
        source_bytes = midi()
        plan, execution, verification = verified_chain(source_bytes)
        writer = AtomicVerifiedWriter()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "song.mid"
            output = root / "song_enhanced.mid"
            report = root / "song_enhanced.json"
            source.write_bytes(source_bytes)
            result = writer.write(
                source_path=source,
                output_midi_path=output,
                output_report_path=report,
                plan=plan,
                execution=execution,
                verification=verification,
                saved_at="2026-08-14T15:02:00+02:00",
            )
            rolled_back = writer.rollback(result)
            self.assertEqual(rolled_back.status, WriteStatus.ROLLED_BACK)
            self.assertFalse(rolled_back.rollback_available)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())
            self.assertEqual(source.read_bytes(), source_bytes)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "song.mid"
            output = root / "song_enhanced.mid"
            report = root / "song_enhanced.json"
            source.write_bytes(source_bytes)
            result = writer.write(
                source_path=source,
                output_midi_path=output,
                output_report_path=report,
                plan=plan,
                execution=execution,
                verification=verification,
                saved_at="2026-08-14T15:02:00+02:00",
            )
            output.write_bytes(output.read_bytes() + b"tampered")
            with self.assertRaisesRegex(VerifiedWriterError, "MIDI was modified"):
                writer.rollback(result)
            self.assertTrue(output.exists())
            self.assertTrue(report.exists())
            self.assertEqual(source.read_bytes(), source_bytes)


if __name__ == "__main__":
    unittest.main()
