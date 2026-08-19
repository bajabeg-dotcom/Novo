from decimal import Decimal
from fractions import Fraction
import gc
import json
from pathlib import Path
import weakref

import pytest

from rxoptimizer.rhythm_multimodal import (
    CAPABILITY,
    CandidateFit,
    DecimalInterval,
    ModalityAssessment,
    PhaseObservation,
    VerifiedFactoryAssessment,
    assess_factory_model,
    assess_groove_coherence,
    assess_multimodal,
    canonical_model_config,
    circular_distance,
    component_collapse_reason,
    equal_source_weights,
    fit_candidate,
    model_config_sha256,
    _initial_means,
    strict_interval_maximum,
    strict_interval_minimum,
    _laplace_density_interval,
    validate_verified_factory_assessment,
)


def _sha(index):
    return f"{index:064x}"


def _observations(phases_by_source, resolution=Fraction(1, 384), slot="slot"):
    result = []
    for source_index, phases in enumerate(phases_by_source, 1):
        for bar_index, phase in enumerate(phases):
            result.append(PhaseObservation(
                _sha(source_index), f"bar-{bar_index}", Fraction(phase), resolution, slot))
    return result


def test_circular_distance_wrap_and_reduced_fraction():
    assert circular_distance(Fraction(99, 100), Fraction(1, 100)) == Fraction(1, 50)
    assert PhaseObservation(_sha(1), "b", Fraction(5, 4), Fraction(1, 960)).phase == Fraction(1, 4)


def test_mixed_ppq_resolution_is_preserved_exactly():
    first = PhaseObservation(_sha(1), "b1", Fraction(1, 3), Fraction(1, 384))
    second = PhaseObservation(_sha(2), "b2", Fraction(1, 3), Fraction(1, 768))
    assert first.half_tick_resolution != second.half_tick_resolution
    assert isinstance(first.phase, Fraction)
    with pytest.raises(TypeError):
        PhaseObservation(_sha(1), "bad", 0.25, Fraction(1, 384))
    assert PhaseObservation(_sha(1), "tuple", (1, 4), Fraction(1, 384)).phase == Fraction(1, 4)


def test_equal_source_kish_weights_and_scale_invariance():
    observations = _observations([[Fraction(1, 4)] * 2, [Fraction(1, 4)] * 8,
                                  [Fraction(1, 4)] * 4])
    weighted, n_eff = equal_source_weights(observations)
    masses = {}
    for item in weighted:
        masses.setdefault(item.observation.source_sha256, Decimal(0))
        masses[item.observation.source_sha256] += item.normalized_weight
    quantum = Decimal("1e-24")
    assert len({value.quantize(quantum) for value in masses.values()}) == 1
    assert sum((item.normalized_weight for item in weighted), Decimal(0)).quantize(quantum) == \
        n_eff.quantize(quantum)
    duplicated = observations + [o for o in observations if o.source_sha256 == _sha(2)]
    duplicate_weights, _ = equal_source_weights(duplicated)
    duplicate_masses = {}
    for item in duplicate_weights:
        duplicate_masses.setdefault(item.observation.source_sha256, Decimal(0))
        duplicate_masses[item.observation.source_sha256] += item.normalized_weight
    assert len({value.quantize(quantum) for value in duplicate_masses.values()}) == 1


def test_insufficient_and_exact_repeat_pre_gate():
    insufficient = assess_multimodal(_observations([[Fraction(1, 4)] * 4] * 2))
    assert insufficient.status == "INSUFFICIENT_MODAL_EVIDENCE"
    exact = assess_multimodal(_observations([[Fraction(1, 4)] * 9] * 4))
    assert exact.status == "DEGENERATE_EXACT_REFERENCE"
    assert exact.components[0].scale == 0
    assert not exact.repair_allowed


def test_unimodal_is_grid_free_and_deterministic():
    phases = [[Fraction(1, 4) + Fraction((bar % 3) - 1, 1000) for bar in range(9)]
              for _ in range(4)]
    observations = _observations(phases)
    forward = assess_multimodal(observations)
    reverse = assess_multimodal(reversed(observations))
    assert forward.status == "ASSESSED_UNIMODAL"
    assert forward.semantic_sha256 == reverse.semantic_sha256
    assert forward.components[0].mean in {item.phase for item in observations}


