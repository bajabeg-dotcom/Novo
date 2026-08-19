"""Deterministic pre-model protection adapters for X10.

The adapters consume an immutable, RAW-derived stable-subject snapshot and
emit only the sparse ANALYZE_ONLY protocol from :mod:`rhythm_protection`.
They deliberately do not parse legacy databases, infer approximate joins, or
produce MIDI changes or timing destinations.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .rhythm_protection import (
    ADAPTER_VERSION_BY_RULE,
    APPLICABILITY_PREDICATE_VERSION_BY_RULE,
    SUBJECT_UNIVERSE_QUERY_VERSION_BY_RULE,
    AdapterContract,
    AdapterRun,
    CoveragePartition,
    ProtectionEvidenceRegistry,
    ProtectionGroup,
    ProtectionGroupMembership,
    ValidatedSubjectRegistrySnapshot,
    canonical_partition_result_sha256,
    protection_config_sha256,
)
from .rhythm_subject_registry import StableSubject, StableSubjectRegistry, canonical_json


SOURCE_KINDS = (
    "FACTORY_RAW",
    "GOLD_REFERENCE_RAW",
    "HUMAN_VALIDATED_RAW",
    "SYNTHETIC_TEST",
)
FORBIDDEN_SOURCE_KINDS = (
    "SIX_SONG_DELAY_TERCA",
    "OPTIMIZER_OUTPUT",
    "REPAIRED_OUTPUT",
)
SOURCE_GUARD_POLICY_VERSION = "X10_SOURCE_GUARD_POLICY_V1"
SOURCE_LINEAGE_VERIFIER_VERSION = "X10_SOURCE_LINEAGE_VERIFIER_V1"
LINEAGE_CLASS_MATRIX_VERSION = "X10_LINEAGE_CLASS_MATRIX_V1"
SIX_SONG_FORBIDDEN_SHA256S = (
    "2b5a265a919cdbc309bcf9c086cf2d3c1930bb6a35fdd8e10d175806a58d3205",
    "715f2a1b1f566c3b147eeb0f775dd6ddd9f51ff55b731d8b696223a679b7c384",
    "d06872eea5f7793c85b6d0408b35671f6f03436271ea8025d7e917d6cd372f5c",
    "d29fea56be55892670752d5900c12f802dfe1f834a5947bf2456ae35daeda364",
    "fe3144ad138c535efc329cb85c7bd8ddc3cac49efdb84da7076eb8bb6103e684",
    "fec0b6d3517d01fc38e47064a8cceac35dd1a7d4cdc28f1d0ba1d33703f66847",
)
ALLOWED_LINEAGE_PARENT_CLASSES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "FACTORY_RAW": ("FACTORY_RAW",),
    "GOLD_REFERENCE_RAW": ("GOLD_REFERENCE_RAW",),
    "HUMAN_VALIDATED_RAW": ("HUMAN_VALIDATED_RAW",),
    "SYNTHETIC_TEST": ("SYNTHETIC_TEST",),
})


def lineage_class_matrix_sha256() -> str:
    return _digest([LINEAGE_CLASS_MATRIX_VERSION,
                    {key: list(ALLOWED_LINEAGE_PARENT_CLASSES[key])
                     for key in sorted(ALLOWED_LINEAGE_PARENT_CLASSES)}])
EXACT_ROLE_STATUS = "EXACT"
EXACT_TRACK_TYPE_STATUS = "EXACT"
RX_DNC_EVIDENCE_VERSION = "X10_RX_DNC_EVIDENCE_V1"
RX_CLAIM_STATUSES = (
    "CONFIRMED_NON_RX",
    "CONFIRMED_RX_COMPLETE",
    "CONFIRMED_RX_INCOMPLETE",
    "UNKNOWN",
    "CONFLICT",
    "CATALOG_ONLY",
    "CONFIRMED_UNJOINABLE",
)
HUMAN_EVIDENCE_KINDS = ("GRACE", "DRUM_ARTICULATION")
BOUNDARY_STATUSES = (
    "CHANGE_EXACT",
    "UNSPECIFIED_TO_EXACT",
    "CONFLICT",
    "UNSPECIFIED",
)
EXTRACTION_DOMAINS = (
    "TRACKS",
    "NOTES",
    "PHRASES",
    "SECTIONS",
    "BOUNDARIES",
    "BAR_PATTERNS",
    "RX_SUBJECTS",
    "HUMAN_COMPONENTS",
)
EXTRACTION_STATUSES = ("COMPLETE",)
EXTRACTOR_VERSION_BY_DOMAIN = {
    domain: f"X10_RAW_{domain}_EXTRACTOR_V1" for domain in EXTRACTION_DOMAINS
}


def _digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("ascii")).hexdigest()


def _require_sha(value: str, label: str) -> str:
    if (not isinstance(value, str) or len(value) != 64 or
            any(character not in "0123456789abcdef" for character in value)):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _population_digest(values: Iterable[str]) -> str:
    return _digest(sorted(values))


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise ValueError(f"Unsupported immutable semantic value: {type(value).__name__}")


def _semantic_value(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _semantic_value(getattr(value, item.name)) for item in fields(value)
                if item.init}
    if isinstance(value, Mapping):
        return {key: _semantic_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_semantic_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise ValueError(f"Unsupported semantic record value: {type(value).__name__}")


def _canonical_tuple(values: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(sorted(tuple(values), key=lambda item: canonical_json(_semantic_value(item))))


def _frozen_mapping(value: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    # Canonical round-trip rejects floats and mutable/non-JSON values.
    canonical_json(value)
    return _deep_freeze(value)


def extraction_domain_sha256(domain: str, records: Iterable[Any]) -> str:
    if domain not in EXTRACTION_DOMAINS:
        raise ValueError("Unknown extraction domain")
    payload = sorted((_semantic_value(item) for item in records), key=canonical_json)
    return _digest(["X10_EXTRACTION_ATTESTATION_V1", domain, payload])


@dataclass(frozen=True)
class ExtractionAttestation:
    domain: str
    status: str
    extractor_version: str
    semantic_sha256: str

    def __post_init__(self) -> None:
        if self.domain not in EXTRACTION_DOMAINS:
            raise ValueError("Unknown extraction attestation domain")
        if self.status not in EXTRACTION_STATUSES:
            raise ValueError("Unknown extraction attestation status")
        if not isinstance(self.extractor_version, str) or not self.extractor_version:
            raise ValueError("extractor_version is required")
        _require_sha(self.semantic_sha256, "extraction semantic_sha256")


def complete_extraction_attestation(
    domain: str,
    records: Iterable[Any],
    extractor_version: str | None = None,
) -> ExtractionAttestation:
    records = tuple(records)
    if domain not in EXTRACTOR_VERSION_BY_DOMAIN:
        raise ValueError("Unknown extraction domain")
    return ExtractionAttestation(domain, "COMPLETE",
                                 extractor_version or EXTRACTOR_VERSION_BY_DOMAIN[domain],
                                 extraction_domain_sha256(domain, records))


def rx_dnc_claims_sha256(claims: Iterable["RxDncClaim"]) -> str:
    records = sorted((_semantic_value(item) for item in claims), key=canonical_json)
    return _digest([RX_DNC_EVIDENCE_VERSION, records])


def _source_guard_policy_digest() -> str:
    return _digest([SOURCE_GUARD_POLICY_VERSION, list(SIX_SONG_FORBIDDEN_SHA256S),
                    SOURCE_LINEAGE_VERIFIER_VERSION,
                    LINEAGE_CLASS_MATRIX_VERSION, lineage_class_matrix_sha256(),
                    ["SIX_SONG_DELAY_TERCA", "OPTIMIZER_OUTPUT", "REPAIRED_OUTPUT"]])


@dataclass(frozen=True)
class SourceGuardPolicy:
    policy_version: str
    forbidden_six_song_sha256s: tuple[str, ...]
    lineage_verifier_version: str
    lineage_matrix_version: str
    lineage_matrix_sha256: str
    policy_sha256: str

    def __post_init__(self) -> None:
        if self.policy_version != SOURCE_GUARD_POLICY_VERSION:
            raise ValueError("Source guard policy version mismatch")
        forbidden = tuple(sorted(self.forbidden_six_song_sha256s))
        if forbidden != SIX_SONG_FORBIDDEN_SHA256S:
            raise ValueError("Source guard policy must contain the exact six-song SHA set")
        if self.lineage_verifier_version != SOURCE_LINEAGE_VERIFIER_VERSION:
            raise ValueError("Source lineage verifier version mismatch")
        if self.lineage_matrix_version != LINEAGE_CLASS_MATRIX_VERSION:
            raise ValueError("Source lineage class matrix version mismatch")
        if self.lineage_matrix_sha256 != lineage_class_matrix_sha256():
            raise ValueError("Source lineage class matrix digest mismatch")
        if self.policy_sha256 != _source_guard_policy_digest():
            raise ValueError("Source guard policy digest mismatch")
        object.__setattr__(self, "forbidden_six_song_sha256s", forbidden)


def trusted_source_guard_policy() -> SourceGuardPolicy:
    return SourceGuardPolicy(SOURCE_GUARD_POLICY_VERSION, SIX_SONG_FORBIDDEN_SHA256S,
                             SOURCE_LINEAGE_VERIFIER_VERSION, LINEAGE_CLASS_MATRIX_VERSION,
                             lineage_class_matrix_sha256(), _source_guard_policy_digest())


@dataclass(frozen=True)
class SourceLineageRecord:
    source_sha256: str
    lineage_class: str
    parent_sha256s: tuple[str, ...]
    record_version: str = SOURCE_LINEAGE_VERIFIER_VERSION
    record_id: str = field(init=False)

    def __post_init__(self) -> None:
        _require_sha(self.source_sha256, "lineage source_sha256")
        if self.lineage_class not in SOURCE_KINDS + FORBIDDEN_SOURCE_KINDS:
            raise ValueError("Unknown source lineage kind")
        parents = tuple(sorted(self.parent_sha256s))
        if len(parents) != len(set(parents)):
            raise ValueError("Source lineage parents cannot contain duplicates")
        for parent in parents:
            _require_sha(parent, "lineage parent_sha256")
        if self.record_version != SOURCE_LINEAGE_VERIFIER_VERSION:
            raise ValueError("Source lineage verifier version mismatch")
        object.__setattr__(self, "parent_sha256s", parents)
        payload = [self.record_version, self.source_sha256, self.lineage_class, list(parents)]
        object.__setattr__(self, "record_id", _digest(payload))

    @property
    def semantic_record(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "record_version": self.record_version,
            "source_sha256": self.source_sha256,
            "lineage_class": self.lineage_class,
            "parent_sha256s": self.parent_sha256s,
            "record_id": self.record_id,
        })


def lineage_inventory_sha256(records: Iterable[SourceLineageRecord | Mapping[str, Any]]) -> str:
    semantic = []
    for record in records:
        value = record.semantic_record if isinstance(record, SourceLineageRecord) else record
        semantic.append(_semantic_value(value))
    semantic.sort(key=lambda item: item["source_sha256"])
    return _digest([SOURCE_LINEAGE_VERIFIER_VERSION, semantic])


class TrustedSourceLineageSnapshot:
    """Validated immutable lineage DAG; direct verified-flag assertion is impossible."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("TrustedSourceLineageSnapshot must be created from canonical semantic records")

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("TrustedSourceLineageSnapshot is immutable")
        object.__setattr__(self, name, value)

    @classmethod
    def from_semantic_records(
        cls,
        records: Iterable[Mapping[str, Any]],
        expected_inventory_sha256: str,
    ) -> "TrustedSourceLineageSnapshot":
        _require_sha(expected_inventory_sha256, "expected lineage inventory SHA")
        required = {"record_version", "source_sha256", "lineage_class",
                    "parent_sha256s", "record_id"}
        rebuilt: dict[str, SourceLineageRecord] = {}
        for raw in records:
            if not isinstance(raw, Mapping) or set(raw) != required:
                raise ValueError("Canonical source lineage semantic record fields are required")
            record = SourceLineageRecord(raw["source_sha256"], raw["lineage_class"],
                                         tuple(raw["parent_sha256s"]), raw["record_version"])
            if raw["record_id"] != record.record_id:
                raise ValueError("Source lineage record ID mismatch")
            if canonical_json(_semantic_value(raw)) != canonical_json(
                    _semantic_value(record.semantic_record)):
                raise ValueError("Source lineage semantic record is not canonical")
            previous = rebuilt.get(record.source_sha256)
            if previous is not None and previous != record:
                raise ValueError("Contradictory source lineage record")
            if previous is not None:
                raise ValueError("Duplicate source lineage record")
            rebuilt[record.source_sha256] = record
        for record in rebuilt.values():
            missing = sorted(set(record.parent_sha256s) - set(rebuilt))
            if missing:
                raise ValueError(f"Source lineage parent is missing: {missing}")
            if record.lineage_class in FORBIDDEN_SOURCE_KINDS:
                raise ValueError("Forbidden lineage class cannot enter WP-012B evidence")
            allowed = ALLOWED_LINEAGE_PARENT_CLASSES.get(record.lineage_class)
            if allowed is None:
                raise ValueError("Unknown lineage class matrix subject")
            for parent_id in record.parent_sha256s:
                parent_class = rebuilt[parent_id].lineage_class
                if parent_class not in allowed:
                    raise ValueError(
                        f"Illegal lineage parent class {parent_class} for {record.lineage_class}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(source_id: str) -> None:
            if source_id in visiting:
                raise ValueError("Source lineage cycle is forbidden")
            if source_id in visited:
                return
            visiting.add(source_id)
            for parent in rebuilt[source_id].parent_sha256s:
                visit(parent)
            visiting.remove(source_id)
            visited.add(source_id)

        for source_id in sorted(rebuilt):
            visit(source_id)
        for source_id, record in rebuilt.items():
            closure: set[str] = set()

            def collect(parent_source_id: str) -> None:
                for ancestor in rebuilt[parent_source_id].parent_sha256s:
                    if ancestor not in closure:
                        closure.add(ancestor)
                        collect(ancestor)

            collect(source_id)
            illegal = sorted({rebuilt[item].lineage_class for item in closure} -
                             set(ALLOWED_LINEAGE_PARENT_CLASSES[record.lineage_class]))
            if illegal:
                raise ValueError(
                    f"Illegal transitive lineage class for {record.lineage_class}: {illegal}")
        digest = lineage_inventory_sha256(record.semantic_record for record in rebuilt.values())
        if digest != expected_inventory_sha256:
            raise ValueError("Source lineage inventory digest mismatch")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_records", MappingProxyType(dict(sorted(rebuilt.items()))))
        object.__setattr__(instance, "semantic_sha256", digest)
        object.__setattr__(instance, "_sealed", True)
        return instance

    @property
    def records(self) -> tuple[SourceLineageRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def record_for(self, source_sha256: str) -> SourceLineageRecord | None:
        return self._records.get(source_sha256)

    def ancestor_closure(self, source_sha256: str, *, include_self: bool = True) -> tuple[str, ...]:
        if source_sha256 not in self._records:
            raise ValueError("Source lineage record is missing")
        closure: set[str] = set()

        def collect(source_id: str) -> None:
            for parent in self._records[source_id].parent_sha256s:
                if parent not in closure:
                    closure.add(parent)
                    collect(parent)

        collect(source_sha256)
        if include_self:
            closure.add(source_sha256)
        return tuple(sorted(closure))


def trusted_source_lineage_snapshot(
    records: Iterable[SourceLineageRecord | Mapping[str, Any]],
) -> TrustedSourceLineageSnapshot:
    records = tuple(records)
    semantic = tuple(record.semantic_record if isinstance(record, SourceLineageRecord) else record
                     for record in records)
    return TrustedSourceLineageSnapshot.from_semantic_records(
        semantic, lineage_inventory_sha256(semantic))


class FrozenStableSubjectRegistry(StableSubjectRegistry):
    """A deep-frozen registry copy safe to retain inside an adapter snapshot."""

    def __init__(self, subjects: Iterable[Any], edges: Iterable[Any]) -> None:
        super().__init__()
        self._sealed = False
        subjects = tuple(subjects)
        structural = {"ONSET_CLUSTER", "PHRASE", "COMPONENT"}
        for subject in sorted((item for item in subjects if item.subject_type not in structural),
                              key=lambda item: item.subject_id):
            super().add_subject(subject)
        pending = {item.subject_id: item for item in subjects if item.subject_type in structural}
        while pending:
            progressed = False
            for subject_id in sorted(tuple(pending)):
                subject = pending[subject_id]
                key = "on_event_ids" if subject.subject_type == "ONSET_CLUSTER" else "ordered_note_ids"
                if not set(subject.natural_key[key]).issubset(self._subjects):
                    continue
                super().add_subject(subject)
                pending.pop(subject_id)
                progressed = True
            if not progressed:
                raise ValueError("Frozen structural subject dependencies are unresolved")
        for edge in edges:
            super().add_edge(edge)
        self._sealed = True

    def add_subject(self, subject: Any) -> Any:
        if self._sealed:
            raise TypeError("Frozen stable subject registry is immutable")
        return super().add_subject(subject)

    def add_edge(self, edge: Any) -> Any:
        if self._sealed:
            raise TypeError("Frozen stable subject registry is immutable")
        return super().add_edge(edge)

    def extend_subjects(self, subjects: Iterable[Any]) -> None:
        if self._sealed:
            raise TypeError("Frozen stable subject registry is immutable")
        super().extend_subjects(subjects)


@dataclass(frozen=True)
class TrackObservation:
    track_subject_id: str
    track_index: int
    channel: int
    role: str = "UNKNOWN"
    role_status: str = "UNKNOWN"
    instrument_class: str = "UNKNOWN"
    instrument_class_status: str = "UNKNOWN"
    track_type: str = "UNKNOWN"
    track_type_status: str = "UNKNOWN"
    command_subject_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_sha(self.track_subject_id, "track_subject_id")
        if (not isinstance(self.track_index, int) or isinstance(self.track_index, bool) or
                self.track_index < 0):
            raise ValueError("track_index must be a nonnegative integer")
        if (not isinstance(self.channel, int) or isinstance(self.channel, bool) or
                not 0 <= self.channel <= 15):
            raise ValueError("channel must be an integer from 0 to 15")
        for value in (self.role, self.role_status, self.instrument_class,
                      self.instrument_class_status, self.track_type, self.track_type_status):
            if not isinstance(value, str) or not value:
                raise ValueError("Track observation tokens must be non-empty strings")
        commands = tuple(sorted(self.command_subject_ids))
        if len(commands) != len(set(commands)):
            raise ValueError("command_subject_ids cannot contain duplicates")
        for subject_id in commands:
            _require_sha(subject_id, "command_subject_id")
        object.__setattr__(self, "command_subject_ids", commands)


@dataclass(frozen=True)
class NoteObservation:
    note_subject_id: str
    track_subject_id: str
    phrase_subject_id: str | None
    onset_cluster_id: str
    bar_subject_id: str
    meter_segment_id: str
    pitch: int
    start_tick: int
    end_tick: int
    bar_start_tick: int
    bar_end_tick: int
    meter_status: str

    def __post_init__(self) -> None:
        for label, value in (("note_subject_id", self.note_subject_id),
                             ("track_subject_id", self.track_subject_id),
                             ("onset_cluster_id", self.onset_cluster_id),
                             ("bar_subject_id", self.bar_subject_id),
                             ("meter_segment_id", self.meter_segment_id)):
            _require_sha(value, label)
        if self.phrase_subject_id is not None:
            _require_sha(self.phrase_subject_id, "phrase_subject_id")
        if (not isinstance(self.pitch, int) or isinstance(self.pitch, bool) or
                not 0 <= self.pitch <= 127):
            raise ValueError("pitch must be an integer from 0 to 127")
        ticks = (self.start_tick, self.end_tick, self.bar_start_tick, self.bar_end_tick)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in ticks):
            raise ValueError("Note/bar ticks must be nonnegative integers")
        if self.end_tick < self.start_tick or self.bar_end_tick <= self.bar_start_tick:
            raise ValueError("Note/bar tick interval is invalid")
        if not isinstance(self.meter_status, str) or not self.meter_status:
            raise ValueError("meter_status is required")


@dataclass(frozen=True)
class PhraseObservation:
    phrase_subject_id: str
    track_subject_id: str
    ordered_note_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha(self.phrase_subject_id, "phrase_subject_id")
        _require_sha(self.track_subject_id, "track_subject_id")
        if not self.ordered_note_ids or len(self.ordered_note_ids) != len(set(self.ordered_note_ids)):
            raise ValueError("ordered_note_ids must be non-empty and unique")
        for subject_id in self.ordered_note_ids:
            _require_sha(subject_id, "ordered_note_id")


@dataclass(frozen=True)
class SectionObservation:
    track_subject_id: str
    section: str
    section_status: str
    provenance_method: str
    ordered_bar_ids: tuple[str, ...]
    note_ids_by_bar: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_sha(self.track_subject_id, "track_subject_id")
        if not all(isinstance(item, str) and item for item in
                   (self.section, self.section_status, self.provenance_method)):
            raise ValueError("Section tokens must be non-empty strings")
        if not self.ordered_bar_ids or len(self.ordered_bar_ids) != len(set(self.ordered_bar_ids)):
            raise ValueError("ordered_bar_ids must be non-empty and unique")
        for bar_id in self.ordered_bar_ids:
            _require_sha(bar_id, "ordered_bar_id")
        normalized: dict[str, tuple[str, ...]] = {}
        for bar_id, note_ids in self.note_ids_by_bar.items():
            _require_sha(bar_id, "note_ids_by_bar key")
            if bar_id not in self.ordered_bar_ids:
                raise ValueError("note_ids_by_bar key must belong to ordered_bar_ids")
            values = tuple(sorted(note_ids))
            if len(values) != len(set(values)):
                raise ValueError("note_ids_by_bar cannot contain duplicate note IDs")
            for note_id in values:
                _require_sha(note_id, "section note_id")
            normalized[bar_id] = values
        object.__setattr__(self, "note_ids_by_bar", MappingProxyType(normalized))


@dataclass(frozen=True)
class BoundaryObservation:
    boundary_subject_id: str
    boundary_kind: str
    boundary_status: str
    tick: int
    affected_subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha(self.boundary_subject_id, "boundary_subject_id")
        if self.boundary_kind not in {"TEMPO", "METER"}:
            raise ValueError("boundary_kind must be TEMPO or METER")
        if self.boundary_status not in BOUNDARY_STATUSES:
            raise ValueError("Unknown boundary_status")
        if not isinstance(self.tick, int) or isinstance(self.tick, bool) or self.tick < 0:
            raise ValueError("Boundary tick must be a nonnegative integer")
        values = tuple(sorted(self.affected_subject_ids))
        if not values or len(values) != len(set(values)):
            raise ValueError("affected_subject_ids must be non-empty and unique")
        for subject_id in values:
            _require_sha(subject_id, "affected_subject_id")
        object.__setattr__(self, "affected_subject_ids", values)


@dataclass(frozen=True)
class BarPatternObservation:
    bar_subject_id: str
    track_subject_id: str
    meter_segment_id: str
    rhythm_sha256: str
    topology_sha256: str
    member_subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for label, value in (("bar_subject_id", self.bar_subject_id),
                             ("track_subject_id", self.track_subject_id),
                             ("meter_segment_id", self.meter_segment_id),
                             ("rhythm_sha256", self.rhythm_sha256),
                             ("topology_sha256", self.topology_sha256)):
            _require_sha(value, label)
        members = tuple(sorted(self.member_subject_ids))
        if not members or len(members) != len(set(members)):
            raise ValueError("Bar pattern members must be non-empty and unique")
        for subject_id in members:
            _require_sha(subject_id, "bar pattern member_subject_id")
        object.__setattr__(self, "member_subject_ids", members)


@dataclass(frozen=True)
class RxSubjectObservation:
    stable_subject_id: str
    program_segment_id: str
    program_status: str
    bank_msb: int | None
    bank_lsb: int | None
    program: int | None

    def __post_init__(self) -> None:
        _require_sha(self.stable_subject_id, "RX stable_subject_id")
        _require_sha(self.program_segment_id, "RX program_segment_id")
        if not isinstance(self.program_status, str) or not self.program_status:
            raise ValueError("program_status is required")
        for label, value in (("bank_msb", self.bank_msb), ("bank_lsb", self.bank_lsb),
                             ("program", self.program)):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or
                                      not 0 <= value <= 127):
                raise ValueError(f"{label} must be None or an integer from 0 to 127")

    @property
    def address(self) -> tuple[int, int, int] | None:
        if (self.program_status != "PROGRAM_EXACT" or self.bank_msb is None or
                self.bank_lsb is None or self.program is None):
            return None
        return self.bank_msb, self.bank_lsb, self.program


