import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from rxoptimizer.rhythm_context_models import V2_SCHEMA, semantic_digest_v2
from rxoptimizer.rhythm_proposal_readiness import (
    ACCEPTANCE_STATUS, AUTHORIZATION_MAP, AUTHORIZATION_STATUSES,
    build_withheld_readiness_database,
)
from rxoptimizer.rhythm_protection_adapters import (
    SIX_SONG_FORBIDDEN_SHA256S, SourceLineageRecord, TrustedSourceLineageSnapshot,
    lineage_inventory_sha256, trusted_source_guard_policy, trusted_source_lineage_snapshot,
)
from rxoptimizer.rhythm_subject_registry import StableSubject, canonical_json


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fixture(tmp_path: Path, statuses=AUTHORIZATION_STATUSES):
    raw = b"frozen schema-v2 source bytes"
    source_sha = hashlib.sha256(raw).hexdigest()
    path = tmp_path / "accepted-v2.sqlite3"
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(V2_SCHEMA)
    config_sha = "1" * 64
    lineage_record = SourceLineageRecord(source_sha, "FACTORY_RAW", ())
    lineage = trusted_source_lineage_snapshot((lineage_record,))
    lineage_sha = lineage.semantic_sha256
    db.executemany("INSERT INTO build_info VALUES(?,?)", (
        ("schema_version", _json(2)), ("builder_version", _json("fixture")),
        ("capability", _json("ANALYZE_ONLY")), ("mutation_capability", _json("NONE")),
        ("build_config_sha256", _json(config_sha)), ("config", _json({"fixture": True}))))
    contract = {"builder_version": "fixture", "schema_version": 2,
                "build_config_sha256": config_sha, "protection_config_sha256": "3" * 64,
                "model_config_sha256": "4" * 64, "reference_config_sha256": "5" * 64,
                "negative_manifest_sha256": "6" * 64}
    db.execute("INSERT INTO build_contract_v2 VALUES(?,?,?,?,?,?,?,?,?)", (
        "7" * 64, "fixture", 2, config_sha, "3" * 64, "4" * 64, "5" * 64,
        "6" * 64, _json(contract)))
    source_semantic = {"context_snapshots": [{"manifest": {
        "source_class": "FACTORY_RAW", "lineage_sha256": lineage_sha}}],
        "unproven_partition": None}
    db.execute("INSERT INTO source_context_v2 VALUES(?,?,?,?,?,?,?,?,?)", (
        source_sha, "factory", "FACTORY_RAW", "Factory/test.mid", "NORMAL", _json({}),
        lineage_sha, "8" * 64, _json(source_semantic)))
    for index, status in enumerate(statuses):
        natural = {"note_id": hashlib.sha256(f"note-{index}".encode()).hexdigest()}
        subject = StableSubject("NOTE", source_sha, natural)
        db.execute("INSERT INTO stable_subjects VALUES(?,?,?,?,?,?)", (
            subject.subject_id, source_sha, "NOTE", subject.contract_version,
            canonical_json(subject.natural_key), canonical_json(subject.semantic_record)))
        event_slot = hashlib.sha256(f"slot-{index}".encode()).hexdigest()
        context_status = "CONTEXT_UNPROVEN" if status == "PRESERVE_CONTEXT_UNPROVEN" else "EXACT_CONTEXT_MATCH"
        exact = None if context_status == "CONTEXT_UNPROVEN" else "ctx"
        db.execute("INSERT INTO context_eligibility VALUES(?,?,?,?,?,?,?,?)", (
            source_sha, subject.subject_id, natural["note_id"], exact, event_slot,
            context_status, "NORMAL", _json({"note_context": {}, "pre_model_rule_statuses": {}})))
        allowed = int(status == "ANALYZE_ALLOWED")
        semantic = {"per_rule_statuses": {}, "decision": {"authorization_status": status}, "context": {}}
        db.execute("INSERT INTO analysis_authorization VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
            source_sha, subject.subject_id, exact, event_slot, "PROTECTION_CLEAR",
            "FACTORY_SUFFICIENT", "ASSESSED_UNIMODAL", "REFERENCE_SUPPORT", status,
            allowed, "ANALYZE_ONLY", _json(semantic)))
    db.commit()
    digest = semantic_digest_v2(path)
    db.execute("INSERT INTO semantic_digest VALUES('SHA-256',2,?)", (digest,))
    db.commit(); db.close()
    manifest = {"source_class": "FACTORY_RAW", "lineage_sha256": lineage_sha}
    config = {"source_guard_policy": trusted_source_guard_policy(),
              "trusted_lineage_snapshot": lineage,
              "source_manifests_by_sha256": {source_sha: manifest}}
    return path, source_sha, raw, config


