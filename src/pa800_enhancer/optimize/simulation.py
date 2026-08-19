from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path

from ..analysis.controllers import analyze_controllers
from ..analysis.initialization import analyze_initialization_bar
from ..analysis.parameters import analyze_parameters
from ..analysis.summary import summarize
from ..analysis.sysex import analyze_sysex
from ..domain.song import Song
from ..validation.validator import SongValidator
from .engine import song_revision
from .history import CommandHistory
from .policy import AutoPolicy, AutoPolicyLoader, PolicyAction, evaluate_policy
from .proposals import ProposalRegistry, ProposalStatus


@dataclass(frozen=True, slots=True)
class SimulationMetrics:
    event_count: int
    note_count: int
    controller_events: int
    program_events: int
    sysex_events: int
    maximum_polyphony: int
    end_tick: int
    duration_seconds: float
    validation_findings: int
    export_blockers: int


@dataclass(frozen=True, slots=True)
class SimulationDelta:
    event_count: int
    note_count: int
    controller_events: int
    program_events: int
    sysex_events: int
    maximum_polyphony: int
    end_tick: int
    duration_seconds: float
    validation_findings: int
    export_blockers: int


@dataclass(frozen=True, slots=True)
class AnalyzerSnapshot:
    revision: str
    metrics: SimulationMetrics
    analyzer_hashes: tuple[tuple[str, str], ...]
    blocker_fingerprints: tuple[str, ...]
    digest: str


@dataclass(frozen=True, slots=True)
class SimulationStep:
    proposal_id: str
    transaction_digest: str
    before_revision: str
    after_revision: str
    changed_events: int


@dataclass(frozen=True, slots=True)
class SimulationReport:
    status: str
    plan_digest: str
    policy_digest: str
    original_revision: str
    projected_revision: str
    selected_proposal_ids: tuple[str, ...]
    deferred_proposal_ids: tuple[str, ...]
    steps: tuple[SimulationStep, ...]
    before: AnalyzerSnapshot
    after: AnalyzerSnapshot
    delta: SimulationDelta
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    digest: str


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    report: SimulationReport
    projected_song: Song


