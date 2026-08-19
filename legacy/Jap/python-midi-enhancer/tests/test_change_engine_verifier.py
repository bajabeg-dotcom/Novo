from __future__ import annotations

import hashlib
import struct
import unittest
from dataclasses import replace

from change_engine import (
    BytePreservingChangeEngine,
    ChangeExecutionError,
    ChangeExecutionStatus,
    create_execution_request,
)
from change_plan import PlanState, UserDecision
from change_verifier import IndependentChangeVerifier, VerificationStatus
from instrument_identity_resolver import InstrumentIdentityResolver
from instrument_segmenter import InstrumentSegmenter, SegmentationInput
from k03_sound_replacement import K03SoundReplacementBuilder
from style_loader import StandardMidiLoader


def vlq(value: int) -> bytes:
    result = [value & 0x7F]
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))


def midi(*, running_cc32: bool = False) -> bytes:
    events = [
        b"\x00\xb0\x00\x79",
        b"\x00\x20\x00" if running_cc32 else b"\x00\xb0\x20\x00",
        b"\x00\xc0\x21",
        b"\x00\x90\x3c\x5a",
        vlq(96) + b"\x80\x3c\x00",
        b"\x00\xff\x2f\x00",
    ]
    body = b"".join(events)
    return (
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192)
        + b"MTrk" + struct.pack(">I", len(body)) + body
    )


def approved_k03(source: bytes, target: str = "121.1.34"):
    model = StandardMidiLoader().load_bytes(source, source_name="change.mid")
    events = model.tracks[0].events
    segmentation = InstrumentSegmenter().segment(SegmentationInput(
        source_sha256=model.sha256,
        events=events,
        ticks_per_beat=model.ticks_per_beat,
        window_end_tick=384,
    ))
    identities = InstrumentIdentityResolver().resolve(segmentation)
    plan = K03SoundReplacementBuilder().build_plan(
        segmentation=segmentation,
        identities=identities,
        events=events,
        segment_ordinal=1,
        target_address=target,
        user_selected=True,
    )
    approved = plan.record_decision(
        plan.proposals[0].proposal_id,
        UserDecision.APPROVE,
        decided_at="2026-08-14T14:00:00+02:00",
    )
    return model, approved


def execute(source: bytes, target: str = "121.1.34"):
    model, plan = approved_k03(source, target)
    request = create_execution_request(
        plan, requested_at="2026-08-14T14:01:00+02:00"
    )
    result = BytePreservingChangeEngine().execute(
        plan=plan, request=request, source_bytes=source
    )
    return model, plan, request, result


