from fractions import Fraction
from hashlib import sha256
import sqlite3

import pytest

from rxoptimizer.midi import Event, MidiFile, encode_midi
from rxoptimizer.rhythm_context_models import (FrozenV2SourceInput, V2SourceArtifacts,
    V2UnprovenPartition,
    build_context_qualified_database_v2, canonical_semantic_rows_v2,
    event_slot_key_from_evidence, semantic_digest_v2)
from rxoptimizer.rhythm_multimodal import PhaseObservation
from rxoptimizer.rhythm_protection_adapters import (EXTRACTION_DOMAINS,
    BarPatternObservation, NoteObservation, SectionObservation, SourceLineageRecord,
    SIX_SONG_FORBIDDEN_SHA256S, StructuralSourceSnapshot, TrackObservation, complete_extraction_attestation,
    trusted_source_guard_policy, trusted_source_lineage_snapshot)
from rxoptimizer.rhythm_subject_registry import (StableSubject, StableSubjectEdge,
    StableSubjectRegistry)


def raw_record(tag="a", corpus="factory"):
    midi = MidiFile(1, 480, [[
        Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "control", 0, 32, 2, 0xB0),
        Event(0, 2, "program", 0, 33, status=0xC0),
        Event(0, 3, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))),
        Event(0, 4, "meta", data1=0x51, raw=(500000).to_bytes(3, "big")),
        Event(0, 5, "meta", data1=0x01, raw=tag.encode()),
        Event(0, 6, "note_on", 0, 60, 80, 0x90),
        Event(120, 7, "note_off", 0, 60, 0, 0x80),
    ]])
    data = encode_midi(midi)
    return {"bytes": data, "source_sha256": sha256(data).hexdigest(), "corpus": corpus,
        "member_path": f"{'Factory' if corpus == 'factory' else 'Gold'}/{tag}.mid",
        "quality_status": "NORMAL", "metadata": {
            "role": "BASS", "role_status": "EXACT", "style_name": "Test",
            "style_status": "EXPLICIT_METADATA", "section": "VARIATION", "section_no": 0,
            "section_status": "EXACT", "cv": 0, "cv_status": "CV_EXACT",
            "role_method": "RAW_TRACK", "role_locator": "raw#track=0",
            "style_method": "EXPLICIT_METADATA", "style_locator": "raw#style",
            "section_method": "EXPLICIT_METADATA", "section_locator": "raw#section",
            "cv_method": "EXPLICIT_METADATA", "cv_locator": "raw#cv"}}


def multi_slot_record(tag="multi"):
    midi = MidiFile(1, 480, [[
        Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "control", 0, 32, 2, 0xB0),
        Event(0, 2, "program", 0, 33, status=0xC0),
        Event(0, 3, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))),
        Event(0, 4, "meta", data1=0x51, raw=(500000).to_bytes(3, "big")),
        Event(0, 5, "note_on", 0, 60, 80, 0x90),
        Event(120, 6, "note_off", 0, 60, 0, 0x80),
        Event(240, 7, "note_on", 0, 62, 82, 0x90),
        Event(360, 8, "note_off", 0, 62, 0, 0x80),
    ]])
    record = raw_record(tag); data = encode_midi(midi)
    record.update(bytes=data, source_sha256=sha256(data).hexdigest())
    return record


def multi_context_record(tag="contexts"):
    midi = MidiFile(1, 480, [[
        Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "control", 0, 32, 2, 0xB0),
        Event(0, 2, "program", 0, 33, status=0xC0),
        Event(0, 3, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))),
        Event(0, 4, "meta", data1=0x51, raw=(500000).to_bytes(3, "big")),
        Event(0, 5, "note_on", 0, 60, 80, 0x90),
        Event(120, 6, "note_off", 0, 60, 0, 0x80),
        Event(240, 7, "program", 0, 34, status=0xC0),
        Event(241, 8, "note_on", 0, 62, 82, 0x90),
        Event(360, 9, "note_off", 0, 62, 0, 0x80),
    ]])
    record = raw_record(tag); data = encode_midi(midi)
    record.update(bytes=data, source_sha256=sha256(data).hexdigest())
    return record


