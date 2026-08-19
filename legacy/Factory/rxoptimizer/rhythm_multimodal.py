"""Deterministic, grid-free multimodal rhythm assessment for X10.

This module is deliberately ANALYZE_ONLY.  It models observed circular onset
phases; it never produces a target tick, proposal, repair, or MIDI mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from hashlib import sha256
from itertools import permutations
from typing import Iterable, Mapping, Sequence

from .rhythm_protection import (
    CANDIDATE_FIT_STATUSES,
    MODALITY_STATUSES,
    SUFFICIENCY_THRESHOLDS,
    canonical_json,
    protection_config_sha256,
)


MODEL_VERSION = "X10_WRAPPED_LAPLACE_BIC_V1"
SUFFICIENCY_VERSION = "X10_SUFFICIENCY_V1"
CAPABILITY = "ANALYZE_ONLY"
MUTATION_CAPABILITY = "NONE"
SEMANTIC_PRECISION = 50
INTERVAL_PRECISION = 60
TRANSCENDENTAL_PRECISION = 100
MAX_ITERATIONS = 1024


def _fraction(value: Fraction | Decimal | int | str | tuple[int, int]) -> Fraction:
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, float):
        raise TypeError("Binary float is forbidden for exact rational phase input")
    elif isinstance(value, bool):
        raise TypeError("Boolean is not a rational phase")
    elif isinstance(value, tuple):
        if (len(value) != 2 or any(isinstance(item, bool) or not isinstance(item, int)
                                  for item in value)):
            raise TypeError("Rational tuple must be exactly (integer numerator, integer denominator)")
        result = Fraction(value[0], value[1])
    else:
        result = Fraction(value)
    return result


def _phase(value: Fraction | int | str) -> Fraction:
    return _fraction(value) % 1


def circular_distance(a: Fraction, b: Fraction) -> Fraction:
    delta = abs(_phase(a) - _phase(b))
    return min(delta, 1 - delta)


def _decimal(value: Fraction | Decimal | int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    with localcontext() as ctx:
        ctx.prec = SEMANTIC_PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        if isinstance(value, Fraction):
            return +(Decimal(value.numerator) / Decimal(value.denominator))
        return +Decimal(value)


@dataclass(frozen=True)
class DecimalInterval:
    lower: Decimal
    upper: Decimal

    def __post_init__(self) -> None:
        if not self.lower.is_finite() or not self.upper.is_finite():
            raise ValueError("Decimal interval endpoints must be finite")
        if self.lower > self.upper:
            raise ValueError("Decimal interval lower endpoint exceeds upper endpoint")

    def strictly_below(self, other: "DecimalInterval") -> bool:
        return self.upper < other.lower

    def strictly_above(self, other: "DecimalInterval") -> bool:
        return self.lower > other.upper

    @classmethod
    def exact(cls, value: Decimal | int) -> "DecimalInterval":
        value = value if isinstance(value, Decimal) else Decimal(value)
        return cls(value, value)

    @classmethod
    def rational(cls, value: Fraction) -> "DecimalInterval":
        return cls(
            _rounded_binary(Decimal(value.numerator), Decimal(value.denominator), "div", ROUND_FLOOR),
            _rounded_binary(Decimal(value.numerator), Decimal(value.denominator), "div", ROUND_CEILING),
        )

    def __neg__(self) -> "DecimalInterval":
        # copy_negate is exact; unary ``-`` would apply the ambient Decimal
        # context and could silently collapse a certified 60-digit endpoint.
        return DecimalInterval(self.upper.copy_negate(), self.lower.copy_negate())

    def add(self, other: "DecimalInterval") -> "DecimalInterval":
        return DecimalInterval(
            _rounded_binary(self.lower, other.lower, "add", ROUND_FLOOR),
            _rounded_binary(self.upper, other.upper, "add", ROUND_CEILING),
        )

    def subtract(self, other: "DecimalInterval") -> "DecimalInterval":
        return self.add(-other)

    def multiply(self, other: "DecimalInterval") -> "DecimalInterval":
        lows = [_rounded_binary(a, b, "mul", ROUND_FLOOR)
                for a in (self.lower, self.upper) for b in (other.lower, other.upper)]
        highs = [_rounded_binary(a, b, "mul", ROUND_CEILING)
                 for a in (self.lower, self.upper) for b in (other.lower, other.upper)]
        return DecimalInterval(min(lows), max(highs))

    def divide(self, other: "DecimalInterval") -> "DecimalInterval":
        if other.lower <= 0 <= other.upper:
            raise ValueError("Interval division by a range containing zero")
        lows = [_rounded_binary(a, b, "div", ROUND_FLOOR)
                for a in (self.lower, self.upper) for b in (other.lower, other.upper)]
        highs = [_rounded_binary(a, b, "div", ROUND_CEILING)
                 for a in (self.lower, self.upper) for b in (other.lower, other.upper)]
        return DecimalInterval(min(lows), max(highs))

    def exp(self) -> "DecimalInterval":
        return DecimalInterval(
            _transcendental_bound(self.lower, "exp", lower=True),
            _transcendental_bound(self.upper, "exp", lower=False),
        )

    def ln(self) -> "DecimalInterval":
        if self.lower <= 0:
            raise ValueError("Natural log interval must be positive")
        return DecimalInterval(
            _transcendental_bound(self.lower, "ln", lower=True),
            _transcendental_bound(self.upper, "ln", lower=False),
        )


def _rounded_binary(a: Decimal, b: Decimal, operation: str, rounding: str) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = INTERVAL_PRECISION
        ctx.rounding = rounding
        if operation == "add":
            return +(a + b)
        if operation == "mul":
            return +(a * b)
        if operation == "div":
            return +(a / b)
    raise ValueError("Unknown directed Decimal operation")


def _transcendental_bound(value: Decimal, operation: str, *, lower: bool) -> Decimal:
    """Enclose a correctly-rounded Decimal exp/ln result conservatively.

    Decimal specifies correctly-rounded exp/ln under ROUND_HALF_EVEN.  A
    precision-P result therefore differs from the mathematical result by at
    most half an ulp.  We deliberately expand by two full P-precision ulps,
    then round outward at the contract interval precision.  The extra ulp also
    covers the preceding exact Decimal endpoint conversion.
    """
    with localcontext() as ctx:
        ctx.prec = TRANSCENDENTAL_PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        result = value.exp() if operation == "exp" else value.ln()
        if not result.is_finite():
            raise ArithmeticError("Non-finite Decimal transcendental")
        ulp = Decimal(1).scaleb(result.adjusted() - TRANSCENDENTAL_PRECISION + 1)
        expanded = result - 2 * ulp if lower else result + 2 * ulp
    with localcontext() as ctx:
        ctx.prec = INTERVAL_PRECISION
        ctx.rounding = ROUND_FLOOR if lower else ROUND_CEILING
        return +expanded


def strict_interval_minimum(intervals: Sequence[DecimalInterval]) -> int | None:
    winners = [index for index, interval in enumerate(intervals) if all(
        index == other or interval.strictly_below(other_interval)
        for other, other_interval in enumerate(intervals))]
    return winners[0] if len(winners) == 1 else None


def strict_interval_maximum(intervals: Sequence[DecimalInterval]) -> int | None:
    winners = [index for index, interval in enumerate(intervals) if all(
        index == other or interval.strictly_above(other_interval)
        for other, other_interval in enumerate(intervals))]
    return winners[0] if len(winners) == 1 else None


def component_collapse_reason(
    means: Sequence[Fraction],
    scales: Sequence[Decimal],
    mixture_weights: Sequence[Decimal],
    hard_assignments: Sequence[int],
) -> str | None:
    if not (len(means) == len(scales) == len(mixture_weights)) or not means:
        return "INVALID_COMPONENT_VECTOR"
    for index, weight in enumerate(mixture_weights):
        if weight <= 0:
            return "NONPOSITIVE_COMPONENT_MASS"
        if index not in hard_assignments:
            return "NO_FINAL_HARD_MEMBERS"
    canonical = [(mean, str(scale), str(weight))
                 for mean, scale, weight in zip(means, scales, mixture_weights)]
    if len(canonical) != len(set(canonical)):
        return "IDENTICAL_CANONICAL_COMPONENT"
    return None


@dataclass(frozen=True)
class PhaseObservation:
    source_sha256: str
    bar_id: str
    phase: Fraction
    half_tick_resolution: Fraction
    event_slot_key: str = "slot-0"
    exact_context_key: str = "context-0"
    observation_id: str = ""
    authority: str = "FACTORY"
    source_quality: str = "NORMAL"
    context_status: str = "EXACT_CONTEXT_MATCH"

    def __post_init__(self) -> None:
        if len(self.source_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.source_sha256):
            raise ValueError("source_sha256 must be lowercase SHA-256")
        if not self.bar_id or not self.event_slot_key or not self.exact_context_key:
            raise ValueError("bar_id, event_slot_key and exact_context_key are required")
        if self.authority not in {"FACTORY", "GOLD_REFERENCE", "REFERENCE"}:
            raise ValueError("Unknown phase observation authority")
        if self.source_quality not in {"NORMAL", "RARE", "OUTLIER", "INVALID"}:
            raise ValueError("Unknown phase observation source quality")
        if self.context_status not in {"EXACT_CONTEXT_MATCH", "CONTEXT_UNPROVEN", "CONTEXT_CONFLICT"}:
            raise ValueError("Unknown phase observation context status")
        phase = _phase(self.phase)
        resolution = _fraction(self.half_tick_resolution)
        if resolution <= 0 or resolution > Fraction(1, 2):
            raise ValueError("half_tick_resolution must be in (0, 1/2]")
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "half_tick_resolution", resolution)
        if not self.observation_id:
            payload = [self.source_sha256, self.bar_id, self.event_slot_key,
                       self.exact_context_key,
                       phase.numerator, phase.denominator,
                       resolution.numerator, resolution.denominator,
                       self.authority, self.source_quality, self.context_status]
            object.__setattr__(self, "observation_id", sha256(
                canonical_json(payload).encode("ascii")).hexdigest())

    @property
    def slot_key(self) -> str:
        return self.event_slot_key


@dataclass(frozen=True)
class WeightedObservation:
    observation: PhaseObservation
    raw_weight: Fraction
    normalized_weight_exact: Fraction
    normalized_weight: Decimal


@dataclass(frozen=True)
class Component:
    component_id: int
    mean: Fraction
    scale: Decimal
    mixture_weight: Decimal
    hard_observation_ids: tuple[str, ...]
    source_files: tuple[str, ...]
    bar_ids: tuple[tuple[str, str], ...]
    dominant_source_share: Decimal


@dataclass(frozen=True)
class CandidateFit:
    k: int
    status: str
    components: tuple[Component, ...] = ()
    log_likelihood: DecimalInterval | None = None
    bic: DecimalInterval | None = None
    iterations: int = 0
    reason_codes: tuple[str, ...] = ()
    posterior_tie: bool = False

    def __post_init__(self) -> None:
        if self.status not in CANDIDATE_FIT_STATUSES:
            raise ValueError(f"Unknown candidate fit status: {self.status}")


@dataclass(frozen=True)
class ModalityAssessment:
    status: str
    selected_k: int | None
    components: tuple[Component, ...]
    candidates: tuple[CandidateFit, ...]
    n_eff: Decimal
    config_sha256: str
    reason_codes: tuple[str, ...] = ()
    repair_allowed: bool = False
    proposal_allowed: bool = False
    mutation_capability: str = MUTATION_CAPABILITY
    capability: str = CAPABILITY
    semantic_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.status not in MODALITY_STATUSES:
            raise ValueError(f"Unknown modality status: {self.status}")
        if self.capability != CAPABILITY or self.mutation_capability != MUTATION_CAPABILITY:
            raise ValueError("Multimodal assessment capability is immutable ANALYZE_ONLY/NONE")
        if self.repair_allowed or self.proposal_allowed:
            raise ValueError("Multimodal assessment cannot authorize proposal or repair")
        if self.config_sha256 != model_config_sha256():
            raise ValueError("Multimodal assessment canonical config hash mismatch")
        payload = _assessment_payload(self)
        object.__setattr__(self, "semantic_sha256", sha256(
            canonical_json(payload).encode("ascii")).hexdigest())


def _observation_record(observation: PhaseObservation) -> dict[str, object]:
    return {
        "source_sha256": observation.source_sha256,
        "bar_id": observation.bar_id,
        "phase": [observation.phase.numerator, observation.phase.denominator],
        "half_tick_resolution": [observation.half_tick_resolution.numerator,
                                 observation.half_tick_resolution.denominator],
        "event_slot_key": observation.event_slot_key,
        "exact_context_key": observation.exact_context_key,
        "observation_id": observation.observation_id,
        "authority": observation.authority,
        "source_quality": observation.source_quality,
        "context_status": observation.context_status,
    }


def _verified_snapshot_payload(
    assessment: ModalityAssessment,
    observations: Sequence[PhaseObservation],
) -> dict[str, object]:
    return {
        "contract": "X10_VERIFIED_FACTORY_ASSESSMENT_V1",
        "assessment": _assessment_payload(assessment),
        "observations": [_observation_record(item) for item in observations],
    }


@dataclass(frozen=True)
class VerifiedFactoryAssessment:
    """Self-authenticating only through deterministic full reproduction.

    This type intentionally has no secret, token, registry, or authority
    state.  Construction is public, but validation accepts a value only when
    its complete model is byte-for-byte reproducible from its observations.
    """

    assessment: ModalityAssessment
    observations: tuple[PhaseObservation, ...]
    semantic_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.assessment, ModalityAssessment):
            raise TypeError("assessment must be ModalityAssessment")
        if not isinstance(self.observations, tuple) or any(
                not isinstance(item, PhaseObservation) for item in self.observations):
            raise TypeError("observations must be a tuple of PhaseObservation")
        if (not isinstance(self.semantic_sha256, str) or len(self.semantic_sha256) != 64 or
                any(char not in "0123456789abcdef" for char in self.semantic_sha256)):
            raise ValueError("semantic_sha256 must be lowercase SHA-256")

    @property
    def status(self) -> str:
        return self.assessment.status

    @property
    def components(self) -> tuple[Component, ...]:
        return self.assessment.components

    @property
    def config_sha256(self) -> str:
        return self.assessment.config_sha256


def _component_record(component: Component) -> dict[str, object]:
    return {
        "component_id": component.component_id,
        "mean": [component.mean.numerator, component.mean.denominator],
        "scale": str(component.scale),
        "mixture_weight": str(component.mixture_weight),
        "hard_observation_ids": list(component.hard_observation_ids),
        "source_files": list(component.source_files),
        "bar_ids": [list(item) for item in component.bar_ids],
        "dominant_source_share": str(component.dominant_source_share),
    }


def _interval_record(interval: DecimalInterval | None) -> list[str] | None:
    return None if interval is None else [str(interval.lower), str(interval.upper)]


def _candidate_record(candidate: CandidateFit) -> dict[str, object]:
    return {
        "k": candidate.k,
        "status": candidate.status,
        "components": [_component_record(item) for item in candidate.components],
        "log_likelihood": _interval_record(candidate.log_likelihood),
        "bic": _interval_record(candidate.bic),
        "iterations": candidate.iterations,
        "reason_codes": list(candidate.reason_codes),
        "posterior_tie": candidate.posterior_tie,
    }


def _assessment_payload(assessment: ModalityAssessment) -> dict[str, object]:
    return {
        "version": MODEL_VERSION,
        "status": assessment.status,
        "selected_k": assessment.selected_k,
        "components": [_component_record(c) for c in assessment.components],
        "candidates": [_candidate_record(c) for c in assessment.candidates],
        "n_eff": str(assessment.n_eff),
        "config_sha256": assessment.config_sha256,
        "reason_codes": list(assessment.reason_codes),
        "repair_allowed": assessment.repair_allowed,
        "proposal_allowed": assessment.proposal_allowed,
        "capability": assessment.capability,
        "mutation_capability": assessment.mutation_capability,
    }


def canonical_model_config() -> dict[str, object]:
    return {
        "model_version": MODEL_VERSION,
        "sufficiency_version": SUFFICIENCY_VERSION,
        "minimum_distinct_factory_files": 3,
        "minimum_bar_observations": 9,
        "maximum_dominant_source_share": "0.5",
        "minimum_loso_files": 4,
        "semantic_precision": SEMANTIC_PRECISION,
        "semantic_rounding": "ROUND_HALF_EVEN",
        "interval_precision": INTERVAL_PRECISION,
        "interval_rounding": ["ROUND_FLOOR", "ROUND_CEILING"],
        "transcendental_precision": TRANSCENDENTAL_PRECISION,
        "transcendental_rounding": "ROUND_HALF_EVEN",
        "directed_enclosure_version": "X10_DECIMAL_ULP_ENCLOSURE_V1",
        "directed_enclosure_algorithm": "correctly_rounded_exp_ln_plus_outward_ulp_hull",
        "transcendental_expansion_ulp_count": 2,
        "transcendental_expansion_policy": "two_work_precision_ulps_then_interval_outward_round",
        "max_iterations": MAX_ITERATIONS,
        "density": "exp(-d/b)/(2*b*(1-exp(-1/(2*b))))",
        "parameter_count": "3*k-1",
        "weighting": "equal-source Kish",
        "initialization": "weighted circular medoid then farthest-first",
        "mean_domain": "observed reduced rational phases",
        "capability": CAPABILITY,
        "mutation_capability": MUTATION_CAPABILITY,
        "parent_config_sha256": protection_config_sha256(),
    }


def model_config_sha256(config: Mapping[str, object] | None = None) -> str:
    canonical = canonical_model_config()
    if config is not None and dict(config) != canonical:
        raise ValueError("Multimodal canonical config is immutable")
    return sha256(canonical_json(canonical).encode("ascii")).hexdigest()


def equal_source_weights(observations: Iterable[PhaseObservation]) -> tuple[tuple[WeightedObservation, ...], Decimal]:
    ordered = tuple(sorted(observations, key=lambda o: (
        o.source_sha256, o.bar_id, o.slot_key, o.phase, o.observation_id)))
    if not ordered:
        return (), Decimal(0)
    counts: dict[str, int] = {}
    for obs in ordered:
        counts[obs.source_sha256] = counts.get(obs.source_sha256, 0) + 1
    raw = [Fraction(1, counts[obs.source_sha256]) for obs in ordered]
    total = sum(raw, Fraction())
    sum_squares = sum((item * item for item in raw), Fraction())
    n_eff_fraction = total * total / sum_squares
    with localcontext() as ctx:
        ctx.prec = SEMANTIC_PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        n_eff = +_decimal(n_eff_fraction)
        source_mass = +(n_eff / Decimal(len(counts)))
        remaining = dict((source, source_mass) for source in counts)
        remaining_count = dict(counts)
        normalized = []
        for obs in ordered:
            count = remaining_count[obs.source_sha256]
            if count == 1:
                weight = remaining[obs.source_sha256]
            else:
                weight = +(source_mass / Decimal(counts[obs.source_sha256]))
            normalized.append(weight)
            remaining[obs.source_sha256] -= weight
            remaining_count[obs.source_sha256] -= 1
    normalized_exact = [item * n_eff_fraction / total for item in raw]
    return tuple(WeightedObservation(obs, weight, exact, norm)
                 for obs, weight, exact, norm in zip(ordered, raw, normalized_exact, normalized)), n_eff


def _sufficient(observations: Sequence[PhaseObservation]) -> tuple[bool, tuple[str, ...]]:
    sources = {o.source_sha256 for o in observations}
    bars = {(o.source_sha256, o.bar_id) for o in observations}
    counts: dict[str, int] = {}
    for obs in observations:
        counts[obs.source_sha256] = counts.get(obs.source_sha256, 0) + 1
    dominance = Fraction(max(counts.values()), len(observations)) if observations else Fraction(1)
    reasons = []
    if len(sources) < int(SUFFICIENCY_THRESHOLDS["minimum_distinct_factory_files"]):
        reasons.append("INSUFFICIENT_DISTINCT_FILES")
    if len(bars) < int(SUFFICIENCY_THRESHOLDS["minimum_bar_observations"]):
        reasons.append("INSUFFICIENT_BAR_OBSERVATIONS")
    if dominance > Fraction(SUFFICIENCY_THRESHOLDS["maximum_dominant_source_share"]):
        reasons.append("DOMINANT_SOURCE_SHARE_EXCEEDED")
    return not reasons, tuple(reasons)


def _component_sufficient(members: Sequence[WeightedObservation]) -> tuple[bool, tuple[str, ...], Decimal]:
    observations = [item.observation for item in members]
    sources = {item.source_sha256 for item in observations}
    bars = {(item.source_sha256, item.bar_id) for item in observations}
    source_bars: dict[str, set[str]] = {}
    for item in observations:
        source_bars.setdefault(item.source_sha256, set()).add(item.bar_id)
    total_bars = len(bars)
    with localcontext() as ctx:
        ctx.prec = SEMANTIC_PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        dominance = (+(Decimal(max(len(values) for values in source_bars.values())) /
                       Decimal(total_bars))) if total_bars else Decimal(1)
    reasons = []
    if len(sources) < 3:
        reasons.append("INSUFFICIENT_DISTINCT_FILES")
    if len(bars) < 9:
        reasons.append("INSUFFICIENT_BAR_OBSERVATIONS")
    if dominance > Decimal("0.5"):
        reasons.append("DOMINANT_SOURCE_SHARE_EXCEEDED")
    return not reasons, tuple(reasons), dominance


def _weighted_median(values: Sequence[tuple[Fraction, Decimal]]) -> Fraction:
    ordered = sorted(values, key=lambda pair: pair[0])
    with localcontext() as ctx:
        ctx.prec = SEMANTIC_PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        total = sum((weight for _, weight in ordered), Decimal(0))
        cumulative = Decimal(0)
        for value, weight in ordered:
            cumulative = +(cumulative + weight)
            if +(cumulative * Decimal(2)) >= total:
                return value
    return ordered[-1][0]


def _initial_means(weighted: Sequence[WeightedObservation], k: int) -> tuple[Fraction, ...]:
    phases = sorted({item.observation.phase for item in weighted})
    costs = []
    with localcontext() as ctx:
        ctx.prec = SEMANTIC_PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        for candidate in phases:
            cost = sum((+(_decimal(circular_distance(item.observation.phase, candidate)) *
                          item.normalized_weight) for item in weighted), Decimal(0))
            costs.append((+cost, candidate))
    means = [min(costs)[1]]
    while len(means) < k:
        ranked = []
        for candidate in phases:
            if candidate in means:
                continue
            minimum = min(circular_distance(candidate, mean) for mean in means)
            ranked.append((minimum, candidate))
        maximum = max(distance for distance, _ in ranked)
        means.append(min(candidate for distance, candidate in ranked if distance == maximum))
    return tuple(sorted(means))


def _hard_by_distance(weighted: Sequence[WeightedObservation], means: Sequence[Fraction]) -> list[int]:
    assigned = []
    for item in weighted:
        distances = [circular_distance(item.observation.phase, mean) for mean in means]
        assigned.append(min(range(len(means)), key=lambda index: (distances[index], index)))
    return assigned


def _laplace_density(distance: Fraction, scale: Decimal) -> Decimal:
    if scale <= 0:
        raise ValueError("Wrapped Laplace scale must be positive")
    with localcontext() as ctx:
        ctx.prec = SEMANTIC_PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        d = _decimal(distance)
        return +((-d / scale).exp() / (Decimal(2) * scale *
                 (Decimal(1) - (-Decimal(1) / (Decimal(2) * scale)).exp())))


def _laplace_density_interval(distance: Fraction, scale: Decimal) -> DecimalInterval:
    if scale <= 0:
        raise ValueError("Wrapped Laplace scale must be positive")
    d = DecimalInterval.rational(distance)
    b = DecimalInterval.exact(scale)
    numerator = (-d.divide(b)).exp()
    half_inverse = DecimalInterval.exact(-1).divide(
        DecimalInterval.exact(2).multiply(b))
    normalization_tail = DecimalInterval.exact(1).subtract(half_inverse.exp())
    denominator = DecimalInterval.exact(2).multiply(b).multiply(normalization_tail)
    return numerator.divide(denominator)


def _weighted_objective_interval(
    weighted: Sequence[WeightedObservation],
    responsibilities: Sequence[Sequence[Decimal]],
    component: int,
    candidate: Fraction,
) -> DecimalInterval:
    total = DecimalInterval.exact(0)
    for item, row in zip(weighted, responsibilities):
        term = DecimalInterval.rational(item.normalized_weight_exact)
        term = term.multiply(DecimalInterval.exact(row[component]))
        term = term.multiply(DecimalInterval.rational(
            circular_distance(item.observation.phase, candidate)))
        total = total.add(term)
    return total


def _likelihood_interval(
    weighted: Sequence[WeightedObservation],
    means: Sequence[Fraction],
    scales: Sequence[Decimal],
    pis: Sequence[Decimal],
) -> DecimalInterval:
    total = DecimalInterval.exact(0)
    for item in weighted:
        density = DecimalInterval.exact(0)
        for h in range(len(means)):
            term = DecimalInterval.exact(pis[h]).multiply(
                _laplace_density_interval(
                    circular_distance(item.observation.phase, means[h]), scales[h]))
            density = density.add(term)
        total = total.add(
            DecimalInterval.rational(item.normalized_weight_exact).multiply(density.ln()))
    return total


def _parameter_digest(means: Sequence[Fraction], scales: Sequence[Decimal], pis: Sequence[Decimal]) -> str:
    payload = [[[m.numerator, m.denominator], str(b), str(p)]
               for m, b, p in zip(means, scales, pis)]
    return sha256(canonical_json(payload).encode("ascii")).hexdigest()


def _invalid(k: int, status: str, *reasons: str, iterations: int = 0) -> CandidateFit:
    return CandidateFit(k=k, status=status, iterations=iterations, reason_codes=tuple(reasons))


def fit_candidate(observations: Sequence[PhaseObservation], k: int) -> CandidateFit:
    weighted, n_eff = equal_source_weights(observations)
    if k < 1 or len({o.phase for o in observations}) < k or n_eff <= Decimal(3 * k - 1):
        return _invalid(k, "INVALID_IDENTIFIABILITY", "K_OR_N_EFF_IDENTIFIABILITY")
    means = _initial_means(weighted, k)
    assignments = _hard_by_distance(weighted, means)
    if set(assignments) != set(range(k)):
        return _invalid(k, "INVALID_EMPTY_INITIAL_COMPONENT", "EMPTY_INITIAL_COMPONENT")
    with localcontext() as ctx:
        ctx.prec = SEMANTIC_PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        masses = [sum((item.normalized_weight for item, a in zip(weighted, assignments) if a == h), Decimal(0))
                  for h in range(k)]
        pis = [+(mass / n_eff) for mass in masses]
        scales = []
        for h in range(k):
            members = [(item, means[h]) for item, a in zip(weighted, assignments) if a == h]
            raw = sum((_decimal(circular_distance(item.observation.phase, mean)) * item.normalized_weight
                       for item, mean in members), Decimal(0)) / masses[h]
            floor_fraction = _weighted_median([
                (item.observation.half_tick_resolution, item.normalized_weight) for item, _ in members])
            scales.append(+max(raw, _decimal(floor_fraction)))

    seen: dict[str, int] = {}
    responsibilities: list[list[Decimal]] = []
    for iteration in range(1, MAX_ITERATIONS + 1):
        digest = _parameter_digest(means, scales, pis)
        if digest in seen and seen[digest] != iteration - 1:
            return _invalid(k, "INVALID_NUMERICAL_CONSTRAINT", "NUMERICAL_CYCLE", iterations=iteration)
        seen[digest] = iteration
        responsibilities = []
        with localcontext() as ctx:
            ctx.prec = SEMANTIC_PRECISION
            ctx.rounding = ROUND_HALF_EVEN
            for item in weighted:
                try:
                    scores = [pis[h] * _laplace_density(
                        circular_distance(item.observation.phase, means[h]), scales[h])
                              for h in range(k)]
                except (ArithmeticError, ValueError):
                    return _invalid(k, "INVALID_NUMERICAL_CONSTRAINT",
                                    "SEMANTIC_DENSITY_UNAVAILABLE", iterations=iteration)
                denominator = sum(scores, Decimal(0))
                if not denominator.is_finite() or denominator <= 0:
                    return _invalid(k, "INVALID_NONFINITE_LIKELIHOOD", "INVALID_POSTERIOR_DENOMINATOR", iterations=iteration)
                responsibilities.append([+(score / denominator) for score in scores])
            new_means: list[Fraction] = []
            new_scales: list[Decimal] = []
            new_pis: list[Decimal] = []
            observed_phases = sorted({item.observation.phase for item in weighted})
            for h in range(k):
                mass = sum((item.normalized_weight * row[h]
                            for item, row in zip(weighted, responsibilities)), Decimal(0))
                if mass <= 0:
                    return _invalid(k, "INVALID_COMPONENT_COLLAPSE", "NONPOSITIVE_COMPONENT_MASS", iterations=iteration)
                objective: list[tuple[DecimalInterval, Fraction]] = []
                for candidate in observed_phases:
                    interval = _weighted_objective_interval(
                        weighted, responsibilities, h, candidate)
                    objective.append((interval, candidate))
                strict = [candidate for interval, candidate in objective if all(
                    candidate == other_candidate or interval.strictly_below(other_interval)
                    for other_interval, other_candidate in objective)]
                if len(strict) == 1:
                    mean = strict[0]
                else:
                    lowest_upper = min(interval.upper for interval, _ in objective)
                    overlapping = [candidate for interval, candidate in objective
                                   if interval.lower <= lowest_upper]
                    mean = min(overlapping)
                raw_scale = sum((item.normalized_weight * row[h] *
                                 _decimal(circular_distance(item.observation.phase, mean))
                                 for item, row in zip(weighted, responsibilities)), Decimal(0)) / mass
                floor_fraction = _weighted_median([
                    (item.observation.half_tick_resolution, item.normalized_weight * row[h])
                    for item, row in zip(weighted, responsibilities) if row[h] > 0])
                new_means.append(mean)
                new_scales.append(+max(raw_scale, _decimal(floor_fraction)))
                new_pis.append(+(mass / n_eff))
            canonical = sorted(zip(new_means, new_scales, new_pis), key=lambda item: (item[0], item[1], item[2]))
            new_means = [item[0] for item in canonical]
            new_scales = [item[1] for item in canonical]
            new_pis = [item[2] for item in canonical]
        new_digest = _parameter_digest(new_means, new_scales, new_pis)
        means, scales, pis = tuple(new_means), new_scales, new_pis
        if new_digest == digest:
            break
    else:
        return _invalid(k, "INVALID_NUMERICAL_CONSTRAINT", "NUMERICAL_NONCONVERGENCE", iterations=MAX_ITERATIONS)

    # Recompute final scores and use directed intervals for the strict winner rule.
    hard: list[int] = []
    posterior_tie = False
    for item in weighted:
        intervals = []
        try:
            for h in range(k):
                intervals.append(DecimalInterval.exact(pis[h]).multiply(
                    _laplace_density_interval(
                        circular_distance(item.observation.phase, means[h]), scales[h])))
        except (ArithmeticError, ValueError):
            return _invalid(k, "INVALID_NUMERICAL_CONSTRAINT",
                            "CERTIFIED_POSTERIOR_INTERVAL_UNAVAILABLE", iterations=iteration)
        winner = strict_interval_maximum(intervals)
        if winner is None:
            posterior_tie = True
            hard.append(min(range(k), key=lambda h: (-intervals[h].lower, h)))
        else:
            hard.append(winner)
    if posterior_tie:
        return _invalid(k, "INVALID_NUMERICAL_CONSTRAINT", "POSTERIOR_ASSIGNMENT_TIE", iterations=iteration)

    collapse_reason = component_collapse_reason(means, scales, pis, hard)
    if collapse_reason:
        return _invalid(k, "INVALID_COMPONENT_COLLAPSE", collapse_reason, iterations=iteration)
    components = []
    canonical_vectors: set[tuple[Fraction, str, str, tuple[int, ...]]] = set()
    for h in range(k):
        members = [item for item, assignment in zip(weighted, hard) if assignment == h]
        obs = [item.observation for item in members]
        enough, reasons, dominance = _component_sufficient(members)
        if not enough:
            return _invalid(k, "INVALID_COMPONENT_INSUFFICIENT", *reasons, iterations=iteration)
        source_counts: dict[str, int] = {}
        for member in obs:
            source_counts[member.source_sha256] = source_counts.get(member.source_sha256, 0) + 1
        vector = tuple(hard)
        canonical_key = (means[h], str(scales[h]), str(pis[h]), vector)
        if canonical_key in canonical_vectors:
            return _invalid(k, "INVALID_COMPONENT_COLLAPSE", "IDENTICAL_CANONICAL_COMPONENT", iterations=iteration)
        canonical_vectors.add(canonical_key)
        components.append(Component(
            h, means[h], scales[h], pis[h],
            tuple(sorted(member.observation.observation_id for member in members)),
            tuple(sorted(source_counts)),
            tuple(sorted({(member.observation.source_sha256, member.observation.bar_id)
                          for member in members})),
            dominance,
        ))

    try:
        likelihood = _likelihood_interval(weighted, means, scales, pis)
        raw_total = sum((item.raw_weight for item in weighted), Fraction())
        raw_squares = sum((item.raw_weight * item.raw_weight for item in weighted), Fraction())
        n_eff_exact = raw_total * raw_total / raw_squares
        bic = DecimalInterval.exact(-2).multiply(likelihood).add(
            DecimalInterval.exact(3 * k - 1).multiply(
                DecimalInterval.rational(n_eff_exact).ln()))
    except (ArithmeticError, ValueError):
        return _invalid(k, "INVALID_NUMERICAL_CONSTRAINT",
                        "CERTIFIED_INTERVAL_UNAVAILABLE", iterations=iteration)
    return CandidateFit(k, "VALID_CONVERGED", tuple(components), likelihood, bic, iteration)


def _select_candidate(observations: Sequence[PhaseObservation]) -> tuple[CandidateFit | None, tuple[CandidateFit, ...], str | None]:
    weighted, n_eff = equal_source_weights(observations)
    unique = len({o.phase for o in observations})
    bars = len({(o.source_sha256, o.bar_id) for o in observations})
    k_by_bic = 0
    for k in range(1, unique + 1):
        if Decimal(3 * k - 1) < n_eff:
            k_by_bic = k
    k_max = min(unique, bars // 9, k_by_bic)
    if k_max < 1:
        return None, (), "NO_IDENTIFIABLE_CANDIDATE"
    candidates = tuple(fit_candidate(observations, k) for k in range(1, k_max + 1))
    # A mathematically eligible candidate with an uncertified outcome is not a
    # losing candidate.  It makes the model comparison itself unprovable and
    # therefore blocks selection from otherwise converged candidates.  Only
    # structural/ineligibility failures may be excluded from BIC comparison.
    uncertainty_precedence = (
        ("NUMERICAL_REVIEW", lambda candidate: (
            candidate.status == "INVALID_NONFINITE_LIKELIHOOD" or
            (candidate.status == "VALID_CONVERGED" and candidate.bic is None) or
            any(reason in {
                "CERTIFIED_INTERVAL_UNAVAILABLE",
                "CERTIFIED_POSTERIOR_INTERVAL_UNAVAILABLE",
                "SEMANTIC_DENSITY_UNAVAILABLE",
                "INVALID_POSTERIOR_DENOMINATOR",
            } for reason in candidate.reason_codes))),
        ("NUMERICAL_CYCLE", lambda candidate:
            "NUMERICAL_CYCLE" in candidate.reason_codes),
        ("NUMERICAL_NONCONVERGENCE", lambda candidate:
            "NUMERICAL_NONCONVERGENCE" in candidate.reason_codes),
        ("POSTERIOR_TIE", lambda candidate:
            "POSTERIOR_ASSIGNMENT_TIE" in candidate.reason_codes),
        ("NUMERICAL_REVIEW", lambda candidate:
            candidate.status == "INVALID_NUMERICAL_CONSTRAINT"),
    )
    for error, predicate in uncertainty_precedence:
        if any(predicate(candidate) for candidate in candidates):
            return None, candidates, error
    valid = [candidate for candidate in candidates if candidate.status == "VALID_CONVERGED" and candidate.bic]
    if not valid:
        if any(c.status == "INVALID_COMPONENT_COLLAPSE" for c in candidates):
            return None, candidates, "COMPONENT_COLLAPSE"
        return None, candidates, "NO_VALID_CANDIDATE"
    winner_index = strict_interval_minimum([candidate.bic for candidate in valid])
    if winner_index is None:
        return None, candidates, "BIC_NEAR_TIE"
    return valid[winner_index], candidates, None


def _loso_stable(observations: Sequence[PhaseObservation], selected: CandidateFit) -> tuple[bool, str | None]:
    sources = sorted({o.source_sha256 for o in observations})
    if len(sources) < 4:
        return False, "LOSO_REQUIRES_FOUR_FILES"
    for omitted in sources:
        fold = [o for o in observations if o.source_sha256 != omitted]
        enough, _ = _sufficient(fold)
        if not enough:
            return False, "LOSO_FOLD_INSUFFICIENT"
        winner, _, error = _select_candidate(fold)
        if winner is None or error or winner.k != selected.k:
            return False, "LOSO_COMPONENT_COUNT_CHANGED"
        if selected.k == 1:
            continue
        costs: list[tuple[Fraction, tuple[int, ...]]] = []
        for permutation in permutations(range(selected.k)):
            cost = sum((circular_distance(selected.components[i].mean,
                                          winner.components[permutation[i]].mean)
                        for i in range(selected.k)), Fraction())
            costs.append((cost, permutation))
        intervals = [DecimalInterval.rational(cost) for cost, _ in costs]
        if strict_interval_minimum(intervals) is None:
            return False, "LOSO_COMPONENT_MATCH_TIE"
    return True, None


def assess_multimodal(observations: Iterable[PhaseObservation]) -> ModalityAssessment:
    observations = tuple(sorted(observations, key=lambda o: (
        o.source_sha256, o.bar_id, o.slot_key, o.phase, o.observation_id)))
    config_hash = model_config_sha256()
    if len({item.observation_id for item in observations}) != len(observations):
        raise ValueError("Duplicate multimodal observation_id")
    natural_instances = {(item.source_sha256, item.bar_id, item.slot_key) for item in observations}
    if len(natural_instances) != len(observations):
        raise ValueError("Multimodal event slot has multiple observations in one source/bar instance")
    if len({item.slot_key for item in observations}) > 1:
        raise ValueError("One multimodal assessment may contain only one exact slot")
    if len({item.exact_context_key for item in observations}) > 1:
        raise ValueError("One multimodal assessment may contain only one exact context")
    if any(item.authority != "FACTORY" for item in observations):
        raise ValueError("Factory multimodal fit rejects Gold/reference observations")
    if any(item.source_quality != "NORMAL" for item in observations):
        raise ValueError("Factory multimodal fit accepts only NORMAL source quality")
    if any(item.context_status != "EXACT_CONTEXT_MATCH" for item in observations):
        raise ValueError("Factory multimodal fit accepts only exact context")
    _, n_eff = equal_source_weights(observations)
    enough, reasons = _sufficient(observations)
    if not enough:
        return ModalityAssessment("INSUFFICIENT_MODAL_EVIDENCE", None, (), (), n_eff,
                                  config_hash, reasons)
    if len({o.phase for o in observations}) == 1:
        phase = observations[0].phase
        source_bars = {
            source: {(o.source_sha256, o.bar_id) for o in observations
                     if o.source_sha256 == source}
            for source in {o.source_sha256 for o in observations}
        }
        all_bars = {(o.source_sha256, o.bar_id) for o in observations}
        with localcontext() as ctx:
            ctx.prec = SEMANTIC_PRECISION
            ctx.rounding = ROUND_HALF_EVEN
            dominance = +(Decimal(max(len(values) for values in source_bars.values())) /
                          Decimal(len(all_bars)))
        component = Component(0, phase, Decimal(0), Decimal(1),
                              tuple(sorted(o.observation_id for o in observations)),
                              tuple(sorted({o.source_sha256 for o in observations})),
                              tuple(sorted(all_bars)), dominance)
        return ModalityAssessment("DEGENERATE_EXACT_REFERENCE", 1, (component,), (), n_eff,
                                  config_hash, ("EXACT_RATIONAL_REPEAT",))
    selected, candidates, error = _select_candidate(observations)
    if selected is None:
        status = {
            "BIC_NEAR_TIE": "UNSTABLE_BIC_NEAR_TIE",
            "POSTERIOR_TIE": "UNSTABLE_POSTERIOR_TIE",
            "COMPONENT_COLLAPSE": "UNSTABLE_COMPONENT_COLLAPSE",
            "NUMERICAL_CYCLE": "NUMERICAL_CYCLE_REVIEW_REQUIRED",
            "NUMERICAL_NONCONVERGENCE": "NUMERICAL_NONCONVERGENCE_REVIEW_REQUIRED",
            "NUMERICAL_REVIEW": "NUMERICAL_REVIEW_REQUIRED",
        }.get(error, "UNSTABLE_MODAL_STRUCTURE")
        return ModalityAssessment(status, None, (), candidates, n_eff, config_hash,
                                  (error or "NO_VALID_CANDIDATE",))
    stable, loso_error = _loso_stable(observations, selected)
    if not stable:
        status = "UNSTABLE_COMPONENT_MATCH" if loso_error == "LOSO_COMPONENT_MATCH_TIE" else "UNSTABLE_MODAL_STRUCTURE"
        return ModalityAssessment(status, selected.k, selected.components, candidates, n_eff,
                                  config_hash, (loso_error or "LOSO_UNSTABLE",))
    return ModalityAssessment(
        "ASSESSED_UNIMODAL" if selected.k == 1 else "ASSESSED_MULTIMODAL",
        selected.k, selected.components, candidates, n_eff, config_hash)


def assess_factory_model(observations: Iterable[PhaseObservation]) -> VerifiedFactoryAssessment:
    ordered = tuple(sorted(observations, key=lambda o: (
        o.source_sha256, o.bar_id, o.event_slot_key, o.phase, o.observation_id)))
    assessment = assess_multimodal(ordered)
    payload = _verified_snapshot_payload(assessment, ordered)
    return VerifiedFactoryAssessment(
        assessment, ordered, sha256(canonical_json(payload).encode("ascii")).hexdigest())


def validate_verified_factory_assessment(
    snapshot: object,
) -> VerifiedFactoryAssessment:
    """Recompute full canonical model; secrets and authority state are absent."""
    if not isinstance(snapshot, VerifiedFactoryAssessment):
        raise TypeError("Expected VerifiedFactoryAssessment")
    current_assessment_payload = _assessment_payload(snapshot.assessment)
    current_assessment_digest = sha256(canonical_json(
        current_assessment_payload).encode("ascii")).hexdigest()
    if current_assessment_digest != snapshot.assessment.semantic_sha256:
        raise ValueError("Nested Factory assessment semantic digest mismatch")
    current_payload = _verified_snapshot_payload(snapshot.assessment, snapshot.observations)
    current_digest = sha256(canonical_json(current_payload).encode("ascii")).hexdigest()
    if current_digest != snapshot.semantic_sha256:
        raise ValueError("Factory snapshot current-field digest mismatch")
    reproduced = assess_multimodal(snapshot.observations)
    reproduced_payload = _assessment_payload(reproduced)
    if (canonical_json(reproduced_payload) != canonical_json(current_assessment_payload) or
            reproduced.semantic_sha256 != snapshot.assessment.semantic_sha256):
        raise ValueError("Factory snapshot full multimodal reproduction mismatch")
    return snapshot


def assess_groove_coherence(
    slot_snapshots: Mapping[str, VerifiedFactoryAssessment],
) -> tuple[str, tuple[tuple[int, ...], ...]]:
    """Derive and assess cross-slot tuples from verified hard memberships."""
    slots = tuple(sorted(slot_snapshots))
    if not slots:
        return "UNSTABLE_GROOVE_MODE_STRUCTURE", ()
    snapshots = {slot: validate_verified_factory_assessment(slot_snapshots[slot])
                 for slot in slots}
    expected_config = model_config_sha256()
    if any(snapshots[slot].config_sha256 != expected_config for slot in slots):
        raise ValueError("Groove slot assessment config mismatch")
    if any(snapshots[slot].status not in {"ASSESSED_UNIMODAL", "ASSESSED_MULTIMODAL"}
           for slot in slots):
        return "UNSTABLE_GROOVE_MODE_STRUCTURE", ()
    contexts = {obs.exact_context_key for snapshot in snapshots.values()
                for obs in snapshot.observations}
    if len(contexts) != 1:
        return "UNSTABLE_GROOVE_MODE_STRUCTURE", ()
    per_instance: dict[tuple[str, str], dict[str, int]] = {}
    expected_universe: set[tuple[str, str]] | None = None
    for slot in slots:
        observations = snapshots[slot].observations
        if any(obs.authority != "FACTORY" or obs.source_quality != "NORMAL" or
               obs.context_status != "EXACT_CONTEXT_MATCH" or obs.event_slot_key != slot
               for obs in observations):
            raise ValueError("Groove observations must be NORMAL exact Factory slot evidence")
        universe = {(obs.source_sha256, obs.bar_id) for obs in observations}
        if expected_universe is None:
            expected_universe = universe
        elif universe != expected_universe:
            return "UNSTABLE_GROOVE_MODE_STRUCTURE", ()
        by_id = {obs.observation_id: obs for obs in observations}
        if len(by_id) != len(observations):
            raise ValueError("Duplicate groove observation_id")
        membership: dict[str, int] = {}
        for component in snapshots[slot].components:
            for observation_id in component.hard_observation_ids:
                if observation_id in membership:
                    raise ValueError("Groove component memberships are not disjoint")
                membership[observation_id] = component.component_id
        if set(membership) != set(by_id):
            raise ValueError("Groove component memberships do not exactly cover slot observations")
        for observation_id, component_id in membership.items():
            obs = by_id[observation_id]
            instance = (obs.source_sha256, obs.bar_id)
            if slot in per_instance.setdefault(instance, {}):
                raise ValueError("Multiple groove observations for one source/bar/slot")
            per_instance[instance][slot] = component_id
    tuples = []
    grouped: dict[tuple[int, ...], list[tuple[str, str]]] = {}
    for instance, assignments in sorted(per_instance.items()):
        if set(assignments) != set(slots) or any(assignments[slot] is None for slot in slots):
            return "UNSTABLE_GROOVE_MODE_STRUCTURE", ()
        values = []
        for slot in slots:
            if snapshots[slot].status == "ASSESSED_UNIMODAL":
                values.append(0)
                continue
            value = int(assignments[slot])
            if value < 0 or value >= len(snapshots[slot].components):
                return "UNSTABLE_GROOVE_MODE_STRUCTURE", ()
            values.append(value)
        value = tuple(values)
        tuples.append(value)
        grouped.setdefault(value, []).append(instance)
    for instances in grouped.values():
        sources = {source for source, _ in instances}
        dominance = Fraction(max(sum(1 for source, _ in instances if source == candidate)
                                 for candidate in sources), len(instances))
        if len(sources) < 3 or len(instances) < 9 or dominance > Fraction(1, 2):
            return "UNSTABLE_GROOVE_MODE_STRUCTURE", tuple(sorted(set(tuples)))
    all_sources = sorted({source for source, _ in per_instance})
    if len(all_sources) < 4:
        return "UNSTABLE_GROOVE_MODE_STRUCTURE", tuple(sorted(set(tuples)))
    # LOSO is identity matching for discrete ordered tuples: every fold must
    # retain exactly the same tuple modes and each mode must remain sufficient.
    expected_modes = set(grouped)
    for omitted in all_sources:
        fold_groups: dict[tuple[int, ...], list[tuple[str, str]]] = {}
        for mode, instances in grouped.items():
            fold_groups[mode] = [item for item in instances if item[0] != omitted]
        if {mode for mode, values in fold_groups.items() if values} != expected_modes:
            return "UNSTABLE_GROOVE_MODE_STRUCTURE", tuple(sorted(expected_modes))
        for instances in fold_groups.values():
            sources = {source for source, _ in instances}
            dominance = Fraction(max(sum(1 for source, _ in instances if source == candidate)
                                     for candidate in sources), len(instances))
            if len(sources) < 3 or len(instances) < 9 or dominance > Fraction(1, 2):
                return "UNSTABLE_GROOVE_MODE_STRUCTURE", tuple(sorted(expected_modes))
    return ("ASSESSED_MULTIMODAL" if len(grouped) > 1 else "ASSESSED_UNIMODAL",
            tuple(sorted(grouped)))