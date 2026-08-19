from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..domain.changes import RiskLevel
from .proposals import ProposalPlan, ProposalStatus


AUTO_POLICY_SCHEMA_VERSION = 1


class AutomationMode(str, Enum):
    ANALYZE_ONLY = "analyze_only"
    SAFE_AUTO = "safe_auto"
    ASSISTED = "assisted"
    VERIFIED_BATCH = "verified_batch"


class AutomationPackage(str, Enum):
    AUDIT = "audit"
    CLEAN = "clean"
    PA800_READY = "pa800_ready"
    PERFORMANCE = "performance"
    FULL_ASSISTED = "full_assisted"


class PolicyAction(str, Enum):
    ANALYZE_ONLY = "analyze_only"
    AUTO_APPLY = "auto_apply"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class PolicyProfile:
    profile_id: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ErrorBudgets:
    maximum_timing_ticks: int = 0
    maximum_timing_ms: float = 0.0
    maximum_velocity_delta: int = 0
    maximum_error_db: float = 0.0
    maximum_controller_reduction_ratio: float = 0.0
    maximum_high_risk_groups: int = 0


@dataclass(frozen=True, slots=True)
class PolicyLocks:
    event_ids: tuple[str, ...] = ()
    track_indices: tuple[int, ...] = ()
    channels: tuple[int, ...] = ()
    drum_notes: tuple[int, ...] = ()
    message_kinds: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModulePolicy:
    enabled: bool = True
    minimum_confidence: float = 0.0
    allow_auto: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AutoPolicy:
    policy_id: str
    policy_version: str
    mode: AutomationMode
    package: AutomationPackage
    seed: int
    goals: tuple[str, ...]
    budgets: ErrorBudgets
    locks: PolicyLocks
    modules: dict[str, ModulePolicy]
    maximum_auto_risk: RiskLevel = RiskLevel.LOW
    profile: PolicyProfile | None = None
    approved_transactions: dict[str, str] = field(default_factory=dict)
    schema_version: int = AUTO_POLICY_SCHEMA_VERSION
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    proposal_id: str
    action: PolicyAction
    reasons: tuple[str, ...]


SUPPORTED_GOALS = {
    "compatibility",
    "controller-cleanup",
    "dynamic-headroom",
    "timing-cleanup",
    "polyphony-review",
    "size-reduction",
}

PACKAGE_MODULES = {
    AutomationPackage.AUDIT: (),
    AutomationPackage.CLEAN: ("controller_thinning", "cc7_cc11_conversion"),
    AutomationPackage.PA800_READY: (
        "initialization_update",
        "sound_mapping",
        "drum_mapping",
    ),
    AutomationPackage.PERFORMANCE: ("quantization", "velocity", "polyphony"),
    AutomationPackage.FULL_ASSISTED: (
        "controller_thinning",
        "cc7_cc11_conversion",
        "initialization_update",
        "sound_mapping",
        "drum_mapping",
        "quantization",
        "velocity",
        "polyphony",
    ),
}

AUTO_POLICY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://pa800-enhancer.invalid/schema/auto-policy-v1.json",
    "title": "Pa800 Enhancer auto policy",
    "type": "object",
    "required": [
        "schema_version",
        "policy_id",
        "policy_version",
        "mode",
        "package",
        "seed",
        "goals",
        "budgets",
        "locks",
        "modules",
        "maximum_auto_risk",
        "approved_transactions",
    ],
    "properties": {
        "schema_version": {"const": AUTO_POLICY_SCHEMA_VERSION},
        "policy_id": {"type": "string", "minLength": 1},
        "policy_version": {"type": "string", "minLength": 1},
        "mode": {"enum": [item.value for item in AutomationMode]},
        "package": {"enum": [item.value for item in AutomationPackage]},
        "seed": {"type": "integer"},
        "goals": {"type": "array", "uniqueItems": True},
        "budgets": {"type": "object"},
        "locks": {"type": "object"},
        "modules": {"type": "object"},
        "maximum_auto_risk": {"enum": ["information", "low"]},
        "profile": {"type": ["object", "null"]},
        "approved_transactions": {"type": "object"},
        "extensions": {"type": "object"},
    },
    "additionalProperties": False,
}