def mixed_context_record(tag="mixed"):
    midi = MidiFile(1, 480, [[
        Event(0, 0, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))),
        Event(0, 1, "meta", data1=0x51, raw=(500000).to_bytes(3, "big")),
        Event(0, 2, "note_on", 0, 60, 80, 0x90),
        Event(120, 3, "note_off", 0, 60, 0, 0x80),
        Event(240, 4, "control", 0, 0, 10, 0xB0),
        Event(240, 5, "control", 0, 32, 2, 0xB0),
        Event(240, 6, "program", 0, 33, status=0xC0),
        Event(241, 7, "note_on", 0, 62, 82, 0x90),
        Event(360, 8, "note_off", 0, 62, 0, 0x80),
    ]])
    record = raw_record(tag); data = encode_midi(midi)
    record.update(bytes=data, source_sha256=sha256(data).hexdigest())
    return record


def empty_record(tag="empty"):
    data = encode_midi(MidiFile(1, 480, [[]]))
    record = raw_record(tag); record.update(bytes=data, source_sha256=sha256(data).hexdigest())
    return record


def all_unproven_record(tag="all-unproven"):
    record = raw_record(tag); record["metadata"]["role_status"] = "UNKNOWN"
    return record


def artifact_factory(frozen):
    assert isinstance(frozen, FrozenV2SourceInput)
    source_sha = frozen.source_sha256
    notes = frozen.base_note_context
    kind = "FACTORY_RAW" if frozen.corpus == "factory" else "GOLD_REFERENCE_RAW"
    lineage = trusted_source_lineage_snapshot((SourceLineageRecord(source_sha, kind, ()),))
    snapshots = []; all_observations = []
    groups = {}; unproven_notes = []
    for item in notes:
        if item.get("exact_context_key"): groups.setdefault(item["exact_context_key"], []).append(item)
        else: unproven_notes.append(item)
    for exact_key in sorted(groups):
        context_notes = groups[exact_key]; meter = context_notes[0]["meter_segment_id"]
        registry = StableSubjectRegistry()
        scope = registry.add_subject(StableSubject("EXACT_CONTEXT", source_sha,
            {"exact_context_key": exact_key}))
        track = registry.add_subject(StableSubject("TRACK_CHANNEL", source_sha,
            {"track_index": 0, "channel": 0}))
        bar = registry.add_subject(StableSubject("BAR", source_sha,
            {"meter_segment_id": meter, "start_tick": 0, "end_tick": 1920}))
        note_rows = []; stable_notes = []
        for item in context_notes:
            event = registry.add_subject(StableSubject("EVENT", source_sha,
                {"event_id": item["on_event_id"], "event_kind": "NOTE_ON"}))
            note = registry.add_subject(StableSubject("NOTE", source_sha, {"note_id": item["note_id"]}))
            cluster = registry.add_subject(StableSubject("ONSET_CLUSTER", source_sha,
                {"track_index": 0, "channel": 0, "meter_segment_id": meter,
                 "tick": item["start_tick"], "on_event_ids": [event.subject_id]}))
            for edge_type, parent, child in (
                ("TRACK_CHANNEL_CONTAINS_NOTE", track, note), ("NOTE_HAS_ON_EVENT", note, event),
                ("BAR_CONTAINS_ONSET_CLUSTER", bar, cluster),
                ("ONSET_CLUSTER_CONTAINS_NOTE", cluster, note),
                ("EXACT_CONTEXT_CONTAINS_NOTE", scope, note)):
                registry.add_edge(StableSubjectEdge(edge_type, parent.subject_id,
                                                    child.subject_id, source_sha))
            stable_notes.append((item, note, event, cluster))
            note_rows.append(NoteObservation(note.subject_id, track.subject_id, None,
                cluster.subject_id, bar.subject_id, meter, item["note"], item["start_tick"],
                item["end_tick"], 0, 1920, "METER_EXACT"))
        tracks = (TrackObservation(track.subject_id, 0, 0, role="BASS", role_status="EXACT"),)
        sections = (SectionObservation(track.subject_id, "VARIATION", "EXACT", "RAW_TRACK",
            (bar.subject_id,), {bar.subject_id: tuple(item[1].subject_id for item in stable_notes)}),)
        patterns = (BarPatternObservation(bar.subject_id, track.subject_id, meter,
            "4" * 64, "5" * 64, tuple(item[1].subject_id for item in stable_notes)),)
        note_rows = tuple(note_rows)
        domains = {"TRACKS": tracks, "NOTES": note_rows, "PHRASES": (),
            "SECTIONS": sections, "BOUNDARIES": (), "BAR_PATTERNS": patterns,
            "RX_SUBJECTS": (), "HUMAN_COMPONENTS": ()}
        attestations = tuple(complete_extraction_attestation(name, domains[name])
                             for name in EXTRACTION_DOMAINS)
        snapshots.append(StructuralSourceSnapshot(source_sha, kind, registry, scope.subject_id,
            attestations, trusted_source_guard_policy(), lineage, tracks=tracks, notes=note_rows,
            sections=sections, bar_patterns=patterns,
            source_manifest={"source_class": kind, "lineage_sha256": lineage.semantic_sha256}))
        all_observations.extend(PhaseObservation(source_sha, bar.subject_id,
            Fraction(item[0]["start_tick"], 1920), Fraction(1, 3840),
            event_slot_key_from_evidence(exact_key, item[0]["note"], 0, 1920,
                                         item[0]["start_tick"]), exact_key, authority=(
                "FACTORY" if frozen.corpus == "factory" else "GOLD_REFERENCE"),
            observation_id=sha256(f"{source_sha}:{item[1].subject_id}".encode()).hexdigest())
            for item in stable_notes)
    observations = tuple(all_observations)
    unproven = None
    if unproven_notes or not snapshots:
        registry = StableSubjectRegistry(); note_ids = []
        track = registry.add_subject(StableSubject("TRACK_CHANNEL", source_sha,
            {"track_index": 0, "channel": 0})) if unproven_notes else None
        for item in unproven_notes:
            meter = item["meter_segment_id"]
            event = registry.add_subject(StableSubject("EVENT", source_sha,
                {"event_id": item["on_event_id"], "event_kind": "NOTE_ON"}))
            note = registry.add_subject(StableSubject("NOTE", source_sha, {"note_id": item["note_id"]}))
            bar = registry.add_subject(StableSubject("BAR", source_sha,
                {"meter_segment_id": meter, "start_tick": 0, "end_tick": 1920}))
            cluster = registry.add_subject(StableSubject("ONSET_CLUSTER", source_sha,
                {"track_index": 0, "channel": 0, "meter_segment_id": meter,
                 "tick": item["start_tick"], "on_event_ids": [event.subject_id]}))
            for edge_type, parent, child in (
                ("TRACK_CHANNEL_CONTAINS_NOTE", track, note), ("NOTE_HAS_ON_EVENT", note, event),
                ("BAR_CONTAINS_ONSET_CLUSTER", bar, cluster),
                ("ONSET_CLUSTER_CONTAINS_NOTE", cluster, note)):
                registry.add_edge(StableSubjectEdge(edge_type, parent.subject_id,
                                                    child.subject_id, source_sha))
            note_ids.append(item["note_id"])
        unproven = V2UnprovenPartition(source_sha, kind, registry, tuple(note_ids),
            trusted_source_guard_policy(), lineage,
            {"source_class": kind, "lineage_sha256": lineage.semantic_sha256,
             "partition_kind": "UNPROVEN_SOURCE_PRESERVATION"})
    if frozen.corpus == "factory":
        return V2SourceArtifacts(tuple(snapshots), observations, (), unproven)
    return V2SourceArtifacts(tuple(snapshots), (), observations, unproven)


