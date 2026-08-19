"""Private USER_INPUT storage contracts for WP-X10-013B.

This module deliberately contains no application adapter.  Production callers must
inject every trust-bearing port.  The concrete adapters in this file are marked
``SYNTHETIC_TEST_ONLY`` and reject production construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import multiprocessing
import re
import secrets
import shutil
import stat
import tempfile
import threading
import time
from types import MappingProxyType
from typing import BinaryIO, Iterable, Iterator, Mapping, Protocol, runtime_checkable


CONTRACT_VERSION = "X10_USER_INPUT_STORE_V1"
SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_MEMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class PublicErrorCode(str, Enum):
    NOT_AVAILABLE = "NOT_AVAILABLE"
    INVALID_OR_UNSUPPORTED_MIDI = "INVALID_OR_UNSUPPORTED_MIDI"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    UPLOAD_CAPABILITY_REJECTED = "UPLOAD_CAPABILITY_REJECTED"
    LOCATOR_CONTENT_CONFLICT = "LOCATOR_CONTENT_CONFLICT"
    POLICY_REJECTED = "POLICY_REJECTED"
    OPERATION_IN_PROGRESS = "OPERATION_IN_PROGRESS"
    INTERNAL_OPERATION_FAILED = "INTERNAL_OPERATION_FAILED"
    PLATFORM_CAPABILITY_UNAVAILABLE = "PLATFORM_CAPABILITY_UNAVAILABLE"


class StoreContractError(Exception):
    """Sanitized public failure.  Details are intentionally not retained."""

    def __init__(self, code: PublicErrorCode):
        self.code = PublicErrorCode(code)
        super().__init__(self.code.value)


class Operation(str, Enum):
    CREATE = "CREATE"
    GET = "GET"
    LIST = "LIST"
    VERIFY = "VERIFY"
    LEASE = "LEASE"
    PURGE = "PURGE"


class LifecycleState(str, Enum):
    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    PURGE_REQUESTED = "PURGE_REQUESTED"
    ACCESS_REVOKED = "ACCESS_REVOKED"
    PHYSICAL_PURGE_PENDING = "PHYSICAL_PURGE_PENDING"
    PURGED = "PURGED"
    BUILD_FAILED = "BUILD_FAILED"


class ReservationKind(str, Enum):
    NEW = "NEW"
    RETRY = "RETRY"
    IDEMPOTENT = "IDEMPOTENT"
    IN_PROGRESS = "IN_PROGRESS"


def _validated_identifier(value: object) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
    return value


def _canonical(parts: Iterable[object]) -> bytes:
    return json.dumps(list(parts), ensure_ascii=True, separators=(",", ":")).encode("ascii")


@dataclass(frozen=True)
class VerifiedAuthorizationScope:
    owner_scope_id: str
    session_locator_id: str
    upload_locator_id: str
    authenticated_principal_binding: str
    allowed_operations: frozenset[Operation]
    _attestation: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_scope_id", _validated_identifier(self.owner_scope_id))
        object.__setattr__(self, "session_locator_id", _validated_identifier(self.session_locator_id))
        object.__setattr__(self, "upload_locator_id", _validated_identifier(self.upload_locator_id))
        _validated_identifier(self.authenticated_principal_binding)


@dataclass(frozen=True)
class SealedUploadRead:
    chunks: Iterator[bytes]
    seal_generation: str


@dataclass(frozen=True)
class CompositeSnapshotKey:
    owner_scope_id: str
    session_locator_id: str
    upload_locator_id: str
    snapshot_instance_id: str

    def __post_init__(self) -> None:
        for value in (
            self.owner_scope_id,
            self.session_locator_id,
            self.upload_locator_id,
            self.snapshot_instance_id,
        ):
            _validated_identifier(value)

    @property
    def locator_key(self) -> tuple[str, str, str]:
        return (self.owner_scope_id, self.session_locator_id, self.upload_locator_id)


@dataclass(frozen=True)
class ReservationIdentity:
    raw_sha256: str
    raw_byte_count: int
    policy_digest: str
    parser_digest: str
    seal_generation: str = field(compare=False, hash=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256):
            raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
        if self.raw_byte_count < 0:
            raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
        for value in (self.policy_digest, self.parser_digest, self.seal_generation):
            if not isinstance(value, str) or not value:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)


@dataclass(frozen=True)
class ReservationOutcome:
    kind: ReservationKind
    key: CompositeSnapshotKey
    state: LifecycleState
    generation_token: str


@dataclass(frozen=True)
class LeaseGrant:
    token: str
    key: CompositeSnapshotKey
    revocation_epoch: int


@dataclass(frozen=True)
class PurgeRequestResult:
    key: CompositeSnapshotKey
    state: LifecycleState
    revocation_epoch: int
    ready_for_quarantine: bool


@dataclass(frozen=True)
class PackageInventory:
    members: Mapping[str, tuple[int, str]]
    generation_digest: str


@dataclass(frozen=True)
class TrustedIngestContract:
    policy_digest: str
    parser_config_sha256: str
    parser_version: str
    limits_version: str
    limits: object
    six_song_sha256: frozenset[str]
    forbidden_sha256: frozenset[str]
    parser_callable: object = field(repr=False, compare=False)
    _attestation: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class QuotaReservation:
    token: str
    owner_scope_id: str
    session_locator_id: str


@dataclass(frozen=True)
class WatchdogLease:
    token: str
    phase: str
    deadline_monotonic: float = field(repr=False)


@runtime_checkable
class AuthorizationVerifierPort(Protocol):
    def verify(self, auth_handle: object, operation: Operation) -> VerifiedAuthorizationScope: ...


@runtime_checkable
class SealedUploadPort(Protocol):
    def stream_once(self, upload_handle: object, verified_scope: VerifiedAuthorizationScope) -> SealedUploadRead: ...


@runtime_checkable
class TenantKeyProviderPort(Protocol):
    @property
    def provider_version(self) -> str: ...
    def namespace_hmac(self, scope: VerifiedAuthorizationScope, payload: bytes) -> str: ...
    def new_snapshot_payload_key(self, scope: VerifiedAuthorizationScope) -> tuple[str, bytes]: ...
    def snapshot_payload_key(self, scope: VerifiedAuthorizationScope, generation_token: str) -> tuple[str, bytes]: ...
    def payload_hmac(self, key_id: str, key_material: bytes, payload: bytes) -> str: ...
    def audit_hmac(self, scope: VerifiedAuthorizationScope, payload: bytes) -> str: ...
    def destroy_snapshot_payload_key(self, key: CompositeSnapshotKey, generation_token: str) -> None: ...


@runtime_checkable
class OperationalRegistryPort(Protocol):
    def reserve(self, scope: VerifiedAuthorizationScope, identity: ReservationIdentity) -> ReservationOutcome: ...
    def finish_create(self, key: CompositeSnapshotKey, inventory_digest: str) -> None: ...
    def fail_create(self, key: CompositeSnapshotKey) -> None: ...
    def acquire_lease(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey) -> LeaseGrant: ...
    def validate_lease(self, grant: LeaseGrant) -> None: ...
    def release_lease(self, grant: LeaseGrant) -> bool: ...
    def request_purge(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey) -> PurgeRequestResult: ...
    def move_to_quarantine(self, key: CompositeSnapshotKey) -> None: ...
    def mark_physical_purge_pending(self, key: CompositeSnapshotKey) -> None: ...
    def payload_key_generation(self, key: CompositeSnapshotKey) -> str: ...
    def mark_payload_key_destroyed(self, key: CompositeSnapshotKey) -> None: ...
    def finish_purge(self, key: CompositeSnapshotKey, inventory_reconciled: bool) -> str: ...
    def recover(self) -> tuple[CompositeSnapshotKey, ...]: ...
    def get_state(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey) -> LifecycleState: ...
    def accepted_inventory_digest(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey) -> str: ...


@runtime_checkable
class PrivatePackageStorePort(Protocol):
    def create_stage(self, key: CompositeSnapshotKey) -> object: ...
    def write_private_member(self, stage: object, member_name: str, chunks: Iterable[bytes]) -> tuple[int, str]: ...
    def fsync_stage(self, stage: object) -> PackageInventory: ...
    def abort_stage(self, stage: object) -> None: ...
    def publish_generation(self, stage: object, key: CompositeSnapshotKey) -> PackageInventory: ...
    def open_active_read_only(self, key: CompositeSnapshotKey, member_name: str) -> BinaryIO: ...
    def quarantine(self, key: CompositeSnapshotKey) -> None: ...
    def delete_quarantine(self, key: CompositeSnapshotKey) -> None: ...
    def inventory(self, key: CompositeSnapshotKey, *, quarantine: bool = False) -> PackageInventory: ...
    def reconcile_absent(self, key: CompositeSnapshotKey) -> bool: ...


@runtime_checkable
class TrustedIngestContractPort(Protocol):
    def resolve(self, scope: VerifiedAuthorizationScope) -> TrustedIngestContract: ...
    def owns(self, contract: TrustedIngestContract) -> bool: ...


@runtime_checkable
class SessionRetainedQuotaPort(Protocol):
    def begin(self, scope: VerifiedAuthorizationScope) -> QuotaReservation: ...
    def consume(self, reservation: QuotaReservation, delta_bytes: int) -> None: ...
    def commit(self, reservation: QuotaReservation, key: CompositeSnapshotKey, retained_bytes: int) -> None: ...
    def abort(self, reservation: QuotaReservation) -> None: ...
    def release_snapshot(self, key: CompositeSnapshotKey) -> None: ...


@runtime_checkable
class TrustedWatchdogPort(Protocol):
    def start(self, scope: VerifiedAuthorizationScope, phase: str, max_seconds: int) -> WatchdogLease: ...
    def checkpoint(self, lease: WatchdogLease) -> None: ...
    def finish(self, lease: WatchdogLease) -> None: ...


@runtime_checkable
class TrustedParserExecutorPort(Protocol):
    def execute(
        self,
        scope: VerifiedAuthorizationScope,
        contract: TrustedIngestContract,
        raw: bytes,
        timeout_seconds: int,
    ) -> object: ...


@dataclass(frozen=True)
class StorePorts:
    authorization: AuthorizationVerifierPort
    sealed_upload: SealedUploadPort
    tenant_keys: TenantKeyProviderPort
    registry: OperationalRegistryPort
    packages: PrivatePackageStorePort
    ingest_contracts: TrustedIngestContractPort
    session_quota: SessionRetainedQuotaPort
    watchdog: TrustedWatchdogPort
    parser_executor: TrustedParserExecutorPort


def require_production_ports(ports: StorePorts | None) -> StorePorts:
    """Reject absent or explicitly synthetic ports; there is no local fallback."""
    if ports is None:
        raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
    required = (ports.authorization, ports.sealed_upload, ports.tenant_keys, ports.registry, ports.packages,
                ports.ingest_contracts, ports.session_quota, ports.watchdog)
    required = required + (ports.parser_executor,)
    if any(getattr(port, "adapter_class", None) == SYNTHETIC_TEST_ONLY for port in required):
        raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
    return ports


@dataclass(frozen=True)
class _SyntheticAuthHandle:
    token: str


class SyntheticAuthorizationVerifier:
    adapter_class = SYNTHETIC_TEST_ONLY

    def __init__(self) -> None:
        self.__seal = object()
        self.__handles: dict[str, tuple[str, str, str, str, frozenset[Operation]]] = {}

    def issue(
        self,
        owner_scope_id: str,
        session_locator_id: str,
        upload_locator_id: str,
        operations: Iterable[Operation] = tuple(Operation),
    ) -> _SyntheticAuthHandle:
        owner = _validated_identifier(owner_scope_id)
        session = _validated_identifier(session_locator_id)
        upload = _validated_identifier(upload_locator_id)
        token = secrets.token_urlsafe(32)
        principal = secrets.token_urlsafe(24)
        self.__handles[token] = (owner, session, upload, principal, frozenset(operations))
        return _SyntheticAuthHandle(token)

    def verify(self, auth_handle: object, operation: Operation) -> VerifiedAuthorizationScope:
        if type(auth_handle) is not _SyntheticAuthHandle:
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        record = self.__handles.get(auth_handle.token)
        if record is None or Operation(operation) not in record[4]:
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        return VerifiedAuthorizationScope(*record, _attestation=self.__seal)

    def owns(self, scope: VerifiedAuthorizationScope) -> bool:
        return scope._attestation is self.__seal


@dataclass(frozen=True)
class _SyntheticUploadHandle:
    token: str


class SyntheticSealedUploadPort:
    adapter_class = SYNTHETIC_TEST_ONLY

    def __init__(self, authorization: SyntheticAuthorizationVerifier) -> None:
        self._authorization = authorization
        self._uploads: dict[str, tuple[tuple[str, str, str], bytes, str, bool]] = {}

    def seal(self, auth_handle: object, payload: bytes) -> _SyntheticUploadHandle:
        scope = self._authorization.verify(auth_handle, Operation.CREATE)
        token = secrets.token_urlsafe(32)
        generation = secrets.token_urlsafe(24)
        locator = (scope.owner_scope_id, scope.session_locator_id, scope.upload_locator_id)
        self._uploads[token] = (locator, bytes(payload), generation, False)
        return _SyntheticUploadHandle(token)

    def stream_once(self, upload_handle: object, verified_scope: VerifiedAuthorizationScope) -> SealedUploadRead:
        if not self._authorization.owns(verified_scope) or type(upload_handle) is not _SyntheticUploadHandle:
            raise StoreContractError(PublicErrorCode.UPLOAD_CAPABILITY_REJECTED)
        record = self._uploads.get(upload_handle.token)
        expected = (verified_scope.owner_scope_id, verified_scope.session_locator_id, verified_scope.upload_locator_id)
        if record is None or record[0] != expected or record[3]:
            raise StoreContractError(PublicErrorCode.UPLOAD_CAPABILITY_REJECTED)
        self._uploads[upload_handle.token] = (record[0], record[1], record[2], True)

        def chunks() -> Iterator[bytes]:
            view = memoryview(record[1])
            for offset in range(0, len(view), 65536):
                yield bytes(view[offset : offset + 65536])

        return SealedUploadRead(chunks(), record[2])


class SyntheticTenantKeyProvider:
    adapter_class = SYNTHETIC_TEST_ONLY
    provider_version = "SYNTHETIC_TENANT_KEYS_V1"

    def __init__(self) -> None:
        self._identity: dict[str, bytes] = {}
        self._audit: dict[str, bytes] = {}
        self._payload_generations: dict[tuple[str, str], tuple[str, bytes]] = {}
        self._destroyed_payload_generations: set[tuple[str, str]] = set()

    def _key(self, mapping: dict[str, bytes], owner: str) -> bytes:
        return mapping.setdefault(owner, secrets.token_bytes(32))

    def namespace_hmac(self, scope: VerifiedAuthorizationScope, payload: bytes) -> str:
        return hmac.new(self._key(self._identity, scope.owner_scope_id), payload, hashlib.sha256).hexdigest()

    def new_snapshot_payload_key(self, scope: VerifiedAuthorizationScope) -> tuple[str, bytes]:
        del scope
        return ("SYNTHETIC_PAYLOAD_KEY_V1:" + secrets.token_urlsafe(18), secrets.token_bytes(32))

    def snapshot_payload_key(self, scope: VerifiedAuthorizationScope, generation_token: str) -> tuple[str, bytes]:
        _validated_identifier(generation_token)
        identity = (scope.owner_scope_id, generation_token)
        if identity in self._destroyed_payload_generations:
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        if identity not in self._payload_generations:
            self._payload_generations[identity] = self.new_snapshot_payload_key(scope)
        return self._payload_generations[identity]

    def destroy_snapshot_payload_key(self, key: CompositeSnapshotKey, generation_token: str) -> None:
        _validated_identifier(generation_token)
        identity = (key.owner_scope_id, generation_token)
        self._payload_generations.pop(identity, None)
        self._destroyed_payload_generations.add(identity)

    def payload_hmac(self, key_id: str, key_material: bytes, payload: bytes) -> str:
        if not key_id.startswith("SYNTHETIC_PAYLOAD_KEY_V1:") or len(key_material) != 32:
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        return hmac.new(key_material, payload, hashlib.sha256).hexdigest()

    def audit_hmac(self, scope: VerifiedAuthorizationScope, payload: bytes) -> str:
        return hmac.new(self._key(self._audit, scope.owner_scope_id), payload, hashlib.sha256).hexdigest()


class SyntheticTrustedIngestContractPort:
    adapter_class = SYNTHETIC_TEST_ONLY

    def __init__(self) -> None:
        self.__seal = object()
        self._contract: TrustedIngestContract | None = None

    def configure(
        self,
        *,
        policy_digest: str,
        parser_config_sha256: str,
        parser_version: str,
        limits_version: str,
        limits: object,
        six_song_sha256: Iterable[str],
        forbidden_sha256: Iterable[str],
        parser_callable: object,
    ) -> None:
        six = frozenset(six_song_sha256)
        forbidden = frozenset(forbidden_sha256)
        if len(six) != 6 or not callable(parser_callable):
            raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
        if any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in six | forbidden):
            raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
        self._contract = TrustedIngestContract(
            policy_digest,
            parser_config_sha256,
            parser_version,
            limits_version,
            limits,
            six,
            forbidden,
            parser_callable,
            self.__seal,
        )

    def resolve(self, scope: VerifiedAuthorizationScope) -> TrustedIngestContract:
        del scope
        if self._contract is None:
            raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
        return self._contract

    def owns(self, contract: TrustedIngestContract) -> bool:
        return contract._attestation is self.__seal


@dataclass
class _QuotaRecord:
    owner: str
    session: str
    consumed: int = 0
    committed_credit: int = 0


class SyntheticSessionRetainedQuota:
    adapter_class = SYNTHETIC_TEST_ONLY

    def __init__(self, authorization: SyntheticAuthorizationVerifier, max_session_retained_bytes: int = 536_870_912) -> None:
        self._authorization = authorization
        self._maximum = max_session_retained_bytes
        self._lock = threading.RLock()
        self._pending: dict[str, _QuotaRecord] = {}
        self._snapshots: dict[CompositeSnapshotKey, int] = {}

    def _session_total(self, owner: str, session: str, *, excluding: str | None = None) -> int:
        retained = sum(size for key, size in self._snapshots.items() if key.owner_scope_id == owner and key.session_locator_id == session)
        pending = sum(max(0, record.consumed - record.committed_credit) for token, record in self._pending.items()
                      if token != excluding and record.owner == owner and record.session == session)
        return retained + pending

    def begin(self, scope: VerifiedAuthorizationScope) -> QuotaReservation:
        if not self._authorization.owns(scope):
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        token = secrets.token_urlsafe(24)
        with self._lock:
            credit = sum(
                size for key, size in self._snapshots.items()
                if key.owner_scope_id == scope.owner_scope_id
                and key.session_locator_id == scope.session_locator_id
                and key.upload_locator_id == scope.upload_locator_id
            )
            self._pending[token] = _QuotaRecord(scope.owner_scope_id, scope.session_locator_id, committed_credit=credit)
        return QuotaReservation(token, scope.owner_scope_id, scope.session_locator_id)

    def consume(self, reservation: QuotaReservation, delta_bytes: int) -> None:
        if not isinstance(delta_bytes, int) or delta_bytes < 0:
            raise StoreContractError(PublicErrorCode.RESOURCE_LIMIT_EXCEEDED)
        with self._lock:
            record = self._pending.get(reservation.token)
            if record is None or (record.owner, record.session) != (reservation.owner_scope_id, reservation.session_locator_id):
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            proposed = record.consumed + delta_bytes
            effective = max(0, proposed - record.committed_credit)
            if self._session_total(record.owner, record.session, excluding=reservation.token) + effective > self._maximum:
                raise StoreContractError(PublicErrorCode.RESOURCE_LIMIT_EXCEEDED)
            record.consumed = proposed

    def commit(self, reservation: QuotaReservation, key: CompositeSnapshotKey, retained_bytes: int) -> None:
        with self._lock:
            record = self._pending.get(reservation.token)
            if record is None or key.owner_scope_id != record.owner or key.session_locator_id != record.session:
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            existing = self._snapshots.get(key)
            if existing is not None and existing != retained_bytes:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            if existing == retained_bytes:
                self._pending.pop(reservation.token, None)
                return
            if retained_bytes < 0 or self._session_total(record.owner, record.session, excluding=reservation.token) + retained_bytes > self._maximum:
                raise StoreContractError(PublicErrorCode.RESOURCE_LIMIT_EXCEEDED)
            self._snapshots[key] = retained_bytes
            self._pending.pop(reservation.token, None)

    def abort(self, reservation: QuotaReservation) -> None:
        with self._lock:
            self._pending.pop(reservation.token, None)

    def release_snapshot(self, key: CompositeSnapshotKey) -> None:
        with self._lock:
            self._snapshots.pop(key, None)


class SyntheticTrustedWatchdog:
    adapter_class = SYNTHETIC_TEST_ONLY

    def __init__(self, authorization: SyntheticAuthorizationVerifier, clock=time.monotonic) -> None:
        self._authorization = authorization
        self._clock = clock
        self._active: set[str] = set()

    def start(self, scope: VerifiedAuthorizationScope, phase: str, max_seconds: int) -> WatchdogLease:
        if not self._authorization.owns(scope) or not phase or max_seconds <= 0:
            raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
        token = secrets.token_urlsafe(24)
        self._active.add(token)
        return WatchdogLease(token, phase, self._clock() + max_seconds)

    def checkpoint(self, lease: WatchdogLease) -> None:
        if lease.token not in self._active:
            raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
        if self._clock() > lease.deadline_monotonic:
            self._active.discard(lease.token)
            raise StoreContractError(PublicErrorCode.RESOURCE_LIMIT_EXCEEDED)

    def finish(self, lease: WatchdogLease) -> None:
        self._active.discard(lease.token)


def _synthetic_parser_worker(connection, parser, raw: bytes) -> None:
    try:
        connection.send(("OK", parser(raw)))
    except BaseException as exc:  # child boundary intentionally reduces exception detail
        connection.send(("ERROR", type(exc).__name__))
    finally:
        connection.close()


class SyntheticTrustedParserExecutor:
    """Killable process executor used only by synthetic contract tests."""

    adapter_class = SYNTHETIC_TEST_ONLY

    def __init__(
        self,
        authorization: SyntheticAuthorizationVerifier,
        contracts: SyntheticTrustedIngestContractPort,
        *,
        timeout_cap_seconds: float | None = None,
    ) -> None:
        self._authorization = authorization
        self._contracts = contracts
        self.timeout_cap_seconds = timeout_cap_seconds

    def execute(
        self,
        scope: VerifiedAuthorizationScope,
        contract: TrustedIngestContract,
        raw: bytes,
        timeout_seconds: int,
    ) -> object:
        if (
            not self._authorization.owns(scope)
            or not self._contracts.owns(contract)
            or not callable(contract.parser_callable)
            or timeout_seconds <= 0
        ):
            raise StoreContractError(PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE)
        timeout = float(timeout_seconds)
        if self.timeout_cap_seconds is not None:
            timeout = min(timeout, float(self.timeout_cap_seconds))
        if timeout <= 0:
            raise StoreContractError(PublicErrorCode.RESOURCE_LIMIT_EXCEEDED)
        methods = multiprocessing.get_all_start_methods()
        context = multiprocessing.get_context("fork" if "fork" in methods else methods[0])
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=_synthetic_parser_worker, args=(child, contract.parser_callable, bytes(raw)))
        process.daemon = True
        process.start()
        child.close()
        try:
            if not parent.poll(timeout):
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive() and hasattr(process, "kill"):
                    process.kill()
                    process.join(timeout=1.0)
                raise StoreContractError(PublicErrorCode.RESOURCE_LIMIT_EXCEEDED)
            status, value = parent.recv()
            process.join(timeout=1.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
                raise StoreContractError(PublicErrorCode.RESOURCE_LIMIT_EXCEEDED)
            if status != "OK":
                raise StoreContractError(PublicErrorCode.INVALID_OR_UNSUPPORTED_MIDI)
            return value
        finally:
            parent.close()
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)


@dataclass
class _RegistryRecord:
    key: CompositeSnapshotKey
    identity: ReservationIdentity | None
    state: LifecycleState = LifecycleState.CREATING
    inventory_digest: str | None = None
    revocation_epoch: int = 0
    leases: dict[str, int] = field(default_factory=dict)
    generation_token: str | None = field(default_factory=lambda: secrets.token_urlsafe(24))
    payload_key_destroyed: bool = False
    purge_receipt_id: str | None = None


class SyntheticOperationalRegistry:
    adapter_class = SYNTHETIC_TEST_ONLY

    def __init__(self, authorization: SyntheticAuthorizationVerifier) -> None:
        self._authorization = authorization
        self._lock = threading.RLock()
        self._records: dict[tuple[str, str, str], _RegistryRecord] = {}
        self._purge_audit_key = secrets.token_bytes(32)

    def _authorized(self, scope: VerifiedAuthorizationScope, operation: Operation) -> tuple[str, str, str]:
        if not self._authorization.owns(scope) or operation not in scope.allowed_operations:
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        return (scope.owner_scope_id, scope.session_locator_id, scope.upload_locator_id)

    def _record_for(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey, operation: Operation) -> _RegistryRecord:
        locator = self._authorized(scope, operation)
        if key.locator_key != locator:
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        record = self._records.get(locator)
        if record is None or record.key != key:
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        return record

    def reserve(self, scope: VerifiedAuthorizationScope, identity: ReservationIdentity) -> ReservationOutcome:
        locator = self._authorized(scope, Operation.CREATE)
        with self._lock:
            current = self._records.get(locator)
            if current is not None:
                if current.identity != identity:
                    raise StoreContractError(PublicErrorCode.LOCATOR_CONTENT_CONFLICT)
                if current.state is LifecycleState.PURGED:
                    raise StoreContractError(PublicErrorCode.LOCATOR_CONTENT_CONFLICT)
                if current.generation_token is None:
                    raise StoreContractError(PublicErrorCode.LOCATOR_CONTENT_CONFLICT)
                if current.state is LifecycleState.BUILD_FAILED:
                    current.state = LifecycleState.CREATING
                    return ReservationOutcome(ReservationKind.RETRY, current.key, current.state, current.generation_token)
                kind = ReservationKind.IN_PROGRESS if current.state is LifecycleState.CREATING else ReservationKind.IDEMPOTENT
                if current.state is LifecycleState.CREATING:
                    kind = ReservationKind.RETRY
                return ReservationOutcome(kind, current.key, current.state, current.generation_token)
            instance = secrets.token_urlsafe(24)
            key = CompositeSnapshotKey(*locator, instance)
            self._records[locator] = _RegistryRecord(key=key, identity=identity)
            record = self._records[locator]
            return ReservationOutcome(ReservationKind.NEW, key, LifecycleState.CREATING, record.generation_token)

    def finish_create(self, key: CompositeSnapshotKey, inventory_digest: str) -> None:
        with self._lock:
            record = self._records.get(key.locator_key)
            if record is None or record.key != key:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            if record.state is LifecycleState.ACTIVE:
                if record.inventory_digest != inventory_digest:
                    raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
                return
            if record.state is not LifecycleState.CREATING:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            record.inventory_digest = inventory_digest
            record.state = LifecycleState.ACTIVE

    def fail_create(self, key: CompositeSnapshotKey) -> None:
        with self._lock:
            record = self._records.get(key.locator_key)
            if record is not None and record.key == key and record.state is LifecycleState.CREATING:
                record.state = LifecycleState.BUILD_FAILED

    def acquire_lease(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey) -> LeaseGrant:
        with self._lock:
            record = self._record_for(scope, key, Operation.LEASE)
            if record.state is not LifecycleState.ACTIVE:
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            token = secrets.token_urlsafe(32)
            record.leases[token] = record.revocation_epoch
            return LeaseGrant(token, key, record.revocation_epoch)

    def validate_lease(self, grant: LeaseGrant) -> None:
        with self._lock:
            record = self._records.get(grant.key.locator_key)
            if (
                record is None
                or record.key != grant.key
                or record.state is not LifecycleState.ACTIVE
                or record.revocation_epoch != grant.revocation_epoch
                or record.leases.get(grant.token) != grant.revocation_epoch
            ):
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)

    def release_lease(self, grant: LeaseGrant) -> bool:
        with self._lock:
            record = self._records.get(grant.key.locator_key)
            if record is None or record.key != grant.key:
                return False
            record.leases.pop(grant.token, None)
            return record.state is LifecycleState.PURGE_REQUESTED and not record.leases

    def request_purge(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey) -> PurgeRequestResult:
        with self._lock:
            record = self._record_for(scope, key, Operation.PURGE)
            if record.state is LifecycleState.ACTIVE:
                record.state = LifecycleState.PURGE_REQUESTED
                record.revocation_epoch += 1
            elif record.state not in {
                LifecycleState.PURGE_REQUESTED,
                LifecycleState.ACCESS_REVOKED,
                LifecycleState.PHYSICAL_PURGE_PENDING,
                LifecycleState.PURGED,
            }:
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            return PurgeRequestResult(
                key,
                record.state,
                record.revocation_epoch,
                record.state is LifecycleState.PURGE_REQUESTED and not record.leases,
            )

    def move_to_quarantine(self, key: CompositeSnapshotKey) -> None:
        with self._lock:
            record = self._records.get(key.locator_key)
            if record is None or record.key != key:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            if record.state in {LifecycleState.ACCESS_REVOKED, LifecycleState.PHYSICAL_PURGE_PENDING}:
                return
            if record.state is not LifecycleState.PURGE_REQUESTED or record.leases:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            record.state = LifecycleState.ACCESS_REVOKED

    def mark_physical_purge_pending(self, key: CompositeSnapshotKey) -> None:
        with self._lock:
            record = self._records.get(key.locator_key)
            if record is None or record.key != key:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            if record.state is LifecycleState.PHYSICAL_PURGE_PENDING:
                return
            if record.state is not LifecycleState.ACCESS_REVOKED:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            record.state = LifecycleState.PHYSICAL_PURGE_PENDING

    def payload_key_generation(self, key: CompositeSnapshotKey) -> str:
        with self._lock:
            record = self._records.get(key.locator_key)
            if (
                record is None
                or record.key != key
                or record.state not in {LifecycleState.ACCESS_REVOKED, LifecycleState.PHYSICAL_PURGE_PENDING}
                or record.generation_token is None
            ):
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            return record.generation_token

    def mark_payload_key_destroyed(self, key: CompositeSnapshotKey) -> None:
        with self._lock:
            record = self._records.get(key.locator_key)
            if record is None or record.key != key or record.state is not LifecycleState.PHYSICAL_PURGE_PENDING:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            record.payload_key_destroyed = True

    def finish_purge(self, key: CompositeSnapshotKey, inventory_reconciled: bool) -> str:
        with self._lock:
            record = self._records.get(key.locator_key)
            if record is None or record.key != key:
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            if record.state is LifecycleState.PURGED:
                if record.purge_receipt_id is None:
                    raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
                return record.purge_receipt_id
            if not inventory_reconciled or record.state not in {
                LifecycleState.ACCESS_REVOKED,
                LifecycleState.PHYSICAL_PURGE_PENDING,
            }:
                record.state = LifecycleState.PHYSICAL_PURGE_PENDING
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            if not record.payload_key_destroyed:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            receipt = hmac.new(
                self._purge_audit_key,
                _canonical((CONTRACT_VERSION, key.locator_key, "PURGED")),
                hashlib.sha256,
            ).hexdigest()
            record.state = LifecycleState.PURGED
            record.inventory_digest = None
            record.identity = None
            record.generation_token = None
            record.payload_key_destroyed = False
            record.purge_receipt_id = receipt
            return receipt

    def recover(self) -> tuple[CompositeSnapshotKey, ...]:
        with self._lock:
            return tuple(
                record.key
                for record in self._records.values()
                if (
                    record.state in {LifecycleState.ACCESS_REVOKED, LifecycleState.PHYSICAL_PURGE_PENDING}
                    or (record.state is LifecycleState.PURGE_REQUESTED and not record.leases)
                )
            )

    def get_state(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey) -> LifecycleState:
        with self._lock:
            return self._record_for(scope, key, Operation.GET).state

    def accepted_inventory_digest(self, scope: VerifiedAuthorizationScope, key: CompositeSnapshotKey) -> str:
        with self._lock:
            record = self._record_for(scope, key, Operation.VERIFY)
            if record.state is not LifecycleState.ACTIVE or not record.inventory_digest:
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            return record.inventory_digest


@dataclass(frozen=True)
class _StageHandle:
    token: str
    path: Path = field(repr=False, compare=False)


class SyntheticPrivatePackageStore:
    """Filesystem-backed atomic package store exclusively for contract tests."""

    adapter_class = SYNTHETIC_TEST_ONLY
    _ALLOWED_MEMBERS = frozenset({"original_upload.bin", "snapshot.sqlite3", "private_manifest.json", "payload_key.slot"})

    def __init__(self, private_root: str | os.PathLike[str] | None = None) -> None:
        if private_root is None:
            private_root = tempfile.mkdtemp(prefix="x10-synthetic-private-")
        self._root = Path(private_root)
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._root, 0o700)
        self._staging = self._root / "staging"
        self._active = self._root / "active"
        self._quarantine = self._root / "quarantine"
        for directory in (self._staging, self._active, self._quarantine):
            directory.mkdir(mode=0o700, exist_ok=True)
        self._lock = threading.RLock()

    @staticmethod
    def _dirname(key: CompositeSnapshotKey) -> str:
        return hmac.new(b"synthetic-private-store", _canonical((CONTRACT_VERSION, *key.locator_key, key.snapshot_instance_id)), hashlib.sha256).hexdigest()

    def _member(self, base: Path, member_name: str) -> Path:
        if member_name not in self._ALLOWED_MEMBERS or not _MEMBER_RE.fullmatch(member_name):
            raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
        return base / member_name

    def create_stage(self, key: CompositeSnapshotKey) -> _StageHandle:
        del key
        with self._lock:
            token = secrets.token_urlsafe(24)
            path = self._staging / token
            path.mkdir(mode=0o700)
            self._fsync_directory(self._staging)
            return _StageHandle(token, path)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def write_private_member(self, stage: object, member_name: str, chunks: Iterable[bytes]) -> tuple[int, str]:
        if type(stage) is not _StageHandle or not stage.path.parent.samefile(self._staging):
            raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
        target = self._member(stage.path, member_name)
        digest = hashlib.sha256()
        count = 0
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(target, flags, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                for chunk in chunks:
                    if not isinstance(chunk, (bytes, bytearray, memoryview)):
                        raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
                    value = bytes(chunk)
                    stream.write(value)
                    digest.update(value)
                    count += len(value)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(fd)
        return count, digest.hexdigest()

    @staticmethod
    def _inventory_for(directory: Path) -> PackageInventory:
        members: dict[str, tuple[int, str]] = {}
        if not directory.is_dir() or directory.is_symlink():
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
        for member in sorted(directory.iterdir(), key=lambda item: item.name):
            if member.name not in SyntheticPrivatePackageStore._ALLOWED_MEMBERS:
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            info = member.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            data_hash = hashlib.sha256()
            size = 0
            with member.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    size += len(chunk)
                    data_hash.update(chunk)
            members[member.name] = (size, data_hash.hexdigest())
        generation = hashlib.sha256(_canonical((CONTRACT_VERSION, sorted(members.items())))).hexdigest()
        return PackageInventory(MappingProxyType(members), generation)

    def fsync_stage(self, stage: object) -> PackageInventory:
        if type(stage) is not _StageHandle:
            raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
        inventory = self._inventory_for(stage.path)
        fd = os.open(stage.path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return inventory

    def abort_stage(self, stage: object) -> None:
        if type(stage) is not _StageHandle:
            raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
        with self._lock:
            try:
                parent_matches = stage.path.parent.samefile(self._staging)
            except FileNotFoundError:
                return
            if not parent_matches:
                raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
            if stage.path.exists():
                shutil.rmtree(stage.path)

    def publish_generation(self, stage: object, key: CompositeSnapshotKey) -> PackageInventory:
        if type(stage) is not _StageHandle:
            raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
        with self._lock:
            inventory = self.fsync_stage(stage)
            target = self._active / self._dirname(key)
            if target.exists():
                existing = self._inventory_for(target)
                if existing != inventory:
                    raise StoreContractError(PublicErrorCode.INTERNAL_OPERATION_FAILED)
                shutil.rmtree(stage.path)
                return existing
            os.replace(stage.path, target)
            self._fsync_directory(self._active)
            self._fsync_directory(self._staging)
            return self._inventory_for(target)

    def open_active_read_only(self, key: CompositeSnapshotKey, member_name: str) -> BinaryIO:
        directory = self._active / self._dirname(key)
        path = self._member(directory, member_name)
        try:
            flags = os.O_RDONLY | (getattr(os, "O_NOFOLLOW", 0))
            fd = os.open(path, flags)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                os.close(fd)
                raise StoreContractError(PublicErrorCode.NOT_AVAILABLE)
            return os.fdopen(fd, "rb")
        except (OSError, ValueError) as exc:
            raise StoreContractError(PublicErrorCode.NOT_AVAILABLE) from None

    def quarantine(self, key: CompositeSnapshotKey) -> None:
        with self._lock:
            name = self._dirname(key)
            source = self._active / name
            target = self._quarantine / name
            if target.exists():
                return
            if not source.exists():
                return
            os.replace(source, target)
            self._fsync_directory(self._active)
            self._fsync_directory(self._quarantine)

    def delete_quarantine(self, key: CompositeSnapshotKey) -> None:
        with self._lock:
            target = self._quarantine / self._dirname(key)
            if target.exists():
                shutil.rmtree(target)
                self._fsync_directory(self._quarantine)

    def inventory(self, key: CompositeSnapshotKey, *, quarantine: bool = False) -> PackageInventory:
        root = self._quarantine if quarantine else self._active
        return self._inventory_for(root / self._dirname(key))

    def reconcile_absent(self, key: CompositeSnapshotKey) -> bool:
        name = self._dirname(key)
        return not (self._active / name).exists() and not (self._quarantine / name).exists()


def synthetic_store_ports() -> tuple[StorePorts, SyntheticAuthorizationVerifier]:
    """Create isolated test ports; never call this from production composition."""
    authorization = SyntheticAuthorizationVerifier()
    contracts = SyntheticTrustedIngestContractPort()
    try:
        from rxoptimizer.midi import parse_midi
        from rxoptimizer.user_input_snapshot import DEFAULT_LIMITS, LIMITS_VERSION

        contracts.configure(
            policy_digest="synthetic-policy-v1",
            parser_config_sha256=hashlib.sha256(b"synthetic-parser-config-v1").hexdigest(),
            parser_version="RXOPTIMIZER_MIDI_V1",
            limits_version=LIMITS_VERSION,
            limits=DEFAULT_LIMITS,
            six_song_sha256=(hashlib.sha256(f"synthetic-six-{index}".encode()).hexdigest() for index in range(6)),
            forbidden_sha256=(),
            parser_callable=parse_midi,
        )
    except ImportError:
        pass
    return (
        StorePorts(
            authorization=authorization,
            sealed_upload=SyntheticSealedUploadPort(authorization),
            tenant_keys=SyntheticTenantKeyProvider(),
            registry=SyntheticOperationalRegistry(authorization),
            packages=SyntheticPrivatePackageStore(),
            ingest_contracts=contracts,
            session_quota=SyntheticSessionRetainedQuota(authorization),
            watchdog=SyntheticTrustedWatchdog(authorization),
            parser_executor=SyntheticTrustedParserExecutor(authorization, contracts),
        ),
        authorization,
    )