@dataclass(frozen=True)
class RxDncClaim:
    address: tuple[int, int, int]
    status: str
    evidence_sha256: str
    evidence_locator: str
    trigger_subject_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (not isinstance(self.address, tuple) or len(self.address) != 3 or
                any(not isinstance(value, int) or isinstance(value, bool) or
                    not 0 <= value <= 127 for value in self.address)):
            raise ValueError("RX address must contain three MIDI 0..127 integers")
        if self.status not in RX_CLAIM_STATUSES:
            raise ValueError("Unknown RX/DNC claim status")
        _require_sha(self.evidence_sha256, "RX evidence_sha256")
        if not isinstance(self.evidence_locator, str) or not self.evidence_locator:
            raise ValueError("RX evidence_locator is required")
        triggers = tuple(sorted(self.trigger_subject_ids))
        if len(triggers) != len(set(triggers)):
            raise ValueError("RX trigger_subject_ids cannot contain duplicates")
        for subject_id in triggers:
            _require_sha(subject_id, "RX trigger_subject_id")
        if self.status != "CONFIRMED_RX_COMPLETE" and triggers:
            raise ValueError("Only complete confirmed RX claims may enumerate triggers")
        object.__setattr__(self, "trigger_subject_ids", triggers)


@dataclass(frozen=True)
class RxDncEvidenceSnapshot:
    version: str
    registry_sha256: str
    claims: tuple[RxDncClaim, ...]

    def __post_init__(self) -> None:
        if self.version != RX_DNC_EVIDENCE_VERSION:
            raise ValueError("RX/DNC evidence version mismatch")
        _require_sha(self.registry_sha256, "RX registry_sha256")
        ordered = tuple(sorted(self.claims, key=lambda item: item.address))
        addresses = [item.address for item in ordered]
        if len(addresses) != len(set(addresses)):
            raise ValueError("RX/DNC claims require unique exact addresses")
        if self.registry_sha256 != rx_dnc_claims_sha256(ordered):
            raise ValueError("RX/DNC Evidence Registry semantic digest mismatch")
        object.__setattr__(self, "claims", ordered)

    @property
    def by_address(self) -> Mapping[tuple[int, int, int], RxDncClaim]:
        return MappingProxyType({claim.address: claim for claim in self.claims})