def test_v2_streaming_atomic_sparse_deterministic_and_public_summary(tmp_path):
    records = [raw_record(str(index)) for index in range(4)]
    first = tmp_path / "one.sqlite3"; second = tmp_path / "two.sqlite3"
    report1 = build_context_qualified_database_v2(iter(records), first,
        {"v2_source_artifact_factory": artifact_factory})
    report2 = build_context_qualified_database_v2(iter(reversed(records)), second,
        {"v2_source_artifact_factory": artifact_factory})
    assert report1["parse_count"] == report1["sources"] == 4
    assert report1["peak_source_notes"] == 1
    assert report1["sparse_membership_rows"] < report1["dense_equivalent_rows"]
    assert report1["semantic_digest"] == report2["semantic_digest"]
    assert canonical_semantic_rows_v2(first) == canonical_semantic_rows_v2(second)
    assert semantic_digest_v2(first) == report1["semantic_digest"]
    assert report1["capability"] == "ANALYZE_ONLY" and report1["mutation_capability"] == "NONE"
    db = sqlite3.connect(first)
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("SELECT COUNT(*) FROM factory_models").fetchone()[0] == 1
    assert db.execute("SELECT modality_status FROM factory_models").fetchone()[0] == "INSUFFICIENT_MODAL_EVIDENCE"
    assert db.execute("SELECT COUNT(*) FROM analysis_authorization").fetchone()[0] == 4
    assert db.execute("SELECT COUNT(DISTINCT rule_key) FROM adapter_runs").fetchone()[0] == 9
    assert db.execute("SELECT COUNT(*) FROM factory_local_profiles").fetchone()[0] == 4
    assert db.execute("SELECT COUNT(*) FROM factory_consensus_slots").fetchone()[0] == 1
    db.close()


