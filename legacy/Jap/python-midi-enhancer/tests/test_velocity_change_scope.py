from __future__ import annotations

import json
import struct
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from change_engine import BytePreservingChangeEngine, ChangeExecutionError, create_execution_request
from change_plan import UserDecision
from change_verifier import IndependentChangeVerifier, VerificationStatus
from contextual_profile_builder import ContextualProfileBuilder, ProfileKey, ProfileObservation
from profile_suggest_engine import ProfileVelocitySuggestor, SuggestionStatus
from style_loader import StandardMidiLoader
from velocity_change_scope import (
    VELOCITY_SWITCH_RISK_ACK,
    VelocityChangeScopeError,
    create_velocity_execution_request,
)
from verified_writer import AtomicVerifiedWriter, WriteStatus

SHA = "c" * 64


def profile_catalog():
    key = ProfileKey(
        source_kind="FACTORY_STYLE", address="121.0.33",
        item_kind="FACTORY_SOUND", function="ACCOMP_CHORDAL",
        element="VARIATION_1", cv=1, structural_role="ACC1",
        encoding="ORDINARY_MIDI", fixed_intro_ending_candidate=False,
    )
    observations = []
    for index in range(3):
        velocities = (50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 60, 70)
        observations.append(ProfileObservation(
            source_id="FACTORY", source_sha256=SHA, source_kind="FACTORY_STYLE",
            member_name=f"S{index}/S{index}_Var1.mid", style_name=f"S{index}",
            key=key, official_name="Finger Bass GM", segment_status="READY",
            measurement_status="READY", velocities=velocities,
            pitches=tuple(range(48, 60)), duration_beats=(0.5,) * 12,
            density_per_beat=2.0, maximum_sounding_polyphony=2,
            maximum_onset_polyphony=2, controller_event_counts=(),
        ))
    catalog = ContextualProfileBuilder().build_from_observations(
        observations, source_id="FACTORY", source_path="factory.zip",
        source_sha256=SHA, source_kind="FACTORY_STYLE",
    )
    return key, catalog


def midi_source() -> bytes:
    # Second Note On uses running status and is an upper outlier.
    body = b"".join([
        b"\x00\xc0\x21",
        b"\x00\x90\x3c\x14",  # velocity 20
        b"\x00\x3d\x78",      # running Note On, velocity 120
        b"\x30\x80\x3c\x00",
        b"\x00\x3d\x00",      # running Note Off
        b"\x00\xff\x2f\x00",
    ])
    return (
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192)
        + b"MTrk" + struct.pack(">I", len(body)) + body
    )


def approved_s01(source: bytes):
    model = StandardMidiLoader().load_bytes(source, source_name="velocity.mid")
    key, catalog = profile_catalog()
    result = ProfileVelocitySuggestor().suggest(
        catalog=catalog, key=key, source_sha256=model.sha256,
        events=model.tracks[0].events, identity_status="FACTORY_CONFIRMED",
        classification_status="CLASSIFIED", classification_confidence=82,
        edit_policy="SAFE_BOUNDED", user_enabled_rule=True,
    )
    if result.status is not SuggestionStatus.SUGGEST_PLAN_READY or result.plan is None:
        raise AssertionError(result)
    plan = result.plan.record_decision(
        result.plan.proposals[0].proposal_id,
        UserDecision.APPROVE,
        decided_at="2026-08-14T18:00:00+02:00",
    )
    return model, plan


