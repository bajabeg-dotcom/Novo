from dataclasses import replace
from hashlib import sha256
import json
import sqlite3

import pytest

from rxoptimizer.rhythm_protection_adapters import (
    EXTRACTION_DOMAINS,
    BarPatternObservation,
    NoteObservation,
    SectionObservation,
    SourceLineageRecord,
    StructuralSourceSnapshot,
    TrackObservation,
    complete_extraction_attestation,
    trusted_source_guard_policy,
    trusted_source_lineage_snapshot,
)
from rxoptimizer.rhythm_structural_slots import (
    AcceptedFactoryCorpusAuthorityVerifierPort,
    CalibrationContextPrimitives,
    FactoryStructuralSource,
    StructuralBarPrimitive,
    StructuralClusterPrimitive,
    StructuralIdentityConfig,
    StructuralVoicePrimitive,
    TestOnlyFactoryCorpusAuthorityEvidence as _TestOnlyAuthorityEvidence,
    assert_structural_registry_surface,
    build_structural_registry,
    calibration_context_identity,
    _TestOnlyAcceptedFactoryCorpusAuthorityVerifier as _TestOnlyAuthorityVerifier,
    structural_semantic_digest,
    structural_slot_identity,
    verify_structural_registry,
)
from rxoptimizer.rhythm_context_models import V2_SCHEMA, semantic_digest_v2
from rxoptimizer.rhythm_subject_registry import canonical_json
from rxoptimizer.rhythm_subject_registry import StableSubject, StableSubjectEdge, StableSubjectRegistry


CONFIG = StructuralIdentityConfig(("BASS", "DRUMS", "GUITAR"),
                                  ("ACC_TRACK", "DRUM_TRACK"))


def context(*, policy="TRANSPOSING_LOWEST_ANCHOR", section="VARIATION"):
    return CalibrationContextPrimitives(
        "BASS" if policy != "EXACT_DRUM_LANE" else "DRUMS",
        10, 2, 33, "FINGER_BASS" if policy != "EXACT_DRUM_LANE" else "DRUM_KIT",
        "  Test\u00a0Style  ", section, 1 if section != "BREAK" else None,
        "EXACT", 0, 4, 4, 500000,
        "ACC_TRACK" if policy != "EXACT_DRUM_LANE" else "DRUM_TRACK", policy)


def _sha(tag):
    return sha256(tag.encode()).hexdigest()