def test_v2_failure_preserves_old_database_and_rejects_v1_model_input(tmp_path):
    output = tmp_path / "atomic.sqlite3"
    build_context_qualified_database_v2([raw_record("ok")], output,
        {"v2_source_artifact_factory": artifact_factory})
    before = semantic_digest_v2(output)
    broken = raw_record("bad"); broken["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA mismatch"):
        build_context_qualified_database_v2([broken], output,
            {"v2_source_artifact_factory": artifact_factory})
    assert semantic_digest_v2(output) == before
    with pytest.raises(ValueError, match="v1 database/model"):
        build_context_qualified_database_v2([raw_record("legacy")], tmp_path / "legacy.sqlite3",
            {"v2_source_artifact_factory": artifact_factory, "v1_database": "old.sqlite3"})


def test_v2_rejects_optimizer_and_repaired_sources_without_output(tmp_path):
    record = raw_record("unsafe"); record["is_optimizer_output"] = True
    with pytest.raises(ValueError, match="Optimizer/repaired"):
        build_context_qualified_database_v2([record], tmp_path / "unsafe.sqlite3",
            {"v2_source_artifact_factory": artifact_factory})


def test_v2_callback_receives_only_immutable_frozen_artifact_input(tmp_path):
    def guarded(value):
        assert isinstance(value, FrozenV2SourceInput)
        for forbidden in ("bytes", "raw_bytes", "record", "midi", "parser", "parse_midi"):
            assert not hasattr(value, forbidden)
        with pytest.raises(TypeError): value.metadata["role"] = "FORGED"
        with pytest.raises(TypeError): value.base_note_context[0]["note"] = 1
        return artifact_factory(value)
    report = build_context_qualified_database_v2([raw_record("frozen")],
        tmp_path / "frozen.sqlite3", {"v2_source_artifact_factory": guarded})
    assert report["parse_count"] == report["runtime_metrics"]["parse_count"] == 1


def test_v2_builds_and_authorizes_every_real_slot_without_slot_zero(tmp_path):
    output = tmp_path / "multi.sqlite3"
    build_context_qualified_database_v2([multi_slot_record()], output,
        {"v2_source_artifact_factory": artifact_factory})
    db = sqlite3.connect(output)
    slots = {row[0] for row in db.execute("SELECT event_slot_key FROM factory_observations")}
    authorization = {row[0] for row in db.execute("SELECT event_slot_key FROM analysis_authorization")}
    assert len(slots) == 2 and authorization == slots and "slot-0" not in slots
    assert db.execute("SELECT COUNT(*) FROM factory_models").fetchone()[0] == 2
    db.close()


