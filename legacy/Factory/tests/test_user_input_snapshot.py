from __future__ import annotations

from hashlib import sha256
from dataclasses import replace
import base64
import inspect
import json
from pathlib import Path
import struct

from rxoptimizer.midi import Event, MidiFile, encode_midi
from rxoptimizer.user_input_snapshot import (
    AcceptedSnapshot, DEFAULT_LIMITS, ExclusionReceipt, LIMITS_VERSION,
    create_user_input_snapshot, request_user_input_snapshot_purge,
    run_user_input_purge_sweeper, verify_user_input_snapshot,
)
from rxoptimizer.user_input_store import CompositeSnapshotKey, synthetic_store_ports


def midi_bytes(*, private=False, unmatched=False, unmatched_off=False):
    events=[]
    if unmatched_off:
        events.append(Event(0,0,"note_off",0,61,0,0x80))
    events.append(Event(0,1,"note_on",0,60,90,0x90))
    if private:
        events.append(Event(0,2,"meta",data1=1,raw=b"password=sesame"))
        events.append(Event(1,3,"sysex",status=0xF0,raw=b"secret-sysex"))
    if not unmatched:
        events.append(Event(120,4,"note_off",0,60,0,0x80))
    return encode_midi(MidiFile(0,480,[events]))


def policy(*, six=(), forbidden=()):
    six=set(six)
    while len(six)<6:
        six.add(sha256(f"six-{len(six)}".encode()).hexdigest())
    return frozenset(six),frozenset(forbidden)


def configure(ports, *, six=(), forbidden=(), parser=None, limits=DEFAULT_LIMITS):
    from rxoptimizer.midi import parse_midi
    six,forbidden=policy(six=six,forbidden=forbidden)
    ports.ingest_contracts.configure(policy_digest="trusted-policy-v1",parser_config_sha256="c"*64,
        parser_version="RXOPTIMIZER_MIDI_V1",limits_version=LIMITS_VERSION,limits=limits,
        six_song_sha256=six,forbidden_sha256=forbidden,parser_callable=parser or parse_midi)


def context(raw, suffix="A"):
    ports,auth=synthetic_store_ports()
    handle=auth.issue(f"OWNER_{suffix}_abcdefgh",f"SESSION_{suffix}_abcdef",f"UPLOAD_{suffix}_abcdefgh")
    upload=ports.sealed_upload.seal(handle,raw)
    return ports,handle,upload


def key(result):
    h=result.handle
    return CompositeSnapshotKey(h.owner_scope_id,h.session_locator_id,h.upload_locator_id,h.snapshot_instance_id)


def members(ports,result):
    output={}
    for name in ("original_upload.bin","snapshot.sqlite3","private_manifest.json","payload_key.slot"):
        stream=ports.packages.open_active_read_only(key(result),name)
        try: output[name]=stream.read()
        finally: stream.close()
    return output


def test_accepted_exactly_one_parse_and_full_verify():
    raw=midi_bytes(); p,auth,upload=context(raw); calls=[]
    def parser(data):
        calls.append(data)
        from rxoptimizer.midi import parse_midi
        return parse_midi(data)
    configure(p,parser=parser)
    result=create_user_input_snapshot(p,auth,upload)
    assert isinstance(result,AcceptedSnapshot)
    assert result.parse_invocation_count==1
    assert result.event_count==3 and result.note_count==1
    assert verify_user_input_snapshot(p,auth,result.handle)=={"status":"FULL_RAW_AND_GRAPH_VERIFIED"}
    assert set(p.packages.inventory(key(result)).members)=={
        "original_upload.bin","snapshot.sqlite3","private_manifest.json","payload_key.slot"}


