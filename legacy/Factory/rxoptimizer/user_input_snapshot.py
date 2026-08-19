"""Immutable, authority-isolated USER_INPUT MIDI snapshot orchestration.

This module deliberately has no application upload, MIDI writer, corpus,
evidence, calibration, anomaly, candidate, or repair integration.  Every trust
primitive is supplied as an injected port by :mod:`user_input_store`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import base64
import hmac
import io
import json
import sqlite3
import struct
import tempfile
import os
import time
from typing import Any, Callable, Iterable, Mapping

from .midi import MidiError, MidiFile, parse_midi
from .user_input_store import (
    CompositeSnapshotKey, LifecycleState, Operation, PublicErrorCode,
    ReservationIdentity, ReservationKind, StoreContractError,
)


AUTHORITY_DOMAIN = "USER_INPUT"
SOURCE_CLASS = "USER_INPUT_RAW"
ORIGIN_TRUST = "UNVERIFIED_USER_ORIGIN"
CAPABILITY = "ANALYZE_ONLY"
MUTATION_CAPABILITY = "NONE"
TRAINING_ELIGIBILITY = "NEVER"
CONTRACT_VERSION = "X10_USER_INPUT_SNAPSHOT_V1"
SUBJECT_VERSION = "X10_USER_INPUT_SUBJECT_V1"
LIMITS_VERSION = "X10_USER_INPUT_LIMITS_V1"
RETENTION_POLICY = "UNTIL_EXPLICIT_MANUAL_PURGE"


@dataclass(frozen=True)
class UserInputLimits:
    max_raw_bytes: int = 33_554_432
    max_session_retained_bytes: int = 536_870_912
    max_tracks: int = 256
    max_events_total: int = 2_000_000
    max_notes_total: int = 1_000_000
    max_events_per_track: int = 1_000_000
    max_declared_track_bytes: int = 33_554_432
    max_text_payload_bytes_event: int = 1_048_576
    max_sysex_payload_bytes_event: int = 4_194_304
    max_cumulative_private_payload: int = 16_777_216
    max_vlq_bytes: int = 4
    max_absolute_tick: int = 9_007_199_254_740_991
    max_graph_subjects: int = 4_000_000
    max_graph_edges: int = 8_000_000
    max_staged_package_bytes: int = 1_073_741_824
    max_parser_wall_seconds: int = 60
    max_builder_wall_seconds: int = 180
    max_peak_event_batch: int = 65_536


DEFAULT_LIMITS = UserInputLimits()


@dataclass(frozen=True)
class FrozenSourceGuardPolicy:
    policy_digest: str
    six_song_sha256: frozenset[str]
    forbidden_sha256: frozenset[str]
    parser_config_sha256: str
    parser_version: str = "RXOPTIMIZER_MIDI_V1"
    limits: UserInputLimits = DEFAULT_LIMITS


@dataclass(frozen=True)
class SnapshotHandle:
    owner_scope_id: str
    session_locator_id: str
    upload_locator_id: str
    snapshot_instance_id: str
    snapshot_namespace_id: str


@dataclass(frozen=True)
class AcceptedSnapshot:
    status: str
    handle: SnapshotHandle
    raw_byte_sha256: str
    raw_byte_count: int
    semantic_digest: str
    subject_graph_sha256: str
    parse_invocation_count: int
    event_count: int
    note_count: int
    subject_count: int
    edge_count: int
    source_class: str = SOURCE_CLASS
    origin_trust: str = ORIGIN_TRUST
    capability: str = CAPABILITY
    mutation_capability: str = MUTATION_CAPABILITY
    evidence_authority: str = "NONE"
    model_authority: str = "NONE"
    training_eligibility: str = TRAINING_ELIGIBILITY
    retention_policy: str = RETENTION_POLICY


@dataclass(frozen=True)
class ExclusionReceipt:
    status: str
    owner_private_receipt_id: str
    terminal_reason: str
    guard_policy_digest: str
    raw_byte_sha256: str
    raw_byte_count: int
    orchestration_parse_invocation_count: int = 0
    subject_graph_status: str = "NOT_CREATED"
    automatic_route_status: str = "NOT_INVOKED"
    retention_state: str = RETENTION_POLICY
    package_inventory_digest: str = ""


@dataclass(frozen=True)
class PublicFailure:
    status: str


@dataclass
class _ParseCounter:
    count: int = 0

    def invoke(self, parser: Callable[[bytes], MidiFile], raw: bytes) -> MidiFile:
        if self.count:
            raise RuntimeError("parser invocation contract violated")
        self.count += 1
        return parser(raw)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _hex_digest(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _hmac_port(keys: Any, method: str, payload: bytes, *, scope: Any | None = None,
               key_id: str | None = None, key: bytes | None = None) -> str:
    fn = getattr(keys, method, None)
    if callable(fn):
        try:
            if key is not None:
                value = fn(key_id, key, payload) if key_id is not None else fn(key, payload)
            else:
                value = fn(scope, payload) if scope is not None else fn(payload)
        except TypeError:
            value = fn(payload=payload) if key is None else fn(key=key, payload=payload)
        return _hex_digest(value)
    raise RuntimeError("tenant key provider capability unavailable")


def _scope_value(scope: Any, name: str) -> str:
    value = getattr(scope, name, None)
    if value is None and isinstance(scope, Mapping):
        value = scope.get(name)
    if not isinstance(value, str) or not value:
        raise RuntimeError("invalid verified authorization scope")
    return value


def _policy_value(policy: Any, name: str) -> Any:
    if isinstance(policy, Mapping):
        return policy.get(name)
    return getattr(policy, name, None)


def _freeze_policy(policy: Any) -> FrozenSourceGuardPolicy:
    if policy is None:
        raise RuntimeError("mandatory guard policy unavailable")
    digest = _policy_value(policy, "policy_digest") or _policy_value(policy, "guard_policy_digest")
    parser_digest = _policy_value(policy, "parser_config_sha256")
    six = _policy_value(policy, "six_song_sha256")
    forbidden = _policy_value(policy, "forbidden_sha256")
    if not isinstance(digest, str) or not digest or not isinstance(parser_digest, str) or not parser_digest:
        raise RuntimeError("invalid frozen guard policy")
    if six is None or forbidden is None:
        raise RuntimeError("guard membership sets are mandatory")
    six_set = frozenset(str(item).lower() for item in six)
    forbidden_set = frozenset(str(item).lower() for item in forbidden)
    if len(six_set) != 6:
        raise RuntimeError("six-song guard policy must contain exactly six SHA-256 values")
    for item in six_set | forbidden_set:
        if len(item) != 64 or any(ch not in "0123456789abcdef" for ch in item):
            raise RuntimeError("invalid guard SHA-256")
    limits = _policy_value(policy, "limits") or DEFAULT_LIMITS
    if isinstance(limits, Mapping):
        limits = UserInputLimits(**limits)
    if not isinstance(limits, UserInputLimits):
        raise RuntimeError("invalid resource limits")
    if limits != DEFAULT_LIMITS or _policy_value(policy, "limits_version") != LIMITS_VERSION:
        raise RuntimeError("noncanonical resource contract")
    return FrozenSourceGuardPolicy(
        digest, six_set, forbidden_set, parser_digest,
        str(_policy_value(policy, "parser_version") or "RXOPTIMIZER_MIDI_V1"), limits,
    )


def _trusted_ingest_contract(ports: Any, scope: Any) -> tuple[Any, FrozenSourceGuardPolicy]:
    trusted = getattr(ports, "ingest_contracts", None)
    if trusted is None or not callable(getattr(trusted, "resolve", None)) or not callable(getattr(trusted, "owns", None)):
        raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
    contract = trusted.resolve(scope)
    if not trusted.owns(contract):
        raise StoreContractError(PublicErrorCode.POLICY_REJECTED)
    return contract, _freeze_policy(contract)


def _trusted_parse(ports: Any, scope: Any, contract: Any, raw: bytes, timeout_seconds: int) -> MidiFile:
    executor = getattr(ports, "parser_executor", None)
    if executor is None or not callable(getattr(executor,"execute",None)):
        raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
    try:
        midi = executor.execute(scope,contract,raw,timeout_seconds)
    except StoreContractError as exc:
        if exc.code is PublicErrorCode.INVALID_OR_UNSUPPORTED_MIDI:
            raise MidiError("trusted parser rejected MIDI") from None
        raise
    if not isinstance(midi, MidiFile):
        raise StoreContractError(PublicErrorCode.POLICY_REJECTED)
    return midi


def _builder_deadline(started: float, limits: UserInputLimits) -> float:
    if limits.max_builder_wall_seconds <= 0:
        raise ResourceLimitError
    return started + limits.max_builder_wall_seconds


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ResourceLimitError


def _stream_upload(ports: Any, upload_handle: Any, scope: Any) -> tuple[Iterable[bytes], str]:
    upload = getattr(ports, "sealed_upload", None) or getattr(ports, "upload", None)
    if upload is None or not callable(getattr(upload, "stream_once", None)):
        raise RuntimeError("sealed upload capability unavailable")
    result = upload.stream_once(upload_handle, scope)
    if isinstance(result, tuple) and len(result) == 2:
        return result[0], str(result[1])
    stream = getattr(result, "chunks", None) or getattr(result, "stream", None)
    generation = getattr(result, "seal_generation", None)
    if stream is None or generation is None:
        raise RuntimeError("invalid sealed upload stream")
    return stream, str(generation)


def _copy_and_rehash(chunks: Iterable[bytes], limits: UserInputLimits, *, on_chunk: Callable[[int], None] | None = None,
                     checkpoint: Callable[[], None] | None = None) -> tuple[tempfile.SpooledTemporaryFile, str, int]:
    spool = tempfile.SpooledTemporaryFile(max_size=1_048_576, mode="w+b")
    digest = sha256()
    count = 0
    try:
        for chunk in chunks:
            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                raise RuntimeError("sealed upload yielded non-bytes")
            data = bytes(chunk)
            count += len(data)
            if count > limits.max_raw_bytes:
                raise ResourceLimitError
            if on_chunk is not None: on_chunk(len(data))
            if checkpoint is not None: checkpoint()
            digest.update(data)
            spool.write(data)
        spool.flush()
        before = digest.hexdigest()
        spool.seek(0)
        verify = sha256()
        verify_count = 0
        while True:
            block = spool.read(65_536)
            if not block:
                break
            verify.update(block)
            verify_count += len(block)
        if verify.hexdigest() != before or verify_count != count:
            raise ByteIdentityError
        spool.seek(0)
        return spool, before, count
    except Exception:
        spool.close()
        raise


class ResourceLimitError(RuntimeError):
    pass


class ByteIdentityError(RuntimeError):
    pass


class _GraphSpool:
    """Disk-backed canonical graph sink with an enforced active batch bound."""

    def __init__(self, max_batch: int):
        if max_batch <= 0:
            raise ResourceLimitError
        handle = tempfile.NamedTemporaryFile(prefix="x10-user-graph-", suffix=".sqlite3", delete=False)
        self.path = handle.name
        handle.close()
        self.connection = sqlite3.connect(self.path)
        self.connection.executescript("""
            CREATE TABLE subjects(subject_id TEXT PRIMARY KEY,subject_type TEXT NOT NULL,natural_key_json TEXT NOT NULL,payload_json TEXT NOT NULL);
            CREATE TABLE edges(edge_type TEXT NOT NULL,parent_id TEXT NOT NULL,child_id TEXT NOT NULL,
              PRIMARY KEY(edge_type,parent_id,child_id));
        """)
        self.max_batch = max_batch
        self.subject_buffer: list[tuple[str, str, str, str]] = []
        self.edge_buffer: list[tuple[str, str, str]] = []
        self.peak_batch = 0
        self.subject_count = 0
        self.edge_count = 0

    def _observe(self) -> None:
        current = len(self.subject_buffer) + len(self.edge_buffer)
        self.peak_batch = max(self.peak_batch, current)
        if current >= self.max_batch:
            self.flush()

    def add_subject(self, row: Mapping[str, Any]) -> None:
        self.subject_buffer.append((row["subject_id"], row["subject_type"], _canonical(row["natural_key"]).decode(),
                                    _canonical(row["payload"]).decode()))
        self.subject_count += 1
        self._observe()

    def add_edge(self, row: Mapping[str, Any]) -> None:
        self.edge_buffer.append((row["edge_type"], row["parent_id"], row["child_id"]))
        self.edge_count += 1
        self._observe()

    def flush(self) -> None:
        if self.subject_buffer:
            self.connection.executemany("INSERT INTO subjects VALUES (?,?,?,?)", self.subject_buffer)
            self.subject_buffer.clear()
        if self.edge_buffer:
            self.connection.executemany("INSERT INTO edges VALUES (?,?,?)", self.edge_buffer)
            self.edge_buffer.clear()

    def finalize(self) -> None:
        self.flush()
        self.connection.commit()

    def subjects(self):
        self.finalize()
        for sid, kind, natural, payload in self.connection.execute(
            "SELECT subject_id,subject_type,natural_key_json,payload_json FROM subjects ORDER BY subject_type,subject_id"
        ):
            yield {"subject_id": sid, "subject_type": kind, "natural_key": json.loads(natural), "payload": json.loads(payload)}

    def edges(self):
        self.finalize()
        for kind, parent, child in self.connection.execute(
            "SELECT edge_type,parent_id,child_id FROM edges ORDER BY edge_type,parent_id,child_id"
        ):
            yield {"edge_type": kind, "parent_id": parent, "child_id": child}

    def close(self) -> None:
        try:
            self.connection.close()
        finally:
            try: os.unlink(self.path)
            except FileNotFoundError: pass


class _DiskArtifact:
    def __init__(self, path: str):
        self.path=path
        self.size=os.path.getsize(path)
    def chunks(self):
        with open(self.path,"rb") as stream:
            while True:
                block=stream.read(65_536)
                if not block: break
                yield block
    def close(self):
        try: os.unlink(self.path)
        except FileNotFoundError: pass


def _graph_digest(namespace: str, spool: _GraphSpool) -> str:
    digest = sha256()
    def add(value: Any) -> None:
        encoded = _canonical(value)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    add({"contract": SUBJECT_VERSION, "namespace": namespace})
    for value in spool.subjects(): add(value)
    for value in spool.edges(): add(value)
    return digest.hexdigest()


def _graph_digest_from_connection(namespace: str, connection: sqlite3.Connection) -> str:
    digest = sha256()
    def add(value: Any) -> None:
        encoded = _canonical(value); digest.update(len(encoded).to_bytes(8, "big")); digest.update(encoded)
    add({"contract": SUBJECT_VERSION, "namespace": namespace})
    for sid, kind, natural, payload in connection.execute(
        "SELECT subject_id,subject_type,natural_key_json,payload_json FROM user_input_subjects ORDER BY subject_type,subject_id"
    ):
        add({"subject_id":sid,"subject_type":kind,"natural_key":json.loads(natural),"payload":json.loads(payload)})
    for kind,parent,child in connection.execute(
        "SELECT edge_type,parent_id,child_id FROM user_input_subject_edges ORDER BY edge_type,parent_id,child_id"
    ):
        add({"edge_type":kind,"parent_id":parent,"child_id":child})
    return digest.hexdigest()


def _preflight(raw: bytes, limits: UserInputLimits) -> None:
    if len(raw) < 14 or raw[:4] != b"MThd":
        raise MidiError("invalid header")
    header_len = struct.unpack(">I", raw[4:8])[0]
    if header_len < 6 or 8 + header_len > len(raw):
        raise MidiError("invalid header length")
    _, tracks, division = struct.unpack(">HHH", raw[8:14])
    if tracks > limits.max_tracks:
        raise ResourceLimitError
    if division & 0x8000:
        raise MidiError("unsupported SMPTE division")
    pos = 8 + header_len
    total_events = 0
    total_private = 0

    def vlq(chunk: bytes, offset: int) -> tuple[int, int]:
        value = 0
        start = offset
        for _ in range(limits.max_vlq_bytes):
            if offset >= len(chunk):
                raise MidiError("truncated VLQ")
            byte = chunk[offset]
            offset += 1
            value = (value << 7) | (byte & 0x7F)
            if not byte & 0x80:
                width = offset - start
                if (width > 1 and value < 1 << (7 * (width - 1))):
                    raise ResourceLimitError
                return value, offset
        raise ResourceLimitError

    for _ in range(tracks):
        if pos + 8 > len(raw) or raw[pos:pos + 4] != b"MTrk":
            raise MidiError("invalid track header")
        length = struct.unpack(">I", raw[pos + 4:pos + 8])[0]
        if length > limits.max_declared_track_bytes:
            raise ResourceLimitError
        if length > len(raw) - (pos + 8):
            raise MidiError("declared track exceeds remaining bytes")
        chunk = raw[pos + 8:pos + 8 + length]
        cursor = 0
        running = None
        tick = 0
        track_events = 0
        while cursor < len(chunk):
            delta, cursor = vlq(chunk, cursor)
            tick += delta
            if tick > limits.max_absolute_tick or cursor >= len(chunk):
                raise ResourceLimitError if tick > limits.max_absolute_tick else MidiError("truncated event")
            if chunk[cursor] & 0x80:
                status = chunk[cursor]
                cursor += 1
            elif running is not None:
                status = running
            else:
                raise MidiError("running status without status")
            if status == 0xFF:
                running = None
                if cursor >= len(chunk):
                    raise MidiError("truncated meta type")
                meta_type = chunk[cursor]
                cursor += 1
                size, cursor = vlq(chunk, cursor)
                if size > len(chunk) - cursor:
                    raise MidiError("truncated meta payload")
                if meta_type in {1, 2, 3, 4, 5, 6, 7}:
                    if size > limits.max_text_payload_bytes_event:
                        raise ResourceLimitError
                    total_private += size
                cursor += size
            elif status in (0xF0, 0xF7):
                running = None
                size, cursor = vlq(chunk, cursor)
                if size > limits.max_sysex_payload_bytes_event:
                    raise ResourceLimitError
                if size > len(chunk) - cursor:
                    raise MidiError("truncated SysEx payload")
                total_private += size
                cursor += size
            elif 0x80 <= status <= 0xEF:
                running = status
                size = 1 if (status & 0xF0) in (0xC0, 0xD0) else 2
                if size > len(chunk) - cursor:
                    raise MidiError("truncated channel event")
                if any(value & 0x80 for value in chunk[cursor:cursor + size]):
                    raise MidiError("invalid channel data")
                cursor += size
            else:
                raise MidiError("unsupported system event")
            track_events += 1
            total_events += 1
            if track_events > limits.max_events_per_track or total_events > limits.max_events_total:
                raise ResourceLimitError
            if total_private > limits.max_cumulative_private_payload:
                raise ResourceLimitError
        pos += 8 + length


def _event_semantic(event: Any, payload_key_id: str, payload_key: bytes, keys: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    private = event.kind in {"sysex"} or (event.kind == "meta" and event.data1 in {1, 2, 3, 4, 5, 6, 7})
    raw = bytes(event.raw or b"")
    if private:
        data_digest = _hmac_port(keys, "payload_hmac", _canonical(["X10_PRIVATE_MIDI_PAYLOAD_V1", event.kind]) + raw,
                                 key_id=payload_key_id, key=payload_key)
        public_payload = {"private_payload": True, "payload_length": len(raw)}
    else:
        data_digest = sha256(_canonical([event.data1, event.data2, event.status, raw.hex()])).hexdigest()
        public_payload = {"private_payload": False, "payload_length": len(raw)}
    natural = {
        "authority_domain": AUTHORITY_DOMAIN, "absolute_tick": int(event.tick), "event_kind": event.kind,
        "channel_or_null": event.channel, "status_or_meta_type": event.status if event.kind != "meta" else event.data1,
        "canonical_data_digest": data_digest,
    }
    return natural, public_payload


def _build_graph(midi: MidiFile, namespace: str, payload_key_id: str, payload_key: bytes, keys: Any,
                 scope: Any, limits: UserInputLimits, *, deadline: float | None = None) -> tuple[_GraphSpool, int, int]:
    spool = _GraphSpool(limits.max_peak_event_batch)
    track_channel_ids: dict[tuple[int, int], str] = {}
    active: dict[tuple[int, int, int], list[tuple[str, Any]]] = {}
    note_count = 0
    private_total = 0

    def subject_id(kind: str, natural: Mapping[str, Any]) -> str:
        return _hmac_port(keys, "namespace_hmac", _canonical([namespace, kind, natural]), scope=scope)

    def check_deadline() -> None:
        if deadline is not None and time.monotonic() > deadline:
            raise ResourceLimitError

    for track_index, events in enumerate(midi.tracks):
        if len(events) > limits.max_events_per_track:
            raise ResourceLimitError
        for ordinal, event in enumerate(events):
            check_deadline()
            if event.tick < 0 or event.tick > limits.max_absolute_tick:
                raise ResourceLimitError
            if event.kind == "sysex" and len(event.raw or b"") > limits.max_sysex_payload_bytes_event:
                raise ResourceLimitError
            if event.kind == "meta" and event.data1 in {1, 2, 3, 4, 5, 6, 7} and len(event.raw or b"") > limits.max_text_payload_bytes_event:
                raise ResourceLimitError
            if event.kind == "sysex" or (event.kind == "meta" and event.data1 in {1, 2, 3, 4, 5, 6, 7}):
                private_total += len(event.raw or b"")
                if private_total > limits.max_cumulative_private_payload:
                    raise ResourceLimitError
            natural, public_payload = _event_semantic(event, payload_key_id, payload_key, keys)
            natural.update({"format_track_index": track_index, "track_event_ordinal": ordinal})
            eid = subject_id("EVENT", natural)
            spool.add_subject({"subject_id": eid, "subject_type": "EVENT", "natural_key": natural, "payload": public_payload})
            if event.channel is not None:
                tc_key = (track_index, int(event.channel))
                if tc_key not in track_channel_ids:
                    tc_natural = {"authority_domain": AUTHORITY_DOMAIN, "format_track_index": track_index, "channel": int(event.channel)}
                    tcid = subject_id("TRACK_CHANNEL", tc_natural)
                    track_channel_ids[tc_key] = tcid
                    spool.add_subject({"subject_id": tcid, "subject_type": "TRACK_CHANNEL", "natural_key": tc_natural, "payload": {}})
                spool.add_edge({"edge_type": "TRACK_CHANNEL_CONTAINS_EVENT", "parent_id": track_channel_ids[tc_key], "child_id": eid})
            key = (track_index, int(event.channel or 0), int(event.data1 or 0))
            if event.kind == "note_on" and int(event.data2 or 0) > 0:
                active.setdefault(key, []).append((eid, event))
            elif event.kind == "note_off" and active.get(key):
                on_id, on_event = active[key].pop(0)
                note_natural = {"authority_domain": AUTHORITY_DOMAIN, "on_event_id": on_id, "off_event_id": eid,
                                "unmatched_status": "MATCHED", "channel": key[1], "pitch": key[2]}
                nid = subject_id("NOTE", note_natural)
                spool.add_subject({"subject_id": nid, "subject_type": "NOTE", "natural_key": note_natural,
                                   "payload": {"start_tick": int(on_event.tick), "end_tick": int(event.tick)}})
                for edge in [
                    {"edge_type": "TRACK_CHANNEL_CONTAINS_NOTE", "parent_id": track_channel_ids[(track_index, key[1])], "child_id": nid},
                    {"edge_type": "NOTE_HAS_ON_EVENT", "parent_id": nid, "child_id": on_id},
                    {"edge_type": "NOTE_HAS_OFF_EVENT", "parent_id": nid, "child_id": eid},
                ]: spool.add_edge(edge)
                note_count += 1
            elif event.kind == "note_off":
                note_natural = {"authority_domain": AUTHORITY_DOMAIN, "on_event_id": None, "off_event_id": eid,
                                "unmatched_status": "UNMATCHED_OFF", "channel": key[1], "pitch": key[2]}
                nid = subject_id("NOTE", note_natural)
                spool.add_subject({"subject_id": nid, "subject_type": "NOTE", "natural_key": note_natural,
                                   "payload": {"start_tick": None, "end_tick": int(event.tick)}})
                for edge in [
                    {"edge_type": "TRACK_CHANNEL_CONTAINS_NOTE", "parent_id": track_channel_ids[(track_index, key[1])], "child_id": nid},
                    {"edge_type": "NOTE_HAS_OFF_EVENT", "parent_id": nid, "child_id": eid},
                ]: spool.add_edge(edge)
                note_count += 1
    for (track_index, channel, pitch), rows in sorted(active.items()):
        for on_id, on_event in rows:
            note_natural = {"authority_domain": AUTHORITY_DOMAIN, "on_event_id": on_id, "off_event_id": None,
                            "unmatched_status": "UNMATCHED_ON", "channel": channel, "pitch": pitch}
            nid = subject_id("NOTE", note_natural)
            spool.add_subject({"subject_id": nid, "subject_type": "NOTE", "natural_key": note_natural,
                               "payload": {"start_tick": int(on_event.tick), "end_tick": None}})
            for edge in [
                {"edge_type": "TRACK_CHANNEL_CONTAINS_NOTE", "parent_id": track_channel_ids[(track_index, channel)], "child_id": nid},
                {"edge_type": "NOTE_HAS_ON_EVENT", "parent_id": nid, "child_id": on_id},
            ]: spool.add_edge(edge)
            note_count += 1
    event_count = sum(len(track) for track in midi.tracks)
    spool.finalize()
    if event_count > limits.max_events_total or spool.subject_count > limits.max_graph_subjects or spool.edge_count > limits.max_graph_edges or note_count > limits.max_notes_total:
        spool.close()
        raise ResourceLimitError
    return spool, event_count, note_count


def _sqlite_snapshot(run: Mapping[str, Any], spool: _GraphSpool) -> _DiskArtifact:
    handle=tempfile.NamedTemporaryFile(prefix="x10-user-snapshot-",suffix=".sqlite3",delete=False);path=handle.name;handle.close()
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript("""
        CREATE TABLE snapshot_runs(snapshot_id TEXT PRIMARY KEY, semantic_json TEXT NOT NULL,
          terminal_status TEXT NOT NULL CHECK(terminal_status='SNAPSHOT_ACCEPTED_USER_INPUT'),
          capability TEXT NOT NULL CHECK(capability='ANALYZE_ONLY'),
          mutation_capability TEXT NOT NULL CHECK(mutation_capability='NONE'));
        CREATE TABLE user_input_artifacts(snapshot_id TEXT PRIMARY KEY, raw_sha256 TEXT NOT NULL,
          raw_byte_count INTEGER NOT NULL CHECK(raw_byte_count>=0), content_id TEXT NOT NULL,
          authority_domain TEXT NOT NULL CHECK(authority_domain='USER_INPUT'),
          FOREIGN KEY(snapshot_id) REFERENCES snapshot_runs(snapshot_id));
        CREATE TABLE user_input_origins(snapshot_id TEXT PRIMARY KEY, owner_scope_id TEXT NOT NULL,
          session_locator_id TEXT NOT NULL, upload_locator_id TEXT NOT NULL,
          origin_trust TEXT NOT NULL CHECK(origin_trust='UNVERIFIED_USER_ORIGIN'),
          FOREIGN KEY(snapshot_id) REFERENCES snapshot_runs(snapshot_id));
        CREATE TABLE user_input_source_classification(snapshot_id TEXT PRIMARY KEY,
          source_class TEXT NOT NULL CHECK(source_class='USER_INPUT_RAW'), guard_policy_digest TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status='SNAPSHOT_ACCEPTED_USER_INPUT'),
          FOREIGN KEY(snapshot_id) REFERENCES snapshot_runs(snapshot_id));
        CREATE TABLE user_input_parse_manifests(snapshot_id TEXT PRIMARY KEY, midi_format INTEGER NOT NULL,
          division INTEGER NOT NULL, track_count INTEGER NOT NULL, event_count INTEGER NOT NULL,
          note_count INTEGER NOT NULL, parser_version TEXT NOT NULL, parser_config_sha256 TEXT NOT NULL,
          parse_invocation_count INTEGER NOT NULL CHECK(parse_invocation_count=1),
          FOREIGN KEY(snapshot_id) REFERENCES snapshot_runs(snapshot_id));
        CREATE TABLE user_input_subjects(
          snapshot_namespace_id TEXT NOT NULL, subject_id TEXT NOT NULL,
          subject_type TEXT NOT NULL CHECK(subject_type IN ('EVENT','NOTE','TRACK_CHANNEL')),
          natural_key_json TEXT NOT NULL, payload_json TEXT NOT NULL,
          PRIMARY KEY(snapshot_namespace_id,subject_id));
        CREATE TABLE user_input_subject_edges(
          snapshot_namespace_id TEXT NOT NULL, edge_type TEXT NOT NULL
            CHECK(edge_type IN ('TRACK_CHANNEL_CONTAINS_EVENT','TRACK_CHANNEL_CONTAINS_NOTE','NOTE_HAS_ON_EVENT','NOTE_HAS_OFF_EVENT')),
          parent_id TEXT NOT NULL, child_id TEXT NOT NULL,
          PRIMARY KEY(snapshot_namespace_id,edge_type,parent_id,child_id),
          FOREIGN KEY(snapshot_namespace_id,parent_id) REFERENCES user_input_subjects(snapshot_namespace_id,subject_id),
          FOREIGN KEY(snapshot_namespace_id,child_id) REFERENCES user_input_subjects(snapshot_namespace_id,subject_id));
        CREATE TABLE snapshot_authority_policy(snapshot_id TEXT PRIMARY KEY,
          evidence_authority TEXT NOT NULL CHECK(evidence_authority='NONE'),
          model_authority TEXT NOT NULL CHECK(model_authority='NONE'),
          training_eligibility TEXT NOT NULL CHECK(training_eligibility='NEVER'),
          midi_output TEXT NOT NULL CHECK(midi_output='NONE'), policy_digest TEXT NOT NULL,
          FOREIGN KEY(snapshot_id) REFERENCES snapshot_runs(snapshot_id));
        CREATE TABLE snapshot_semantic_digest(snapshot_id TEXT PRIMARY KEY, semantic_digest TEXT NOT NULL,
          subject_graph_sha256 TEXT NOT NULL,
          FOREIGN KEY(snapshot_id) REFERENCES snapshot_runs(snapshot_id));
    """)
    namespace = str(run["snapshot_namespace_id"])
    snapshot_id = str(run["snapshot_id"])
    connection.execute("INSERT INTO snapshot_runs VALUES (?,?,?,?,?)", (snapshot_id, _canonical(run).decode(),
        "SNAPSHOT_ACCEPTED_USER_INPUT", CAPABILITY, MUTATION_CAPABILITY))
    content_id = sha256(_canonical(["X10_USER_INPUT_CONTENT_V1", run["raw_byte_sha256"], run["raw_byte_count"]])).hexdigest()
    connection.execute("INSERT INTO user_input_artifacts VALUES (?,?,?,?,?)",
        (snapshot_id, run["raw_byte_sha256"], run["raw_byte_count"], content_id, AUTHORITY_DOMAIN))
    connection.execute("INSERT INTO user_input_origins VALUES (?,?,?,?,?)", (snapshot_id, run["owner_scope_id"],
        run["session_locator_id"], run["upload_locator_id"], ORIGIN_TRUST))
    connection.execute("INSERT INTO user_input_source_classification VALUES (?,?,?,?)",
        (snapshot_id, SOURCE_CLASS, run["guard_policy_digest"], "SNAPSHOT_ACCEPTED_USER_INPUT"))
    connection.execute("INSERT INTO user_input_parse_manifests VALUES (?,?,?,?,?,?,?,?,?)", (snapshot_id,
        run["midi_format"], run["division"], run["track_count"], run["event_count"], run["note_count"],
        run["parser_version"], run["parser_config_sha256"], 1))
    subject_batch=[]
    for row in spool.subjects():
        subject_batch.append((namespace,row["subject_id"],row["subject_type"],_canonical(row["natural_key"]).decode(),_canonical(row["payload"]).decode()))
        if len(subject_batch)>=spool.max_batch:
            connection.executemany("INSERT INTO user_input_subjects VALUES (?,?,?,?,?)",subject_batch);subject_batch.clear()
    if subject_batch: connection.executemany("INSERT INTO user_input_subjects VALUES (?,?,?,?,?)",subject_batch)
    edge_batch=[]
    for row in spool.edges():
        edge_batch.append((namespace,row["edge_type"],row["parent_id"],row["child_id"]))
        if len(edge_batch)>=spool.max_batch:
            connection.executemany("INSERT INTO user_input_subject_edges VALUES (?,?,?,?)",edge_batch);edge_batch.clear()
    if edge_batch: connection.executemany("INSERT INTO user_input_subject_edges VALUES (?,?,?,?)",edge_batch)
    connection.execute("INSERT INTO snapshot_authority_policy VALUES (?,?,?,?,?,?)", (snapshot_id, "NONE", "NONE",
        TRAINING_ELIGIBILITY, "NONE", run["authority_policy_digest"]))
    connection.execute("INSERT INTO snapshot_semantic_digest VALUES (?,?,?)", (snapshot_id,
        run["semantic_digest"], run["subject_graph_sha256"]))
    connection.commit()
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or connection.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("snapshot SQLite validation failed")
    connection.close()
    return _DiskArtifact(path)


def _verify_auth(ports: Any, auth_handle: Any, operation: str) -> Any:
    verifier = getattr(ports, "authorization", None) or getattr(ports, "auth", None)
    if verifier is None or not callable(getattr(verifier, "verify", None)):
        raise RuntimeError("authorization capability unavailable")
    try:
        operation_value = Operation(operation)
    except ValueError:
        operation_value = operation
    return verifier.verify(auth_handle, operation_value)


def _make_receipt(keys: Any, scope: Any, raw_sha: str, raw_count: int, policy: FrozenSourceGuardPolicy,
                  reason: str, *, parse_count: int = 0) -> ExclusionReceipt:
    receipt_payload = ["X10_USER_INPUT_EXCLUSION_RECEIPT_V1", _scope_value(scope, "owner_scope_id"),
                       _scope_value(scope, "session_locator_id"), _scope_value(scope, "upload_locator_id"),
                       raw_sha, raw_count, policy.policy_digest, reason, parse_count]
    rid = _hmac_port(keys, "audit_hmac", _canonical(receipt_payload), scope=scope)
    inventory = sha256(_canonical({"raw_retained": False, "parse": False, "graph": False,
                                   "midi_output": False, "delay_terca_handoff": False})).hexdigest()
    return ExclusionReceipt(reason, rid, reason, policy.policy_digest, raw_sha, raw_count,
                            orchestration_parse_invocation_count=parse_count, package_inventory_digest=inventory)


def _read_member(package: Any, key: CompositeSnapshotKey, name: str) -> bytes:
    stream = package.open_active_read_only(key, name)
    try:
        return stream.read()
    finally:
        stream.close()


def _accepted_from_package(package: Any, key: CompositeSnapshotKey) -> AcceptedSnapshot:
    manifest = json.loads(_read_member(package, key, "private_manifest.json"))
    handle = SnapshotHandle(key.owner_scope_id, key.session_locator_id, key.upload_locator_id,
                            key.snapshot_instance_id, manifest["snapshot_namespace_id"])
    return AcceptedSnapshot("SNAPSHOT_ACCEPTED_USER_INPUT", handle, manifest["raw_byte_sha256"],
        int(manifest["raw_byte_count"]), manifest["semantic_digest"], manifest["subject_graph_sha256"],
        int(manifest["parse_invocation_count"]), int(manifest["event_count"]), int(manifest["note_count"]),
        int(manifest["subject_count"]), int(manifest["edge_count"]))


def create_user_input_snapshot(ports: Any, auth_handle: Any, upload_handle: Any) -> AcceptedSnapshot | ExclusionReceipt | PublicFailure:
    """Create one immutable USER_INPUT package through injected trusted ports."""
    stage = None
    spool = None
    graph_spool = None
    sqlite_artifact = None
    reservation_key = None
    new_reservation = False
    create_finished = False
    registry = None
    package = None
    quota_token = None
    quota = None
    builder_watch = None
    quota_committed = False
    started = time.monotonic()
    try:
        scope = _verify_auth(ports, auth_handle, "CREATE")
        ingest_contract, frozen = _trusted_ingest_contract(ports, scope)
        deadline = _builder_deadline(started, frozen.limits)
        quota = getattr(ports, "session_quota", None)
        watchdog = getattr(ports, "watchdog", None)
        if quota is None or not callable(getattr(quota, "begin", None)) or watchdog is None:
            raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
        quota_token = quota.begin(scope)
        builder_watch = watchdog.start(scope, "BUILDER", frozen.limits.max_builder_wall_seconds)
        chunks, seal_generation = _stream_upload(ports, upload_handle, scope)
        spool, raw_sha, raw_count = _copy_and_rehash(chunks, frozen.limits,
            on_chunk=lambda size: quota.consume(quota_token,size), checkpoint=lambda: watchdog.checkpoint(builder_watch))
        _check_deadline(deadline)
        keys = getattr(ports, "keys", None) or getattr(ports, "tenant_keys", None)
        if keys is None:
            raise RuntimeError("tenant key provider unavailable")
        if raw_sha in frozen.six_song_sha256:
            return _make_receipt(keys, scope, raw_sha, raw_count, frozen, "EXCLUDED_SIX_SONG_GENERAL_X10")
        if raw_sha in frozen.forbidden_sha256:
            return _make_receipt(keys, scope, raw_sha, raw_count, frozen, "EXCLUDED_FORBIDDEN_SOURCE")
        spool.seek(0)
        raw = spool.read()
        try:
            _preflight(raw, frozen.limits)
        except MidiError:
            return _make_receipt(keys, scope, raw_sha, raw_count, frozen, "INVALID_OR_UNSUPPORTED_MIDI")
        _check_deadline(deadline)
        watchdog.checkpoint(builder_watch)
        registry = getattr(ports, "registry", None) or getattr(ports, "operational_registry", None)
        package = getattr(ports, "packages", None) or getattr(ports, "package_store", None)
        if package is None or registry is None:
            raise RuntimeError("package or registry capability unavailable")
        identity = ReservationIdentity(raw_sha, raw_count, frozen.policy_digest,
                                       frozen.parser_config_sha256, seal_generation)
        reservation = registry.reserve(scope, identity)
        reservation_key = reservation.key
        if reservation.kind is ReservationKind.IN_PROGRESS:
            return PublicFailure("OPERATION_IN_PROGRESS")
        if reservation.kind is ReservationKind.IDEMPOTENT:
            return _accepted_from_package(package, reservation.key)
        new_reservation = True
        counter = _ParseCounter()
        try:
            midi = counter.invoke(lambda payload: _trusted_parse(ports, scope, ingest_contract, payload,
                                                                 frozen.limits.max_parser_wall_seconds), raw)
        except MidiError:
            return _make_receipt(keys, scope, raw_sha, raw_count, frozen, "INVALID_OR_UNSUPPORTED_MIDI", parse_count=counter.count)
        if counter.count != 1:
            raise RuntimeError("exactly-one parse contract violated")
        watchdog.checkpoint(builder_watch)
        payload_result = keys.snapshot_payload_key(scope, reservation.generation_token)
        if not isinstance(payload_result, tuple) or len(payload_result) != 2:
            raise RuntimeError("invalid snapshot payload key result")
        payload_key_id, payload_key = payload_result
        if not isinstance(payload_key_id, str) or not payload_key_id or not isinstance(payload_key, bytes) or len(payload_key) != 32:
            raise RuntimeError("invalid snapshot payload key")
        namespace_payload = _canonical(["X10_USER_INPUT_NAMESPACE_V1", _scope_value(scope, "owner_scope_id"),
                                        _scope_value(scope, "session_locator_id"), _scope_value(scope, "upload_locator_id"),
                                        raw_sha, frozen.parser_config_sha256])
        namespace = _hmac_port(keys, "namespace_hmac", namespace_payload, scope=scope)
        graph_spool, event_count, note_count = _build_graph(midi, namespace, payload_key_id, payload_key, keys, scope,
                                                            frozen.limits, deadline=deadline)
        watchdog.checkpoint(builder_watch)
        spool.seek(0)
        post_parse_digest = sha256()
        post_parse_count = 0
        while True:
            block = spool.read(65_536)
            if not block:
                break
            post_parse_digest.update(block)
            post_parse_count += len(block)
        if post_parse_digest.hexdigest() != raw_sha or post_parse_count != raw_count:
            raise ByteIdentityError
        graph_digest = _graph_digest(namespace, graph_spool)
        snapshot_instance_id = reservation.key.snapshot_instance_id
        authority_policy_digest = sha256(_canonical({"authority_domain": AUTHORITY_DOMAIN, "source_class": SOURCE_CLASS,
            "evidence_authority": "NONE", "model_authority": "NONE", "training_eligibility": TRAINING_ELIGIBILITY,
            "mutation_capability": MUTATION_CAPABILITY, "midi_output": "NONE"})).hexdigest()
        run = {"snapshot_id": snapshot_instance_id, "snapshot_namespace_id": namespace, "contract_version": CONTRACT_VERSION,
               "subject_version": SUBJECT_VERSION, "limits_version": LIMITS_VERSION, "parser_version": frozen.parser_version,
               "parser_config_sha256": frozen.parser_config_sha256, "guard_policy_digest": frozen.policy_digest,
               "request_generation_token": reservation.generation_token,
               "raw_byte_sha256": raw_sha, "raw_byte_count": raw_count,
               "owner_scope_id": _scope_value(scope, "owner_scope_id"),
               "session_locator_id": _scope_value(scope, "session_locator_id"),
               "upload_locator_id": _scope_value(scope, "upload_locator_id"),
               "midi_format": int(midi.format), "division": int(midi.division), "track_count": len(midi.tracks),
               "event_count": event_count, "note_count": note_count,
               "source_class": SOURCE_CLASS, "origin_trust": ORIGIN_TRUST, "capability": CAPABILITY,
               "mutation_capability": MUTATION_CAPABILITY, "evidence_authority": "NONE", "model_authority": "NONE",
               "training_eligibility": TRAINING_ELIGIBILITY, "retention_policy": RETENTION_POLICY,
               "parse_invocation_count": 1, "subject_graph_sha256": graph_digest,
               "authority_policy_digest": authority_policy_digest, "midi_output": "NONE"}
        semantic_digest = sha256(_canonical(run)).hexdigest()
        run["semantic_digest"] = semantic_digest
        sqlite_artifact = _sqlite_snapshot(run, graph_spool)
        watchdog.checkpoint(builder_watch)
        manifest = _canonical({**run, "event_count": event_count, "note_count": note_count,
                               "subject_count": graph_spool.subject_count, "edge_count": graph_spool.edge_count,
                               "peak_graph_batch": graph_spool.peak_batch,
                               "private_payload_algorithm": "HMAC-SHA256", "private_payload_key_bytes": 32,
                               "private_payload_key_id": payload_key_id,
                               "tenant_key_provider_version": str(getattr(keys, "provider_version", "UNSPECIFIED"))})
        key_slot = _canonical({"key_id": payload_key_id, "algorithm": "HMAC-SHA256",
                               "provider_version": str(getattr(keys, "provider_version", "UNSPECIFIED")),
                               "key_material_base64url": base64.urlsafe_b64encode(payload_key).decode("ascii").rstrip("=")})
        if raw_count + sqlite_artifact.size + len(manifest) + len(key_slot) > frozen.limits.max_staged_package_bytes:
            raise ResourceLimitError
        quota.consume(quota_token, sqlite_artifact.size + len(manifest) + len(key_slot))
        _check_deadline(deadline)
        locator = reservation.key
        stage = package.create_stage(locator)
        package.write_private_member(stage, "original_upload.bin", (raw,))
        package.write_private_member(stage, "snapshot.sqlite3", sqlite_artifact.chunks())
        package.write_private_member(stage, "private_manifest.json", (manifest,))
        package.write_private_member(stage, "payload_key.slot", (key_slot,))
        staged_inventory = package.fsync_stage(stage)
        if set(staged_inventory.members) != {"original_upload.bin", "snapshot.sqlite3", "private_manifest.json", "payload_key.slot"}:
            raise RuntimeError("package inventory mismatch")
        inventory = package.publish_generation(stage, locator)
        stage = None
        handle = SnapshotHandle(locator.owner_scope_id, locator.session_locator_id, locator.upload_locator_id,
                                locator.snapshot_instance_id, namespace)
        accepted = AcceptedSnapshot("SNAPSHOT_ACCEPTED_USER_INPUT", handle, raw_sha, raw_count, semantic_digest,
                                    graph_digest, 1, event_count, note_count, graph_spool.subject_count, graph_spool.edge_count)
        retained_bytes=sum(item[0] for item in inventory.members.values())
        quota.commit(quota_token, locator, retained_bytes)
        quota_committed = True
        registry.finish_create(locator, inventory.generation_digest)
        create_finished = True
        watchdog.finish(builder_watch)
        return accepted
    except ResourceLimitError:
        return PublicFailure("RESOURCE_LIMIT_EXCEEDED")
    except ByteIdentityError:
        return PublicFailure("INTERNAL_OPERATION_FAILED")
    except StoreContractError as exc:
        return PublicFailure(exc.code.value)
    except Exception:
        return PublicFailure("INTERNAL_OPERATION_FAILED")
    finally:
        if spool is not None:
            spool.close()
        if graph_spool is not None:
            graph_spool.close()
        if sqlite_artifact is not None:
            sqlite_artifact.close()
        if stage is not None:
            try:
                package.abort_stage(stage)
            except Exception:
                pass
        if reservation_key is not None and new_reservation and not create_finished and registry is not None:
            try:
                registry.fail_create(reservation_key)
            except Exception:
                pass
        if quota_token is not None and not quota_committed:
            try:
                quota.abort(quota_token)
            except Exception:
                pass
        if reservation_key is not None and quota_committed and not create_finished:
            try:
                quota.release_snapshot(reservation_key)
            except Exception:
                pass
        if builder_watch is not None and not create_finished:
            try:
                watchdog.finish(builder_watch)
            except Exception:
                pass


def verify_user_input_snapshot(ports: Any, auth_handle: Any, snapshot_handle: SnapshotHandle) -> Mapping[str, str]:
    """Verify the full raw + graph package; no graph-only state is accepted."""
    rebuild = None
    try:
        scope = _verify_auth(ports, auth_handle, "VERIFY")
        ingest_contract, frozen = _trusted_ingest_contract(ports, scope)
        deadline = _builder_deadline(time.monotonic(), frozen.limits)
        if (_scope_value(scope, "owner_scope_id"), _scope_value(scope, "session_locator_id"),
            _scope_value(scope, "upload_locator_id")) != (snapshot_handle.owner_scope_id,
                                                            snapshot_handle.session_locator_id,
                                                            snapshot_handle.upload_locator_id):
            return {"status": "NOT_AVAILABLE"}
        registry = getattr(ports, "registry", None) or getattr(ports, "operational_registry", None)
        package = getattr(ports, "packages", None) or getattr(ports, "package_store", None)
        locator = CompositeSnapshotKey(snapshot_handle.owner_scope_id, snapshot_handle.session_locator_id,
                                       snapshot_handle.upload_locator_id, snapshot_handle.snapshot_instance_id)
        lease = registry.acquire_lease(scope, locator)
        try:
            registry.validate_lease(lease)
            inventory = package.inventory(locator)
            if set(inventory.members) != {"original_upload.bin", "snapshot.sqlite3", "private_manifest.json", "payload_key.slot"}:
                return {"status": "NOT_AVAILABLE"}
            accepted_inventory = registry.accepted_inventory_digest(scope, locator)
            if accepted_inventory != inventory.generation_digest:
                return {"status": "NOT_AVAILABLE"}
            raw = _read_member(package, locator, "original_upload.bin")
            manifest_bytes = _read_member(package, locator, "private_manifest.json")
            database = _read_member(package, locator, "snapshot.sqlite3")
            key_slot_bytes = _read_member(package, locator, "payload_key.slot")
            key_slot = json.loads(key_slot_bytes)
            manifest = json.loads(manifest_bytes)
            if (manifest.get("snapshot_id")!=snapshot_handle.snapshot_instance_id
                or manifest.get("contract_version")!=CONTRACT_VERSION
                or manifest.get("subject_version")!=SUBJECT_VERSION
                or manifest.get("limits_version")!=LIMITS_VERSION
                or manifest.get("guard_policy_digest")!=frozen.policy_digest
                or manifest.get("parser_config_sha256")!=frozen.parser_config_sha256
                or manifest.get("parser_version")!=frozen.parser_version
                or manifest.get("raw_byte_sha256") in frozen.six_song_sha256|frozen.forbidden_sha256):
                return {"status":"NOT_AVAILABLE"}
            encoded_key = key_slot.get("key_material_base64url", "")
            payload_key = base64.urlsafe_b64decode(encoded_key + "=" * (-len(encoded_key) % 4))
            if (len(payload_key) != 32 or key_slot.get("algorithm") != "HMAC-SHA256"
                or set(key_slot)!={"key_id","algorithm","provider_version","key_material_base64url"}
                or key_slot.get("key_id") != manifest.get("private_payload_key_id")
                or key_slot.get("provider_version") != manifest.get("tenant_key_provider_version")
                or key_slot.get("provider_version") != getattr(ports.tenant_keys, "provider_version", None)
                or manifest.get("private_payload_algorithm")!="HMAC-SHA256"
                or manifest.get("private_payload_key_bytes")!=32):
                return {"status": "NOT_AVAILABLE"}
            if sha256(raw).hexdigest() != manifest["raw_byte_sha256"] or len(raw) != manifest["raw_byte_count"]:
                return {"status": "NOT_AVAILABLE"}
            _preflight(raw, frozen.limits)
            midi = _trusted_parse(ports, scope, ingest_contract, raw, frozen.limits.max_parser_wall_seconds)
            _check_deadline(deadline)
            connection = sqlite3.connect(":memory:")
            connection.deserialize(database)
            ok = connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            fk_ok = not connection.execute("PRAGMA foreign_key_check").fetchall()
            row = connection.execute("SELECT semantic_json FROM snapshot_runs").fetchone()
            if not ok or not fk_ok or row is None:
                connection.close()
                return {"status": "NOT_AVAILABLE"}
            stored_run = json.loads(row[0])
            run = dict(stored_run)
            semantic = run.pop("semantic_digest", None)
            extras = {"subject_count","edge_count","peak_graph_batch","private_payload_algorithm",
                      "private_payload_key_bytes","private_payload_key_id","tenant_key_provider_version"}
            if (set(manifest) != set(stored_run) | extras
                or any(manifest.get(key) != value for key,value in stored_run.items())
                or semantic != sha256(_canonical(run)).hexdigest() or semantic != manifest.get("semantic_digest")):
                connection.close()
                return {"status": "NOT_AVAILABLE"}
            namespace = manifest["snapshot_namespace_id"]
            keys = getattr(ports, "keys", None) or getattr(ports, "tenant_keys", None)
            namespace_payload = _canonical(["X10_USER_INPUT_NAMESPACE_V1", manifest["owner_scope_id"],
                manifest["session_locator_id"], manifest["upload_locator_id"], manifest["raw_byte_sha256"],
                manifest["parser_config_sha256"]])
            expected_namespace = _hmac_port(keys, "namespace_hmac", namespace_payload, scope=scope)
            if expected_namespace != namespace or namespace != snapshot_handle.snapshot_namespace_id:
                connection.close()
                return {"status": "NOT_AVAILABLE"}
            for sid,kind,natural_json in connection.execute(
                "SELECT subject_id,subject_type,natural_key_json FROM user_input_subjects ORDER BY subject_type,subject_id"
            ):
                natural=json.loads(natural_json)
                expected_subject = _hmac_port(keys, "namespace_hmac",
                    _canonical([namespace,kind,natural]), scope=scope)
                if expected_subject != sid:
                    connection.close()
                    return {"status": "NOT_AVAILABLE"}
            stored_graph = _graph_digest_from_connection(namespace, connection)
            counts = {
                "subject_count":connection.execute("SELECT COUNT(*) FROM user_input_subjects").fetchone()[0],
                "edge_count":connection.execute("SELECT COUNT(*) FROM user_input_subject_edges").fetchone()[0],
            }
            parse_row = connection.execute("SELECT midi_format,division,track_count,event_count,note_count,parser_version,parser_config_sha256,parse_invocation_count FROM user_input_parse_manifests").fetchone()
            authority = connection.execute("SELECT evidence_authority,model_authority,training_eligibility,midi_output FROM snapshot_authority_policy").fetchone()
            digest_row = connection.execute("SELECT semantic_digest,subject_graph_sha256 FROM snapshot_semantic_digest").fetchone()
            content_id=sha256(_canonical(["X10_USER_INPUT_CONTENT_V1",manifest["raw_byte_sha256"],manifest["raw_byte_count"]])).hexdigest()
            artifact_row=connection.execute("SELECT snapshot_id,raw_sha256,raw_byte_count,content_id,authority_domain FROM user_input_artifacts").fetchone()
            origin_row=connection.execute("SELECT snapshot_id,owner_scope_id,session_locator_id,upload_locator_id,origin_trust FROM user_input_origins").fetchone()
            classification_row=connection.execute("SELECT snapshot_id,source_class,guard_policy_digest,status FROM user_input_source_classification").fetchone()
            singleton_counts=[connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in
                ("snapshot_runs","user_input_artifacts","user_input_origins","user_input_source_classification",
                 "user_input_parse_manifests","snapshot_authority_policy","snapshot_semantic_digest")]
            connection.close()
            rebuild,event_count,note_count = _build_graph(midi,namespace,key_slot["key_id"],payload_key,keys,scope,
                                                          frozen.limits,deadline=deadline)
            rebuilt_graph = _graph_digest(namespace,rebuild)
            expected_parse=(int(midi.format),int(midi.division),len(midi.tracks),event_count,note_count,
                            frozen.parser_version,frozen.parser_config_sha256,1)
            if (stored_graph != manifest["subject_graph_sha256"] or rebuilt_graph != stored_graph
                or counts["subject_count"] != manifest["subject_count"] or counts["edge_count"] != manifest["edge_count"]
                or rebuild.subject_count != counts["subject_count"] or rebuild.edge_count != counts["edge_count"]
                or rebuild.peak_batch != manifest["peak_graph_batch"] or not 0<=manifest["peak_graph_batch"]<=frozen.limits.max_peak_event_batch
                or parse_row != expected_parse or digest_row != (semantic,stored_graph)
                or artifact_row != (manifest["snapshot_id"],manifest["raw_byte_sha256"],manifest["raw_byte_count"],content_id,AUTHORITY_DOMAIN)
                or origin_row != (manifest["snapshot_id"],manifest["owner_scope_id"],manifest["session_locator_id"],manifest["upload_locator_id"],ORIGIN_TRUST)
                or classification_row != (manifest["snapshot_id"],SOURCE_CLASS,manifest["guard_policy_digest"],"SNAPSHOT_ACCEPTED_USER_INPUT")
                or any(count!=1 for count in singleton_counts)
                or authority != ("NONE","NONE","NEVER","NONE")):
                return {"status": "NOT_AVAILABLE"}
            return {"status": "FULL_RAW_AND_GRAPH_VERIFIED"}
        finally:
            registry.release_lease(lease)
    except Exception:
        return {"status": "NOT_AVAILABLE"}
    finally:
        if rebuild is not None: rebuild.close()


def request_user_input_snapshot_purge(ports: Any, auth_handle: Any, snapshot_handle: SnapshotHandle) -> Mapping[str, str]:
    try:
        scope = _verify_auth(ports, auth_handle, "PURGE")
        if (_scope_value(scope, "owner_scope_id"), _scope_value(scope, "session_locator_id"),
            _scope_value(scope, "upload_locator_id")) != (snapshot_handle.owner_scope_id,
                                                            snapshot_handle.session_locator_id,
                                                            snapshot_handle.upload_locator_id):
            return {"status": "NOT_AVAILABLE"}
        registry = getattr(ports, "registry", None) or getattr(ports, "operational_registry", None)
        package = getattr(ports, "packages", None) or getattr(ports, "package_store", None)
        locator = CompositeSnapshotKey(snapshot_handle.owner_scope_id, snapshot_handle.session_locator_id,
                                       snapshot_handle.upload_locator_id, snapshot_handle.snapshot_instance_id)
        result = registry.request_purge(scope, locator)
        if result.ready_for_quarantine:
            registry.move_to_quarantine(locator)
            package.quarantine(locator)
        return {"status": result.state.value}
    except Exception:
        return {"status": "NOT_AVAILABLE"}


def run_user_input_purge_sweeper(ports: Any) -> Mapping[str, int | str]:
    """Idempotently quarantine/delete every registry item ready for physical purge."""
    registry = getattr(ports, "registry", None) or getattr(ports, "operational_registry", None)
    package = getattr(ports, "packages", None) or getattr(ports, "package_store", None)
    if registry is None or package is None:
        return {"status": "INTERNAL_OPERATION_FAILED", "purged": 0}
    purged = 0
    try:
        for locator in registry.recover():
            registry.move_to_quarantine(locator)
            package.quarantine(locator)
            registry.mark_physical_purge_pending(locator)
            package.delete_quarantine(locator)
            reconciled = package.reconcile_absent(locator)
            if not reconciled:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            quota = getattr(ports,"session_quota",None)
            generation=registry.payload_key_generation(locator)
            keys=getattr(ports,"tenant_keys",None) or getattr(ports,"keys",None)
            keys.destroy_snapshot_payload_key(locator,generation)
            registry.mark_payload_key_destroyed(locator)
            if quota is not None: quota.release_snapshot(locator)
            registry.finish_purge(locator, inventory_reconciled=reconciled)
            purged += 1
        return {"status": "OK", "purged": purged}
    except Exception:
        return {"status": "INTERNAL_OPERATION_FAILED", "purged": purged}


__all__ = [
    "AcceptedSnapshot", "DEFAULT_LIMITS", "ExclusionReceipt", "FrozenSourceGuardPolicy", "PublicFailure",
    "SnapshotHandle", "UserInputLimits", "create_user_input_snapshot", "request_user_input_snapshot_purge",
    "run_user_input_purge_sweeper", "verify_user_input_snapshot",
]