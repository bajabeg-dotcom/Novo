from __future__ import annotations

import hashlib
import json
import struct
import unittest

from change_plan import (
    ChangePlanError,
    EvidenceReference,
    EvidenceStatus,
    EventMutation,
    InputMeasurement,
    MutationField,
    PlanState,
    RiskLevel,
    UserDecision,
    create_plan,
    create_proposal,
    render_plan,
)
from style_loader import StandardMidiLoader


def source_event():
    body = b"\x00\xb0\x07\x64\x00\xff\x2f\x00"
    source = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192) + b"MTrk" + struct.pack(">I", len(body)) + body
    model = StandardMidiLoader().load_bytes(source, source_name="plan.mid")
    return source, model, model.tracks[0].events[0]


def proposal_for(source_sha256: str, event, *, new_value: int = 80, status=EvidenceStatus.DERIVED):
    mutation = EventMutation.from_event(event, MutationField.DATA_1, new_value)
    return create_proposal(
        source_sha256=source_sha256,
        rule_id="P01.TEST_VOLUME",
        rule_version="1.0.0",
        title="Test volume proposal",
        description="Change one exact controller value in Suggest mode.",
        evidence_status=status,
        confidence_percent=(75.0 if status is EvidenceStatus.INFERRED else None),
        risk=RiskLevel.LOW,
        input_measurements=(
            InputMeasurement("controller", 7, "CC", EvidenceStatus.CONFIRMED),
            InputMeasurement("old_value", event.data[1], "MIDI_7BIT", EvidenceStatus.CONFIRMED),
        ),
        evidence=(
            EvidenceReference("TEST-SOURCE", EvidenceStatus.CONFIRMED, "Synthetic exact event"),
        ),
        mutations=(mutation,),
        expected_difference="Only CC7 data[1] changes from 100 to 80.",
        protections=("No writer is present.",),
    )


class ChangePlanTests(unittest.TestCase):
    def test_proposal_and_plan_ids_are_deterministic_and_serialization_is_stable(self) -> None:
        source, model, event = source_event()
        first = proposal_for(model.sha256, event)
        second = proposal_for(model.sha256, event)
        self.assertEqual(first, second)
        plan_one = create_plan(source_sha256=model.sha256, proposals=(first,), created_by="POLICY_ENGINE")
        plan_two = create_plan(source_sha256=model.sha256, proposals=(second,), created_by="POLICY_ENGINE")
        self.assertEqual(plan_one.plan_id, plan_two.plan_id)
        self.assertEqual(render_plan(plan_one), render_plan(plan_two))
        parsed = json.loads(render_plan(plan_one))
        self.assertEqual(parsed["phase"], "SUGGEST")
        self.assertFalse(parsed["apply_authorized"])
        self.assertEqual(parsed["expected_mutation_count"], 1)
        self.assertEqual(hashlib.sha256(source).hexdigest(), plan_one.source_sha256)

    def test_explicit_user_decision_changes_state_but_never_authorizes_apply(self) -> None:
        _source, model, event = source_event()
        proposal = proposal_for(model.sha256, event)
        plan = create_plan(source_sha256=model.sha256, proposals=(proposal,), created_by="POLICY_ENGINE")
        self.assertEqual(plan.state, PlanState.AWAITING_CONFIRMATION)
        approved = plan.record_decision(
            proposal.proposal_id,
            UserDecision.APPROVE,
            decided_at="2026-08-14T12:00:00+02:00",
        )
        self.assertEqual(approved.state, PlanState.APPROVED)
        self.assertEqual(approved.approved_proposal_ids, (proposal.proposal_id,))
        self.assertFalse(approved.apply_authorized)
        self.assertEqual(plan.decisions, ())
        rejected = approved.record_decision(
            proposal.proposal_id,
            UserDecision.REJECT,
            decided_at="2026-08-14T12:01:00+02:00",
            note="User changed decision",
        )
        self.assertEqual(rejected.state, PlanState.REJECTED)
        self.assertEqual(rejected.approved_proposal_ids, ())
        self.assertEqual(len(rejected.decisions), 2)

    def test_non_user_or_timezone_free_decision_is_rejected(self) -> None:
        _source, model, event = source_event()
        proposal = proposal_for(model.sha256, event)
        plan = create_plan(source_sha256=model.sha256, proposals=(proposal,), created_by="POLICY_ENGINE")
        with self.assertRaisesRegex(ChangePlanError, "explicit USER"):
            plan.record_decision(
                proposal.proposal_id, UserDecision.APPROVE,
                decided_at="2026-08-14T12:00:00+02:00", actor="SYSTEM",
            )
        with self.assertRaisesRegex(ChangePlanError, "timezone"):
            plan.record_decision(
                proposal.proposal_id, UserDecision.APPROVE,
                decided_at="2026-08-14T12:00:00",
            )

    def test_inferred_evidence_requires_percentage_and_confirmed_forbids_it(self) -> None:
        _source, model, event = source_event()
        mutation = EventMutation.from_event(event, MutationField.DATA_1, 80)
        common = dict(
            source_sha256=model.sha256,
            rule_id="P01.TEST_VOLUME",
            rule_version="1.0.0",
            title="Title",
            description="Description",
            risk=RiskLevel.LOW,
            input_measurements=(InputMeasurement("x", 1, None, EvidenceStatus.DERIVED),),
            evidence=(EvidenceReference("E", EvidenceStatus.CONFIRMED, "detail"),),
            mutations=(mutation,),
            expected_difference="one value",
            protections=(),
        )
        with self.assertRaisesRegex(ChangePlanError, "requires confidence"):
            create_proposal(
                **common, evidence_status=EvidenceStatus.INFERRED, confidence_percent=None
            )
        with self.assertRaisesRegex(ChangePlanError, "must not use"):
            create_proposal(
                **common, evidence_status=EvidenceStatus.CONFIRMED, confidence_percent=99.0
            )

    def test_duplicate_event_field_across_proposals_is_rejected(self) -> None:
        _source, model, event = source_event()
        first = proposal_for(model.sha256, event, new_value=80)
        second = proposal_for(model.sha256, event, new_value=70)
        with self.assertRaisesRegex(ChangePlanError, "multiple proposals"):
            create_plan(
                source_sha256=model.sha256,
                proposals=(first, second),
                created_by="POLICY_ENGINE",
            )

    def test_noop_and_out_of_range_mutations_are_rejected(self) -> None:
        _source, _model, event = source_event()
        with self.assertRaisesRegex(ChangePlanError, "no-op"):
            EventMutation.from_event(event, MutationField.DATA_1, 100)
        with self.assertRaisesRegex(ChangePlanError, "0..127"):
            EventMutation.from_event(event, MutationField.DATA_1, 128)


if __name__ == "__main__":
    unittest.main()
