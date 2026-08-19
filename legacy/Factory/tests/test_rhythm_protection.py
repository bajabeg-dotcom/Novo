from dataclasses import FrozenInstanceError, replace

import pytest

from rxoptimizer.rhythm_protection import (
    ADAPTER_RUN_STATUSES,
    BUILD_TERMINAL_STATUSES,
    ENUM_DOMAINS,
    ENUM_DOMAIN_SHA256,
    FINAL_AUTHORIZATION_STATUSES,
    MODALITY_STATUSES,
    MODEL_CONTRACT_SPECS,
    PER_RULE_PROTECTION_STATUSES,
    PROTECTION_CONTRACT_VERSION,
    REQUIRED_PROTECTION_RULES,
    SUBJECT_UNIVERSE_QUERY_VERSION_BY_RULE,
    SUFFICIENCY_CONTRACT_VERSION,
    AdapterContract,
    AdapterRegistry,
    AdapterRun,
    AuthorizationDecision,
    CoveragePartition,
    ProtectionGroup,
    ProtectionGroupMembership,
    ProtectionEvidenceRegistry,
    ValidatedSubjectRegistrySnapshot,
    aggregate_protection_status,
    canonical_partition_result_sha256,
    enum_domain_sha256,
    final_analysis_authorization,
    canonical_protection_config,
    protection_config_sha256,
    sparse_rule_status,
    validate_enum_domains,
)
from rxoptimizer.rhythm_subject_registry import (
    StableSubject,
    StableSubjectEdge,
    StableSubjectRegistry,
    canonical_json,
)
from hashlib import sha256


D = {
    "source": "1" * 64,
    "universe": "3" * 64,
    "input": "4" * 64,
    "dependency": "5" * 64,
    "result": "6" * 64,
}
SCOPE_SUBJECT = StableSubject("TRACK_CHANNEL", D["source"], {"track_index": 0, "channel": 1})
NOTE_A = StableSubject("NOTE", D["source"], {"note_id": "A"})
NOTE_B = StableSubject("NOTE", D["source"], {"note_id": "B"})
NOTE_C = StableSubject("NOTE", D["source"], {"note_id": "C"})
NOTE_D = StableSubject("NOTE", D["source"], {"note_id": "D"})
OTHER_NOTE = StableSubject("NOTE", "b" * 64, {"note_id": "OTHER"})
OTHER_SCOPE = StableSubject("TRACK_CHANNEL", "f" * 64, {"track_index": 0, "channel": 1})
V2_SCOPE = StableSubject(
    "TRACK_CHANNEL", D["source"], {"track_index": 0, "channel": 1}, "X10_STABLE_SUBJECT_V2")
D["scope"] = SCOPE_SUBJECT.subject_id
SUBJECT_A = NOTE_A.subject_id
SUBJECT_B = NOTE_B.subject_id
SUBJECT_C = NOTE_C.subject_id
SUBJECT_D = NOTE_D.subject_id
POPULATION = (SUBJECT_A, SUBJECT_B, SUBJECT_C, SUBJECT_D)
SUBJECT_CATALOG = {
    item.subject_id: item for item in (
        SCOPE_SUBJECT, NOTE_A, NOTE_B, NOTE_C, NOTE_D, OTHER_NOTE, OTHER_SCOPE, V2_SCOPE)
}


def population_digest(*subject_ids):
    return sha256(canonical_json(sorted(subject_ids)).encode("ascii")).hexdigest()


def edge_semantic_record(edge):
    return {
        "contract_version": edge.contract_version,
        "edge_type": edge.edge_type,
        "source_sha256": edge.source_sha256,
        "parent_subject_id": edge.parent_subject_id,
        "child_subject_id": edge.child_subject_id,
        "edge_id": edge.edge_id,
    }


def evidence_registry(sources):
    registry = StableSubjectRegistry()
    for subject_id, source_sha256 in sources.items():
        subject = SUBJECT_CATALOG[subject_id]
        assert subject.source_sha256 == source_sha256
        registry.add_subject(subject)
    return ProtectionEvidenceRegistry(registry)


def contract(rule="GUITAR_MODE", adapter_class="CORE_REQUIRED"):
    return AdapterContract(rule, "1", adapter_class, "PREDICATE_V1")


def run(status="COMPLETE", adapter=None, universe_count=None, applicable=2, scanned=2, resolved=2,
        protected=0, ambiguous=0, universe_sha256=None, applicable_sha256=None,
        result_sha256=None):
    adapter = adapter or contract()
    universe_count = applicable if universe_count is None else universe_count
    universe_ids = POPULATION[:universe_count]
    applicable_ids = POPULATION[:applicable]
    scanned_ids = POPULATION[:scanned]
    resolved_ids = POPULATION[:resolved]
    provisional = AdapterRun(D["source"], adapter, "TRACK_CHANNEL", D["scope"], "UNIVERSE_V1",
        universe_count, universe_sha256 or population_digest(*universe_ids), applicable,
        applicable_sha256 or population_digest(*applicable_ids), scanned,
        population_digest(*scanned_ids), resolved, population_digest(*resolved_ids),
        protected, ambiguous, D["input"], D["dependency"],
        result_sha256 or "0" * 64, status)
    if result_sha256 is None and status in {"COMPLETE", "PARTIAL"}:
        partition_status = "COMPLETE" if applicable == scanned == resolved else "PARTIAL"
        default_partition = CoveragePartition(provisional.run_id, "partition-0", D["scope"],
            universe_count, applicable, scanned, resolved, provisional.subject_universe_sha256,
            provisional.applicable_universe_sha256, provisional.scanned_universe_sha256,
            provisional.resolved_universe_sha256, D["result"], partition_status)
        provisional = replace(provisional, result_sha256=canonical_partition_result_sha256(
            provisional, [default_partition]))
    return provisional


def commit_run(value, partitions):
    return replace(value, result_sha256=canonical_partition_result_sha256(value, partitions))


def add_run(evidence, value, *, universe_ids=None, applicable_ids=None, scanned_ids=None,
        resolved_ids=None):
    universe_ids = list(universe_ids or POPULATION[:value.subject_universe_count])
    applicable_ids = list(applicable_ids or POPULATION[:value.applicable_count])
    scanned_ids = list(scanned_ids or POPULATION[:value.scanned_count])
    resolved_ids = list(resolved_ids or POPULATION[:value.resolved_count])
    return evidence.add_run(value, subject_universe_ids=universe_ids,
        applicable_subject_ids=applicable_ids, scanned_subject_ids=scanned_ids,
        resolved_subject_ids=resolved_ids)


