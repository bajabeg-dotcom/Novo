"""Atomic context-qualified ANALYZE_ONLY SQLite materialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping

from .midi import parse_midi
from .rhythm_context import bar_pattern_fingerprints
from .rhythm_context_join import build_channel_context, join_note_context
from .rhythm_negative_corpus import validate_negative_manifest
from .rhythm_multimodal import (PhaseObservation, VerifiedFactoryAssessment,
    assess_factory_model, model_config_sha256)
from .rhythm_protection import (ADAPTER_VERSION_BY_RULE, APPLICABILITY_PREDICATE_VERSION_BY_RULE,
    SUBJECT_UNIVERSE_QUERY_VERSION_BY_RULE, REQUIRED_PROTECTION_RULES, AdapterContract,
    AdapterRun, CoveragePartition, ProtectionEvidenceRegistry, ProtectionGroup,
    ProtectionGroupMembership, aggregate_protection_status, canonical_partition_result_sha256,
    canonical_protection_config, final_analysis_authorization, protection_config_sha256,
    sparse_rule_status)
from .rhythm_protection_adapters import (SIX_SONG_FORBIDDEN_SHA256S, AdapterEmission,
    ALLOWED_LINEAGE_PARENT_CLASSES, FORBIDDEN_SOURCE_KINDS, FrozenStableSubjectRegistry,
    SourceGuardPolicy, StructuralSourceSnapshot, TrustedSourceLineageSnapshot,
    build_pre_model_adapter_emissions)
from .rhythm_reference_conflict import (ReferenceRelationship, assess_reference_relationship,
    reference_config_sha256)
from .rhythm_subject_registry import StableSubjectRegistry, canonical_json


FORBIDDEN_IDENTIFIER_ROOTS = ("target", "candidate", "proposal", "repair", "apply", "commit", "mutation")
NONSEMANTIC_KEYS = {"timestamp", "created_at", "updated_at", "build_timestamp", "generated_at", "absolute_path"}
SEMANTIC_TABLES = ("source_context", "channel_state_events", "program_segments", "meter_segments",
    "tempo_segments", "note_context", "bar_context", "protection_observations", "negative_corpus_cases")

SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
CREATE TABLE source_context(source_sha256 TEXT PRIMARY KEY,corpus TEXT NOT NULL,member_path TEXT NOT NULL,
 metadata_json TEXT NOT NULL,quality_json TEXT NOT NULL,capability TEXT NOT NULL);
CREATE TABLE channel_state_events(source_sha256 TEXT NOT NULL,channel INTEGER NOT NULL,tick INTEGER NOT NULL,
 event_kind TEXT NOT NULL,semantic_value_sha256 TEXT NOT NULL,state_event_id TEXT NOT NULL UNIQUE,
 semantic_value_json TEXT NOT NULL,locators_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,channel,tick,event_kind,semantic_value_sha256),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE program_segments(source_sha256 TEXT NOT NULL,channel INTEGER NOT NULL,start_tick INTEGER NOT NULL,
 program_segment_id TEXT NOT NULL UNIQUE,end_tick INTEGER,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,
 status TEXT NOT NULL,segment_kind TEXT NOT NULL,locators_json TEXT NOT NULL,PRIMARY KEY(source_sha256,channel,start_tick,program_segment_id),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE meter_segments(source_sha256 TEXT NOT NULL,start_tick INTEGER NOT NULL,meter_segment_id TEXT NOT NULL UNIQUE,
 end_tick INTEGER,numerator INTEGER,denominator INTEGER,status TEXT NOT NULL,locators_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,start_tick,meter_segment_id),FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE tempo_segments(source_sha256 TEXT NOT NULL,start_tick INTEGER NOT NULL,tempo_segment_id TEXT NOT NULL UNIQUE,
 end_tick INTEGER,microseconds_per_quarter INTEGER,tempo_regime_key TEXT,status TEXT NOT NULL,locators_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,start_tick,tempo_segment_id),FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE note_context(source_sha256 TEXT NOT NULL,note_id TEXT NOT NULL,on_event_id TEXT NOT NULL,off_event_id TEXT NOT NULL,
 track_index INTEGER NOT NULL,channel INTEGER NOT NULL,note INTEGER NOT NULL,velocity INTEGER NOT NULL,start_tick INTEGER NOT NULL,
 end_tick INTEGER NOT NULL,duration_ticks INTEGER NOT NULL,bar_index INTEGER NOT NULL,beat_index INTEGER NOT NULL,
 program_segment_id TEXT NOT NULL,meter_segment_id TEXT NOT NULL,tempo_segment_id TEXT NOT NULL,
 context_json TEXT NOT NULL,eligibility_status TEXT NOT NULL,PRIMARY KEY(source_sha256,note_id),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256),
 FOREIGN KEY(program_segment_id) REFERENCES program_segments(program_segment_id),
 FOREIGN KEY(meter_segment_id) REFERENCES meter_segments(meter_segment_id),
 FOREIGN KEY(tempo_segment_id) REFERENCES tempo_segments(tempo_segment_id));
CREATE TABLE bar_context(source_sha256 TEXT NOT NULL,track_index INTEGER NOT NULL,channel INTEGER NOT NULL,bar_index INTEGER NOT NULL,
 topology_sha256 TEXT NOT NULL,exact_context_key TEXT,eligibility_status TEXT NOT NULL,context_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,track_index,channel,bar_index,topology_sha256),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE protection_observations(source_sha256 TEXT NOT NULL,stable_subject_id TEXT NOT NULL,rule_key TEXT NOT NULL,
 adapter_version TEXT NOT NULL,detection_status TEXT NOT NULL,evidence_status TEXT NOT NULL,observation_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,stable_subject_id,rule_key,adapter_version),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE negative_corpus_cases(source_class TEXT NOT NULL,case_id TEXT NOT NULL,case_json TEXT NOT NULL,
 PRIMARY KEY(source_class,case_id));
CREATE TABLE semantic_digest(digest_algorithm TEXT NOT NULL,schema_version INTEGER NOT NULL,digest TEXT NOT NULL,
 PRIMARY KEY(digest_algorithm,schema_version));
"""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _is_nonsemantic_key(key) -> bool:
    lowered = str(key).lower()
    return lowered in NONSEMANTIC_KEYS or "timestamp" in lowered or lowered.endswith("_at")


def _normalize(value):
    if isinstance(value, dict): return {key: _normalize(value[key]) for key in sorted(value) if not _is_nonsemantic_key(key)}
    if isinstance(value, (list, tuple)): return [_normalize(item) for item in value]
    if isinstance(value, Path): return PurePosixPath(value).as_posix()
    if isinstance(value, bytes): return {"sha256": sha256(value).hexdigest()}
    if isinstance(value, str):
        path = value.replace("\\", "/")
        if path.startswith("/") or (len(path) > 2 and path[1] == ":" and path[2] == "/"):
            return f"ABSOLUTE_PATH/{PurePosixPath(path).name}"
    return value


def _forbidden_identifier(value) -> bool:
    lowered = str(value).lower()
    return any(root in lowered for root in FORBIDDEN_IDENTIFIER_ROOTS)


def _record_bytes(record):
    data = record.get("bytes", record.get("data"))
    if not isinstance(data, bytes): raise ValueError("RAW source record requires bytes")
    return data


def _reject_forbidden_fields(value, location="root"):
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()
            if _forbidden_identifier(lower):
                raise ValueError(f"Analyze-only forbidden field at {location}.{key}")
            _reject_forbidden_fields(item, f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value): _reject_forbidden_fields(item, f"{location}[{index}]")


def assert_analyze_only_schema(database_path) -> None:
    database = sqlite3.connect(database_path)
    try:
        rows = database.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')").fetchall()
        for (name,) in rows:
            if name.startswith("sqlite_"): continue
            if _forbidden_identifier(name):
                raise ValueError(f"Forbidden analyze-only schema identifier in {name}")
            for column in database.execute(f'PRAGMA table_info("{name}")'):
                if _forbidden_identifier(column[1]):
                    raise ValueError(f"Forbidden analyze-only schema identifier in {name}.{column[1]}")
        info = dict(database.execute("SELECT key,value_json FROM build_info"))
        if json.loads(info.get("capability", 'null')) != "ANALYZE_ONLY" or json.loads(info.get("mutation_capability", 'null')) != "NONE":
            raise ValueError("Database does not declare ANALYZE_ONLY/NONE")
    finally: database.close()


def canonical_semantic_rows(database_path) -> list[str]:
    database = sqlite3.connect(database_path); database.row_factory = sqlite3.Row
    rows = []
    try:
        for table in SEMANTIC_TABLES:
            exists = database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not exists: continue
            values = []
            for row in database.execute(f'SELECT * FROM "{table}"'):
                item = dict(row)
                for key, value in list(item.items()):
                    if key.endswith("_json") and isinstance(value, str):
                        try: item[key] = json.loads(value)
                        except json.JSONDecodeError: pass
                values.append(_normalize(item))
            values.sort(key=_json)
            rows.extend(_json({"table": table, "row": value}) for value in values)
    finally: database.close()
    return rows


def semantic_digest(database_path) -> str:
    payload = "\n".join(canonical_semantic_rows(database_path)).encode("utf-8")
    return sha256(payload).hexdigest()


def _insert_timelines(db, context):
    for row in context["channel_state_events"]:
        db.execute("INSERT INTO channel_state_events VALUES(?,?,?,?,?,?,?,?)", (row["source_sha256"], row["channel"], row["tick"],
            row["event_kind"], row["semantic_value_sha256"], row["state_event_id"], _json(row["semantic_value"]), _json(row["evidence_locators"])))
    for row in context["program_segments"]:
        db.execute("INSERT INTO program_segments VALUES(?,?,?,?,?,?,?,?,?,?,?)", (row["source_sha256"], row["channel"], row["start_tick"],
            row["program_segment_id"], row["end_tick"], row["bank_msb"], row["bank_lsb"], row["program"], row["status"],
            row["segment_kind"], _json(row["evidence_locators"])))
    for row in context["meter_segments"]:
        db.execute("INSERT INTO meter_segments VALUES(?,?,?,?,?,?,?,?)", (row["source_sha256"], row["start_tick"], row["meter_segment_id"],
            row["end_tick"], row["numerator"], row["denominator"], row["status"], _json(row["evidence_locators"])))
    for row in context["tempo_segments"]:
        db.execute("INSERT INTO tempo_segments VALUES(?,?,?,?,?,?,?,?)", (row["source_sha256"], row["start_tick"], row["tempo_segment_id"],
            row["end_tick"], row["microseconds_per_quarter"], row["tempo_regime_key"], row["status"], _json(row["evidence_locators"])))


