"""Canonical stable subjects for the X10 ANALYZE_ONLY pipeline.

This module deliberately has no SQLite or MIDI mutation responsibility.  It
defines the portable identity contract used by protection adapters and later
schema-v2 materialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping


SUBJECT_CONTRACT_VERSION = "X10_STABLE_SUBJECT_V1"
SUBJECT_TYPES = (
    "EVENT",
    "NOTE",
    "ONSET_CLUSTER",
    "BAR",
    "PHRASE",
    "COMPONENT",
    "BOUNDARY",
    "TRACK_CHANNEL",
    "PROGRAM_SEGMENT",
    "EXACT_CONTEXT",
)

# Direction is containment/evidence-owner -> contained/evidence-member.
EDGE_TYPE_DOMAINS: Mapping[str, tuple[str, str]] = {
    "TRACK_CHANNEL_CONTAINS_EVENT": ("TRACK_CHANNEL", "EVENT"),
    "TRACK_CHANNEL_CONTAINS_NOTE": ("TRACK_CHANNEL", "NOTE"),
    "NOTE_HAS_ON_EVENT": ("NOTE", "EVENT"),
    "NOTE_HAS_OFF_EVENT": ("NOTE", "EVENT"),
    "BAR_CONTAINS_ONSET_CLUSTER": ("BAR", "ONSET_CLUSTER"),
    "ONSET_CLUSTER_CONTAINS_NOTE": ("ONSET_CLUSTER", "NOTE"),
    "PHRASE_CONTAINS_NOTE": ("PHRASE", "NOTE"),
    "COMPONENT_CONTAINS_NOTE": ("COMPONENT", "NOTE"),
    "BOUNDARY_TOUCHES_BAR": ("BOUNDARY", "BAR"),
    "BOUNDARY_TOUCHES_NOTE": ("BOUNDARY", "NOTE"),
    "PROGRAM_SEGMENT_CONTAINS_NOTE": ("PROGRAM_SEGMENT", "NOTE"),
    "EXACT_CONTEXT_CONTAINS_NOTE": ("EXACT_CONTEXT", "NOTE"),
}
EDGE_TYPES = tuple(EDGE_TYPE_DOMAINS)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _validate_sha256(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _canonicalize(value: Any) -> Any:
    """Return a JSON-safe deterministic value and reject ambiguous keys."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        raise ValueError("Stable natural keys cannot contain floats")
    if isinstance(value, Mapping):
        result = {}
        if any(not isinstance(key, str) or not key for key in value):
            raise ValueError("Stable natural-key mapping keys must be non-empty strings")
        for key in sorted(value):
            result[key] = _canonicalize(value[key])
        return result
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    raise ValueError(f"Unsupported stable natural-key value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(_canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _normalize_subject_natural_key(subject_type: str, natural_key: Any) -> Any:
    normalized = _canonicalize(natural_key)
    strict_schemas = {
        "ONSET_CLUSTER": {
            "track_index", "channel", "meter_segment_id", "tick", "on_event_ids",
        },
        "PHRASE": {
            "track_index", "channel", "meter_segment_id", "ordered_note_ids",
        },
        "COMPONENT": {
            "track_index", "channel", "meter_segment_id", "component_kind",
            "ordered_note_ids",
        },
    }
    if subject_type in strict_schemas:
        if not isinstance(normalized, dict):
            raise ValueError(f"{subject_type} natural key must be a mapping")
        required = strict_schemas[subject_type]
        if set(normalized) != required:
            raise ValueError(
                f"{subject_type} natural key must use exactly canonical fields {sorted(required)}")
        for key in ("track_index", "tick"):
            if key in normalized and (
                    not isinstance(normalized[key], int) or isinstance(normalized[key], bool) or
                    normalized[key] < 0):
                raise ValueError(f"{subject_type} {key} must be a nonnegative integer")
        channel = normalized["channel"]
        if not isinstance(channel, int) or isinstance(channel, bool) or not 0 <= channel <= 15:
            raise ValueError(f"{subject_type} channel must be an integer from 0 to 15")
        _validate_sha256(normalized["meter_segment_id"], "meter_segment_id")
        if subject_type == "COMPONENT" and (
                not isinstance(normalized["component_kind"], str) or
                not normalized["component_kind"]):
            raise ValueError("COMPONENT component_kind must be a non-empty string")
        membership_key = "on_event_ids" if subject_type == "ONSET_CLUSTER" else "ordered_note_ids"
        members = normalized[membership_key]
        if not isinstance(members, list) or not members:
            qualifier = "ordered " if subject_type != "ONSET_CLUSTER" else ""
            raise ValueError(f"{subject_type} membership must be a non-empty {qualifier}list")
        for member in members:
            _validate_sha256(member, f"{subject_type} stable membership ID")
        if len(members) != len(set(members)):
            raise ValueError(f"{subject_type} membership cannot contain duplicates")
        if subject_type == "ONSET_CLUSTER":
            normalized[membership_key] = sorted(members)
    return normalized


def stable_subject_id(
    subject_type: str,
    source_sha256: str,
    natural_key: Any,
    contract_version: str = SUBJECT_CONTRACT_VERSION,
) -> str:
    if subject_type not in SUBJECT_TYPES:
        raise ValueError(f"Unknown stable subject type: {subject_type}")
    _validate_sha256(source_sha256, "source_sha256")
    if not isinstance(contract_version, str) or not contract_version:
        raise ValueError("contract_version is required")
    normalized = _normalize_subject_natural_key(subject_type, natural_key)
    if normalized in ({}, []):
        raise ValueError("Stable subject natural_key cannot be empty")
    payload = [contract_version, subject_type, source_sha256, normalized]
    return sha256(canonical_json(payload).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class StableSubject:
    subject_type: str
    source_sha256: str
    natural_key: Any
    contract_version: str = SUBJECT_CONTRACT_VERSION
    subject_id: str = field(init=False)

    def __post_init__(self) -> None:
        normalized = _normalize_subject_natural_key(self.subject_type, self.natural_key)
        object.__setattr__(self, "natural_key", normalized)
        object.__setattr__(self, "subject_id", stable_subject_id(
            self.subject_type, self.source_sha256, normalized, self.contract_version))

    @property
    def semantic_record(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "subject_type": self.subject_type,
            "source_sha256": self.source_sha256,
            "natural_key": self.natural_key,
            "subject_id": self.subject_id,
        }


@dataclass(frozen=True)
class StableSubjectEdge:
    edge_type: str
    parent_subject_id: str
    child_subject_id: str
    source_sha256: str
    contract_version: str = SUBJECT_CONTRACT_VERSION
    edge_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.edge_type not in EDGE_TYPE_DOMAINS:
            raise ValueError(f"Unknown stable edge type: {self.edge_type}")
        _validate_sha256(self.parent_subject_id, "parent_subject_id")
        _validate_sha256(self.child_subject_id, "child_subject_id")
        _validate_sha256(self.source_sha256, "source_sha256")
        if self.parent_subject_id == self.child_subject_id:
            raise ValueError("Stable subject self-cycle is forbidden")
        payload = [self.contract_version, self.edge_type, self.source_sha256,
                   self.parent_subject_id, self.child_subject_id]
        object.__setattr__(self, "edge_id", sha256(canonical_json(payload).encode("ascii")).hexdigest())


class StableSubjectRegistry:
    """In-memory validator used before a disk-backed schema-v2 merge."""

    def __init__(self) -> None:
        self._subjects: dict[str, StableSubject] = {}
        self._natural_keys: dict[tuple[str, str, str, str], str] = {}
        self._edges: dict[str, StableSubjectEdge] = {}

    @property
    def subjects(self) -> tuple[StableSubject, ...]:
        return tuple(self._subjects[key] for key in sorted(self._subjects))

    @property
    def edges(self) -> tuple[StableSubjectEdge, ...]:
        return tuple(self._edges[key] for key in sorted(self._edges))

    def add_subject(self, subject: StableSubject) -> StableSubject:
        if not isinstance(subject, StableSubject):
            raise TypeError("subject must be StableSubject")
        membership_contract = {
            "ONSET_CLUSTER": ("on_event_ids", {"EVENT"}),
            "PHRASE": ("ordered_note_ids", {"NOTE"}),
            "COMPONENT": ("ordered_note_ids", {"NOTE"}),
        }.get(subject.subject_type)
        if membership_contract is not None:
            membership_key, allowed_types = membership_contract
            for member_id in subject.natural_key[membership_key]:
                member = self._subjects.get(member_id)
                if member is None:
                    raise ValueError(
                        f"{subject.subject_type} member stable subject must already be registered")
                if member.source_sha256 != subject.source_sha256:
                    raise ValueError(f"{subject.subject_type} member belongs to another source")
                if member.contract_version != subject.contract_version:
                    raise ValueError(f"{subject.subject_type} member contract version mismatch")
                if member.subject_type not in allowed_types:
                    raise ValueError(
                        f"{subject.subject_type} member must have stable type {sorted(allowed_types)}")
                if (subject.subject_type == "ONSET_CLUSTER" and
                        member.natural_key.get("event_kind") != "NOTE_ON"):
                    raise ValueError("ONSET_CLUSTER EVENT member must be a canonical NOTE_ON event")
        natural = (subject.contract_version, subject.subject_type, subject.source_sha256,
                   canonical_json(subject.natural_key))
        previous_id = self._natural_keys.get(natural)
        if previous_id is not None and previous_id != subject.subject_id:
            raise ValueError("Contradictory stable subject natural key")
        previous = self._subjects.get(subject.subject_id)
        if previous is not None and previous.semantic_record != subject.semantic_record:
            raise ValueError("Contradictory stable subject ID")
        self._subjects[subject.subject_id] = subject
        self._natural_keys[natural] = subject.subject_id
        return subject

    def add_edge(self, edge: StableSubjectEdge) -> StableSubjectEdge:
        if not isinstance(edge, StableSubjectEdge):
            raise TypeError("edge must be StableSubjectEdge")
        parent = self._subjects.get(edge.parent_subject_id)
        child = self._subjects.get(edge.child_subject_id)
        if parent is None or child is None:
            raise ValueError("Stable edge endpoints must already be registered")
        if parent.source_sha256 != child.source_sha256 or parent.source_sha256 != edge.source_sha256:
            raise ValueError("Cross-source stable subject edges are forbidden")
        if not (parent.contract_version == child.contract_version == edge.contract_version):
            raise ValueError("Stable edge and endpoint contract versions must match")
        expected = EDGE_TYPE_DOMAINS[edge.edge_type]
        if (parent.subject_type, child.subject_type) != expected:
            raise ValueError(f"Edge {edge.edge_type} requires {expected[0]} -> {expected[1]}")
        previous = self._edges.get(edge.edge_id)
        if previous is not None and previous != edge:
            raise ValueError("Contradictory stable edge ID")
        self._edges[edge.edge_id] = edge
        try:
            self._assert_acyclic()
        except Exception:
            if previous is None:
                self._edges.pop(edge.edge_id, None)
            raise
        return edge

    def extend_subjects(self, subjects: Iterable[StableSubject]) -> None:
        for subject in subjects:
            self.add_subject(subject)

    def _assert_acyclic(self) -> None:
        adjacency: dict[str, list[str]] = {}
        for edge in self._edges.values():
            adjacency.setdefault(edge.parent_subject_id, []).append(edge.child_subject_id)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("Forbidden stable subject edge cycle")
            if node in visited:
                return
            visiting.add(node)
            for child in sorted(adjacency.get(node, ())):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(self._subjects):
            visit(node)

    def semantic_digest(self) -> str:
        payload = {
            "contract_version": SUBJECT_CONTRACT_VERSION,
            "subjects": [subject.semantic_record for subject in self.subjects],
            "edges": [{
                "contract_version": edge.contract_version,
                "edge_type": edge.edge_type,
                "source_sha256": edge.source_sha256,
                "parent_subject_id": edge.parent_subject_id,
                "child_subject_id": edge.child_subject_id,
                "edge_id": edge.edge_id,
            } for edge in self.edges],
        }
        return sha256(canonical_json(payload).encode("ascii")).hexdigest()