def partition(status="COMPLETE", universe=2, applicable=2, scanned=2, resolved=2,
        run_id="7" * 64, partition_key="partition-0", universe_ids=None,
        applicable_ids=None, scanned_ids=None, resolved_ids=None, result_sha256=None):
    universe_ids = list(universe_ids or POPULATION[:universe])
    applicable_ids = list(applicable_ids or POPULATION[:applicable])
    scanned_ids = list(scanned_ids or POPULATION[:scanned])
    resolved_ids = list(resolved_ids or POPULATION[:resolved])
    return CoveragePartition(run_id, partition_key, D["scope"], universe, applicable, scanned,
        resolved, population_digest(*universe_ids), population_digest(*applicable_ids),
        population_digest(*scanned_ids), population_digest(*resolved_ids),
        result_sha256 or D["result"], status)


def add_partition(evidence, value, *, universe_ids=None, applicable_ids=None,
        scanned_ids=None, resolved_ids=None):
    universe_ids = list(universe_ids or POPULATION[:value.subject_universe_count])
    applicable_ids = list(applicable_ids or POPULATION[:value.applicable_count])
    scanned_ids = list(scanned_ids or POPULATION[:value.scanned_count])
    resolved_ids = list(resolved_ids or POPULATION[:value.resolved_count])
    return evidence.add_partition(value, subject_universe_ids=universe_ids,
        applicable_subject_ids=applicable_ids, scanned_subject_ids=scanned_ids,
        resolved_subject_ids=resolved_ids)


def allowed(**overrides):
    values = dict(source_quality_status="NORMAL", context_eligibility_status="EXACT_CONTEXT_MATCH",
        core_scan_complete=True, protection_status="PROTECTION_CLEAR",
        factory_model_status="FACTORY_SUFFICIENT", modality_status="ASSESSED_UNIMODAL",
        reference_relationship_status="REFERENCE_SUPPORT")
    values.update(overrides)
    return final_analysis_authorization(**values)


def test_enum_domains_are_closed_ordered_hashed_and_reject_duplicate_unknown_unreachable():
    assert validate_enum_domains(ENUM_DOMAINS, ENUM_DOMAIN_SHA256) == ENUM_DOMAIN_SHA256
    assert enum_domain_sha256(ENUM_DOMAINS) == ENUM_DOMAIN_SHA256
    duplicate = dict(ENUM_DOMAINS); duplicate["adapter_run"] = ADAPTER_RUN_STATUSES + ("COMPLETE",)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_enum_domains(duplicate)
    unknown = dict(ENUM_DOMAINS); unknown["adapter_run"] = ADAPTER_RUN_STATUSES + ("MAYBE",)
    with pytest.raises(ValueError, match="unknown"):
        validate_enum_domains(unknown)
    unreachable = dict(ENUM_DOMAINS); unreachable["adapter_run"] = ADAPTER_RUN_STATUSES[:-1]
    with pytest.raises(ValueError, match="unreachable"):
        validate_enum_domains(unreachable)
    reordered = dict(ENUM_DOMAINS); reordered["adapter_run"] = tuple(reversed(ADAPTER_RUN_STATUSES))
    with pytest.raises(ValueError, match="order"):
        validate_enum_domains(reordered)
    with pytest.raises(ValueError, match="mismatch"):
        validate_enum_domains(ENUM_DOMAINS, "0" * 64)
    invalid_type = dict(ENUM_DOMAINS); invalid_type["adapter_run"] = ADAPTER_RUN_STATUSES[:-1] + (1,)
    with pytest.raises(ValueError, match="string tokens"):
        validate_enum_domains(invalid_type)


def test_config_hash_is_deterministic_and_contract_fields_cannot_be_overridden():
    assert protection_config_sha256({"capability": "ANALYZE_ONLY"}) == protection_config_sha256()
    with pytest.raises(ValueError, match="cannot be overridden"):
        protection_config_sha256({"capability": "WRITE"})
    with pytest.raises(ValueError, match="Unknown canonical config field"):
        protection_config_sha256({"custom": "value"})


def test_adapter_registry_is_idempotent_conflict_checked_and_complete():
    registry = AdapterRegistry()
    for rule in REQUIRED_PROTECTION_RULES:
        kind = "POST_MODEL_REQUIRED" if rule == "FACTORY_REFERENCE_CONFLICT" else (
            "EXTERNAL_OPTIONAL_FAIL_CLOSED" if rule == "RX_DNC" else "CORE_REQUIRED")
        item = contract(rule, kind)
        registry.register(item); registry.register(item)
    registry.validate_complete()
    with pytest.raises(ValueError, match="predicate version mismatch"):
        registry.register(AdapterContract("GUITAR_MODE", "1", "CORE_REQUIRED", "PREDICATE_V2"))
    incomplete = AdapterRegistry(); incomplete.register(contract())
    with pytest.raises(ValueError, match="incomplete"):
        incomplete.validate_complete()
    with pytest.raises(ValueError, match="canonical config hash mismatch"):
        replace(contract(), config_sha256="f" * 64)


def test_adapter_class_and_run_status_semantics_fail_closed():
    with pytest.raises(ValueError, match="canonical adapter class"):
        contract("RX_DNC", "CORE_REQUIRED")
    with pytest.raises(ValueError, match="canonical adapter class"):
        contract("CROSS_BAR", "EXTERNAL_OPTIONAL_FAIL_CLOSED")
    with pytest.raises(ValueError, match="post-model"):
        run("DEFERRED_POST_MODEL")
    with pytest.raises(ValueError, match="external optional"):
        run("DEPENDENCY_UNAVAILABLE")
    external = contract("RX_DNC", "EXTERNAL_OPTIONAL_FAIL_CLOSED")
    assert run("DEPENDENCY_UNAVAILABLE", external, applicable=2, scanned=0, resolved=0).run_status == "DEPENDENCY_UNAVAILABLE"
    post = contract("FACTORY_REFERENCE_CONFLICT", "POST_MODEL_REQUIRED")
    assert run("DEFERRED_POST_MODEL", post, applicable=2, scanned=0, resolved=0).run_status == "DEFERRED_POST_MODEL"