def test_six_and_forbidden_are_preparse_receipts_without_package_or_route():
    for reason in ("EXCLUDED_SIX_SONG_GENERAL_X10","EXCLUDED_FORBIDDEN_SOURCE"):
        raw=midi_bytes(); digest=sha256(raw).hexdigest(); p,auth,upload=context(raw,reason[-1])
        configure(p,six={digest} if reason.startswith("EXCLUDED_SIX") else (),
                  forbidden={digest} if reason.endswith("FORBIDDEN_SOURCE") else ())
        calls=[]; result=create_user_input_snapshot(p,auth,upload)
        assert isinstance(result,ExclusionReceipt) and result.terminal_reason==reason
        assert result.orchestration_parse_invocation_count==0 and not calls
        assert result.subject_graph_status=="NOT_CREATED" and result.automatic_route_status=="NOT_INVOKED"


def test_all_six_hashes_excluded_with_true_zero_parse():
    raws=[midi_bytes()+bytes([i]) for i in range(6)]
    for index,raw in enumerate(raws):
        p,auth,upload=context(raw,str(index)); calls=[]
        configure(p,six={sha256(item).hexdigest() for item in raws})
        result=create_user_input_snapshot(p,auth,upload)
        assert result.terminal_reason=="EXCLUDED_SIX_SONG_GENERAL_X10" and not calls


def test_private_payload_has_no_plaintext_or_unsalted_digest_oracle():
    raw=midi_bytes(private=True); p,auth,upload=context(raw)
    result=create_user_input_snapshot(p,auth,upload); package=members(p,result)
    exposed=json.dumps(result.__dict__,default=lambda obj:obj.__dict__,sort_keys=True).encode()+package["private_manifest.json"]+package["snapshot.sqlite3"]
    assert b"password=sesame" not in exposed and b"secret-sysex" not in exposed
    assert sha256(b"password=sesame").hexdigest().encode() not in exposed


def test_identical_bytes_different_owners_are_unlinkable():
    raw=midi_bytes(); p1,a1,u1=context(raw,"A"); p2,a2,u2=context(raw,"B")
    one=create_user_input_snapshot(p1,a1,u1); two=create_user_input_snapshot(p2,a2,u2)
    assert one.handle.snapshot_namespace_id!=two.handle.snapshot_namespace_id
    assert one.handle.snapshot_instance_id!=two.handle.snapshot_instance_id


def test_unmatched_on_and_off_are_preserved_not_repaired():
    raw=midi_bytes(unmatched=True,unmatched_off=True); p,auth,upload=context(raw)
    result=create_user_input_snapshot(p,auth,upload)
    assert result.note_count==2
    database=members(p,result)["snapshot.sqlite3"]
    assert b"UNMATCHED_ON" in database and b"UNMATCHED_OFF" in database


def test_declared_length_and_streaming_raw_limit_fail_closed_before_parse():
    attack=b"MThd"+struct.pack(">IHHH",6,0,1,480)+b"MTrk"+struct.pack(">I",2**31)
    p,auth,upload=context(attack); calls=[]
    result=create_user_input_snapshot(p,auth,upload)
    assert result.status=="RESOURCE_LIMIT_EXCEEDED" and not calls
    raw=b"x"*(33_554_432+1); p,auth,upload=context(raw,"L")
    result=create_user_input_snapshot(p,auth,upload)
    assert result.__dict__=={"status":"RESOURCE_LIMIT_EXCEEDED"}


def test_noncanonical_vlq_is_resource_rejected_before_parser():
    # Delta zero encoded as 0x80 0x00 is mathematically valid but noncanonical.
    body=b"\x80\x00\xff\x2f\x00"
    raw=b"MThd"+struct.pack(">IHHH",6,0,1,480)+b"MTrk"+struct.pack(">I",len(body))+body
    p,auth,upload=context(raw,"V"); calls=[]
    result=create_user_input_snapshot(p,auth,upload)
    assert result.status=="RESOURCE_LIMIT_EXCEEDED" and calls==[]


def test_invalid_midi_is_separate_zero_graph_receipt_and_no_active_package():
    raw=b"not-midi"; p,auth,upload=context(raw,"I")
    result=create_user_input_snapshot(p,auth,upload)
    assert isinstance(result,ExclusionReceipt)
    assert result.terminal_reason=="INVALID_OR_UNSUPPORTED_MIDI"
    assert result.subject_graph_status=="NOT_CREATED"


