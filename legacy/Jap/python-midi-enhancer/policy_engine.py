"""Read-only Policy Engine for auditable Suggest-phase Change Plans.

A policy verdict can allow a proposal to appear in Suggest mode. It never
confirms the proposal for the user and never authorizes Apply or writes MIDI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from change_plan import (
    ChangePlan,
    ChangePlanError,
    ChangeProposal,
    EvidenceStatus,
    EventRef,
    MutationField,
    RiskLevel,
    create_plan,
)
from style_loader import MidiEvent


class PolicyError(ValueError):
    """Raised when a proposal cannot enter a Change Plan."""


class PolicyVerdict(str, Enum):
    SUGGEST_ALLOWED = "SUGGEST_ALLOWED"
    BLOCKED = "BLOCKED"


RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.BLOCKING: 3,
}


@dataclass(frozen=True, slots=True)
class PolicyRule:
    rule_id: str
    version: str
    description: str
    allowed_event_kinds: tuple[str, ...]
    allowed_fields: tuple[MutationField, ...]
    maximum_risk: RiskLevel
    allow_inferred_evidence: bool
    requires_user_confirmation: bool = True


@dataclass(frozen=True, slots=True)
class PolicyResult:
    proposal_id: str
    rule_id: str
    verdict: PolicyVerdict
    reasons: tuple[str, ...]
    checked_mutation_ids: tuple[str, ...]
    apply_authorized: bool = False


class PolicyEngine:
    """Validate exact proposals against named rules and current source events."""

    def __init__(self, rules: tuple[PolicyRule, ...]):
        if not rules:
            raise PolicyError("Policy Engine requires at least one named rule")
        ids = [rule.rule_id for rule in rules]
        if len(ids) != len(set(ids)):
            raise PolicyError("duplicate policy rule ID")
        self._rules = {rule.rule_id: rule for rule in rules}

    @property
    def rules(self) -> tuple[PolicyRule, ...]:
        return tuple(self._rules[key] for key in sorted(self._rules))

    def evaluate(
        self,
        proposal: ChangeProposal,
        events: Mapping[EventRef, MidiEvent],
    ) -> PolicyResult:
        reasons: list[str] = []
        rule = self._rules.get(proposal.rule_id)
        if rule is None:
            reasons.append("Proposal rule ID is not registered.")
            return self._result(proposal, PolicyVerdict.BLOCKED, reasons)
        if proposal.rule_version != rule.version:
            reasons.append("Proposal rule version does not match Policy Engine rule version.")
        if not rule.requires_user_confirmation or not proposal.requires_user_confirmation:
            reasons.append("Rule and proposal must require explicit user confirmation.")
        if RISK_ORDER[proposal.risk] > RISK_ORDER[rule.maximum_risk]:
            reasons.append("Proposal risk exceeds the rule maximum.")
        if proposal.risk is RiskLevel.BLOCKING:
            reasons.append("BLOCKING risk cannot enter Suggest plan.")
        if proposal.evidence_status in {
            EvidenceStatus.CONFLICT,
            EvidenceStatus.UNKNOWN,
            EvidenceStatus.UNSUPPORTED,
        }:
            reasons.append(f"Evidence status {proposal.evidence_status.value} blocks Suggest.")
        if (
            proposal.evidence_status is EvidenceStatus.INFERRED
            and not rule.allow_inferred_evidence
        ):
            reasons.append("Rule does not allow inferred evidence.")
        if any(
            item.status in {
                EvidenceStatus.CONFLICT,
                EvidenceStatus.UNKNOWN,
                EvidenceStatus.UNSUPPORTED,
            }
            for item in proposal.evidence
        ):
            reasons.append("At least one evidence reference has a blocking status.")

        for mutation in proposal.mutations:
            event = events.get(mutation.event_ref)
            if event is None:
                reasons.append(f"Missing source event for {mutation.event_ref}.")
                continue
            for error in mutation.verify_event(event):
                reasons.append(f"{mutation.mutation_id}: {error}.")
            if mutation.event_kind not in rule.allowed_event_kinds:
                reasons.append(
                    f"{mutation.mutation_id}: event kind {mutation.event_kind} is not allowed."
                )
            if mutation.field not in rule.allowed_fields:
                reasons.append(
                    f"{mutation.mutation_id}: field {mutation.field.value} is not allowed."
                )

        verdict = PolicyVerdict.BLOCKED if reasons else PolicyVerdict.SUGGEST_ALLOWED
        return self._result(proposal, verdict, reasons)

    def build_plan(
        self,
        *,
        source_sha256: str,
        proposals: tuple[ChangeProposal, ...],
        events: Mapping[EventRef, MidiEvent],
    ) -> ChangePlan:
        results = tuple(self.evaluate(proposal, events) for proposal in proposals)
        blocked = [result for result in results if result.verdict is PolicyVerdict.BLOCKED]
        if blocked:
            details = "; ".join(
                f"{result.proposal_id}: {', '.join(result.reasons)}"
                for result in blocked
            )
            raise PolicyError(f"Change Plan contains blocked proposals: {details}")
        try:
            return create_plan(
                source_sha256=source_sha256,
                proposals=proposals,
                created_by="POLICY_ENGINE",
            )
        except ChangePlanError as exc:
            raise PolicyError(str(exc)) from exc

    @staticmethod
    def _result(
        proposal: ChangeProposal,
        verdict: PolicyVerdict,
        reasons: list[str],
    ) -> PolicyResult:
        return PolicyResult(
            proposal_id=proposal.proposal_id,
            rule_id=proposal.rule_id,
            verdict=verdict,
            reasons=tuple(reasons),
            checked_mutation_ids=tuple(item.mutation_id for item in proposal.mutations),
            apply_authorized=False,
        )