def build_context_qualified_database(source_records, output_path, config=None) -> dict:
    """Build an atomic RAW-derived database; never accepts a legacy model input."""
    cfg = dict(config or {})
    _reject_forbidden_fields(cfg, "config")
    for legacy in ("calibration_path", "consensus_path", "legacy_database"):
        if legacy in cfg: raise ValueError("Legacy calibration/consensus cannot be builder input")
    output_path = Path(output_path); temp = output_path.with_suffix(output_path.suffix + ".tmp"); temp.unlink(missing_ok=True)
    forbidden = {str(value).lower() for value in cfg.get("forbidden_sha256", ())}
    negative = validate_negative_manifest(cfg.get("negative_manifest", {"schema_version": 1, "cases": []}), forbidden)
    records = list(source_records)
    if not records: raise ValueError("At least one RAW source is required")
    db = sqlite3.connect(temp); db.execute("PRAGMA foreign_keys=ON"); db.executescript(SCHEMA)
    try:
        adapter_config = [{"rule_key": str(getattr(adapter, "rule_key", getattr(adapter, "__name__", "UNKNOWN_ADAPTER"))),
                           "version": str(getattr(adapter, "version", getattr(adapter, "__version__", "UNVERSIONED")))}
                          for adapter in cfg.get("protection_adapters", ())]
        stored_config = {key: value for key, value in cfg.items() if key not in {"negative_manifest", "protection_adapters"}}
        stored_config["protection_adapters"] = adapter_config
        db.executemany("INSERT INTO build_info VALUES(?,?)", (("schema_version", _json(1)), ("builder_version", _json(1)),
            ("capability", _json("ANALYZE_ONLY")), ("mutation_capability", _json("NONE")),
            ("config", _json(_normalize(stored_config)))))
        note_total = exact_total = 0; protection_seen = {}
        seen_sources = set()
        for record in records:
            _reject_forbidden_fields(record, "source_record")
            data = _record_bytes(record); before = sha256(data).hexdigest(); declared = str(record.get("source_sha256", before)).lower()
            if before != declared: raise ValueError("RAW source SHA mismatch")
            if declared in forbidden: raise ValueError("Forbidden source SHA")
            if declared in seen_sources: raise ValueError("Duplicate RAW source natural key")
            seen_sources.add(declared)
            corpus = str(record.get("corpus", "")).lower()
            if corpus not in {"factory", "gold", "reference"}: raise ValueError("Unsupported corpus")
            member = PurePosixPath(str(record.get("member_path", ""))).as_posix()
            if not member or member.startswith("/") or ".." in PurePosixPath(member).parts: raise ValueError("Invalid member path")
            metadata = dict(record.get("metadata") or {}); quality = record.get("quality_status", "INVALID")
            _reject_forbidden_fields(metadata)
            midi = parse_midi(data)
            db.execute("INSERT INTO source_context VALUES(?,?,?,?,?,?)", (declared, corpus, member, _json(metadata), _json(quality), "ANALYZE_ONLY"))
            timelines = build_channel_context(midi, declared); _insert_timelines(db, timelines)
            notes = join_note_context(midi, declared, metadata, quality, cfg.get("protection_adapters", ()))
            _reject_forbidden_fields(notes)
            for row in notes:
                note_total += 1; exact_total += int(row["eligibility_status"] == "EXACT_CONTEXT_MATCH")
                db.execute("INSERT INTO note_context VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (declared, row["note_id"], row["on_event_id"],
                    row["off_event_id"], row["track"], row["channel"], row["note"], row["velocity"], row["start_tick"], row["end_tick"],
                    row["duration_ticks"], row["bar"], row["beat"], row["program_segment_id"], row["meter_segment_id"], row["tempo_segment_id"],
                    _json(row), row["eligibility_status"]))
                for observation in row.get("protection_observations", []):
                    natural_key = (declared, observation["stable_subject_id"], observation["rule_key"], observation["adapter_version"])
                    semantic = _json(observation)
                    if natural_key in protection_seen:
                        if protection_seen[natural_key] != semantic:
                            raise ValueError("Contradictory protection observation natural key")
                        continue
                    protection_seen[natural_key] = semantic
                    db.execute("INSERT INTO protection_observations VALUES(?,?,?,?,?,?,?)", (*natural_key,
                        observation["detection_status"], observation.get("evidence_status", "UNVERIFIED"), semantic))
            by_bar = {}
            for pattern in bar_pattern_fingerprints(notes):
                group = [row for row in notes if row["track"] == pattern["track"] and row["channel"] == pattern["channel"] and row["bar"] == pattern["bar"]]
                exact_keys = {row["exact_context_key"] for row in group}
                exact_key = next(iter(exact_keys)) if len(exact_keys) == 1 and None not in exact_keys else None
                status = "EXACT_CONTEXT_MATCH" if exact_key and all(row["eligibility_status"] == "EXACT_CONTEXT_MATCH" for row in group) else "PROTECTED_CONTEXT"
                key = (declared, pattern["track"], pattern["channel"], pattern["bar"], pattern["topology_sha256"])
                if key in by_bar: raise ValueError("Contradictory bar natural key")
                by_bar[key] = True
                db.execute("INSERT INTO bar_context VALUES(?,?,?,?,?,?,?,?)", (*key, exact_key, status, _json({"pattern": pattern, "note_ids": [row["note_id"] for row in group]})))
            if sha256(data).hexdigest() != before: raise ValueError("RAW source mutated")
        for case in negative["cases"]:
            db.execute("INSERT INTO negative_corpus_cases VALUES(?,?,?)", (case["source_class"], case["case_id"], _json(case)))
        db.commit()
        assert_analyze_only_schema(temp)
        digest = semantic_digest(temp)
        db.execute("INSERT INTO semantic_digest VALUES('SHA-256',1,?)", (digest,)); db.commit()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        fk = db.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or fk: raise ValueError(f"SQLite validation failed: {integrity}, fk={len(fk)}")
        db.close(); temp.replace(output_path)
        return {"sources": len(records), "notes": note_total, "exact_notes": exact_total,
                "semantic_digest": digest, "capability": "ANALYZE_ONLY"}
    except Exception:
        db.close(); temp.unlink(missing_ok=True); raise


# Schema v2 is deliberately parallel to the accepted v1 materializer above.
# No v1 table, digest, or public function is migrated or reinterpreted.
V2_SCHEMA_VERSION = 2
V2_BUILDER_VERSION = "X10_CONTEXT_SCHEMA_V2_RAW_REBUILD_V1"
V2_SEMANTIC_TABLES = (
    "build_contract_v2",
    "source_context_v2", "stable_subjects", "stable_subject_edges", "context_subject_membership", "adapter_runs",
    "coverage_partitions", "protection_groups", "protection_memberships",
    "context_eligibility", "model_eligibility", "factory_observations",
    "reference_observations", "factory_local_profiles", "factory_consensus_slots",
    "factory_models", "multimodal_components",
    "reference_relationships", "analysis_authorization", "negative_corpus_cases_v2",
)

V2_SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
CREATE TABLE build_contract_v2(
 contract_id TEXT PRIMARY KEY,builder_version TEXT NOT NULL,schema_version INTEGER NOT NULL,
 build_config_sha256 TEXT NOT NULL,protection_config_sha256 TEXT NOT NULL,
 model_config_sha256 TEXT NOT NULL,reference_config_sha256 TEXT NOT NULL,
 negative_manifest_sha256 TEXT NOT NULL,semantic_json TEXT NOT NULL,
 CHECK(schema_version=2));
CREATE TABLE source_context_v2(
 source_sha256 TEXT PRIMARY KEY,corpus TEXT NOT NULL,source_kind TEXT NOT NULL,
 member_path TEXT NOT NULL,quality_status TEXT NOT NULL,metadata_json TEXT NOT NULL,
 lineage_sha256 TEXT NOT NULL,registry_sha256 TEXT NOT NULL,source_semantic_json TEXT NOT NULL,
 CHECK(corpus IN ('factory','gold','reference')),
 CHECK(source_kind IN ('FACTORY_RAW','GOLD_REFERENCE_RAW')),
 CHECK(quality_status IN ('NORMAL','RARE','OUTLIER','INVALID')));