def test_parser_level_invalid_receipt_commits_actual_one_invocation():
    from rxoptimizer.midi import MidiError
    raw=midi_bytes(); p,auth,upload=context(raw,"P"); calls=[]
    def rejected(data):
        calls.append(data)
        raise MidiError("private detail must not escape")
    configure(p,parser=rejected)
    result=create_user_input_snapshot(p,auth,upload)
    assert isinstance(result,ExclusionReceipt)
    assert result.terminal_reason=="INVALID_OR_UNSUPPORTED_MIDI"
    assert result.orchestration_parse_invocation_count==1


def test_corruption_and_wrong_owner_are_same_not_available_shape():
    raw=midi_bytes(); p,auth,upload=context(raw); result=create_user_input_snapshot(p,auth,upload)
    directory=p.packages._active/p.packages._dirname(key(result))
    (directory/"original_upload.bin").write_bytes(raw+b"x")
    corrupt=verify_user_input_snapshot(p,auth,result.handle)
    _,other_auth=synthetic_store_ports(); foreign=other_auth.issue("OWNER_X_abcdefgh","SESSION_X_abcdef","UPLOAD_X_abcdefgh")
    foreign_result=verify_user_input_snapshot(p,foreign,result.handle)
    assert corrupt==foreign_result=={"status":"NOT_AVAILABLE"}


def test_manual_purge_revokes_then_sweeper_removes_whole_package():
    raw=midi_bytes(); p,auth,upload=context(raw); result=create_user_input_snapshot(p,auth,upload)
    assert request_user_input_snapshot_purge(p,auth,result.handle)=={"status":"PURGE_REQUESTED"}
    assert verify_user_input_snapshot(p,auth,result.handle)=={"status":"NOT_AVAILABLE"}
    assert run_user_input_purge_sweeper(p)=={"status":"OK","purged":1}
    assert verify_user_input_snapshot(p,auth,result.handle)=={"status":"NOT_AVAILABLE"}


def test_sweeper_recovers_crash_after_physical_delete_before_registry_finish():
    raw=midi_bytes(); p,auth,upload=context(raw,"D"); result=create_user_input_snapshot(p,auth,upload)
    request_user_input_snapshot_purge(p,auth,result.handle)
    snapshot_key=key(result)
    p.registry.mark_physical_purge_pending(snapshot_key)
    p.packages.delete_quarantine(snapshot_key)
    assert p.packages.reconcile_absent(snapshot_key)
    assert run_user_input_purge_sweeper(p)=={"status":"OK","purged":1}
    assert p.registry.recover()==()
    assert run_user_input_purge_sweeper(p)=={"status":"OK","purged":0}


def test_no_forbidden_api_or_midi_output_member():
    import rxoptimizer.user_input_snapshot as module
    forbidden=("target","candidate","repair","calibration","anomaly","write_midi","export_midi")
    assert not any(any(word in name.lower() for word in forbidden) for name in module.__all__)
    raw=midi_bytes(); p,auth,upload=context(raw); result=create_user_input_snapshot(p,auth,upload)
    assert not any(name.endswith((".mid",".midi")) for name in p.packages.inventory(key(result)).members)


def test_public_create_has_no_caller_policy_parser_or_limits_surface():
    signature=inspect.signature(create_user_input_snapshot)
    assert tuple(signature.parameters)==("ports","auth_handle","upload_handle")
    raw=midi_bytes(); p,auth,upload=context(raw,"T")
    try:
        create_user_input_snapshot(p,auth,upload,object())
    except TypeError:
        pass
    else:
        raise AssertionError("caller policy unexpectedly accepted")


def test_noncanonical_trusted_limits_fail_closed_and_session_quota_is_enforced():
    raw=midi_bytes(); p,auth,upload=context(raw,"Q")
    configure(p,limits=replace(DEFAULT_LIMITS,max_raw_bytes=DEFAULT_LIMITS.max_raw_bytes+1))
    assert create_user_input_snapshot(p,auth,upload).status=="INTERNAL_OPERATION_FAILED"
    p,auth,upload=context(raw,"R"); p.session_quota._maximum=1
    assert create_user_input_snapshot(p,auth,upload).status=="RESOURCE_LIMIT_EXCEEDED"