def test_v2_config_contract_participates_in_digest(tmp_path):
    first = tmp_path / "config-a.sqlite3"; second = tmp_path / "config-b.sqlite3"
    one = build_context_qualified_database_v2([raw_record("cfg")], first,
        {"v2_source_artifact_factory": artifact_factory, "caller_policy": "A"})
    two = build_context_qualified_database_v2([raw_record("cfg")], second,
        {"v2_source_artifact_factory": artifact_factory, "caller_policy": "B"})
    assert one["build_config_sha256"] != two["build_config_sha256"]
    assert one["semantic_digest"] != two["semantic_digest"]
    assert any("build_contract_v2" in row for row in canonical_semantic_rows_v2(first))


@pytest.mark.parametrize("forgery", ["bar", "slot", "phase"])
def test_v2_rejects_fabricated_observation_anchors(tmp_path, forgery):
    def forged(value):
        base = artifact_factory(value); original = base.factory_observations[0]
        kwargs = dict(source_sha256=original.source_sha256, bar_id=original.bar_id,
            phase=original.phase, half_tick_resolution=original.half_tick_resolution,
            event_slot_key=original.event_slot_key, exact_context_key=original.exact_context_key,
            authority=original.authority)
        if forgery == "bar": kwargs["bar_id"] = "f" * 64
        elif forgery == "slot": kwargs["event_slot_key"] = "e" * 64
        else: kwargs["phase"] = Fraction(1, 4)
        return V2SourceArtifacts(base.context_snapshots, (PhaseObservation(**kwargs),), ())
    with pytest.raises(ValueError, match="Observation"):
        build_context_qualified_database_v2([raw_record(f"forged-{forgery}")],
            tmp_path / f"forged-{forgery}.sqlite3",
            {"v2_source_artifact_factory": forged})


def test_v2_reports_actual_peak_spool_growth_as_runtime_only(tmp_path):
    output = tmp_path / "spool.sqlite3"
    report = build_context_qualified_database_v2([raw_record(str(i)) for i in range(3)], output,
        {"v2_source_artifact_factory": artifact_factory})
    metrics = report["runtime_metrics"]
    assert metrics["spool_peak_bytes"] >= metrics["final_bytes"] > 0
    assert metrics["peak_source_bytes"] > 0 and metrics["peak_source_subjects"] > 0
    assert "runtime_metrics" not in "\n".join(canonical_semantic_rows_v2(output))


def test_v2_one_parse_supports_two_exact_contexts_with_partitioned_adapters(tmp_path):
    record = multi_context_record()
    first = tmp_path / "contexts-a.sqlite3"; second = tmp_path / "contexts-b.sqlite3"
    one = build_context_qualified_database_v2([record], first,
        {"v2_source_artifact_factory": artifact_factory})
    def reversed_factory(value):
        result = artifact_factory(value)
        return V2SourceArtifacts(tuple(reversed(result.context_snapshots)),
            tuple(reversed(result.factory_observations)), result.reference_observations)
    two = build_context_qualified_database_v2([record], second,
        {"v2_source_artifact_factory": reversed_factory})
    assert one["parse_count"] == one["sources"] == 1
    assert one["context_snapshot_count"] == 2
    assert one["semantic_digest"] == two["semantic_digest"]
    db = sqlite3.connect(first)
    assert db.execute("SELECT COUNT(DISTINCT exact_context_key) FROM context_eligibility").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM adapter_runs").fetchone()[0] == 18
    assert db.execute("SELECT COUNT(*) FROM analysis_authorization").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM (SELECT subject_id FROM context_subject_membership "
        "WHERE subject_id IN (SELECT note_subject_id FROM context_eligibility) "
        "GROUP BY subject_id HAVING COUNT(DISTINCT exact_context_key)<>1)").fetchone()[0] == 0
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
    before = semantic_digest_v2(first)
    def overlapping(value):
        result = artifact_factory(value)
        return V2SourceArtifacts((result.context_snapshots[0], result.context_snapshots[0]),
                                 result.factory_observations, ())
    with pytest.raises(ValueError, match="unique|partition"):
        build_context_qualified_database_v2([record], first,
            {"v2_source_artifact_factory": overlapping})
    assert semantic_digest_v2(first) == before


