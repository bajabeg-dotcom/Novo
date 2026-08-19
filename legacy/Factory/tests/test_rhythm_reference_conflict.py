from dataclasses import replace
from fractions import Fraction

import pytest

from rxoptimizer.rhythm_multimodal import (
    Component, ModalityAssessment, PhaseObservation, VerifiedFactoryAssessment,
    assess_factory_model, assess_multimodal, model_config_sha256,
    validate_verified_factory_assessment,
)
from rxoptimizer.rhythm_reference_conflict import (
    ReferenceRelationship,
    assess_reference_relationship,
    build_factory_support_arcs,
    shortest_support_arc,
)


def _sha(index):
    return f"{index:064x}"


def _obs(index, phase, source=1, resolution=Fraction(1, 1000)):
    return PhaseObservation(_sha(source), f"bar-{index}", Fraction(phase), resolution,
                            observation_id=f"{1000 + source * 100 + index:064x}")


def _ref(index, phase, source=10, resolution=Fraction(1, 1000)):
    return PhaseObservation(_sha(source), f"bar-{index}", Fraction(phase), resolution,
                            observation_id=f"{5000 + source * 100 + index:064x}",
                            authority="REFERENCE")


def _component(observations):
    return Component(0, observations[0].phase, __import__("decimal").Decimal("0.01"),
                     __import__("decimal").Decimal(1),
                     tuple(item.observation_id for item in observations),
                     tuple(sorted({item.source_sha256 for item in observations})),
                     tuple(sorted({(item.source_sha256, item.bar_id) for item in observations})),
                     __import__("decimal").Decimal("0.25"))


def test_shortest_arc_uses_largest_gap_and_wraps():
    observations = [_obs(1, Fraction(99, 100)), _obs(2, Fraction(1, 100)),
                    _obs(3, Fraction(2, 100))]
    arc = shortest_support_arc(0, observations)
    assert arc.start == Fraction(99, 100)
    assert arc.end == Fraction(1, 50)
    assert arc.contains_expanded(Fraction(0), Fraction(1, 1000))
    assert not arc.contains_expanded(Fraction(1, 2), Fraction(1, 1000))


def test_largest_gap_tie_uses_smallest_canonical_start():
    arc = shortest_support_arc(0, [_obs(1, 0), _obs(2, Fraction(1, 2))])
    assert arc.start == 0
    assert arc.end == Fraction(1, 2)


def test_full_circle_is_uninformative():
    factory = [_obs(i, 0, source=(i % 4) + 1, resolution=Fraction(1, 2))
               for i in range(12)]
    result = assess_reference_relationship(assess_factory_model(factory), [])
    assert result.status == "FACTORY_SUPPORT_UNINFORMATIVE"


def test_no_reference_and_unstable_factory_statuses():
    factory = [_obs(i, Fraction(i, 100), source=(i % 4) + 1) for i in range(12)]
    component = _component(factory)
    assert assess_reference_relationship(assess_factory_model(factory), []).status == \
        "NO_REFERENCE_EVIDENCE"
    unstable = assess_factory_model(factory[:4])
    assert assess_reference_relationship(unstable, []).status == \
        "DEFERRED_FACTORY_MODEL_UNSTABLE"


def test_reference_support_is_resolution_aware():
    factory = [_obs(i, Fraction(1, 4) + Fraction(i % 3, 100), source=(i % 4) + 1)
               for i in range(12)]
    component = _component(factory)
    reference = [_ref(i, Fraction(27, 100), source=10 + (i % 4), resolution=Fraction(1, 100))
                 for i in range(12)]
    result = assess_reference_relationship(assess_factory_model(factory), reference)
    assert result.status == "REFERENCE_SUPPORT"


def test_sufficient_outside_reference_is_potential_contradiction():
    factory = [_obs(i, Fraction(1, 4) + Fraction(i % 3, 1000), source=(i % 4) + 1)
               for i in range(12)]
    component = _component(factory)
    reference = [_ref(i, Fraction(3, 4), source=10 + (i % 4)) for i in range(12)]
    result = assess_reference_relationship(assess_factory_model(factory), reference)
    assert result.status == "POTENTIAL_CONTRADICTION"
    assert result.outside_observation_ids
    assert not result.repair_allowed


def test_insufficient_reference_never_claims_contradiction():
    factory = [_obs(i, Fraction(1, 4), source=(i % 4) + 1) for i in range(12)]
    component = _component(factory)
    result = assess_reference_relationship(
        assess_factory_model(factory), [_ref(30, Fraction(3, 4), source=20)])
    assert result.status == "INSUFFICIENT_REFERENCE_EVIDENCE"