def source_fixture(tag, cluster_specs, *, kind="FACTORY_RAW", context_value=None,
                   voice_tokens=None, legacy="legacy-slot"):
    """cluster_specs is ``[(tick, [pitches]), ...]``."""
    source_sha = _sha(f"source:{tag}")
    registry = StableSubjectRegistry()
    meter = _sha(f"meter:{tag}")
    scope = registry.add_subject(StableSubject("EXACT_CONTEXT", source_sha,
        {"exact_context_key": _sha(f"exact:{tag}")}))
    track = registry.add_subject(StableSubject("TRACK_CHANNEL", source_sha,
        {"track_index": 0, "channel": 0}))
    bar_start = min(tick for tick, _pitches in cluster_specs)
    bar = registry.add_subject(StableSubject("BAR", source_sha,
        {"meter_segment_id": meter, "start_tick": bar_start,
         "end_tick": bar_start + 1920}))
    note_rows = []; primitive_clusters = []; member_ids = []
    tokens = voice_tokens or {}
    for cluster_index, (tick, pitches) in enumerate(cluster_specs):
        events = []; notes = []; primitive_voices = []
        for voice_index, pitch in enumerate(pitches):
            event = registry.add_subject(StableSubject("EVENT", source_sha,
                {"event_id": _sha(f"event:{tag}:{cluster_index}:{voice_index}"),
                 "event_kind": "NOTE_ON"}))
            note = registry.add_subject(StableSubject("NOTE", source_sha,
                {"note_id": _sha(f"note:{tag}:{cluster_index}:{voice_index}")}))
            events.append(event); notes.append(note); member_ids.append(note.subject_id)
        cluster = registry.add_subject(StableSubject("ONSET_CLUSTER", source_sha,
            {"track_index": 0, "channel": 0, "meter_segment_id": meter, "tick": tick,
             "on_event_ids": [item.subject_id for item in events]}))
        registry.add_edge(StableSubjectEdge("BAR_CONTAINS_ONSET_CLUSTER", bar.subject_id,
                                            cluster.subject_id, source_sha))
        for voice_index, (pitch, event, note) in enumerate(zip(pitches, events, notes)):
            for edge_type, parent, child in (
                ("TRACK_CHANNEL_CONTAINS_NOTE", track, note),
                ("NOTE_HAS_ON_EVENT", note, event),
                ("ONSET_CLUSTER_CONTAINS_NOTE", cluster, note),
                ("EXACT_CONTEXT_CONTAINS_NOTE", scope, note),
            ):
                registry.add_edge(StableSubjectEdge(edge_type, parent.subject_id,
                                                    child.subject_id, source_sha))
            note_rows.append(NoteObservation(note.subject_id, track.subject_id, None,
                cluster.subject_id, bar.subject_id, meter, pitch, tick, tick + 120,
                bar_start, bar_start + 1920, "METER_EXACT"))
            primitive_voices.append(StructuralVoicePrimitive(
                note.subject_id, event.subject_id, pitch,
                tokens.get((cluster_index, voice_index)), legacy))
        primitive_clusters.append(StructuralClusterPrimitive(cluster.subject_id, tick,
                                                              tuple(primitive_voices)))
    effective_context = context_value or context()
    tracks = (TrackObservation(track.subject_id, 0, 0, role=effective_context.role, role_status="EXACT"),)
    sections = (SectionObservation(track.subject_id, effective_context.section, "EXACT", "RAW_TRACK",
        (bar.subject_id,), {bar.subject_id: tuple(member_ids)}),)
    patterns = (BarPatternObservation(bar.subject_id, track.subject_id, meter,
        _sha(f"rhythm:{tag}"), _sha(f"topology:{tag}"), tuple(member_ids)),)
    domains = {"TRACKS": tracks, "NOTES": tuple(note_rows), "PHRASES": (),
        "SECTIONS": sections, "BOUNDARIES": (), "BAR_PATTERNS": patterns,
        "RX_SUBJECTS": (), "HUMAN_COMPONENTS": ()}
    attestations = tuple(complete_extraction_attestation(name, domains[name])
                         for name in EXTRACTION_DOMAINS)
    lineage = trusted_source_lineage_snapshot((SourceLineageRecord(source_sha, kind, ()),))
    snapshot = StructuralSourceSnapshot(source_sha, kind, registry, scope.subject_id,
        attestations, trusted_source_guard_policy(), lineage, tracks=tracks,
        notes=tuple(note_rows), sections=sections, bar_patterns=patterns,
        source_manifest={"source_class": kind, "lineage_sha256": lineage.semantic_sha256})
    primitive_bar = StructuralBarPrimitive(bar.subject_id, track.subject_id,
        tuple(primitive_clusters), _sha(f"legacy-context:{tag}"), _sha(f"topology:{tag}"))
    return FactoryStructuralSource(snapshot, effective_context, (primitive_bar,))