class ChangeEngineVerifierTests(unittest.TestCase):
    def test_engine_changes_working_copy_verifier_passes_and_rollback_is_exact(self) -> None:
        source = midi()
        model, plan, request, result = execute(source)
        self.assertEqual(plan.state, PlanState.APPROVED)
        self.assertEqual(request.actor, "USER")
        self.assertEqual(result.status, ChangeExecutionStatus.PENDING_VERIFICATION)
        self.assertFalse(result.verified)
        self.assertFalse(result.save_authorized)
        self.assertTrue(result.original_preserved)
        self.assertEqual(result.original_bytes, source)
        self.assertNotEqual(result.working_bytes, source)
        self.assertEqual(len(result.applied_mutations), 2)
        self.assertEqual(hashlib.sha256(source).hexdigest(), model.sha256)

        verification = IndependentChangeVerifier().verify(plan=plan, result=result)
        self.assertEqual(verification.status, VerificationStatus.PASS)
        self.assertEqual(verification.expected_mutation_count, 2)
        self.assertEqual(verification.actual_changed_byte_count, 2)
        self.assertEqual(verification.verified_bytes, result.working_bytes)
        self.assertTrue(verification.save_authorized)
        self.assertEqual(verification.reasons, ())

        parsed = StandardMidiLoader().load_bytes(verification.verified_bytes)
        controls = [e for e in parsed.tracks[0].events if e.kind == "control_change"]
        program = next(e for e in parsed.tracks[0].events if e.kind == "program_change")
        self.assertEqual(controls[1].data, (32, 1))
        self.assertEqual(program.data, (34,))
        self.assertEqual(sum(e.is_note_on for e in parsed.tracks[0].events), 1)

        rolled_back = result.rollback()
        self.assertEqual(rolled_back.status, ChangeExecutionStatus.ROLLED_BACK)
        self.assertEqual(rolled_back.working_bytes, source)
        self.assertEqual(rolled_back.output_sha256, model.sha256)
        self.assertEqual(rolled_back.applied_mutations, ())
        self.assertFalse(rolled_back.save_authorized)

    def test_running_status_is_preserved_while_cc_data_byte_changes(self) -> None:
        source = midi(running_cc32=True)
        _model, plan, _request, result = execute(source)
        verification = IndependentChangeVerifier().verify(plan=plan, result=result)
        self.assertEqual(verification.status, VerificationStatus.PASS)
        original = StandardMidiLoader().load_bytes(source)
        changed = StandardMidiLoader().load_bytes(result.working_bytes)
        original_cc32 = [e for e in original.tracks[0].events if e.kind == "control_change"][1]
        changed_cc32 = [e for e in changed.tracks[0].events if e.kind == "control_change"][1]
        self.assertFalse(original_cc32.status_explicit)
        self.assertFalse(changed_cc32.status_explicit)
        self.assertEqual(original_cc32.status, changed_cc32.status)
        self.assertEqual(original_cc32.raw[:-1], changed_cc32.raw[:-1])
        self.assertEqual((original_cc32.raw[-1], changed_cc32.raw[-1]), (0, 1))

    def test_unapproved_plan_and_non_user_execution_request_are_blocked(self) -> None:
        source = midi()
        model = StandardMidiLoader().load_bytes(source)
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
        with self.assertRaisesRegex(ChangeExecutionError, "approved"):
            create_execution_request(plan, requested_at="2026-08-14T14:01:00+02:00")
        approved = plan.record_decision(
            plan.proposals[0].proposal_id,
            UserDecision.APPROVE,
            decided_at="2026-08-14T14:00:00+02:00",
        )
        with self.assertRaisesRegex(ChangeExecutionError, "actor"):
            create_execution_request(
                approved,
                requested_at="2026-08-14T14:01:00+02:00",
                actor="SYSTEM",
            )

    def test_tampered_source_is_rejected_before_working_copy(self) -> None:
        source = midi()
        _model, plan = approved_k03(source)
        request = create_execution_request(
            plan, requested_at="2026-08-14T14:01:00+02:00"
        )
        tampered = bytearray(source)
        note_index = source.index(b"\x90\x3c\x5a") + 2
        tampered[note_index] = 89
        with self.assertRaisesRegex(ChangeExecutionError, "SHA-256"):
            BytePreservingChangeEngine().execute(
                plan=plan, request=request, source_bytes=bytes(tampered)
            )

    def test_verifier_blocks_extra_unapproved_byte_even_with_updated_output_hash(self) -> None:
        source = midi()
        _model, plan, _request, result = execute(source)
        tampered = bytearray(result.working_bytes)
        note_index = result.working_bytes.index(b"\x90\x3c\x5a") + 2
        tampered[note_index] = 89
        changed = bytes(tampered)
        forged = replace(
            result,
            working_bytes=changed,
            output_sha256=hashlib.sha256(changed).hexdigest(),
        )
        verification = IndependentChangeVerifier().verify(plan=plan, result=forged)
        self.assertEqual(verification.status, VerificationStatus.FAIL)
        self.assertFalse(verification.save_authorized)
        self.assertIsNone(verification.verified_bytes)
        self.assertTrue(any("Unexpected changed byte" in item for item in verification.reasons))

    def test_verifier_blocks_forged_applied_record_and_truncated_output(self) -> None:
        source = midi()
        _model, plan, _request, result = execute(source)
        first = result.applied_mutations[0]
        forged_record = replace(first, absolute_byte_offset=first.absolute_byte_offset + 1)
        forged = replace(
            result,
            applied_mutations=(forged_record,) + result.applied_mutations[1:],
        )
        record_check = IndependentChangeVerifier().verify(plan=plan, result=forged)
        self.assertEqual(record_check.status, VerificationStatus.FAIL)
        self.assertTrue(any("Applied record mismatch" in item for item in record_check.reasons))

        truncated_bytes = result.working_bytes[:-1]
        truncated = replace(
            result,
            working_bytes=truncated_bytes,
            output_sha256=hashlib.sha256(truncated_bytes).hexdigest(),
        )
        parse_check = IndependentChangeVerifier().verify(plan=plan, result=truncated)
        self.assertEqual(parse_check.status, VerificationStatus.FAIL)
        self.assertTrue(any("reparse failed" in item.lower() for item in parse_check.reasons))


if __name__ == "__main__":
    unittest.main()