def _rows(path, query):
    db = sqlite3.connect(path)
    try: return db.execute(query).fetchall()
    finally: db.close()


def _replace_lineage(path, snapshot, manifest):
    db = sqlite3.connect(path)
    row = db.execute("SELECT source_semantic_json FROM source_context_v2").fetchone()
    payload = json.loads(row[0])
    for context in payload.get("context_snapshots", ()):
        context["manifest"] = manifest
    db.execute("UPDATE source_context_v2 SET lineage_sha256=?,source_semantic_json=?",
               (snapshot.semantic_sha256, _json(payload)))
    db.execute("DELETE FROM semantic_digest"); db.commit()
    digest = semantic_digest_v2(path)
    db.execute("INSERT INTO semantic_digest VALUES('SHA-256',2,?)", (digest,))
    db.commit(); db.close()


def test_all_21_authorizations_are_total_mapped_and_withheld(tmp_path):
    source, sha, raw, config = _fixture(tmp_path)
    output = tmp_path / "readiness.sqlite3"
    report = build_withheld_readiness_database(source, output, {sha: raw}, config)
    assert report["status"] == ACCEPTANCE_STATUS
    assert report["assessments"] == 21
    rows = _rows(output, "SELECT authorization_status,eligibility_status,anomaly_status,withheld_reasons_json,assessment_status FROM candidate_assessments ORDER BY authorization_status")
    assert {row[0] for row in rows} == set(AUTHORIZATION_STATUSES)
    assert all(row[1] == AUTHORIZATION_MAP[row[0]][0] for row in rows)
    assert all(row[2] == AUTHORIZATION_MAP[row[0]][1] for row in rows)
    assert all(json.loads(row[3]) and row[4] == "WITHHELD_ONLY" for row in rows)


