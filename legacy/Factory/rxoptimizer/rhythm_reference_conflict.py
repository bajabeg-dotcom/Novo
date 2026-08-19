"""Resolution-aware Factory/reference comparison for X10 ANALYZE_ONLY."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from hashlib import sha256
from typing import Iterable, Sequence

from .rhythm_multimodal import (
    Component, PhaseObservation, VerifiedFactoryAssessment, circular_distance,
    model_config_sha256, validate_verified_factory_assessment,
)
from .rhythm_protection import MODALITY_STATUSES, REFERENCE_RELATIONSHIP_STATUSES, canonical_json


REFERENCE_CONTRACT_VERSION = "X10_FACTORY_REFERENCE_SUPPORT_V1"


def reference_config_sha256() -> str:
    payload = {
        "contract_version": REFERENCE_CONTRACT_VERSION,
        "model_config_sha256": model_config_sha256(),
        "support_arc": "complement_largest_exact_gap_smallest_start_tie",
        "expansion": "actual_member_and_reference_half_tick_resolution",
        "factory_authority": "FACTORY_ONLY_NO_REFIT",
        "capability": "ANALYZE_ONLY",
        "mutation_capability": "NONE",
    }
    return sha256(canonical_json(payload).encode("ascii")).hexdigest()


def _phase(value: Fraction) -> Fraction:
    return value % 1


@dataclass(frozen=True)
class CircularSupportArc:
    start: Fraction
    end: Fraction
    start_expansion: Fraction
    end_expansion: Fraction
    full_circle: bool
    component_id: int

    @property
    def expansion(self) -> Fraction:
        """Compatibility/report summary; containment uses directional floors."""
        return max(self.start_expansion, self.end_expansion)

    def contains_expanded(self, phase: Fraction, resolution: Fraction) -> bool:
        if self.full_circle:
            return True
        # Two closed circular intervals touch iff center distance does not exceed
        # the sum of their directed radii and arc half width.
        base_width = (self.end - self.start) % 1
        expanded_start = (self.start - self.start_expansion) % 1
        expanded_width = base_width + self.start_expansion + self.end_expansion
        if expanded_width + 2 * resolution >= 1:
            return True
        center = (expanded_start + expanded_width / 2) % 1
        return circular_distance(_phase(phase), center) <= expanded_width / 2 + resolution


@dataclass(frozen=True)
class ReferenceRelationship:
    status: str
    factory_arcs: tuple[CircularSupportArc, ...]
    supported_observation_ids: tuple[str, ...]
    outside_observation_ids: tuple[str, ...]
    config_sha256: str
    reason_codes: tuple[str, ...] = ()
    repair_allowed: bool = False
    proposal_allowed: bool = False
    mutation_capability: str = "NONE"
    semantic_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.status not in REFERENCE_RELATIONSHIP_STATUSES:
            raise ValueError(f"Unknown reference relationship status: {self.status}")
        if self.repair_allowed or self.proposal_allowed or self.mutation_capability != "NONE":
            raise ValueError("Reference relationship is immutable ANALYZE_ONLY")
        if self.config_sha256 != reference_config_sha256():
            raise ValueError("Reference relationship canonical config hash mismatch")
        payload = {
            "version": REFERENCE_CONTRACT_VERSION,
            "status": self.status,
            "arcs": [[a.component_id, a.start.numerator, a.start.denominator,
                      a.end.numerator, a.end.denominator,
                      a.start_expansion.numerator, a.start_expansion.denominator,
                      a.end_expansion.numerator, a.end_expansion.denominator, a.full_circle]
                     for a in self.factory_arcs],
            "supported": list(self.supported_observation_ids),
            "outside": list(self.outside_observation_ids),
            "config_sha256": self.config_sha256,
            "reason_codes": list(self.reason_codes),
        }
        object.__setattr__(self, "semantic_sha256", sha256(
            canonical_json(payload).encode("ascii")).hexdigest())


def shortest_support_arc(component_id: int, observations: Sequence[PhaseObservation]) -> CircularSupportArc:
    if not observations:
        raise ValueError("Factory support arc requires observations")
    phases = sorted({obs.phase for obs in observations})
    if len(phases) == 1:
        expansion = max(obs.half_tick_resolution for obs in observations)
        return CircularSupportArc(phases[0], phases[0], expansion, expansion,
                                  expansion * 2 >= 1, component_id)
    gaps = []
    for index, phase in enumerate(phases):
        next_phase = phases[(index + 1) % len(phases)]
        gap = (next_phase - phase) % 1
        # Complement starts at the end of the removed gap.  Smallest start is
        # the mandatory deterministic tie-break for equal largest gaps.
        gaps.append((gap, next_phase, phase))
    largest = max(gap for gap, _, _ in gaps)
    start, end = min((start, end) for gap, start, end in gaps if gap == largest)
    start_expansion = max(obs.half_tick_resolution for obs in observations if obs.phase == start)
    end_expansion = max(obs.half_tick_resolution for obs in observations if obs.phase == end)
    width = Fraction(1) - largest
    full_circle = width + start_expansion + end_expansion >= 1
    return CircularSupportArc(start, end, start_expansion, end_expansion, full_circle, component_id)


def build_factory_support_arcs(
    components: Sequence[Component],
    factory_observations: Iterable[PhaseObservation],
) -> tuple[CircularSupportArc, ...]:
    factory_observations = tuple(factory_observations)
    if any(obs.authority != "FACTORY" or obs.source_quality != "NORMAL" or
           obs.context_status != "EXACT_CONTEXT_MATCH" for obs in factory_observations):
        raise ValueError("Factory support arcs require NORMAL exact Factory observations")
    by_id = {obs.observation_id: obs for obs in factory_observations}
    if len(by_id) != len(factory_observations):
        raise ValueError("Duplicate Factory support observation_id")
    if len({component.component_id for component in components}) != len(components):
        raise ValueError("Duplicate Factory component_id")
    memberships = [member for component in components for member in component.hard_observation_ids]
    if len(memberships) != len(set(memberships)):
        raise ValueError("Factory component hard memberships must be disjoint")
    if set(memberships) != set(by_id):
        raise ValueError("Factory component hard memberships must cover observations exactly once")
    arcs = []
    for component in sorted(components, key=lambda item: item.component_id):
        try:
            members = [by_id[item] for item in component.hard_observation_ids]
        except KeyError as exc:
            raise ValueError("Factory component member is absent from exact observations") from exc
        arcs.append(shortest_support_arc(component.component_id, members))
    return tuple(arcs)


def _reference_sufficient(observations: Sequence[PhaseObservation]) -> bool:
    sources = {obs.source_sha256 for obs in observations}
    bars = {(obs.source_sha256, obs.bar_id) for obs in observations}
    counts = {source: sum(1 for obs in observations if obs.source_sha256 == source)
              for source in sources}
    return (len(sources) >= 3 and len(bars) >= 9 and observations and
            Fraction(max(counts.values()), len(observations)) <= Fraction(1, 2))


def assess_reference_relationship(
    factory_snapshot: VerifiedFactoryAssessment,
    reference_observations: Iterable[PhaseObservation],
    *,
    post_model_complete: bool = True,
) -> ReferenceRelationship:
    factory_snapshot = validate_verified_factory_assessment(factory_snapshot)
    assessment = factory_snapshot.assessment
    factory_modality_status = assessment.status
    components = assessment.components
    factory_observations = factory_snapshot.observations
    if factory_modality_status not in MODALITY_STATUSES:
        raise ValueError("Unknown Factory modality status")
    if factory_snapshot.config_sha256 != model_config_sha256():
        raise ValueError("Verified Factory model config hash mismatch")
    config_hash = reference_config_sha256()
    if not post_model_complete:
        return ReferenceRelationship("POST_MODEL_PARTIAL", (), (), (), config_hash,
                                     ("POST_MODEL_SCAN_PARTIAL",))
    if factory_modality_status not in {
        "ASSESSED_UNIMODAL", "ASSESSED_MULTIMODAL", "DEGENERATE_EXACT_REFERENCE"
    }:
        return ReferenceRelationship("DEFERRED_FACTORY_MODEL_UNSTABLE", (), (), (), config_hash,
                                     (factory_modality_status,))
    factory_observations = tuple(factory_observations)
    if not components or not factory_observations:
        raise ValueError("Stable Factory modality requires components and exact observations")
    context_keys = {item.exact_context_key for item in factory_observations}
    slot_keys = {item.event_slot_key for item in factory_observations}
    if len(context_keys) != 1 or len(slot_keys) != 1:
        raise ValueError("Verified Factory model must contain one exact context and event slot")
    exact_context_key = next(iter(context_keys))
    event_slot_key = next(iter(slot_keys))
    if any(item.exact_context_key != exact_context_key or
           item.event_slot_key != event_slot_key for item in factory_observations):
        raise ValueError("Factory observations do not match exact context/event slot")
    if assessment.selected_k != len(components):
        raise ValueError("Verified Factory selected_k/component count mismatch")
    arcs = build_factory_support_arcs(tuple(components), factory_observations)
    by_id = {item.observation_id: item for item in factory_observations}
    for component in components:
        members = [by_id[item] for item in component.hard_observation_ids]
        sources = {item.source_sha256 for item in members}
        bars = {(item.source_sha256, item.bar_id) for item in members}
        source_bars = {
            source: {bar for source_id, bar in bars if source_id == source}
            for source in sources
        }
        dominance = Fraction(max(len(values) for values in source_bars.values()), len(bars))
        if len(sources) < 3 or len(bars) < 9 or dominance > Fraction(1, 2):
            raise ValueError("Verified Factory component fails sufficiency recomputation")
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_EVEN
            expected_dominance = +(Decimal(dominance.numerator) / Decimal(dominance.denominator))
        if (set(component.source_files) != sources or set(component.bar_ids) != bars or
                component.dominant_source_share != expected_dominance):
            raise ValueError("Verified Factory component semantic summary mismatch")
    if any(arc.full_circle for arc in arcs):
        return ReferenceRelationship("FACTORY_SUPPORT_UNINFORMATIVE", arcs, (), (), config_hash,
                                     ("FULL_CIRCLE_SUPPORT_ARC",))
    references = tuple(sorted(reference_observations, key=lambda item: (
        item.source_sha256, item.bar_id, item.phase, item.observation_id)))
    if any(item.authority not in {"REFERENCE", "GOLD_REFERENCE"} for item in references):
        raise ValueError("Reference relationship rejects Factory observations as reference evidence")
    if any(item.source_quality != "NORMAL" or item.context_status != "EXACT_CONTEXT_MATCH"
           for item in references):
        raise ValueError("Reference relationship requires NORMAL exact reference evidence")
    if len({item.observation_id for item in references}) != len(references):
        raise ValueError("Duplicate reference observation_id")
    if any(item.exact_context_key != exact_context_key or
           item.event_slot_key != event_slot_key for item in references):
        raise ValueError("Reference observations do not match Factory exact context/event slot")
    if not references:
        return ReferenceRelationship("NO_REFERENCE_EVIDENCE", arcs, (), (), config_hash)
    supported = tuple(obs.observation_id for obs in references
                      if any(arc.contains_expanded(obs.phase, obs.half_tick_resolution) for arc in arcs))
    outside = tuple(obs.observation_id for obs in references if obs.observation_id not in set(supported))
    if not _reference_sufficient(references):
        return ReferenceRelationship("INSUFFICIENT_REFERENCE_EVIDENCE", arcs, supported, outside,
                                     config_hash, ("REFERENCE_SUFFICIENCY_GATE",))
    if outside:
        return ReferenceRelationship("POTENTIAL_CONTRADICTION", arcs, supported, outside,
                                     config_hash, ("REFERENCE_OUTSIDE_FACTORY_SUPPORT",))
    return ReferenceRelationship("REFERENCE_SUPPORT", arcs, supported, (), config_hash)