def test_exact_epsilon_medoid_and_ambient_decimal_context_invariance():
    epsilon = Fraction(1, 10**40)
    observations = _observations([[Fraction(1, 4), Fraction(1, 4) + epsilon,
                                   Fraction(1, 4) + epsilon] for _ in range(4)],
                                 resolution=Fraction(1, 10**45))
    weighted, _ = equal_source_weights(observations)
    with __import__("decimal").localcontext() as ctx:
        ctx.prec = 6
        ctx.rounding = __import__("decimal").ROUND_FLOOR
        low_context_mean = _initial_means(weighted, 1)
        low_context_result = assess_multimodal(observations)
    with __import__("decimal").localcontext() as ctx:
        ctx.prec = 17
        ctx.rounding = __import__("decimal").ROUND_CEILING
        high_context_mean = _initial_means(weighted, 1)
        high_context_result = assess_multimodal(reversed(observations))
    assert low_context_mean == high_context_mean == (Fraction(1, 4) + epsilon,)
    assert low_context_result.semantic_sha256 == high_context_result.semantic_sha256


def test_mixed_exact_contexts_are_rejected():
    observations = _observations([[Fraction(1, 4)] * 9] * 4)
    observations[-1] = PhaseObservation(
        observations[-1].source_sha256, observations[-1].bar_id,
        observations[-1].phase, observations[-1].half_tick_resolution,
        observations[-1].event_slot_key, "different-context")
    with pytest.raises(ValueError):
        assess_multimodal(observations)


def test_bimodal_and_wrap_fixture():
    fixture = json.loads(Path("tests/fixtures/x10_multimodal/wrap_bimodal.json").read_text())
    phases = []
    for _ in range(fixture["sources"]):
        values = []
        for phase in fixture["phases"]:
            values.extend([Fraction(phase)] * fixture["bars_per_phase_per_source"])
        phases.append(values)
    assessment = assess_multimodal(_observations(phases, Fraction(fixture["half_tick_resolution"])))
    assert assessment.status == "ASSESSED_MULTIMODAL"
    assert assessment.selected_k == 2
    assert {component.mean for component in assessment.components} == {Fraction(1, 100), Fraction(99, 100)}


def test_component_sufficiency_rejects_source_local_mode():
    phases = [
        [Fraction(1, 4)] * 9,
        [Fraction(1, 4)] * 9,
        [Fraction(3, 4)] * 9,
        [Fraction(3, 4)] * 9,
    ]
    fit = fit_candidate(_observations(phases), 2)
    assert fit.status == "INVALID_COMPONENT_INSUFFICIENT"


def test_component_dominance_is_hard_assigned_source_bar_share():
    counts_a = [3, 3, 3, 0]
    counts_b = [30, 15, 15, 3]
    phases = [[Fraction(1, 4)] * counts_a[index] +
              [Fraction(3, 4)] * counts_b[index] for index in range(4)]
    result = assess_multimodal(_observations(phases))
    component = next(item for item in result.components if item.mean == Fraction(3, 4))
    with __import__("decimal").localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = __import__("decimal").ROUND_HALF_EVEN
        expected = +(Decimal(30) / Decimal(63))
    assert component.dominant_source_share == expected
    assert len(component.bar_ids) == 63


def test_decimal_interval_strict_near_tie_contract():
    left = DecimalInterval(Decimal("1.0"), Decimal("1.1"))
    overlap = DecimalInterval(Decimal("1.05"), Decimal("1.2"))
    right = DecimalInterval(Decimal("1.2"), Decimal("1.3"))
    assert not left.strictly_below(overlap)
    assert left.strictly_below(right)
    assert strict_interval_minimum([left, overlap]) is None
    assert strict_interval_minimum([left, right]) == 0
    assert strict_interval_maximum([left, right]) == 1


def test_certified_transcendental_intervals_are_non_point_and_contain_high_precision_value():
    interval = _laplace_density_interval(Fraction(1, 7), Decimal("0.03125"))
    assert interval.lower < interval.upper
    with __import__("decimal").localcontext() as ctx:
        ctx.prec = 90
        distance = Decimal(1) / Decimal(7)
        scale = Decimal("0.03125")
        expected = (-distance / scale).exp() / (
            Decimal(2) * scale * (Decimal(1) - (-Decimal(1) / (Decimal(2) * scale)).exp()))
    assert interval.lower <= expected <= interval.upper


def test_likelihood_and_bic_use_non_point_certified_enclosures():
    phases = [[Fraction(1, 4) + Fraction((bar % 3) - 1, 1000) for bar in range(9)]
              for _ in range(4)]
    fit = fit_candidate(_observations(phases), 1)
    assert fit.status == "VALID_CONVERGED"
    assert fit.log_likelihood.lower < fit.log_likelihood.upper
    assert fit.bic.lower < fit.bic.upper