def accepted_corpus(tmp_path, sources, *, context_overrides=None, quality_overrides=None,
                    omit_sources=(), lineage_overrides=None, manifest_overrides=None):
    """Materialize the external accepted schema-v2 authority used by 013C-S."""
    path = tmp_path / f"accepted-{_sha(':'.join(sorted(s.snapshot.source_sha256 for s in sources)))[:12]}.sqlite3"
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript(V2_SCHEMA)
    db.execute("INSERT INTO build_info VALUES(?,?)", ("schema_version", "2"))
    hashes = [_sha(name) for name in ("build", "protection", "model", "reference", "negative")]
    db.execute("INSERT INTO build_contract_v2 VALUES(?,?,?,?,?,?,?,?,?)", (
        _sha("contract"), "X10_CONTEXT_SCHEMA_V2_RAW_REBUILD_V1", 2, *hashes,
        canonical_json({"accepted_factory_authority": True})))
    context_overrides = context_overrides or {}; quality_overrides = quality_overrides or {}
    lineage_overrides = lineage_overrides or {}; manifest_overrides = manifest_overrides or {}
    for source in sorted(sources, key=lambda item: item.snapshot.source_sha256):
        snapshot = source.snapshot; source_sha = snapshot.source_sha256
        if source_sha in omit_sources:
            continue
        accepted_context = context_overrides.get(source_sha, source.context)
        quality = quality_overrides.get(source_sha, "NORMAL")
        accepted_lineage = lineage_overrides.get(source_sha, snapshot.source_lineage)
        accepted_manifest = manifest_overrides.get(source_sha, dict(snapshot.source_manifest))
        metadata = {
            "instrument_identity": accepted_context.instrument_identity_key,
            "instrument_identity_status": "EXACT", "instrument_identity_method": "CORPUS_REGISTRY",
            "instrument_identity_locator": f"accepted#{source_sha}/instrument",
            "track_channel_role": accepted_context.track_channel_role,
            "track_channel_role_status": "EXACT", "track_channel_role_method": "CORPUS_REGISTRY",
            "track_channel_role_locator": f"accepted#{source_sha}/track-role",
            "voice_policy": accepted_context.voice_policy,
            "voice_policy_status": "EXACT", "voice_policy_method": "STRUCTURAL_POLICY",
            "voice_policy_locator": f"accepted#{source_sha}/voice-policy",
        }
        scope = next(item for item in snapshot.subject_registry.subjects
                     if item.subject_id == snapshot.scope_subject_id)
        exact_key = scope.natural_key["exact_context_key"]
        source_semantic = {"context_snapshots": [{"exact_context_key": exact_key,
            "snapshot_semantic_sha256": snapshot.semantic_sha256,
            "scope_subject_id": snapshot.scope_subject_id,
            "manifest": accepted_manifest}]}
        db.execute("INSERT INTO source_context_v2 VALUES(?,?,?,?,?,?,?,?,?)", (
            source_sha, "factory", "FACTORY_RAW", f"Factory/{source_sha}.mid", quality,
            canonical_json(metadata), accepted_lineage.semantic_sha256,
            snapshot.subject_registry.semantic_digest(), canonical_json(source_semantic)))
        for subject in snapshot.subject_registry.subjects:
            db.execute("INSERT INTO stable_subjects VALUES(?,?,?,?,?,?)", (
                subject.subject_id, source_sha, subject.subject_type, subject.contract_version,
                canonical_json(subject.natural_key), canonical_json(subject.semantic_record)))
        for edge in snapshot.subject_registry.edges:
            semantic = {"contract_version": edge.contract_version, "edge_type": edge.edge_type,
                "source_sha256": edge.source_sha256, "parent_subject_id": edge.parent_subject_id,
                "child_subject_id": edge.child_subject_id, "edge_id": edge.edge_id}
            db.execute("INSERT INTO stable_subject_edges VALUES(?,?,?,?,?,?,?)", (
                edge.edge_id, source_sha, edge.edge_type, edge.contract_version,
                edge.parent_subject_id, edge.child_subject_id, canonical_json(semantic)))
        for bar in source.bars:
            for cluster in bar.clusters:
                for voice in cluster.voices:
                    note_subject = next(item for item in snapshot.subject_registry.subjects
                                        if item.subject_id == voice.note_subject_id)
                    note_context = {
                        "role": accepted_context.role, "role_status": "EXACT",
                        "role_method": "RAW_TRACK", "role_locator": "raw#role",
                        "bank_msb": accepted_context.bank_msb, "bank_lsb": accepted_context.bank_lsb,
                        "program": accepted_context.program, "program_status": "PROGRAM_EXACT",
                        "style_name": accepted_context.style_name, "style_status": "EXPLICIT_METADATA",
                        "style_method": "EXPLICIT_METADATA", "style_locator": "raw#style",
                        "section": accepted_context.section, "section_no": accepted_context.section_no,
                        "section_status": "EXACT", "section_method": "EXPLICIT_METADATA",
                        "section_locator": "raw#section", "cv": accepted_context.cv,
                        "cv_status": "CV_EXACT" if accepted_context.cv_status == "EXACT" else "CV_NOT_APPLICABLE",
                        "cv_method": "EXPLICIT_METADATA", "cv_locator": "raw#cv",
                        "meter_numerator": accepted_context.meter_numerator,
                        "meter_denominator": accepted_context.meter_denominator,
                        "meter_status": "METER_EXACT",
                        "microseconds_per_quarter": accepted_context.microseconds_per_quarter,
                        "tempo_status": "TEMPO_EXACT", "quality_status": quality,
                    }
                    db.execute("INSERT INTO context_eligibility VALUES(?,?,?,?,?,?,?,?)", (
                        source_sha, voice.note_subject_id, note_subject.natural_key["note_id"], exact_key,
                        _sha(f"slot:{voice.note_subject_id}"), "EXACT_CONTEXT_MATCH", quality,
                        canonical_json({"note_context": note_context, "pre_model_rule_statuses": {}})))
    db.commit()
    digest = semantic_digest_v2(path)
    db.execute("INSERT INTO semantic_digest VALUES('SHA256',2,?)", (digest,))
    db.commit(); db.close()
    return _TestOnlyAuthorityVerifier(
        path, digest,
        {source.snapshot.source_sha256: lineage_overrides.get(
            source.snapshot.source_sha256, source.snapshot.source_lineage) for source in sources
         if source.snapshot.source_sha256 not in omit_sources},
        {source.snapshot.source_sha256: manifest_overrides.get(
            source.snapshot.source_sha256, dict(source.snapshot.source_manifest)) for source in sources
         if source.snapshot.source_sha256 not in omit_sources})


