"""Immutable withheld-only readiness materialization for X10 schema-v2.

This module deliberately has no MIDI parser, encoder, writer, exporter, target,
delta, overlay, or mutation path.  It turns every accepted schema-v2 analysis
authorization row into an auditable ``WITHHELD_ONLY`` assessment and proves
that the frozen inputs remain byte- and semantics-identical.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Mapping
from urllib.parse import quote

from .rhythm_context_models import V2_SEMANTIC_TABLES
from .rhythm_protection_adapters import (
    FORBIDDEN_SOURCE_KINDS, SIX_SONG_FORBIDDEN_SHA256S, SourceGuardPolicy,
    TrustedSourceLineageSnapshot, lineage_inventory_sha256, trusted_source_guard_policy,
)
from .rhythm_subject_registry import StableSubjectEdge, canonical_json, stable_subject_id


CONTRACT_VERSION = "X10_WITHHELD_READINESS_V1"
SCHEMA_VERSION = 1
BUILDER_VERSION = "WP_X10_013A_V1"
ACCEPTANCE_STATUS = "013A_WITHHELD_FOUNDATION_ACCEPTED"

AUTHORIZATION_STATUSES = (
    "EXCLUDED_INVALID_SOURCE", "PRESERVE_SOURCE_QUALITY", "PRESERVE_CONTEXT_UNPROVEN",
    "PRESERVE_CORE_SCAN_PARTIAL", "PROTECTED_DETECTED", "PRESERVE_PROTECTION_UNRESOLVED",
    "PRESERVE_EXTERNAL_EVIDENCE_GAP", "PRESERVE_PROTECTION_SCAN_PARTIAL",
    "PRESERVE_PROTECTION_DEFERRED", "PRESERVE_PROTECTION_CONTRACT_INCOMPLETE",
    "INSUFFICIENT_FACTORY_EVIDENCE", "ZERO_VARIANCE_REVIEW", "PRESERVE_MODALITY_INSUFFICIENT",
    "PRESERVE_MODALITY_UNSTABLE", "PRESERVE_MODALITY_DEFERRED", "PRESERVE_MULTIMODAL_CONTEXT",
    "PRESERVE_REFERENCE_GATE_PARTIAL", "PRESERVE_REFERENCE_GATE_DEFERRED",
    "REVIEW_FACTORY_REFERENCE_CONFLICT", "PRESERVE_FACTORY_SUPPORT_UNINFORMATIVE",
    "ANALYZE_ALLOWED",
)
ELIGIBILITY_STATUSES = (
    "INELIGIBLE_INVALID_SOURCE", "INELIGIBLE_SOURCE_QUALITY", "INELIGIBLE_CONTEXT_UNPROVEN",
    "INELIGIBLE_PROTECTION", "INELIGIBLE_FACTORY_EVIDENCE", "INELIGIBLE_MODALITY",
    "INELIGIBLE_REFERENCE_CONFLICT", "READINESS_INPUT_ANALYZE_ALLOWED",
)
ANOMALY_STATUSES = (
    "ANOMALY_NOT_EVALUATED_INELIGIBLE", "ANOMALY_NOT_PROVEN_CONTRACT_UNAVAILABLE",
)
WITHHELD_REASONS = (
    "SOURCE_NOT_USER_INPUT", "SCHEMA_V2_AUTHORIZATION_NOT_ALLOWED",
    "PROTECTION_OR_MUSICAL_INTENT_PRESERVED", "FACTORY_EVIDENCE_INSUFFICIENT_OR_UNSTABLE",
    "REFERENCE_CONFLICT_OR_DEFERRED", "CALIBRATION_ENVELOPE_UNAVAILABLE",
    "LOCAL_COMPARISON_MODEL_UNAVAILABLE", "ANOMALY_PROOF_CONTRACT_UNAVAILABLE",
    "EXACT_TARGET_CONTRACT_UNAVAILABLE", "CHANGE_SIMULATION_CONTRACT_UNAVAILABLE",
)

_BASE_REASONS = {
    "SOURCE_NOT_USER_INPUT", "CALIBRATION_ENVELOPE_UNAVAILABLE",
    "LOCAL_COMPARISON_MODEL_UNAVAILABLE", "ANOMALY_PROOF_CONTRACT_UNAVAILABLE",
    "EXACT_TARGET_CONTRACT_UNAVAILABLE", "CHANGE_SIMULATION_CONTRACT_UNAVAILABLE",
}
_FORBIDDEN_KEYS = {
    "target_phase", "target_tick", "derived_tick", "delta_ticks", "candidate_value",
    "shadow_tick", "repair_budget", "modification_cost", "improvement_score",
}
_NONSEMANTIC_KEYS = {
    "timestamp", "created_at", "updated_at", "build_timestamp", "generated_at", "absolute_path",
}


def _mapping(eligibility: str, *extra_reasons: str) -> tuple[str, str, tuple[str, ...]]:
    reasons = set(_BASE_REASONS)
    if eligibility != "READINESS_INPUT_ANALYZE_ALLOWED":
        reasons.add("SCHEMA_V2_AUTHORIZATION_NOT_ALLOWED")
    reasons.update(extra_reasons)
    anomaly = ("ANOMALY_NOT_PROVEN_CONTRACT_UNAVAILABLE" if
               eligibility == "READINESS_INPUT_ANALYZE_ALLOWED" else
               "ANOMALY_NOT_EVALUATED_INELIGIBLE")
    return eligibility, anomaly, tuple(sorted(reasons))


AUTHORIZATION_MAP = {
    "EXCLUDED_INVALID_SOURCE": _mapping("INELIGIBLE_INVALID_SOURCE"),
    "PRESERVE_SOURCE_QUALITY": _mapping("INELIGIBLE_SOURCE_QUALITY"),
    "PRESERVE_CONTEXT_UNPROVEN": _mapping("INELIGIBLE_CONTEXT_UNPROVEN"),
    "PRESERVE_CORE_SCAN_PARTIAL": _mapping("INELIGIBLE_CONTEXT_UNPROVEN"),
    "PROTECTED_DETECTED": _mapping("INELIGIBLE_PROTECTION", "PROTECTION_OR_MUSICAL_INTENT_PRESERVED"),
    "PRESERVE_PROTECTION_UNRESOLVED": _mapping("INELIGIBLE_PROTECTION", "PROTECTION_OR_MUSICAL_INTENT_PRESERVED"),
    "PRESERVE_EXTERNAL_EVIDENCE_GAP": _mapping("INELIGIBLE_PROTECTION", "PROTECTION_OR_MUSICAL_INTENT_PRESERVED"),
    "PRESERVE_PROTECTION_SCAN_PARTIAL": _mapping("INELIGIBLE_PROTECTION", "PROTECTION_OR_MUSICAL_INTENT_PRESERVED"),
    "PRESERVE_PROTECTION_DEFERRED": _mapping("INELIGIBLE_PROTECTION", "PROTECTION_OR_MUSICAL_INTENT_PRESERVED"),
    "PRESERVE_PROTECTION_CONTRACT_INCOMPLETE": _mapping("INELIGIBLE_PROTECTION", "PROTECTION_OR_MUSICAL_INTENT_PRESERVED"),
    "INSUFFICIENT_FACTORY_EVIDENCE": _mapping("INELIGIBLE_FACTORY_EVIDENCE", "FACTORY_EVIDENCE_INSUFFICIENT_OR_UNSTABLE"),
    "ZERO_VARIANCE_REVIEW": _mapping("INELIGIBLE_FACTORY_EVIDENCE", "FACTORY_EVIDENCE_INSUFFICIENT_OR_UNSTABLE"),
    "PRESERVE_MODALITY_INSUFFICIENT": _mapping("INELIGIBLE_MODALITY", "FACTORY_EVIDENCE_INSUFFICIENT_OR_UNSTABLE"),
    "PRESERVE_MODALITY_UNSTABLE": _mapping("INELIGIBLE_MODALITY", "FACTORY_EVIDENCE_INSUFFICIENT_OR_UNSTABLE"),
    "PRESERVE_MODALITY_DEFERRED": _mapping("INELIGIBLE_MODALITY", "FACTORY_EVIDENCE_INSUFFICIENT_OR_UNSTABLE"),
    "PRESERVE_MULTIMODAL_CONTEXT": _mapping("INELIGIBLE_MODALITY", "FACTORY_EVIDENCE_INSUFFICIENT_OR_UNSTABLE"),
    "PRESERVE_REFERENCE_GATE_PARTIAL": _mapping("INELIGIBLE_REFERENCE_CONFLICT", "REFERENCE_CONFLICT_OR_DEFERRED"),
    "PRESERVE_REFERENCE_GATE_DEFERRED": _mapping("INELIGIBLE_REFERENCE_CONFLICT", "REFERENCE_CONFLICT_OR_DEFERRED"),
    "REVIEW_FACTORY_REFERENCE_CONFLICT": _mapping("INELIGIBLE_REFERENCE_CONFLICT", "REFERENCE_CONFLICT_OR_DEFERRED"),
    "PRESERVE_FACTORY_SUPPORT_UNINFORMATIVE": _mapping("INELIGIBLE_REFERENCE_CONFLICT", "REFERENCE_CONFLICT_OR_DEFERRED"),
    "ANALYZE_ALLOWED": _mapping("READINESS_INPUT_ANALYZE_ALLOWED"),
}
if tuple(AUTHORIZATION_MAP) != AUTHORIZATION_STATUSES:
    raise RuntimeError("Authorization mapping is not exhaustive and ordered")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_json(value).encode("ascii")).hexdigest()


def _file_sha256(path: Path) -> str:
    value = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _readonly(path: Path) -> sqlite3.Connection:
    database = sqlite3.connect(f"file:{quote(str(path.resolve()))}?mode=ro", uri=True)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA query_only=ON")
    return database


def _reject_forbidden_keys(value: Any, location: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ValueError(f"Forbidden withheld-only key at {location}.{key}")
            _reject_forbidden_keys(nested, f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_forbidden_keys(nested, f"{location}[{index}]")


def _v2_semantic(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _v2_semantic(value[key]) for key in sorted(value)
                if str(key).lower() not in _NONSEMANTIC_KEYS and
                "timestamp" not in str(key).lower() and not str(key).lower().endswith("_at")}
    if isinstance(value, (list, tuple)):
        return [_v2_semantic(item) for item in value]
    if isinstance(value, str):
        path = value.replace("\\", "/")
        if path.startswith("/") or (len(path) > 2 and path[1:3] == ":/"):
            return f"ABSOLUTE_PATH/{Path(path).name}"
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise ValueError(f"Unsupported schema-v2 value: {type(value).__name__}")


def _schema_v2_semantic_digest(database: sqlite3.Connection) -> str:
    rows: list[str] = []
    for table in V2_SEMANTIC_TABLES:
        values = []
        for row in database.execute(f'SELECT * FROM "{table}"'):
            item = dict(row)
            for key, value in tuple(item.items()):
                if key.endswith("_json"):
                    item[key] = json.loads(value)
                    _reject_forbidden_keys(item[key], f"{table}.{key}")
            values.append(_v2_semantic(item))
        values.sort(key=canonical_json)
        rows.extend(canonical_json({"table": table, "row": value}) for value in values)
    return sha256("\n".join(rows).encode()).hexdigest()


def _subject_universe_digest(database: sqlite3.Connection) -> str:
    subjects = []
    for row in database.execute("SELECT * FROM stable_subjects ORDER BY subject_id"):
        item = dict(row); natural = json.loads(item["natural_key_json"])
        if stable_subject_id(item["subject_type"], item["source_sha256"], natural,
                             item["contract_version"]) != item["subject_id"]:
            raise ValueError("Stable subject identity mismatch")
        semantic = json.loads(item["semantic_json"])
        _reject_forbidden_keys(semantic, "stable_subjects.semantic_json")
        subjects.append({"subject_id": item["subject_id"], "source_sha256": item["source_sha256"],
                         "subject_type": item["subject_type"], "contract_version": item["contract_version"],
                         "natural_key": natural, "semantic": semantic})
    edges = []
    for row in database.execute("SELECT * FROM stable_subject_edges ORDER BY edge_id"):
        item = dict(row)
        expected = StableSubjectEdge(item["edge_type"], item["parent_subject_id"],
                                     item["child_subject_id"], item["source_sha256"],
                                     item["contract_version"]).edge_id
        if expected != item["edge_id"]:
            raise ValueError("Stable subject edge identity mismatch")
        semantic = json.loads(item["semantic_json"])
        _reject_forbidden_keys(semantic, "stable_subject_edges.semantic_json")
        edges.append({"edge_id": item["edge_id"], "source_sha256": item["source_sha256"],
                      "edge_type": item["edge_type"], "contract_version": item["contract_version"],
                      "parent_subject_id": item["parent_subject_id"],
                      "child_subject_id": item["child_subject_id"], "semantic": semantic})
    return _digest({"subjects": subjects, "edges": edges})


def _midi_artifacts(directory: Path) -> tuple[str, ...]:
    if not directory.exists():
        return ()
    return tuple(sorted(str(path.relative_to(directory)) for path in directory.rglob("*")
                        if path.is_file() and path.suffix.lower() in {".mid", ".midi"}))


def _canonical_lineage_inputs(config: dict[str, Any]) -> tuple[
        SourceGuardPolicy, TrustedSourceLineageSnapshot, dict[str, Mapping[str, Any]]]:
    policy = config.pop("source_guard_policy", None)
    snapshot = config.pop("trusted_lineage_snapshot", None)
    manifests = config.pop("source_manifests_by_sha256", None)
    if not isinstance(policy, SourceGuardPolicy):
        raise ValueError("Frozen canonical SourceGuardPolicy is required")
    if not isinstance(snapshot, TrustedSourceLineageSnapshot):
        raise ValueError("Frozen canonical TrustedSourceLineageSnapshot is required")
    if not isinstance(manifests, Mapping):
        raise ValueError("Frozen canonical source manifests are required")
    rebuilt_policy = SourceGuardPolicy(
        policy.policy_version, tuple(policy.forbidden_six_song_sha256s),
        policy.lineage_verifier_version, policy.lineage_matrix_version,
        policy.lineage_matrix_sha256, policy.policy_sha256)
    if rebuilt_policy != trusted_source_guard_policy():
        raise ValueError("Source guard policy is not the accepted canonical policy")
    semantic_records = tuple(dict(record.semantic_record) for record in snapshot.records)
    inventory = lineage_inventory_sha256(semantic_records)
    rebuilt_snapshot = TrustedSourceLineageSnapshot.from_semantic_records(semantic_records, inventory)
    if rebuilt_snapshot.semantic_sha256 != snapshot.semantic_sha256:
        raise ValueError("Trusted lineage DAG digest mismatch")
    frozen_manifests: dict[str, Mapping[str, Any]] = {}
    for source_sha, manifest in manifests.items():
        key = str(source_sha).lower()
        if not isinstance(manifest, Mapping):
            raise ValueError("Canonical source manifest must be a mapping")
        payload = json.loads(_json(dict(manifest)))
        _reject_forbidden_keys(payload, "source_manifest")
        frozen_manifests[key] = payload
    return rebuilt_policy, rebuilt_snapshot, frozen_manifests


def _source_manifest_digest(row: sqlite3.Row, policy: SourceGuardPolicy,
                            lineage: TrustedSourceLineageSnapshot,
                            frozen_manifest: Mapping[str, Any]) -> tuple[str, str]:
    source_sha = str(row["source_sha256"]).lower()
    source_kind = str(row["source_kind"])
    root = lineage.record_for(source_sha)
    if root is None:
        raise ValueError("Trusted lineage root record is missing")
    if root.lineage_class != source_kind:
        raise ValueError("Trusted lineage root class/source kind mismatch")
    closure = lineage.ancestor_closure(source_sha)
    if source_sha not in closure:
        raise ValueError("Trusted lineage root closure is incomplete")
    forbidden_sha = set(policy.forbidden_six_song_sha256s) | set(SIX_SONG_FORBIDDEN_SHA256S)
    if forbidden_sha.intersection(closure):
        raise ValueError("Forbidden six-song SHA in trusted lineage closure")
    for ancestor_sha in closure:
        ancestor = lineage.record_for(ancestor_sha)
        if ancestor is None:
            raise ValueError("Trusted lineage ancestor closure is incomplete")
        if ancestor.lineage_class in FORBIDDEN_SOURCE_KINDS:
            raise ValueError("Forbidden optimizer/repaired/source lineage class")
    manifest = dict(frozen_manifest)
    if manifest.get("source_class") != source_kind:
        raise ValueError("Source manifest class does not match trusted root class")
    if manifest.get("lineage_sha256") != lineage.semantic_sha256:
        raise ValueError("Source manifest lineage digest mismatch")
    stored_lineage = str(row["lineage_sha256"]).lower()
    if stored_lineage != lineage.semantic_sha256:
        raise ValueError("Schema-v2 trusted lineage digest mismatch")
    source_payload = json.loads(row["source_semantic_json"])
    _reject_forbidden_keys(source_payload, "source_context_v2.source_semantic_json")
    embedded: list[Mapping[str, Any]] = []
    for context in source_payload.get("context_snapshots", ()):
        if isinstance(context, Mapping) and isinstance(context.get("manifest"), Mapping):
            embedded.append(context["manifest"])
    if any(_json(dict(value)) != _json(manifest) for value in embedded):
        raise ValueError("Schema-v2 embedded source manifest mismatch")
    return _digest(manifest), lineage.semantic_sha256


SCHEMA = f"""
CREATE TABLE assessment_runs(
 run_id TEXT PRIMARY KEY,contract_version TEXT NOT NULL,schema_version INTEGER NOT NULL,
 builder_version TEXT NOT NULL,build_config_sha256 TEXT NOT NULL,schema_v2_semantic_digest TEXT NOT NULL,
 source_count INTEGER NOT NULL,subject_count INTEGER NOT NULL,terminal_status TEXT NOT NULL,
 capability TEXT NOT NULL,mutation_capability TEXT NOT NULL,semantic_json TEXT NOT NULL,
 CHECK(schema_version={SCHEMA_VERSION}),CHECK(terminal_status='COMPLETED_WITHHELD_ONLY'),
 CHECK(capability='ANALYZE_ONLY'),CHECK(mutation_capability='NONE'));