def test_trusted_parser_watchdog_timeout_is_fail_closed():
    import time
    raw=midi_bytes(); p,auth,upload=context(raw,"W")
    def hanging_parser(data):
        del data
        while True: time.sleep(1)
    configure(p,parser=hanging_parser)
    p.parser_executor.timeout_cap_seconds=0.2
    started=time.monotonic();result=create_user_input_snapshot(p,auth,upload);elapsed=time.monotonic()-started
    assert result.status=="RESOURCE_LIMIT_EXCEEDED" and elapsed<2
    assert not p.session_quota._pending
    assert not any(p.packages._active.iterdir()) and not any(p.packages._staging.iterdir())


def test_builder_watchdog_timeout_is_fail_closed_after_parser():
    raw=midi_bytes(); p,auth,upload=context(raw,"B"); now=[0.0]
    def advancing_clock():
        now[0]+=50.0
        return now[0]
    p.watchdog._clock=advancing_clock
    assert create_user_input_snapshot(p,auth,upload).status=="RESOURCE_LIMIT_EXCEEDED"


def test_same_locator_retry_new_seal_is_idempotent_and_byte_identical():
    raw=midi_bytes(private=True); p,auth,upload=context(raw,"Y")
    first=create_user_input_snapshot(p,auth,upload)
    before=p.packages.inventory(key(first))
    retry_upload=p.sealed_upload.seal(auth,raw)
    second=create_user_input_snapshot(p,auth,retry_upload)
    after=p.packages.inventory(key(second))
    assert isinstance(second,AcceptedSnapshot)
    assert first.handle==second.handle and first.semantic_digest==second.semantic_digest
    assert before==after


def _refresh_registry_inventory(ports,result):
    inventory=ports.packages.inventory(key(result))
    ports.registry._records[key(result).locator_key].inventory_digest=inventory.generation_digest


def test_verify_rejects_payload_key_corruption_even_if_inventory_commit_is_forged():
    raw=midi_bytes(private=True); p,auth,upload=context(raw,"K"); result=create_user_input_snapshot(p,auth,upload)
    directory=p.packages._active/p.packages._dirname(key(result))
    slot=json.loads((directory/"payload_key.slot").read_bytes())
    slot["key_material_base64url"]=base64.urlsafe_b64encode(b"z"*32).decode().rstrip("=")
    (directory/"payload_key.slot").write_text(json.dumps(slot,separators=(",",":")))
    _refresh_registry_inventory(p,result)
    assert verify_user_input_snapshot(p,auth,result.handle)=={"status":"NOT_AVAILABLE"}


def test_verify_rejects_manifest_count_corruption_even_if_inventory_commit_is_forged():
    raw=midi_bytes(); p,auth,upload=context(raw,"M"); result=create_user_input_snapshot(p,auth,upload)
    directory=p.packages._active/p.packages._dirname(key(result))
    manifest=json.loads((directory/"private_manifest.json").read_bytes());manifest["subject_count"]+=100
    (directory/"private_manifest.json").write_text(json.dumps(manifest,separators=(",",":"),sort_keys=True))
    _refresh_registry_inventory(p,result)
    assert verify_user_input_snapshot(p,auth,result.handle)=={"status":"NOT_AVAILABLE"}


def test_graph_spool_is_disk_backed_and_enforces_peak_batch():
    from rxoptimizer.user_input_snapshot import _GraphSpool
    spool=_GraphSpool(3); path=Path(spool.path)
    try:
        for index in range(10):
            spool.add_subject({"subject_id":str(index),"subject_type":"EVENT","natural_key":{"i":index},"payload":{}})
        spool.finalize()
        assert path.is_file() and spool.peak_batch<=3 and spool.subject_count==10
    finally:
        spool.close()
    assert not path.exists()