def build_registry(sources, path, config=CONFIG, *, accepted_sources=None, **anchor_kwargs):
    accepted = accepted_corpus(path.parent, accepted_sources or sources, **anchor_kwargs)
    return build_structural_registry(sources, path, config, accepted,
                                     allow_test_only_authority=True)


def _fetch(path, sql):
    db = sqlite3.connect(path)
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


def test_topology_preserving_timing_variants_share_context_and_slot(tmp_path):
    first = source_fixture("phase-a", [(0, [60]), (240, [62])])
    second = source_fixture("phase-b", [(31, [65]), (399, [67])])
    path = tmp_path / "structural.sqlite3"
    report = build_registry((first, second), path)
    assert report["resolved_memberships"] == 4 and report["ambiguous_bars"] == 0
    assert _fetch(path, "SELECT COUNT(*) FROM structural_context_registry") == [(1,)]
    assert _fetch(path, "SELECT COUNT(*) FROM structural_slot_registry") == [(2,)]
    identity = _fetch(path, "SELECT identity_json FROM structural_context_registry")[0][0]
    for forbidden in ("tick", "phase", "ioi", "duration", "velocity", "legacy", "topology"):
        assert forbidden not in identity.lower()


def test_identity_api_is_typed_and_rejects_digest_smuggling():
    structure = ((1, (0,)),)
    one = calibration_context_identity(context(), structure, CONFIG)
    with pytest.raises(TypeError):
        calibration_context_identity({"context": context(), "phase_sha256": "0" * 64}, structure, CONFIG)
    with pytest.raises(TypeError):
        structural_slot_identity(one[1], 0, 1, [0], 0, 0, CONFIG)
    assert one == calibration_context_identity(context(), structure, CONFIG)


def test_transposition_aligns_but_inversion_does_not(tmp_path):
    transposed_a = source_fixture("tr-a", [(0, [60, 64, 67])])
    transposed_b = source_fixture("tr-b", [(30, [62, 66, 69])])
    good = tmp_path / "transposition.sqlite3"
    assert build_registry((transposed_a, transposed_b), good)["resolved_memberships"] == 6
    inversion = source_fixture("inv", [(20, [60, 63, 68])])
    bad = tmp_path / "inversion.sqlite3"
    result = build_registry((transposed_a, inversion), bad)
    assert result["resolved_memberships"] == 0 and result["ambiguous_bars"] == 2


@pytest.mark.parametrize("left,right", [
    ([(0, [60, 64, 67])], [(0, [60]), (40, [64]), (80, [67])]),
    ([(0, [60]), (240, [62])], [(0, [60])]),
    ([(0, [60]), (240, [62])], [(0, [60, 62])]),
])
def test_split_merge_insert_delete_and_arpeggiation_are_ambiguous(tmp_path, left, right):
    a = source_fixture(f"left:{left}:{right}", left)
    b = source_fixture(f"right:{left}:{right}", right)
    report = build_registry((a, b), tmp_path / _sha(str(left))[:10])
    assert report["resolved_memberships"] == 0 and report["ambiguous_bars"] == 2


def test_duplicate_unison_without_timing_free_discriminator_is_ambiguous(tmp_path):
    item = source_fixture("unison", [(0, [60, 60])])
    path = tmp_path / "unison.sqlite3"
    report = build_registry((item,), path)
    assert report["resolved_memberships"] == 0
    assert _fetch(path, "SELECT status FROM structural_resolution") == [
        ("STRUCTURAL_DUPLICATE_AMBIGUOUS",)]


