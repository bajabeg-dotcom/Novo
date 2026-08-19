"""S01 exact contextual profile matcher and Suggest-only velocity advisor.

The engine never falls back to another instrument, function, Element, CV, role,
encoding, fixed flag, or source kind. It can create an immutable Suggest plan
for a small number of Note On velocity outliers, but C01 intentionally does not
support applying Note On mutations yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from change_plan import (
    ChangePlan,
    EvidenceReference,
    EvidenceStatus,
    EventMutation,
    InputMeasurement,
    MutationField,
    RiskLevel,
    create_proposal,
)
from contextual_profile_builder import (
    ContextualInstrumentProfile,
    ContextualProfileCatalog,
    ProfileKey,
)
from policy_engine import PolicyEngine, PolicyRule
from style_loader import MidiEvent


class SuggestionStatus(str, Enum):
    SUGGEST_PLAN_READY = "SUGGEST_PLAN_READY"
    NO_PROFILE = "NO_PROFILE"
    INSUFFICIENT_REFERENCE = "INSUFFICIENT_REFERENCE"
    CONTEXT_BLOCKED = "CONTEXT_BLOCKED"
    NO_OUTLIERS = "NO_OUTLIERS"
    TOO_MANY_OUTLIERS = "TOO_MANY_OUTLIERS"


@dataclass(frozen=True, slots=True)
class SuggestionConfig:
    minimum_observations: int = 3
    minimum_styles: int = 2
    minimum_notes: int = 32
    minimum_deviation: int = 4
    maximum_adjustment: int = 8
    maximum_mutations: int = 32
    source: str = "PROJECT_POLICY_S01_CONSERVATIVE_DEFAULTS"

    def validate(self) -> None:
        values = (
            self.minimum_observations,
            self.minimum_styles,
            self.minimum_notes,
            self.minimum_deviation,
            self.maximum_adjustment,
            self.maximum_mutations,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("S01 configuration values must be positive integers")
        if self.maximum_adjustment > 32:
            raise ValueError("S01 maximum_adjustment must be <= 32")


@dataclass(frozen=True, slots=True)
class ProfileMatchResult:
    status: SuggestionStatus
    key: ProfileKey
    profile: ContextualInstrumentProfile | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VelocitySuggestionResult:
    status: SuggestionStatus
    match: ProfileMatchResult
    outlier_event_refs: tuple[tuple[int, int], ...]
    plan: ChangePlan | None
    reasons: tuple[str, ...]
    apply_supported: bool = False


S01_RULE = PolicyRule(
    rule_id="S01.PROFILE_VELOCITY_OUTLIER",
    version="1.0.0",
    description=(
        "Suggest a bounded Note On velocity step toward the exact contextual "
        "Factory profile p10-p90 interval."
    ),
    allowed_event_kinds=("note_on",),
    allowed_fields=(MutationField.DATA_1,),
    maximum_risk=RiskLevel.MEDIUM,
    allow_inferred_evidence=True,
)


class ExactContextualProfileMatcher:
    def __init__(self, config: SuggestionConfig | None = None) -> None:
        self.config = config or SuggestionConfig()
        self.config.validate()

    def match(
        self,
        catalog: ContextualProfileCatalog,
        key: ProfileKey,
    ) -> ProfileMatchResult:
        if key.source_kind != catalog.source_kind:
            return ProfileMatchResult(
                SuggestionStatus.NO_PROFILE, key, None,
                ("source kind differs; Factory and Gold profiles never mix",),
            )
        matches = [profile for profile in catalog.profiles if profile.key == key]
        if len(matches) != 1:
            return ProfileMatchResult(
                SuggestionStatus.NO_PROFILE, key, None,
                ("no single exact contextual profile key match",),
            )
        profile = matches[0]
        reasons: list[str] = []
        if profile.observation_count < self.config.minimum_observations:
            reasons.append("reference observation count is below configured minimum")
        if profile.style_count < self.config.minimum_styles:
            reasons.append("reference Style count is below configured minimum")
        if profile.note_count < self.config.minimum_notes:
            reasons.append("reference note count is below configured minimum")
        if profile.velocity.p10 is None or profile.velocity.p90 is None:
            reasons.append("reference velocity percentiles are unavailable")
        if reasons:
            return ProfileMatchResult(
                SuggestionStatus.INSUFFICIENT_REFERENCE,
                key,
                profile,
                tuple(reasons),
            )
        return ProfileMatchResult(
            SuggestionStatus.SUGGEST_PLAN_READY,
            key,
            profile,
            (),
        )


class ProfileVelocitySuggestor:
    """Create a Suggest plan only; Note On Apply remains unsupported by C01."""

    def __init__(
        self,
        config: SuggestionConfig | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self.config = config or SuggestionConfig()
        self.config.validate()
        self.matcher = ExactContextualProfileMatcher(self.config)
        self.policy_engine = policy_engine or PolicyEngine((S01_RULE,))

    def suggest(
        self,
        *,
        catalog: ContextualProfileCatalog,
        key: ProfileKey,
        source_sha256: str,
        events: tuple[MidiEvent, ...],
        identity_status: str,
        classification_status: str,
        classification_confidence: int,
        edit_policy: str,
        user_enabled_rule: bool,
    ) -> VelocitySuggestionResult:
        match = self.matcher.match(catalog, key)
        if match.status is not SuggestionStatus.SUGGEST_PLAN_READY:
            return VelocitySuggestionResult(match.status, match, (), None, match.reasons)
        assert match.profile is not None
        blockers: list[str] = []
        if not user_enabled_rule:
            blockers.append("USER has not enabled S01 velocity suggestion")
        if identity_status != "FACTORY_CONFIRMED":
            blockers.append("identity is not FACTORY_CONFIRMED")
        if classification_status != "CLASSIFIED":
            blockers.append("M07 context is not CLASSIFIED")
        if not 0 <= classification_confidence <= 100:
            blockers.append("classification confidence is outside 0..100")
        if edit_policy == "DO_NOT_TOUCH":
            blockers.append("upstream edit policy is DO_NOT_TOUCH")
        if key.encoding != "ORDINARY_MIDI":
            blockers.append("encoding is not ORDINARY_MIDI")
        if key.fixed_intro_ending_candidate:
            blockers.append("fixed Intro/Ending candidate is protected")
        if key.function == "UNKNOWN":
            blockers.append("UNKNOWN function cannot produce S01 suggestion")
        if blockers:
            return VelocitySuggestionResult(
                SuggestionStatus.CONTEXT_BLOCKED,
                match,
                (),
                None,
                tuple(blockers),
            )

        low = int(round(match.profile.velocity.p10 or 0))
        high = int(round(match.profile.velocity.p90 or 127))
        event_map = {
            (event.track_index, event.event_index): event for event in events
        }
        candidates: list[tuple[MidiEvent, int]] = []
        for event in events:
            if not event.is_note_on:
                continue
            velocity = int(event.data[1])
            target: int | None = None
            if velocity < low - self.config.minimum_deviation:
                target = min(low, velocity + self.config.maximum_adjustment)
            elif velocity > high + self.config.minimum_deviation:
                target = max(high, velocity - self.config.maximum_adjustment)
            if target is not None:
                target = max(1, min(127, target))
                if target != velocity:
                    candidates.append((event, target))
        refs = tuple((event.track_index, event.event_index) for event, _ in candidates)
        if not candidates:
            return VelocitySuggestionResult(
                SuggestionStatus.NO_OUTLIERS,
                match,
                (),
                None,
                ("all Note On velocities are within the configured profile tolerance",),
            )
        if len(candidates) > self.config.maximum_mutations:
            return VelocitySuggestionResult(
                SuggestionStatus.TOO_MANY_OUTLIERS,
                match,
                refs,
                None,
                ("outlier count exceeds maximum mutations per proposal",),
            )

        mutations = tuple(
            EventMutation.from_event(event, MutationField.DATA_1, target)
            for event, target in candidates
        )
        profile = match.profile
        proposal = create_proposal(
            source_sha256=source_sha256,
            rule_id=S01_RULE.rule_id,
            rule_version=S01_RULE.version,
            title=(
                f"Suggest bounded velocity steps for {profile.key.address} — "
                f"{profile.official_name} / {profile.key.function}"
            ),
            description=(
                "Move only profile-outlier Note On velocities by a bounded step "
                "toward the exact contextual Factory p10-p90 interval."
            ),
            evidence_status=EvidenceStatus.INFERRED,
            confidence_percent=float(classification_confidence),
            risk=RiskLevel.MEDIUM,
            input_measurements=(
                InputMeasurement("profile_observations", profile.observation_count, "SEGMENTS", EvidenceStatus.DERIVED),
                InputMeasurement("profile_styles", profile.style_count, "STYLES", EvidenceStatus.DERIVED),
                InputMeasurement("profile_notes", profile.note_count, "NOTES", EvidenceStatus.DERIVED),
                InputMeasurement("profile_velocity_p10", profile.velocity.p10, "MIDI_7BIT", EvidenceStatus.DERIVED),
                InputMeasurement("profile_velocity_p90", profile.velocity.p90, "MIDI_7BIT", EvidenceStatus.DERIVED),
                InputMeasurement("outlier_count", len(mutations), "NOTE_ON_EVENTS", EvidenceStatus.DERIVED),
                InputMeasurement("maximum_adjustment", self.config.maximum_adjustment, "MIDI_7BIT", EvidenceStatus.CONFIRMED),
            ),
            evidence=(
                EvidenceReference(
                    source_id=profile.profile_id,
                    status=EvidenceStatus.DERIVED,
                    detail=(
                        f"Exact R01 key match with {profile.observation_count} observations "
                        f"from {profile.style_count} Styles."
                    ),
                    path=catalog.source_path,
                ),
                EvidenceReference(
                    source_id="M07",
                    status=EvidenceStatus.INFERRED,
                    detail=(
                        f"function={key.function}, confidence={classification_confidence}, "
                        f"edit_policy={edit_policy}"
                    ),
                ),
            ),
            mutations=mutations,
            expected_difference=(
                f"At most {self.config.maximum_adjustment} velocity units per listed "
                f"Note On; exact profile interval {low}-{high}."
            ),
            protections=(
                "S01 is Suggest-only and requires individual USER review.",
                "Relative timing, pitch, duration and all non-listed velocities remain unchanged.",
                "Velocity-switch/RX thresholds are unknown; C01 Note On Apply is unsupported.",
            ),
        )
        plan = self.policy_engine.build_plan(
            source_sha256=source_sha256,
            proposals=(proposal,),
            events=event_map,
        )
        return VelocitySuggestionResult(
            SuggestionStatus.SUGGEST_PLAN_READY,
            match,
            refs,
            plan,
            (),
            apply_supported=False,
        )
