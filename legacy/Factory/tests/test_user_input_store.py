from __future__ import annotations

import hashlib
import os
from pathlib import Path
import threading
import time

import pytest

from rxoptimizer.user_input_store import (
    CompositeSnapshotKey,
    LifecycleState,
    Operation,
    PublicErrorCode,
    ReservationIdentity,
    ReservationKind,
    StoreContractError,
    SyntheticAuthorizationVerifier,
    SyntheticOperationalRegistry,
    SyntheticPrivatePackageStore,
    SyntheticSealedUploadPort,
    SyntheticTenantKeyProvider,
    VerifiedAuthorizationScope,
    require_production_ports,
    synthetic_store_ports,
)


def ident(payload: bytes = b"midi") -> ReservationIdentity:
    return ReservationIdentity(
        hashlib.sha256(payload).hexdigest(),
        len(payload),
        "policy-v1",
        "parser-v1",
        "seal-v1",
    )


def ids(seed: str) -> str:
    return (seed + "_" * 32)[:24]


def scope_and_registry():
    auth = SyntheticAuthorizationVerifier()
    handle = auth.issue(ids("owner"), ids("session"), ids("upload"))
    scope = auth.verify(handle, Operation.CREATE)
    return auth, handle, scope, SyntheticOperationalRegistry(auth)


def test_production_factory_rejects_missing_and_synthetic_ports():
    with pytest.raises(StoreContractError) as error:
        require_production_ports(None)
    assert error.value.code is PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE
    ports, _ = synthetic_store_ports()
    with pytest.raises(StoreContractError) as error:
        require_production_ports(ports)
    assert error.value.code is PublicErrorCode.PLATFORM_CAPABILITY_UNAVAILABLE


def test_forged_scope_and_caller_built_handle_are_rejected():
    auth, handle, scope, registry = scope_and_registry()
    with pytest.raises(StoreContractError) as error:
        auth.verify({"token": handle.token}, Operation.CREATE)
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE

    forged = VerifiedAuthorizationScope(
        scope.owner_scope_id,
        scope.session_locator_id,
        scope.upload_locator_id,
        scope.authenticated_principal_binding,
        frozenset(Operation),
        object(),
    )
    with pytest.raises(StoreContractError) as error:
        registry.reserve(forged, ident())
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE


@pytest.mark.parametrize(
    "bad",
    ["short", "has/slash____________", "has\\slash___________", "white space________", "ü" * 16, "a" * 129],
)
def test_opaque_locator_validation_is_closed(bad):
    auth = SyntheticAuthorizationVerifier()
    with pytest.raises(StoreContractError) as error:
        auth.issue(bad, ids("session"), ids("upload"))
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE


def test_sealed_upload_is_owner_bound_and_one_read_only():
    auth = SyntheticAuthorizationVerifier()
    one = auth.issue(ids("owner1"), ids("session1"), ids("upload1"))
    two = auth.issue(ids("owner2"), ids("session2"), ids("upload2"))
    upload_port = SyntheticSealedUploadPort(auth)
    upload = upload_port.seal(one, b"abc" * 100_000)
    with pytest.raises(StoreContractError) as error:
        upload_port.stream_once(upload, auth.verify(two, Operation.CREATE))
    assert error.value.code is PublicErrorCode.UPLOAD_CAPABILITY_REJECTED

    read = upload_port.stream_once(upload, auth.verify(one, Operation.CREATE))
    assert b"".join(read.chunks) == b"abc" * 100_000
    assert read.seal_generation
    with pytest.raises(StoreContractError) as error:
        upload_port.stream_once(upload, auth.verify(one, Operation.CREATE))
    assert error.value.code is PublicErrorCode.UPLOAD_CAPABILITY_REJECTED