def test_duplicate_unison_with_arbitrary_tokens_remains_ambiguous(tmp_path):
    item = source_fixture("unison-ok", [(0, [60, 60])],
                          voice_tokens={(0, 0): "VOICE_A", (0, 1): "VOICE_B"})
    report = build_registry((item,), tmp_path / "unison-ok.sqlite3")
    assert report["resolved_memberships"] == 0
    assert _fetch(tmp_path / "unison-ok.sqlite3", "SELECT status FROM structural_resolution") == [
        ("STRUCTURAL_DUPLICATE_AMBIGUOUS",)]


@pytest.mark.parametrize("tokens", [
    {(0, 0): "V000123", (0, 1): "V000124"},
    {(0, 0): "ORDER_0001", (0, 1): "ORDER_0002"},
    {(0, 0): "VOICE_A", (0, 1): "VOICE_B"},
])
def test_unison_cannot_smuggle_timing_or_parser_order_through_tokens(tmp_path, tokens):
    item = source_fixture(f"unison-smuggle:{tokens}", [(123, [60, 60])], voice_tokens=tokens)
    path = tmp_path / f"unison-{_sha(str(tokens))[:8]}.sqlite3"
    report = build_registry((item,), path)
    assert report["resolved_memberships"] == 0
    assert _fetch(path, "SELECT status FROM structural_resolution") == [
        ("STRUCTURAL_DUPLICATE_AMBIGUOUS",)]


def test_caller_voice_tokens_do_not_change_unique_pitch_identity(tmp_path):
    tokens = {(0, 0): "VOICE_A", (0, 1): "VOICE_B",
              (1, 0): "VOICE_B", (1, 1): "VOICE_A"}
    item = source_fixture("crossing", [(0, [60, 64]), (240, [60, 64])], voice_tokens=tokens)
    path = tmp_path / "crossing.sqlite3"
    assert build_registry((item,), path)["resolved_memberships"] == 4


def test_exact_drum_lane_is_not_transposed(tmp_path):
    drum_context = context(policy="EXACT_DRUM_LANE")
    first = source_fixture("drum-a", [(0, [36, 42])], context_value=drum_context)
    second = source_fixture("drum-b", [(10, [38, 44])], context_value=drum_context)
    report = build_registry((first, second), tmp_path / "drums.sqlite3")
    assert report["resolved_memberships"] == 0


def test_untrusted_authority_is_rejected_before_database(tmp_path):
    item = source_fixture("synthetic", [(0, [60])], kind="SYNTHETIC_TEST")
    path = tmp_path / "synthetic.sqlite3"
    with pytest.raises(ValueError, match="root/class|FACTORY_RAW"):
        build_registry((item,), path)
    assert not path.exists()


def test_self_declared_factory_absent_from_accepted_corpus_is_rejected(tmp_path):
    accepted_source = source_fixture("accepted-authority", [(0, [60])])
    masquerade = source_fixture("self-declared-factory", [(0, [60])])
    anchor = accepted_corpus(tmp_path, (accepted_source,))
    path = tmp_path / "masquerade.sqlite3"
    with pytest.raises(ValueError, match="absent from the accepted schema-v2 corpus"):
        build_structural_registry((masquerade,), path, CONFIG, anchor,
                                  allow_test_only_authority=True)
    assert not path.exists()


def test_normal_quality_must_come_from_accepted_quality_registry(tmp_path):
    item = source_fixture("forged-normal", [(0, [60])])
    anchor = accepted_corpus(tmp_path, (item,),
                             quality_overrides={item.snapshot.source_sha256: "RARE"})
    with pytest.raises(ValueError, match="NORMAL quality"):
        build_structural_registry((item,), tmp_path / "forged-normal.sqlite3", CONFIG, anchor,
                                  allow_test_only_authority=True)


def test_accepted_schema_v2_anchor_is_byte_pinned_after_load(tmp_path):
    item = source_fixture("pinned", [(0, [60])])
    anchor = accepted_corpus(tmp_path, (item,))
    db = sqlite3.connect(anchor.test_database_path)
    try:
        db.execute("UPDATE build_info SET value_json='2' WHERE key='schema_version'")
        db.execute("INSERT OR REPLACE INTO build_info VALUES('tamper','true')")
        db.commit()
    finally:
        db.close()
    with pytest.raises(ValueError, match="changed after verifier pinning"):
        build_structural_registry((item,), tmp_path / "tampered-anchor.sqlite3", CONFIG, anchor,
                                  allow_test_only_authority=True)