CREATE TABLE input_snapshots(
 input_snapshot_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,
 source_class TEXT NOT NULL,source_kind TEXT NOT NULL,member_path TEXT NOT NULL,
 trusted_lineage_digest TEXT NOT NULL,source_manifest_digest TEXT NOT NULL,
 schema_v2_semantic_digest TEXT NOT NULL,schema_v2_byte_sha256 TEXT NOT NULL,
 stable_subject_universe_digest TEXT NOT NULL,schema_v2_build_config_sha256 TEXT NOT NULL,
 build_config_sha256 TEXT NOT NULL,source_guard_policy_digest TEXT NOT NULL,
 protection_digest TEXT NOT NULL,model_digest TEXT NOT NULL,reference_digest TEXT NOT NULL,
 raw_byte_sha256 TEXT NOT NULL,before_semantic_digest TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(run_id,source_sha256),FOREIGN KEY(run_id) REFERENCES assessment_runs(run_id));
CREATE TABLE candidate_assessments(
 assessment_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,input_snapshot_id TEXT NOT NULL,
 stable_subject_id TEXT NOT NULL,subject_type TEXT NOT NULL,source_sha256 TEXT NOT NULL,
 exact_context_key TEXT,event_slot_key TEXT NOT NULL,authorization_locator TEXT NOT NULL,
 authorization_row_digest TEXT NOT NULL,authorization_status TEXT NOT NULL,
 eligibility_status TEXT NOT NULL,anomaly_status TEXT NOT NULL,withheld_reasons_json TEXT NOT NULL,
 dependency_digest TEXT NOT NULL,provenance_json TEXT NOT NULL,assessment_status TEXT NOT NULL,
 semantic_json TEXT NOT NULL,contract_version TEXT NOT NULL,
 UNIQUE(contract_version_placeholder,input_snapshot_id,stable_subject_id,authorization_locator),
 FOREIGN KEY(run_id) REFERENCES assessment_runs(run_id),
 FOREIGN KEY(input_snapshot_id) REFERENCES input_snapshots(input_snapshot_id),
 CHECK(subject_type='NOTE'),CHECK(assessment_status='WITHHELD_ONLY'),
 CHECK(authorization_status IN ({','.join(repr(x) for x in AUTHORIZATION_STATUSES)})),
 CHECK(eligibility_status IN ({','.join(repr(x) for x in ELIGIBILITY_STATUSES)})),
 CHECK(anomaly_status IN ({','.join(repr(x) for x in ANOMALY_STATUSES)})));