def test_lifecycle_is_identity_only_and_fk_clean(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    output = tmp_path / "readiness.sqlite3"
    build_withheld_readiness_database(source, output, {sha: raw}, config)
    simulation = _rows(output, "SELECT before_byte_sha256,after_byte_sha256,before_semantic_digest,after_semantic_digest,before_subject_universe_digest,after_subject_universe_digest,changed_event_count,changed_field_count,output_artifact_status FROM no_change_simulations")[0]
    assert simulation[0] == simulation[1]
    assert simulation[2] == simulation[3]
    assert simulation[4] == simulation[5]
    assert simulation[6:] == (0, 0, "NOT_CREATED")
    assert _rows(output, "PRAGMA foreign_key_check") == []
    assert not list(tmp_path.glob("*.mid")) and not list(tmp_path.glob("*.midi"))


def test_authorization_locator_commits_composite_and_row_digest(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    output = tmp_path / "readiness.sqlite3"
    build_withheld_readiness_database(source, output, {sha: raw}, config)
    row = _rows(output, "SELECT source_sha256,stable_subject_id,event_slot_key,authorization_locator,authorization_row_digest,provenance_json FROM candidate_assessments")[0]
    provenance = json.loads(row[5])
    assert provenance["authorization_composite"] == [row[0], row[1], row[2]]
    assert provenance["authorization_locator"] == row[3]
    assert provenance["authorization_row_digest"] == row[4]


@pytest.mark.parametrize("payload", [
    {"target_tick": 1}, {"nested": {"delta_ticks": 2}},
    {"nested": [{"shadow_tick": 3}]}, {"candidate_value": 4},
])
def test_recursive_forbidden_key_guard(tmp_path, payload):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    config = dict(config); config.update(payload)
    with pytest.raises(ValueError, match="Forbidden withheld-only key"):
        build_withheld_readiness_database(source, tmp_path / "out.sqlite3", {sha: raw}, config)


def test_frozen_source_universe_and_bytes_are_mandatory(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    with pytest.raises(ValueError, match="universe"):
        build_withheld_readiness_database(source, tmp_path / "missing.sqlite3", {}, config)
    with pytest.raises(ValueError, match="SHA mismatch"):
        build_withheld_readiness_database(source, tmp_path / "wrong.sqlite3", {sha: raw + b"x"}, config)


def test_schema_v2_is_read_only_and_forged_digest_is_rejected(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    before = source.read_bytes()
    build_withheld_readiness_database(source, tmp_path / "ok.sqlite3", {sha: raw}, config)
    assert source.read_bytes() == before
    db = sqlite3.connect(source)
    db.execute("UPDATE semantic_digest SET digest=?", ("0" * 64,)); db.commit(); db.close()
    with pytest.raises(ValueError, match="semantic digest mismatch"):
        build_withheld_readiness_database(source, tmp_path / "bad.sqlite3", {sha: raw}, config)


def test_non_note_and_cross_source_authorization_fail_closed(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    db = sqlite3.connect(source)
    db.execute("UPDATE stable_subjects SET subject_type='BAR'")
    db.commit()
    db.execute("DELETE FROM semantic_digest")
    db.commit(); digest = semantic_digest_v2(source)
    db.execute("INSERT INTO semantic_digest VALUES('SHA-256',2,?)", (digest,)); db.commit(); db.close()
    with pytest.raises(ValueError, match="Stable subject identity mismatch|NOTE subject"):
        build_withheld_readiness_database(source, tmp_path / "out.sqlite3", {sha: raw}, config)


def test_deterministic_under_source_map_order_and_schema_has_no_action_fields(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED", "PROTECTED_DETECTED"))
    first = tmp_path / "first.sqlite3"; second = tmp_path / "second.sqlite3"
    one = build_withheld_readiness_database(source, first, dict([(sha, raw)]), config)
    two = build_withheld_readiness_database(source, second, dict(reversed([(sha, raw)])), config)
    assert one["semantic_digest"] == two["semantic_digest"]
    assert first.read_bytes() == second.read_bytes()
    sql = "\n".join(row[0] or "" for row in _rows(first, "SELECT sql FROM sqlite_master"))
    for forbidden in ("target_tick", "target_phase", "delta_ticks", "candidate_value", "shadow_tick",
                      "repair_budget", "modification_cost", "improvement_score"):
        assert forbidden not in sql.lower()


def test_atomic_failure_keeps_previous_output_byte_identical(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    output = tmp_path / "readiness.sqlite3"
    build_withheld_readiness_database(source, output, {sha: raw}, config)
    before = output.read_bytes()
    with pytest.raises(ValueError):
        build_withheld_readiness_database(source, output, {sha: raw + b"broken"}, config)
    assert output.read_bytes() == before
    assert not output.with_suffix(output.suffix + ".013a.tmp").exists()


def test_input_connection_rejects_write_attempt(tmp_path):
    source, _sha, _raw, _config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    uri = f"file:{source.resolve()}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    with pytest.raises(sqlite3.OperationalError):
        db.execute("DELETE FROM analysis_authorization")
    db.close()


def test_canonical_lineage_policy_snapshot_and_manifests_are_mandatory(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    for missing in ("source_guard_policy", "trusted_lineage_snapshot", "source_manifests_by_sha256"):
        broken = dict(config); broken.pop(missing)
        with pytest.raises(ValueError, match="required"):
            build_withheld_readiness_database(source, tmp_path / f"{missing}.sqlite3", {sha: raw}, broken)


def test_forged_consistent_stored_lineage_digest_is_rejected_against_frozen_snapshot(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    forged = "f" * 64
    db = sqlite3.connect(source)
    payload = json.loads(db.execute("SELECT source_semantic_json FROM source_context_v2").fetchone()[0])
    payload["context_snapshots"][0]["manifest"]["lineage_sha256"] = forged
    db.execute("UPDATE source_context_v2 SET lineage_sha256=?,source_semantic_json=?", (forged, _json(payload)))
    db.execute("DELETE FROM semantic_digest"); db.commit()
    digest = semantic_digest_v2(source)
    db.execute("INSERT INTO semantic_digest VALUES('SHA-256',2,?)", (digest,)); db.commit(); db.close()
    with pytest.raises(ValueError, match="trusted lineage digest mismatch"):
        build_withheld_readiness_database(source, tmp_path / "forged.sqlite3", {sha: raw}, config)


def test_optimizer_output_manifest_class_is_rejected(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    broken = dict(config)
    broken["source_manifests_by_sha256"] = {
        sha: {"source_class": "OPTIMIZER_OUTPUT",
              "lineage_sha256": config["trusted_lineage_snapshot"].semantic_sha256}}
    with pytest.raises(ValueError, match="manifest class"):
        build_withheld_readiness_database(source, tmp_path / "optimizer.sqlite3", {sha: raw}, broken)


def test_forbidden_six_song_sha_in_full_ancestor_closure_is_rejected(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    forbidden = SIX_SONG_FORBIDDEN_SHA256S[0]
    ancestor = SourceLineageRecord(forbidden, "FACTORY_RAW", ())
    root = SourceLineageRecord(sha, "FACTORY_RAW", (forbidden,))
    snapshot = trusted_source_lineage_snapshot((ancestor, root))
    manifest = {"source_class": "FACTORY_RAW", "lineage_sha256": snapshot.semantic_sha256}
    _replace_lineage(source, snapshot, manifest)
    broken = dict(config); broken["trusted_lineage_snapshot"] = snapshot
    broken["source_manifests_by_sha256"] = {sha: manifest}
    with pytest.raises(ValueError, match="Forbidden six-song SHA"):
        build_withheld_readiness_database(source, tmp_path / "six-song.sqlite3", {sha: raw}, broken)


def test_cross_authority_and_forbidden_class_lineage_cannot_be_canonicalized():
    parent_sha = hashlib.sha256(b"gold-parent").hexdigest()
    root_sha = hashlib.sha256(b"factory-root").hexdigest()
    gold = SourceLineageRecord(parent_sha, "GOLD_REFERENCE_RAW", ())
    factory = SourceLineageRecord(root_sha, "FACTORY_RAW", (parent_sha,))
    with pytest.raises(ValueError, match="Illegal lineage parent class"):
        trusted_source_lineage_snapshot((gold, factory))
    forbidden = SourceLineageRecord(parent_sha, "OPTIMIZER_OUTPUT", ())
    with pytest.raises(ValueError, match="Forbidden lineage class"):
        trusted_source_lineage_snapshot((forbidden,))


def test_missing_root_and_missing_ancestor_closure_are_rejected(tmp_path):
    source, sha, raw, config = _fixture(tmp_path, ("ANALYZE_ALLOWED",))
    unrelated = SourceLineageRecord(hashlib.sha256(b"unrelated").hexdigest(), "FACTORY_RAW", ())
    unrelated_snapshot = trusted_source_lineage_snapshot((unrelated,))
    broken = dict(config); broken["trusted_lineage_snapshot"] = unrelated_snapshot
    with pytest.raises(ValueError, match="root record is missing"):
        build_withheld_readiness_database(source, tmp_path / "missing-root.sqlite3", {sha: raw}, broken)
    missing_parent = hashlib.sha256(b"missing-parent").hexdigest()
    root = SourceLineageRecord(sha, "FACTORY_RAW", (missing_parent,))
    with pytest.raises(ValueError, match="parent is missing"):
        trusted_source_lineage_snapshot((root,))


def test_lineage_record_id_and_dag_digest_mismatch_are_rejected():
    record = SourceLineageRecord(hashlib.sha256(b"root").hexdigest(), "FACTORY_RAW", ())
    semantic = dict(record.semantic_record)
    bad_record = dict(semantic); bad_record["record_id"] = "0" * 64
    inventory = lineage_inventory_sha256((bad_record,))
    with pytest.raises(ValueError, match="record ID mismatch"):
        TrustedSourceLineageSnapshot.from_semantic_records((bad_record,), inventory)
    with pytest.raises(ValueError, match="inventory digest mismatch"):
        TrustedSourceLineageSnapshot.from_semantic_records((semantic,), "0" * 64)