def test_accepted_schema_v2_requires_external_expected_semantic_root(tmp_path):
    item = source_fixture("wrong-root", [(0, [60])])
    anchor = accepted_corpus(tmp_path, (item,))
    wrong = _TestOnlyAuthorityVerifier(
        anchor.test_database_path, _sha("not-accepted-root"),
        {item.snapshot.source_sha256: item.snapshot.source_lineage},
        {item.snapshot.source_sha256: dict(item.snapshot.source_manifest)})
    with pytest.raises(ValueError, match="semantic root mismatch"):
        wrong.verify_factory_corpus_authority()


def test_missing_production_authority_port_fails_closed(tmp_path):
    item = source_fixture("missing-port", [(0, [60])])
    with pytest.raises(TypeError, match="VerifierPort is mandatory"):
        build_structural_registry((item,), tmp_path / "missing-port.sqlite3", CONFIG, None)


def test_self_minted_test_authority_cannot_auto_promote_to_production(tmp_path):
    item = source_fixture("self-minted-test", [(0, [60])])
    verifier = accepted_corpus(tmp_path, (item,))
    with pytest.raises(ValueError, match="NOT_PROVABLE"):
        build_structural_registry((item,), tmp_path / "not-production.sqlite3", CONFIG, verifier)


def test_custom_verifier_cannot_forge_production_scope_for_build_or_verify(tmp_path):
    item = source_fixture("forged-production-scope", [(0, [60])])
    test_verifier = accepted_corpus(tmp_path, (item,))
    evidence = test_verifier.verify_factory_corpus_authority()
    forged = object.__new__(_TestOnlyAuthorityEvidence)
    for field in ("authority_id", "database_path", "database_sha256",
                  "schema_v2_semantic_digest", "build_config_sha256", "sources"):
        object.__setattr__(forged, field, getattr(evidence, field))
    object.__setattr__(forged, "authority_scope", "PRODUCTION")

    class ForgedVerifier(AcceptedFactoryCorpusAuthorityVerifierPort):
        def verify_factory_corpus_authority(self):
            return forged

    verifier = ForgedVerifier(); path = tmp_path / "forged-production.sqlite3"
    with pytest.raises(ValueError, match="NOT_PROVABLE"):
        build_structural_registry((item,), path, CONFIG, verifier,
                                  allow_test_only_authority=True)
    assert not path.exists()
    valid = tmp_path / "test-only-valid.sqlite3"
    build_structural_registry((item,), valid, CONFIG, test_verifier,
                              allow_test_only_authority=True)
    with pytest.raises(ValueError, match="NOT_PROVABLE"):
        verify_structural_registry(valid, verifier, allow_test_only_authority=True)


def test_authority_port_recomputes_full_lineage_closure_and_forbidden_matrix(tmp_path):
    item = source_fixture("forbidden-ancestor", [(0, [60])])
    source_sha = item.snapshot.source_sha256; parent_sha = _sha("optimizer-parent")
    with pytest.raises(ValueError, match="Illegal lineage parent class"):
        trusted_source_lineage_snapshot((
            SourceLineageRecord(parent_sha, "GOLD_REFERENCE_RAW", ()),
            SourceLineageRecord(source_sha, "FACTORY_RAW", (parent_sha,)),
        ))


@pytest.mark.parametrize("field,value", [
    ("role", "GUITAR"), ("bank_msb", 99), ("bank_lsb", 88), ("program", 77),
    ("instrument_identity_key", "FORGED_IDENTITY"), ("style_name", "Forged Style"),
    ("section", "INTRO"), ("section_no", 9), ("cv", 7),
    ("meter_numerator", 7), ("meter_denominator", 8),
    ("microseconds_per_quarter", 666666), ("track_channel_role", "DRUM_TRACK"),
    ("voice_policy", "EXACT_DRUM_LANE"),
])
def test_every_identity_context_dimension_is_reconstructed_not_caller_claimed(tmp_path, field, value):
    accepted_source = source_fixture(f"context-anchor:{field}", [(0, [60])])
    forged_context = replace(accepted_source.context, **{field: value})
    forged = replace(accepted_source, context=forged_context)
    path = tmp_path / f"forged-{field}.sqlite3"
    report = build_registry((forged,), path, accepted_sources=(accepted_source,))
    assert report["resolved_memberships"] == 0 and report["ambiguous_bars"] == 1
    assert _fetch(path, "SELECT status FROM structural_resolution") == [
        ("STRUCTURAL_CONTEXT_UNPROVEN",)]
    assert _fetch(path, "SELECT COUNT(*) FROM structural_context_registry") == [(0,)]