@pytest.mark.parametrize(("candidate", "expected_status"), [
    (CandidateFit(2, "INVALID_NUMERICAL_CONSTRAINT",
                  reason_codes=("POSTERIOR_ASSIGNMENT_TIE",)),
     "UNSTABLE_POSTERIOR_TIE"),
    (CandidateFit(2, "INVALID_NUMERICAL_CONSTRAINT",
                  reason_codes=("CERTIFIED_INTERVAL_UNAVAILABLE",)),
     "NUMERICAL_REVIEW_REQUIRED"),
    (CandidateFit(2, "INVALID_NUMERICAL_CONSTRAINT",
                  reason_codes=("NUMERICAL_CYCLE",)),
     "NUMERICAL_CYCLE_REVIEW_REQUIRED"),
    (CandidateFit(2, "INVALID_NUMERICAL_CONSTRAINT",
                  reason_codes=("NUMERICAL_NONCONVERGENCE",)),
     "NUMERICAL_NONCONVERGENCE_REVIEW_REQUIRED"),
    (CandidateFit(2, "VALID_CONVERGED"), "NUMERICAL_REVIEW_REQUIRED"),
])
def test_uncertain_eligible_k_blocks_otherwise_valid_k1(monkeypatch, candidate, expected_status):
    observations = _observations([
        [Fraction(1, 4), Fraction(3, 4)] * 5 for _ in range(4)])
    valid_k1 = CandidateFit(
        1, "VALID_CONVERGED",
        log_likelihood=DecimalInterval(Decimal("-10.1"), Decimal("-10.0")),
        bic=DecimalInterval(Decimal("22.0"), Decimal("22.1")),
    )
    import rxoptimizer.rhythm_multimodal as module
    monkeypatch.setattr(module, "fit_candidate", lambda _observations, k:
                        valid_k1 if k == 1 else candidate)
    result = assess_multimodal(observations)
    assert result.status == expected_status
    assert result.status != "ASSESSED_UNIMODAL"


def test_overlapping_certified_bic_candidates_block_selection(monkeypatch):
    observations = _observations([
        [Fraction(1, 4), Fraction(3, 4)] * 5 for _ in range(4)])
    candidates = {
        1: CandidateFit(1, "VALID_CONVERGED",
                        bic=DecimalInterval(Decimal("10.0"), Decimal("10.2"))),
        2: CandidateFit(2, "VALID_CONVERGED",
                        bic=DecimalInterval(Decimal("10.1"), Decimal("10.3"))),
    }
    import rxoptimizer.rhythm_multimodal as module
    monkeypatch.setattr(module, "fit_candidate", lambda _observations, k: candidates[k])
    assert assess_multimodal(observations).status == "UNSTABLE_BIC_NEAR_TIE"


def test_component_collapse_contract_is_explicit():
    assert component_collapse_reason(
        [Fraction(1, 4), Fraction(1, 4)],
        [Decimal("0.01"), Decimal("0.01")],
        [Decimal("0.5"), Decimal("0.5")],
        [0, 1],
    ) == "IDENTICAL_CANONICAL_COMPONENT"
    assert component_collapse_reason(
        [Fraction(1, 4), Fraction(3, 4)],
        [Decimal("0.01"), Decimal("0.01")],
        [Decimal("1"), Decimal("0")],
        [0],
    ) == "NONPOSITIVE_COMPONENT_MASS"


def test_loso_detects_mode_that_depends_on_one_source():
    phases = []
    for source in range(4):
        values = [Fraction(3, 4)] * 3
        if source < 3:
            values += [Fraction(1, 4)] * 3
        phases.append(values)
    result = assess_multimodal(_observations(phases))
    assert result.status == "UNSTABLE_MODAL_STRUCTURE"
    assert result.reason_codes == ("LOSO_COMPONENT_COUNT_CHANGED",)


def test_config_is_closed_versioned_and_analyze_only():
    config = canonical_model_config()
    assert config["capability"] == CAPABILITY == "ANALYZE_ONLY"
    assert config["mutation_capability"] == "NONE"
    assert config["transcendental_precision"] == 100
    assert config["directed_enclosure_version"] == "X10_DECIMAL_ULP_ENCLOSURE_V1"
    assert config["transcendental_expansion_ulp_count"] == 2
    assert len(model_config_sha256()) == 64
    tampered = dict(config)
    tampered["max_iterations"] = 3
    with pytest.raises(ValueError):
        model_config_sha256(tampered)