@dataclass(frozen=True)
class HumanValidatedComponent:
    evidence_kind: str
    component_subject_id: str
    member_subject_ids: tuple[str, ...]
    source_sha256: str
    evidence_sha256: str
    evidence_locator: str
    provenance: str = "HUMAN_OWNER"

    def __post_init__(self) -> None:
        if self.evidence_kind not in HUMAN_EVIDENCE_KINDS:
            raise ValueError("Unknown Human evidence kind")
        for label, value in (("component_subject_id", self.component_subject_id),
                             ("source_sha256", self.source_sha256),
                             ("evidence_sha256", self.evidence_sha256)):
            _require_sha(value, label)
        if self.provenance != "HUMAN_OWNER":
            raise ValueError("Hardware/human evidence requires HUMAN_OWNER provenance")
        if not isinstance(self.evidence_locator, str) or not self.evidence_locator:
            raise ValueError("Human evidence_locator is required")
        members = tuple(self.member_subject_ids)
        if not members or len(members) != len(set(members)):
            raise ValueError("Human evidence members must be non-empty and unique")
        for subject_id in members:
            _require_sha(subject_id, "Human evidence member_subject_id")
        object.__setattr__(self, "member_subject_ids", members)


@dataclass(frozen=True)
class StructuralSourceSnapshot:
    source_sha256: str
    source_kind: str
    subject_registry: StableSubjectRegistry | ValidatedSubjectRegistrySnapshot
    scope_subject_id: str
    extraction_attestations: tuple[ExtractionAttestation, ...]
    source_guard_policy: SourceGuardPolicy
    source_lineage: TrustedSourceLineageSnapshot
    tracks: tuple[TrackObservation, ...] = ()
    notes: tuple[NoteObservation, ...] = ()
    phrases: tuple[PhraseObservation, ...] = ()
    sections: tuple[SectionObservation, ...] = ()
    boundaries: tuple[BoundaryObservation, ...] = ()
    bar_patterns: tuple[BarPatternObservation, ...] = ()
    rx_subjects: tuple[RxSubjectObservation, ...] = ()
    human_components: tuple[HumanValidatedComponent, ...] = ()
    rx_evidence: RxDncEvidenceSnapshot | None = None
    source_manifest: Mapping[str, Any] = field(default_factory=dict)
    semantic_sha256: str = field(init=False)
    _subjects: tuple[Any, ...] = field(init=False, repr=False)
    _edges: tuple[Any, ...] = field(init=False, repr=False)
    _subjects_by_id: Mapping[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _require_sha(self.source_sha256, "source_sha256")
        if not isinstance(self.source_guard_policy, SourceGuardPolicy):
            raise TypeError("A trusted SourceGuardPolicy is mandatory")
        if not isinstance(self.source_lineage, TrustedSourceLineageSnapshot):
            raise TypeError("A TrustedSourceLineageSnapshot is mandatory")
        source_record = self.source_lineage.record_for(self.source_sha256)
        if source_record is None:
            raise ValueError("Source lineage record is missing")
        closure = self.source_lineage.ancestor_closure(self.source_sha256)
        forbidden_ancestors = sorted(set(closure).intersection(
            self.source_guard_policy.forbidden_six_song_sha256s))
        if forbidden_ancestors:
            raise ValueError(f"Forbidden six-song SHA exists in source lineage: {forbidden_ancestors}")
        forbidden_classes = sorted({self.source_lineage.record_for(item).lineage_class
                                    for item in closure
                                    if self.source_lineage.record_for(item).lineage_class in
                                    FORBIDDEN_SOURCE_KINDS})
        if forbidden_classes:
            raise ValueError("Optimizer/repaired/six-song lineage cannot enter protection adapters")
        if source_record.lineage_class != self.source_kind:
            raise ValueError("source_kind cannot override verified source lineage")
        if self.source_kind in FORBIDDEN_SOURCE_KINDS or self.source_kind not in SOURCE_KINDS:
            raise ValueError("Forbidden or unknown protection-adapter source kind")
        if not isinstance(self.subject_registry, StableSubjectRegistry):
            raise TypeError("StructuralSourceSnapshot input requires StableSubjectRegistry")
        subject_records = tuple(_deep_freeze(item.semantic_record)
                                for item in self.subject_registry.subjects)
        edge_records = tuple(_deep_freeze({
            "contract_version": item.contract_version,
            "edge_type": item.edge_type,
            "source_sha256": item.source_sha256,
            "parent_subject_id": item.parent_subject_id,
            "child_subject_id": item.child_subject_id,
            "edge_id": item.edge_id,
        }) for item in self.subject_registry.edges)
        registry_digest = self.subject_registry.semantic_digest()
        validated = ValidatedSubjectRegistrySnapshot.from_semantic_records(
            tuple(_semantic_value(item) for item in subject_records), registry_digest,
            tuple(_semantic_value(item) for item in edge_records))
        # Clone semantic subjects and deep-freeze their natural keys.  Adapters
        # never retain or read the caller's mutable registry after this point.
        frozen_subjects = []
        for record in subject_records:
            subject = StableSubject(record["subject_type"], record["source_sha256"],
                                    _semantic_value(record["natural_key"]),
                                    record["contract_version"])
            object.__setattr__(subject, "natural_key", _deep_freeze(subject.natural_key))
            frozen_subjects.append(subject)
        frozen_subjects = tuple(sorted(frozen_subjects, key=lambda item: item.subject_id))
        frozen_edges = tuple(sorted(self.subject_registry.edges, key=lambda item: item.edge_id))
        subjects = MappingProxyType({item.subject_id: item for item in frozen_subjects})
        frozen_registry = FrozenStableSubjectRegistry(frozen_subjects, frozen_edges)
        if frozen_registry.semantic_digest() != validated.semantic_sha256:
            raise ValueError("Frozen stable subject registry digest mismatch")
        object.__setattr__(self, "subject_registry", frozen_registry)
        object.__setattr__(self, "_subjects", frozen_subjects)
        object.__setattr__(self, "_edges", frozen_edges)
        object.__setattr__(self, "_subjects_by_id", subjects)
        scope = subjects.get(self.scope_subject_id)
        if scope is None or scope.source_sha256 != self.source_sha256:
            raise ValueError("scope_subject_id must be registered in the source")
        if scope.subject_type != "EXACT_CONTEXT":
            raise ValueError("Protection adapter source scope must be EXACT_CONTEXT")
        if any(item.source_sha256 != self.source_sha256 for item in subjects.values()):
            raise ValueError("Protection adapter registry must contain exactly one source")
        for name in ("tracks", "notes", "phrases", "sections", "boundaries",
                     "bar_patterns", "rx_subjects", "human_components"):
            object.__setattr__(self, name, _canonical_tuple(getattr(self, name)))
        attestations = _canonical_tuple(self.extraction_attestations)
        if len(attestations) != len({item.domain for item in attestations}):
            raise ValueError("Extraction attestations require unique domains")
        object.__setattr__(self, "extraction_attestations", attestations)
        manifest = _frozen_mapping(self.source_manifest, "source_manifest")
        declared_class = manifest.get("source_class")
        if declared_class is not None and declared_class != self.source_kind:
            raise ValueError("Source manifest class contradicts source_kind")
        if manifest.get("is_optimizer_output") or manifest.get("is_repaired_output"):
            raise ValueError("Optimizer/repaired output cannot enter protection adapters")
        if manifest.get("is_six_song_delay_terca"):
            raise ValueError("Six Delay/Terca songs cannot enter protection adapters")
        if manifest.get("lineage_sha256") != self.source_lineage.semantic_sha256:
            raise ValueError("Source manifest lineage digest is missing or unverified")
        object.__setattr__(self, "source_manifest", manifest)
        self._validate_subject_references(subjects)
        self._validate_extraction_attestations()
        self._validate_registry_extraction_coverage(subjects)
        object.__setattr__(self, "semantic_sha256", self.recompute_semantic_sha256())

    def _semantic_payload(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "source_kind": self.source_kind,
            "registry_sha256": self.subject_registry.semantic_digest(),
            "subject_records": [_semantic_value(item.semantic_record) for item in self._subjects],
            "edge_records": [_semantic_value({
                "contract_version": item.contract_version,
                "edge_type": item.edge_type,
                "source_sha256": item.source_sha256,
                "parent_subject_id": item.parent_subject_id,
                "child_subject_id": item.child_subject_id,
                "edge_id": item.edge_id,
            }) for item in self._edges],
            "scope_subject_id": self.scope_subject_id,
            "source_guard_policy": _semantic_value(self.source_guard_policy),
            "source_lineage": {
                "semantic_sha256": self.source_lineage.semantic_sha256,
                "records": [_semantic_value(item.semantic_record)
                            for item in self.source_lineage.records],
                "ancestor_closure": list(self.source_lineage.ancestor_closure(
                    self.source_sha256)),
            },
            "extraction_attestations": [_semantic_value(item) for item in self.extraction_attestations],
            "tracks": [_semantic_value(item) for item in self.tracks],
            "notes": [_semantic_value(item) for item in self.notes],
            "phrases": [_semantic_value(item) for item in self.phrases],
            "sections": [_semantic_value(item) for item in self.sections],
            "boundaries": [_semantic_value(item) for item in self.boundaries],
            "bar_patterns": [_semantic_value(item) for item in self.bar_patterns],
            "rx_subjects": [_semantic_value(item) for item in self.rx_subjects],
            "human_components": [_semantic_value(item) for item in self.human_components],
            "rx_evidence": None if self.rx_evidence is None else _semantic_value(self.rx_evidence),
            "source_manifest": _semantic_value(self.source_manifest),
        }

    def recompute_semantic_sha256(self) -> str:
        return _digest(self._semantic_payload())

    def _validate_extraction_attestations(self) -> None:
        by_domain = {item.domain: item for item in self.extraction_attestations}
        missing = sorted(set(EXTRACTION_DOMAINS) - set(by_domain))
        if missing:
            raise ValueError(f"Missing core extraction attestations: {missing}")
        domain_records = {
            "TRACKS": self.tracks,
            "NOTES": self.notes,
            "PHRASES": self.phrases,
            "SECTIONS": self.sections,
            "BOUNDARIES": self.boundaries,
            "BAR_PATTERNS": self.bar_patterns,
            "RX_SUBJECTS": self.rx_subjects,
            "HUMAN_COMPONENTS": self.human_components,
        }
        for domain in EXTRACTION_DOMAINS:
            attestation = by_domain[domain]
            expected = extraction_domain_sha256(domain, domain_records[domain])
            if (attestation.status != "COMPLETE" or
                    attestation.extractor_version != EXTRACTOR_VERSION_BY_DOMAIN[domain] or
                    attestation.semantic_sha256 != expected):
                raise ValueError(f"Core extraction attestation mismatch for {domain}")

    def require_domains(self, *domains: str) -> None:
        by_domain = {item.domain: item for item in self.extraction_attestations}
        for domain in domains:
            if domain not in EXTRACTION_DOMAINS or domain not in by_domain:
                raise ValueError(f"Missing core extraction attestation: {domain}")
            if by_domain[domain].status != "COMPLETE":
                raise ValueError(f"Core extraction is incomplete: {domain}")

    def _validate_registry_extraction_coverage(self, subjects: Mapping[str, Any]) -> None:
        by_type: dict[str, set[str]] = {}
        for subject in subjects.values():
            by_type.setdefault(subject.subject_type, set()).add(subject.subject_id)
        coverage = {
            "TRACKS": {item.track_subject_id for item in self.tracks},
            "NOTES": {item.note_subject_id for item in self.notes},
            "PHRASES": {item.phrase_subject_id for item in self.phrases},
            "BOUNDARIES": {item.boundary_subject_id for item in self.boundaries},
            "BAR_PATTERNS": {(item.track_subject_id, item.bar_subject_id)
                             for item in self.bar_patterns},
            "SECTIONS": {item.track_subject_id for item in self.sections},
        }
        expected = {
            "TRACKS": by_type.get("TRACK_CHANNEL", set()),
            "NOTES": by_type.get("NOTE", set()),
            "PHRASES": by_type.get("PHRASE", set()),
            "BOUNDARIES": by_type.get("BOUNDARY", set()),
            "BAR_PATTERNS": {(note.track_subject_id, note.bar_subject_id)
                             for note in self.notes},
            "SECTIONS": {note.track_subject_id for note in self.notes},
        }
        for domain, expected_ids in expected.items():
            if coverage[domain] != expected_ids:
                missing = sorted(expected_ids - coverage[domain])
                extra = sorted(coverage[domain] - expected_ids)
                raise ValueError(
                    f"Core extraction registry coverage mismatch for {domain}; "
                    f"missing={missing}, extra={extra}")

    def _validate_subject_references(self, subjects: Mapping[str, Any]) -> None:
        expected_types: list[tuple[str, str]] = [(self.scope_subject_id, "EXACT_CONTEXT")]
        for track in self.tracks:
            expected_types.append((track.track_subject_id, "TRACK_CHANNEL"))
            for item in track.command_subject_ids:
                subject = subjects.get(item)
                if subject is None or subject.subject_type not in {"EVENT", "COMPONENT"}:
                    raise ValueError("Guitar command must be a registered EVENT or COMPONENT")
                expected_types.append((item, subject.subject_type))
        for note in self.notes:
            expected_types.extend(((note.note_subject_id, "NOTE"),
                                   (note.track_subject_id, "TRACK_CHANNEL"),
                                   (note.onset_cluster_id, "ONSET_CLUSTER"),
                                   (note.bar_subject_id, "BAR")))
            if note.phrase_subject_id is not None:
                expected_types.append((note.phrase_subject_id, "PHRASE"))
        for phrase in self.phrases:
            expected_types.extend(((phrase.phrase_subject_id, "PHRASE"),
                                   (phrase.track_subject_id, "TRACK_CHANNEL")))
            expected_types.extend((item, "NOTE") for item in phrase.ordered_note_ids)
        for section in self.sections:
            expected_types.append((section.track_subject_id, "TRACK_CHANNEL"))
            expected_types.extend((item, "BAR") for item in section.ordered_bar_ids)
            for values in section.note_ids_by_bar.values():
                expected_types.extend((item, "NOTE") for item in values)
        for boundary in self.boundaries:
            expected_types.append((boundary.boundary_subject_id, "BOUNDARY"))
            for item in boundary.affected_subject_ids:
                subject = subjects.get(item)
                if subject is None or subject.subject_type not in {
                        "NOTE", "ONSET_CLUSTER", "BAR", "PHRASE"}:
                    raise ValueError("Boundary member must be a registered note/cluster/bar/phrase")
                expected_types.append((item, subject.subject_type))
        for item in self.bar_patterns:
            expected_types.extend(((item.bar_subject_id, "BAR"),
                                   (item.track_subject_id, "TRACK_CHANNEL")))
            expected_types.extend((member_id, "NOTE") for member_id in item.member_subject_ids)
        for item in self.rx_subjects:
            subject = subjects.get(item.stable_subject_id)
            if subject is None or subject.subject_type != "NOTE":
                raise ValueError("RX v1 observation must join a registered NOTE subject")
            expected_types.append((item.stable_subject_id, "NOTE"))
            expected_types.append((item.program_segment_id, "PROGRAM_SEGMENT"))
        for component in self.human_components:
            if component.source_sha256 != self.source_sha256:
                raise ValueError("Human evidence belongs to another source")
            expected_types.append((component.component_subject_id, "COMPONENT"))
            for item in component.member_subject_ids:
                subject = subjects.get(item)
                if subject is None:
                    raise ValueError("Human evidence member is not registered")
                expected_types.append((item, subject.subject_type))
        for subject_id, expected_type in expected_types:
            subject = subjects.get(subject_id)
            if subject is None:
                raise ValueError("Adapter observation references an unregistered stable subject")
            if subject.source_sha256 != self.source_sha256:
                raise ValueError("Adapter observation contains a cross-source subject")
            if subject.subject_type != expected_type:
                raise ValueError(f"Adapter observation expected {expected_type} subject")
        track_ids = [item.track_subject_id for item in self.tracks]
        note_ids = [item.note_subject_id for item in self.notes]
        phrase_ids = [item.phrase_subject_id for item in self.phrases]
        section_track_ids = [item.track_subject_id for item in self.sections]
        boundary_ids = [item.boundary_subject_id for item in self.boundaries]
        pattern_pairs = [(item.track_subject_id, item.bar_subject_id)
                         for item in self.bar_patterns]
        rx_subject_ids = [item.stable_subject_id for item in self.rx_subjects]
        human_component_ids = [item.component_subject_id for item in self.human_components]
        if any(len(values) != len(set(values)) for values in (
                track_ids, note_ids, phrase_ids, section_track_ids, boundary_ids,
                pattern_pairs, rx_subject_ids, human_component_ids)):
            raise ValueError("Adapter observations require unique stable natural subjects")
        command_owners: dict[str, str] = {}
        for track in self.tracks:
            stable_track = subjects[track.track_subject_id]
            if (stable_track.natural_key.get("track_index") != track.track_index or
                    stable_track.natural_key.get("channel") != track.channel):
                raise ValueError("Track observation contradicts stable TRACK_CHANNEL coordinates")
            for command_id in track.command_subject_ids:
                previous = command_owners.setdefault(command_id, track.track_subject_id)
                if previous != track.track_subject_id:
                    raise ValueError("Guitar command subject cannot belong to multiple tracks")
        observed_tracks = set(track_ids)
        note_map = {item.note_subject_id: item for item in self.notes}
        phrase_map = {item.phrase_subject_id: item for item in self.phrases}
        edge_keys = {(item.edge_type, item.parent_subject_id, item.child_subject_id)
                     for item in self._edges}
        for note in self.notes:
            if note.track_subject_id not in observed_tracks:
                raise ValueError("Note track is missing from track observations")
            if note.phrase_subject_id is not None and note.phrase_subject_id not in phrase_map:
                raise ValueError("Note phrase reference is not present in phrase observations")
            bar = subjects[note.bar_subject_id]
            if (bar.natural_key.get("start_tick") != note.bar_start_tick or
                    bar.natural_key.get("end_tick") != note.bar_end_tick or
                    bar.natural_key.get("meter_segment_id") != note.meter_segment_id):
                raise ValueError("Note bar interval contradicts stable BAR subject")
            if not note.bar_start_tick <= note.start_tick < note.bar_end_tick:
                raise ValueError("Note onset must belong to its exact stable BAR interval")
            cluster = subjects[note.onset_cluster_id]
            track_observation = next(item for item in self.tracks
                                     if item.track_subject_id == note.track_subject_id)
            if (cluster.natural_key.get("tick") != note.start_tick or
                    cluster.natural_key.get("meter_segment_id") != note.meter_segment_id or
                    cluster.natural_key.get("track_index") != track_observation.track_index or
                    cluster.natural_key.get("channel") != track_observation.channel):
                raise ValueError("Note onset contradicts exact ONSET_CLUSTER coordinates")
        for phrase in self.phrases:
            if phrase.track_subject_id not in observed_tracks:
                raise ValueError("Phrase track is missing from track observations")
            stable_members = tuple(subjects[phrase.phrase_subject_id].natural_key["ordered_note_ids"])
            if stable_members != phrase.ordered_note_ids:
                raise ValueError("Phrase observation contradicts stable PHRASE membership")
            for note_id in phrase.ordered_note_ids:
                note = note_map.get(note_id)
                if (note is None or note.phrase_subject_id != phrase.phrase_subject_id or
                        note.track_subject_id != phrase.track_subject_id):
                    raise ValueError("Phrase membership contradicts note observation")
        for section in self.sections:
            if section.track_subject_id not in observed_tracks:
                raise ValueError("Section track is missing from track observations")
            for bar_id, values in section.note_ids_by_bar.items():
                for note_id in values:
                    note = note_map.get(note_id)
                    if (note is None or note.track_subject_id != section.track_subject_id or
                            note.bar_subject_id != bar_id):
                        raise ValueError("Section bar/note membership contradicts note observation")
            expected_by_bar: dict[str, set[str]] = {}
            for note in self.notes:
                if note.track_subject_id == section.track_subject_id:
                    expected_by_bar.setdefault(note.bar_subject_id, set()).add(note.note_subject_id)
            if set(section.ordered_bar_ids) != set(expected_by_bar):
                raise ValueError("Section bars do not cover the complete track/bar universe")
            actual_by_bar = {bar_id: set(section.note_ids_by_bar.get(bar_id, ()))
                             for bar_id in section.ordered_bar_ids}
            if actual_by_bar != expected_by_bar:
                raise ValueError("Section notes do not cover the complete track membership universe")
        for pattern in self.bar_patterns:
            if pattern.track_subject_id not in observed_tracks:
                raise ValueError("Pattern track is missing from track observations")
            if subjects[pattern.bar_subject_id].natural_key.get("meter_segment_id") != pattern.meter_segment_id:
                raise ValueError("Bar pattern meter segment contradicts stable BAR subject")
            expected_members = {note.note_subject_id for note in self.notes
                                if note.track_subject_id == pattern.track_subject_id and
                                note.bar_subject_id == pattern.bar_subject_id}
            if set(pattern.member_subject_ids) != expected_members:
                raise ValueError("Bar pattern members do not match exact Track/Channel + BAR relation")
        for boundary in self.boundaries:
            stable_boundary = subjects[boundary.boundary_subject_id]
            if (stable_boundary.natural_key.get("tick") != boundary.tick or
                    stable_boundary.natural_key.get("boundary_kind") != boundary.boundary_kind):
                raise ValueError("Boundary observation contradicts stable BOUNDARY subject")
            for subject_id in boundary.affected_subject_ids:
                subject = subjects[subject_id]
                if subject.subject_type == "NOTE":
                    note = note_map.get(subject_id)
                    touches = note is not None and note.start_tick <= boundary.tick <= note.end_tick
                    edge = ("BOUNDARY_TOUCHES_NOTE", boundary.boundary_subject_id, subject_id)
                    if edge not in edge_keys:
                        raise ValueError("Boundary note membership requires stable boundary edge")
                elif subject.subject_type == "BAR":
                    start = subject.natural_key.get("start_tick")
                    end = subject.natural_key.get("end_tick")
                    touches = isinstance(start, int) and isinstance(end, int) and start <= boundary.tick <= end
                    edge = ("BOUNDARY_TOUCHES_BAR", boundary.boundary_subject_id, subject_id)
                    if edge not in edge_keys:
                        raise ValueError("Boundary bar membership requires stable boundary edge")
                elif subject.subject_type == "ONSET_CLUSTER":
                    touches = subject.natural_key.get("tick") == boundary.tick
                else:
                    phrase = phrase_map.get(subject_id)
                    phrase_notes = [] if phrase is None else [note_map[item] for item in phrase.ordered_note_ids]
                    touches = bool(phrase_notes) and min(item.start_tick for item in phrase_notes) <= boundary.tick <= max(
                        item.end_tick for item in phrase_notes)
                if not touches:
                    raise ValueError("Boundary member does not touch or cross the actual boundary tick")
        rx_map = {item.stable_subject_id: item for item in self.rx_subjects}
        for item in self.rx_subjects:
            segment = subjects[item.program_segment_id]
            if item.address is not None:
                expected = {"bank_msb": item.bank_msb, "bank_lsb": item.bank_lsb,
                            "program": item.program, "program_status": item.program_status}
                if any(segment.natural_key.get(key) != value for key, value in expected.items()):
                    raise ValueError("RX observation address contradicts stable Program segment")
            if subjects[item.stable_subject_id].subject_type == "NOTE" and (
                    "PROGRAM_SEGMENT_CONTAINS_NOTE", item.program_segment_id,
                    item.stable_subject_id) not in edge_keys:
                raise ValueError("RX note requires exact Program-segment membership edge")
        for component in self.human_components:
            stable_component = subjects[component.component_subject_id]
            natural_members = tuple(stable_component.natural_key.get("ordered_note_ids", ()))
            expected_kind = "GRACE" if component.evidence_kind == "GRACE" else None
            if expected_kind is not None and stable_component.natural_key.get("component_kind") != expected_kind:
                raise ValueError("Human grace evidence requires exact COMPONENT kind GRACE")
            if natural_members != component.member_subject_ids:
                raise ValueError("Human component evidence membership must exactly match stable natural key")
            member_notes = [note_map.get(item) for item in component.member_subject_ids]
            if any(item is None for item in member_notes):
                raise ValueError("Human component members must be exact NOTE observations")
            member_tracks = {item.track_subject_id for item in member_notes if item is not None}
            if len(member_tracks) != 1:
                raise ValueError("Human component members must belong to one exact track")
            track = next(item for item in self.tracks
                         if item.track_subject_id == next(iter(member_tracks)))
            if (stable_component.natural_key.get("track_index") != track.track_index or
                    stable_component.natural_key.get("channel") != track.channel or
                    len({item.meter_segment_id for item in member_notes if item is not None}) != 1 or
                    stable_component.natural_key.get("meter_segment_id") != member_notes[0].meter_segment_id):
                raise ValueError("Human component track coordinates contradict stable natural key")
        if self.rx_evidence is not None:
            for claim in self.rx_evidence.claims:
                for subject_id in claim.trigger_subject_ids:
                    observation = rx_map.get(subject_id)
                    if observation is None:
                        raise ValueError("RX claim trigger lacks exact Program observation")
                    if observation.address != claim.address:
                        raise ValueError("RX claim trigger address contradicts Program observation")

    @property
    def subject_ids(self) -> tuple[str, ...]:
        return tuple(item.subject_id for item in self._subjects)


@dataclass(frozen=True)
class AdapterEmission:
    run: AdapterRun
    partition: CoveragePartition | None
    groups: tuple[ProtectionGroup, ...]
    memberships: tuple[ProtectionGroupMembership, ...]
    subject_universe_ids: tuple[str, ...]
    applicable_subject_ids: tuple[str, ...]
    scanned_subject_ids: tuple[str, ...]
    resolved_subject_ids: tuple[str, ...]
    capability: str = field(default="ANALYZE_ONLY", init=False)
    mutation_capability: str = field(default="NONE", init=False)

    def install(self, registry: ProtectionEvidenceRegistry) -> None:
        if not isinstance(registry, ProtectionEvidenceRegistry):
            raise TypeError("registry must be ProtectionEvidenceRegistry")
        registry.add_run(self.run, subject_universe_ids=self.subject_universe_ids,
                         applicable_subject_ids=self.applicable_subject_ids,
                         scanned_subject_ids=self.scanned_subject_ids,
                         resolved_subject_ids=self.resolved_subject_ids)
        if self.partition is not None:
            registry.add_partition(self.partition,
                subject_universe_ids=self.subject_universe_ids,
                applicable_subject_ids=self.applicable_subject_ids,
                scanned_subject_ids=self.scanned_subject_ids,
                resolved_subject_ids=self.resolved_subject_ids)
        for group in self.groups:
            registry.add_group(group)
        for membership in self.memberships:
            registry.add_membership(membership)


def _contract(rule_key: str) -> AdapterContract:
    adapter_class = "EXTERNAL_OPTIONAL_FAIL_CLOSED" if rule_key == "RX_DNC" else (
        "POST_MODEL_REQUIRED" if rule_key == "FACTORY_REFERENCE_CONFLICT" else "CORE_REQUIRED")
    return AdapterContract(rule_key, ADAPTER_VERSION_BY_RULE[rule_key], adapter_class,
                           APPLICABILITY_PREDICATE_VERSION_BY_RULE[rule_key])


def _group_specs_digest(specs: Iterable[tuple[str, Any, tuple[str, ...], Any]]) -> str:
    return _digest([{"status": status, "key": key, "members": list(members), "evidence": evidence}
                    for status, key, members, evidence in specs])


def _emission(
    snapshot: StructuralSourceSnapshot,
    rule_key: str,
    applicable_ids: Iterable[str],
    group_specs: Iterable[tuple[str, Any, Iterable[str], Any]],
    *,
    run_status: str = "COMPLETE",
    scanned_ids: Iterable[str] | None = None,
    resolved_ids: Iterable[str] | None = None,
    dependency: Any = None,
) -> AdapterEmission:
    if snapshot.recompute_semantic_sha256() != snapshot.semantic_sha256:
        raise ValueError("Protection adapter snapshot semantic digest is stale")
    universe = tuple(sorted(snapshot.subject_ids))
    applicable = tuple(sorted(set(applicable_ids)))
    if not set(applicable).issubset(universe):
        raise ValueError("Adapter applicable population is outside stable subject registry")
    if scanned_ids is None:
        scanned = applicable if run_status == "COMPLETE" else ()
    else:
        scanned = tuple(sorted(set(scanned_ids)))
    if resolved_ids is None:
        resolved = scanned if run_status == "COMPLETE" else ()
    else:
        resolved = tuple(sorted(set(resolved_ids)))
    normalized_specs = []
    for status, key, members, evidence in group_specs:
        values = tuple(sorted(set(members)))
        if not values:
            raise ValueError("Sparse non-clear groups require stable members")
        if not set(values).issubset(applicable):
            raise ValueError("Sparse group member is outside adapter applicability")
        normalized_specs.append((status, key, values, evidence))
    normalized_specs.sort(key=lambda item: (item[0], canonical_json(item[1]), item[2]))
    detected_members = set().union(
        *(set(item[2]) for item in normalized_specs if item[0] == "DETECTED"), set())
    disjoint_specs = []
    for status, key, values, evidence in normalized_specs:
        if status in {"AMBIGUOUS", "EVIDENCE_UNJOINABLE"}:
            values = tuple(item for item in values if item not in detected_members)
            if not values:
                continue
        disjoint_specs.append((status, key, values, evidence))
    normalized_specs = disjoint_specs
    protected = set().union(*(set(item[2]) for item in normalized_specs if item[0] == "DETECTED"), set())
    ambiguous = set().union(*(set(item[2]) for item in normalized_specs
                              if item[0] in {"AMBIGUOUS", "EVIDENCE_UNJOINABLE"}), set())
    if run_status == "NOT_APPLICABLE":
        applicable = scanned = resolved = ()
    contract = _contract(rule_key)
    input_sha = _digest([snapshot.semantic_sha256, rule_key, universe, applicable])
    dependency_sha = _digest(dependency if dependency is not None else ["LOCAL_RAW", rule_key])
    population = dict(
        source_sha256=snapshot.source_sha256,
        contract=contract,
        scope_type="EXACT_CONTEXT",
        scope_subject_id=snapshot.scope_subject_id,
        subject_universe_query_version=SUBJECT_UNIVERSE_QUERY_VERSION_BY_RULE[rule_key],
        subject_universe_count=len(universe),
        subject_universe_sha256=_population_digest(universe),
        applicable_count=len(applicable),
        applicable_universe_sha256=_population_digest(applicable),
        scanned_count=len(scanned),
        scanned_universe_sha256=_population_digest(scanned),
        resolved_count=len(resolved),
        resolved_universe_sha256=_population_digest(resolved),
        protected_count=len(protected),
        ambiguous_count=len(ambiguous),
        input_sha256=input_sha,
        dependency_sha256=dependency_sha,
        run_status=run_status,
    )
    partition = None
    if run_status in {"COMPLETE", "PARTIAL"}:
        partition_evidence = _group_specs_digest(normalized_specs)
        provisional = AdapterRun(result_sha256="0" * 64, **population)
        provisional_partition = CoveragePartition(
            provisional.run_id, "SOURCE_COMPLETE" if run_status == "COMPLETE" else "SOURCE_PARTIAL",
            snapshot.scope_subject_id, len(universe), len(applicable), len(scanned), len(resolved),
            _population_digest(universe), _population_digest(applicable),
            _population_digest(scanned), _population_digest(resolved), partition_evidence,
            "COMPLETE" if run_status == "COMPLETE" else "PARTIAL")
        result_sha = canonical_partition_result_sha256(provisional, (provisional_partition,))
        run = AdapterRun(result_sha256=result_sha, **population)
        partition = CoveragePartition(
            run.run_id, provisional_partition.partition_key, snapshot.scope_subject_id,
            len(universe), len(applicable), len(scanned), len(resolved),
            _population_digest(universe), _population_digest(applicable),
            _population_digest(scanned), _population_digest(resolved), partition_evidence,
            provisional_partition.status)
        if canonical_partition_result_sha256(run, (partition,)) != result_sha:
            raise ValueError("Adapter partition commitment is not deterministic")
    else:
        run = AdapterRun(result_sha256=_group_specs_digest(normalized_specs), **population)
    groups = []
    memberships = []
    for status, key, members, evidence in normalized_specs:
        group = ProtectionGroup(run.run_id, snapshot.source_sha256, rule_key,
                                contract.adapter_version, key, status, _digest(evidence))
        groups.append(group)
        memberships.extend(ProtectionGroupMembership(group.group_id, subject_id)
                           for subject_id in members)
    return AdapterEmission(run, partition, tuple(groups), tuple(memberships), universe,
                           applicable, tuple(scanned), tuple(resolved))


def guitar_mode_adapter(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    snapshot.require_domains("TRACKS")
    applicable: set[str] = set()
    specs = []
    for track in sorted(snapshot.tracks, key=lambda item: item.track_subject_id):
        exact_guitar = (track.track_type_status == EXACT_TRACK_TYPE_STATUS and
                        track.track_type.upper() in {"GTR", "GUITAR_MODE"})
        if exact_guitar:
            members = (track.track_subject_id, *track.command_subject_ids)
            applicable.update(members)
            specs.append(("DETECTED", ["EXACT_GUITAR_TRACK", track.track_subject_id], members,
                          [track.track_type, track.track_type_status, track.command_subject_ids]))
        elif track.command_subject_ids:
            members = (track.track_subject_id, *track.command_subject_ids)
            applicable.update(members)
            specs.append(("AMBIGUOUS", ["COMMAND_WITHOUT_EXACT_GUITAR_TYPE", track.track_subject_id],
                          members, [track.track_type, track.track_type_status,
                                    track.command_subject_ids]))
        elif track.role_status == EXACT_ROLE_STATUS and track.role.upper() == "GUITAR":
            applicable.add(track.track_subject_id)
            specs.append(("AMBIGUOUS", ["EXACT_GUITAR_ROLE_TRACK_TYPE_UNPROVEN",
                                         track.track_subject_id],
                          (track.track_subject_id,), [track.role, track.role_status,
                                                       track.track_type,
                                                       track.track_type_status]))
    return _emission(snapshot, "GUITAR_MODE", applicable, specs,
                     run_status="COMPLETE" if applicable else "NOT_APPLICABLE")


def rx_dnc_adapter(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    snapshot.require_domains("RX_SUBJECTS")
    applicable = {item.stable_subject_id for item in snapshot.rx_subjects}
    if not applicable:
        return _emission(snapshot, "RX_DNC", (), (), run_status="NOT_APPLICABLE")
    if snapshot.rx_evidence is None:
        return _emission(snapshot, "RX_DNC", applicable, (),
                         run_status="DEPENDENCY_UNAVAILABLE",
                         dependency=["RX_DNC_EVIDENCE", "UNAVAILABLE"])
    claims = snapshot.rx_evidence.by_address
    specs = []
    for item in sorted(snapshot.rx_subjects, key=lambda value: value.stable_subject_id):
        if item.address is None:
            specs.append(("AMBIGUOUS", ["PROGRAM_CONTEXT_UNPROVEN", item.stable_subject_id],
                          (item.stable_subject_id,), item.__dict__))
            continue
        claim = claims.get(item.address)
        if claim is None:
            specs.append(("EVIDENCE_UNJOINABLE", ["RX_CLAIM_MISSING", list(item.address)],
                          (item.stable_subject_id,), [item.address, snapshot.rx_evidence.registry_sha256]))
        elif claim.status == "CONFIRMED_RX_COMPLETE" and item.stable_subject_id in claim.trigger_subject_ids:
            specs.append(("DETECTED", ["CONFIRMED_RX_TRIGGER", list(item.address),
                                       item.stable_subject_id], (item.stable_subject_id,), claim.__dict__))
        elif claim.status in {"CONFIRMED_RX_INCOMPLETE", "UNKNOWN", "CONFLICT", "CATALOG_ONLY"}:
            specs.append(("AMBIGUOUS", [claim.status, list(item.address)],
                          (item.stable_subject_id,), claim.__dict__))
        elif claim.status == "CONFIRMED_UNJOINABLE":
            specs.append(("EVIDENCE_UNJOINABLE", [claim.status, list(item.address)],
                          (item.stable_subject_id,), claim.__dict__))
        # CONFIRMED_NON_RX and non-trigger members of complete coverage are proven clear.
    dependency = [snapshot.rx_evidence.version, snapshot.rx_evidence.registry_sha256,
                  [claim.__dict__ for claim in snapshot.rx_evidence.claims]]
    return _emission(snapshot, "RX_DNC", applicable, specs, dependency=dependency)


def _strict_trill_runs(notes: list[NoteObservation]) -> list[tuple[str, ...]]:
    runs: list[tuple[str, ...]] = []
    index = 0
    while index + 3 < len(notes):
        first, second = notes[index], notes[index + 1]
        if first.pitch == second.pitch or first.onset_cluster_id == second.onset_cluster_id:
            index += 1
            continue
        end = index + 2
        seen_clusters = {first.onset_cluster_id, second.onset_cluster_id}
        while end < len(notes):
            expected = first.pitch if (end - index) % 2 == 0 else second.pitch
            if (notes[end].pitch != expected or
                    notes[end].onset_cluster_id in seen_clusters):
                break
            seen_clusters.add(notes[end].onset_cluster_id)
            end += 1
        if end - index >= 4:
            runs.append(tuple(item.note_subject_id for item in notes[index:end]))
            index = end
        else:
            index += 1
    return runs


def ornament_trill_grace_adapter(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    snapshot.require_domains("TRACKS", "NOTES", "PHRASES", "HUMAN_COMPONENTS")
    tracks = {item.track_subject_id: item for item in snapshot.tracks}
    notes = {item.note_subject_id: item for item in snapshot.notes}
    applicable_tracks = {track_id for track_id, item in tracks.items()
                         if item.role_status == EXACT_ROLE_STATUS and
                         item.role.upper() in {"MELODY", "GUITAR", "SOLO", "RIFF"}}
    applicable_notes = {note_id for note_id, item in notes.items()
                        if item.track_subject_id in applicable_tracks}
    applicable = set(applicable_tracks) | applicable_notes
    specs = []
    phrase_members: set[str] = set()
    for phrase in sorted(snapshot.phrases, key=lambda item: item.phrase_subject_id):
        if phrase.track_subject_id not in applicable_tracks:
            continue
        ordered = [notes[note_id] for note_id in phrase.ordered_note_ids]
        phrase_members.update(phrase.ordered_note_ids)
        for run_members in _strict_trill_runs(ordered):
            specs.append(("DETECTED", ["STRICT_ALTERNATING_TWO_PITCH", list(run_members)],
                          run_members, [(notes[item].pitch, notes[item].onset_cluster_id)
                                        for item in run_members]))
    missing = applicable_notes - phrase_members
    if missing:
        raise ValueError("Ornament core scan requires exact phrase membership for every applicable note")
    for component in snapshot.human_components:
        if component.evidence_kind != "GRACE":
            continue
        member_tracks = {notes[item].track_subject_id for item in component.member_subject_ids
                         if item in notes}
        if len(member_tracks) != 1 or not member_tracks.issubset(applicable_tracks):
            raise ValueError("Human grace component must join one applicable exact track")
        applicable.update((component.component_subject_id, *component.member_subject_ids))
        specs.append(("DETECTED", ["HUMAN_VALIDATED_GRACE", component.component_subject_id],
                      (component.component_subject_id, *component.member_subject_ids),
                      component.__dict__))
    # Exact Human evidence validates only the named component.  It does not
    # magically make the unavailable general grace classifier complete.
    for track_id in sorted(applicable_tracks):
        specs.append(("AMBIGUOUS", ["GRACE_CLASSIFIER_UNAVAILABLE", track_id],
                      (track_id,), ["NO_EXACT_HUMAN_GRACE_EVIDENCE", track_id]))
    return _emission(snapshot, "ORNAMENT_TRILL_GRACE", applicable, specs,
                     run_status="COMPLETE" if applicable else "NOT_APPLICABLE")


def drum_flam_roll_ghost_adapter(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    snapshot.require_domains("TRACKS", "NOTES", "PHRASES", "HUMAN_COMPONENTS")
    tracks = {item.track_subject_id: item for item in snapshot.tracks}
    notes = {item.note_subject_id: item for item in snapshot.notes}
    exact_drum_tracks = {track_id for track_id, item in tracks.items()
                         if ((item.instrument_class_status == EXACT_ROLE_STATUS and
                              item.instrument_class == "DRUM_KIT") or
                             (item.role_status == EXACT_ROLE_STATUS and
                              item.role.upper() in {"DRUM", "KICK", "SNARE", "HIHAT",
                                                    "PERCUSSION", "FILL"}))}
    hinted_tracks = {track_id for track_id, item in tracks.items()
                     if track_id not in exact_drum_tracks and
                     (item.instrument_class == "DRUM_KIT" or item.role.upper() in {
                         "DRUM", "KICK", "SNARE", "HIHAT", "PERCUSSION", "FILL"})}
    applicable_notes = {note_id for note_id, item in notes.items()
                        if item.track_subject_id in exact_drum_tracks | hinted_tracks}
    applicable = set(applicable_notes)
    specs = []
    phrase_members: set[str] = set()
    detected: set[str] = set()
    for phrase in sorted(snapshot.phrases, key=lambda item: item.phrase_subject_id):
        if phrase.track_subject_id not in exact_drum_tracks:
            continue
        ordered = [notes[note_id] for note_id in phrase.ordered_note_ids]
        phrase_members.update(phrase.ordered_note_ids)
        by_lane: dict[int, list[NoteObservation]] = {}
        for note in ordered:
            by_lane.setdefault(note.pitch, []).append(note)
        for pitch, lane in sorted(by_lane.items()):
            cluster_ids = {item.onset_cluster_id for item in lane}
            if len(lane) >= 2 and len(cluster_ids) >= 2:
                members = tuple(item.note_subject_id for item in lane)
                detected.update(members)
                specs.append(("DETECTED", ["REPEATED_SAME_LANE", phrase.phrase_subject_id, pitch],
                              members, [(item.note_subject_id, item.onset_cluster_id) for item in lane]))
    exact_note_ids = {note_id for note_id, item in notes.items()
                      if item.track_subject_id in exact_drum_tracks}
    if exact_note_ids - phrase_members:
        raise ValueError("Drum core scan requires exact phrase membership for every applicable note")
    for component in snapshot.human_components:
        if component.evidence_kind != "DRUM_ARTICULATION":
            continue
        if not set(component.member_subject_ids).issubset(exact_note_ids):
            raise ValueError("Human drum component must join exact drum note subjects")
        applicable.update((component.component_subject_id, *component.member_subject_ids))
        detected.update(component.member_subject_ids)
        specs.append(("DETECTED", ["HUMAN_VALIDATED_DRUM_COMPONENT",
                                   component.component_subject_id],
                      (component.component_subject_id, *component.member_subject_ids),
                      component.__dict__))
    unresolved = exact_note_ids - detected
    if unresolved:
        specs.append(("AMBIGUOUS", ["DRUM_ARTICULATION_CLASSIFIER_UNAVAILABLE"],
                      tuple(sorted(unresolved)), ["NO_VELOCITY_OR_IOI_HEURISTIC", sorted(unresolved)]))
    hinted_notes = {note_id for note_id, item in notes.items()
                    if item.track_subject_id in hinted_tracks}
    if hinted_notes:
        specs.append(("AMBIGUOUS", ["DRUM_SCOPE_UNPROVEN"], tuple(sorted(hinted_notes)),
                      ["ROLE_OR_KIT_STATUS_NOT_EXACT", sorted(hinted_tracks)]))
    return _emission(snapshot, "DRUM_FLAM_ROLL_GHOST", applicable, specs,
                     run_status="COMPLETE" if applicable else "NOT_APPLICABLE")


def cross_bar_adapter(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    snapshot.require_domains("NOTES", "PHRASES")
    applicable: set[str] = set()
    specs = []
    for note in sorted(snapshot.notes, key=lambda item: item.note_subject_id):
        applicable.add(note.note_subject_id)
        if note.meter_status != "METER_EXACT":
            specs.append(("AMBIGUOUS", ["METER_CONTEXT_UNPROVEN", note.note_subject_id],
                          (note.note_subject_id,), note.__dict__))
        elif note.start_tick < note.bar_end_tick < note.end_tick:
            specs.append(("DETECTED", ["NOTE_CROSSES_BAR", note.note_subject_id],
                          (note.note_subject_id,), [note.start_tick, note.end_tick,
                                                   note.bar_start_tick, note.bar_end_tick]))
    note_map = {item.note_subject_id: item for item in snapshot.notes}
    for phrase in sorted(snapshot.phrases, key=lambda item: item.phrase_subject_id):
        phrase_notes = [note_map[item] for item in phrase.ordered_note_ids]
        applicable.add(phrase.phrase_subject_id)
        if any(item.meter_status != "METER_EXACT" for item in phrase_notes):
            specs.append(("AMBIGUOUS", ["PHRASE_METER_CONTEXT_UNPROVEN", phrase.phrase_subject_id],
                          (phrase.phrase_subject_id,), phrase.__dict__))
        elif len({item.bar_subject_id for item in phrase_notes}) > 1:
            members = (phrase.phrase_subject_id, *phrase.ordered_note_ids)
            applicable.update(phrase.ordered_note_ids)
            specs.append(("DETECTED", ["PHRASE_CROSSES_BAR", phrase.phrase_subject_id],
                          members, [item.bar_subject_id for item in phrase_notes]))
    return _emission(snapshot, "CROSS_BAR", applicable, specs,
                     run_status="COMPLETE" if applicable else "NOT_APPLICABLE")


def section_transition_adapter(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    snapshot.require_domains("SECTIONS")
    applicable: set[str] = set()
    specs = []
    full_sections = {"INTRO", "FILL", "BREAK", "ENDING"}
    exact_methods = {"RAW_TRACK", "RAW_MIDI", "EXPLICIT_METADATA"}
    for item in sorted(snapshot.sections, key=lambda value: value.track_subject_id):
        all_members = set(item.ordered_bar_ids)
        for values in item.note_ids_by_bar.values():
            all_members.update(values)
        applicable.update(all_members)
        exact = item.section_status == "EXACT" and item.provenance_method in exact_methods
        if not exact:
            all_members.add(item.track_subject_id)
            applicable.add(item.track_subject_id)
            specs.append(("AMBIGUOUS", ["SECTION_PROVENANCE_UNPROVEN", item.track_subject_id],
                          tuple(sorted(all_members)), item.__dict__))
            continue
        if item.section.upper() in full_sections:
            selected_bars = item.ordered_bar_ids
        else:
            selected_bars = (item.ordered_bar_ids[0],) if len(item.ordered_bar_ids) == 1 else (
                item.ordered_bar_ids[0], item.ordered_bar_ids[-1])
        members: set[str] = set(selected_bars)
        for bar_id in selected_bars:
            members.update(item.note_ids_by_bar.get(bar_id, ()))
        specs.append(("DETECTED", ["EXACT_SECTION_TRANSITION", item.track_subject_id,
                                   item.section.upper(), list(selected_bars)],
                      tuple(sorted(members)), [item.section_status, item.provenance_method,
                                                list(item.ordered_bar_ids)]))
    return _emission(snapshot, "SECTION_TRANSITION", applicable, specs,
                     run_status="COMPLETE" if applicable else "NOT_APPLICABLE")


def tempo_meter_boundary_adapter(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    snapshot.require_domains("BOUNDARIES")
    applicable: set[str] = set()
    specs = []
    for item in sorted(snapshot.boundaries, key=lambda value: value.boundary_subject_id):
        members = (item.boundary_subject_id, *item.affected_subject_ids)
        applicable.update(members)
        status = "DETECTED" if item.boundary_status in {"CHANGE_EXACT", "UNSPECIFIED_TO_EXACT"} else "AMBIGUOUS"
        specs.append((status, [item.boundary_kind, item.boundary_status,
                              item.boundary_subject_id], members, item.__dict__))
    return _emission(snapshot, "TEMPO_METER_BOUNDARY", applicable, specs,
                     run_status="COMPLETE" if applicable else "NOT_APPLICABLE")


def local_repeated_pattern_adapter(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    snapshot.require_domains("BAR_PATTERNS")
    applicable = {member_id for item in snapshot.bar_patterns
                  for member_id in item.member_subject_ids}
    grouped: dict[tuple[str, str, str, str], list[BarPatternObservation]] = {}
    for item in snapshot.bar_patterns:
        key = (item.track_subject_id, item.meter_segment_id,
               item.rhythm_sha256, item.topology_sha256)
        grouped.setdefault(key, []).append(item)
    specs = []
    for key, observations in sorted(grouped.items()):
        if len(observations) >= 2:
            bar_pairs = sorted((item.track_subject_id, item.bar_subject_id)
                               for item in observations)
            members = tuple(sorted({member_id for item in observations
                                    for member_id in item.member_subject_ids}))
            specs.append(("DETECTED", ["EXACT_LOCAL_REPEAT", *key, bar_pairs], members,
                          ["EXACT_TRACK_BAR_HASH_EQUALITY", bar_pairs, list(members)]))
    return _emission(snapshot, "LOCAL_REPEATED_PATTERN", applicable, specs,
                     run_status="COMPLETE" if applicable else "NOT_APPLICABLE")


def factory_reference_conflict_deferred(snapshot: StructuralSourceSnapshot) -> AdapterEmission:
    """Emit the S4 interface marker; comparison belongs exclusively to WP-012C."""
    applicable = tuple(item.subject_id for item in snapshot._subjects
                       if item.subject_type == "EXACT_CONTEXT")
    if not applicable:
        applicable = (snapshot.scope_subject_id,)
    return _emission(snapshot, "FACTORY_REFERENCE_CONFLICT", applicable, (),
                     run_status="DEFERRED_POST_MODEL",
                     dependency=["POST_MODEL_REQUIRED", "WP-X10-012C"])


def build_pre_model_adapter_emissions(snapshot: StructuralSourceSnapshot) -> tuple[AdapterEmission, ...]:
    """Run all eight S1 adapters and emit the S4 deferred interface marker."""
    before = snapshot.recompute_semantic_sha256()
    if before != snapshot.semantic_sha256:
        raise ValueError("Protection adapter snapshot semantic digest is stale")
    emissions = (
        guitar_mode_adapter(snapshot),
        rx_dnc_adapter(snapshot),
        ornament_trill_grace_adapter(snapshot),
        drum_flam_roll_ghost_adapter(snapshot),
        cross_bar_adapter(snapshot),
        section_transition_adapter(snapshot),
        tempo_meter_boundary_adapter(snapshot),
        local_repeated_pattern_adapter(snapshot),
        factory_reference_conflict_deferred(snapshot),
    )
    if snapshot.recompute_semantic_sha256() != before:
        raise ValueError("Protection adapter input changed during ANALYZE_ONLY execution")
    if any(item.capability != "ANALYZE_ONLY" or item.mutation_capability != "NONE"
           for item in emissions):
        raise ValueError("Protection adapters must remain ANALYZE_ONLY")
    return emissions


def install_pre_model_adapter_emissions(
    snapshot: StructuralSourceSnapshot,
    evidence_registry: ProtectionEvidenceRegistry,
) -> tuple[AdapterEmission, ...]:
    emissions = build_pre_model_adapter_emissions(snapshot)
    for emission in emissions:
        emission.install(evidence_registry)
    return emissions


__all__ = (
    "ALLOWED_LINEAGE_PARENT_CLASSES",
    "AdapterEmission",
    "BarPatternObservation",
    "BoundaryObservation",
    "EXTRACTION_DOMAINS",
    "EXTRACTOR_VERSION_BY_DOMAIN",
    "ExtractionAttestation",
    "FORBIDDEN_SOURCE_KINDS",
    "HumanValidatedComponent",
    "LINEAGE_CLASS_MATRIX_VERSION",
    "NoteObservation",
    "PhraseObservation",
    "RX_DNC_EVIDENCE_VERSION",
    "RxDncClaim",
    "RxDncEvidenceSnapshot",
    "RxSubjectObservation",
    "SOURCE_KINDS",
    "SIX_SONG_FORBIDDEN_SHA256S",
    "SOURCE_GUARD_POLICY_VERSION",
    "SOURCE_LINEAGE_VERIFIER_VERSION",
    "SectionObservation",
    "SourceGuardPolicy",
    "SourceLineageRecord",
    "TrustedSourceLineageSnapshot",
    "StructuralSourceSnapshot",
    "TrackObservation",
    "build_pre_model_adapter_emissions",
    "complete_extraction_attestation",
    "cross_bar_adapter",
    "drum_flam_roll_ghost_adapter",
    "factory_reference_conflict_deferred",
    "guitar_mode_adapter",
    "install_pre_model_adapter_emissions",
    "local_repeated_pattern_adapter",
    "ornament_trill_grace_adapter",
    "rx_dnc_adapter",
    "rx_dnc_claims_sha256",
    "section_transition_adapter",
    "lineage_inventory_sha256",
    "lineage_class_matrix_sha256",
    "tempo_meter_boundary_adapter",
    "trusted_source_guard_policy",
    "trusted_source_lineage_snapshot",
)