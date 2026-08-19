"""Phase-independent Factory structural identities for X10 calibration.

This module is deliberately limited to structural identity and provenance.  It
does not fit distributions or evaluate uploaded material.  Public identity
builders accept typed primitives only; stored provenance is never an ancestor
of an identity digest.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import unicodedata
from typing import Any, Iterable

from .rhythm_context_models import semantic_digest_v2
from .rhythm_protection import ValidatedSubjectRegistrySnapshot
from .rhythm_protection_adapters import (
    ALLOWED_LINEAGE_PARENT_CLASSES,
    FORBIDDEN_SOURCE_KINDS,
    SIX_SONG_FORBIDDEN_SHA256S,
    SourceGuardPolicy,
    StructuralSourceSnapshot,
    TrustedSourceLineageSnapshot,
    trusted_source_guard_policy,
)
from .rhythm_subject_registry import StableSubject, StableSubjectEdge, canonical_json


CONTEXT_CONTRACT = "X10_CALIBRATION_CONTEXT_V1"
SLOT_CONTRACT = "X10_STRUCTURAL_SLOT_V1"
BUILD_CONTRACT = "X10_STRUCTURAL_REGISTRY_BUILD_V1"
TEMPO_CONTRACT = "X10_TEMPO_REGIME_V1"
CAPABILITY = "ANALYZE_ONLY"
MUTATION_CAPABILITY = "NONE"
PRODUCTION_AUTHORITY_STATUS = "NOT_PROVABLE"
CALIBRATION_ENVELOPE_ALLOWED = False

SECTIONS = ("INTRO", "VARIATION", "FILL", "BREAK", "ENDING", "OTHER_EXACT")
CV_STATUSES = ("NONE", "EXACT")
VOICE_POLICIES = ("TRANSPOSING_LOWEST_ANCHOR", "EXACT_DRUM_LANE")
RESOLUTION_STATUSES = (
    "STRUCTURAL_SLOT_RESOLVED",
    "STRUCTURAL_CONTEXT_UNPROVEN",
    "STRUCTURAL_ALIGNMENT_AMBIGUOUS",
    "STRUCTURAL_DUPLICATE_AMBIGUOUS",
    "STRUCTURAL_VOICE_CROSSING_AMBIGUOUS",
    "STRUCTURAL_OBSERVATION_AMBIGUOUS",
)

_SHA_RE = re.compile(r"[0-9a-f]{64}")
_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_VOICE_RE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_VOICE_FORBIDDEN = ("TICK", "PHASE", "IOI", "DURATION", "VELOCITY", "EVENT", "NOTE_ID", "DIGEST", "SHA")
_STATIC_FORBIDDEN = (
    "user_input", "anomaly", "target", "candidate", "proposal", "simulation",
    "repair", "apply", "writer", "midi_output", "factory_model", "envelope", "delta",
    "reference_overlay",
)


@dataclass(frozen=True)
class AcceptedFactorySourceAnchor:
    """Frozen source facts read from one verified schema-v2 corpus database."""

    source_sha256: str
    quality_status: str
    lineage_sha256: str
    metadata: dict[str, Any]
    source_semantic: dict[str, Any]
    subjects: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    note_contexts: tuple[tuple[str, dict[str, Any]], ...]
    lineage_records: tuple[dict[str, Any], ...]
    source_manifest: dict[str, Any]


@dataclass(frozen=True)
class TestOnlyFactoryCorpusAuthorityEvidence:
    """Integrity evidence for isolated tests; never production authority."""

    authority_scope: str
    authority_id: str
    database_path: str
    database_sha256: str
    schema_v2_semantic_digest: str
    build_config_sha256: str
    sources: tuple[AcceptedFactorySourceAnchor, ...]

    def __post_init__(self) -> None:
        if self.authority_scope != "TEST_ONLY":
            raise ValueError("013C-S cannot issue or accept production authority")
        _require_sha(self.authority_id, "authority_id")

    def source_for(self, source_sha256: str) -> AcceptedFactorySourceAnchor | None:
        return next((item for item in self.sources if item.source_sha256 == source_sha256), None)


class AcceptedFactoryCorpusAuthorityVerifierPort(ABC):
    """Required isolated-test port.  Production authority is not implemented."""

    @abstractmethod
    def verify_factory_corpus_authority(self) -> TestOnlyFactoryCorpusAuthorityEvidence:
        raise NotImplementedError


class _TestOnlyAcceptedFactoryCorpusAuthorityVerifier(AcceptedFactoryCorpusAuthorityVerifierPort):
    """Explicit synthetic-fixture adapter; never production-authoritative."""

    def __init__(self, database_path: str | Path, expected_semantic_digest: str,
                 trusted_lineages: dict[str, TrustedSourceLineageSnapshot],
                 source_manifests: dict[str, dict[str, Any]]) -> None:
        self._database_path = Path(database_path)
        self._database_sha256 = sha256(self._database_path.read_bytes()).hexdigest()
        self._expected = expected_semantic_digest
        self._lineages = dict(trusted_lineages)
        self._manifests = {key: dict(value) for key, value in source_manifests.items()}

    @property
    def test_database_path(self) -> Path:
        return self._database_path

    def verify_factory_corpus_authority(self) -> TestOnlyFactoryCorpusAuthorityEvidence:
        return _verify_test_only_factory_corpus(
            self._database_path, self._database_sha256, self._expected,
            self._lineages, self._manifests)


def _verify_test_only_factory_corpus(database_path: str | Path,
                                     expected_database_sha256: str,
                                     expected_semantic_digest: str,
                                     trusted_lineages: dict[str, TrustedSourceLineageSnapshot],
                                     source_manifests: dict[str, dict[str, Any]],
                                     ) -> TestOnlyFactoryCorpusAuthorityEvidence:
    """Test-only verifier.  Production has no raw path/digest fallback."""
    expected = _require_sha(expected_semantic_digest, "expected_semantic_digest")
    path = Path(database_path)
    before = sha256(path.read_bytes()).hexdigest()
    if before != _require_sha(expected_database_sha256, "expected_database_sha256"):
        raise ValueError("Accepted schema-v2 authority database changed after verifier pinning")
    uri = f"file:{path.resolve().as_posix()}?mode=ro&immutable=1"
    db = sqlite3.connect(uri, uri=True); db.row_factory = sqlite3.Row
    try:
        required = {"build_info", "build_contract_v2", "source_context_v2", "stable_subjects",
                    "stable_subject_edges", "context_eligibility", "semantic_digest"}
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required.issubset(present):
            raise ValueError("Accepted schema-v2 database is missing authority tables")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute(
                "PRAGMA foreign_key_check").fetchall():
            raise ValueError("Accepted schema-v2 database integrity/FK failure")
        version = db.execute("SELECT value_json FROM build_info WHERE key='schema_version'").fetchone()
        if version is None or json.loads(version[0]) != 2:
            raise ValueError("Accepted corpus must use schema-v2")
        roots = db.execute("SELECT digest FROM semantic_digest WHERE digest_algorithm='SHA256' AND schema_version=2").fetchall()
        if len(roots) != 1 or roots[0][0] != expected:
            raise ValueError("Accepted schema-v2 semantic root mismatch")
        actual = semantic_digest_v2(path)
        if actual != expected:
            raise ValueError("Accepted schema-v2 semantic rows do not match their root")
        contracts = db.execute("SELECT build_config_sha256,schema_version FROM build_contract_v2").fetchall()
        if len(contracts) != 1 or contracts[0][1] != 2:
            raise ValueError("Accepted schema-v2 build contract is not singular")
        build_config = _require_sha(contracts[0][0], "build_config_sha256")
        anchors = []
        for row in db.execute("SELECT * FROM source_context_v2 WHERE corpus='factory' ORDER BY source_sha256"):
            if row["source_kind"] != "FACTORY_RAW":
                raise ValueError("Accepted Factory corpus contains a non-Factory source class")
            source_sha = _require_sha(row["source_sha256"], "source_sha256")
            contexts = []
            for value in db.execute("SELECT note_subject_id,context_status,quality_status,context_json "
                                    "FROM context_eligibility WHERE source_sha256=? ORDER BY note_subject_id",
                                    (source_sha,)):
                if value["context_status"] == "EXACT_CONTEXT_MATCH":
                    contexts.append((value["note_subject_id"], json.loads(value["context_json"])))
            subjects = tuple(dict(value) for value in db.execute(
                "SELECT subject_id,subject_type,contract_version,natural_key_json,semantic_json "
                "FROM stable_subjects WHERE source_sha256=? ORDER BY subject_id", (source_sha,)))
            edges = tuple(dict(value) for value in db.execute(
                "SELECT edge_id,edge_type,contract_version,parent_subject_id,child_subject_id,semantic_json "
                "FROM stable_subject_edges WHERE source_sha256=? ORDER BY edge_id", (source_sha,)))
            lineage = trusted_lineages.get(source_sha)
            manifest = source_manifests.get(source_sha)
            if not isinstance(lineage, TrustedSourceLineageSnapshot) or not isinstance(manifest, dict):
                raise ValueError("Test-only authority requires canonical lineage and manifest records")
            rebuilt_lineage = TrustedSourceLineageSnapshot.from_semantic_records(
                [item.semantic_record for item in lineage.records], lineage.semantic_sha256)
            if rebuilt_lineage.semantic_sha256 != row["lineage_sha256"]:
                raise ValueError("Authority lineage records do not match schema-v2 source_context")
            root = rebuilt_lineage.record_for(source_sha)
            if root is None or root.lineage_class != "FACTORY_RAW":
                raise ValueError("Authority lineage root/class mismatch")
            closure = rebuilt_lineage.ancestor_closure(source_sha)
            if set(closure).intersection(SIX_SONG_FORBIDDEN_SHA256S):
                raise ValueError("Forbidden six-song authority lineage")
            classes = {rebuilt_lineage.record_for(item).lineage_class for item in closure}
            if classes.intersection(FORBIDDEN_SOURCE_KINDS) or not classes.issubset(
                    ALLOWED_LINEAGE_PARENT_CLASSES["FACTORY_RAW"]):
                raise ValueError("Forbidden or cross-authority lineage records")
            if not any(isinstance(item, dict) and item.get("manifest") == manifest
                       for item in json.loads(row["source_semantic_json"]).get("context_snapshots", [])):
                raise ValueError("Authority source manifest does not match schema-v2 source_context")
            if manifest.get("source_class") != "FACTORY_RAW" or \
                    manifest.get("lineage_sha256") != rebuilt_lineage.semantic_sha256 or \
                    manifest.get("is_optimizer_output") or manifest.get("is_repaired_output") or \
                    manifest.get("is_six_song_delay_terca"):
                raise ValueError("Authority source manifest is not trusted Factory RAW")
            anchors.append(AcceptedFactorySourceAnchor(
                source_sha, row["quality_status"], row["lineage_sha256"],
                json.loads(row["metadata_json"]), json.loads(row["source_semantic_json"]),
                subjects, edges, tuple(contexts),
                tuple(item.semantic_record for item in rebuilt_lineage.records), manifest))
    finally:
        db.close()
    if sha256(path.read_bytes()).hexdigest() != before:
        raise ValueError("Accepted schema-v2 database changed during verification")
    authority_record = {"authority_scope": "TEST_ONLY", "database_sha256": before,
                        "schema_v2_semantic_digest": expected,
                        "build_config_sha256": build_config,
                        "production_authority_status": PRODUCTION_AUTHORITY_STATUS,
                        "calibration_envelope_allowed": CALIBRATION_ENVELOPE_ALLOWED,
                        "source_proof_digests": [_digest({"source_sha256": item.source_sha256,
                            "lineage_records": item.lineage_records,
                            "source_manifest": item.source_manifest}) for item in anchors]}
    authority_id = _digest(authority_record)
    return TestOnlyFactoryCorpusAuthorityEvidence(
        "TEST_ONLY", authority_id, str(path), before, expected, build_config,
        tuple(anchors))


def _resolve_factory_authority(
        verifier: AcceptedFactoryCorpusAuthorityVerifierPort,
        allow_test_only_authority: bool) -> TestOnlyFactoryCorpusAuthorityEvidence:
    if not isinstance(verifier, AcceptedFactoryCorpusAuthorityVerifierPort):
        raise TypeError("AcceptedFactoryCorpusAuthorityVerifierPort is mandatory")
    authority = verifier.verify_factory_corpus_authority()
    if not isinstance(authority, TestOnlyFactoryCorpusAuthorityEvidence):
        raise TypeError("Authority verifier must return TEST_ONLY evidence")
    if authority.authority_scope != "TEST_ONLY" or not allow_test_only_authority:
        raise ValueError("013C-S production authority is NOT_PROVABLE; explicit TEST_ONLY mode is required")
    return authority


def _require_sha(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_int(value: int, label: str, lower: int, upper: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < lower or (upper is not None and value > upper):
        raise ValueError(f"{label} is outside its closed integer domain")
    return value


def _digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("ascii")).hexdigest()


def _semantic(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _semantic(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_semantic(item) for item in value]
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise ValueError(f"Unsupported structural semantic value: {type(value).__name__}")


def _normalize_style(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("style_name must be a non-empty string")
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _closed_token(value: str, domain: tuple[str, ...], label: str) -> str:
    if value not in domain:
        raise ValueError(f"Unknown {label}")
    return value


@dataclass(frozen=True)
class StructuralIdentityConfig:
    allowed_roles: tuple[str, ...]
    allowed_track_channel_roles: tuple[str, ...]
    tempo_bucket_width_bpm: int = 10
    contract_version: str = "X10_STRUCTURAL_IDENTITY_CONFIG_V1"

    def __post_init__(self) -> None:
        for label, values in (("allowed_roles", self.allowed_roles),
                              ("allowed_track_channel_roles", self.allowed_track_channel_roles)):
            values = tuple(sorted(values))
            if not values or len(values) != len(set(values)) or any(not _TOKEN_RE.fullmatch(item) for item in values):
                raise ValueError(f"{label} must contain unique closed ASCII tokens")
            object.__setattr__(self, label, values)
        if self.tempo_bucket_width_bpm != 10:
            raise ValueError("Structural identity v1 locks the tempo bucket width to 10 BPM")
        if self.contract_version != "X10_STRUCTURAL_IDENTITY_CONFIG_V1":
            raise ValueError("Structural identity config version mismatch")

    @property
    def semantic_sha256(self) -> str:
        return _digest(_semantic(self))


@dataclass(frozen=True)
class CalibrationContextPrimitives:
    role: str
    bank_msb: int
    bank_lsb: int
    program: int
    instrument_identity_key: str
    style_name: str
    section: str
    section_no: int | None
    cv_status: str
    cv: int | None
    meter_numerator: int
    meter_denominator: int
    microseconds_per_quarter: int
    track_channel_role: str
    voice_policy: str

    def __post_init__(self) -> None:
        for label, value in (("bank_msb", self.bank_msb), ("bank_lsb", self.bank_lsb),
                             ("program", self.program)):
            _require_int(value, label, 0, 127)
        if not isinstance(self.instrument_identity_key, str) or not self.instrument_identity_key.strip():
            raise ValueError("instrument_identity_key is required")
        _closed_token(self.section, SECTIONS, "section")
        if self.section in {"INTRO", "VARIATION", "FILL", "ENDING"}:
            _require_int(self.section_no, "section_no", 0)
        elif self.section_no is not None:
            _require_int(self.section_no, "section_no", 0)
        _closed_token(self.cv_status, CV_STATUSES, "cv_status")
        if self.cv_status == "EXACT":
            _require_int(self.cv, "cv", 0)
        elif self.cv is not None:
            raise ValueError("cv must be NULL when cv_status is NONE")
        _require_int(self.meter_numerator, "meter_numerator", 1)
        _require_int(self.meter_denominator, "meter_denominator", 1)
        if self.meter_denominator & (self.meter_denominator - 1):
            raise ValueError("meter_denominator must be a power of two")
        _require_int(self.microseconds_per_quarter, "microseconds_per_quarter", 1)
        _closed_token(self.voice_policy, VOICE_POLICIES, "voice_policy")


@dataclass(frozen=True)
class StructuralVoicePrimitive:
    note_subject_id: str
    on_event_subject_id: str
    pitch: int
    voice_token: str | None = None
    legacy_event_slot_key: str | None = None

    def __post_init__(self) -> None:
        _require_sha(self.note_subject_id, "note_subject_id")
        _require_sha(self.on_event_subject_id, "on_event_subject_id")
        _require_int(self.pitch, "pitch", 0, 127)
        if self.voice_token is not None:
            if not _VOICE_RE.fullmatch(self.voice_token) or any(item in self.voice_token for item in _VOICE_FORBIDDEN):
                raise ValueError("voice_token must be a timing-free structural token")
        if self.legacy_event_slot_key is not None and not isinstance(self.legacy_event_slot_key, str):
            raise TypeError("legacy_event_slot_key must be a string or NULL")


@dataclass(frozen=True)
class StructuralClusterPrimitive:
    onset_cluster_subject_id: str
    tick: int
    voices: tuple[StructuralVoicePrimitive, ...]

    def __post_init__(self) -> None:
        _require_sha(self.onset_cluster_subject_id, "onset_cluster_subject_id")
        _require_int(self.tick, "tick", 0)
        voices = tuple(self.voices)
        if not voices:
            raise ValueError("Structural cluster must contain at least one voice")
        if len({item.note_subject_id for item in voices}) != len(voices):
            raise ValueError("Structural cluster cannot repeat a NOTE subject")
        object.__setattr__(self, "voices", voices)


@dataclass(frozen=True)
class StructuralBarPrimitive:
    bar_subject_id: str
    track_channel_subject_id: str
    clusters: tuple[StructuralClusterPrimitive, ...]
    legacy_exact_context_key: str | None = None
    legacy_topology_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_sha(self.bar_subject_id, "bar_subject_id")
        _require_sha(self.track_channel_subject_id, "track_channel_subject_id")
        clusters = tuple(self.clusters)
        if not clusters:
            raise ValueError("Structural bar must contain at least one cluster")
        if len({item.onset_cluster_subject_id for item in clusters}) != len(clusters):
            raise ValueError("Structural bar cannot repeat an onset cluster")
        object.__setattr__(self, "clusters", clusters)
        if self.legacy_topology_sha256 is not None:
            _require_sha(self.legacy_topology_sha256, "legacy_topology_sha256")


@dataclass(frozen=True)
class FactoryStructuralSource:
    snapshot: StructuralSourceSnapshot
    context: CalibrationContextPrimitives
    bars: tuple[StructuralBarPrimitive, ...]
    quality_status: str = "NORMAL"

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, StructuralSourceSnapshot):
            raise TypeError("snapshot must be a trusted StructuralSourceSnapshot")
        if not isinstance(self.context, CalibrationContextPrimitives):
            raise TypeError("context must use typed calibration primitives")
        bars = tuple(self.bars)
        if not bars or len({item.bar_subject_id for item in bars}) != len(bars):
            raise ValueError("Source bars must be non-empty and unique")
        if self.quality_status != "NORMAL":
            raise ValueError("Only quality NORMAL Factory sources are eligible")
        object.__setattr__(self, "bars", bars)


@dataclass(frozen=True)
class _ClusterToken:
    cardinality: int
    signature: tuple[int, ...]
    ordered_voices: tuple[StructuralVoicePrimitive, ...]


def _context_base(context: CalibrationContextPrimitives, config: StructuralIdentityConfig) -> dict[str, Any]:
    role = _closed_token(context.role, config.allowed_roles, "role")
    track_role = _closed_token(context.track_channel_role, config.allowed_track_channel_roles,
                               "track_channel_role")
    bpm = Fraction(60_000_000, context.microseconds_per_quarter)
    lower = config.tempo_bucket_width_bpm * (bpm // config.tempo_bucket_width_bpm)
    return {
        "contract": CONTEXT_CONTRACT,
        "role": role,
        "instrument": {"bank_msb": context.bank_msb, "bank_lsb": context.bank_lsb,
                       "program": context.program,
                       "identity_key": unicodedata.normalize("NFKC", context.instrument_identity_key).strip()},
        "style": {"name_key": _normalize_style(context.style_name), "section": context.section,
                  "section_no": context.section_no, "cv_status": context.cv_status, "cv": context.cv},
        "meter": {"numerator": context.meter_numerator, "denominator": context.meter_denominator},
        "tempo_regime": {"contract": TEMPO_CONTRACT, "lower_inclusive": int(lower),
                         "upper_exclusive": int(lower + config.tempo_bucket_width_bpm)},
        "track_channel_role": track_role,
        "config_sha256": config.semantic_sha256,
    }


def _cluster_token(cluster: StructuralClusterPrimitive, policy: str) -> _ClusterToken:
    voices = tuple(cluster.voices)
    pitches = [item.pitch for item in voices]
    duplicates = {pitch for pitch in pitches if pitches.count(pitch) > 1}
    if duplicates:
        # There is no accepted timing-free voice-lane registry in v1.  Caller
        # tokens, event/NOTE IDs and parser order cannot resolve a unison.
        raise ValueError("STRUCTURAL_DUPLICATE_AMBIGUOUS")
    ordered = tuple(sorted(voices, key=lambda item: item.pitch))
    if policy == "EXACT_DRUM_LANE":
        signature = tuple(item.pitch for item in ordered)
    else:
        anchor = min(pitches)
        signature = tuple(item.pitch - anchor for item in ordered)
    return _ClusterToken(len(voices), signature, ordered)


def _bar_tokens(bar: StructuralBarPrimitive, policy: str) -> tuple[_ClusterToken, ...]:
    ordered = tuple(sorted(bar.clusters, key=lambda item: item.tick))
    if len({item.tick for item in ordered}) != len(ordered):
        raise ValueError("STRUCTURAL_ALIGNMENT_AMBIGUOUS")
    return tuple(_cluster_token(item, policy) for item in ordered)


def _token_sequence(tokens: tuple[_ClusterToken, ...]) -> tuple[tuple[int, tuple[int, ...]], ...]:
    return tuple((item.cardinality, item.signature) for item in tokens)


def _validate_voice_paths(all_tokens: Iterable[tuple[_ClusterToken, ...]]) -> None:
    # Reserved for a future accepted voice-lane registry.  Unique pitch lanes
    # are deterministic without consulting caller-supplied voice tokens.
    tuple(all_tokens)


def calibration_context_identity(context: CalibrationContextPrimitives,
                                 bar_structure: tuple[tuple[int, tuple[int, ...]], ...],
                                 config: StructuralIdentityConfig) -> tuple[str, str]:
    """Return canonical JSON and key from typed, phase-independent primitives."""
    if not isinstance(context, CalibrationContextPrimitives) or not isinstance(config, StructuralIdentityConfig):
        raise TypeError("Typed context and identity config are required")
    payload = _context_base(context, config)
    payload["bar_structure"] = {
        "cluster_cardinalities": [item[0] for item in bar_structure],
        "voice_signatures": [list(item[1]) for item in bar_structure],
    }
    identity_json = canonical_json(payload)
    return identity_json, sha256(identity_json.encode("ascii")).hexdigest()


def structural_slot_identity(calibration_context_key: str, cluster_ordinal: int,
                             cluster_cardinality: int, voice_signature: tuple[int, ...],
                             voice_ordinal: int, voice_offset_or_drum_lane: int,
                             config: StructuralIdentityConfig) -> tuple[str, str]:
    """Return a slot identity; no generic mapping or digest input is accepted."""
    _require_sha(calibration_context_key, "calibration_context_key")
    for label, value in (("cluster_ordinal", cluster_ordinal),
                         ("cluster_cardinality", cluster_cardinality),
                         ("voice_ordinal", voice_ordinal)):
        _require_int(value, label, 0)
    if not isinstance(voice_signature, tuple) or any(not isinstance(item, int) for item in voice_signature):
        raise TypeError("voice_signature must be a tuple of integers")
    if len(voice_signature) != cluster_cardinality or not 0 <= voice_ordinal < cluster_cardinality:
        raise ValueError("Slot voice cardinality is inconsistent")
    payload = {"contract": SLOT_CONTRACT, "calibration_context_key": calibration_context_key,
               "cluster_ordinal": cluster_ordinal, "cluster_cardinality": cluster_cardinality,
               "voice_signature": list(voice_signature), "voice_ordinal": voice_ordinal,
               "voice_offset_or_drum_lane": voice_offset_or_drum_lane,
               "identity_config_sha256": config.semantic_sha256}
    identity_json = canonical_json(payload)
    return identity_json, sha256(identity_json.encode("ascii")).hexdigest()


def _subject_records(snapshot: StructuralSourceSnapshot) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    subjects = [item.semantic_record for item in snapshot.subject_registry.subjects]
    edges = [{"contract_version": item.contract_version, "edge_type": item.edge_type,
              "source_sha256": item.source_sha256, "parent_subject_id": item.parent_subject_id,
              "child_subject_id": item.child_subject_id, "edge_id": item.edge_id}
             for item in snapshot.subject_registry.edges]
    return subjects, edges


def _validate_source(source: FactoryStructuralSource) -> None:
    snapshot = source.snapshot
    if snapshot.source_kind != "FACTORY_RAW":
        raise ValueError("Structural registry accepts only trusted FACTORY_RAW sources")
    if not isinstance(snapshot.source_guard_policy, SourceGuardPolicy) or snapshot.source_guard_policy != trusted_source_guard_policy():
        raise ValueError("Trusted Factory guard policy must be revalidated")
    if not isinstance(snapshot.source_lineage, TrustedSourceLineageSnapshot):
        raise TypeError("Trusted Factory lineage is mandatory")
    records = [item.semantic_record for item in snapshot.source_lineage.records]
    rebuilt_lineage = TrustedSourceLineageSnapshot.from_semantic_records(
        records, snapshot.source_lineage.semantic_sha256)
    record = rebuilt_lineage.record_for(snapshot.source_sha256)
    if record is None or record.lineage_class != "FACTORY_RAW":
        raise ValueError("Factory lineage root is missing or has the wrong authority")
    closure = rebuilt_lineage.ancestor_closure(snapshot.source_sha256)
    if set(closure).intersection(SIX_SONG_FORBIDDEN_SHA256S):
        raise ValueError("Forbidden six-song lineage cannot enter structural registry")
    classes = {rebuilt_lineage.record_for(item).lineage_class for item in closure}
    if classes.intersection(FORBIDDEN_SOURCE_KINDS) or not classes.issubset(
            ALLOWED_LINEAGE_PARENT_CLASSES["FACTORY_RAW"]):
        raise ValueError("Forbidden or cross-authority Factory lineage")
    manifest = dict(snapshot.source_manifest)
    if manifest.get("source_class") != "FACTORY_RAW" or manifest.get("lineage_sha256") != rebuilt_lineage.semantic_sha256:
        raise ValueError("Factory source manifest parity failed")
    if manifest.get("is_optimizer_output") or manifest.get("is_repaired_output") or manifest.get("is_six_song_delay_terca"):
        raise ValueError("Forbidden source manifest flags")
    if snapshot.recompute_semantic_sha256() != snapshot.semantic_sha256:
        raise ValueError("Structural source snapshot semantic digest mismatch")
    subjects, edges = _subject_records(snapshot)
    rebuilt = ValidatedSubjectRegistrySnapshot.from_semantic_records(
        subjects, snapshot.subject_registry.semantic_digest(), edges)
    if rebuilt.semantic_sha256 != snapshot.subject_registry.semantic_digest():
        raise ValueError("Stable subject registry parity failed")


def _accepted_source_anchor(source: FactoryStructuralSource,
                            accepted: TestOnlyFactoryCorpusAuthorityEvidence) -> AcceptedFactorySourceAnchor:
    """Bind a source to accepted schema-v2 rows instead of its own labels."""
    if sha256(Path(accepted.database_path).read_bytes()).hexdigest() != accepted.database_sha256:
        raise ValueError("Accepted schema-v2 authority database changed after verification")
    anchor = accepted.source_for(source.snapshot.source_sha256)
    if anchor is None:
        raise ValueError("Factory source is absent from the accepted schema-v2 corpus")
    if anchor.quality_status != "NORMAL" or source.quality_status != anchor.quality_status:
        raise ValueError("Factory NORMAL quality lacks accepted schema-v2 authority")
    if anchor.lineage_sha256 != source.snapshot.source_lineage.semantic_sha256:
        raise ValueError("Factory lineage differs from accepted schema-v2 source_context")
    snapshots = anchor.source_semantic.get("context_snapshots")
    if not isinstance(snapshots, list) or not any(
            isinstance(item, dict) and
            item.get("snapshot_semantic_sha256") == source.snapshot.semantic_sha256 and
            item.get("scope_subject_id") == source.snapshot.scope_subject_id and
            item.get("manifest") == dict(source.snapshot.source_manifest)
            for item in snapshots):
        raise ValueError("Factory snapshot is not committed by accepted schema-v2 source_context")
    accepted_subjects = {item["subject_id"]: json.loads(item["semantic_json"])
                         for item in anchor.subjects}
    for subject in source.snapshot.subject_registry.subjects:
        if canonical_json(accepted_subjects.get(subject.subject_id)) != canonical_json(subject.semantic_record):
            raise ValueError("Factory stable subject is not anchored in accepted schema-v2")
    accepted_edges = {item["edge_id"]: json.loads(item["semantic_json"])
                      for item in anchor.edges}
    for edge in source.snapshot.subject_registry.edges:
        expected = {"contract_version": edge.contract_version, "edge_type": edge.edge_type,
                    "source_sha256": edge.source_sha256,
                    "parent_subject_id": edge.parent_subject_id,
                    "child_subject_id": edge.child_subject_id, "edge_id": edge.edge_id}
        if accepted_edges.get(edge.edge_id) != expected:
            raise ValueError("Factory stable edge is not anchored in accepted schema-v2")
    return anchor


def _exact_metadata(anchor: AcceptedFactorySourceAnchor, key: str) -> Any:
    if (anchor.metadata.get(f"{key}_status") != "EXACT" or
            not isinstance(anchor.metadata.get(f"{key}_method"), str) or
            not anchor.metadata.get(f"{key}_method") or
            not isinstance(anchor.metadata.get(f"{key}_locator"), str) or
            not anchor.metadata.get(f"{key}_locator")):
        raise ValueError(f"Accepted schema-v2 {key} provenance is incomplete")
    return anchor.metadata.get(key)


def _context_from_accepted_note(anchor: AcceptedFactorySourceAnchor,
                                note_subject_id: str) -> CalibrationContextPrimitives:
    payload = dict(anchor.note_contexts).get(note_subject_id)
    if not isinstance(payload, dict) or not isinstance(payload.get("note_context"), dict):
        raise ValueError("Accepted schema-v2 exact NOTE context is missing")
    row = payload["note_context"]
    exact = {"program_status": "PROGRAM_EXACT", "meter_status": "METER_EXACT",
             "tempo_status": "TEMPO_EXACT", "role_status": "EXACT",
             "style_status": "EXPLICIT_METADATA", "section_status": "EXACT"}
    if any(row.get(key) != value for key, value in exact.items()) or row.get("quality_status") != "NORMAL":
        raise ValueError("Accepted NOTE context is not exact NORMAL Factory evidence")
    for key in ("role", "style", "section", "cv"):
        if not isinstance(row.get(f"{key}_method"), str) or not row.get(f"{key}_method") or \
                not isinstance(row.get(f"{key}_locator"), str) or not row.get(f"{key}_locator"):
            raise ValueError(f"Accepted NOTE {key} provenance is incomplete")
    if row.get("cv_status") == "CV_EXACT":
        cv_status, cv = "EXACT", row.get("cv")
    elif row.get("cv_status") == "CV_NOT_APPLICABLE":
        cv_status, cv = "NONE", None
    else:
        raise ValueError("Accepted NOTE CV context is not exact")
    return CalibrationContextPrimitives(
        str(row["role"]), int(row["bank_msb"]), int(row["bank_lsb"]), int(row["program"]),
        str(_exact_metadata(anchor, "instrument_identity")), str(row["style_name"]),
        str(row["section"]), row.get("section_no"), cv_status, cv,
        int(row["meter_numerator"]), int(row["meter_denominator"]),
        int(row["microseconds_per_quarter"]),
        str(_exact_metadata(anchor, "track_channel_role")),
        str(_exact_metadata(anchor, "voice_policy")))


def _reconstruct_bar_context(source: FactoryStructuralSource, bar: StructuralBarPrimitive,
                             anchor: AcceptedFactorySourceAnchor) -> CalibrationContextPrimitives:
    contexts = {_context_from_accepted_note(anchor, voice.note_subject_id)
                for cluster in bar.clusters for voice in cluster.voices}
    if len(contexts) != 1:
        raise ValueError("Accepted schema-v2 bar has mixed or unproven structural context")
    context = next(iter(contexts))
    if context != source.context:
        raise ValueError("Caller context contradicts frozen accepted schema-v2 provenance")
    return context


def _validate_bar_anchor(source: FactoryStructuralSource, bar: StructuralBarPrimitive) -> None:
    snapshot = source.snapshot
    subjects = {item.subject_id: item for item in snapshot.subject_registry.subjects}
    bar_subject = subjects.get(bar.bar_subject_id)
    track_subject = subjects.get(bar.track_channel_subject_id)
    if bar_subject is None or bar_subject.subject_type != "BAR" or track_subject is None or track_subject.subject_type != "TRACK_CHANNEL":
        raise ValueError("Structural bar/track stable subjects are missing")


def _validate_bar_provenance(source: FactoryStructuralSource, bar: StructuralBarPrimitive,
                             context: CalibrationContextPrimitives) -> None:
    _validate_bar_anchor(source, bar)
    snapshot = source.snapshot
    subjects = {item.subject_id: item for item in snapshot.subject_registry.subjects}
    edges = {(item.edge_type, item.parent_subject_id, item.child_subject_id)
             for item in snapshot.subject_registry.edges}
    tracks = [item for item in snapshot.tracks if item.track_subject_id == bar.track_channel_subject_id]
    if len(tracks) != 1 or tracks[0].role_status != "EXACT" or tracks[0].role != context.role:
        raise ValueError("Calibration role lacks exact frozen Factory provenance")
    sections = [item for item in snapshot.sections
                if item.track_subject_id == bar.track_channel_subject_id and
                bar.bar_subject_id in item.ordered_bar_ids]
    if len(sections) != 1 or sections[0].section_status != "EXACT" or sections[0].section != context.section:
        raise ValueError("Calibration section lacks exact frozen Factory provenance")
    note_observations = {item.note_subject_id: item for item in snapshot.notes}
    for cluster in bar.clusters:
        cluster_subject = subjects.get(cluster.onset_cluster_subject_id)
        if cluster_subject is None or cluster_subject.subject_type != "ONSET_CLUSTER":
            raise ValueError("Onset cluster stable subject is missing")
        if cluster_subject.natural_key.get("tick") != cluster.tick:
            raise ValueError("Onset cluster provenance tick mismatch")
        if ("BAR_CONTAINS_ONSET_CLUSTER", bar.bar_subject_id, cluster.onset_cluster_subject_id) not in edges:
            raise ValueError("Bar-to-cluster provenance edge is missing")
        declared_events = set(cluster_subject.natural_key.get("on_event_ids", ()))
        for voice in cluster.voices:
            note_subject = subjects.get(voice.note_subject_id)
            event_subject = subjects.get(voice.on_event_subject_id)
            observation = note_observations.get(voice.note_subject_id)
            if note_subject is None or note_subject.subject_type != "NOTE" or event_subject is None or event_subject.subject_type != "EVENT":
                raise ValueError("Structural NOTE/NOTE_ON stable subject is missing")
            if observation is None or observation.pitch != voice.pitch or observation.bar_subject_id != bar.bar_subject_id or observation.onset_cluster_id != cluster.onset_cluster_subject_id:
                raise ValueError("Structural voice contradicts frozen Factory extraction")
            required = {
                ("TRACK_CHANNEL_CONTAINS_NOTE", bar.track_channel_subject_id, voice.note_subject_id),
                ("NOTE_HAS_ON_EVENT", voice.note_subject_id, voice.on_event_subject_id),
                ("ONSET_CLUSTER_CONTAINS_NOTE", cluster.onset_cluster_subject_id, voice.note_subject_id),
            }
            if not required.issubset(edges) or voice.on_event_subject_id not in declared_events:
                raise ValueError("Structural source-local membership recomputation failed")


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE build_contract(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
CREATE TABLE authority_proof(authority_id TEXT PRIMARY KEY,authority_scope TEXT NOT NULL,
 database_sha256 TEXT NOT NULL,schema_v2_semantic_digest TEXT NOT NULL,
 build_config_sha256 TEXT NOT NULL,production_authority_status TEXT NOT NULL,
 calibration_envelope_allowed INTEGER NOT NULL,semantic_json TEXT NOT NULL,
 CHECK(authority_scope='TEST_ONLY'),CHECK(production_authority_status='NOT_PROVABLE'),
 CHECK(calibration_envelope_allowed=0));
CREATE TABLE source_registry(source_sha256 TEXT PRIMARY KEY,source_class TEXT NOT NULL CHECK(source_class='FACTORY_RAW'),
 quality_status TEXT NOT NULL CHECK(quality_status='NORMAL'),manifest_json TEXT NOT NULL,
 lineage_sha256 TEXT NOT NULL,subject_registry_sha256 TEXT NOT NULL,snapshot_sha256 TEXT NOT NULL,
 accepted_schema_v2_sha256 TEXT NOT NULL,accepted_build_config_sha256 TEXT NOT NULL);
CREATE TABLE accepted_source_proofs(source_sha256 TEXT PRIMARY KEY,authority_id TEXT NOT NULL,
 quality_status TEXT NOT NULL,lineage_sha256 TEXT NOT NULL,manifest_json TEXT NOT NULL,
 metadata_json TEXT NOT NULL,source_semantic_json TEXT NOT NULL,note_contexts_json TEXT NOT NULL,
 FOREIGN KEY(source_sha256) REFERENCES source_registry(source_sha256),
 FOREIGN KEY(authority_id) REFERENCES authority_proof(authority_id));
CREATE TABLE accepted_lineage_records(root_source_sha256 TEXT NOT NULL,record_sha256 TEXT NOT NULL,
 lineage_class TEXT NOT NULL,parent_sha256s_json TEXT NOT NULL,semantic_json TEXT NOT NULL,
 PRIMARY KEY(root_source_sha256,record_sha256),
 FOREIGN KEY(root_source_sha256) REFERENCES source_registry(source_sha256));
CREATE TABLE stable_subjects(source_sha256 TEXT NOT NULL,subject_id TEXT NOT NULL,subject_type TEXT NOT NULL,
 semantic_json TEXT NOT NULL,PRIMARY KEY(source_sha256,subject_id),
 FOREIGN KEY(source_sha256) REFERENCES source_registry(source_sha256));
CREATE TABLE stable_edges(source_sha256 TEXT NOT NULL,edge_id TEXT NOT NULL,edge_type TEXT NOT NULL,
 parent_subject_id TEXT NOT NULL,child_subject_id TEXT NOT NULL,semantic_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,edge_id),
 FOREIGN KEY(source_sha256,parent_subject_id) REFERENCES stable_subjects(source_sha256,subject_id),
 FOREIGN KEY(source_sha256,child_subject_id) REFERENCES stable_subjects(source_sha256,subject_id));
CREATE TABLE structural_context_registry(calibration_context_key TEXT PRIMARY KEY,identity_json TEXT NOT NULL UNIQUE,
 identity_config_sha256 TEXT NOT NULL);
CREATE TABLE structural_slot_registry(structural_event_slot_key TEXT PRIMARY KEY,calibration_context_key TEXT NOT NULL,
 identity_json TEXT NOT NULL UNIQUE,FOREIGN KEY(calibration_context_key) REFERENCES structural_context_registry(calibration_context_key));
CREATE TABLE structural_slot_memberships(source_sha256 TEXT NOT NULL,bar_subject_id TEXT NOT NULL,
 structural_event_slot_key TEXT NOT NULL,onset_cluster_subject_id TEXT NOT NULL,note_subject_id TEXT NOT NULL,
 on_event_subject_id TEXT NOT NULL,track_channel_subject_id TEXT NOT NULL,provenance_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,bar_subject_id,structural_event_slot_key),
 FOREIGN KEY(source_sha256) REFERENCES source_registry(source_sha256),
 FOREIGN KEY(structural_event_slot_key) REFERENCES structural_slot_registry(structural_event_slot_key),
 FOREIGN KEY(source_sha256,bar_subject_id) REFERENCES stable_subjects(source_sha256,subject_id),
 FOREIGN KEY(source_sha256,onset_cluster_subject_id) REFERENCES stable_subjects(source_sha256,subject_id),
 FOREIGN KEY(source_sha256,note_subject_id) REFERENCES stable_subjects(source_sha256,subject_id),
 FOREIGN KEY(source_sha256,on_event_subject_id) REFERENCES stable_subjects(source_sha256,subject_id),
 FOREIGN KEY(source_sha256,track_channel_subject_id) REFERENCES stable_subjects(source_sha256,subject_id));
CREATE TABLE structural_resolution(source_sha256 TEXT NOT NULL,bar_subject_id TEXT NOT NULL,status TEXT NOT NULL,
 reason TEXT NOT NULL,detail_json TEXT NOT NULL,PRIMARY KEY(source_sha256,bar_subject_id),
 FOREIGN KEY(source_sha256) REFERENCES source_registry(source_sha256),
 FOREIGN KEY(source_sha256,bar_subject_id) REFERENCES stable_subjects(source_sha256,subject_id));
CREATE TABLE semantic_root(algorithm TEXT PRIMARY KEY,digest TEXT NOT NULL);
"""