def test_canonical_config_locks_subject_adapter_predicate_query_and_sufficiency_contracts():
    config = canonical_protection_config()
    assert config["contract_version"] == PROTECTION_CONTRACT_VERSION
    assert config["subject_contract_version"]
    assert config["sufficiency_contract_version"] == SUFFICIENCY_CONTRACT_VERSION
    assert set(config["adapter_versions_by_rule"]) == set(REQUIRED_PROTECTION_RULES)
    assert set(config["applicability_predicate_versions_by_rule"]) == set(REQUIRED_PROTECTION_RULES)
    assert set(config["subject_universe_query_versions_by_rule"]) == set(REQUIRED_PROTECTION_RULES)
    for name, spec in MODEL_CONTRACT_SPECS.items():
        assert config[f"{name}_contract_version"] == spec["version"]
        assert len(config[f"{name}_contract_sha256"]) == 64
    assert config["decimal_semantic_precision"] == 50
    assert config["decimal_semantic_rounding"] == "ROUND_HALF_EVEN"
    assert config["decimal_interval_precision"] == 60
    assert config["decimal_interval_rounding"] == ["ROUND_FLOOR", "ROUND_CEILING"]
    with pytest.raises(ValueError, match="adapter version mismatch"):
        AdapterContract("GUITAR_MODE", "2", "CORE_REQUIRED", "PREDICATE_V1")
    with pytest.raises(ValueError, match="predicate version mismatch"):
        AdapterContract("GUITAR_MODE", "1", "CORE_REQUIRED", "PREDICATE_V2")
    with pytest.raises(ValueError, match="contract version mismatch"):
        replace(contract(), contract_version="X10_PROTECTION_V2")
    with pytest.raises(ValueError, match="canonical config hash mismatch"):
        replace(contract(), config_sha256="f" * 64)
    with pytest.raises(ValueError, match="query version mismatch"):
        replace(run(), subject_universe_query_version="UNIVERSE_V2")
    with pytest.raises(ValueError, match="registry canonical config hash mismatch"):
        AdapterRegistry("f" * 64)


def test_failed_runs_are_hard_fail_records_not_sparse_evidence():
    evidence = evidence_registry({D["scope"]: D["source"]})
    failed = run("FAILED_RUNTIME", applicable=2, scanned=0, resolved=0)
    with pytest.raises(ValueError, match="build-hard-fail"):
        evidence.add_run(failed, subject_universe_ids=[], applicable_subject_ids=[],
            scanned_subject_ids=[], resolved_subject_ids=[])