def test_source_local_subject_edges_are_recomputed(tmp_path):
    item = source_fixture("edges", [(0, [60])])
    voice = item.bars[0].clusters[0].voices[0]
    forged_voice = StructuralVoicePrimitive(voice.note_subject_id, _sha("not-the-event"), 60)
    forged_cluster = StructuralClusterPrimitive(item.bars[0].clusters[0].onset_cluster_subject_id,
                                                0, (forged_voice,))
    forged_bar = StructuralBarPrimitive(item.bars[0].bar_subject_id,
                                        item.bars[0].track_channel_subject_id, (forged_cluster,))
    forged = FactoryStructuralSource(item.snapshot, item.context, (forged_bar,))
    with pytest.raises(ValueError, match="NOTE/NOTE_ON"):
        build_registry((forged,), tmp_path / "forged.sqlite3", accepted_sources=(item,))


def test_one_observation_per_source_bar_slot_and_foreign_keys(tmp_path):
    item = source_fixture("unique", [(0, [60, 64, 67])])
    path = tmp_path / "unique.sqlite3"
    verifier = accepted_corpus(tmp_path, (item,))
    build_structural_registry((item,), path, CONFIG, verifier, allow_test_only_authority=True)
    assert _fetch(path, "SELECT COUNT(*),COUNT(DISTINCT source_sha256||bar_subject_id||structural_event_slot_key) FROM structural_slot_memberships") == [(3, 3)]
    assert _fetch(path, "PRAGMA foreign_key_check") == []
    assert _fetch(path, "PRAGMA integrity_check") == [("ok",)]
    assert verify_structural_registry(
        path, verifier, allow_test_only_authority=True) == {
            "semantic_digest": structural_semantic_digest(path), "contexts": 1, "slots": 3,
            "authority_scope": "TEST_ONLY", "production_authority_status": "NOT_PROVABLE",
            "calibration_envelope_allowed": False, "memberships": 3}


def test_verifier_rejects_rehashed_but_forged_membership_provenance(tmp_path):
    item = source_fixture("verify-forgery", [(0, [60])])
    path = tmp_path / "verify-forgery.sqlite3"
    verifier = accepted_corpus(tmp_path, (item,))
    build_structural_registry((item,), path, CONFIG, verifier, allow_test_only_authority=True)
    db = sqlite3.connect(path)
    try:
        row = db.execute("SELECT provenance_json FROM structural_slot_memberships").fetchone()
        provenance = json.loads(row[0]); provenance["note_subject_id"] = _sha("forged-note")
        db.execute("UPDATE structural_slot_memberships SET provenance_json=?", (canonical_json(provenance),))
        db.commit()
        forged_root = structural_semantic_digest(path)
        db.execute("UPDATE semantic_root SET digest=? WHERE algorithm='SHA256'", (forged_root,))
        db.commit()
    finally:
        db.close()
    with pytest.raises(ValueError, match="provenance row mismatch"):
        verify_structural_registry(path, verifier, allow_test_only_authority=True)


