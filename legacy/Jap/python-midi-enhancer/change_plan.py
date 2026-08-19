"""Immutable Suggest/Change Plan data model with no MIDI writer.

This module describes exact, auditable proposed event-field differences and
explicit user decisions. It cannot apply a mutation and always reports
``apply_authorized = False``; a future Change Engine and independent Verifier
must consume a confirmed plan through a separate interface.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any

from style_loader import MidiEvent

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Z][A-Z0-9_.-]+$")
MetricValue = str | int | float | bool | None
EventRef = tuple[int, int]


class ChangePlanError(ValueError):
    """Raised when an immutable plan invariant is violated."""


class EvidenceStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKING = "BLOCKING"


class MutationField(str, Enum):
    DATA_0 = "data[0]"
    DATA_1 = "data[1]"

    @property
    def index(self) -> int:
        return 0 if self is MutationField.DATA_0 else 1


class UserDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class PlanState(str, Enum):
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    PARTIALLY_DECIDED = "PARTIALLY_DECIDED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class InputMeasurement:
    name: str
    value: MetricValue
    unit: str | None
    status: EvidenceStatus


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    source_id: str
    status: EvidenceStatus
    detail: str
    path: str | None = None
    printed_pages: tuple[int, ...] = ()
    pdf_pages: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class EventMutation:
    mutation_id: str
    event_ref: EventRef
    absolute_tick: int
    event_kind: str
    channel: int | None
    field: MutationField
    old_value: int
    new_value: int
    expected_raw_sha256: str

    @classmethod
    def from_event(
        cls, event: MidiEvent, field: MutationField, new_value: int
    ) -> "EventMutation":
        if not 0 <= new_value <= 127:
            raise ChangePlanError(f"new MIDI value must be in 0..127: {new_value}")
        index = field.index
        if len(event.data) <= index:
            raise ChangePlanError(
                f"event {event.track_index}:{event.event_index} has no {field.value}"
            )
        old_value = int(event.data[index])
        if old_value == new_value:
            raise ChangePlanError("no-op event mutation is not allowed")
        raw_hash = hashlib.sha256(event.raw).hexdigest()
        payload = {
            "event_ref": [event.track_index, event.event_index],
            "absolute_tick": event.absolute_tick,
            "event_kind": event.kind,
            "channel": event.channel,
            "field": field.value,
            "old_value": old_value,
            "new_value": new_value,
            "expected_raw_sha256": raw_hash,
        }
        return cls(
            mutation_id="MUT-" + _stable_digest(payload)[:20].upper(),
            event_ref=(event.track_index, event.event_index),
            absolute_tick=event.absolute_tick,
            event_kind=event.kind,
            channel=event.channel,
            field=field,
            old_value=old_value,
            new_value=new_value,
            expected_raw_sha256=raw_hash,
        )

    def verify_event(self, event: MidiEvent) -> tuple[str, ...]:
        errors: list[str] = []
        if (event.track_index, event.event_index) != self.event_ref:
            errors.append("event reference mismatch")
        if event.absolute_tick != self.absolute_tick:
            errors.append("absolute tick mismatch")
        if event.kind != self.event_kind:
            errors.append("event kind mismatch")
        if event.channel != self.channel:
            errors.append("event channel mismatch")
        if len(event.data) <= self.field.index:
            errors.append(f"event has no {self.field.value}")
        elif event.data[self.field.index] != self.old_value:
            errors.append("old value mismatch")
        if hashlib.sha256(event.raw).hexdigest() != self.expected_raw_sha256:
            errors.append("raw event SHA-256 mismatch")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class ChangeProposal:
    proposal_id: str
    rule_id: str
    rule_version: str
    title: str
    description: str
    evidence_status: EvidenceStatus
    confidence_percent: float | None
    risk: RiskLevel
    input_measurements: tuple[InputMeasurement, ...]
    evidence: tuple[EvidenceReference, ...]
    mutations: tuple[EventMutation, ...]
    expected_difference: str
    protections: tuple[str, ...]
    requires_user_confirmation: bool = True


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    decision_id: str
    proposal_id: str
    decision: UserDecision
    decided_at: str
    actor: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ChangePlan:
    schema_version: str
    plan_id: str
    source_sha256: str
    phase: str
    proposals: tuple[ChangeProposal, ...]
    decisions: tuple[DecisionRecord, ...]
    created_by: str
    apply_authorized: bool = False

    @property
    def state(self) -> PlanState:
        latest = self.latest_decisions
        if not latest:
            return PlanState.AWAITING_CONFIRMATION
        if any(item.decision is UserDecision.REJECT for item in latest.values()):
            return PlanState.REJECTED
        if len(latest) < len(self.proposals):
            return PlanState.PARTIALLY_DECIDED
        return PlanState.APPROVED

    @property
    def latest_decisions(self) -> dict[str, DecisionRecord]:
        latest: dict[str, DecisionRecord] = {}
        for item in self.decisions:
            latest[item.proposal_id] = item
        return latest

    @property
    def approved_proposal_ids(self) -> tuple[str, ...]:
        return tuple(sorted(
            proposal_id for proposal_id, decision in self.latest_decisions.items()
            if decision.decision is UserDecision.APPROVE
        ))

    @property
    def expected_mutation_count(self) -> int:
        return sum(len(proposal.mutations) for proposal in self.proposals)

    def record_decision(
        self,
        proposal_id: str,
        decision: UserDecision,
        *,
        decided_at: str,
        actor: str = "USER",
        note: str | None = None,
    ) -> "ChangePlan":
        if proposal_id not in {item.proposal_id for item in self.proposals}:
            raise ChangePlanError(f"decision references unknown proposal: {proposal_id}")
        if actor != "USER":
            raise ChangePlanError("only an explicit USER decision is accepted")
        _validate_timestamp(decided_at)
        payload = {
            "proposal_id": proposal_id,
            "decision": decision.value,
            "decided_at": decided_at,
            "actor": actor,
            "note": note,
        }
        record = DecisionRecord(
            decision_id="DECISION-" + _stable_digest(payload)[:20].upper(),
            proposal_id=proposal_id,
            decision=decision,
            decided_at=decided_at,
            actor=actor,
            note=note,
        )
        updated = replace(self, decisions=self.decisions + (record,))
        validate_plan(updated)
        return updated


def create_proposal(
    *,
    source_sha256: str,
    rule_id: str,
    rule_version: str,
    title: str,
    description: str,
    evidence_status: EvidenceStatus,
    confidence_percent: float | None,
    risk: RiskLevel,
    input_measurements: tuple[InputMeasurement, ...],
    evidence: tuple[EvidenceReference, ...],
    mutations: tuple[EventMutation, ...],
    expected_difference: str,
    protections: tuple[str, ...],
) -> ChangeProposal:
    _validate_sha256(source_sha256)
    if not ID_RE.fullmatch(rule_id):
        raise ChangePlanError(f"invalid rule ID: {rule_id!r}")
    if not rule_version or not title.strip() or not description.strip():
        raise ChangePlanError("rule version, title and description are required")
    if not mutations:
        raise ChangePlanError("proposal must contain at least one exact mutation")
    _validate_confidence(evidence_status, confidence_percent)
    if not input_measurements:
        raise ChangePlanError("proposal must contain input measurements")
    if not evidence:
        raise ChangePlanError("proposal must contain evidence references")
    _validate_mutations(mutations)
    payload = {
        "source_sha256": source_sha256,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "mutations": [_mutation_dict(item) for item in mutations],
    }
    return ChangeProposal(
        proposal_id="PROPOSAL-" + _stable_digest(payload)[:20].upper(),
        rule_id=rule_id,
        rule_version=rule_version,
        title=title.strip(),
        description=description.strip(),
        evidence_status=evidence_status,
        confidence_percent=confidence_percent,
        risk=risk,
        input_measurements=input_measurements,
        evidence=evidence,
        mutations=mutations,
        expected_difference=expected_difference.strip(),
        protections=protections,
    )


def create_plan(
    *, source_sha256: str, proposals: tuple[ChangeProposal, ...], created_by: str
) -> ChangePlan:
    _validate_sha256(source_sha256)
    if not proposals:
        raise ChangePlanError("Change Plan must contain at least one proposal")
    if created_by != "POLICY_ENGINE":
        raise ChangePlanError("Change Plan must be created by POLICY_ENGINE")
    payload = {
        "schema_version": "1.0.0",
        "source_sha256": source_sha256,
        "proposal_ids": [item.proposal_id for item in proposals],
    }
    plan = ChangePlan(
        schema_version="1.0.0",
        plan_id="PLAN-" + _stable_digest(payload)[:20].upper(),
        source_sha256=source_sha256,
        phase="SUGGEST",
        proposals=proposals,
        decisions=(),
        created_by=created_by,
        apply_authorized=False,
    )
    validate_plan(plan)
    return plan


def validate_plan(plan: ChangePlan) -> None:
    if plan.schema_version != "1.0.0" or plan.phase != "SUGGEST":
        raise ChangePlanError("unsupported schema or phase")
    _validate_sha256(plan.source_sha256)
    if plan.created_by != "POLICY_ENGINE":
        raise ChangePlanError("invalid plan creator")
    if plan.apply_authorized:
        raise ChangePlanError("Change Plan foundation cannot authorize Apply")
    proposal_ids = [item.proposal_id for item in plan.proposals]
    if len(proposal_ids) != len(set(proposal_ids)):
        raise ChangePlanError("duplicate proposal ID")
    mutation_targets: set[tuple[EventRef, MutationField]] = set()
    for proposal in plan.proposals:
        _validate_confidence(proposal.evidence_status, proposal.confidence_percent)
        _validate_mutations(proposal.mutations)
        for mutation in proposal.mutations:
            target = (mutation.event_ref, mutation.field)
            if target in mutation_targets:
                raise ChangePlanError(f"event field appears in multiple proposals: {target}")
            mutation_targets.add(target)
    known = set(proposal_ids)
    for decision in plan.decisions:
        if decision.proposal_id not in known:
            raise ChangePlanError(f"unknown decision proposal: {decision.proposal_id}")
        if decision.actor != "USER":
            raise ChangePlanError("decision actor must be USER")
        _validate_timestamp(decision.decided_at)


def plan_to_dict(plan: ChangePlan) -> dict[str, Any]:
    data = asdict(plan)
    data["state"] = plan.state.value
    data["approved_proposal_ids"] = list(plan.approved_proposal_ids)
    data["expected_mutation_count"] = plan.expected_mutation_count
    data["apply_authorized"] = False
    return _enum_values(data)


def render_plan(plan: ChangePlan) -> str:
    validate_plan(plan)
    return json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=2) + "\n"


def _validate_sha256(value: str) -> None:
    if not SHA256_RE.fullmatch(value):
        raise ChangePlanError(f"invalid source SHA-256: {value!r}")


def _validate_confidence(status: EvidenceStatus, confidence: float | None) -> None:
    if status is EvidenceStatus.INFERRED:
        if confidence is None or not 0 <= confidence <= 100:
            raise ChangePlanError("INFERRED proposal requires confidence in 0..100")
    elif confidence is not None:
        raise ChangePlanError(f"{status.value} proposal must not use a probability percentage")


def _validate_mutations(mutations: tuple[EventMutation, ...]) -> None:
    ids = [item.mutation_id for item in mutations]
    if len(ids) != len(set(ids)):
        raise ChangePlanError("duplicate mutation ID")
    targets = [(item.event_ref, item.field) for item in mutations]
    if len(targets) != len(set(targets)):
        raise ChangePlanError("duplicate event-field mutation")
    for item in mutations:
        if not SHA256_RE.fullmatch(item.expected_raw_sha256):
            raise ChangePlanError("invalid event raw SHA-256")
        if not 0 <= item.old_value <= 127 or not 0 <= item.new_value <= 127:
            raise ChangePlanError("mutation values must be in 0..127")
        if item.old_value == item.new_value:
            raise ChangePlanError("no-op mutation")


def _validate_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChangePlanError(f"invalid ISO-8601 decision timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ChangePlanError("decision timestamp must include timezone")


def _mutation_dict(item: EventMutation) -> dict[str, Any]:
    return {
        "mutation_id": item.mutation_id,
        "event_ref": list(item.event_ref),
        "absolute_tick": item.absolute_tick,
        "event_kind": item.event_kind,
        "channel": item.channel,
        "field": item.field.value,
        "old_value": item.old_value,
        "new_value": item.new_value,
        "expected_raw_sha256": item.expected_raw_sha256,
    }


def _stable_digest(value: Any) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _enum_values(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _enum_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_enum_values(item) for item in value]
    return value