def test_tenant_keys_are_unlinkable_and_payload_keys_are_random():
    auth = SyntheticAuthorizationVerifier()
    one = auth.issue(ids("owner1"), ids("session1"), ids("upload1"))
    two = auth.issue(ids("owner2"), ids("session2"), ids("upload2"))
    s1 = auth.verify(one, Operation.CREATE)
    s2 = auth.verify(two, Operation.CREATE)
    keys = SyntheticTenantKeyProvider()
    payload = b"dictionary-friendly-secret"
    assert keys.namespace_hmac(s1, payload) != keys.namespace_hmac(s2, payload)
    key_id1, key1 = keys.new_snapshot_payload_key(s1)
    key_id2, key2 = keys.new_snapshot_payload_key(s1)
    assert (key_id1, key1) != (key_id2, key2)
    assert keys.payload_hmac(key_id1, key1, payload) != hashlib.sha256(payload).hexdigest()
    assert keys.audit_hmac(s1, payload) != keys.audit_hmac(s2, payload)


def test_same_locator_idempotency_conflict_and_no_recycle_after_purge():
    auth, handle, scope, registry = scope_and_registry()
    first = registry.reserve(scope, ident(b"one"))
    assert first.kind is ReservationKind.NEW
    retry_creating = registry.reserve(scope, ident(b"one"))
    assert retry_creating.kind is ReservationKind.RETRY
    assert retry_creating.generation_token == first.generation_token
    registry.finish_create(first.key, "inventory")
    assert registry.reserve(scope, ident(b"one")).kind is ReservationKind.IDEMPOTENT
    with pytest.raises(StoreContractError) as error:
        registry.reserve(scope, ident(b"two"))
    assert error.value.code is PublicErrorCode.LOCATOR_CONTENT_CONFLICT

    purging = registry.request_purge(auth.verify(handle, Operation.PURGE), first.key)
    assert purging.ready_for_quarantine
    registry.move_to_quarantine(first.key)
    registry.mark_physical_purge_pending(first.key)
    registry.mark_payload_key_destroyed(first.key)
    registry.finish_purge(first.key, True)
    assert registry.request_purge(auth.verify(handle, Operation.PURGE), first.key).state is LifecycleState.PURGED
    with pytest.raises(StoreContractError) as error:
        registry.reserve(scope, ident(b"one"))
    assert error.value.code is PublicErrorCode.LOCATOR_CONTENT_CONFLICT