def test_unknown_modality_and_capability_escalation_rejected():
    with pytest.raises(ValueError):
        ModalityAssessment("UNKNOWN", None, (), (), Decimal(0), model_config_sha256())
    with pytest.raises(ValueError):
        ModalityAssessment("DEFERRED", None, (), (), Decimal(0), model_config_sha256(),
                           repair_allowed=True)
    with pytest.raises(ValueError):
        ModalityAssessment("DEFERRED", None, (), (), Decimal(0), "0" * 64)


def test_factory_fit_rejects_reference_non_normal_and_unproven_context():
    base = _observations([[Fraction(1, 4)] * 9] * 4)
    with pytest.raises(ValueError):
        assess_multimodal([PhaseObservation(
            item.source_sha256, item.bar_id, item.phase, item.half_tick_resolution,
            item.slot_key, authority="REFERENCE") for item in base])
    with pytest.raises(ValueError):
        assess_multimodal([PhaseObservation(
            item.source_sha256, item.bar_id, item.phase, item.half_tick_resolution,
            item.slot_key, source_quality="RARE") for item in base])
    with pytest.raises(ValueError):
        assess_multimodal([PhaseObservation(
            item.source_sha256, item.bar_id, item.phase, item.half_tick_resolution,
            item.slot_key, context_status="CONTEXT_UNPROVEN") for item in base])


def test_groove_tuple_missing_and_sufficient_modes():
    phases = [[Fraction(1, 4) + Fraction((i % 3) - 1, 1000) for i in range(9)]
              for _ in range(4)]
    obs_a = _observations(phases, slot="a")
    obs_b = _observations(phases, slot="b")
    slots = {"a": assess_factory_model(obs_a), "b": assess_factory_model(obs_b)}
    incomplete_b = obs_b[:-1]
    incomplete_slots = {"a": slots["a"], "b": assess_factory_model(incomplete_b)}
    assert assess_groove_coherence(incomplete_slots)[0] == \
        "UNSTABLE_GROOVE_MODE_STRUCTURE"
    assert assess_groove_coherence(slots)[0] == \
        "ASSESSED_UNIMODAL"


def test_groove_rejects_forged_hard_membership():
    phases = [[Fraction(1, 4) + Fraction((i % 3) - 1, 1000) for i in range(9)]
              for _ in range(4)]
    observations = _observations(phases, slot="a")
    raw_assessment = assess_multimodal(observations)
    with pytest.raises(TypeError):
        assess_groove_coherence({"a": raw_assessment})


def test_groove_rejects_degenerate_exact_snapshot_and_direct_fabrication():
    exact = _observations([[Fraction(1, 4)] * 9] * 4, slot="a")
    assert assess_groove_coherence({"a": assess_factory_model(exact)})[0] == \
        "UNSTABLE_GROOVE_MODE_STRUCTURE"
    forged = object.__new__(VerifiedFactoryAssessment)
    with pytest.raises((ValueError, AttributeError)):
        assess_groove_coherence({"a": forged})


@pytest.mark.parametrize("field,value", [
    ("status", "ASSESSED_MULTIMODAL"),
    ("selected_k", 99),
    ("components", ()),
    ("config_sha256", "0" * 64),
])
def test_verified_snapshot_rejects_current_nested_assessment_tamper(field, value):
    phases = [[Fraction(1, 4) + Fraction((i % 3) - 1, 1000) for i in range(9)]
              for _ in range(4)]
    snapshot = assess_factory_model(_observations(phases, slot="a"))
    object.__setattr__(snapshot.assessment, field, value)
    with pytest.raises(ValueError):
        validate_verified_factory_assessment(snapshot)


def test_verified_snapshot_rejects_current_observation_tamper():
    phases = [[Fraction(1, 4) + Fraction((i % 3) - 1, 1000) for i in range(9)]
              for _ in range(4)]
    snapshot = assess_factory_model(_observations(phases, slot="a"))
    object.__setattr__(snapshot.observations[0], "phase", Fraction(1, 3))
    with pytest.raises(ValueError):
        validate_verified_factory_assessment(snapshot)


def test_verification_authority_retains_no_snapshots_or_corpus_objects():
    references = []
    for iteration in range(40):
        observations = _observations([[Fraction(1, 4)] * 9] * 4, slot=f"s{iteration}")
        snapshot = assess_factory_model(observations)
        references.append(weakref.ref(snapshot))
    del snapshot, observations
    gc.collect()
    assert all(reference() is None for reference in references)
    import rxoptimizer.rhythm_multimodal as module
    assert module.assess_factory_model.__closure__ is None
    assert module.validate_verified_factory_assessment.__closure__ is None
    assert "hmac" not in module.__dict__ and "secrets" not in module.__dict__