CREATE TABLE no_change_simulations(
 simulation_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,input_snapshot_id TEXT NOT NULL,
 assessment_id TEXT NOT NULL,simulation_status TEXT NOT NULL,before_byte_sha256 TEXT NOT NULL,
 after_byte_sha256 TEXT NOT NULL,before_semantic_digest TEXT NOT NULL,after_semantic_digest TEXT NOT NULL,
 before_subject_universe_digest TEXT NOT NULL,after_subject_universe_digest TEXT NOT NULL,
 changed_event_count INTEGER NOT NULL,changed_field_count INTEGER NOT NULL,
 output_artifact_status TEXT NOT NULL,semantic_json TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES assessment_runs(run_id),
 FOREIGN KEY(input_snapshot_id) REFERENCES input_snapshots(input_snapshot_id),
 FOREIGN KEY(assessment_id) REFERENCES candidate_assessments(assessment_id),
 CHECK(simulation_status='NO_CHANGE_IDENTITY_PROVEN'),CHECK(changed_event_count=0),
 CHECK(changed_field_count=0),CHECK(output_artifact_status='NOT_CREATED'));
CREATE TABLE identity_validations(
 validation_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,input_snapshot_id TEXT NOT NULL,
 simulation_id TEXT NOT NULL,validation_status TEXT NOT NULL,byte_parity INTEGER NOT NULL,
 semantic_parity INTEGER NOT NULL,subject_fk_parity INTEGER NOT NULL,no_output_guard INTEGER NOT NULL,
 validator_registry_digest TEXT NOT NULL,validation_config_digest TEXT NOT NULL,semantic_json TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES assessment_runs(run_id),
 FOREIGN KEY(input_snapshot_id) REFERENCES input_snapshots(input_snapshot_id),
 FOREIGN KEY(simulation_id) REFERENCES no_change_simulations(simulation_id),
 CHECK(validation_status='IDENTITY_VALIDATED'),CHECK(byte_parity=1),CHECK(semantic_parity=1),
 CHECK(subject_fk_parity=1),CHECK(no_output_guard=1));