@pytest.mark.parametrize("gap", ["program", "role", "section", "cv", "meter", "tempo"])
def test_v2_nonexact_notes_are_stable_materialized_and_preserved_without_models(tmp_path, gap):
    record = raw_record(f"unproven-{gap}")
    if gap == "program":
        midi = MidiFile(1, 480, [[Event(0, 0, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))),
            Event(0, 1, "meta", data1=0x51, raw=(500000).to_bytes(3, "big")),
            Event(0, 2, "note_on", 0, 60, 80, 0x90), Event(120, 3, "note_off", 0, 60, 0, 0x80)]])
        data = encode_midi(midi); record.update(bytes=data, source_sha256=sha256(data).hexdigest())
    elif gap == "role": record["metadata"]["role_status"] = "UNKNOWN"
    elif gap == "section": record["metadata"]["section_status"] = "UNKNOWN"
    elif gap == "cv": record["metadata"]["cv_status"] = "CV_UNKNOWN"
    elif gap in {"meter", "tempo"}:
        events = [Event(0, 0, "control", 0, 0, 10, 0xB0),
            Event(0, 1, "control", 0, 32, 2, 0xB0), Event(0, 2, "program", 0, 33, status=0xC0)]
        if gap != "meter": events.append(Event(0, 3, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))))
        if gap != "tempo": events.append(Event(0, 4, "meta", data1=0x51, raw=(500000).to_bytes(3, "big")))
        events.extend((Event(0, 5, "note_on", 0, 60, 80, 0x90),
                       Event(120, 6, "note_off", 0, 60, 0, 0x80)))
        data = encode_midi(MidiFile(1, 480, [events])); record.update(
            bytes=data, source_sha256=sha256(data).hexdigest())
    output = tmp_path / f"unproven-{gap}.sqlite3"
    report = build_context_qualified_database_v2([record], output,
        {"v2_source_artifact_factory": artifact_factory})
    assert report["parse_count"] == 1 and report["context_snapshot_count"] == 0
    db = sqlite3.connect(output)
    assert db.execute("SELECT context_status FROM context_eligibility").fetchone()[0] == "CONTEXT_UNPROVEN"
    assert db.execute("SELECT authorization_status FROM analysis_authorization").fetchone()[0] == "PRESERVE_CONTEXT_UNPROVEN"
    assert db.execute("SELECT COUNT(*) FROM adapter_runs").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM factory_observations").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM factory_models").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM stable_subjects WHERE subject_type='NOTE'").fetchone()[0] == 1
    db.close()


def test_v2_mixed_exact_and_unproven_source_partitions_without_dense_dummy_rows(tmp_path):
    output = tmp_path / "mixed.sqlite3"
    report = build_context_qualified_database_v2([mixed_context_record()], output,
        {"v2_source_artifact_factory": artifact_factory})
    assert report["parse_count"] == 1 and report["context_snapshot_count"] == 1
    db = sqlite3.connect(output)
    statuses = dict(db.execute("SELECT context_status,COUNT(*) FROM context_eligibility GROUP BY context_status"))
    assert statuses == {"CONTEXT_UNPROVEN": 1, "EXACT_CONTEXT_MATCH": 1}
    assert db.execute("SELECT COUNT(*) FROM adapter_runs").fetchone()[0] == 9
    assert db.execute("SELECT COUNT(*) FROM factory_observations").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM analysis_authorization WHERE authorization_status='PRESERVE_CONTEXT_UNPROVEN'").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM context_subject_membership c JOIN context_eligibility e "
        "ON e.note_subject_id=c.subject_id WHERE e.context_status='CONTEXT_UNPROVEN'").fetchone()[0] == 0
    db.close()