def test_factory_component_membership_must_resolve_exactly():
    factory = [_obs(i, Fraction(1, 4), source=(i % 4) + 1) for i in range(12)]
    component = replace(_component(factory), hard_observation_ids=("f" * 64,))
    with pytest.raises(ValueError):
        build_factory_support_arcs([component], factory)


def test_partial_post_model_is_fail_closed():
    result = assess_reference_relationship(
        assess_factory_model([]), [], post_model_complete=False)
    assert result.status == "POST_MODEL_PARTIAL"
    assert result.mutation_capability == "NONE"


def test_unknown_modality_and_factory_as_reference_are_rejected():
    with pytest.raises(ValueError):
        ModalityAssessment("UNKNOWN", None, (), (), __import__("decimal").Decimal(0), model_config_sha256())
    factory = [_obs(i, Fraction(1, 4), source=(i % 4) + 1) for i in range(12)]
    with pytest.raises(ValueError):
        assess_reference_relationship(
            assess_factory_model(factory), factory)
    with pytest.raises(ValueError):
        ReferenceRelationship("NO_REFERENCE_EVIDENCE", (), (), (), "0" * 64)


def test_reference_requires_nonforgeable_verified_factory_snapshot():
    factory = [_obs(i, Fraction(1, 4), source=(i % 4) + 1) for i in range(12)]
    with pytest.raises(TypeError):
        VerifiedFactoryAssessment(None, (), "0" * 64)
    with pytest.raises(TypeError):
        assess_reference_relationship(assess_multimodal(factory), [])
    import rxoptimizer.rhythm_multimodal as module
    assert not hasattr(module, "_VERIFIED_FACTORY_TOKEN")
    assert not hasattr(module, "_issue_verified_factory")
    assert "hmac" not in module.__dict__ and "secrets" not in module.__dict__
    forged = object.__new__(VerifiedFactoryAssessment)
    with pytest.raises((ValueError, AttributeError)):
        validate_verified_factory_assessment(forged)
    with pytest.raises((ValueError, AttributeError)):
        assess_reference_relationship(forged, [])


def test_self_consistent_looking_forged_snapshot_fails_full_reproduction():
    import rxoptimizer.rhythm_multimodal as module
    factory = [_obs(i, Fraction(1, 4), source=(i % 4) + 1) for i in range(12)]
    original = assess_multimodal(factory)
    forged_assessment = replace(original, status="ASSESSED_MULTIMODAL", selected_k=1)
    ordered = tuple(sorted(factory, key=lambda o: (
        o.source_sha256, o.bar_id, o.event_slot_key, o.phase, o.observation_id)))
    payload = module._verified_snapshot_payload(forged_assessment, ordered)
    forged = VerifiedFactoryAssessment(
        forged_assessment, ordered,
        __import__("hashlib").sha256(module.canonical_json(payload).encode("ascii")).hexdigest())
    with pytest.raises(ValueError, match="reproduction"):
        validate_verified_factory_assessment(forged)
    with pytest.raises(ValueError):
        assess_reference_relationship(forged, [])


def test_context_and_slot_parity_are_required():
    factory = [_obs(i, Fraction(1, 4), source=(i % 4) + 1) for i in range(12)]
    snapshot = assess_factory_model(factory)
    wrong_context = [PhaseObservation(
        _sha(10 + (i % 4)), f"bar-{i}", Fraction(1, 4), Fraction(1, 1000),
        "slot-0", "other-context", authority="REFERENCE") for i in range(12)]
    with pytest.raises(ValueError):
        assess_reference_relationship(snapshot, wrong_context)


def test_degenerate_exact_point_support_is_compared_not_deferred():
    factory = [_obs(i, Fraction(1, 4), source=(i % 4) + 1, resolution=Fraction(1, 1000))
               for i in range(12)]
    supported = [_ref(i, Fraction(251, 1000), source=10 + (i % 4),
                      resolution=Fraction(1, 1000)) for i in range(12)]
    outside = [_ref(i, Fraction(3, 4), source=20 + (i % 4)) for i in range(12)]
    assert assess_reference_relationship(
        assess_factory_model(factory), supported).status == \
        "REFERENCE_SUPPORT"
    assert assess_reference_relationship(
        assess_factory_model(factory), outside).status == \
        "POTENTIAL_CONTRADICTION"