@pytest.mark.parametrize("mutation", [
    "UPDATE source_registry SET manifest_json='{}'",
    "UPDATE source_registry SET lineage_sha256='" + ("f" * 64) + "'",
    "UPDATE source_registry SET accepted_schema_v2_sha256='" + ("e" * 64) + "'",
    "UPDATE accepted_source_proofs SET source_semantic_json='{}'",
    "UPDATE accepted_lineage_records SET semantic_json='{}'",
    "UPDATE stable_subjects SET semantic_json='{}' WHERE subject_type='NOTE'",
    "UPDATE stable_edges SET semantic_json='{}' WHERE edge_type='NOTE_HAS_ON_EVENT'",
])
def test_external_authority_rejects_rehashed_source_lineage_subject_edge_tampering(
        tmp_path, mutation):
    item = source_fixture(f"rehashed:{mutation}", [(0, [60])])
    path = tmp_path / f"rehashed-{_sha(mutation)[:8]}.sqlite3"
    verifier = accepted_corpus(tmp_path, (item,))
    build_structural_registry((item,), path, CONFIG, verifier, allow_test_only_authority=True)
    db = sqlite3.connect(path)
    try:
        db.execute(mutation)
        db.commit()
        db.execute("UPDATE semantic_root SET digest=? WHERE algorithm='SHA256'",
                   (structural_semantic_digest(path),))
        db.commit()
    finally:
        db.close()
    with pytest.raises(ValueError):
        verify_structural_registry(path, verifier, allow_test_only_authority=True)


def test_deterministic_permutation_semantic_digest(tmp_path):
    items = (source_fixture("perm-a", [(0, [60]), (240, [62])]),
             source_fixture("perm-b", [(20, [65]), (300, [67])]))
    first = tmp_path / "first.sqlite3"; second = tmp_path / "second.sqlite3"
    anchor = accepted_corpus(tmp_path, items)
    one = build_structural_registry(items, first, CONFIG, anchor, allow_test_only_authority=True)
    two = build_structural_registry(tuple(reversed(items)), second, CONFIG, anchor,
                                    allow_test_only_authority=True)
    assert one["semantic_digest"] == two["semantic_digest"]
    assert structural_semantic_digest(first) == structural_semantic_digest(second)
    assert first.read_bytes() == second.read_bytes()


def test_atomic_failure_preserves_accepted_database(tmp_path):
    path = tmp_path / "atomic.sqlite3"
    accepted = source_fixture("accepted", [(0, [60])])
    anchor = accepted_corpus(tmp_path, (accepted,))
    build_structural_registry((accepted,), path, CONFIG, anchor, allow_test_only_authority=True)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="only once"):
        build_structural_registry((accepted, accepted), path, CONFIG, anchor,
                                  allow_test_only_authority=True)
    assert path.read_bytes() == before and not (tmp_path / "atomic.sqlite3.tmp").exists()


def test_static_surface_and_provenance_identity_separation(tmp_path):
    item = source_fixture("surface", [(123, [60])], legacy="phase-bearing-private-value")
    path = tmp_path / "surface.sqlite3"
    report = build_registry((item,), path)
    assert report["capability"] == "ANALYZE_ONLY" and report["mutation_capability"] == "NONE"
    assert report["authority_scope"] == "TEST_ONLY"
    assert report["production_authority_status"] == "NOT_PROVABLE"
    assert report["calibration_envelope_allowed"] is False
    assert_structural_registry_surface(path)
    identity = _fetch(path, "SELECT identity_json FROM structural_slot_registry")[0][0]
    provenance = _fetch(path, "SELECT provenance_json FROM structural_slot_memberships")[0][0]
    assert "phase-bearing-private-value" not in identity
    assert "phase-bearing-private-value" in provenance


def test_closed_context_domains_fail_unproven_before_materialization(tmp_path):
    bad_context = CalibrationContextPrimitives("UNKNOWN", 0, 0, 0, "X", "Style",
        "OTHER_EXACT", None, "NONE", None, 4, 4, 500000, "ACC_TRACK",
        "TRANSPOSING_LOWEST_ANCHOR")
    item = source_fixture("bad-role", [(0, [60])], context_value=bad_context)
    path = tmp_path / "bad-role.sqlite3"
    report = build_registry((item,), path)
    assert report["resolved_memberships"] == 0 and report["ambiguous_bars"] == 1
    assert _fetch(path, "SELECT status FROM structural_resolution") == [
        ("STRUCTURAL_CONTEXT_UNPROVEN",)]


def test_style_and_tempo_identity_are_canonical():
    a = context()
    b = CalibrationContextPrimitives(a.role, a.bank_msb, a.bank_lsb, a.program,
        a.instrument_identity_key, "test style", a.section, a.section_no, a.cv_status,
        a.cv, a.meter_numerator, a.meter_denominator, a.microseconds_per_quarter,
        a.track_channel_role, a.voice_policy)
    structure = ((1, (0,)),)
    assert calibration_context_identity(a, structure, CONFIG) == calibration_context_identity(b, structure, CONFIG)