CREATE TABLE semantic_digest(digest_algorithm TEXT NOT NULL,schema_version INTEGER NOT NULL,digest TEXT NOT NULL,
 PRIMARY KEY(digest_algorithm,schema_version));
""".replace("contract_version_placeholder", "contract_version")


SEMANTIC_TABLES = ("assessment_runs", "input_snapshots", "candidate_assessments",
                   "no_change_simulations", "identity_validations")


def _output_semantic_digest(database: sqlite3.Connection) -> str:
    rows = []
    for table in SEMANTIC_TABLES:
        values = []
        for row in database.execute(f'SELECT * FROM "{table}"'):
            item = dict(row)
            for key, value in tuple(item.items()):
                if key.endswith("_json"): item[key] = json.loads(value)
            _reject_forbidden_keys(item, table)
            values.append(item)
        values.sort(key=_json)
        rows.extend(_json({"table": table, "row": value}) for value in values)
    return sha256("\n".join(rows).encode()).hexdigest()


def _assert_no_forbidden_schema(database: sqlite3.Connection) -> None:
    for row in database.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')"):
        name = row[0]
        if name.startswith("sqlite_"): continue
        for column in database.execute(f'PRAGMA table_info("{name}")'):
            if column[1].lower() in _FORBIDDEN_KEYS:
                raise ValueError(f"Forbidden withheld-only schema column: {name}.{column[1]}")


def build_withheld_readiness_database(schema_v2_path, output_path,
                                      source_bytes_by_sha256, config=None) -> dict[str, Any]:
    """Atomically materialize one withheld assessment per v2 authorization row."""
    schema_path = Path(schema_v2_path); output = Path(output_path)
    if not schema_path.is_file(): raise ValueError("Accepted schema-v2 database is required")
    if output.suffix.lower() in {".mid", ".midi"}: raise ValueError("MIDI output is forbidden")
    if not isinstance(source_bytes_by_sha256, Mapping): raise TypeError("Frozen source byte map is required")
    cfg = dict(config or {})
    source_guard_policy, trusted_lineage, frozen_manifests = _canonical_lineage_inputs(cfg)
    _reject_forbidden_keys(cfg, "config")
    if set(AUTHORIZATION_MAP) != set(AUTHORIZATION_STATUSES) or len(AUTHORIZATION_MAP) != 21:
        raise RuntimeError("Authorization mapping contract is incomplete")
    normalized_bytes = {}
    for key, value in source_bytes_by_sha256.items():
        source_sha = str(key).lower()
        if not isinstance(value, bytes) or sha256(value).hexdigest() != source_sha:
            raise ValueError("Frozen source byte SHA mismatch")
        normalized_bytes[source_sha] = value
    temp = output.with_suffix(output.suffix + ".013a.tmp")
    temp.unlink(missing_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output_before = output.read_bytes() if output.exists() else None
    artifacts_before = _midi_artifacts(output.parent)
    schema_byte_before = _file_sha256(schema_path)
    source_raw_before = {key: sha256(value).hexdigest() for key, value in normalized_bytes.items()}
    input_db = _readonly(schema_path)
    target_db: sqlite3.Connection | None = None
    try:
        build_info = {row["key"]: json.loads(row["value_json"])
                      for row in input_db.execute("SELECT key,value_json FROM build_info")}
        _reject_forbidden_keys(build_info, "schema_v2.build_info")
        if (build_info.get("schema_version") != 2 or build_info.get("capability") != "ANALYZE_ONLY" or
                build_info.get("mutation_capability") != "NONE"):
            raise ValueError("Input is not accepted ANALYZE_ONLY schema-v2")
        stored = input_db.execute("SELECT digest FROM semantic_digest WHERE digest_algorithm='SHA-256' AND schema_version=2").fetchone()
        schema_semantic = _schema_v2_semantic_digest(input_db)
        if stored is None or stored[0] != schema_semantic:
            raise ValueError("Schema-v2 semantic digest mismatch")
        fk_input = input_db.execute("PRAGMA foreign_key_check").fetchall()
        if fk_input: raise ValueError("Schema-v2 foreign key violation")
        subject_universe = _subject_universe_digest(input_db)
        sources = list(input_db.execute("SELECT * FROM source_context_v2 ORDER BY source_sha256"))
        expected_sources = {str(row["source_sha256"]).lower() for row in sources}
        if set(normalized_bytes) != expected_sources:
            raise ValueError("Frozen source byte universe must exactly match schema-v2 sources")
        if set(frozen_manifests) != expected_sources:
            raise ValueError("Frozen source manifest universe must exactly match schema-v2 sources")
        contract = input_db.execute("SELECT * FROM build_contract_v2").fetchone()
        if contract is None: raise ValueError("Schema-v2 build contract missing")
        protection_digest = str(contract["protection_config_sha256"])
        model_digest = str(contract["model_config_sha256"])
        reference_digest = str(contract["reference_config_sha256"])
        schema_v2_build_config = str(contract["build_config_sha256"])
        config_payload = {"contract_version": CONTRACT_VERSION, "builder_version": BUILDER_VERSION,
                          "schema_version": SCHEMA_VERSION, "caller_config": cfg,
                          "authorization_mapping": AUTHORIZATION_MAP,
                          "validator_registry": "X10_013A_IDENTITY_VALIDATOR_V1",
                          "source_guard_policy_digest": source_guard_policy.policy_sha256,
                          "trusted_lineage_digest": trusted_lineage.semantic_sha256,
                          "source_manifest_digests": {key: _digest(frozen_manifests[key])
                                                      for key in sorted(frozen_manifests)}}
        config_digest = _digest(config_payload)
        auth_rows = list(input_db.execute("SELECT * FROM analysis_authorization ORDER BY source_sha256,note_subject_id,event_slot_key"))
        auth_keys = {(row["source_sha256"], row["note_subject_id"], row["event_slot_key"]) for row in auth_rows}
        if len(auth_keys) != len(auth_rows): raise ValueError("Duplicate authorization natural key")
        source_by_sha = {row["source_sha256"]: row for row in sources}
        snapshots = {}
        for source_sha, source_row in source_by_sha.items():
            manifest_digest, lineage_digest = _source_manifest_digest(
                source_row, source_guard_policy, trusted_lineage, frozen_manifests[source_sha])
            snapshots[source_sha] = (manifest_digest, lineage_digest)
        assessments = []
        counts = {source_sha: 0 for source_sha in expected_sources}
        for row in auth_rows:
            item = dict(row); semantic = json.loads(item["semantic_json"])
            _reject_forbidden_keys(semantic, "analysis_authorization.semantic_json")
            status = item["authorization_status"]
            if status not in AUTHORIZATION_MAP: raise ValueError(f"Unknown authorization status: {status}")
            subject = input_db.execute("SELECT * FROM stable_subjects WHERE subject_id=?", (item["note_subject_id"],)).fetchone()
            if subject is None or subject["subject_type"] != "NOTE" or subject["source_sha256"] != item["source_sha256"]:
                raise ValueError("Authorization must reference same-source NOTE subject")
            eligibility = input_db.execute("SELECT event_slot_key FROM context_eligibility WHERE source_sha256=? AND note_subject_id=?",
                                           (item["source_sha256"], item["note_subject_id"])).fetchone()
            if eligibility is None or eligibility[0] != item["event_slot_key"]:
                raise ValueError("Authorization event slot/context membership mismatch")
            row_payload = dict(item); row_payload["semantic_json"] = semantic
            row_digest = _digest(row_payload)
            composite = [item["source_sha256"], item["note_subject_id"], item["event_slot_key"]]
            locator = _digest([composite, row_digest])
            mapped_eligibility, anomaly, reasons = AUTHORIZATION_MAP[status]
            if not reasons or any(reason not in WITHHELD_REASONS for reason in reasons):
                raise ValueError("Invalid withheld reason set")
            assessments.append((item, row_digest, locator, mapped_eligibility, anomaly, reasons))
            counts[item["source_sha256"]] += 1
        if len(assessments) != len(auth_rows) or sum(counts.values()) != len(auth_rows):
            raise ValueError("Assessment universe reconciliation failed")

        run_semantic = {"contract_version": CONTRACT_VERSION, "schema_version": SCHEMA_VERSION,
                        "builder_version": BUILDER_VERSION, "build_config_sha256": config_digest,
                        "schema_v2_semantic_digest": schema_semantic, "source_count": len(sources),
                        "subject_count": len(auth_rows), "terminal_status": "COMPLETED_WITHHELD_ONLY",
                        "capability": "ANALYZE_ONLY", "mutation_capability": "NONE"}
        run_id = _digest(["ASSESSMENT_RUN", run_semantic])
        target_db = sqlite3.connect(temp); target_db.row_factory = sqlite3.Row
        target_db.execute("PRAGMA foreign_keys=ON"); target_db.executescript(SCHEMA)
        target_db.execute("INSERT INTO assessment_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
            run_id, CONTRACT_VERSION, SCHEMA_VERSION, BUILDER_VERSION, config_digest, schema_semantic,
            len(sources), len(auth_rows), "COMPLETED_WITHHELD_ONLY", "ANALYZE_ONLY", "NONE", _json(run_semantic)))
        snapshot_ids = {}
        for source_row in sources:
            source_sha = source_row["source_sha256"]
            manifest_digest, lineage_digest = snapshots[source_sha]
            snapshot_semantic = {"run_id": run_id, "source_sha256": source_sha,
                "source_class": source_row["corpus"], "source_kind": source_row["source_kind"],
                "member_path": source_row["member_path"], "trusted_lineage_digest": lineage_digest,
                "source_manifest_digest": manifest_digest, "schema_v2_semantic_digest": schema_semantic,
                "schema_v2_byte_sha256": schema_byte_before, "stable_subject_universe_digest": subject_universe,
                "schema_v2_build_config_sha256": schema_v2_build_config,
                "build_config_sha256": config_digest, "protection_digest": protection_digest,
                "model_digest": model_digest, "reference_digest": reference_digest,
                "raw_byte_sha256": source_sha, "before_semantic_digest": schema_semantic,
                "source_guard_policy_digest": source_guard_policy.policy_sha256}
            snapshot_id = _digest(["INPUT_SNAPSHOT", snapshot_semantic]); snapshot_ids[source_sha] = snapshot_id
            target_db.execute("INSERT INTO input_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                snapshot_id, run_id, source_sha, source_row["corpus"], source_row["source_kind"],
                source_row["member_path"], lineage_digest, manifest_digest, schema_semantic,
                schema_byte_before, subject_universe, schema_v2_build_config, config_digest,
                source_guard_policy.policy_sha256,
                protection_digest, model_digest,
                reference_digest, source_sha, schema_semantic, _json(snapshot_semantic)))
        validator_digest = _digest({"registry": "X10_013A_IDENTITY_VALIDATOR_V1",
            "checks": ["RAW_SHA", "SCHEMA_BYTE_SHA", "SCHEMA_SEMANTIC", "SUBJECT_EDGE_UNIVERSE",
                       "SOURCE_MANIFEST_LINEAGE", "FOREIGN_KEYS", "NO_MIDI_ARTIFACT"]})
        for item, row_digest, locator, eligibility, anomaly, reasons in assessments:
            source_sha = item["source_sha256"]; snapshot_id = snapshot_ids[source_sha]
            dependency = _digest({"schema": schema_semantic, "subject_universe": subject_universe,
                "protection": protection_digest, "model": model_digest, "reference": reference_digest,
                "authorization_row": row_digest, "config": config_digest})
            provenance = {"authorization_composite": [source_sha, item["note_subject_id"], item["event_slot_key"]],
                          "authorization_row_digest": row_digest, "authorization_locator": locator,
                          "source_manifest_digest": snapshots[source_sha][0],
                          "trusted_lineage_digest": snapshots[source_sha][1]}
            assessment_semantic = {"contract_version": CONTRACT_VERSION, "input_snapshot_id": snapshot_id,
                "stable_subject_id": item["note_subject_id"], "source_sha256": source_sha,
                "exact_context_key": item["exact_context_key"], "event_slot_key": item["event_slot_key"],
                "authorization_locator": locator, "authorization_row_digest": row_digest,
                "authorization_status": item["authorization_status"], "eligibility_status": eligibility,
                "anomaly_status": anomaly, "withheld_reasons": list(reasons), "dependency_digest": dependency,
                "provenance": provenance, "assessment_status": "WITHHELD_ONLY"}
            assessment_id = _digest(["CANDIDATE_ASSESSMENT", assessment_semantic])
            target_db.execute("INSERT INTO candidate_assessments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                assessment_id, run_id, snapshot_id, item["note_subject_id"], "NOTE", source_sha,
                item["exact_context_key"], item["event_slot_key"], locator, row_digest,
                item["authorization_status"], eligibility, anomaly, _json(list(reasons)), dependency,
                _json(provenance), "WITHHELD_ONLY", _json(assessment_semantic), CONTRACT_VERSION))
            simulation_semantic = {"assessment_id": assessment_id, "status": "NO_CHANGE_IDENTITY_PROVEN",
                "before_byte_sha256": schema_byte_before, "after_byte_sha256": schema_byte_before,
                "before_semantic_digest": schema_semantic, "after_semantic_digest": schema_semantic,
                "before_subject_universe_digest": subject_universe, "after_subject_universe_digest": subject_universe,
                "changed_event_count": 0, "changed_field_count": 0, "output_artifact_status": "NOT_CREATED"}
            simulation_id = _digest(["NO_CHANGE_SIMULATION", simulation_semantic])
            target_db.execute("INSERT INTO no_change_simulations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                simulation_id, run_id, snapshot_id, assessment_id, "NO_CHANGE_IDENTITY_PROVEN",
                schema_byte_before, schema_byte_before, schema_semantic, schema_semantic,
                subject_universe, subject_universe, 0, 0, "NOT_CREATED", _json(simulation_semantic)))
            validation_semantic = {"simulation_id": simulation_id, "status": "IDENTITY_VALIDATED",
                "byte_parity": True, "semantic_parity": True, "subject_fk_parity": True,
                "no_output_guard": True, "validator_registry_digest": validator_digest,
                "validation_config_digest": config_digest}
            validation_id = _digest(["IDENTITY_VALIDATION", validation_semantic])
            target_db.execute("INSERT INTO identity_validations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                validation_id, run_id, snapshot_id, simulation_id, "IDENTITY_VALIDATED", 1, 1, 1, 1,
                validator_digest, config_digest, _json(validation_semantic)))
        target_db.commit()
        _assert_no_forbidden_schema(target_db)
        if _file_sha256(schema_path) != schema_byte_before: raise ValueError("Schema-v2 bytes mutated")
        if _schema_v2_semantic_digest(input_db) != schema_semantic: raise ValueError("Schema-v2 semantics mutated")
        if _subject_universe_digest(input_db) != subject_universe: raise ValueError("Subject universe mutated")
        for source_sha, source_row in source_by_sha.items():
            if _source_manifest_digest(source_row, source_guard_policy, trusted_lineage,
                                       frozen_manifests[source_sha]) != snapshots[source_sha]:
                raise ValueError("Source manifest/lineage identity mutated")
        if {key: sha256(value).hexdigest() for key, value in normalized_bytes.items()} != source_raw_before:
            raise ValueError("Frozen RAW bytes mutated")
        if _midi_artifacts(output.parent) != artifacts_before: raise ValueError("MIDI output artifact created")
        if target_db.execute("PRAGMA integrity_check").fetchone()[0] != "ok": raise ValueError("Output integrity failure")
        if target_db.execute("PRAGMA foreign_key_check").fetchall(): raise ValueError("Output foreign key failure")
        digest = _output_semantic_digest(target_db)
        target_db.execute("INSERT INTO semantic_digest VALUES('SHA-256',?,?)", (SCHEMA_VERSION, digest))
        target_db.commit(); target_db.close(); target_db = None
        input_db.close()
        os.replace(temp, output)
        return {"status": ACCEPTANCE_STATUS, "assessments": len(auth_rows), "sources": len(sources),
                "semantic_digest": digest, "schema_v2_semantic_digest": schema_semantic,
                "capability": "ANALYZE_ONLY", "mutation_capability": "NONE",
                "output_artifact_status": "NOT_CREATED"}
    except Exception:
        if target_db is not None: target_db.close()
        input_db.close(); temp.unlink(missing_ok=True)
        if output_before is not None and (not output.exists() or output.read_bytes() != output_before):
            raise RuntimeError("Atomic rollback contract violated")
        raise