def test_v2_empty_midi_has_source_level_unproven_partition_without_dummy_rows(tmp_path):
    output = tmp_path / "empty.sqlite3"
    report = build_context_qualified_database_v2([empty_record()], output,
        {"v2_source_artifact_factory": artifact_factory})
    assert report["parse_count"] == 1 and report["notes"] == 0
    assert report["context_snapshot_count"] == 0
    db = sqlite3.connect(output)
    for table in ("context_eligibility", "adapter_runs", "factory_observations",
                  "factory_models", "analysis_authorization"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    db.close()


def test_v2_unproven_note_cannot_be_smuggled_into_model_and_failure_rolls_back(tmp_path):
    output = tmp_path / "unproven-rollback.sqlite3"; record = mixed_context_record()
    build_context_qualified_database_v2([record], output,
        {"v2_source_artifact_factory": artifact_factory})
    before = semantic_digest_v2(output)
    def smuggled(value):
        result = artifact_factory(value)
        unproven_note = next(item for item in value.base_note_context if not item.get("exact_context_key"))
        observation = PhaseObservation(value.source_sha256, "f" * 64, Fraction(0),
            Fraction(1, 3840), "e" * 64, "forged-context")
        return V2SourceArtifacts(result.context_snapshots,
            result.factory_observations + (observation,), (), result.unproven_partition)
    with pytest.raises(ValueError, match="Factory-only model input|Observation"):
        build_context_qualified_database_v2([record], output,
            {"v2_source_artifact_factory": smuggled})
    assert semantic_digest_v2(output) == before


@pytest.mark.parametrize("record_factory", [all_unproven_record, mixed_context_record])
@pytest.mark.parametrize("violation", ["unrelated", "missing_root", "wrong_class",
    "forbidden_ancestor", "manifest_class", "manifest_digest"])
def test_v2_unproven_partition_enforces_trusted_lineage_and_manifest_contract(
        tmp_path, record_factory, violation):
    record = record_factory(f"lineage-{violation}")
    output = tmp_path / f"lineage-{record_factory.__name__}-{violation}.sqlite3"
    build_context_qualified_database_v2([record], output,
        {"v2_source_artifact_factory": artifact_factory})
    before = semantic_digest_v2(output)
    def invalid(value):
        result = artifact_factory(value); partition = result.unproven_partition
        assert partition is not None
        lineage = partition.source_lineage; kind = partition.source_kind
        manifest = dict(partition.source_manifest)
        if violation in {"unrelated", "missing_root"}:
            lineage = trusted_source_lineage_snapshot((SourceLineageRecord("a" * 64, kind, ()),))
        elif violation == "wrong_class":
            wrong = "GOLD_REFERENCE_RAW" if kind == "FACTORY_RAW" else "FACTORY_RAW"
            lineage = trusted_source_lineage_snapshot((SourceLineageRecord(value.source_sha256, wrong, ()),))
        elif violation == "forbidden_ancestor":
            forbidden = SIX_SONG_FORBIDDEN_SHA256S[0]
            lineage = trusted_source_lineage_snapshot((
                SourceLineageRecord(forbidden, kind, ()),
                SourceLineageRecord(value.source_sha256, kind, (forbidden,))))
            manifest["lineage_sha256"] = lineage.semantic_sha256
        elif violation == "manifest_class": manifest["source_class"] = "GOLD_REFERENCE_RAW"
        else: manifest["lineage_sha256"] = "0" * 64
        replacement = V2UnprovenPartition(value.source_sha256, kind,
            partition.subject_registry, partition.note_ids, trusted_source_guard_policy(),
            lineage, manifest)
        return V2SourceArtifacts(result.context_snapshots, result.factory_observations,
                                 result.reference_observations, replacement)
    with pytest.raises((ValueError, TypeError), match="lineage|manifest|class|Source"):
        build_context_qualified_database_v2([record], output,
            {"v2_source_artifact_factory": invalid})
    assert semantic_digest_v2(output) == before