class VelocityChangeScopeTests(unittest.TestCase):
    def test_specialized_user_ack_executes_verifies_saves_and_rolls_back(self) -> None:
        source_bytes = midi_source()
        model, plan = approved_s01(source_bytes)
        request = create_velocity_execution_request(
            plan,
            requested_at="2026-08-14T18:01:00+02:00",
            user_acknowledged_unknown_switch_risk=True,
        )
        self.assertEqual(request.authorized_rule_ids, ("S01.PROFILE_VELOCITY_OUTLIER",))
        self.assertEqual(request.risk_acknowledgements, (VELOCITY_SWITCH_RISK_ACK,))
        execution = BytePreservingChangeEngine().execute(
            plan=plan, request=request, source_bytes=source_bytes
        )
        verification = IndependentChangeVerifier().verify(plan=plan, result=execution)
        self.assertEqual(verification.status, VerificationStatus.PASS)
        self.assertTrue(verification.save_authorized)
        output = StandardMidiLoader().load_bytes(verification.verified_bytes)
        notes = [event for event in output.tracks[0].events if event.is_note_on]
        self.assertEqual([event.data[1] for event in notes], [28, 112])
        self.assertTrue(notes[0].status_explicit)
        self.assertFalse(notes[1].status_explicit)
        self.assertEqual(sum(event.is_note_on for event in output.tracks[0].events), 2)
        self.assertEqual(model.sha256, plan.source_sha256)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "velocity.mid"
            target = root / "velocity_enhanced.mid"
            source.write_bytes(source_bytes)
            saved = AtomicVerifiedWriter().write(
                source_path=source, output_midi_path=target,
                output_report_path=target.with_suffix(".json"), plan=plan,
                execution=execution, verification=verification,
                saved_at="2026-08-14T18:02:00+02:00",
            )
            self.assertEqual(saved.status, WriteStatus.SAVED)
            report = json.loads(target.with_suffix(".json").read_text())
            self.assertEqual(
                report["execution"]["risk_acknowledgements"],
                [VELOCITY_SWITCH_RISK_ACK],
            )
            rolled = AtomicVerifiedWriter().rollback(saved)
            self.assertEqual(rolled.status, WriteStatus.ROLLED_BACK)
            self.assertEqual(source.read_bytes(), source_bytes)

    def test_missing_ack_and_generic_request_remain_blocked(self) -> None:
        source = midi_source()
        _model, plan = approved_s01(source)
        with self.assertRaisesRegex(VelocityChangeScopeError, "acknowledge"):
            create_velocity_execution_request(
                plan, requested_at="2026-08-14T18:01:00+02:00",
                user_acknowledged_unknown_switch_risk=False,
            )
        generic = create_execution_request(
            plan, requested_at="2026-08-14T18:01:00+02:00"
        )
        with self.assertRaisesRegex(ChangeExecutionError, "lacks rule authorization"):
            BytePreservingChangeEngine().execute(
                plan=plan, request=generic, source_bytes=source
            )

    def test_velocity_zero_and_large_adjustment_are_blocked_before_execution(self) -> None:
        source = midi_source()
        _model, plan = approved_s01(source)
        proposal = plan.proposals[0]
        first = proposal.mutations[0]
        for new_value, message in ((0, "1..127"), (40, "exceeds 8")):
            with self.subTest(new_value=new_value):
                forged_mutation = replace(first, new_value=new_value)
                forged_proposal = replace(
                    proposal,
                    mutations=(forged_mutation,) + proposal.mutations[1:],
                )
                forged_plan = replace(plan, proposals=(forged_proposal,))
                with self.assertRaisesRegex(VelocityChangeScopeError, message):
                    create_velocity_execution_request(
                        forged_plan,
                        requested_at="2026-08-14T18:01:00+02:00",
                        user_acknowledged_unknown_switch_risk=True,
                    )

    def test_independent_verifier_rejects_removed_specialized_ack(self) -> None:
        source = midi_source()
        _model, plan = approved_s01(source)
        request = create_velocity_execution_request(
            plan, requested_at="2026-08-14T18:01:00+02:00",
            user_acknowledged_unknown_switch_risk=True,
        )
        execution = BytePreservingChangeEngine().execute(
            plan=plan, request=request, source_bytes=source
        )
        forged_request = replace(request, risk_acknowledgements=())
        forged = replace(execution, request=forged_request)
        verification = IndependentChangeVerifier().verify(plan=plan, result=forged)
        self.assertEqual(verification.status, VerificationStatus.FAIL)
        self.assertFalse(verification.save_authorized)
        self.assertTrue(any("acknowledgement missing" in item for item in verification.reasons))


if __name__ == "__main__":
    unittest.main()