CREATE TABLE stable_subjects(
 subject_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,subject_type TEXT NOT NULL,
 contract_version TEXT NOT NULL,natural_key_json TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(source_sha256,subject_type,contract_version,natural_key_json),
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 CHECK(subject_type IN ('EVENT','NOTE','ONSET_CLUSTER','BAR','PHRASE','COMPONENT','BOUNDARY','TRACK_CHANNEL','PROGRAM_SEGMENT','EXACT_CONTEXT')));
CREATE TABLE stable_subject_edges(
 edge_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,edge_type TEXT NOT NULL,
 contract_version TEXT NOT NULL,parent_subject_id TEXT NOT NULL,child_subject_id TEXT NOT NULL,
 semantic_json TEXT NOT NULL,UNIQUE(edge_type,parent_subject_id,child_subject_id,contract_version),
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 FOREIGN KEY(parent_subject_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(child_subject_id) REFERENCES stable_subjects(subject_id),
 CHECK(edge_type IN ('TRACK_CHANNEL_CONTAINS_EVENT','TRACK_CHANNEL_CONTAINS_NOTE','NOTE_HAS_ON_EVENT','NOTE_HAS_OFF_EVENT','BAR_CONTAINS_ONSET_CLUSTER','ONSET_CLUSTER_CONTAINS_NOTE','PHRASE_CONTAINS_NOTE','COMPONENT_CONTAINS_NOTE','BOUNDARY_TOUCHES_BAR','BOUNDARY_TOUCHES_NOTE','PROGRAM_SEGMENT_CONTAINS_NOTE','EXACT_CONTEXT_CONTAINS_NOTE')));
CREATE TABLE context_subject_membership(
 source_sha256 TEXT NOT NULL,exact_context_key TEXT NOT NULL,scope_subject_id TEXT NOT NULL,
 subject_id TEXT NOT NULL,semantic_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,exact_context_key,subject_id),
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 FOREIGN KEY(scope_subject_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(subject_id) REFERENCES stable_subjects(subject_id));
CREATE TABLE adapter_runs(
 run_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,rule_key TEXT NOT NULL,
 adapter_version TEXT NOT NULL,run_status TEXT NOT NULL,scope_subject_id TEXT NOT NULL,
 config_sha256 TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(source_sha256,rule_key,adapter_version,scope_subject_id),
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 FOREIGN KEY(scope_subject_id) REFERENCES stable_subjects(subject_id),
 CHECK(rule_key IN ('GUITAR_MODE','RX_DNC','ORNAMENT_TRILL_GRACE','DRUM_FLAM_ROLL_GHOST','CROSS_BAR','SECTION_TRANSITION','TEMPO_METER_BOUNDARY','LOCAL_REPEATED_PATTERN','FACTORY_REFERENCE_CONFLICT')),
 CHECK(run_status IN ('COMPLETE','PARTIAL','DEPENDENCY_UNAVAILABLE','DEFERRED_POST_MODEL','NOT_APPLICABLE')));
CREATE TABLE coverage_partitions(
 partition_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,partition_key TEXT NOT NULL,
 stable_scope_id TEXT NOT NULL,status TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(run_id,partition_key,stable_scope_id),
 FOREIGN KEY(run_id) REFERENCES adapter_runs(run_id),
 FOREIGN KEY(stable_scope_id) REFERENCES stable_subjects(subject_id),
 CHECK(status IN ('COMPLETE','PARTIAL')));
CREATE TABLE protection_groups(
 group_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,
 rule_key TEXT NOT NULL,per_rule_status TEXT NOT NULL,semantic_json TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES adapter_runs(run_id),
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 CHECK(rule_key IN ('GUITAR_MODE','RX_DNC','ORNAMENT_TRILL_GRACE','DRUM_FLAM_ROLL_GHOST','CROSS_BAR','SECTION_TRANSITION','TEMPO_METER_BOUNDARY','LOCAL_REPEATED_PATTERN','FACTORY_REFERENCE_CONFLICT')),
 CHECK(per_rule_status IN ('DETECTED','AMBIGUOUS','EVIDENCE_UNJOINABLE','DEPENDENCY_GAP','DEFERRED','PARTIAL_UNRESOLVED')));
CREATE TABLE protection_memberships(
 membership_id TEXT PRIMARY KEY,group_id TEXT NOT NULL,stable_subject_id TEXT NOT NULL,
 membership_role TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(group_id,stable_subject_id,membership_role),
 FOREIGN KEY(group_id) REFERENCES protection_groups(group_id),
 FOREIGN KEY(stable_subject_id) REFERENCES stable_subjects(subject_id),
 CHECK(membership_role IN ('AFFECTED_SUBJECT')));
CREATE TABLE context_eligibility(
 source_sha256 TEXT NOT NULL,note_subject_id TEXT NOT NULL,note_id TEXT NOT NULL,
 exact_context_key TEXT,event_slot_key TEXT NOT NULL,context_status TEXT NOT NULL,quality_status TEXT NOT NULL,
 context_json TEXT NOT NULL,PRIMARY KEY(source_sha256,note_subject_id),
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 FOREIGN KEY(note_subject_id) REFERENCES stable_subjects(subject_id),
 CHECK(context_status IN ('EXACT_CONTEXT_MATCH','CONTEXT_UNPROVEN','CONTEXT_CONFLICT')),
 CHECK(quality_status IN ('NORMAL','RARE','OUTLIER','INVALID')));
CREATE TABLE model_eligibility(
 exact_context_key TEXT NOT NULL,event_slot_key TEXT NOT NULL,model_status TEXT NOT NULL,
 reason_json TEXT NOT NULL,PRIMARY KEY(exact_context_key,event_slot_key),
 CHECK(model_status IN ('FACTORY_SUFFICIENT','FACTORY_INSUFFICIENT','FACTORY_UNAVAILABLE')));
CREATE TABLE factory_observations(
 observation_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,exact_context_key TEXT NOT NULL,
 event_slot_key TEXT NOT NULL,bar_id TEXT NOT NULL,event_slot_subject_id TEXT NOT NULL,
 on_event_subject_id TEXT NOT NULL,onset_cluster_subject_id TEXT NOT NULL,note_subject_id TEXT NOT NULL,
 phase_tick INTEGER NOT NULL,bar_start_tick INTEGER NOT NULL,bar_end_tick INTEGER NOT NULL,
 phase_numerator INTEGER NOT NULL,
 phase_denominator INTEGER NOT NULL,resolution_numerator INTEGER NOT NULL,
 resolution_denominator INTEGER NOT NULL,semantic_json TEXT NOT NULL,
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 FOREIGN KEY(bar_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(event_slot_subject_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(on_event_subject_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(onset_cluster_subject_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(note_subject_id) REFERENCES stable_subjects(subject_id),
 CHECK(bar_end_tick>bar_start_tick),
 CHECK(phase_tick>=bar_start_tick AND phase_tick<bar_end_tick),
 CHECK(phase_denominator>0),CHECK(resolution_denominator>0));
CREATE TABLE reference_observations(
 observation_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,exact_context_key TEXT NOT NULL,
 event_slot_key TEXT NOT NULL,bar_id TEXT NOT NULL,event_slot_subject_id TEXT NOT NULL,
 on_event_subject_id TEXT NOT NULL,onset_cluster_subject_id TEXT NOT NULL,note_subject_id TEXT NOT NULL,
 phase_tick INTEGER NOT NULL,bar_start_tick INTEGER NOT NULL,bar_end_tick INTEGER NOT NULL,
 authority TEXT NOT NULL,semantic_json TEXT NOT NULL,
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 FOREIGN KEY(bar_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(event_slot_subject_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(on_event_subject_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(onset_cluster_subject_id) REFERENCES stable_subjects(subject_id),
 FOREIGN KEY(note_subject_id) REFERENCES stable_subjects(subject_id),
 CHECK(authority IN ('REFERENCE','GOLD_REFERENCE')),
 CHECK(bar_end_tick>bar_start_tick),CHECK(phase_tick>=bar_start_tick AND phase_tick<bar_end_tick));
CREATE TABLE factory_local_profiles(
 local_profile_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,exact_context_key TEXT NOT NULL,
 event_slot_key TEXT NOT NULL,observation_count INTEGER NOT NULL CHECK(observation_count>0),
 observations_sha256 TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(source_sha256,exact_context_key,event_slot_key),
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256));
CREATE TABLE factory_consensus_slots(
 consensus_slot_id TEXT PRIMARY KEY,exact_context_key TEXT NOT NULL,event_slot_key TEXT NOT NULL,
 distinct_source_count INTEGER NOT NULL,bar_observation_count INTEGER NOT NULL,
 model_eligibility_status TEXT NOT NULL,observations_sha256 TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(exact_context_key,event_slot_key));
CREATE TABLE factory_models(
 model_id TEXT PRIMARY KEY,exact_context_key TEXT NOT NULL,event_slot_key TEXT NOT NULL,
 factory_model_status TEXT NOT NULL,modality_status TEXT NOT NULL,selected_k INTEGER,
 config_sha256 TEXT NOT NULL,semantic_sha256 TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(exact_context_key,event_slot_key,config_sha256),
 CHECK(factory_model_status IN ('FACTORY_SUFFICIENT','FACTORY_INSUFFICIENT','FACTORY_UNAVAILABLE')),
 CHECK(modality_status IN ('ASSESSED_UNIMODAL','ASSESSED_MULTIMODAL','DEGENERATE_EXACT_REFERENCE','INSUFFICIENT_MODAL_EVIDENCE','UNSTABLE_MODAL_STRUCTURE','UNSTABLE_BIC_NEAR_TIE','UNSTABLE_COMPONENT_MATCH','UNSTABLE_GROOVE_MODE_STRUCTURE','UNSTABLE_POSTERIOR_TIE','UNSTABLE_COMPONENT_COLLAPSE','NUMERICAL_REVIEW_REQUIRED','NUMERICAL_CYCLE_REVIEW_REQUIRED','NUMERICAL_NONCONVERGENCE_REVIEW_REQUIRED','DEFERRED')));
CREATE TABLE multimodal_components(
 model_id TEXT NOT NULL,component_id INTEGER NOT NULL,semantic_json TEXT NOT NULL,
 PRIMARY KEY(model_id,component_id),FOREIGN KEY(model_id) REFERENCES factory_models(model_id));
CREATE TABLE reference_relationships(
 relationship_id TEXT PRIMARY KEY,model_id TEXT NOT NULL,status TEXT NOT NULL,
 config_sha256 TEXT NOT NULL,semantic_sha256 TEXT NOT NULL,semantic_json TEXT NOT NULL,
 UNIQUE(model_id,config_sha256),FOREIGN KEY(model_id) REFERENCES factory_models(model_id),
 CHECK(status IN ('REFERENCE_SUPPORT','NO_REFERENCE_EVIDENCE','INSUFFICIENT_REFERENCE_EVIDENCE','POTENTIAL_CONTRADICTION','FACTORY_SUPPORT_UNINFORMATIVE','DEFERRED_FACTORY_MODEL_UNSTABLE','POST_MODEL_PARTIAL')));
CREATE TABLE analysis_authorization(
 source_sha256 TEXT NOT NULL,note_subject_id TEXT NOT NULL,exact_context_key TEXT,
 event_slot_key TEXT NOT NULL,protection_status TEXT NOT NULL,factory_model_status TEXT NOT NULL,
 modality_status TEXT NOT NULL,reference_status TEXT NOT NULL,authorization_status TEXT NOT NULL,
 analysis_allowed INTEGER NOT NULL CHECK(analysis_allowed IN (0,1)),capability TEXT NOT NULL,
 semantic_json TEXT NOT NULL,PRIMARY KEY(source_sha256,note_subject_id,event_slot_key),
 FOREIGN KEY(source_sha256) REFERENCES source_context_v2(source_sha256),
 FOREIGN KEY(note_subject_id) REFERENCES stable_subjects(subject_id),
 CHECK(protection_status IN ('PROTECTION_CLEAR','PROTECTED_DETECTED','PROTECTION_UNRESOLVED','EXTERNAL_EVIDENCE_GAP','PROTECTION_SCAN_PARTIAL','PROTECTION_DEFERRED','PROTECTION_CONTRACT_INCOMPLETE')),
 CHECK(factory_model_status IN ('FACTORY_SUFFICIENT','FACTORY_INSUFFICIENT','FACTORY_UNAVAILABLE')),
 CHECK(modality_status IN ('ASSESSED_UNIMODAL','ASSESSED_MULTIMODAL','DEGENERATE_EXACT_REFERENCE','INSUFFICIENT_MODAL_EVIDENCE','UNSTABLE_MODAL_STRUCTURE','UNSTABLE_BIC_NEAR_TIE','UNSTABLE_COMPONENT_MATCH','UNSTABLE_GROOVE_MODE_STRUCTURE','UNSTABLE_POSTERIOR_TIE','UNSTABLE_COMPONENT_COLLAPSE','NUMERICAL_REVIEW_REQUIRED','NUMERICAL_CYCLE_REVIEW_REQUIRED','NUMERICAL_NONCONVERGENCE_REVIEW_REQUIRED','DEFERRED')),
 CHECK(reference_status IN ('REFERENCE_SUPPORT','NO_REFERENCE_EVIDENCE','INSUFFICIENT_REFERENCE_EVIDENCE','POTENTIAL_CONTRADICTION','FACTORY_SUPPORT_UNINFORMATIVE','DEFERRED_FACTORY_MODEL_UNSTABLE','POST_MODEL_PARTIAL')),
 CHECK(authorization_status IN ('EXCLUDED_INVALID_SOURCE','PRESERVE_SOURCE_QUALITY','PRESERVE_CONTEXT_UNPROVEN','PRESERVE_CORE_SCAN_PARTIAL','PROTECTED_DETECTED','PRESERVE_PROTECTION_UNRESOLVED','PRESERVE_EXTERNAL_EVIDENCE_GAP','PRESERVE_PROTECTION_SCAN_PARTIAL','PRESERVE_PROTECTION_DEFERRED','PRESERVE_PROTECTION_CONTRACT_INCOMPLETE','INSUFFICIENT_FACTORY_EVIDENCE','ZERO_VARIANCE_REVIEW','PRESERVE_MODALITY_INSUFFICIENT','PRESERVE_MODALITY_UNSTABLE','PRESERVE_MODALITY_DEFERRED','PRESERVE_MULTIMODAL_CONTEXT','PRESERVE_REFERENCE_GATE_PARTIAL','PRESERVE_REFERENCE_GATE_DEFERRED','REVIEW_FACTORY_REFERENCE_CONFLICT','PRESERVE_FACTORY_SUPPORT_UNINFORMATIVE','ANALYZE_ALLOWED')),
 CHECK(capability='ANALYZE_ONLY'));
CREATE TABLE negative_corpus_cases_v2(
 source_class TEXT NOT NULL,case_id TEXT NOT NULL,case_json TEXT NOT NULL,
 PRIMARY KEY(source_class,case_id),
 CHECK(source_class IN ('FACTORY_NEGATIVE_OBSERVATION','REFERENCE_NEGATIVE_OBSERVATION','SYNTHETIC_GUARD_FIXTURE','HUMAN_VALIDATED_NEGATIVE')));
CREATE TABLE semantic_digest(
 digest_algorithm TEXT NOT NULL,schema_version INTEGER NOT NULL,digest TEXT NOT NULL,
 PRIMARY KEY(digest_algorithm,schema_version));
CREATE INDEX factory_observation_context_idx ON factory_observations(exact_context_key,event_slot_key,source_sha256,bar_id);
CREATE INDEX reference_observation_context_idx ON reference_observations(exact_context_key,event_slot_key,source_sha256,bar_id);
CREATE INDEX membership_subject_idx ON protection_memberships(stable_subject_id,group_id);
"""


@dataclass(frozen=True)
class V2SourceArtifacts:
    """Accepted A/B/C artifacts derived from the already parsed RAW source."""

    context_snapshots: tuple[StructuralSourceSnapshot, ...]
    factory_observations: tuple[PhaseObservation, ...] = ()
    reference_observations: tuple[PhaseObservation, ...] = ()
    unproven_partition: "V2UnprovenPartition | None" = None

    def __post_init__(self) -> None:
        snapshots = tuple(self.context_snapshots)
        if any(not isinstance(item, StructuralSourceSnapshot) for item in snapshots):
            raise ValueError("V2SourceArtifacts context snapshots must be StructuralSourceSnapshots")
        if self.unproven_partition is not None and not isinstance(self.unproven_partition, V2UnprovenPartition):
            raise TypeError("unproven_partition must be V2UnprovenPartition")
        if not snapshots and self.unproven_partition is None:
            raise ValueError("Zero exact contexts require an unproven source partition")
        object.__setattr__(self, "context_snapshots", snapshots)
        object.__setattr__(self, "factory_observations", tuple(self.factory_observations))
        object.__setattr__(self, "reference_observations", tuple(self.reference_observations))


def _validate_v2_source_identity(source_sha256: str, source_kind: str,
                                 source_guard_policy: SourceGuardPolicy,
                                 source_lineage: TrustedSourceLineageSnapshot,
                                 source_manifest: Mapping[str, Any]) -> None:
    """Shared exact/unproven source identity and full-lineage gate."""
    if not isinstance(source_guard_policy, SourceGuardPolicy):
        raise TypeError("Trusted SourceGuardPolicy is mandatory")
    if not isinstance(source_lineage, TrustedSourceLineageSnapshot):
        raise TypeError("TrustedSourceLineageSnapshot is mandatory")
    root = source_lineage.record_for(source_sha256)
    if root is None: raise ValueError("Source lineage root record is missing")
    if root.lineage_class != source_kind:
        raise ValueError("Source lineage root class does not match source_kind")
    closure = source_lineage.ancestor_closure(source_sha256)
    forbidden_sha = sorted(set(closure).intersection(
        source_guard_policy.forbidden_six_song_sha256s))
    if forbidden_sha: raise ValueError("Forbidden SHA exists in source lineage closure")
    records = {item.source_sha256: item for item in source_lineage.records}
    forbidden_classes = sorted({records[item].lineage_class for item in closure
                                if records[item].lineage_class in FORBIDDEN_SOURCE_KINDS})
    if forbidden_classes: raise ValueError("Forbidden class exists in source lineage closure")
    allowed = set(ALLOWED_LINEAGE_PARENT_CLASSES.get(source_kind, ()))
    illegal = sorted({records[item].lineage_class for item in closure} - allowed)
    if illegal: raise ValueError("Illegal class exists in source lineage closure")
    manifest = dict(source_manifest)
    if manifest.get("source_class") != source_kind:
        raise ValueError("Source manifest class does not match source_kind")
    if manifest.get("lineage_sha256") != source_lineage.semantic_sha256:
        raise ValueError("Source manifest lineage digest mismatch")


@dataclass(frozen=True)
class V2UnprovenPartition:
    """Source-level stable evidence for notes that have no exact context.

    It is deliberately not an adapter scope and cannot emit adapter/model data.
    """

    source_sha256: str
    source_kind: str
    subject_registry: StableSubjectRegistry
    note_ids: tuple[str, ...]
    source_guard_policy: SourceGuardPolicy
    source_lineage: TrustedSourceLineageSnapshot
    source_manifest: Mapping[str, Any]
    semantic_sha256: str = ""

    def __post_init__(self) -> None:
        if self.source_kind not in {"FACTORY_RAW", "GOLD_REFERENCE_RAW"}:
            raise ValueError("Unproven partition source kind is forbidden")
        _validate_v2_source_identity(self.source_sha256, self.source_kind,
                                     self.source_guard_policy, self.source_lineage,
                                     self.source_manifest)
        if not isinstance(self.subject_registry, StableSubjectRegistry):
            raise TypeError("Unproven partition requires StableSubjectRegistry")
        subjects = tuple(self.subject_registry.subjects); edges = tuple(self.subject_registry.edges)
        if any(item.source_sha256 != self.source_sha256 for item in subjects):
            raise ValueError("Unproven partition contains cross-source subject")
        frozen = FrozenStableSubjectRegistry(subjects, edges)
        object.__setattr__(self, "subject_registry", frozen)
        ids = tuple(sorted(self.note_ids))
        if len(ids) != len(set(ids)): raise ValueError("Unproven note_ids must be unique")
        registered = {item.natural_key.get("note_id") for item in frozen.subjects
                      if item.subject_type == "NOTE"}
        if set(ids) != registered:
            raise ValueError("Unproven note_ids must exactly match stable NOTE registry")
        object.__setattr__(self, "note_ids", ids)
        frozen_manifest = _freeze_json_value(self.source_manifest)
        object.__setattr__(self, "source_manifest", frozen_manifest)
        semantic = {"source_sha256": self.source_sha256, "source_kind": self.source_kind,
            "registry_sha256": frozen.semantic_digest(), "note_ids": ids,
            "source_guard_policy_sha256": self.source_guard_policy.policy_sha256,
            "lineage_sha256": self.source_lineage.semantic_sha256,
            "source_manifest": frozen_manifest}
        object.__setattr__(self, "semantic_sha256", _v2_digest(semantic))


def _freeze_json_value(value: Any) -> Any:
    """Produce a callback-safe immutable tree with no RAW bytes or parser handle."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json_value(item)
                                 for key, item in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(item) for item in value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value.hex()
    raise ValueError(f"Unsupported frozen callback value: {type(value).__name__}")


@dataclass(frozen=True)
class FrozenV2SourceInput:
    """Only information an artifact callback may inspect.

    Deliberately excludes the original record, RAW bytes, ``MidiFile`` and any
    parser callable.  Every nested collection is immutable.
    """

    source_sha256: str
    corpus: str
    member_path: str
    quality_status: str
    metadata: Mapping[str, Any]
    base_note_context: tuple[Mapping[str, Any], ...]
    channel_context: Mapping[str, Any]

    @classmethod
    def create(cls, source_sha256: str, corpus: str, member_path: str,
               quality_status: str, metadata: Mapping[str, Any], notes: Iterable[Mapping[str, Any]],
               channel_context: Mapping[str, Any]) -> "FrozenV2SourceInput":
        return cls(source_sha256, corpus, member_path, quality_status,
                   _freeze_json_value(metadata),
                   tuple(_freeze_json_value(row) for row in notes),
                   _freeze_json_value(channel_context))


def _v2_semantic(value: Any) -> Any:
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, float):
        if not value == value or value in {float("inf"), float("-inf")}:
            raise ValueError("Non-finite schema-v2 float is forbidden")
        return {"binary64_hex": value.hex()}
    if is_dataclass(value):
        return {field.name: _v2_semantic(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _v2_semantic(value[key]) for key in sorted(value)
                if not _is_nonsemantic_key(key)}
    if isinstance(value, (tuple, list)): return [_v2_semantic(item) for item in value]
    if isinstance(value, str):
        path = value.replace("\\", "/")
        if path.startswith("/") or (len(path) > 2 and path[1:3] == ":/"):
            return f"ABSOLUTE_PATH/{PurePosixPath(path).name}"
        return value
    if value is None or isinstance(value, (bool, int)): return value
    raise ValueError(f"Unsupported schema-v2 semantic value: {type(value).__name__}")


def _v2_json(value: Any) -> str:
    return canonical_json(_v2_semantic(value))


def _v2_digest(value: Any) -> str:
    return sha256(_v2_json(value).encode("ascii")).hexdigest()


def canonical_semantic_rows_v2(database_path) -> list[str]:
    database = sqlite3.connect(database_path); database.row_factory = sqlite3.Row
    rows: list[str] = []
    try:
        version = database.execute("SELECT value_json FROM build_info WHERE key='schema_version'").fetchone()
        if version is None or json.loads(version[0]) != V2_SCHEMA_VERSION:
            raise ValueError("Schema-v2 semantic reader rejects v1 database input")
        for table in V2_SEMANTIC_TABLES:
            values = []
            for row in database.execute(f'SELECT * FROM "{table}"'):
                item = dict(row)
                for key, value in tuple(item.items()):
                    if key.endswith("_json"):
                        item[key] = json.loads(value)
                values.append(item)
            values.sort(key=_v2_json)
            rows.extend(_v2_json({"table": table, "row": value}) for value in values)
    finally: database.close()
    return rows


def semantic_digest_v2(database_path) -> str:
    return sha256("\n".join(canonical_semantic_rows_v2(database_path)).encode()).hexdigest()


def _validate_v2_artifacts(artifacts: Any, source_sha256: str, corpus: str,
                           quality_status: str, exact_context_keys: set[str],
                           exact_note_ids_by_context: Mapping[str, set[str]],
                           unproven_note_ids: set[str]) -> V2SourceArtifacts:
    if not isinstance(artifacts, V2SourceArtifacts):
        raise TypeError("v2_source_artifact_factory must return V2SourceArtifacts")
    expected_kind = "FACTORY_RAW" if corpus == "factory" else "GOLD_REFERENCE_RAW"
    snapshot_by_context: dict[str, StructuralSourceSnapshot] = {}
    observed_note_owners: dict[str, str] = {}
    lineage_hashes = set()
    for snapshot in artifacts.context_snapshots:
        _validate_v2_source_identity(snapshot.source_sha256, snapshot.source_kind,
                                     snapshot.source_guard_policy, snapshot.source_lineage,
                                     snapshot.source_manifest)
        if snapshot.source_sha256 != source_sha256:
            raise ValueError("Schema-v2 artifact source SHA mismatch")
        if snapshot.source_kind != expected_kind:
            raise ValueError("Schema-v2 artifact lineage/corpus mismatch")
        scope = next((item for item in snapshot.subject_registry.subjects
                      if item.subject_id == snapshot.scope_subject_id), None)
        exact_key = None if scope is None else scope.natural_key.get("exact_context_key")
        if not exact_key or exact_key not in exact_context_keys or exact_key in snapshot_by_context:
            raise ValueError("Context snapshot requires one unique RAW exact_context subject")
        snapshot_by_context[exact_key] = snapshot
        lineage_hashes.add(snapshot.source_lineage.semantic_sha256)
        for subject in snapshot.subject_registry.subjects:
            if subject.subject_type != "NOTE": continue
            note_id = subject.natural_key.get("note_id")
            if note_id in observed_note_owners:
                raise ValueError("Stable NOTE belongs to more than one context snapshot")
            observed_note_owners[note_id] = exact_key
    partition = artifacts.unproven_partition
    if partition is not None:
        if partition.source_sha256 != source_sha256 or partition.source_kind != expected_kind:
            raise ValueError("Unproven partition source/corpus mismatch")
        lineage_hashes.add(partition.source_lineage.semantic_sha256)
        if set(partition.note_ids) != unproven_note_ids:
            raise ValueError("Unproven partition must contain every non-exact RAW note exactly once")
    elif unproven_note_ids:
        raise ValueError("Non-exact RAW notes require an unproven preservation partition")
    if len(lineage_hashes) != 1:
        raise ValueError("Context snapshots must share one source lineage")
    expected_note_owners = {note_id: key for key, values in exact_note_ids_by_context.items()
                            for note_id in values}
    if observed_note_owners != expected_note_owners:
        raise ValueError("Context snapshots must partition every exact RAW note exactly once")
    if set(observed_note_owners).intersection(unproven_note_ids):
        raise ValueError("Unproven RAW note cannot enter an exact context snapshot")
    for observation in artifacts.factory_observations:
        if (not isinstance(observation, PhaseObservation) or observation.source_sha256 != source_sha256 or
                corpus != "factory" or quality_status != "NORMAL" or
                observation.authority != "FACTORY" or observation.source_quality != quality_status or
                observation.context_status != "EXACT_CONTEXT_MATCH" or
                observation.exact_context_key not in snapshot_by_context):
            raise ValueError("Factory-only model input contract violated")
    for observation in artifacts.reference_observations:
        if (not isinstance(observation, PhaseObservation) or observation.source_sha256 != source_sha256 or
                corpus not in {"gold", "reference"} or
                quality_status != "NORMAL" or observation.source_quality != quality_status or
                observation.context_status != "EXACT_CONTEXT_MATCH" or
                observation.exact_context_key not in snapshot_by_context or
                observation.authority not in {"REFERENCE", "GOLD_REFERENCE"}):
            raise ValueError("Reference observation contract violated")
    return artifacts


def event_slot_key_from_evidence(exact_context_key: str, note_number: int,
                                 bar_start_tick: int, bar_end_tick: int,
                                 onset_tick: int) -> str:
    """Cross-source slot identity derived only from exact musical evidence."""
    if not exact_context_key or bar_end_tick <= bar_start_tick:
        raise ValueError("Exact context and valid bar interval are required")
    phase = Fraction(onset_tick - bar_start_tick, bar_end_tick - bar_start_tick)
    return _v2_digest(["EVENT_SLOT_V2", exact_context_key, int(note_number),
                       phase.numerator, phase.denominator])


def _observation_anchor(snapshot: StructuralSourceSnapshot,
                        observation: PhaseObservation) -> dict[str, Any]:
    """Prove an observation against stable NOTE/EVENT/CLUSTER/BAR evidence."""
    subjects = {item.subject_id: item for item in snapshot.subject_registry.subjects}
    # The stable slot subject is selected by matching the cross-source slot
    # semantic key against every exact NOTE extraction row.
    candidates = []
    for candidate in snapshot.notes:
        candidate_bar = subjects.get(candidate.bar_subject_id)
        if candidate_bar is None: continue
        derived = event_slot_key_from_evidence(observation.exact_context_key,
            candidate.pitch, int(candidate_bar.natural_key["start_tick"]),
            int(candidate_bar.natural_key["end_tick"]), int(candidate.start_tick))
        if derived == observation.event_slot_key:
            candidates.append(candidate)
    if len(candidates) != 1:
        raise ValueError("Observation event_slot_key must resolve one registered stable NOTE subject")
    note = candidates[0]
    slot = subjects.get(note.note_subject_id)
    if slot is None or slot.subject_type != "NOTE":
        raise ValueError("Observation event slot stable NOTE subject is missing")
    note_rows = {item.note_subject_id: item for item in snapshot.notes}
    note = note_rows.get(slot.subject_id)
    if note is None:
        raise ValueError("Observation slot NOTE is missing exact extraction evidence")
    if observation.bar_id != note.bar_subject_id:
        raise ValueError("Observation bar_id does not match stable NOTE/BAR evidence")
    bar = subjects.get(note.bar_subject_id)
    cluster = subjects.get(note.onset_cluster_id)
    if bar is None or bar.subject_type != "BAR" or cluster is None or cluster.subject_type != "ONSET_CLUSTER":
        raise ValueError("Observation stable BAR/ONSET_CLUSTER evidence is missing")
    edges = {(item.edge_type, item.parent_subject_id, item.child_subject_id)
             for item in snapshot.subject_registry.edges}
    # NOTE_HAS_ON_EVENT is NOTE -> EVENT by contract; retain the explicit
    # spelling here rather than inferring from cluster membership/order.
    on_events = tuple(item.child_subject_id for item in snapshot.subject_registry.edges
                      if item.edge_type == "NOTE_HAS_ON_EVENT" and
                      item.parent_subject_id == slot.subject_id)
    if len(on_events) != 1:
        raise ValueError("Observation NOTE requires exactly one stable NOTE_HAS_ON_EVENT edge")
    on_event = subjects.get(on_events[0])
    if on_event is None or on_event.subject_type != "EVENT" or on_event.natural_key.get("event_kind") != "NOTE_ON":
        raise ValueError("Observation on-event evidence is not a canonical NOTE_ON subject")
    if on_event.subject_id not in tuple(cluster.natural_key.get("on_event_ids", ())):
        raise ValueError("Observation NOTE_ON event is absent from its stable onset cluster")
    if ("ONSET_CLUSTER_CONTAINS_NOTE", cluster.subject_id, slot.subject_id) not in edges:
        raise ValueError("Observation cluster/note membership edge is missing")
    if ("BAR_CONTAINS_ONSET_CLUSTER", bar.subject_id, cluster.subject_id) not in edges:
        raise ValueError("Observation bar/cluster membership edge is missing")
    scope = subjects.get(snapshot.scope_subject_id)
    if (scope is None or scope.natural_key.get("exact_context_key") != observation.exact_context_key or
            ("EXACT_CONTEXT_CONTAINS_NOTE", scope.subject_id, slot.subject_id) not in edges):
        raise ValueError("Observation exact-context stable membership is missing")
    bar_start = int(bar.natural_key.get("start_tick"))
    bar_end = int(bar.natural_key.get("end_tick"))
    phase_tick = int(note.start_tick)
    expected_phase = Fraction(phase_tick - bar_start, bar_end - bar_start)
    expected_resolution = Fraction(1, 2 * (bar_end - bar_start))
    if observation.phase != expected_phase or observation.half_tick_resolution != expected_resolution:
        raise ValueError("Observation phase/resolution contradicts stable tick evidence")
    return {"event_slot_subject_id": slot.subject_id,
            "on_event_subject_id": on_event.subject_id,
            "onset_cluster_subject_id": cluster.subject_id,
            "note_subject_id": slot.subject_id, "bar_id": bar.subject_id,
            "phase_tick": phase_tick, "bar_start_tick": bar_start,
            "bar_end_tick": bar_end}


def _insert_v2_subjects(db: sqlite3.Connection, snapshot: StructuralSourceSnapshot) -> None:
    for subject in snapshot.subject_registry.subjects:
        record = subject.semantic_record
        row = (subject.subject_id, subject.source_sha256, subject.subject_type,
               subject.contract_version, _v2_json(subject.natural_key), _v2_json(record))
        previous = db.execute("SELECT * FROM stable_subjects WHERE subject_id=?",
                              (subject.subject_id,)).fetchone()
        if previous is None: db.execute("INSERT INTO stable_subjects VALUES(?,?,?,?,?,?)", row)
        elif tuple(previous) != row: raise ValueError("Cross-context stable subject contradiction")
    for edge in snapshot.subject_registry.edges:
        record = {"edge_id": edge.edge_id, "edge_type": edge.edge_type,
            "source_sha256": edge.source_sha256, "contract_version": edge.contract_version,
            "parent_subject_id": edge.parent_subject_id, "child_subject_id": edge.child_subject_id}
        row = (edge.edge_id, edge.source_sha256, edge.edge_type, edge.contract_version,
               edge.parent_subject_id, edge.child_subject_id, _v2_json(record))
        previous = db.execute("SELECT * FROM stable_subject_edges WHERE edge_id=?",
                              (edge.edge_id,)).fetchone()
        if previous is None: db.execute("INSERT INTO stable_subject_edges VALUES(?,?,?,?,?,?,?)", row)
        elif tuple(previous) != row: raise ValueError("Cross-context stable edge contradiction")


def _insert_context_membership(db: sqlite3.Connection, snapshot: StructuralSourceSnapshot,
                               exact_context_key: str) -> None:
    for subject in snapshot.subject_registry.subjects:
        semantic = {"source_sha256": snapshot.source_sha256,
            "exact_context_key": exact_context_key,
            "scope_subject_id": snapshot.scope_subject_id, "subject_id": subject.subject_id}
        db.execute("INSERT INTO context_subject_membership VALUES(?,?,?,?,?)", (
            snapshot.source_sha256, exact_context_key, snapshot.scope_subject_id,
            subject.subject_id, _v2_json(semantic)))


def _merged_registry_digest(snapshots: Iterable[StructuralSourceSnapshot]) -> str:
    subjects: dict[str, Any] = {}; edges: dict[str, Any] = {}
    for snapshot in snapshots:
        for subject in snapshot.subject_registry.subjects:
            previous = subjects.setdefault(subject.subject_id, subject.semantic_record)
            if previous != subject.semantic_record:
                raise ValueError("Cross-context stable subject contradiction")
        for edge in snapshot.subject_registry.edges:
            record = {"edge_id": edge.edge_id, "edge_type": edge.edge_type,
                "source_sha256": edge.source_sha256, "contract_version": edge.contract_version,
                "parent_subject_id": edge.parent_subject_id, "child_subject_id": edge.child_subject_id}
            previous = edges.setdefault(edge.edge_id, record)
            if previous != record: raise ValueError("Cross-context stable edge contradiction")
    return _v2_digest({"subjects": [subjects[key] for key in sorted(subjects)],
                       "edges": [edges[key] for key in sorted(edges)]})


def _insert_v2_emission(db: sqlite3.Connection, emission: AdapterEmission) -> None:
    run = emission.run
    db.execute("INSERT INTO adapter_runs VALUES(?,?,?,?,?,?,?,?)", (
        run.run_id, run.source_sha256, run.contract.rule_key, run.contract.adapter_version,
        run.run_status, run.scope_subject_id, run.contract.config_sha256, _v2_json(run)))
    if emission.partition is not None:
        part = emission.partition
        db.execute("INSERT INTO coverage_partitions VALUES(?,?,?,?,?,?)", (
            part.partition_id, part.run_id, part.partition_key, part.stable_scope_id,
            part.status, _v2_json(part)))
    for group in emission.groups:
        db.execute("INSERT INTO protection_groups VALUES(?,?,?,?,?,?)", (
            group.group_id, group.run_id, group.source_sha256, group.rule_key,
            group.per_rule_status, _v2_json(group)))
    for membership in emission.memberships:
        db.execute("INSERT INTO protection_memberships VALUES(?,?,?,?,?)", (
            membership.membership_id, membership.group_id, membership.stable_subject_id,
            membership.membership_role, _v2_json(membership)))


def _install_and_insert_v2_emissions(db: sqlite3.Connection,
                                     snapshot: StructuralSourceSnapshot) -> ProtectionEvidenceRegistry:
    evidence = ProtectionEvidenceRegistry(snapshot.subject_registry)
    emissions = tuple(item for item in build_pre_model_adapter_emissions(snapshot)
                      if item.run.contract.rule_key != "FACTORY_REFERENCE_CONFLICT")
    for emission in emissions:
        emission.install(evidence)
        _insert_v2_emission(db, emission)
    return evidence


def _observation_row(observation: PhaseObservation,
                     anchor: Mapping[str, Any]) -> tuple[Any, ...]:
    return (observation.observation_id, observation.source_sha256, observation.exact_context_key,
            observation.event_slot_key, observation.bar_id,
            anchor["event_slot_subject_id"], anchor["on_event_subject_id"],
            anchor["onset_cluster_subject_id"], anchor["note_subject_id"],
            anchor["phase_tick"], anchor["bar_start_tick"], anchor["bar_end_tick"],
            observation.phase.numerator,
            observation.phase.denominator, observation.half_tick_resolution.numerator,
            observation.half_tick_resolution.denominator, _v2_json(observation))


def _model_status(modality_status: str) -> str:
    if modality_status in {"ASSESSED_UNIMODAL", "ASSESSED_MULTIMODAL", "DEGENERATE_EXACT_REFERENCE"}:
        return "FACTORY_SUFFICIENT"
    if modality_status == "DEFERRED": return "FACTORY_UNAVAILABLE"
    return "FACTORY_INSUFFICIENT"


def _materialize_v2_models(db: sqlite3.Connection) -> dict[tuple[str, str], tuple[str, str, str, str]]:
    keys = db.execute("SELECT DISTINCT exact_context_key,event_slot_key FROM factory_observations ORDER BY 1,2").fetchall()
    results = {}
    for exact_context_key, event_slot_key in keys:
        source_rows = db.execute("SELECT source_sha256,semantic_json FROM factory_observations WHERE exact_context_key=? AND event_slot_key=? ORDER BY source_sha256,bar_id,observation_id",
                                 (exact_context_key, event_slot_key)).fetchall()
        by_source: dict[str, list[str]] = {}
        for source_sha, semantic_json in source_rows:
            by_source.setdefault(source_sha, []).append(semantic_json)
        for source_sha in sorted(by_source):
            observation_payloads = [json.loads(item) for item in by_source[source_sha]]
            observation_sha = _v2_digest(observation_payloads)
            local_id = _v2_digest(["FACTORY_LOCAL_PROFILE_V2", source_sha,
                                   exact_context_key, event_slot_key, observation_sha])
            semantic = {"source_sha256": source_sha, "exact_context_key": exact_context_key,
                "event_slot_key": event_slot_key, "observation_count": len(observation_payloads),
                "observations_sha256": observation_sha}
            db.execute("INSERT INTO factory_local_profiles VALUES(?,?,?,?,?,?,?)", (
                local_id, source_sha, exact_context_key, event_slot_key,
                len(observation_payloads), observation_sha, _v2_json(semantic)))
        factory_rows = db.execute("SELECT semantic_json FROM factory_observations WHERE exact_context_key=? AND event_slot_key=? ORDER BY source_sha256,bar_id,observation_id",
                                  (exact_context_key, event_slot_key)).fetchall()
        observations = tuple(_phase_observation_from_json(row[0]) for row in factory_rows)
        verified = assess_factory_model(observations)
        assessment = verified.assessment
        consensus_observation_sha = _v2_digest([json.loads(row[0]) for row in factory_rows])
        consensus_id = _v2_digest(["FACTORY_CONSENSUS_SLOT_V2", exact_context_key,
                                   event_slot_key, consensus_observation_sha])
        consensus_semantic = {"exact_context_key": exact_context_key,
            "event_slot_key": event_slot_key, "distinct_source_count": len(by_source),
            "bar_observation_count": len(observations),
            "model_eligibility_status": _model_status(assessment.status),
            "observations_sha256": consensus_observation_sha}
        db.execute("INSERT INTO factory_consensus_slots VALUES(?,?,?,?,?,?,?,?)", (
            consensus_id, exact_context_key, event_slot_key, len(by_source), len(observations),
            _model_status(assessment.status), consensus_observation_sha,
            _v2_json(consensus_semantic)))
        model_id = _v2_digest(["FACTORY_MODEL_V2", exact_context_key, event_slot_key,
                               verified.semantic_sha256])
        db.execute("INSERT INTO factory_models VALUES(?,?,?,?,?,?,?,?,?)", (
            model_id, exact_context_key, event_slot_key, _model_status(assessment.status),
            assessment.status, assessment.selected_k, assessment.config_sha256,
            verified.semantic_sha256, _v2_json(verified)))
        for component in assessment.components:
            db.execute("INSERT INTO multimodal_components VALUES(?,?,?)",
                       (model_id, component.component_id, _v2_json(component)))
        reference_rows = db.execute("SELECT semantic_json FROM reference_observations WHERE exact_context_key=? AND event_slot_key=? ORDER BY source_sha256,bar_id,observation_id",
                                    (exact_context_key, event_slot_key)).fetchall()
        references = tuple(_phase_observation_from_json(row[0]) for row in reference_rows)
        relationship = assess_reference_relationship(verified, references)
        relationship_id = _v2_digest(["REFERENCE_RELATIONSHIP_V2", model_id,
                                      relationship.semantic_sha256])
        db.execute("INSERT INTO reference_relationships VALUES(?,?,?,?,?,?)", (
            relationship_id, model_id, relationship.status, relationship.config_sha256,
            relationship.semantic_sha256, _v2_json(relationship),))
        db.execute("INSERT INTO model_eligibility VALUES(?,?,?,?)", (
            exact_context_key, event_slot_key, _model_status(assessment.status),
            _v2_json(assessment.reason_codes)))
        results[(exact_context_key, event_slot_key)] = (
            model_id, _model_status(assessment.status), assessment.status, relationship.status)
    return results


def _phase_observation_from_json(payload: str) -> PhaseObservation:
    value = json.loads(payload)
    def fraction(item): return Fraction(int(item["numerator"]), int(item["denominator"]))
    return PhaseObservation(value["source_sha256"], value["bar_id"], fraction(value["phase"]),
        fraction(value["half_tick_resolution"]), value["event_slot_key"], value["exact_context_key"],
        value["observation_id"], value["authority"], value["source_quality"], value["context_status"])


def _population_sha256(values: Iterable[str]) -> str:
    return sha256(canonical_json(sorted(values)).encode("ascii")).hexdigest()


def _post_model_emission(source_sha: str, scope_subject_id: str, universe: tuple[str, ...],
                         applicable: tuple[str, ...], detected: tuple[str, ...],
                         partial: tuple[str, ...], deferred: tuple[str, ...],
                         model_count: int) -> AdapterEmission:
    rule = "FACTORY_REFERENCE_CONFLICT"
    contract = AdapterContract(rule, ADAPTER_VERSION_BY_RULE[rule], "POST_MODEL_REQUIRED",
                               APPLICABILITY_PREDICATE_VERSION_BY_RULE[rule])
    if deferred:
        run_status, scanned, resolved = "DEFERRED_POST_MODEL", (), ()
    elif partial:
        run_status, scanned = "PARTIAL", applicable
        resolved = tuple(item for item in applicable if item not in set(partial))
    elif applicable:
        run_status = "COMPLETE"; scanned = resolved = applicable
    else:
        run_status = "NOT_APPLICABLE"; scanned = resolved = ()
    population = dict(source_sha256=source_sha, contract=contract, scope_type="EXACT_CONTEXT",
        scope_subject_id=scope_subject_id,
        subject_universe_query_version=SUBJECT_UNIVERSE_QUERY_VERSION_BY_RULE[rule],
        subject_universe_count=len(universe), subject_universe_sha256=_population_sha256(universe),
        applicable_count=len(applicable), applicable_universe_sha256=_population_sha256(applicable),
        scanned_count=len(scanned), scanned_universe_sha256=_population_sha256(scanned),
        resolved_count=len(resolved), resolved_universe_sha256=_population_sha256(resolved),
        protected_count=len(detected), ambiguous_count=0,
        input_sha256=_v2_digest([source_sha, scope_subject_id, universe, applicable]),
        dependency_sha256=_v2_digest(["POST_MODEL", model_count]), run_status=run_status)
    groups = (); memberships = (); partition = None
    if run_status in {"COMPLETE", "PARTIAL"}:
        evidence_sha = _v2_digest(["REFERENCE_CONTRADICTION", detected])
        provisional = AdapterRun(result_sha256="0" * 64, **population)
        provisional_partition = CoveragePartition(provisional.run_id,
            "SOURCE_COMPLETE" if run_status == "COMPLETE" else "SOURCE_PARTIAL",
            scope_subject_id, len(universe), len(applicable), len(scanned), len(resolved),
            _population_sha256(universe), _population_sha256(applicable),
            _population_sha256(scanned), _population_sha256(resolved), evidence_sha,
            "COMPLETE" if run_status == "COMPLETE" else "PARTIAL")
        result_sha = canonical_partition_result_sha256(provisional, (provisional_partition,))
        run = AdapterRun(result_sha256=result_sha, **population)
        partition = CoveragePartition(run.run_id, provisional_partition.partition_key,
            scope_subject_id, len(universe), len(applicable), len(scanned), len(resolved),
            _population_sha256(universe), _population_sha256(applicable),
            _population_sha256(scanned), _population_sha256(resolved), evidence_sha,
            provisional_partition.status)
        if detected:
            group = ProtectionGroup(run.run_id, source_sha, rule, contract.adapter_version,
                ["REFERENCE_CONTRADICTION", scope_subject_id], "DETECTED", evidence_sha)
            groups = (group,)
            memberships = tuple(ProtectionGroupMembership(group.group_id, item)
                                for item in detected)
    else:
        run = AdapterRun(result_sha256=_v2_digest([run_status, deferred, partial]), **population)
    return AdapterEmission(run, partition, groups, memberships, universe, applicable,
                           tuple(scanned), tuple(resolved))


def _install_post_model_conflict_runs(
    db: sqlite3.Connection,
    models: Mapping[tuple[str, str], tuple[str, str, str, str]],
) -> int:
    membership_total = 0
    sources = tuple(row[0] for row in db.execute(
        "SELECT source_sha256 FROM source_context_v2 ORDER BY source_sha256"))
    for source_sha in sources:
        contexts = db.execute("SELECT DISTINCT exact_context_key,scope_subject_id FROM context_subject_membership WHERE source_sha256=? ORDER BY 1,2",
                              (source_sha,)).fetchall()
        for context_key, scope_subject_id in contexts:
            universe = tuple(row[0] for row in db.execute(
                "SELECT subject_id FROM context_subject_membership WHERE source_sha256=? AND exact_context_key=? ORDER BY subject_id",
                (source_sha, context_key)))
            rows = db.execute("SELECT note_subject_id,exact_context_key,event_slot_key FROM context_eligibility WHERE source_sha256=? AND exact_context_key=? ORDER BY note_subject_id",
                              (source_sha, context_key)).fetchall()
            applicable = tuple(subject_id for subject_id, exact_key, _slot in rows if exact_key)
            detected: list[str] = []; partial: list[str] = []; deferred: list[str] = []
            for subject_id, exact_key, event_slot in rows:
                model = models.get((exact_key, event_slot))
                if model is None or model[3] == "DEFERRED_FACTORY_MODEL_UNSTABLE": deferred.append(subject_id)
                elif model[3] == "POST_MODEL_PARTIAL": partial.append(subject_id)
                elif model[3] == "POTENTIAL_CONTRADICTION": detected.append(subject_id)
            emission = _post_model_emission(source_sha, scope_subject_id, universe, applicable,
                tuple(detected), tuple(partial), tuple(deferred), len(models))
            _insert_v2_emission(db, emission)
            membership_total += len(emission.memberships)
    return membership_total


def _insert_v2_authorization(db: sqlite3.Connection,
                             models: Mapping[tuple[str, str], tuple[str, str, str, str]]) -> None:
    rows = db.execute("SELECT source_sha256,note_subject_id,exact_context_key,event_slot_key,context_status,quality_status,context_json FROM context_eligibility ORDER BY 1,2").fetchall()
    for source_sha, subject_id, exact_key, event_slot, context_status, quality, context_json in rows:
        context_payload = json.loads(context_json)
        statuses = dict(context_payload["pre_model_rule_statuses"])
        model_entry = models.get((exact_key, event_slot)) if exact_key else None
        if model_entry is None:
            factory_status, modality_status, reference_status = (
                "FACTORY_UNAVAILABLE", "DEFERRED", "DEFERRED_FACTORY_MODEL_UNSTABLE")
        else:
            _model_id, factory_status, modality_status, reference_status = model_entry
        statuses["FACTORY_REFERENCE_CONFLICT"] = (
            "DETECTED" if reference_status == "POTENTIAL_CONTRADICTION" else
            "PARTIAL_UNRESOLVED" if reference_status == "POST_MODEL_PARTIAL" else
            "DEFERRED" if reference_status == "DEFERRED_FACTORY_MODEL_UNSTABLE" else "CLEAR")
        protection_status = aggregate_protection_status(statuses)
        core_complete = all(statuses[rule] not in {"PARTIAL_UNRESOLVED", "DEFERRED"}
                            for rule in REQUIRED_PROTECTION_RULES
                            if rule != "FACTORY_REFERENCE_CONFLICT")
        decision = final_analysis_authorization(source_quality_status=quality,
            context_eligibility_status=context_status, core_scan_complete=core_complete,
            protection_status=protection_status, factory_model_status=factory_status,
            modality_status=modality_status, reference_relationship_status=reference_status)
        semantic = {"per_rule_statuses": statuses, "decision": decision,
                    "context": context_payload["note_context"]}
        db.execute("INSERT INTO analysis_authorization VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
            source_sha, subject_id, exact_key, event_slot, protection_status, factory_status,
            modality_status, reference_status, decision.authorization_status,
            int(decision.analysis_allowed), "ANALYZE_ONLY", _v2_json(semantic)))


def build_context_qualified_database_v2(source_records: Iterable[Mapping[str, Any]], output_path,
                                        config: Mapping[str, Any]) -> dict:
    """Atomic, disk-backed, single-parse schema-v2 RAW rebuild.

    ``v2_source_artifact_factory`` receives one :class:`FrozenV2SourceInput`.
    RAW bytes, the mutable caller record, parsed ``MidiFile`` and parser are
    intentionally not exposed.  It must return accepted A/B/C objects.
    """
    if not isinstance(config, Mapping): raise TypeError("Schema-v2 config is required")
    cfg = dict(config); _reject_forbidden_fields(cfg, "config")
    artifact_factory = cfg.pop("v2_source_artifact_factory", None)
    if not callable(artifact_factory):
        raise ValueError("Schema-v2 full RAW rebuild requires v2_source_artifact_factory")
    forbidden_config = {"calibration_path", "consensus_path", "legacy_database", "v1_database",
                        "model_input", "factory_model_input"}
    if forbidden_config.intersection(cfg):
        raise ValueError("Schema-v2 rejects v1 database/model input")
    output_path = Path(output_path); temp = output_path.with_suffix(output_path.suffix + ".v2.tmp")
    temp.unlink(missing_ok=True)
    forbidden = set(SIX_SONG_FORBIDDEN_SHA256S) | {
        str(value).lower() for value in cfg.get("forbidden_sha256", ())}
    negative = validate_negative_manifest(cfg.get("negative_manifest", {"schema_version": 1, "cases": []}), forbidden)
    db = sqlite3.connect(temp); db.execute("PRAGMA foreign_keys=ON"); db.executescript(V2_SCHEMA)
    source_count = parse_count = note_count = peak_source_notes = context_snapshot_count = 0
    peak_source_bytes = peak_source_subjects = peak_source_observations = 0
    spool_peak_bytes = 0
    dense_equivalent = membership_count = 0
    seen_sources: set[str] = set()
    try:
        stored_config = {key: value for key, value in cfg.items() if key != "negative_manifest"}
        config_payload = {"builder_version": V2_BUILDER_VERSION,
            "protection_config": canonical_protection_config(),
            "protection_config_sha256": protection_config_sha256(),
            "model_config_sha256": model_config_sha256(),
            "reference_config_sha256": reference_config_sha256(),
            "negative_manifest_sha256": negative["manifest_sha256"],
            "caller_config": _normalize(stored_config)}
        build_config_sha = _v2_digest(config_payload)
        db.executemany("INSERT INTO build_info VALUES(?,?)", (
            ("schema_version", _json(V2_SCHEMA_VERSION)), ("builder_version", _json(V2_BUILDER_VERSION)),
            ("capability", _json("ANALYZE_ONLY")), ("mutation_capability", _json("NONE")),
            ("build_config_sha256", _json(build_config_sha)), ("config", _v2_json(config_payload))))
        contract_semantic = {"builder_version": V2_BUILDER_VERSION,
            "schema_version": V2_SCHEMA_VERSION, "build_config_sha256": build_config_sha,
            "protection_config_sha256": protection_config_sha256(),
            "model_config_sha256": model_config_sha256(),
            "reference_config_sha256": reference_config_sha256(),
            "negative_manifest_sha256": negative["manifest_sha256"]}
        contract_id = _v2_digest(["BUILD_CONTRACT_V2", contract_semantic])
        db.execute("INSERT INTO build_contract_v2 VALUES(?,?,?,?,?,?,?,?,?)", (
            contract_id, V2_BUILDER_VERSION, V2_SCHEMA_VERSION, build_config_sha,
            protection_config_sha256(), model_config_sha256(), reference_config_sha256(),
            negative["manifest_sha256"], _v2_json(contract_semantic)))
        for record in source_records:
            if not isinstance(record, Mapping): raise TypeError("RAW source record must be a mapping")
            _reject_forbidden_fields(record, "source_record")
            data = bytes(_record_bytes(record)); before = sha256(data).hexdigest()
            declared = str(record.get("source_sha256", before)).lower()
            if declared != before: raise ValueError("RAW source SHA mismatch")
            if declared in forbidden: raise ValueError("Forbidden source SHA")
            if declared in seen_sources: raise ValueError("Duplicate RAW source natural key")
            seen_sources.add(declared)
            corpus = str(record.get("corpus", "")).lower()
            if corpus not in {"factory", "gold", "reference"}: raise ValueError("Unsupported corpus")
            if record.get("is_optimizer_output") or record.get("is_repaired_output"):
                raise ValueError("Optimizer/repaired source contamination")
            member = PurePosixPath(str(record.get("member_path", ""))).as_posix()
            if not member or member.startswith("/") or ".." in PurePosixPath(member).parts:
                raise ValueError("Invalid member path")
            quality = str(record.get("quality_status", "INVALID"))
            metadata = dict(record.get("metadata") or {})
            midi = parse_midi(data); parse_count += 1; source_count += 1
            timelines = build_channel_context(midi, declared)
            base_notes = join_note_context(midi, declared, metadata, quality,
                                           required_protection_rules=())
            exact_context_keys = {str(item["exact_context_key"]) for item in base_notes
                                  if item.get("exact_context_key")}
            exact_note_ids_by_context: dict[str, set[str]] = {}
            for item in base_notes:
                if item.get("exact_context_key"):
                    exact_note_ids_by_context.setdefault(str(item["exact_context_key"]), set()).add(
                        str(item["note_id"]))
            unproven_note_ids = {str(item["note_id"]) for item in base_notes
                                 if not item.get("exact_context_key")}
            callback_input = FrozenV2SourceInput.create(declared, corpus, member, quality,
                                                        metadata, base_notes, timelines)
            artifacts = _validate_v2_artifacts(
                artifact_factory(callback_input), declared,
                corpus, quality, exact_context_keys, exact_note_ids_by_context,
                unproven_note_ids)
            if sha256(data).hexdigest() != before:
                raise ValueError("RAW source mutated during artifact callback")
            snapshots = artifacts.context_snapshots
            snapshot_by_context = {}
            for snapshot in snapshots:
                scope = next(item for item in snapshot.subject_registry.subjects
                             if item.subject_id == snapshot.scope_subject_id)
                snapshot_by_context[str(scope.natural_key["exact_context_key"])] = snapshot
            context_snapshot_count += len(snapshots)
            lineage_hashes = {item.source_lineage.semantic_sha256 for item in snapshots}
            source_kinds = {item.source_kind for item in snapshots}
            if artifacts.unproven_partition is not None:
                lineage_hashes.add(artifacts.unproven_partition.source_lineage.semantic_sha256)
                source_kinds.add(artifacts.unproven_partition.source_kind)
            if len(lineage_hashes) != 1 or len(source_kinds) != 1:
                raise ValueError("Context snapshot source metadata contradiction")
            registries = list(snapshots)
            if artifacts.unproven_partition is not None:
                registries.append(artifacts.unproven_partition)
            merged_registry_sha = _merged_registry_digest(registries)
            db.execute("INSERT INTO source_context_v2 VALUES(?,?,?,?,?,?,?,?,?)", (
                declared, corpus, next(iter(source_kinds)), member, quality, _v2_json(metadata),
                next(iter(lineage_hashes)), merged_registry_sha,
                _v2_json({"context_snapshots": [{"exact_context_key": key,
                    "snapshot_semantic_sha256": snapshot_by_context[key].semantic_sha256,
                    "scope_subject_id": snapshot_by_context[key].scope_subject_id,
                    "manifest": snapshot_by_context[key].source_manifest}
                    for key in sorted(snapshot_by_context)],
                    "unproven_partition": None if artifacts.unproven_partition is None else {
                        "semantic_sha256": artifacts.unproven_partition.semantic_sha256,
                        "note_count": len(artifacts.unproven_partition.note_ids)}})))
            evidence_by_note = {}
            note_subjects = {}; extracted_notes = {}; subject_map = {}
            unique_subject_ids = set()
            for exact_key in sorted(snapshot_by_context):
                snapshot = snapshot_by_context[exact_key]
                _insert_v2_subjects(db, snapshot)
                _insert_context_membership(db, snapshot, exact_key)
                evidence = _install_and_insert_v2_emissions(db, snapshot)
                membership_count += len(evidence.memberships)
                unique_subject_ids.update(item.subject_id for item in snapshot.subject_registry.subjects)
                for subject in snapshot.subject_registry.subjects:
                    subject_map[subject.subject_id] = subject
                    if subject.subject_type == "NOTE" and isinstance(subject.natural_key, Mapping):
                        note_subjects[subject.natural_key.get("note_id")] = subject.subject_id
                        evidence_by_note[subject.subject_id] = evidence
                extracted_notes.update({item.note_subject_id: item for item in snapshot.notes})
            if artifacts.unproven_partition is not None:
                partition = artifacts.unproven_partition
                _insert_v2_subjects(db, partition)
                unique_subject_ids.update(item.subject_id for item in partition.subject_registry.subjects)
                for subject in partition.subject_registry.subjects:
                    subject_map[subject.subject_id] = subject
                    if subject.subject_type == "NOTE" and isinstance(subject.natural_key, Mapping):
                        note_subjects[subject.natural_key.get("note_id")] = subject.subject_id
            dense_equivalent += len(unique_subject_ids) * len(REQUIRED_PROTECTION_RULES)
            source_note_count = 0
            for note in base_notes:
                subject_id = note_subjects.get(note["note_id"])
                if subject_id is None: raise ValueError("Stable NOTE subject missing for RAW note")
                context_status = "EXACT_CONTEXT_MATCH" if note.get("exact_context_key") else "CONTEXT_UNPROVEN"
                if context_status == "EXACT_CONTEXT_MATCH":
                    evidence = evidence_by_note.get(subject_id)
                    if evidence is None: raise ValueError("Stable NOTE protection context missing")
                    pre_model_statuses = {rule: sparse_rule_status(evidence, subject_id, rule)
                        for rule in REQUIRED_PROTECTION_RULES
                        if rule != "FACTORY_REFERENCE_CONFLICT"}
                    extracted = extracted_notes.get(subject_id)
                    if extracted is None: raise ValueError("Stable NOTE extraction row missing")
                    stable_bar = subject_map.get(extracted.bar_subject_id)
                    if stable_bar is None: raise ValueError("Stable NOTE BAR subject missing")
                    event_slot = event_slot_key_from_evidence(note["exact_context_key"], extracted.pitch,
                        int(stable_bar.natural_key["start_tick"]),
                        int(stable_bar.natural_key["end_tick"]), extracted.start_tick)
                else:
                    pre_model_statuses = {rule: "DEFERRED" for rule in REQUIRED_PROTECTION_RULES
                                          if rule != "FACTORY_REFERENCE_CONFLICT"}
                    event_slot = _v2_digest(["UNPROVEN_EVENT_SLOT_V2", declared, subject_id])
                db.execute("INSERT INTO context_eligibility VALUES(?,?,?,?,?,?,?,?)", (
                    declared, subject_id, note["note_id"], note.get("exact_context_key"), event_slot, context_status,
                    quality, _v2_json({"note_context": note,
                                       "pre_model_rule_statuses": pre_model_statuses})))
                source_note_count += 1
            note_count += source_note_count; peak_source_notes = max(peak_source_notes, source_note_count)
            peak_source_bytes = max(peak_source_bytes, len(data))
            peak_source_subjects = max(peak_source_subjects, len(unique_subject_ids))
            peak_source_observations = max(peak_source_observations,
                len(artifacts.factory_observations) + len(artifacts.reference_observations))
            for observation in artifacts.factory_observations:
                anchor = _observation_anchor(snapshot_by_context[observation.exact_context_key], observation)
                db.execute("INSERT INTO factory_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           _observation_row(observation, anchor))
            for observation in artifacts.reference_observations:
                anchor = _observation_anchor(snapshot_by_context[observation.exact_context_key], observation)
                db.execute("INSERT INTO reference_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    observation.observation_id, observation.source_sha256, observation.exact_context_key,
                    observation.event_slot_key, observation.bar_id,
                    anchor["event_slot_subject_id"], anchor["on_event_subject_id"],
                    anchor["onset_cluster_subject_id"], anchor["note_subject_id"],
                    anchor["phase_tick"], anchor["bar_start_tick"], anchor["bar_end_tick"], observation.authority,
                    _v2_json(observation)))
            if sha256(data).hexdigest() != before: raise ValueError("RAW source mutated")
            db.commit()  # disk-backed spool boundary; final path remains untouched
            spool_peak_bytes = max(spool_peak_bytes, temp.stat().st_size)
        if source_count == 0: raise ValueError("At least one RAW source is required")
        models = _materialize_v2_models(db)
        membership_count += _install_post_model_conflict_runs(
            db, models)
        _insert_v2_authorization(db, models)
        for case in negative["cases"]:
            db.execute("INSERT INTO negative_corpus_cases_v2 VALUES(?,?,?)",
                       (case["source_class"], case["case_id"], _v2_json(case)))
        db.commit()
        spool_peak_bytes = max(spool_peak_bytes, temp.stat().st_size)
        assert_analyze_only_schema(temp)
        digest = semantic_digest_v2(temp)
        db.execute("INSERT INTO semantic_digest VALUES('SHA-256',2,?)", (digest,)); db.commit()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        fk = db.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or fk: raise ValueError(f"SQLite validation failed: {integrity}, fk={len(fk)}")
        table_counts = {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                        for table in ("stable_subjects", "stable_subject_edges", "adapter_runs",
                            "coverage_partitions", "protection_groups", "protection_memberships",
                            "factory_local_profiles", "factory_consensus_slots", "factory_models",
                            "multimodal_components", "reference_relationships",
                            "analysis_authorization")}
        final_bytes = temp.stat().st_size
        spool_peak_bytes = max(spool_peak_bytes, final_bytes)
        db.close(); os.replace(temp, output_path)
        sparse_ratio = (Decimal(membership_count) / Decimal(dense_equivalent)
                        if dense_equivalent else Decimal(0))
        return {"schema_version": 2, "builder_version": V2_BUILDER_VERSION,
            "sources": source_count, "parse_count": parse_count, "notes": note_count,
            "context_snapshot_count": context_snapshot_count,
            "runtime_metrics": {"parse_count": parse_count,
                "peak_source_notes": peak_source_notes,
                "peak_source_bytes": peak_source_bytes,
                "peak_source_subjects": peak_source_subjects,
                "peak_source_observations": peak_source_observations,
                "spool_peak_bytes": spool_peak_bytes, "final_bytes": final_bytes},
            "peak_source_notes": peak_source_notes, "dense_equivalent_rows": dense_equivalent,
            "sparse_membership_rows": membership_count, "sparse_ratio": str(sparse_ratio),
            "model_contexts": len(models), "spool_peak_bytes": spool_peak_bytes,
            "final_bytes": final_bytes,
            "table_counts": table_counts,
            "semantic_digest": digest, "build_config_sha256": build_config_sha,
            "capability": "ANALYZE_ONLY", "mutation_capability": "NONE",
            "status": "BUILD_COMPLETE"}
    except Exception:
        db.close(); temp.unlink(missing_ok=True); raise