def test_registry_requires_validated_metadata_and_scope_type_version_match():
    with pytest.raises(TypeError, match="validated stable subject registry snapshot"):
        ProtectionEvidenceRegistry({D["scope"]: D["source"]})
    note_scope = evidence_registry({SUBJECT_A: D["source"], SUBJECT_B: D["source"]})
    with pytest.raises(ValueError, match="scope subject type"):
        add_run(note_scope, replace(run(), scope_subject_id=SUBJECT_A))
    wrong_version = evidence_registry({
        V2_SCOPE.subject_id: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"]})
    with pytest.raises(ValueError, match="scope subject contract version mismatch"):
        add_run(wrong_version, replace(run(), scope_subject_id=V2_SCOPE.subject_id))


def test_subject_snapshot_factory_recomputes_ids_digest_and_is_frozen():
    registry = StableSubjectRegistry()
    registry.extend_subjects([SCOPE_SUBJECT, NOTE_A, NOTE_B])
    records = [subject.semantic_record for subject in registry.subjects]
    snapshot = ValidatedSubjectRegistrySnapshot.from_semantic_records(
        records, registry.semantic_digest())
    assert snapshot.semantic_sha256 == registry.semantic_digest()
    assert set(snapshot.entries) == {D["scope"], SUBJECT_A, SUBJECT_B}
    with pytest.raises(TypeError):
        snapshot.entries[SUBJECT_A] = snapshot.entries[SUBJECT_B]
    with pytest.raises(AttributeError, match="immutable"):
        snapshot.semantic_sha256 = "f" * 64
    assert isinstance(ProtectionEvidenceRegistry(snapshot), ProtectionEvidenceRegistry)
    with pytest.raises(TypeError, match="must be created"):
        ValidatedSubjectRegistrySnapshot({}, registry.semantic_digest())


def test_subject_snapshot_rejects_relabeled_tampered_records_ids_and_digest():
    registry = StableSubjectRegistry()
    registry.extend_subjects([SCOPE_SUBJECT, NOTE_A])
    records = [dict(subject.semantic_record) for subject in registry.subjects]
    note_index = next(index for index, record in enumerate(records)
                      if record["subject_id"] == SUBJECT_A)

    relabeled = [dict(record) for record in records]
    relabeled[note_index]["subject_type"] = "TRACK_CHANNEL"
    with pytest.raises(ValueError, match="ID mismatch"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            relabeled, registry.semantic_digest())

    natural_key = [dict(record) for record in records]
    natural_key[note_index]["natural_key"] = {"note_id": "FORGED"}
    with pytest.raises(ValueError, match="ID mismatch"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            natural_key, registry.semantic_digest())

    forged_id = [dict(record) for record in records]
    forged_id[note_index]["subject_id"] = "f" * 64
    with pytest.raises(ValueError, match="ID mismatch"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            forged_id, registry.semantic_digest())

    with pytest.raises(ValueError, match="registry semantic digest mismatch"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(records, "f" * 64)


def test_subject_snapshot_has_no_direct_validated_metadata_factory_bypass():
    assert not hasattr(ValidatedSubjectRegistrySnapshot, "_from_validated")
    with pytest.raises(AttributeError):
        ValidatedSubjectRegistrySnapshot._from_validated({}, "f" * 64)
    with pytest.raises(TypeError, match="must be created"):
        ValidatedSubjectRegistrySnapshot({}, "f" * 64, _token=object())


def test_semantic_record_snapshot_rebuild_is_dependency_and_input_order_independent():
    registry = StableSubjectRegistry()
    note_one = registry.add_subject(StableSubject("NOTE", D["source"], {"note_id": "order-1"}))
    note_two = registry.add_subject(StableSubject("NOTE", D["source"], {"note_id": "order-2"}))
    phrase = registry.add_subject(StableSubject("PHRASE", D["source"], {
        "track_index": 0,
        "channel": 1,
        "meter_segment_id": "e" * 64,
        "ordered_note_ids": [note_one.subject_id, note_two.subject_id],
    }))
    records = [subject.semantic_record for subject in registry.subjects]
    phrase_first = [phrase.semantic_record, note_two.semantic_record, note_one.semantic_record]
    expected = registry.semantic_digest()
    snapshots = [
        ValidatedSubjectRegistrySnapshot.from_semantic_records(records, expected),
        ValidatedSubjectRegistrySnapshot.from_semantic_records(reversed(records), expected),
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            sorted(records, key=lambda item: item["subject_id"]), expected),
        ValidatedSubjectRegistrySnapshot.from_semantic_records(phrase_first, expected),
    ]
    assert {snapshot.semantic_sha256 for snapshot in snapshots} == {expected}
    assert all(set(snapshot.entries) == {note_one.subject_id, note_two.subject_id, phrase.subject_id}
               for snapshot in snapshots)

    orphan_registry = StableSubjectRegistry()
    orphan_note = StableSubject("NOTE", D["source"], {"note_id": "missing"})
    orphan_phrase = StableSubject("PHRASE", D["source"], {
        "track_index": 0,
        "channel": 1,
        "meter_segment_id": "e" * 64,
        "ordered_note_ids": [orphan_note.subject_id],
    })
    with pytest.raises(ValueError, match="unresolved or cyclic"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            [orphan_phrase.semantic_record], orphan_registry.semantic_digest())


def test_semantic_snapshot_reconstructs_full_edge_registry_independent_of_order():
    registry = StableSubjectRegistry()
    registry.extend_subjects([SCOPE_SUBJECT, NOTE_A, NOTE_B])
    first = registry.add_edge(StableSubjectEdge(
        "TRACK_CHANNEL_CONTAINS_NOTE", D["scope"], SUBJECT_A, D["source"]))
    second = registry.add_edge(StableSubjectEdge(
        "TRACK_CHANNEL_CONTAINS_NOTE", D["scope"], SUBJECT_B, D["source"]))
    subject_records = [subject.semantic_record for subject in registry.subjects]
    edges = [edge_semantic_record(first), edge_semantic_record(second)]
    expected = registry.semantic_digest()
    direct = ValidatedSubjectRegistrySnapshot.from_registry(registry)
    rebuilt = ValidatedSubjectRegistrySnapshot.from_semantic_records(
        reversed(subject_records), expected, reversed(edges))
    sorted_rebuild = ValidatedSubjectRegistrySnapshot.from_semantic_records(
        sorted(subject_records, key=lambda item: item["subject_id"]), expected,
        sorted(edges, key=lambda item: item["edge_id"]))
    assert direct.semantic_sha256 == rebuilt.semantic_sha256 == sorted_rebuild.semantic_sha256 == expected
    assert dict(direct.entries) == dict(rebuilt.entries) == dict(sorted_rebuild.entries)


def test_semantic_snapshot_rejects_edge_tamper_endpoint_relation_version_source_and_cycle():
    registry = StableSubjectRegistry()
    registry.extend_subjects([SCOPE_SUBJECT, NOTE_A])
    valid = StableSubjectEdge(
        "TRACK_CHANNEL_CONTAINS_NOTE", D["scope"], SUBJECT_A, D["source"])
    registry.add_edge(valid)
    subjects = [subject.semantic_record for subject in registry.subjects]
    expected = registry.semantic_digest()

    tampered = edge_semantic_record(valid)
    tampered["edge_id"] = "f" * 64
    with pytest.raises(ValueError, match="Edge semantic record ID mismatch"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(subjects, expected, [tampered])

    missing_endpoint = StableSubjectEdge(
        "TRACK_CHANNEL_CONTAINS_NOTE", "e" * 64, SUBJECT_A, D["source"])
    with pytest.raises(ValueError, match="endpoints"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            subjects, expected, [edge_semantic_record(missing_endpoint)])

    wrong_relation = StableSubjectEdge(
        "NOTE_HAS_ON_EVENT", D["scope"], SUBJECT_A, D["source"])
    with pytest.raises(ValueError, match="requires"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            subjects, expected, [edge_semantic_record(wrong_relation)])

    wrong_version = StableSubjectEdge(
        "TRACK_CHANNEL_CONTAINS_NOTE", D["scope"], SUBJECT_A, D["source"],
        contract_version="X10_STABLE_SUBJECT_V2")
    with pytest.raises(ValueError, match="contract versions"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            subjects, expected, [edge_semantic_record(wrong_version)])

    wrong_source = StableSubjectEdge(
        "TRACK_CHANNEL_CONTAINS_NOTE", D["scope"], SUBJECT_A, "b" * 64)
    with pytest.raises(ValueError, match="Cross-source"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(
            subjects, expected, [edge_semantic_record(wrong_source)])

    cycle_payload = ["X10_STABLE_SUBJECT_V1", "TRACK_CHANNEL_CONTAINS_NOTE", D["source"],
                     D["scope"], D["scope"]]
    cycle = {
        "contract_version": "X10_STABLE_SUBJECT_V1",
        "edge_type": "TRACK_CHANNEL_CONTAINS_NOTE",
        "source_sha256": D["source"],
        "parent_subject_id": D["scope"],
        "child_subject_id": D["scope"],
        "edge_id": sha256(canonical_json(cycle_payload).encode("ascii")).hexdigest(),
    }
    with pytest.raises(ValueError, match="self-cycle"):
        ValidatedSubjectRegistrySnapshot.from_semantic_records(subjects, expected, [cycle])


def test_complete_partial_and_not_applicable_count_contracts():
    assert run().run_status == "COMPLETE"
    assert run("PARTIAL", applicable=3, scanned=1, resolved=1).run_status == "PARTIAL"
    assert run("PARTIAL", applicable=3, scanned=3, resolved=2).run_status == "PARTIAL"
    with pytest.raises(ValueError, match="COMPLETE"):
        run("COMPLETE", applicable=3, scanned=2, resolved=2)
    with pytest.raises(ValueError, match="PARTIAL"):
        run("PARTIAL", applicable=2, scanned=2, resolved=2)
    with pytest.raises(ValueError, match="NOT_APPLICABLE"):
        run("NOT_APPLICABLE", applicable=1, scanned=0, resolved=0)


def test_sparse_absence_is_clear_only_inside_matching_complete_coverage():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"], SUBJECT_C: D["source"]}
    evidence = evidence_registry(sources)
    complete_run = add_run(evidence, run())
    complete = partition(run_id=complete_run.run_id)
    add_partition(evidence, complete, universe_ids=[SUBJECT_B, SUBJECT_A],
        applicable_ids=[SUBJECT_B, SUBJECT_A], scanned_ids=[SUBJECT_A, SUBJECT_B],
        resolved_ids=[SUBJECT_A, SUBJECT_B])
    assert sparse_rule_status(evidence, SUBJECT_A, "GUITAR_MODE") == "CLEAR"
    assert sparse_rule_status(evidence, SUBJECT_C, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"

    partial_evidence = evidence_registry(sources)
    partial_run = add_run(partial_evidence, run("PARTIAL", applicable=2, scanned=1, resolved=1))
    partial = partition("PARTIAL", applicable=2, scanned=1, resolved=1, run_id=partial_run.run_id)
    add_partition(partial_evidence, partial, applicable_ids=[SUBJECT_A, SUBJECT_B],
        scanned_ids=[SUBJECT_A], resolved_ids=[SUBJECT_A])
    assert sparse_rule_status(partial_evidence, SUBJECT_A, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"
    assert sparse_rule_status(partial_evidence, SUBJECT_B, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"


def test_multi_partition_coverage_requires_exact_disjoint_aggregate_before_clear():
    sources = {D["scope"]: D["source"], **{item: D["source"] for item in POPULATION}}
    evidence = evidence_registry(sources)
    value = run(universe_count=3, applicable=3, scanned=3, resolved=3, result_sha256="0" * 64)
    first_blueprint = partition(run_id=value.run_id, partition_key="bars-0-1", universe=2,
        applicable=2, scanned=2, resolved=2, universe_ids=[SUBJECT_A, SUBJECT_B],
        applicable_ids=[SUBJECT_A, SUBJECT_B], scanned_ids=[SUBJECT_A, SUBJECT_B],
        resolved_ids=[SUBJECT_A, SUBJECT_B], result_sha256="7" * 64)
    second_blueprint = partition(run_id=value.run_id, partition_key="bars-2", universe=1,
        applicable=1, scanned=1, resolved=1, universe_ids=[SUBJECT_C],
        applicable_ids=[SUBJECT_C], scanned_ids=[SUBJECT_C], resolved_ids=[SUBJECT_C],
        result_sha256="8" * 64)
    parent = add_run(evidence, commit_run(value, [first_blueprint, second_blueprint]))
    first = replace(first_blueprint, run_id=parent.run_id)
    add_partition(evidence, first, universe_ids=[SUBJECT_A, SUBJECT_B],
        applicable_ids=[SUBJECT_A, SUBJECT_B], scanned_ids=[SUBJECT_A, SUBJECT_B],
        resolved_ids=[SUBJECT_A, SUBJECT_B])
    assert sparse_rule_status(evidence, SUBJECT_A, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"
    second = replace(second_blueprint, run_id=parent.run_id)
    add_partition(evidence, second, universe_ids=[SUBJECT_C], applicable_ids=[SUBJECT_C],
        scanned_ids=[SUBJECT_C], resolved_ids=[SUBJECT_C])
    assert sparse_rule_status(evidence, SUBJECT_A, "GUITAR_MODE") == "CLEAR"
    assert sparse_rule_status(evidence, SUBJECT_C, "GUITAR_MODE") == "CLEAR"
    assert sparse_rule_status(evidence, SUBJECT_D, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"


def test_inside_universe_nonapplicable_is_distinct_from_outside_universe_unproven():
    sources = {D["scope"]: D["source"], **{item: D["source"] for item in POPULATION}}
    evidence = evidence_registry(sources)
    value = run(universe_count=3, applicable=2, scanned=2, resolved=2, result_sha256="0" * 64)
    applicable_blueprint = partition(run_id=value.run_id, partition_key="applicable", universe=2,
        applicable=2, scanned=2, resolved=2, universe_ids=[SUBJECT_A, SUBJECT_B],
        applicable_ids=[SUBJECT_A, SUBJECT_B], scanned_ids=[SUBJECT_A, SUBJECT_B],
        resolved_ids=[SUBJECT_A, SUBJECT_B])
    nonapplicable_blueprint = partition(run_id=value.run_id, partition_key="nonapplicable", universe=1,
        applicable=0, scanned=0, resolved=0, universe_ids=[SUBJECT_C],
        applicable_ids=[], scanned_ids=[], resolved_ids=[], result_sha256="9" * 64)
    parent = add_run(evidence, commit_run(value, [applicable_blueprint, nonapplicable_blueprint]))
    applicable = replace(applicable_blueprint, run_id=parent.run_id)
    nonapplicable = replace(nonapplicable_blueprint, run_id=parent.run_id)
    add_partition(evidence, applicable)
    add_partition(evidence, nonapplicable, universe_ids=[SUBJECT_C], applicable_ids=[],
        scanned_ids=[], resolved_ids=[])
    assert sparse_rule_status(evidence, SUBJECT_C, "GUITAR_MODE") == "NOT_APPLICABLE"
    assert sparse_rule_status(evidence, SUBJECT_D, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"


def test_parent_partition_result_digest_is_canonical_ordered_and_tamper_evident():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"]}
    value = run(result_sha256="0" * 64)
    left = partition(run_id=value.run_id, partition_key="left", universe=1, applicable=1,
        scanned=1, resolved=1, universe_ids=[SUBJECT_A], applicable_ids=[SUBJECT_A],
        scanned_ids=[SUBJECT_A], resolved_ids=[SUBJECT_A], result_sha256="7" * 64)
    right = partition(run_id=value.run_id, partition_key="right", universe=1, applicable=1,
        scanned=1, resolved=1, universe_ids=[SUBJECT_B], applicable_ids=[SUBJECT_B],
        scanned_ids=[SUBJECT_B], resolved_ids=[SUBJECT_B], result_sha256="8" * 64)
    assert canonical_partition_result_sha256(value, [left, right]) == (
        canonical_partition_result_sha256(value, [right, left]))
    parent_value = commit_run(value, [left, right])
    evidence = evidence_registry(sources)
    parent = add_run(evidence, parent_value)
    add_partition(evidence, replace(left, run_id=parent.run_id), universe_ids=[SUBJECT_A],
        applicable_ids=[SUBJECT_A], scanned_ids=[SUBJECT_A], resolved_ids=[SUBJECT_A])
    tampered = replace(right, run_id=parent.run_id, result_sha256="9" * 64)
    add_partition(evidence, tampered, universe_ids=[SUBJECT_B], applicable_ids=[SUBJECT_B],
        scanned_ids=[SUBJECT_B], resolved_ids=[SUBJECT_B])
    with pytest.raises(ValueError, match="canonical partition result digest mismatch"):
        sparse_rule_status(evidence, SUBJECT_A, "GUITAR_MODE")


def test_complete_run_nonclear_counts_require_distinct_membership_evidence():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"]}
    evidence = evidence_registry(sources)
    parent = add_run(evidence, run(protected=2))
    add_partition(evidence, partition(run_id=parent.run_id))
    group = evidence.add_group(ProtectionGroup(
        parent.run_id, D["source"], "GUITAR_MODE", "1", {"bar": 2}, "DETECTED", "8" * 64))
    evidence.add_membership(ProtectionGroupMembership(group.group_id, SUBJECT_A))
    with pytest.raises(ValueError, match="counts do not match distinct"):
        sparse_rule_status(evidence, SUBJECT_B, "GUITAR_MODE")

    missing = evidence_registry(sources)
    missing_parent = add_run(missing, run(protected=1))
    add_partition(missing, partition(run_id=missing_parent.run_id))
    missing.add_group(ProtectionGroup(
        missing_parent.run_id, D["source"], "GUITAR_MODE", "1", {"bar": 3},
        "DETECTED", "9" * 64))
    with pytest.raises(ValueError, match="missing applicable subject evidence"):
        sparse_rule_status(missing, SUBJECT_A, "GUITAR_MODE")


@pytest.mark.parametrize(("status", "protected", "ambiguous"), [
    ("DETECTED", 1, 0),
    ("AMBIGUOUS", 0, 1),
])
def test_partial_run_declared_nonclear_requires_and_accepts_scanned_membership_evidence(
        status, protected, ambiguous):
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"]}
    missing = evidence_registry(sources)
    missing_parent = add_run(missing, run("PARTIAL", applicable=2, scanned=1, resolved=1,
        protected=protected, ambiguous=ambiguous))
    add_partition(missing, partition("PARTIAL", run_id=missing_parent.run_id,
        applicable=2, scanned=1, resolved=1))
    with pytest.raises(ValueError, match="counts do not match distinct"):
        sparse_rule_status(missing, SUBJECT_A, "GUITAR_MODE")

    valid = evidence_registry(sources)
    valid_parent = add_run(valid, run("PARTIAL", applicable=2, scanned=1, resolved=1,
        protected=protected, ambiguous=ambiguous))
    add_partition(valid, partition("PARTIAL", run_id=valid_parent.run_id,
        applicable=2, scanned=1, resolved=1))
    group = valid.add_group(ProtectionGroup(
        valid_parent.run_id, D["source"], "GUITAR_MODE", "1", {"status": status},
        status, "8" * 64))
    valid.add_membership(ProtectionGroupMembership(group.group_id, SUBJECT_A))
    assert sparse_rule_status(valid, SUBJECT_A, "GUITAR_MODE") == status
    assert sparse_rule_status(valid, SUBJECT_B, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"


def test_partial_explicit_finding_cannot_target_unscanned_applicable_subject():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"]}
    evidence = evidence_registry(sources)
    parent = add_run(evidence, run("PARTIAL", applicable=2, scanned=1, resolved=1, protected=1))
    group = evidence.add_group(ProtectionGroup(
        parent.run_id, D["source"], "GUITAR_MODE", "1", {"bar": 2}, "DETECTED", "8" * 64))
    with pytest.raises(ValueError, match="outside parent run scanned"):
        evidence.add_membership(ProtectionGroupMembership(group.group_id, SUBJECT_B))


def test_multiple_group_memberships_preserve_provenance_and_conservative_status():
    detected = ProtectionGroup("7" * 64, D["source"], "CROSS_BAR", "1", {"bar": 2}, "DETECTED", "8" * 64)
    ambiguous = ProtectionGroup("6" * 64, D["source"], "SECTION_TRANSITION", "1", {"bar": 2}, "AMBIGUOUS", "9" * 64)
    one = ProtectionGroupMembership(detected.group_id, D["scope"])
    two = ProtectionGroupMembership(ambiguous.group_id, D["scope"])
    assert one.membership_id != two.membership_id
    with pytest.raises(ValueError, match="non-clear"):
        ProtectionGroup("7" * 64, D["source"], "CROSS_BAR", "1", {"bar": 2}, "CLEAR", "8" * 64)


def test_sparse_evidence_registry_enforces_references_sources_and_run_natural_keys():
    evidence = evidence_registry({D["scope"]: D["source"], SUBJECT_A: D["source"],
        SUBJECT_B: D["source"], OTHER_NOTE.subject_id: OTHER_NOTE.source_sha256})
    adapter_run = add_run(evidence, run(protected=1, ambiguous=1))
    part = partition(run_id=adapter_run.run_id)
    add_partition(evidence, part); add_partition(evidence, part)
    group = evidence.add_group(ProtectionGroup(
        adapter_run.run_id, D["source"], "GUITAR_MODE", "1", {"bar": 2}, "DETECTED", "8" * 64))
    membership = ProtectionGroupMembership(group.group_id, SUBJECT_A)
    evidence.add_membership(membership); evidence.add_membership(membership)
    # A second group for the same subject is explicitly legal and preserves provenance.
    second = evidence.add_group(ProtectionGroup(
        adapter_run.run_id, D["source"], "GUITAR_MODE", "1", {"bar": 3}, "AMBIGUOUS", "9" * 64))
    evidence.add_membership(ProtectionGroupMembership(second.group_id, SUBJECT_A))
    assert len(evidence.memberships) == 2
    assert sparse_rule_status(evidence, SUBJECT_A, "GUITAR_MODE") == "DETECTED"
    with pytest.raises(ValueError, match="registered group"):
        evidence.add_membership(ProtectionGroupMembership("d" * 64, SUBJECT_A))
    with pytest.raises(ValueError, match="Cross-source"):
        evidence.add_membership(ProtectionGroupMembership(group.group_id, OTHER_NOTE.subject_id))
    with pytest.raises(ValueError, match="registered adapter run"):
        add_partition(evidence, partition(run_id="d" * 64, partition_key="p1",
            universe=0, applicable=0, scanned=0, resolved=0))
    contradictory = replace(adapter_run, result_sha256="e" * 64)
    with pytest.raises(ValueError, match="natural key"):
        add_run(evidence, contradictory)


def test_group_membership_must_belong_to_parent_run_applicable_population():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"],
        SUBJECT_B: D["source"], SUBJECT_C: D["source"]}
    evidence = evidence_registry(sources)
    parent = add_run(evidence, run(universe_count=3, applicable=2, scanned=2, resolved=2,
        protected=1))
    group = evidence.add_group(ProtectionGroup(
        parent.run_id, D["source"], "GUITAR_MODE", "1", {"bar": 2}, "DETECTED", "8" * 64))
    evidence.add_membership(ProtectionGroupMembership(group.group_id, SUBJECT_A))
    with pytest.raises(ValueError, match="outside parent run applicable"):
        evidence.add_membership(ProtectionGroupMembership(group.group_id, SUBJECT_C))


@pytest.mark.parametrize(("rule_status", "aggregate"), [
    ("DETECTED", "PROTECTED_DETECTED"),
    ("AMBIGUOUS", "PROTECTION_UNRESOLVED"),
    ("EVIDENCE_UNJOINABLE", "PROTECTION_UNRESOLVED"),
    ("DEPENDENCY_GAP", "EXTERNAL_EVIDENCE_GAP"),
    ("PARTIAL_UNRESOLVED", "PROTECTION_SCAN_PARTIAL"),
    ("DEFERRED", "PROTECTION_DEFERRED"),
])
def test_protection_aggregate_precedence(rule_status, aggregate):
    statuses = {rule: "CLEAR" for rule in REQUIRED_PROTECTION_RULES}
    statuses[REQUIRED_PROTECTION_RULES[-1]] = rule_status
    assert aggregate_protection_status(statuses) == aggregate


def test_protection_aggregate_requires_all_nine_clear_or_not_applicable():
    statuses = {rule: ("NOT_APPLICABLE" if index % 2 else "CLEAR")
                for index, rule in enumerate(REQUIRED_PROTECTION_RULES)}
    assert aggregate_protection_status(statuses) == "PROTECTION_CLEAR"
    missing = dict(statuses); missing.pop(REQUIRED_PROTECTION_RULES[-1])
    with pytest.raises(ValueError, match="missing"):
        aggregate_protection_status(missing)
    unknown = dict(statuses); unknown["UNKNOWN_RULE"] = "CLEAR"
    with pytest.raises(ValueError, match="unknown"):
        aggregate_protection_status(unknown)
    with pytest.raises(TypeError, match="rule-keyed"):
        aggregate_protection_status(["CLEAR"] * 9)
    duplicate_pairs = list(statuses.items()) + [(REQUIRED_PROTECTION_RULES[0], "CLEAR")]
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate_protection_status(duplicate_pairs)


def test_run_scope_partition_and_group_semantic_linkage_are_strict():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"]}
    missing_scope = evidence_registry({SUBJECT_A: D["source"]})
    with pytest.raises(ValueError, match="scope subject is not registered"):
        add_run(missing_scope, run())
    wrong_source = evidence_registry({OTHER_SCOPE.subject_id: OTHER_SCOPE.source_sha256})
    with pytest.raises(ValueError, match="another source"):
        add_run(wrong_source, replace(run(), scope_subject_id=OTHER_SCOPE.subject_id))

    evidence = evidence_registry(sources)
    parent = add_run(evidence, run())
    valid = partition(run_id=parent.run_id)
    add_partition(evidence, valid)
    conflicting = replace(valid, result_sha256="e" * 64)
    with pytest.raises(ValueError, match="natural key"):
        add_partition(evidence, conflicting)
    overlap = partition(run_id=parent.run_id, partition_key="other", universe=1,
        applicable=1, scanned=1, resolved=1, universe_ids=[SUBJECT_A],
        applicable_ids=[SUBJECT_A], scanned_ids=[SUBJECT_A], resolved_ids=[SUBJECT_A])
    with pytest.raises(ValueError, match="disjoint"):
        add_partition(evidence, overlap, universe_ids=[SUBJECT_A], applicable_ids=[SUBJECT_A],
            scanned_ids=[SUBJECT_A], resolved_ids=[SUBJECT_A])

    wrong_rule = ProtectionGroup(parent.run_id, D["source"], "CROSS_BAR", "1",
        {"bar": 2}, "DETECTED", "8" * 64)
    with pytest.raises(ValueError, match="contract does not match"):
        evidence.add_group(wrong_rule)
    missing_run = ProtectionGroup("f" * 64, D["source"], "GUITAR_MODE", "1",
        {"bar": 2}, "DETECTED", "8" * 64)
    with pytest.raises(ValueError, match="registered adapter run"):
        evidence.add_group(missing_run)


def test_run_universe_and_applicable_population_have_separate_proven_digests():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"],
        SUBJECT_C: D["source"]}
    evidence = evidence_registry(sources)
    value = run(universe_count=3, universe_sha256=population_digest(SUBJECT_A, SUBJECT_B, SUBJECT_C),
        applicable=2, applicable_sha256=population_digest(SUBJECT_A, SUBJECT_B))
    stored = evidence.add_run(value, subject_universe_ids=[SUBJECT_C, SUBJECT_A, SUBJECT_B],
        applicable_subject_ids=[SUBJECT_B, SUBJECT_A],
        scanned_subject_ids=[SUBJECT_B, SUBJECT_A],
        resolved_subject_ids=[SUBJECT_B, SUBJECT_A])
    assert stored.subject_universe_sha256 != stored.applicable_universe_sha256
    bad = evidence_registry(sources)
    with pytest.raises(ValueError, match="applicable universe digest mismatch"):
        bad.add_run(replace(value, applicable_universe_sha256="e" * 64),
            subject_universe_ids=[SUBJECT_A, SUBJECT_B, SUBJECT_C],
            applicable_subject_ids=[SUBJECT_A, SUBJECT_B],
            scanned_subject_ids=[SUBJECT_A, SUBJECT_B],
            resolved_subject_ids=[SUBJECT_A, SUBJECT_B])
    with pytest.raises(ValueError, match="inside subject universe"):
        evidence_registry(sources).add_run(value,
            subject_universe_ids=[SUBJECT_A, SUBJECT_C, D["scope"]],
            applicable_subject_ids=[SUBJECT_A, SUBJECT_B],
            scanned_subject_ids=[SUBJECT_A, SUBJECT_B],
            resolved_subject_ids=[SUBJECT_A, SUBJECT_B])


@pytest.mark.parametrize("rule", [
    "GUITAR_MODE", "ORNAMENT_TRILL_GRACE", "DRUM_FLAM_ROLL_GHOST", "CROSS_BAR",
    "SECTION_TRANSITION", "TEMPO_METER_BOUNDARY", "LOCAL_REPEATED_PATTERN",
])
def test_seven_structural_rules_are_canonically_core_required(rule):
    assert contract(rule, "CORE_REQUIRED").adapter_class == "CORE_REQUIRED"
    with pytest.raises(ValueError, match="canonical adapter class"):
        contract(rule, "POST_MODEL_REQUIRED")


@pytest.mark.parametrize(("overrides", "expected"), [
    ({"source_quality_status": "INVALID"}, "EXCLUDED_INVALID_SOURCE"),
    ({"source_quality_status": "RARE"}, "PRESERVE_SOURCE_QUALITY"),
    ({"context_eligibility_status": "CONTEXT_CONFLICT"}, "PRESERVE_CONTEXT_UNPROVEN"),
    ({"core_scan_complete": False}, "PRESERVE_CORE_SCAN_PARTIAL"),
    ({"protection_status": "PROTECTED_DETECTED"}, "PROTECTED_DETECTED"),
    ({"protection_status": "PROTECTION_UNRESOLVED"}, "PRESERVE_PROTECTION_UNRESOLVED"),
    ({"protection_status": "EXTERNAL_EVIDENCE_GAP"}, "PRESERVE_EXTERNAL_EVIDENCE_GAP"),
    ({"protection_status": "PROTECTION_SCAN_PARTIAL"}, "PRESERVE_PROTECTION_SCAN_PARTIAL"),
    ({"protection_status": "PROTECTION_DEFERRED"}, "PRESERVE_PROTECTION_DEFERRED"),
    ({"protection_status": "PROTECTION_CONTRACT_INCOMPLETE"}, "PRESERVE_PROTECTION_CONTRACT_INCOMPLETE"),
    ({"factory_model_status": "FACTORY_INSUFFICIENT"}, "INSUFFICIENT_FACTORY_EVIDENCE"),
    ({"modality_status": "DEGENERATE_EXACT_REFERENCE"}, "ZERO_VARIANCE_REVIEW"),
    ({"modality_status": "INSUFFICIENT_MODAL_EVIDENCE"}, "PRESERVE_MODALITY_INSUFFICIENT"),
    ({"modality_status": "UNSTABLE_BIC_NEAR_TIE"}, "PRESERVE_MODALITY_UNSTABLE"),
    ({"modality_status": "DEFERRED"}, "PRESERVE_MODALITY_DEFERRED"),
    ({"modality_status": "ASSESSED_MULTIMODAL"}, "PRESERVE_MULTIMODAL_CONTEXT"),
    ({"reference_relationship_status": "POST_MODEL_PARTIAL"}, "PRESERVE_REFERENCE_GATE_PARTIAL"),
    ({"reference_relationship_status": "DEFERRED_FACTORY_MODEL_UNSTABLE"}, "PRESERVE_REFERENCE_GATE_DEFERRED"),
    ({"reference_relationship_status": "POTENTIAL_CONTRADICTION"}, "REVIEW_FACTORY_REFERENCE_CONFLICT"),
    ({"reference_relationship_status": "FACTORY_SUPPORT_UNINFORMATIVE"}, "PRESERVE_FACTORY_SUPPORT_UNINFORMATIVE"),
    ({}, "ANALYZE_ALLOWED"),
])
def test_final_authorization_status_reachability(overrides, expected):
    decision = allowed(**overrides)
    assert decision.authorization_status == expected
    assert decision.analysis_allowed is (expected == "ANALYZE_ALLOWED")
    assert not decision.proposal_allowed and not decision.repair_allowed
    assert decision.mutation_capability == "NONE" and decision.capability == "ANALYZE_ONLY"


def test_all_unstable_and_numerical_modality_tokens_reach_unstable_preserve():
    for status in MODALITY_STATUSES:
        if status.startswith("UNSTABLE_") or status.startswith("NUMERICAL_"):
            assert allowed(modality_status=status).authorization_status == "PRESERVE_MODALITY_UNSTABLE"


def test_every_final_authorization_status_is_reachable_and_unknown_input_hard_fails():
    reached = {allowed().authorization_status}
    cases = [
        dict(source_quality_status="INVALID"), dict(source_quality_status="OUTLIER"),
        dict(context_eligibility_status="CONTEXT_UNPROVEN"), dict(core_scan_complete=False),
        *[dict(protection_status=status) for status in (
            "PROTECTED_DETECTED", "PROTECTION_UNRESOLVED", "EXTERNAL_EVIDENCE_GAP",
            "PROTECTION_SCAN_PARTIAL", "PROTECTION_DEFERRED", "PROTECTION_CONTRACT_INCOMPLETE")],
        dict(factory_model_status="FACTORY_UNAVAILABLE"), dict(modality_status="DEGENERATE_EXACT_REFERENCE"),
        dict(modality_status="INSUFFICIENT_MODAL_EVIDENCE"), dict(modality_status="UNSTABLE_MODAL_STRUCTURE"),
        dict(modality_status="DEFERRED"), dict(modality_status="ASSESSED_MULTIMODAL"),
        dict(reference_relationship_status="POST_MODEL_PARTIAL"),
        dict(reference_relationship_status="DEFERRED_FACTORY_MODEL_UNSTABLE"),
        dict(reference_relationship_status="POTENTIAL_CONTRADICTION"),
        dict(reference_relationship_status="FACTORY_SUPPORT_UNINFORMATIVE"),
    ]
    reached.update(allowed(**case).authorization_status for case in cases)
    assert reached == set(FINAL_AUTHORIZATION_STATUSES)
    with pytest.raises(ValueError, match="Unknown source"):
        allowed(source_quality_status="MAYBE")
    with pytest.raises(ValueError, match="bool"):
        allowed(core_scan_complete=1)
    with pytest.raises(ValueError, match="exactly match"):
        AuthorizationDecision("ANALYZE_ALLOWED", False)


def test_authorization_destructive_fields_and_capability_are_immutable_constants():
    decision = allowed()
    with pytest.raises(FrozenInstanceError):
        decision.capability = "REPAIR_CAPABLE"
    with pytest.raises(FrozenInstanceError):
        decision.repair_allowed = True
    with pytest.raises(ValueError, match="init=False"):
        replace(decision, capability="REPAIR_CAPABLE")
    with pytest.raises(ValueError, match="init=False"):
        replace(decision, proposal_allowed=True)


def test_declared_enum_appendix_tokens_remain_reachable_in_domains():
    assert set(BUILD_TERMINAL_STATUSES) == set(ENUM_DOMAINS["build_terminal"])
    assert set(PER_RULE_PROTECTION_STATUSES) == set(ENUM_DOMAINS["per_rule_protection"])
    assert set(FINAL_AUTHORIZATION_STATUSES) == set(ENUM_DOMAINS["final_authorization"])