SEMANTIC_TABLES = (
    "build_contract", "authority_proof", "source_registry", "accepted_source_proofs",
    "accepted_lineage_records", "stable_subjects", "stable_edges",
    "structural_context_registry", "structural_slot_registry",
    "structural_slot_memberships", "structural_resolution",
)


def _rows(database_path: str | Path) -> list[str]:
    db = sqlite3.connect(database_path); db.row_factory = sqlite3.Row
    rows: list[str] = []
    try:
        for table in SEMANTIC_TABLES:
            values = []
            for row in db.execute(f'SELECT * FROM "{table}"'):
                value = dict(row)
                for key in tuple(value):
                    if key.endswith("_json"):
                        value[key] = json.loads(value[key])
                values.append(value)
            values.sort(key=canonical_json)
            rows.extend(canonical_json({"table": table, "row": value}) for value in values)
    finally:
        db.close()
    return rows


def structural_semantic_digest(database_path: str | Path) -> str:
    return sha256("\n".join(_rows(database_path)).encode("ascii")).hexdigest()


def assert_structural_registry_surface(database_path: str | Path) -> None:
    db = sqlite3.connect(database_path)
    try:
        for name, sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('table','view','trigger')"):
            lowered = f"{name} {sql or ''}".lower()
            safety_redacted = lowered.replace("calibration_envelope_allowed", "")
            if any(token in safety_redacted for token in _STATIC_FORBIDDEN):
                raise ValueError(f"Forbidden structural registry surface: {name}")
        contract = {key: json.loads(value) for key, value in db.execute("SELECT key,value_json FROM build_contract")}
        if contract.get("capability") != CAPABILITY or contract.get("mutation_capability") != MUTATION_CAPABILITY:
            raise ValueError("Structural registry capability mismatch")
        if contract.get("production_authority_status") != PRODUCTION_AUTHORITY_STATUS or \
                contract.get("calibration_envelope_allowed") is not CALIBRATION_ENVELOPE_ALLOWED:
            raise ValueError("Structural registry production/envelope safety lock mismatch")
    finally:
        db.close()


