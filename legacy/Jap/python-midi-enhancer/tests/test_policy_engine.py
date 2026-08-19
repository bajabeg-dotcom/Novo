from __future__ import annotations

import struct
import unittest

from change_plan import (
    EvidenceReference,
    EvidenceStatus,
    EventMutation,
    InputMeasurement,
    MutationField,
    PlanState,
    RiskLevel,
    create_proposal,
)
from policy_engine import PolicyEngine, PolicyError, PolicyRule, PolicyVerdict
from style_loader import StandardMidiLoader


def event_source(value: int = 100):
    body = bytes([0, 0xB0, 7, value, 0, 0xFF, 0x2F, 0])
    source = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192) + b"MTrk" + struct.pack(">I", len(body)) + body
    model = StandardMidiLoader().load_bytes(source, source_name="policy.mid")
    event = model.tracks[0].events[0]
    return model, event


def make_proposal(model, event, *, status=EvidenceStatus.DERIVED, risk=RiskLevel.LOW):
    return create_proposal(
        source_sha256=model.sha256,
        rule_id="P01.CC7_BOUNDED",
        rule_version="1.0.0",
        title="Bounded CC7 change",
        description="One exact controller change for policy testing.",
        evidence_status=status,
        confidence_percent=(80.0 if status is EvidenceStatus.INFERRED else None),
        risk=risk,
        input_measurements=(
            InputMeasurement("controller", 7, "CC", EvidenceStatus.CONFIRMED),
        ),
        evidence=(
            EvidenceReference("EVENT", status, "Exact or derived source evidence"),
        ),
        mutations=(EventMutation.from_event(event, MutationField.DATA_1, 80),),
        expected_difference="CC7 value 100 -> 80",
        protections=("Suggest only",),
    )


def rule(*, allow_inferred: bool = False, maximum_risk=RiskLevel.MEDIUM):
    return PolicyRule(
        rule_id="P01.CC7_BOUNDED",
        version="1.0.0",
        description="Allow one bounded CC7 data value in Suggest mode.",
        allowed_event_kinds=("control_change",),
        allowed_fields=(MutationField.DATA_1,),
        maximum_risk=maximum_risk,
        allow_inferred_evidence=allow_inferred,
    )


class PolicyEngineTests(unittest.TestCase):
    def test_valid_exact_proposal_can_enter_suggest_plan_only(self) -> None:
        model, event = event_source()
        proposal = make_proposal(model, event)
        engine = PolicyEngine((rule(),))
        events = {(event.track_index, event.event_index): event}
        result = engine.evaluate(proposal, events)
        self.assertEqual(result.verdict, PolicyVerdict.SUGGEST_ALLOWED)
        self.assertEqual(result.reasons, ())
        self.assertFalse(result.apply_authorized)
        plan = engine.build_plan(
            source_sha256=model.sha256, proposals=(proposal,), events=events
        )
        self.assertEqual(plan.phase, "SUGGEST")
        self.assertEqual(plan.state, PlanState.AWAITING_CONFIRMATION)
        self.assertFalse(plan.apply_authorized)

    def test_changed_or_missing_source_event_blocks_proposal(self) -> None:
        model, event = event_source()
        proposal = make_proposal(model, event)
        engine = PolicyEngine((rule(),))
        changed_model, changed_event = event_source(99)
        changed = engine.evaluate(
            proposal,
            {(changed_event.track_index, changed_event.event_index): changed_event},
        )
        self.assertEqual(changed.verdict, PolicyVerdict.BLOCKED)
        self.assertTrue(any("old value mismatch" in item for item in changed.reasons))
        self.assertTrue(any("SHA-256 mismatch" in item for item in changed.reasons))
        missing = engine.evaluate(proposal, {})
        self.assertEqual(missing.verdict, PolicyVerdict.BLOCKED)
        with self.assertRaises(PolicyError):
            engine.build_plan(source_sha256=changed_model.sha256, proposals=(proposal,), events={})

    def test_unknown_conflict_and_blocking_evidence_never_enter_suggest(self) -> None:
        model, event = event_source()
        engine = PolicyEngine((rule(allow_inferred=True, maximum_risk=RiskLevel.HIGH),))
        events = {(0, 0): event}
        for status in (
            EvidenceStatus.UNKNOWN,
            EvidenceStatus.CONFLICT,
            EvidenceStatus.UNSUPPORTED,
        ):
            with self.subTest(status=status):
                proposal = make_proposal(model, event, status=status)
                result = engine.evaluate(proposal, events)
                self.assertEqual(result.verdict, PolicyVerdict.BLOCKED)
        blocking = make_proposal(model, event, risk=RiskLevel.BLOCKING)
        self.assertEqual(engine.evaluate(blocking, events).verdict, PolicyVerdict.BLOCKED)

    def test_inferred_evidence_requires_rule_opt_in(self) -> None:
        model, event = event_source()
        proposal = make_proposal(model, event, status=EvidenceStatus.INFERRED)
        events = {(0, 0): event}
        blocked = PolicyEngine((rule(allow_inferred=False),)).evaluate(proposal, events)
        allowed = PolicyEngine((rule(allow_inferred=True),)).evaluate(proposal, events)
        self.assertEqual(blocked.verdict, PolicyVerdict.BLOCKED)
        self.assertEqual(allowed.verdict, PolicyVerdict.SUGGEST_ALLOWED)

    def test_unregistered_version_kind_field_and_risk_are_blocked(self) -> None:
        model, event = event_source()
        proposal = make_proposal(model, event, risk=RiskLevel.HIGH)
        events = {(0, 0): event}
        risk_result = PolicyEngine((rule(maximum_risk=RiskLevel.MEDIUM),)).evaluate(
            proposal, events
        )
        self.assertEqual(risk_result.verdict, PolicyVerdict.BLOCKED)

        wrong_version = create_proposal(
            source_sha256=model.sha256,
            rule_id="P01.CC7_BOUNDED",
            rule_version="2.0.0",
            title="Wrong version",
            description="Mismatch",
            evidence_status=EvidenceStatus.DERIVED,
            confidence_percent=None,
            risk=RiskLevel.LOW,
            input_measurements=(InputMeasurement("x", 1, None, EvidenceStatus.DERIVED),),
            evidence=(EvidenceReference("E", EvidenceStatus.CONFIRMED, "detail"),),
            mutations=(EventMutation.from_event(event, MutationField.DATA_1, 80),),
            expected_difference="one",
            protections=(),
        )
        version_result = PolicyEngine((rule(),)).evaluate(wrong_version, events)
        self.assertEqual(version_result.verdict, PolicyVerdict.BLOCKED)

        unregistered = create_proposal(
            source_sha256=model.sha256,
            rule_id="P01.UNREGISTERED",
            rule_version="1.0.0",
            title="Unknown rule",
            description="Mismatch",
            evidence_status=EvidenceStatus.DERIVED,
            confidence_percent=None,
            risk=RiskLevel.LOW,
            input_measurements=(InputMeasurement("x", 1, None, EvidenceStatus.DERIVED),),
            evidence=(EvidenceReference("E", EvidenceStatus.CONFIRMED, "detail"),),
            mutations=(EventMutation.from_event(event, MutationField.DATA_1, 80),),
            expected_difference="one",
            protections=(),
        )
        self.assertEqual(
            PolicyEngine((rule(),)).evaluate(unregistered, events).verdict,
            PolicyVerdict.BLOCKED,
        )

    def test_duplicate_rule_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(PolicyError, "duplicate"):
            PolicyEngine((rule(), rule()))


if __name__ == "__main__":
    unittest.main()