class AutoPolicyFormatError(ValueError):
    pass


class AutoPolicyLoader:
    TOP_LEVEL_KEYS = {
        "schema_version",
        "policy_id",
        "policy_version",
        "mode",
        "package",
        "seed",
        "goals",
        "budgets",
        "locks",
        "modules",
        "maximum_auto_risk",
        "profile",
        "approved_transactions",
        "extensions",
    }

    def load(self, path: Path) -> AutoPolicy:
        try:
            return self.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise AutoPolicyFormatError(f"cannot read auto policy {path}: {error}") from error

    def loads(self, text: str) -> AutoPolicy:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise AutoPolicyFormatError(f"invalid auto policy JSON: {error}") from error
        return self.from_data(data)

    def from_data(self, value: object) -> AutoPolicy:
        root = self._object(value, "auto policy")
        unknown = set(root) - self.TOP_LEVEL_KEYS
        if unknown:
            raise AutoPolicyFormatError(
                f"unknown auto policy fields: {', '.join(sorted(unknown))}"
            )
        version = self._integer(root.get("schema_version"), "schema_version")
        if version != AUTO_POLICY_SCHEMA_VERSION:
            raise AutoPolicyFormatError(
                f"auto policy schema {version} is not supported; "
                f"expected {AUTO_POLICY_SCHEMA_VERSION}"
            )
        try:
            mode = AutomationMode(self._text(root.get("mode"), "mode"))
            package = AutomationPackage(self._text(root.get("package"), "package"))
        except ValueError as error:
            raise AutoPolicyFormatError(str(error)) from error
        goals = tuple(self._text(item, "goals item") for item in self._array(root.get("goals"), "goals"))
        if len(goals) != len(set(goals)):
            raise AutoPolicyFormatError("goals must be unique")
        unsupported_goals = sorted(set(goals) - SUPPORTED_GOALS)
        if unsupported_goals:
            raise AutoPolicyFormatError(
                f"unsupported goals: {', '.join(unsupported_goals)}"
            )
        budgets = self._budgets(root.get("budgets"))
        locks = self._locks(root.get("locks"))
        modules = self._modules(root.get("modules"))
        risk_name = self._text(root.get("maximum_auto_risk"), "maximum_auto_risk")
        risk = {
            "information": RiskLevel.INFORMATION,
            "low": RiskLevel.LOW,
        }.get(risk_name)
        if risk is None:
            raise AutoPolicyFormatError("maximum_auto_risk must be information or low")
        profile = self._profile(root.get("profile"))
        approvals = {
            self._text(key, "approved transaction id"): self._sha256(
                digest, f"approved_transactions.{key}"
            )
            for key, digest in self._object(
                root.get("approved_transactions"), "approved_transactions"
            ).items()
        }
        if mode is not AutomationMode.VERIFIED_BATCH and approvals:
            raise AutoPolicyFormatError(
                "approved_transactions are allowed only in verified_batch mode"
            )
        if mode is AutomationMode.VERIFIED_BATCH and profile is None:
            raise AutoPolicyFormatError("verified_batch mode requires a locked profile")
        if package is AutomationPackage.PA800_READY and profile is None:
            raise AutoPolicyFormatError("pa800_ready package requires a locked profile")
        return AutoPolicy(
            policy_id=self._text(root.get("policy_id"), "policy_id"),
            policy_version=self._text(root.get("policy_version"), "policy_version"),
            mode=mode,
            package=package,
            seed=self._integer(root.get("seed"), "seed"),
            goals=goals,
            budgets=budgets,
            locks=locks,
            modules=modules,
            maximum_auto_risk=risk,
            profile=profile,
            approved_transactions=approvals,
            schema_version=version,
            extensions=self._object(root.get("extensions", {}), "extensions"),
        )

    def default(
        self,
        *,
        policy_id: str,
        policy_version: str,
        mode: AutomationMode,
        package: AutomationPackage,
        profile: PolicyProfile | None = None,
        seed: int = 0,
    ) -> AutoPolicy:
        modules = {
            name: ModulePolicy(
                enabled=True,
                minimum_confidence=0.95,
                allow_auto=name not in {
                    "cc7_cc11_conversion",
                    "initialization_update",
                    "sound_mapping",
                    "drum_mapping",
                    "quantization",
                    "velocity",
                    "polyphony",
                },
            )
            for name in PACKAGE_MODULES[package]
        }
        goals = {
            AutomationPackage.AUDIT: (),
            AutomationPackage.CLEAN: ("controller-cleanup",),
            AutomationPackage.PA800_READY: ("compatibility",),
            AutomationPackage.PERFORMANCE: (
                "dynamic-headroom",
                "timing-cleanup",
                "polyphony-review",
            ),
            AutomationPackage.FULL_ASSISTED: (
                "compatibility",
                "controller-cleanup",
                "dynamic-headroom",
                "timing-cleanup",
                "polyphony-review",
            ),
        }[package]
        data = {
            "schema_version": AUTO_POLICY_SCHEMA_VERSION,
            "policy_id": policy_id,
            "policy_version": policy_version,
            "mode": mode.value,
            "package": package.value,
            "seed": seed,
            "goals": list(goals),
            "budgets": asdict(ErrorBudgets()),
            "locks": {
                name: list(entries)
                for name, entries in asdict(PolicyLocks()).items()
            },
            "modules": {name: asdict(item) for name, item in modules.items()},
            "maximum_auto_risk": "low",
            "profile": asdict(profile) if profile else None,
            "approved_transactions": {},
            "extensions": {},
        }
        return self.from_data(data)

    def dumps(self, policy: AutoPolicy, *, indent: int = 2) -> str:
        data = asdict(policy)
        data["mode"] = policy.mode.value
        data["package"] = policy.package.value
        data["maximum_auto_risk"] = (
            "information"
            if policy.maximum_auto_risk is RiskLevel.INFORMATION
            else "low"
        )
        return json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=True) + "\n"

    def digest(self, policy: AutoPolicy) -> str:
        canonical = json.dumps(
            json.loads(self.dumps(policy)), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _budgets(self, value: object) -> ErrorBudgets:
        item = self._object(value, "budgets")
        required = {
            "maximum_timing_ticks",
            "maximum_timing_ms",
            "maximum_velocity_delta",
            "maximum_error_db",
            "maximum_controller_reduction_ratio",
            "maximum_high_risk_groups",
        }
        self._exact_keys(item, required, "budgets")
        timing_ticks = self._nonnegative_int(item["maximum_timing_ticks"], "maximum_timing_ticks")
        timing_ms = self._nonnegative_number(item["maximum_timing_ms"], "maximum_timing_ms")
        velocity = self._nonnegative_int(item["maximum_velocity_delta"], "maximum_velocity_delta")
        if velocity > 127:
            raise AutoPolicyFormatError("maximum_velocity_delta must be at most 127")
        error_db = self._nonnegative_number(item["maximum_error_db"], "maximum_error_db")
        reduction = self._nonnegative_number(
            item["maximum_controller_reduction_ratio"],
            "maximum_controller_reduction_ratio",
        )
        if reduction > 1.0:
            raise AutoPolicyFormatError(
                "maximum_controller_reduction_ratio must be at most 1"
            )
        high_risk = self._nonnegative_int(
            item["maximum_high_risk_groups"], "maximum_high_risk_groups"
        )
        return ErrorBudgets(
            timing_ticks, timing_ms, velocity, error_db, reduction, high_risk
        )

    def _locks(self, value: object) -> PolicyLocks:
        item = self._object(value, "locks")
        required = {
            "event_ids",
            "track_indices",
            "channels",
            "drum_notes",
            "message_kinds",
        }
        self._exact_keys(item, required, "locks")
        event_ids = tuple(self._text(entry, "locks.event_ids") for entry in self._array(item["event_ids"], "locks.event_ids"))
        tracks = tuple(self._nonnegative_int(entry, "locks.track_indices") for entry in self._array(item["track_indices"], "locks.track_indices"))
        channels = tuple(self._integer(entry, "locks.channels") for entry in self._array(item["channels"], "locks.channels"))
        notes = tuple(self._integer(entry, "locks.drum_notes") for entry in self._array(item["drum_notes"], "locks.drum_notes"))
        kinds = tuple(self._text(entry, "locks.message_kinds") for entry in self._array(item["message_kinds"], "locks.message_kinds"))
        for name, entries in (
            ("event_ids", event_ids),
            ("track_indices", tracks),
            ("channels", channels),
            ("drum_notes", notes),
            ("message_kinds", kinds),
        ):
            if len(entries) != len(set(entries)):
                raise AutoPolicyFormatError(f"locks.{name} must be unique")
        if any(not 1 <= channel <= 16 for channel in channels):
            raise AutoPolicyFormatError("locks.channels must be in range 1--16")
        if any(not 0 <= note <= 127 for note in notes):
            raise AutoPolicyFormatError("locks.drum_notes must be in range 0--127")
        return PolicyLocks(event_ids, tracks, channels, notes, kinds)

    def _modules(self, value: object) -> dict[str, ModulePolicy]:
        result = {}
        for name, raw in self._object(value, "modules").items():
            module_name = self._text(name, "module name")
            item = self._object(raw, f"modules.{module_name}")
            required = {"enabled", "minimum_confidence", "allow_auto", "parameters"}
            self._exact_keys(item, required, f"modules.{module_name}")
            enabled = self._boolean(item["enabled"], f"modules.{module_name}.enabled")
            confidence = self._number(
                item["minimum_confidence"], f"modules.{module_name}.minimum_confidence"
            )
            if not 0.0 <= confidence <= 1.0:
                raise AutoPolicyFormatError(
                    f"modules.{module_name}.minimum_confidence must be in range 0--1"
                )
            allow_auto = self._boolean(
                item["allow_auto"], f"modules.{module_name}.allow_auto"
            )
            result[module_name] = ModulePolicy(
                enabled,
                confidence,
                allow_auto,
                self._object(item["parameters"], f"modules.{module_name}.parameters"),
            )
        return result

    def _profile(self, value: object) -> PolicyProfile | None:
        if value is None:
            return None
        item = self._object(value, "profile")
        self._exact_keys(item, {"profile_id", "sha256"}, "profile")
        return PolicyProfile(
            self._text(item["profile_id"], "profile.profile_id"),
            self._sha256(item["sha256"], "profile.sha256"),
        )

    @staticmethod
    def _object(value: object, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise AutoPolicyFormatError(f"{path} must be a JSON object")
        return value

    @staticmethod
    def _array(value: object, path: str) -> list[Any]:
        if not isinstance(value, list):
            raise AutoPolicyFormatError(f"{path} must be a JSON array")
        return value

    @staticmethod
    def _text(value: object, path: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise AutoPolicyFormatError(f"{path} must be a non-empty string")
        return value

    @staticmethod
    def _integer(value: object, path: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise AutoPolicyFormatError(f"{path} must be an integer")
        return value

    def _nonnegative_int(self, value: object, path: str) -> int:
        result = self._integer(value, path)
        if result < 0:
            raise AutoPolicyFormatError(f"{path} must be non-negative")
        return result

    @staticmethod
    def _number(value: object, path: str) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise AutoPolicyFormatError(f"{path} must be a number")
        return float(value)

    def _nonnegative_number(self, value: object, path: str) -> float:
        result = self._number(value, path)
        if result < 0:
            raise AutoPolicyFormatError(f"{path} must be non-negative")
        return result

    @staticmethod
    def _boolean(value: object, path: str) -> bool:
        if not isinstance(value, bool):
            raise AutoPolicyFormatError(f"{path} must be a boolean")
        return value

    @staticmethod
    def _sha256(value: object, path: str) -> str:
        if not isinstance(value, str):
            raise AutoPolicyFormatError(f"{path} must be a SHA-256 string")
        result = value.lower()
        if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
            raise AutoPolicyFormatError(f"{path} must contain 64 hexadecimal characters")
        return result

    @staticmethod
    def _exact_keys(item: dict[str, Any], expected: set[str], path: str) -> None:
        missing = expected - set(item)
        unknown = set(item) - expected
        if missing:
            raise AutoPolicyFormatError(f"{path} is missing: {', '.join(sorted(missing))}")
        if unknown:
            raise AutoPolicyFormatError(f"{path} has unknown fields: {', '.join(sorted(unknown))}")


def evaluate_policy(plan: ProposalPlan, policy: AutoPolicy) -> tuple[PolicyDecision, ...]:
    decisions = []
    locked_events = set(policy.locks.event_ids)
    locked_tracks = set(policy.locks.track_indices)
    locked_channels = set(policy.locks.channels)
    locked_drum_notes = set(policy.locks.drum_notes)
    locked_message_kinds = set(policy.locks.message_kinds)
    for entry in plan.entries:
        reasons: list[str] = []
        if entry.status is not ProposalStatus.PROPOSED:
            reasons.extend(entry.blockers or (entry.status.value,))
            decisions.append(
                PolicyDecision(entry.proposal_id, PolicyAction.BLOCKED, tuple(reasons))
            )
            continue
        if (
            policy.mode is AutomationMode.ANALYZE_ONLY
            or policy.package is AutomationPackage.AUDIT
        ):
            decisions.append(
                PolicyDecision(
                    entry.proposal_id,
                    PolicyAction.ANALYZE_ONLY,
                    ("policy does not apply proposals",),
                )
            )
            continue
        module_policy = policy.modules.get(entry.module)
        if module_policy is None or not module_policy.enabled:
            decisions.append(
                PolicyDecision(
                    entry.proposal_id,
                    PolicyAction.BLOCKED,
                    (f"module is disabled by policy: {entry.module}",),
                )
            )
            continue
        touched_locks = sorted(
            event_id for event_id, _ in entry.targets if event_id in locked_events
        )
        if touched_locks:
            decisions.append(
                PolicyDecision(
                    entry.proposal_id,
                    PolicyAction.BLOCKED,
                    ("proposal targets locked events: " + ", ".join(touched_locks),),
                )
            )
            continue
        context_locks = (
            ("tracks", sorted(set(entry.track_indices) & locked_tracks)),
            ("channels", sorted(set(entry.channels) & locked_channels)),
            ("drum notes", sorted(set(entry.drum_notes) & locked_drum_notes)),
            (
                "message kinds",
                sorted(set(entry.message_kinds) & locked_message_kinds),
            ),
        )
        blocked_context = [
            f"{label}: {', '.join(map(str, values))}"
            for label, values in context_locks
            if values
        ]
        if blocked_context:
            decisions.append(
                PolicyDecision(
                    entry.proposal_id,
                    PolicyAction.BLOCKED,
                    ("proposal intersects policy locks: " + "; ".join(blocked_context),),
                )
            )
            continue
        if entry.confidence < module_policy.minimum_confidence:
            decisions.append(
                PolicyDecision(
                    entry.proposal_id,
                    PolicyAction.REVIEW,
                    (
                        f"confidence {entry.confidence:.3f} is below module minimum "
                        f"{module_policy.minimum_confidence:.3f}",
                    ),
                )
            )
            continue
        approved_digest = policy.approved_transactions.get(entry.proposal_id)
        if (
            policy.mode is AutomationMode.VERIFIED_BATCH
            and approved_digest == entry.transaction_digest
        ):
            decisions.append(
                PolicyDecision(
                    entry.proposal_id,
                    PolicyAction.AUTO_APPLY,
                    ("exact transaction fingerprint was previously approved",),
                )
            )
            continue
        if (
            module_policy.allow_auto
            and entry.risk <= policy.maximum_auto_risk
        ):
            decisions.append(
                PolicyDecision(
                    entry.proposal_id,
                    PolicyAction.AUTO_APPLY,
                    ("proposal is within policy risk and confidence limits",),
                )
            )
        else:
            reasons.append("proposal requires review under the selected policy")
            if approved_digest is not None and approved_digest != entry.transaction_digest:
                reasons.append("stored approval fingerprint does not match this transaction")
            decisions.append(
                PolicyDecision(entry.proposal_id, PolicyAction.REVIEW, tuple(reasons))
            )
    return tuple(decisions)