class ProposalSimulator:
    """Project a policy-selected proposal set without mutating the source song."""

    def __init__(self, validator: SongValidator | None = None) -> None:
        self.validator = validator or SongValidator()

    def simulate(
        self,
        song: Song,
        registry: ProposalRegistry,
        policy: AutoPolicy,
        *,
        approved_proposal_ids: tuple[str, ...] = (),
    ) -> SimulationOutcome:
        plan = registry.build_plan()
        original_revision = song_revision(song)
        before = self._snapshot(song)
        policy_digest = AutoPolicyLoader().digest(policy)
        blockers: list[str] = []
        warnings: list[str] = []
        if original_revision != plan.base_revision:
            blockers.append("song revision does not match the proposal plan")

        approvals = tuple(dict.fromkeys(approved_proposal_ids))
        if len(approvals) != len(approved_proposal_ids):
            blockers.append("approved proposal identifiers must be unique")
        known = set(plan.ordered_proposal_ids)
        unknown = sorted(set(approvals) - known)
        if unknown:
            blockers.append("unknown approved proposals: " + ", ".join(unknown))

        decisions = {item.proposal_id: item for item in evaluate_policy(plan, policy)}
        selected: list[str] = []
        deferred: list[str] = []
        approved = set(approvals)
        for proposal_id in plan.ordered_proposal_ids:
            entry = next(item for item in plan.entries if item.proposal_id == proposal_id)
            decision = decisions[proposal_id]
            if decision.action is PolicyAction.AUTO_APPLY:
                selected.append(proposal_id)
            elif decision.action is PolicyAction.REVIEW and proposal_id in approved:
                selected.append(proposal_id)
            else:
                deferred.append(proposal_id)
                if proposal_id in approved:
                    blockers.append(
                        f"proposal {proposal_id} cannot be approved while {decision.action.value}"
                    )
            if entry.status is not ProposalStatus.PROPOSED and proposal_id in approved:
                blockers.append(f"proposal {proposal_id} is not actionable")

        selected_set = set(selected)
        entries = {item.proposal_id: item for item in plan.entries}
        for proposal_id in selected:
            missing = sorted(set(entries[proposal_id].dependencies) - selected_set)
            if missing:
                blockers.append(
                    f"proposal {proposal_id} requires selected dependencies: "
                    + ", ".join(missing)
                )

        if blockers:
            return self._outcome(
                "blocked",
                plan.digest,
                policy_digest,
                original_revision,
                original_revision,
                tuple(selected),
                tuple(deferred),
                (),
                before,
                before,
                blockers,
                warnings,
                song,
            )

        proposal_map = {item.proposal_id: item for item in registry.proposals}
        history = CommandHistory(song)
        history.checkpoint("simulation-start")
        steps: list[SimulationStep] = []
        projected = history.song
        try:
            for proposal_id in selected:
                proposal = proposal_map[proposal_id]
                transaction = replace(
                    proposal.transaction,
                    base_revision=song_revision(projected),
                )
                before_revision = song_revision(projected)
                projected = history.apply(transaction)
                steps.append(
                    SimulationStep(
                        proposal_id,
                        entries[proposal_id].transaction_digest,
                        before_revision,
                        song_revision(projected),
                        len(transaction.changes),
                    )
                )
            after = self._snapshot(projected)
            new_blockers = sorted(
                set(after.blocker_fingerprints) - set(before.blocker_fingerprints)
            )
            if new_blockers:
                blockers.append(
                    "simulation introduced export blockers: " + ", ".join(new_blockers)
                )
                history.restore_checkpoint("simulation-start")
                return self._outcome(
                    "rolled_back",
                    plan.digest,
                    policy_digest,
                    original_revision,
                    original_revision,
                    tuple(selected),
                    tuple(deferred),
                    tuple(steps),
                    before,
                    after,
                    blockers,
                    warnings,
                    history.song,
                )
        except (ValueError, IndexError, KeyError) as error:
            history.restore_checkpoint("simulation-start")
            blockers.append(f"simulation transaction failed: {error}")
            return self._outcome(
                "rolled_back",
                plan.digest,
                policy_digest,
                original_revision,
                original_revision,
                tuple(selected),
                tuple(deferred),
                tuple(steps),
                before,
                before,
                blockers,
                warnings,
                history.song,
            )

        status = "simulated" if selected else "no_changes"
        if not selected:
            warnings.append("policy selected no proposals for simulation")
        return self._outcome(
            status,
            plan.digest,
            policy_digest,
            original_revision,
            song_revision(projected),
            tuple(selected),
            tuple(deferred),
            tuple(steps),
            before,
            after,
            blockers,
            warnings,
            projected,
        )

    def _snapshot(self, song: Song) -> AnalyzerSnapshot:
        summary = summarize(song)
        validation = self.validator.validate(song)
        analyses = {
            "summary": summary,
            "validation": validation,
            "controllers": analyze_controllers(song),
            "parameters": analyze_parameters(song),
            "sysex": analyze_sysex(song),
            "initialization": analyze_initialization_bar(song),
        }
        hashes = tuple(
            (name, _canonical_digest(value))
            for name, value in sorted(analyses.items())
        )
        blockers = tuple(
            sorted(
                _validation_fingerprint(item)
                for item in validation
                if item.blocks_export
            )
        )
        metrics = SimulationMetrics(
            event_count=summary.event_count,
            note_count=summary.note_count,
            controller_events=summary.controller_events,
            program_events=sum(
                event.kind.value == "channel" and event.message_type == 0xC0
                for track in song.tracks
                for event in track.events
            ),
            sysex_events=summary.sysex_events,
            maximum_polyphony=summary.maximum_polyphony,
            end_tick=summary.end_tick,
            duration_seconds=summary.duration_seconds,
            validation_findings=len(validation),
            export_blockers=len(blockers),
        )
        revision = song_revision(song)
        digest = _canonical_digest(
            {
                "revision": revision,
                "metrics": asdict(metrics),
                "analyzer_hashes": hashes,
                "blockers": blockers,
            }
        )
        return AnalyzerSnapshot(revision, metrics, hashes, blockers, digest)

    @staticmethod
    def _outcome(
        status: str,
        plan_digest: str,
        policy_digest: str,
        original_revision: str,
        projected_revision: str,
        selected: tuple[str, ...],
        deferred: tuple[str, ...],
        steps: tuple[SimulationStep, ...],
        before: AnalyzerSnapshot,
        after: AnalyzerSnapshot,
        blockers: list[str],
        warnings: list[str],
        projected_song: Song,
    ) -> SimulationOutcome:
        delta = _delta(before.metrics, after.metrics)
        payload = {
            "status": status,
            "plan_digest": plan_digest,
            "policy_digest": policy_digest,
            "original_revision": original_revision,
            "projected_revision": projected_revision,
            "selected_proposal_ids": selected,
            "deferred_proposal_ids": deferred,
            "steps": [asdict(item) for item in steps],
            "before": asdict(before),
            "after": asdict(after),
            "delta": asdict(delta),
            "blockers": tuple(dict.fromkeys(blockers)),
            "warnings": tuple(dict.fromkeys(warnings)),
        }
        digest = _canonical_digest(payload)
        report = SimulationReport(
            status,
            plan_digest,
            policy_digest,
            original_revision,
            projected_revision,
            selected,
            deferred,
            steps,
            before,
            after,
            delta,
            payload["blockers"],
            payload["warnings"],
            digest,
        )
        return SimulationOutcome(report, projected_song)


def _delta(before: SimulationMetrics, after: SimulationMetrics) -> SimulationDelta:
    return SimulationDelta(
        event_count=after.event_count - before.event_count,
        note_count=after.note_count - before.note_count,
        controller_events=after.controller_events - before.controller_events,
        program_events=after.program_events - before.program_events,
        sysex_events=after.sysex_events - before.sysex_events,
        maximum_polyphony=after.maximum_polyphony - before.maximum_polyphony,
        end_tick=after.end_tick - before.end_tick,
        duration_seconds=after.duration_seconds - before.duration_seconds,
        validation_findings=after.validation_findings - before.validation_findings,
        export_blockers=after.export_blockers - before.export_blockers,
    )


def _validation_fingerprint(issue) -> str:
    return (
        f"{issue.severity.value}:{issue.code}:"
        f"{issue.track_index}:{issue.tick}:{issue.message}"
    )


def _canonical_digest(value) -> str:
    canonical = json.dumps(
        value,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_default(value):
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")