def verify_structural_registry(
        database_path: str | Path,
        authority_verifier: AcceptedFactoryCorpusAuthorityVerifierPort,
        *, allow_test_only_authority: bool = False) -> dict[str, Any]:
    """Recompute the stored semantic root and all identity-critical links."""
    authority = _resolve_factory_authority(authority_verifier, allow_test_only_authority)
    assert_structural_registry_surface(database_path)
    db = sqlite3.connect(database_path); db.row_factory = sqlite3.Row
    try:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute(
                "PRAGMA foreign_key_check").fetchall():
            raise ValueError("Structural registry integrity/FK verification failed")
        root = db.execute("SELECT digest FROM semantic_root WHERE algorithm='SHA256'").fetchall()
        actual = structural_semantic_digest(database_path)
        if len(root) != 1 or root[0][0] != actual:
            raise ValueError("Structural registry semantic root mismatch")
        authority_rows = db.execute("SELECT * FROM authority_proof").fetchall()
        if len(authority_rows) != 1:
            raise ValueError("Structural registry authority proof is not singular")
        authority_row = authority_rows[0]
        expected_authority = {"authority_scope": authority.authority_scope,
            "database_sha256": authority.database_sha256,
            "schema_v2_semantic_digest": authority.schema_v2_semantic_digest,
            "build_config_sha256": authority.build_config_sha256,
            "production_authority_status": PRODUCTION_AUTHORITY_STATUS,
            "calibration_envelope_allowed": CALIBRATION_ENVELOPE_ALLOWED,
            "source_proof_digests": [_digest({"source_sha256": item.source_sha256,
                "lineage_records": item.lineage_records,
                "source_manifest": item.source_manifest}) for item in authority.sources]}
        if (_digest(expected_authority) != authority.authority_id or
                authority_row["authority_id"] != authority.authority_id or
                authority_row["authority_scope"] != authority.authority_scope or
                authority_row["database_sha256"] != authority.database_sha256 or
                authority_row["schema_v2_semantic_digest"] != authority.schema_v2_semantic_digest or
                authority_row["build_config_sha256"] != authority.build_config_sha256 or
                authority_row["production_authority_status"] != PRODUCTION_AUTHORITY_STATUS or
                authority_row["calibration_envelope_allowed"] != 0 or
                json.loads(authority_row["semantic_json"]) != expected_authority):
            raise ValueError("Structural registry authority commitment mismatch")
        contract = {key: json.loads(value) for key, value in db.execute(
            "SELECT key,value_json FROM build_contract")}
        if (contract.get("authority_id") != authority.authority_id or
                contract.get("authority_scope") != authority.authority_scope or
                contract.get("accepted_schema_v2_semantic_digest") != authority.schema_v2_semantic_digest or
                contract.get("accepted_build_config_sha256") != authority.build_config_sha256 or
                contract.get("production_authority_status") != PRODUCTION_AUTHORITY_STATUS or
                contract.get("calibration_envelope_allowed") is not CALIBRATION_ENVELOPE_ALLOWED):
            raise ValueError("Structural build contract/authority mismatch")
        source_rows = {row["source_sha256"]: row for row in db.execute("SELECT * FROM source_registry")}
        proof_rows = {row["source_sha256"]: row for row in db.execute("SELECT * FROM accepted_source_proofs")}
        if set(source_rows) != set(proof_rows) or not set(source_rows).issubset(
                {item.source_sha256 for item in authority.sources}):
            raise ValueError("Structural source/authority universe mismatch")
        authority_anchors = {item.source_sha256: item for item in authority.sources}
        for source_sha, row in source_rows.items():
            anchor = authority_anchors[source_sha]; proof = proof_rows[source_sha]
            if (row["source_class"] != "FACTORY_RAW" or row["quality_status"] != anchor.quality_status or
                    row["manifest_json"] != canonical_json(anchor.source_manifest) or
                    row["lineage_sha256"] != anchor.lineage_sha256 or
                    row["accepted_schema_v2_sha256"] != authority.schema_v2_semantic_digest or
                    row["accepted_build_config_sha256"] != authority.build_config_sha256 or
                    proof["authority_id"] != authority.authority_id or
                    proof["quality_status"] != anchor.quality_status or
                    proof["lineage_sha256"] != anchor.lineage_sha256 or
                    proof["manifest_json"] != canonical_json(anchor.source_manifest) or
                    proof["metadata_json"] != canonical_json(anchor.metadata) or
                    proof["source_semantic_json"] != canonical_json(anchor.source_semantic) or
                    proof["note_contexts_json"] != canonical_json(dict(anchor.note_contexts))):
                raise ValueError("Persisted accepted source proof differs from authority capability")
            lineage_rows = db.execute(
                "SELECT semantic_json FROM accepted_lineage_records WHERE root_source_sha256=? ORDER BY record_sha256",
                (source_sha,)).fetchall()
            lineage_records = [json.loads(value[0]) for value in lineage_rows]
            if canonical_json(sorted(lineage_records, key=canonical_json)) != \
                    canonical_json(sorted(anchor.lineage_records, key=canonical_json)):
                raise ValueError("Persisted lineage records differ from authority capability")
            rebuilt_lineage = TrustedSourceLineageSnapshot.from_semantic_records(
                lineage_records, anchor.lineage_sha256)
            root_record = rebuilt_lineage.record_for(source_sha)
            closure = rebuilt_lineage.ancestor_closure(source_sha)
            if root_record is None or root_record.lineage_class != "FACTORY_RAW" or \
                    set(closure).intersection(SIX_SONG_FORBIDDEN_SHA256S):
                raise ValueError("Persisted Factory lineage root/closure is invalid")
            classes = {rebuilt_lineage.record_for(item).lineage_class for item in closure}
            if classes.intersection(FORBIDDEN_SOURCE_KINDS) or not classes.issubset(
                    ALLOWED_LINEAGE_PARENT_CLASSES["FACTORY_RAW"]):
                raise ValueError("Persisted Factory lineage crosses authority boundaries")
        statuses = {row[0] for row in db.execute("SELECT DISTINCT status FROM structural_resolution")}
        if not statuses.issubset(RESOLUTION_STATUSES):
            raise ValueError("Structural registry contains an open status domain")
        contexts = {}
        for row in db.execute("SELECT * FROM structural_context_registry"):
            if sha256(row["identity_json"].encode("ascii")).hexdigest() != row["calibration_context_key"]:
                raise ValueError("Structural context identity digest mismatch")
            payload = json.loads(row["identity_json"])
            if payload.get("config_sha256") != row["identity_config_sha256"]:
                raise ValueError("Structural context config provenance mismatch")
            contexts[row["calibration_context_key"]] = payload
        slots = {}
        for row in db.execute("SELECT * FROM structural_slot_registry"):
            if sha256(row["identity_json"].encode("ascii")).hexdigest() != row["structural_event_slot_key"]:
                raise ValueError("Structural slot identity digest mismatch")
            payload = json.loads(row["identity_json"])
            if payload.get("calibration_context_key") != row["calibration_context_key"] or \
                    row["calibration_context_key"] not in contexts:
                raise ValueError("Structural slot/context provenance mismatch")
            slots[row["structural_event_slot_key"]] = payload
        subject_types = {}
        for row in db.execute("SELECT * FROM stable_subjects"):
            semantic = json.loads(row["semantic_json"])
            try:
                rebuilt = StableSubject(semantic["subject_type"], semantic["source_sha256"],
                                        semantic["natural_key"], semantic["contract_version"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Stable subject semantic record is not canonical") from error
            if (rebuilt.subject_id != row["subject_id"] or rebuilt.subject_type != row["subject_type"] or
                    rebuilt.source_sha256 != row["source_sha256"] or
                    canonical_json(rebuilt.semantic_record) != canonical_json(semantic)):
                raise ValueError("Stable subject canonical identity/semantic mismatch")
            anchor = authority_anchors.get(row["source_sha256"])
            accepted = {} if anchor is None else {item["subject_id"]: json.loads(item["semantic_json"])
                                                   for item in anchor.subjects}
            if canonical_json(accepted.get(row["subject_id"])) != canonical_json(semantic):
                raise ValueError("Stable subject differs from accepted schema-v2 authority")
            subject_types[(row["source_sha256"], row["subject_id"])] = row["subject_type"]
        edges = {(row["source_sha256"], row["edge_type"], row["parent_subject_id"], row["child_subject_id"])
                 for row in db.execute("SELECT source_sha256,edge_type,parent_subject_id,child_subject_id FROM stable_edges")}
        for row in db.execute("SELECT * FROM stable_edges"):
            semantic = json.loads(row["semantic_json"])
            try:
                rebuilt = StableSubjectEdge(semantic["edge_type"], semantic["parent_subject_id"],
                                            semantic["child_subject_id"], semantic["source_sha256"],
                                            semantic["contract_version"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Stable edge semantic record is not canonical") from error
            if (rebuilt.edge_id != row["edge_id"] or rebuilt.edge_type != row["edge_type"] or
                    rebuilt.parent_subject_id != row["parent_subject_id"] or
                    rebuilt.child_subject_id != row["child_subject_id"] or
                    rebuilt.source_sha256 != row["source_sha256"] or
                    canonical_json({"contract_version": rebuilt.contract_version,
                        "edge_type": rebuilt.edge_type, "source_sha256": rebuilt.source_sha256,
                        "parent_subject_id": rebuilt.parent_subject_id,
                        "child_subject_id": rebuilt.child_subject_id,
                        "edge_id": rebuilt.edge_id}) != canonical_json(semantic)):
                raise ValueError("Stable edge canonical identity/semantic mismatch")
            anchor = authority_anchors.get(row["source_sha256"])
            accepted = {} if anchor is None else {item["edge_id"]: json.loads(item["semantic_json"])
                                                   for item in anchor.edges}
            if canonical_json(accepted.get(row["edge_id"])) != canonical_json(semantic):
                raise ValueError("Stable edge differs from accepted schema-v2 authority")
        for row in db.execute("SELECT * FROM structural_slot_memberships"):
            source = row["source_sha256"]
            expected_types = {row["bar_subject_id"]: "BAR",
                              row["onset_cluster_subject_id"]: "ONSET_CLUSTER",
                              row["note_subject_id"]: "NOTE", row["on_event_subject_id"]: "EVENT",
                              row["track_channel_subject_id"]: "TRACK_CHANNEL"}
            if any(subject_types.get((source, subject)) != kind
                   for subject, kind in expected_types.items()):
                raise ValueError("Structural membership stable-subject type mismatch")
            required = {(source, "BAR_CONTAINS_ONSET_CLUSTER", row["bar_subject_id"],
                         row["onset_cluster_subject_id"]),
                        (source, "ONSET_CLUSTER_CONTAINS_NOTE", row["onset_cluster_subject_id"],
                         row["note_subject_id"]),
                        (source, "NOTE_HAS_ON_EVENT", row["note_subject_id"],
                         row["on_event_subject_id"]),
                        (source, "TRACK_CHANNEL_CONTAINS_NOTE", row["track_channel_subject_id"],
                         row["note_subject_id"])}
            if not required.issubset(edges) or row["structural_event_slot_key"] not in slots:
                raise ValueError("Structural membership provenance edge mismatch")
            provenance = json.loads(row["provenance_json"])
            for key in ("source_sha256", "bar_subject_id", "onset_cluster_subject_id",
                        "note_subject_id", "on_event_subject_id", "track_channel_subject_id"):
                if provenance.get(key) != row[key]:
                    raise ValueError("Structural membership provenance row mismatch")
        return {"semantic_digest": actual, "contexts": len(contexts), "slots": len(slots),
                "authority_scope": authority.authority_scope,
                "production_authority_status": PRODUCTION_AUTHORITY_STATUS,
                "calibration_envelope_allowed": CALIBRATION_ENVELOPE_ALLOWED,
                "memberships": db.execute("SELECT COUNT(*) FROM structural_slot_memberships").fetchone()[0]}
    finally:
        db.close()


def _ambiguity_status(error: Exception) -> str:
    token = str(error)
    return token if token in RESOLUTION_STATUSES else "STRUCTURAL_ALIGNMENT_AMBIGUOUS"


def build_structural_registry(sources: Iterable[FactoryStructuralSource], database_path: str | Path,
                              config: StructuralIdentityConfig,
                              authority_verifier: AcceptedFactoryCorpusAuthorityVerifierPort,
                              *, allow_test_only_authority: bool = False) -> dict[str, Any]:
    """Materialize an atomic phase-independent structural registry."""
    if not isinstance(config, StructuralIdentityConfig):
        raise TypeError("config must be StructuralIdentityConfig")
    accepted_corpus = _resolve_factory_authority(authority_verifier, allow_test_only_authority)
    items = tuple(sources)
    if not items:
        raise ValueError("At least one trusted Factory source is required")
    if len({item.snapshot.source_sha256 for item in items}) != len(items):
        raise ValueError("Each Factory source may occur only once per build")
    anchors: dict[str, AcceptedFactorySourceAnchor] = {}
    for item in items:
        _validate_source(item)
        anchors[item.snapshot.source_sha256] = _accepted_source_anchor(item, accepted_corpus)
        for bar in item.bars:
            _validate_bar_anchor(item, bar)

    destination = Path(database_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.unlink(missing_ok=True)
    db = sqlite3.connect(temporary)
    try:
        db.executescript(SCHEMA)
        db.executemany("INSERT INTO build_contract VALUES(?,?)", (
            ("build_contract", canonical_json(BUILD_CONTRACT)),
            ("capability", canonical_json(CAPABILITY)),
            ("mutation_capability", canonical_json(MUTATION_CAPABILITY)),
            ("identity_config", canonical_json(_semantic(config))),
            ("identity_config_sha256", canonical_json(config.semantic_sha256)),
            ("accepted_schema_v2_semantic_digest", canonical_json(accepted_corpus.schema_v2_semantic_digest)),
            ("accepted_build_config_sha256", canonical_json(accepted_corpus.build_config_sha256)),
            ("authority_id", canonical_json(accepted_corpus.authority_id)),
            ("authority_scope", canonical_json(accepted_corpus.authority_scope)),
            ("production_authority_status", canonical_json(PRODUCTION_AUTHORITY_STATUS)),
            ("calibration_envelope_allowed", canonical_json(CALIBRATION_ENVELOPE_ALLOWED)),
        ))
        authority_semantic = {"authority_scope": accepted_corpus.authority_scope,
            "database_sha256": accepted_corpus.database_sha256,
            "schema_v2_semantic_digest": accepted_corpus.schema_v2_semantic_digest,
            "build_config_sha256": accepted_corpus.build_config_sha256,
            "production_authority_status": PRODUCTION_AUTHORITY_STATUS,
            "calibration_envelope_allowed": CALIBRATION_ENVELOPE_ALLOWED,
            "source_proof_digests": [_digest({"source_sha256": item.source_sha256,
                "lineage_records": item.lineage_records,
                "source_manifest": item.source_manifest}) for item in accepted_corpus.sources]}
        if _digest(authority_semantic) != accepted_corpus.authority_id:
            raise ValueError("Opaque authority capability semantic mismatch")
        db.execute("INSERT INTO authority_proof VALUES(?,?,?,?,?,?,?,?)", (
            accepted_corpus.authority_id, accepted_corpus.authority_scope,
            accepted_corpus.database_sha256, accepted_corpus.schema_v2_semantic_digest,
            accepted_corpus.build_config_sha256, PRODUCTION_AUTHORITY_STATUS, 0,
            canonical_json(authority_semantic)))
        for item in sorted(items, key=lambda value: value.snapshot.source_sha256):
            snapshot = item.snapshot; subjects, edges = _subject_records(snapshot)
            anchor = anchors[snapshot.source_sha256]
            db.execute("INSERT INTO source_registry VALUES(?,?,?,?,?,?,?,?,?)", (
                snapshot.source_sha256, snapshot.source_kind, item.quality_status,
                canonical_json(dict(snapshot.source_manifest)), snapshot.source_lineage.semantic_sha256,
                snapshot.subject_registry.semantic_digest(), snapshot.semantic_sha256,
                accepted_corpus.schema_v2_semantic_digest, accepted_corpus.build_config_sha256))
            db.execute("INSERT INTO accepted_source_proofs VALUES(?,?,?,?,?,?,?,?)", (
                snapshot.source_sha256, accepted_corpus.authority_id, anchor.quality_status,
                anchor.lineage_sha256, canonical_json(anchor.source_manifest),
                canonical_json(anchor.metadata), canonical_json(anchor.source_semantic),
                canonical_json(dict(anchor.note_contexts))))
            for record in anchor.lineage_records:
                db.execute("INSERT INTO accepted_lineage_records VALUES(?,?,?,?,?)", (
                    snapshot.source_sha256, record["source_sha256"], record["lineage_class"],
                    canonical_json(record["parent_sha256s"]), canonical_json(record)))
            for subject in sorted(subjects, key=lambda value: value["subject_id"]):
                db.execute("INSERT INTO stable_subjects VALUES(?,?,?,?)", (
                    snapshot.source_sha256, subject["subject_id"], subject["subject_type"], canonical_json(subject)))
            for edge in sorted(edges, key=lambda value: value["edge_id"]):
                db.execute("INSERT INTO stable_edges VALUES(?,?,?,?,?,?)", (
                    snapshot.source_sha256, edge["edge_id"], edge["edge_type"], edge["parent_subject_id"],
                    edge["child_subject_id"], canonical_json(edge)))

        grouped: dict[str, list[tuple[FactoryStructuralSource, StructuralBarPrimitive,
                                     CalibrationContextPrimitives]]] = {}
        context_unproven: list[tuple[FactoryStructuralSource, StructuralBarPrimitive, str]] = []
        for item in items:
            for bar in item.bars:
                try:
                    context = _reconstruct_bar_context(
                        item, bar, anchors[item.snapshot.source_sha256])
                    base_key = _digest(_context_base(context, config))
                except (KeyError, TypeError, ValueError) as error:
                    context_unproven.append((item, bar, str(error)))
                    continue
                _validate_bar_provenance(item, bar, context)
                grouped.setdefault(base_key, []).append((item, bar, context))

        resolved_memberships = 0; ambiguous_bars = 0
        for item, bar, reason in context_unproven:
            db.execute("INSERT INTO structural_resolution VALUES(?,?,?,?,?)", (
                item.snapshot.source_sha256, bar.bar_subject_id, "STRUCTURAL_CONTEXT_UNPROVEN",
                reason, canonical_json({"contract": BUILD_CONTRACT})))
            ambiguous_bars += 1
        for base_key in sorted(grouped):
            group = sorted(grouped[base_key], key=lambda value: (
                value[0].snapshot.source_sha256, value[1].bar_subject_id))
            token_rows: list[tuple[FactoryStructuralSource, StructuralBarPrimitive,
                                   CalibrationContextPrimitives, tuple[_ClusterToken, ...]]] = []
            group_error: Exception | None = None
            for item, bar, context in group:
                try:
                    token_rows.append((item, bar, context, _bar_tokens(bar, context.voice_policy)))
                except ValueError as error:
                    group_error = error
                    break
            sequences = {_token_sequence(row[3]) for row in token_rows}
            if group_error is None and len(sequences) != 1:
                group_error = ValueError("STRUCTURAL_ALIGNMENT_AMBIGUOUS")
            if group_error is None:
                try:
                    _validate_voice_paths(row[3] for row in token_rows)
                except ValueError as error:
                    group_error = error
            if group_error is not None:
                status = _ambiguity_status(group_error)
                for item, bar, _context in group:
                    db.execute("INSERT INTO structural_resolution VALUES(?,?,?,?,?)", (
                        item.snapshot.source_sha256, bar.bar_subject_id, status, status,
                        canonical_json({"contract": BUILD_CONTRACT, "base_context_sha256": base_key})))
                    ambiguous_bars += 1
                continue

            sequence = next(iter(sequences))
            context_json, context_key = calibration_context_identity(group[0][2], sequence, config)
            db.execute("INSERT INTO structural_context_registry VALUES(?,?,?)", (
                context_key, context_json, config.semantic_sha256))
            slots: dict[tuple[int, int], str] = {}
            first_tokens = token_rows[0][3]
            for cluster_ordinal, cluster in enumerate(first_tokens):
                for voice_ordinal, voice in enumerate(cluster.ordered_voices):
                    value = voice.pitch if group[0][2].voice_policy == "EXACT_DRUM_LANE" else cluster.signature[voice_ordinal]
                    slot_json, slot_key = structural_slot_identity(
                        context_key, cluster_ordinal, cluster.cardinality, cluster.signature,
                        voice_ordinal, value, config)
                    db.execute("INSERT INTO structural_slot_registry VALUES(?,?,?)", (
                        slot_key, context_key, slot_json))
                    slots[(cluster_ordinal, voice_ordinal)] = slot_key

            seen_observations: set[tuple[str, str, str]] = set()
            for item, bar, _context, tokens in token_rows:
                cluster_by_id = {cluster.onset_cluster_subject_id: cluster for cluster in bar.clusters}
                ordered_clusters = sorted(bar.clusters, key=lambda value: value.tick)
                for cluster_ordinal, token in enumerate(tokens):
                    primitive_cluster = cluster_by_id[ordered_clusters[cluster_ordinal].onset_cluster_subject_id]
                    by_note = {voice.note_subject_id: voice for voice in primitive_cluster.voices}
                    for voice_ordinal, voice in enumerate(token.ordered_voices):
                        primitive = by_note[voice.note_subject_id]
                        slot_key = slots[(cluster_ordinal, voice_ordinal)]
                        natural_key = (item.snapshot.source_sha256, bar.bar_subject_id, slot_key)
                        if natural_key in seen_observations:
                            raise ValueError("STRUCTURAL_OBSERVATION_AMBIGUOUS")
                        seen_observations.add(natural_key)
                        provenance = {"contract": BUILD_CONTRACT, "source_sha256": item.snapshot.source_sha256,
                            "bar_subject_id": bar.bar_subject_id,
                            "onset_cluster_subject_id": primitive_cluster.onset_cluster_subject_id,
                            "note_subject_id": primitive.note_subject_id,
                            "on_event_subject_id": primitive.on_event_subject_id,
                            "track_channel_subject_id": bar.track_channel_subject_id,
                            "source_local_tick": primitive_cluster.tick,
                            "legacy_exact_context_key": bar.legacy_exact_context_key,
                            "legacy_topology_sha256": bar.legacy_topology_sha256,
                            "legacy_event_slot_key": primitive.legacy_event_slot_key,
                            "source_snapshot_sha256": item.snapshot.semantic_sha256,
                            "subject_registry_sha256": item.snapshot.subject_registry.semantic_digest()}
                        db.execute("INSERT INTO structural_slot_memberships VALUES(?,?,?,?,?,?,?,?)", (
                            item.snapshot.source_sha256, bar.bar_subject_id, slot_key,
                            primitive_cluster.onset_cluster_subject_id, primitive.note_subject_id,
                            primitive.on_event_subject_id, bar.track_channel_subject_id, canonical_json(provenance)))
                        resolved_memberships += 1
                db.execute("INSERT INTO structural_resolution VALUES(?,?,?,?,?)", (
                    item.snapshot.source_sha256, bar.bar_subject_id, "STRUCTURAL_SLOT_RESOLVED",
                    "FULL_BAR_EXACT_TOKEN_ALIGNMENT",
                    canonical_json({"contract": BUILD_CONTRACT, "calibration_context_key": context_key,
                                    "cluster_count": len(tokens)})))

        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(f"Structural registry foreign-key failure: {violations}")
        db.commit()
        digest = structural_semantic_digest(temporary)
        db.execute("INSERT INTO semantic_root VALUES('SHA256',?)", (digest,))
        db.commit()
        assert_structural_registry_surface(temporary)
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Structural registry integrity check failed")
        db.execute("VACUUM"); db.close(); db = None
        verify_structural_registry(temporary, authority_verifier,
                                   allow_test_only_authority=allow_test_only_authority)
        os.replace(temporary, destination)
        return {"capability": CAPABILITY, "mutation_capability": MUTATION_CAPABILITY,
                "sources": len(items), "resolved_memberships": resolved_memberships,
                "ambiguous_bars": ambiguous_bars, "semantic_digest": digest,
                "authority_scope": accepted_corpus.authority_scope,
                "production_authority_status": PRODUCTION_AUTHORITY_STATUS,
                "calibration_envelope_allowed": CALIBRATION_ENVELOPE_ALLOWED}
    except Exception:
        if db is not None:
            db.close()
        temporary.unlink(missing_ok=True)
        raise