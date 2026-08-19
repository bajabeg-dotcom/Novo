from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path

from ..domain.song import Song
from .engine import song_revision
from .history import CommandHistory
from .policy import AutoPolicy, AutoPolicyLoader, PolicyDecision, evaluate_policy
from .proposals import ProposalPlan, ProposalRegistry
from .simulation import ProposalSimulator, SimulationOutcome


AUTO_REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class PreparedAutoRun:
    plan: ProposalPlan
    decisions: tuple[PolicyDecision, ...]
    simulation: SimulationOutcome
    approved_proposal_ids: tuple[str, ...]


class AutoWorkflow:
    def __init__(self, simulator: ProposalSimulator | None = None) -> None:
        self.simulator = simulator or ProposalSimulator()

    def prepare(
        self,
        song: Song,
        registry: ProposalRegistry,
        policy: AutoPolicy,
        *,
        approved_proposal_ids: tuple[str, ...] = (),
    ) -> PreparedAutoRun:
        plan = registry.build_plan()
        decisions = evaluate_policy(plan, policy)
        simulation = self.simulator.simulate(
            song,
            registry,
            policy,
            approved_proposal_ids=approved_proposal_ids,
        )
        return PreparedAutoRun(
            plan,
            decisions,
            simulation,
            tuple(dict.fromkeys(approved_proposal_ids)),
        )

    def commit(
        self,
        song: Song,
        registry: ProposalRegistry,
        prepared: PreparedAutoRun,
    ) -> CommandHistory:
        report = prepared.simulation.report
        if report.status != "simulated" or report.blockers:
            raise ValueError("only a successful simulation can be committed")
        if song_revision(song) != report.original_revision:
            raise ValueError("auto plan is stale: source song revision changed")
        refreshed = registry.build_plan()
        if refreshed.digest != prepared.plan.digest or refreshed.digest != report.plan_digest:
            raise ValueError("auto plan is stale: proposal plan changed")
        proposals = {item.proposal_id: item for item in registry.proposals}
        history = CommandHistory(song)
        history.checkpoint("auto-before-commit")
        try:
            for proposal_id in report.selected_proposal_ids:
                transaction = replace(
                    proposals[proposal_id].transaction,
                    base_revision=song_revision(history.song),
                )
                history.apply(transaction)
        except (ValueError, KeyError) as error:
            history.restore_checkpoint("auto-before-commit")
            raise ValueError(f"auto commit failed and was rolled back: {error}") from error
        if song_revision(history.song) != report.after.revision:
            history.restore_checkpoint("auto-before-commit")
            raise ValueError("auto commit differs from the approved simulation")
        return history


def build_auto_report(
    prepared: PreparedAutoRun,
    policy: AutoPolicy,
    *,
    input_name: str,
    input_sha256: str | None,
    profile_id: str | None = None,
    profile_sha256: str | None = None,
    output_name: str | None = None,
    output_sha256: str | None = None,
    project_name: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": AUTO_REPORT_SCHEMA_VERSION,
        "status": prepared.simulation.report.status,
        "input": {
            "name": input_name,
            "sha256": input_sha256,
            "revision": prepared.simulation.report.original_revision,
        },
        "policy": {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "sha256": AutoPolicyLoader().digest(policy),
            "mode": policy.mode.value,
            "package": policy.package.value,
            "seed": policy.seed,
        },
        "profile": (
            {"profile_id": profile_id, "sha256": profile_sha256}
            if profile_id is not None
            else None
        ),
        "approved_proposal_ids": prepared.approved_proposal_ids,
        "plan": asdict(prepared.plan),
        "decisions": [asdict(item) for item in prepared.decisions],
        "simulation": asdict(prepared.simulation.report),
        "output": (
            {"name": output_name, "sha256": output_sha256}
            if output_name is not None
            else None
        ),
        "project": {"name": project_name} if project_name is not None else None,
    }
    canonical = _canonical_json(payload)
    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def write_auto_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                report,
                default=_json_default,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_default(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")