def test_concurrent_reservation_has_single_instance():
    auth, _, scope, registry = scope_and_registry()
    barrier = threading.Barrier(8)
    outcomes = []

    def reserve():
        barrier.wait()
        outcomes.append(registry.reserve(scope, ident()))

    threads = [threading.Thread(target=reserve) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(result.kind is ReservationKind.NEW for result in outcomes) == 1
    assert len({result.key for result in outcomes}) == 1


def test_cross_owner_lookup_is_indistinguishable_from_missing():
    auth = SyntheticAuthorizationVerifier()
    owner1 = auth.issue(ids("owner1"), ids("session1"), ids("upload1"))
    owner2 = auth.issue(ids("owner2"), ids("session2"), ids("upload2"))
    registry = SyntheticOperationalRegistry(auth)
    scope1 = auth.verify(owner1, Operation.CREATE)
    result = registry.reserve(scope1, ident())
    registry.finish_create(result.key, "inventory")
    for key in (
        result.key,
        CompositeSnapshotKey(ids("owner2"), ids("session2"), ids("upload2"), ids("missing")),
    ):
        with pytest.raises(StoreContractError) as error:
            registry.get_state(auth.verify(owner2, Operation.GET), key)
        assert error.value.code is PublicErrorCode.NOT_AVAILABLE
        assert str(error.value) == "NOT_AVAILABLE"


def test_purge_revokes_existing_lease_and_prevents_new_lease():
    auth, handle, scope, registry = scope_and_registry()
    outcome = registry.reserve(scope, ident())
    registry.finish_create(outcome.key, "inventory")
    lease_scope = auth.verify(handle, Operation.LEASE)
    lease = registry.acquire_lease(lease_scope, outcome.key)
    registry.validate_lease(lease)
    request = registry.request_purge(auth.verify(handle, Operation.PURGE), outcome.key)
    assert not request.ready_for_quarantine
    with pytest.raises(StoreContractError) as error:
        registry.validate_lease(lease)
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE
    with pytest.raises(StoreContractError) as error:
        registry.acquire_lease(lease_scope, outcome.key)
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE
    assert registry.release_lease(lease)
    assert registry.recover() == (outcome.key,)
    registry.move_to_quarantine(outcome.key)
    assert registry.recover() == (outcome.key,)
    registry.mark_physical_purge_pending(outcome.key)
    registry.mark_payload_key_destroyed(outcome.key)
    assert registry.recover() == (outcome.key,)
    receipt = registry.finish_purge(outcome.key, True)
    assert len(receipt) == 64
    assert registry.finish_purge(outcome.key, True) == receipt


def test_build_failed_allows_only_same_identity_retry():
    _, _, scope, registry = scope_and_registry()
    result = registry.reserve(scope, ident())
    registry.fail_create(result.key)
    retry = registry.reserve(scope, ident())
    assert retry.kind is ReservationKind.RETRY
    assert retry.state is LifecycleState.CREATING
    assert retry.key == result.key
    registry.fail_create(result.key)
    with pytest.raises(StoreContractError) as error:
        registry.reserve(scope, ident(b"different"))
    assert error.value.code is PublicErrorCode.LOCATOR_CONTENT_CONFLICT


def test_seal_generation_is_nonsemantic_retry_identity():
    _, _, scope, registry = scope_and_registry()
    one = ident(b"same")
    first = registry.reserve(scope, one)
    registry.finish_create(first.key, "inventory")
    two = ReservationIdentity(one.raw_sha256, one.raw_byte_count, one.policy_digest, one.parser_digest, "new-sealed-handle")
    retry = registry.reserve(scope, two)
    assert retry.kind is ReservationKind.IDEMPOTENT
    assert retry.key == first.key
    assert retry.generation_token == first.generation_token


def test_generation_payload_key_reused_for_retry():
    auth, _, scope, registry = scope_and_registry()
    keys = SyntheticTenantKeyProvider()
    first = registry.reserve(scope, ident())
    retry = registry.reserve(scope, ident())
    assert keys.snapshot_payload_key(scope, first.generation_token) == keys.snapshot_payload_key(scope, retry.generation_token)


def test_session_quota_is_atomic_and_released_on_purge():
    from rxoptimizer.user_input_store import SyntheticSessionRetainedQuota

    auth, _, scope, registry = scope_and_registry()
    quota = SyntheticSessionRetainedQuota(auth, max_session_retained_bytes=10)
    reservation = quota.begin(scope)
    quota.consume(reservation, 6)
    key = registry.reserve(scope, ident()).key
    quota.commit(reservation, key, 8)
    retry_same_locator = quota.begin(scope)
    quota.consume(retry_same_locator, 8)
    quota.commit(retry_same_locator, key, 8)
    other_handle = auth.issue(scope.owner_scope_id, scope.session_locator_id, ids("upload2"))
    other_scope = auth.verify(other_handle, Operation.CREATE)
    second = quota.begin(other_scope)
    with pytest.raises(StoreContractError) as error:
        quota.consume(second, 3)
    assert error.value.code is PublicErrorCode.RESOURCE_LIMIT_EXCEEDED
    quota.abort(second)
    quota.release_snapshot(key)
    third = quota.begin(scope)
    quota.consume(third, 10)


def test_purge_recovery_finishes_when_package_already_absent(tmp_path):
    auth, handle, scope, registry = scope_and_registry()
    store = SyntheticPrivatePackageStore(tmp_path)
    outcome = registry.reserve(scope, ident())
    stage = store.create_stage(outcome.key)
    store.write_private_member(stage, "private_manifest.json", [b"{}"])
    inventory = store.publish_generation(stage, outcome.key)
    registry.finish_create(outcome.key, inventory.generation_digest)
    assert registry.request_purge(auth.verify(handle, Operation.PURGE), outcome.key).ready_for_quarantine
    registry.move_to_quarantine(outcome.key)
    store.quarantine(outcome.key)
    registry.mark_physical_purge_pending(outcome.key)
    store.delete_quarantine(outcome.key)
    assert store.reconcile_absent(outcome.key)
    assert registry.recover() == (outcome.key,)
    registry.mark_payload_key_destroyed(outcome.key)
    registry.finish_purge(outcome.key, store.reconcile_absent(outcome.key))
    assert registry.recover() == ()


def test_atomic_private_package_publish_inventory_and_quarantine(tmp_path):
    store = SyntheticPrivatePackageStore(tmp_path)
    key = CompositeSnapshotKey(ids("owner"), ids("session"), ids("upload"), ids("instance"))
    stage = store.create_stage(key)
    raw = b"raw-midi"
    store.write_private_member(stage, "original_upload.bin", [raw])
    store.write_private_member(stage, "snapshot.sqlite3", [b"sqlite"])
    store.write_private_member(stage, "private_manifest.json", [b"{}"])
    store.write_private_member(stage, "payload_key.slot", [b"private-key"])
    staged = store.fsync_stage(stage)
    published = store.publish_generation(stage, key)
    assert published == staged
    with store.open_active_read_only(key, "original_upload.bin") as stream:
        assert stream.read() == raw
    assert all(not Path(name).is_absolute() for name in published.members)
    store.quarantine(key)
    with pytest.raises(StoreContractError) as error:
        store.open_active_read_only(key, "original_upload.bin")
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE
    assert store.inventory(key, quarantine=True) == published
    store.delete_quarantine(key)
    with pytest.raises(StoreContractError):
        store.inventory(key, quarantine=True)


def test_abort_stage_is_idempotent_and_never_publishes(tmp_path):
    store = SyntheticPrivatePackageStore(tmp_path)
    key = CompositeSnapshotKey(ids("owner"), ids("session"), ids("upload"), ids("instance"))
    stage = store.create_stage(key)
    store.write_private_member(stage, "original_upload.bin", [b"private"])
    store.abort_stage(stage)
    store.abort_stage(stage)
    with pytest.raises(StoreContractError) as error:
        store.inventory(key)
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE


def test_package_rejects_path_url_output_and_duplicate_member(tmp_path):
    store = SyntheticPrivatePackageStore(tmp_path)
    key = CompositeSnapshotKey(ids("owner"), ids("session"), ids("upload"), ids("instance"))
    stage = store.create_stage(key)
    for name in ("../raw.mid", "/tmp/raw", "https://host/file", "output.mid", "song.midi"):
        with pytest.raises(StoreContractError) as error:
            store.write_private_member(stage, name, [b"x"])
        assert error.value.code is PublicErrorCode.INTERNAL_OPERATION_FAILED
    store.write_private_member(stage, "private_manifest.json", [b"{}"])
    with pytest.raises(FileExistsError):
        store.write_private_member(stage, "private_manifest.json", [b"other"])


def test_atomic_publish_refuses_generation_collision(tmp_path):
    store = SyntheticPrivatePackageStore(tmp_path)
    key = CompositeSnapshotKey(ids("owner"), ids("session"), ids("upload"), ids("instance"))
    first = store.create_stage(key)
    store.write_private_member(first, "private_manifest.json", [b"one"])
    accepted = store.publish_generation(first, key)
    second = store.create_stage(key)
    store.write_private_member(second, "private_manifest.json", [b"two"])
    with pytest.raises(StoreContractError) as error:
        store.publish_generation(second, key)
    assert error.value.code is PublicErrorCode.INTERNAL_OPERATION_FAILED
    assert store.inventory(key) == accepted


def test_error_contract_does_not_echo_sensitive_input():
    secret = "/private/path/secret.mid"
    auth = SyntheticAuthorizationVerifier()
    with pytest.raises(StoreContractError) as error:
        auth.issue(secret, ids("session"), ids("upload"))
    rendered = repr(error.value) + str(error.value)
    assert secret not in rendered
    assert "path" not in rendered.lower()


def test_trusted_ingest_contract_is_port_attested():
    from rxoptimizer.midi import parse_midi
    from rxoptimizer.user_input_store import SyntheticTrustedIngestContractPort

    auth, _, scope, _ = scope_and_registry()
    contracts = SyntheticTrustedIngestContractPort()
    contracts.configure(
        policy_digest="policy",
        parser_config_sha256="c" * 64,
        parser_version="parser-v1",
        limits_version="limits-v1",
        limits=object(),
        six_song_sha256=(hashlib.sha256(str(index).encode()).hexdigest() for index in range(6)),
        forbidden_sha256=(),
        parser_callable=parse_midi,
    )
    contract = contracts.resolve(scope)
    assert contracts.owns(contract)
    assert contract.parser_callable is parse_midi


def test_watchdog_fails_closed_after_deadline():
    from rxoptimizer.user_input_store import SyntheticTrustedWatchdog

    now = [10.0]
    auth, _, scope, _ = scope_and_registry()
    watchdog = SyntheticTrustedWatchdog(auth, clock=lambda: now[0])
    lease = watchdog.start(scope, "PARSE", 2)
    watchdog.checkpoint(lease)
    now[0] = 12.1
    with pytest.raises(StoreContractError) as error:
        watchdog.checkpoint(lease)
    assert error.value.code is PublicErrorCode.RESOURCE_LIMIT_EXCEEDED


def test_payload_key_destruction_is_idempotent_and_cannot_recreate():
    auth, handle, scope, registry = scope_and_registry()
    keys = SyntheticTenantKeyProvider()
    outcome = registry.reserve(scope, ident(b"private-midi"))
    generation = outcome.generation_token
    original = keys.snapshot_payload_key(scope, generation)
    registry.finish_create(outcome.key, "inventory")
    registry.request_purge(auth.verify(handle, Operation.PURGE), outcome.key)
    registry.move_to_quarantine(outcome.key)
    registry.mark_physical_purge_pending(outcome.key)
    keys.destroy_snapshot_payload_key(outcome.key, generation)
    keys.destroy_snapshot_payload_key(outcome.key, generation)
    with pytest.raises(StoreContractError) as error:
        keys.snapshot_payload_key(scope, generation)
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE
    assert original not in keys._payload_generations.values()
    registry.mark_payload_key_destroyed(outcome.key)
    registry.finish_purge(outcome.key, True)
    record = registry._records[outcome.key.locator_key]
    assert record.identity is None and record.generation_token is None
    assert ident(b"private-midi").raw_sha256 not in repr(record)
    assert "seal-v1" not in repr(record)


def test_finish_purge_refuses_before_durable_key_destruction_mark():
    auth, handle, scope, registry = scope_and_registry()
    outcome = registry.reserve(scope, ident())
    registry.finish_create(outcome.key, "inventory")
    registry.request_purge(auth.verify(handle, Operation.PURGE), outcome.key)
    registry.move_to_quarantine(outcome.key)
    registry.mark_physical_purge_pending(outcome.key)
    with pytest.raises(StoreContractError) as error:
        registry.finish_purge(outcome.key, True)
    assert error.value.code is PublicErrorCode.INTERNAL_OPERATION_FAILED
    assert registry.recover() == (outcome.key,)


def test_killable_parser_executor_returns_before_hanging_parser():
    from rxoptimizer.user_input_store import SyntheticTrustedIngestContractPort, SyntheticTrustedParserExecutor

    auth, _, scope, _ = scope_and_registry()
    contracts = SyntheticTrustedIngestContractPort()

    def hangs(_raw):
        while True:
            time.sleep(1)

    contracts.configure(
        policy_digest="policy",
        parser_config_sha256="c" * 64,
        parser_version="parser-v1",
        limits_version="limits-v1",
        limits=object(),
        six_song_sha256=(hashlib.sha256(str(index).encode()).hexdigest() for index in range(6)),
        forbidden_sha256=(),
        parser_callable=hangs,
    )
    executor = SyntheticTrustedParserExecutor(auth, contracts, timeout_cap_seconds=0.05)
    started = time.monotonic()
    with pytest.raises(StoreContractError) as error:
        executor.execute(scope, contracts.resolve(scope), b"raw", 60)
    assert error.value.code is PublicErrorCode.RESOURCE_LIMIT_EXCEEDED
    assert time.monotonic() - started < 2


def _accepted_synthetic_snapshot():
    from rxoptimizer.midi import Event, MidiFile, encode_midi
    from rxoptimizer.user_input_snapshot import create_user_input_snapshot

    raw = encode_midi(MidiFile(0, 480, [[
        Event(0, 0, "note_on", 0, 60, 90, 0x90),
        Event(120, 1, "note_off", 0, 60, 0, 0x80),
    ]]))
    ports, auth = synthetic_store_ports()
    handle = auth.issue(ids("owner"), ids("session"), ids("upload"))
    upload = ports.sealed_upload.seal(handle, raw)
    result = create_user_input_snapshot(ports, handle, upload)
    assert result.status == "SNAPSHOT_ACCEPTED_USER_INPUT"
    key = CompositeSnapshotKey(
        result.handle.owner_scope_id,
        result.handle.session_locator_id,
        result.handle.upload_locator_id,
        result.handle.snapshot_instance_id,
    )
    return ports, auth, handle, result, key


def test_end_to_end_purge_destroys_key_redacts_identity_and_never_restores():
    from rxoptimizer.user_input_snapshot import request_user_input_snapshot_purge, run_user_input_purge_sweeper

    ports, _, handle, result, key = _accepted_synthetic_snapshot()
    record = ports.registry._records[key.locator_key]
    generation = record.generation_token
    payload_key = ports.tenant_keys._payload_generations[(key.owner_scope_id, generation)][1]
    assert request_user_input_snapshot_purge(ports, handle, result.handle) == {"status": "PURGE_REQUESTED"}
    assert run_user_input_purge_sweeper(ports) == {"status": "OK", "purged": 1}
    assert run_user_input_purge_sweeper(ports) == {"status": "OK", "purged": 0}
    record = ports.registry._records[key.locator_key]
    assert record.state is LifecycleState.PURGED
    assert record.identity is None and record.generation_token is None
    assert payload_key not in (value[1] for value in ports.tenant_keys._payload_generations.values())
    assert (key.owner_scope_id, generation) in ports.tenant_keys._destroyed_payload_generations


@pytest.mark.parametrize("crash_after_mark", [False, True])
def test_purge_recovers_before_or_after_key_destruction_mark(crash_after_mark):
    from rxoptimizer.user_input_snapshot import request_user_input_snapshot_purge, run_user_input_purge_sweeper

    ports, _, handle, result, key = _accepted_synthetic_snapshot()
    request_user_input_snapshot_purge(ports, handle, result.handle)
    ports.registry.mark_physical_purge_pending(key)
    ports.packages.delete_quarantine(key)
    generation = ports.registry.payload_key_generation(key)
    ports.tenant_keys.destroy_snapshot_payload_key(key, generation)
    if crash_after_mark:
        ports.registry.mark_payload_key_destroyed(key)
    assert run_user_input_purge_sweeper(ports) == {"status": "OK", "purged": 1}
    assert ports.registry._records[key.locator_key].identity is None
    with pytest.raises(StoreContractError) as error:
        ports.tenant_keys.snapshot_payload_key(
            ports.authorization.verify(handle, Operation.CREATE), generation
        )
    assert error.value.code is PublicErrorCode.NOT_AVAILABLE