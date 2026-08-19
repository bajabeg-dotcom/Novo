from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from ..domain.changes import (
    ChangeTransaction,
    DeleteEvent,
    InsertEvent,
    RiskLevel,
    transaction_to_dict,
)


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    BLOCKED = "blocked"
    CONFLICTED = "conflicted"


@dataclass(frozen=True, slots=True)
class Proposal:
    proposal_id: str
    transaction: ChangeTransaction
    finding_ids: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    confidence: float = 1.0
    expected_benefit: float = 0.0
    preapproved: bool = False
    declared_risk: RiskLevel | None = None
    evidence_refs: tuple[str, ...] = ()
    track_indices: tuple[int, ...] = ()
    channels: tuple[int, ...] = ()
    drum_notes: tuple[int, ...] = ()
    message_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise ValueError("proposal_id must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("proposal confidence must be in range 0..1")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("proposal dependencies must be unique")
        for label, values in (
            ("finding_ids", self.finding_ids),
            ("evidence_refs", self.evidence_refs),
            ("track_indices", self.track_indices),
            ("channels", self.channels),
            ("drum_notes", self.drum_notes),
            ("message_kinds", self.message_kinds),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"proposal {label} must be unique")
        if any(value < 0 for value in self.track_indices):
            raise ValueError("proposal track indices must be non-negative")
        if any(not 1 <= value <= 16 for value in self.channels):
            raise ValueError("proposal channels must be in range 1..16")
        if any(not 0 <= value <= 127 for value in self.drum_notes):
            raise ValueError("proposal drum notes must be in range 0..127")

    @property
    def risk(self) -> RiskLevel:
        if self.declared_risk is not None:
            return self.declared_risk
        return max(
            (group.risk for group in self.transaction.groups),
            default=RiskLevel.INFORMATION,
        )

    @property
    def targets(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted({(change.event_id, change.field) for change in self.transaction.changes})
        )


@dataclass(frozen=True, slots=True)
class ProposalConflict:
    code: str
    message: str
    proposal_ids: tuple[str, ...]
    event_id: str | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class ProposalPlanEntry:
    proposal_id: str
    transaction_id: str
    transaction_digest: str
    module: str
    status: ProposalStatus
    risk: RiskLevel
    confidence: float
    expected_benefit: float
    preapproved: bool
    finding_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    dependencies: tuple[str, ...]
    targets: tuple[tuple[str, str], ...]
    track_indices: tuple[int, ...]
    channels: tuple[int, ...]
    drum_notes: tuple[int, ...]
    message_kinds: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProposalPlan:
    base_revision: str
    ordered_proposal_ids: tuple[str, ...]
    entries: tuple[ProposalPlanEntry, ...]
    conflicts: tuple[ProposalConflict, ...]
    digest: str

    @property
    def ready_proposal_ids(self) -> tuple[str, ...]:
        return tuple(
            entry.proposal_id
            for entry in self.entries
            if entry.status is ProposalStatus.PROPOSED
        )


class ProposalRegistry:
    """Collect and deterministically preflight independent module proposals."""

    def __init__(self, base_revision: str) -> None:
        if not base_revision:
            raise ValueError("base_revision must not be empty")
        self.base_revision = base_revision
        self._proposals: dict[str, Proposal] = {}

    @property
    def proposals(self) -> tuple[Proposal, ...]:
        return tuple(self._proposals[key] for key in sorted(self._proposals))

    def register(self, proposal: Proposal) -> None:
        if proposal.proposal_id in self._proposals:
            raise ValueError(f"duplicate proposal_id: {proposal.proposal_id}")
        self._proposals[proposal.proposal_id] = proposal

    def build_plan(self) -> ProposalPlan:
        blockers = {
            proposal.proposal_id: list(proposal.blockers)
            for proposal in self.proposals
        }
        warnings = {
            proposal.proposal_id: list(proposal.warnings)
            for proposal in self.proposals
        }
        known = set(self._proposals)
        for proposal in self.proposals:
            transaction = proposal.transaction
            if (
                transaction.base_revision is not None
                and transaction.base_revision != self.base_revision
            ):
                blockers[proposal.proposal_id].append(
                    "transaction base revision does not match the registry"
                )
            unknown = sorted(set(proposal.dependencies) - known)
            if unknown:
                blockers[proposal.proposal_id].append(
                    f"unknown proposal dependencies: {', '.join(unknown)}"
                )
            duplicate_targets = _duplicate_targets(transaction)
            if duplicate_targets:
                labels = ", ".join(
                    f"{event_id}.{field}" for event_id, field in duplicate_targets
                )
                blockers[proposal.proposal_id].append(
                    f"transaction contains duplicate targets: {labels}"
                )

        cycle_members = _cycle_members(self._proposals)
        if cycle_members:
            label = ", ".join(sorted(cycle_members))
            for proposal_id in cycle_members:
                blockers[proposal_id].append(f"proposal dependency cycle: {label}")

        conflicts = _target_conflicts(self.proposals, blockers)
        conflicted = {
            proposal_id
            for conflict in conflicts
            for proposal_id in conflict.proposal_ids
        }

        changed = True
        while changed:
            changed = False
            unavailable = {
                proposal_id
                for proposal_id in known
                if blockers[proposal_id] or proposal_id in conflicted
            }
            for proposal in self.proposals:
                if blockers[proposal.proposal_id]:
                    continue
                failed_dependencies = sorted(
                    set(proposal.dependencies) & unavailable
                )
                if failed_dependencies:
                    blockers[proposal.proposal_id].append(
                        "blocked proposal dependencies: "
                        + ", ".join(failed_dependencies)
                    )
                    changed = True

        ordered = _topological_order(self._proposals)
        entries = []
        for proposal_id in ordered:
            proposal = self._proposals[proposal_id]
            status = (
                ProposalStatus.BLOCKED
                if blockers[proposal_id]
                else ProposalStatus.CONFLICTED
                if proposal_id in conflicted
                else ProposalStatus.PROPOSED
            )
            entries.append(
                ProposalPlanEntry(
                    proposal_id=proposal_id,
                    transaction_id=proposal.transaction.transaction_id,
                    transaction_digest=_transaction_digest(proposal.transaction),
                    module=proposal.transaction.module,
                    status=status,
                    risk=proposal.risk,
                    confidence=proposal.confidence,
                    expected_benefit=proposal.expected_benefit,
                    preapproved=proposal.preapproved,
                    finding_ids=tuple(sorted(proposal.finding_ids)),
                    evidence_refs=tuple(sorted(proposal.evidence_refs)),
                    dependencies=tuple(sorted(proposal.dependencies)),
                    targets=proposal.targets,
                    track_indices=tuple(sorted(proposal.track_indices)),
                    channels=tuple(sorted(proposal.channels)),
                    drum_notes=tuple(sorted(proposal.drum_notes)),
                    message_kinds=tuple(sorted(proposal.message_kinds)),
                    blockers=tuple(dict.fromkeys(blockers[proposal_id])),
                    warnings=tuple(dict.fromkeys(warnings[proposal_id])),
                )
            )
        digest = _plan_digest(self.base_revision, ordered, entries, conflicts, self._proposals)
        return ProposalPlan(
            base_revision=self.base_revision,
            ordered_proposal_ids=ordered,
            entries=tuple(entries),
            conflicts=conflicts,
            digest=digest,
        )


def _duplicate_targets(transaction: ChangeTransaction) -> tuple[tuple[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for change in transaction.changes:
        target = (change.event_id, change.field)
        if target in seen:
            duplicates.add(target)
        seen.add(target)
    return tuple(sorted(duplicates))


def _target_conflicts(
    proposals: tuple[Proposal, ...], blockers: dict[str, list[str]]
) -> tuple[ProposalConflict, ...]:
    eligible = [item for item in proposals if not blockers[item.proposal_id]]
    conflicts: list[ProposalConflict] = []
    for index, first in enumerate(eligible):
        first_actions = _event_actions(first.transaction)
        first_targets = set(first.targets)
        for second in eligible[index + 1 :]:
            second_actions = _event_actions(second.transaction)
            shared_targets = sorted(first_targets & set(second.targets))
            for event_id, field in shared_targets:
                conflicts.append(
                    ProposalConflict(
                        code="duplicate_target",
                        message=(
                            f"proposals {first.proposal_id} and {second.proposal_id} "
                            f"both target {event_id}.{field}"
                        ),
                        proposal_ids=(first.proposal_id, second.proposal_id),
                        event_id=event_id,
                        field=field,
                    )
                )
            shared_events = sorted(set(first_actions) & set(second_actions))
            for event_id in shared_events:
                if any(
                    action in {"insert", "delete"}
                    for action in (first_actions[event_id], second_actions[event_id])
                ) and not any(item.event_id == event_id for item in conflicts):
                    conflicts.append(
                        ProposalConflict(
                            code="structural_target_conflict",
                            message=(
                                f"proposals {first.proposal_id} and {second.proposal_id} "
                                f"use incompatible operations on {event_id}"
                            ),
                            proposal_ids=(first.proposal_id, second.proposal_id),
                            event_id=event_id,
                        )
                    )
    return tuple(
        sorted(
            conflicts,
            key=lambda item: (
                item.proposal_ids,
                item.event_id or "",
                item.field or "",
                item.code,
            ),
        )
    )


def _event_actions(transaction: ChangeTransaction) -> dict[str, str]:
    result = {}
    for change in transaction.changes:
        action = (
            "insert"
            if isinstance(change, InsertEvent)
            else "delete"
            if isinstance(change, DeleteEvent)
            else "update"
        )
        previous = result.get(change.event_id)
        result[change.event_id] = action if previous in (None, action) else "mixed"
    return result


def _cycle_members(proposals: dict[str, Proposal]) -> set[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    cycles: set[str] = set()

    def visit(proposal_id: str) -> None:
        if proposal_id in visited:
            return
        if proposal_id in visiting:
            start = stack.index(proposal_id)
            cycles.update(stack[start:])
            return
        visiting.add(proposal_id)
        stack.append(proposal_id)
        for dependency in sorted(proposals[proposal_id].dependencies):
            if dependency in proposals:
                visit(dependency)
        stack.pop()
        visiting.remove(proposal_id)
        visited.add(proposal_id)

    for proposal_id in sorted(proposals):
        visit(proposal_id)
    return cycles


def _topological_order(proposals: dict[str, Proposal]) -> tuple[str, ...]:
    indegree = {proposal_id: 0 for proposal_id in proposals}
    dependents = {proposal_id: set() for proposal_id in proposals}
    for proposal_id, proposal in proposals.items():
        for dependency in proposal.dependencies:
            if dependency not in proposals:
                continue
            indegree[proposal_id] += 1
            dependents[dependency].add(proposal_id)
    ready = sorted(key for key, value in indegree.items() if value == 0)
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for dependent in sorted(dependents[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort()
    ordered.extend(sorted(set(proposals) - set(ordered)))
    return tuple(ordered)


def _plan_digest(
    base_revision: str,
    ordered: tuple[str, ...],
    entries: list[ProposalPlanEntry],
    conflicts: tuple[ProposalConflict, ...],
    proposals: dict[str, Proposal],
) -> str:
    payload = {
        "base_revision": base_revision,
        "ordered_proposal_ids": ordered,
        "entries": [
            {
                "proposal_id": entry.proposal_id,
                "transaction_digest": entry.transaction_digest,
                "status": entry.status.value,
                "risk": int(entry.risk),
                "confidence": entry.confidence,
                "expected_benefit": entry.expected_benefit,
                "preapproved": entry.preapproved,
                "finding_ids": entry.finding_ids,
                "evidence_refs": entry.evidence_refs,
                "dependencies": entry.dependencies,
                "targets": entry.targets,
                "track_indices": entry.track_indices,
                "channels": entry.channels,
                "drum_notes": entry.drum_notes,
                "message_kinds": entry.message_kinds,
                "blockers": entry.blockers,
                "warnings": entry.warnings,
                "transaction": transaction_to_dict(
                    proposals[entry.proposal_id].transaction
                ),
            }
            for entry in entries
        ],
        "conflicts": [
            {
                "code": conflict.code,
                "message": conflict.message,
                "proposal_ids": conflict.proposal_ids,
                "event_id": conflict.event_id,
                "field": conflict.field,
            }
            for conflict in conflicts
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _transaction_digest(transaction: ChangeTransaction) -> str:
    canonical = json.dumps(
        transaction_to_dict(transaction), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()