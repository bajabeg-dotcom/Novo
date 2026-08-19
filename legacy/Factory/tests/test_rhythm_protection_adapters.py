from dataclasses import fields, replace

import pytest

from rxoptimizer.rhythm_protection import (
    ProtectionEvidenceRegistry,
    sparse_rule_status,
)
from rxoptimizer.rhythm_protection_adapters import (
    AdapterEmission,
    ALLOWED_LINEAGE_PARENT_CLASSES,
    BarPatternObservation,
    BoundaryObservation,
    EXTRACTION_DOMAINS,
    EXTRACTOR_VERSION_BY_DOMAIN,
    ExtractionAttestation,
    HumanValidatedComponent,
    LINEAGE_CLASS_MATRIX_VERSION,
    NoteObservation,
    PhraseObservation,
    RX_DNC_EVIDENCE_VERSION,
    RxDncClaim,
    RxDncEvidenceSnapshot,
    RxSubjectObservation,
    SectionObservation,
    SIX_SONG_FORBIDDEN_SHA256S,
    SOURCE_GUARD_POLICY_VERSION,
    SOURCE_LINEAGE_VERIFIER_VERSION,
    SourceGuardPolicy,
    SourceLineageRecord,
    StructuralSourceSnapshot,
    TrackObservation,
    build_pre_model_adapter_emissions,
    complete_extraction_attestation,
    factory_reference_conflict_deferred,
    local_repeated_pattern_adapter,
    ornament_trill_grace_adapter,
    rx_dnc_adapter,
    rx_dnc_claims_sha256,
    section_transition_adapter,
    tempo_meter_boundary_adapter,
    trusted_source_guard_policy,
    trusted_source_lineage_snapshot,
    TrustedSourceLineageSnapshot,
    lineage_inventory_sha256,
    lineage_class_matrix_sha256,
)
from rxoptimizer.rhythm_subject_registry import (
    StableSubject,
    StableSubjectEdge,
    StableSubjectRegistry,
)


SOURCE = "1" * 64
OTHER = "2" * 64
METER = "3" * 64
RHYTHM = "4" * 64
TOPOLOGY = "5" * 64
EVIDENCE = "6" * 64


def _subject(registry, subject_type, **key):
    return registry.add_subject(StableSubject(subject_type, SOURCE, key))


def source_fixture(*, rx_evidence=None, source_kind="FACTORY_RAW", lineage_kind=None,
                   manifest=None, grace_component_kind="GRACE"):
    registry = StableSubjectRegistry()
    scope = _subject(registry, "EXACT_CONTEXT", scope="source", version=1)
    melody_track = _subject(registry, "TRACK_CHANNEL", track_index=0, channel=0)
    guitar_track = _subject(registry, "TRACK_CHANNEL", track_index=1, channel=1)
    drum_track = _subject(registry, "TRACK_CHANNEL", track_index=2, channel=9)
    guitar_command = _subject(registry, "EVENT", event_id="guitar-command", event_kind="CONTROL")
    guitar_program = _subject(registry, "PROGRAM_SEGMENT", track_index=1, channel=1,
                              bank_msb=1, bank_lsb=2, program=3,
                              program_status="PROGRAM_EXACT")
    bar_one = _subject(registry, "BAR", meter_segment_id=METER, start_tick=0, end_tick=100)
    bar_two = _subject(registry, "BAR", meter_segment_id=METER, start_tick=100, end_tick=200)
    bar_three = _subject(registry, "BAR", meter_segment_id=METER, start_tick=200, end_tick=300)

    note_specs = [
        ("m1", melody_track, 60, 10, 20, bar_one),
        ("m2", melody_track, 62, 30, 40, bar_one),
        ("m3", melody_track, 60, 50, 60, bar_one),
        ("m4", melody_track, 62, 90, 110, bar_one),
        ("m5", melody_track, 65, 120, 125, bar_two),
        ("g1", guitar_track, 55, 25, 45, bar_one),
        ("d1", drum_track, 38, 210, 215, bar_three),
        ("d2", drum_track, 38, 220, 225, bar_three),
        ("d3", drum_track, 42, 230, 235, bar_three),
    ]
    subjects = {}
    clusters = {}
    for name, _track, _pitch, tick, _end, _bar in note_specs:
        event = _subject(registry, "EVENT", event_id=f"{name}-on", event_kind="NOTE_ON")
        note = _subject(registry, "NOTE", note_id=name)
        cluster = _subject(registry, "ONSET_CLUSTER", track_index=_track.natural_key["track_index"],
                           channel=_track.natural_key["channel"], meter_segment_id=METER,
                           tick=tick, on_event_ids=[event.subject_id])
        subjects[name] = note
        clusters[name] = cluster

    melody_phrase = _subject(registry, "PHRASE", track_index=0, channel=0,
                              meter_segment_id=METER,
                              ordered_note_ids=[subjects[name].subject_id
                                                for name in ("m1", "m2", "m3", "m4", "m5")])
    guitar_phrase = _subject(registry, "PHRASE", track_index=1, channel=1,
                              meter_segment_id=METER,
                              ordered_note_ids=[subjects["g1"].subject_id])
    drum_phrase = _subject(registry, "PHRASE", track_index=2, channel=9,
                            meter_segment_id=METER,
                            ordered_note_ids=[subjects[name].subject_id for name in ("d1", "d2", "d3")])
    grace_component = _subject(registry, "COMPONENT", track_index=0, channel=0,
                                meter_segment_id=METER, component_kind=grace_component_kind,
                                ordered_note_ids=[subjects["m5"].subject_id])
    boundary = _subject(registry, "BOUNDARY", boundary_kind="TEMPO", tick=100)

    for track, names in ((melody_track, ("m1", "m2", "m3", "m4", "m5")),
                         (guitar_track, ("g1",)),
                         (drum_track, ("d1", "d2", "d3"))):
        for name in names:
            registry.add_edge(StableSubjectEdge("TRACK_CHANNEL_CONTAINS_NOTE",
                track.subject_id, subjects[name].subject_id, SOURCE))

    phrase_by_name = {
        **{name: melody_phrase for name in ("m1", "m2", "m3", "m4", "m5")},
        "g1": guitar_phrase,
        **{name: drum_phrase for name in ("d1", "d2", "d3")},
    }
    notes = []
    for name, track, pitch, start, end, bar in note_specs:
        notes.append(NoteObservation(subjects[name].subject_id, track.subject_id,
            phrase_by_name[name].subject_id, clusters[name].subject_id, bar.subject_id, METER,
            pitch, start, end, bar.natural_key["start_tick"],
            bar.natural_key["end_tick"], "METER_EXACT"))
    phrases = (
        PhraseObservation(melody_phrase.subject_id, melody_track.subject_id,
                          tuple(subjects[name].subject_id for name in ("m1", "m2", "m3", "m4", "m5"))),
        PhraseObservation(guitar_phrase.subject_id, guitar_track.subject_id,
                          (subjects["g1"].subject_id,)),
        PhraseObservation(drum_phrase.subject_id, drum_track.subject_id,
                          tuple(subjects[name].subject_id for name in ("d1", "d2", "d3"))),
    )
    tracks = (
        TrackObservation(melody_track.subject_id, 0, 0, role="MELODY", role_status="EXACT"),
        TrackObservation(guitar_track.subject_id, 1, 1, role="GUITAR", role_status="EXACT",
                         track_type="GTR", track_type_status="EXACT",
                         command_subject_ids=(guitar_command.subject_id,)),
        TrackObservation(drum_track.subject_id, 2, 9, role="PERCUSSION", role_status="EXACT",
                         instrument_class="DRUM_KIT", instrument_class_status="EXACT"),
    )
    sections = (
        SectionObservation(melody_track.subject_id, "VARIATION", "EXACT", "RAW_TRACK",
                           (bar_one.subject_id, bar_two.subject_id), {
                               bar_one.subject_id: tuple(subjects[name].subject_id
                                                        for name in ("m1", "m2", "m3", "m4")),
                               bar_two.subject_id: (subjects["m5"].subject_id,),
                           }),
        SectionObservation(drum_track.subject_id, "FILL", "EXACT", "RAW_TRACK",
                           (bar_three.subject_id,), {
                               bar_three.subject_id: tuple(subjects[name].subject_id
                                                          for name in ("d1", "d2", "d3")),
                           }),
        SectionObservation(guitar_track.subject_id, "VARIATION", "EXACT", "RAW_TRACK",
                           (bar_one.subject_id,), {
                               bar_one.subject_id: (subjects["g1"].subject_id,),
                           }),
    )
    boundaries = (BoundaryObservation(boundary.subject_id, "TEMPO", "CHANGE_EXACT", 100,
                                      (bar_two.subject_id, subjects["m4"].subject_id)),)
    patterns = (
        BarPatternObservation(bar_one.subject_id, melody_track.subject_id, METER, RHYTHM, TOPOLOGY,
                              tuple(subjects[name].subject_id for name in ("m1", "m2", "m3", "m4"))),
        BarPatternObservation(bar_two.subject_id, melody_track.subject_id, METER, RHYTHM, TOPOLOGY,
                              (subjects["m5"].subject_id,)),
        BarPatternObservation(bar_one.subject_id, guitar_track.subject_id, METER, RHYTHM, TOPOLOGY,
                              (subjects["g1"].subject_id,)),
        BarPatternObservation(bar_three.subject_id, drum_track.subject_id, METER,
                              "8" * 64, "9" * 64,
                              tuple(subjects[name].subject_id for name in ("d1", "d2", "d3"))),
    )
    human = (HumanValidatedComponent("GRACE", grace_component.subject_id,
                                     (subjects["m5"].subject_id,), SOURCE, EVIDENCE,
                                     "pa800:test:grace"),)
    registry.add_edge(StableSubjectEdge("PROGRAM_SEGMENT_CONTAINS_NOTE",
        guitar_program.subject_id, subjects["g1"].subject_id, SOURCE))
    registry.add_edge(StableSubjectEdge("BOUNDARY_TOUCHES_BAR", boundary.subject_id,
        bar_two.subject_id, SOURCE))
    registry.add_edge(StableSubjectEdge("BOUNDARY_TOUCHES_NOTE", boundary.subject_id,
        subjects["m4"].subject_id, SOURCE))
    domain_records = {
        "TRACKS": tracks, "NOTES": tuple(notes), "PHRASES": phrases,
        "SECTIONS": sections, "BOUNDARIES": boundaries, "BAR_PATTERNS": patterns,
        "RX_SUBJECTS": (RxSubjectObservation(subjects["g1"].subject_id,
                                              guitar_program.subject_id,
                                              "PROGRAM_EXACT", 1, 2, 3),),
        "HUMAN_COMPONENTS": human,
    }
    attestations = tuple(complete_extraction_attestation(domain, domain_records[domain])
                         for domain in EXTRACTION_DOMAINS)
    lineage = trusted_source_lineage_snapshot((
        SourceLineageRecord(SOURCE, lineage_kind or source_kind, ()),))
    manifest_value = dict(manifest or {"source_class": source_kind})
    manifest_value.setdefault("lineage_sha256", lineage.semantic_sha256)
    snapshot = StructuralSourceSnapshot(SOURCE, source_kind, registry, scope.subject_id,
        attestations, trusted_source_guard_policy(), lineage,
        tracks=tracks, notes=tuple(notes), phrases=phrases, sections=sections,
        boundaries=boundaries, bar_patterns=patterns,
        rx_subjects=domain_records["RX_SUBJECTS"],
        human_components=human, rx_evidence=rx_evidence,
        source_manifest=manifest_value)
    return snapshot, {
        "scope": scope.subject_id,
        "melody_track": melody_track.subject_id,
        "guitar_track": guitar_track.subject_id,
        "drum_track": drum_track.subject_id,
        "command": guitar_command.subject_id,
        "program_segment": guitar_program.subject_id,
        "input_registry": registry,
        "bar1": bar_one.subject_id,
        "bar2": bar_two.subject_id,
        "bar3": bar_three.subject_id,
        "boundary": boundary.subject_id,
        "grace": grace_component.subject_id,
        **{name: value.subject_id for name, value in subjects.items()},
    }


def reattested(snapshot, **changes):
    values = {
        "TRACKS": changes.get("tracks", snapshot.tracks),
        "NOTES": changes.get("notes", snapshot.notes),
        "PHRASES": changes.get("phrases", snapshot.phrases),
        "SECTIONS": changes.get("sections", snapshot.sections),
        "BOUNDARIES": changes.get("boundaries", snapshot.boundaries),
        "BAR_PATTERNS": changes.get("bar_patterns", snapshot.bar_patterns),
        "RX_SUBJECTS": changes.get("rx_subjects", snapshot.rx_subjects),
        "HUMAN_COMPONENTS": changes.get("human_components", snapshot.human_components),
    }
    changes["extraction_attestations"] = tuple(
        complete_extraction_attestation(domain, values[domain]) for domain in EXTRACTION_DOMAINS)
    return replace(snapshot, **changes)


def installed(snapshot):
    evidence = ProtectionEvidenceRegistry(snapshot.subject_registry)
    emissions = build_pre_model_adapter_emissions(snapshot)
    for emission in emissions:
        emission.install(evidence)
    return emissions, evidence


def test_all_adapters_emit_contract_valid_sparse_analyze_only_records():
    snapshot, ids = source_fixture()
    emissions, evidence = installed(snapshot)
    assert len(emissions) == 9
    assert {item.run.contract.rule_key for item in emissions} == {
        "GUITAR_MODE", "RX_DNC", "ORNAMENT_TRILL_GRACE", "DRUM_FLAM_ROLL_GHOST",
        "CROSS_BAR", "SECTION_TRANSITION", "TEMPO_METER_BOUNDARY",
        "LOCAL_REPEATED_PATTERN", "FACTORY_REFERENCE_CONFLICT",
    }
    assert all(item.capability == "ANALYZE_ONLY" and item.mutation_capability == "NONE"
               for item in emissions)
    assert sparse_rule_status(evidence, ids["guitar_track"], "GUITAR_MODE") == "DETECTED"
    assert sparse_rule_status(evidence, ids["g1"], "RX_DNC") == "DEPENDENCY_GAP"
    assert sparse_rule_status(evidence, ids["m1"], "ORNAMENT_TRILL_GRACE") == "DETECTED"
    assert sparse_rule_status(evidence, ids["guitar_track"], "ORNAMENT_TRILL_GRACE") == "AMBIGUOUS"
    assert sparse_rule_status(evidence, ids["d1"], "DRUM_FLAM_ROLL_GHOST") == "DETECTED"
    assert sparse_rule_status(evidence, ids["d3"], "DRUM_FLAM_ROLL_GHOST") == "AMBIGUOUS"
    assert sparse_rule_status(evidence, ids["m4"], "CROSS_BAR") == "DETECTED"
    assert sparse_rule_status(evidence, ids["bar1"], "SECTION_TRANSITION") == "DETECTED"
    assert sparse_rule_status(evidence, ids["boundary"], "TEMPO_METER_BOUNDARY") == "DETECTED"
    assert sparse_rule_status(evidence, ids["m5"], "LOCAL_REPEATED_PATTERN") == "DETECTED"
    assert sparse_rule_status(evidence, ids["g1"], "LOCAL_REPEATED_PATTERN") == "CLEAR"
    assert sparse_rule_status(evidence, ids["scope"], "FACTORY_REFERENCE_CONFLICT") == "DEFERRED"
    clear_rows = [group for group in evidence.groups.values()
                  if group.per_rule_status in {"CLEAR", "NOT_APPLICABLE"}]
    assert clear_rows == []


def test_adapter_output_is_deterministic_and_does_not_change_snapshot():
    snapshot, _ids = source_fixture()
    before = snapshot.semantic_sha256
    first = build_pre_model_adapter_emissions(snapshot)
    second = build_pre_model_adapter_emissions(snapshot)
    assert snapshot.semantic_sha256 == before
    assert [item.run.run_id for item in first] == [item.run.run_id for item in second]
    assert [item.run.result_sha256 for item in first] == [item.run.result_sha256 for item in second]
    assert [[group.group_id for group in item.groups] for item in first] == [
        [group.group_id for group in item.groups] for item in second]


def test_rx_dnc_is_fail_closed_without_dependency_and_exact_with_confirmed_claims():
    snapshot, ids = source_fixture()
    dependency_gap = rx_dnc_adapter(snapshot)
    assert dependency_gap.run.run_status == "DEPENDENCY_UNAVAILABLE"
    assert dependency_gap.scanned_subject_ids == ()

    claim = RxDncClaim((1, 2, 3), "CONFIRMED_RX_COMPLETE", EVIDENCE,
                       "manual:rx-zone", (ids["g1"],))
    evidence_snapshot = RxDncEvidenceSnapshot(RX_DNC_EVIDENCE_VERSION,
                                               rx_dnc_claims_sha256((claim,)), (claim,))
    confirmed, _ = source_fixture(rx_evidence=evidence_snapshot)
    emission = rx_dnc_adapter(confirmed)
    registry = ProtectionEvidenceRegistry(confirmed.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["g1"], "RX_DNC") == "DETECTED"

    non_rx_claims = (RxDncClaim((1, 2, 3), "CONFIRMED_NON_RX", EVIDENCE,
                                "manual:non-rx"),)
    non_rx = RxDncEvidenceSnapshot(RX_DNC_EVIDENCE_VERSION,
                                   rx_dnc_claims_sha256(non_rx_claims), non_rx_claims)
    clear_snapshot, _ = source_fixture(rx_evidence=non_rx)
    clear = rx_dnc_adapter(clear_snapshot)
    registry = ProtectionEvidenceRegistry(clear_snapshot.subject_registry)
    clear.install(registry)
    assert sparse_rule_status(registry, ids["g1"], "RX_DNC") == "CLEAR"


@pytest.mark.parametrize("status", [
    "CONFIRMED_RX_INCOMPLETE", "UNKNOWN", "CONFLICT", "CATALOG_ONLY",
])
def test_rx_dnc_incomplete_unknown_conflict_and_catalog_never_become_clear(status):
    claim = RxDncClaim((1, 2, 3), status, EVIDENCE, f"evidence:{status}")
    evidence_snapshot = RxDncEvidenceSnapshot(RX_DNC_EVIDENCE_VERSION,
                                               rx_dnc_claims_sha256((claim,)), (claim,))
    snapshot, ids = source_fixture(rx_evidence=evidence_snapshot)
    emission = rx_dnc_adapter(snapshot)
    registry = ProtectionEvidenceRegistry(snapshot.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["g1"], "RX_DNC") == "AMBIGUOUS"


def test_rx_missing_exact_address_claim_is_evidence_unjoinable_not_clear():
    evidence_snapshot = RxDncEvidenceSnapshot(RX_DNC_EVIDENCE_VERSION,
                                               rx_dnc_claims_sha256(()), ())
    snapshot, ids = source_fixture(rx_evidence=evidence_snapshot)
    emission = rx_dnc_adapter(snapshot)
    registry = ProtectionEvidenceRegistry(snapshot.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["g1"], "RX_DNC") == "EVIDENCE_UNJOINABLE"


def test_strict_trill_requires_four_alternating_notes_and_grace_requires_human_evidence():
    snapshot, ids = source_fixture()
    emission = ornament_trill_grace_adapter(snapshot)
    registry = ProtectionEvidenceRegistry(snapshot.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["m1"], "ORNAMENT_TRILL_GRACE") == "DETECTED"
    assert sparse_rule_status(registry, ids["m4"], "ORNAMENT_TRILL_GRACE") == "DETECTED"
    assert sparse_rule_status(registry, ids["m5"], "ORNAMENT_TRILL_GRACE") == "DETECTED"
    assert sparse_rule_status(registry, ids["guitar_track"], "ORNAMENT_TRILL_GRACE") == "AMBIGUOUS"
    assert not any("duration" in canonical for canonical in
                   (str(group.group_natural_key).lower() for group in emission.groups))


def test_missing_phrase_membership_is_core_contract_failure_not_musical_ambiguity():
    snapshot, _ids = source_fixture()
    bad_note = replace(snapshot.notes[0], phrase_subject_id=None)
    bad_notes = (bad_note, *snapshot.notes[1:])
    # Registry data is still valid; the adapter-specific core dependency is not.
    with pytest.raises(ValueError, match="PHRASE membership"):
        reattested(snapshot, notes=bad_notes,
                   phrases=(replace(snapshot.phrases[0],
                      ordered_note_ids=snapshot.phrases[0].ordered_note_ids[1:]),
                            *snapshot.phrases[1:]))


def test_boundary_conflict_and_filename_only_section_are_ambiguous():
    snapshot, ids = source_fixture()
    conflict_boundary = replace(snapshot.boundaries[0], boundary_status="CONFLICT")
    boundary_snapshot = reattested(snapshot, boundaries=(conflict_boundary,))
    boundary = tempo_meter_boundary_adapter(boundary_snapshot)
    registry = ProtectionEvidenceRegistry(boundary_snapshot.subject_registry)
    boundary.install(registry)
    assert sparse_rule_status(registry, ids["boundary"], "TEMPO_METER_BOUNDARY") == "AMBIGUOUS"

    melody_section = next(item for item in snapshot.sections
                          if item.track_subject_id == ids["melody_track"])
    filename_section = replace(melody_section, section_status="UNKNOWN",
                               provenance_method="FILENAME")
    section_snapshot = reattested(snapshot, sections=tuple(
        filename_section if item.track_subject_id == filename_section.track_subject_id else item
        for item in snapshot.sections))
    section = section_transition_adapter(section_snapshot)
    registry = ProtectionEvidenceRegistry(section_snapshot.subject_registry)
    section.install(registry)
    assert sparse_rule_status(registry, ids["melody_track"], "SECTION_TRANSITION") == "AMBIGUOUS"


def test_local_repeat_uses_exact_track_meter_rhythm_and_topology_identity_only():
    snapshot, ids = source_fixture()
    exact = local_repeated_pattern_adapter(snapshot)
    registry = ProtectionEvidenceRegistry(snapshot.subject_registry)
    exact.install(registry)
    assert sparse_rule_status(registry, ids["m1"], "LOCAL_REPEATED_PATTERN") == "DETECTED"
    assert len([item for item in snapshot.bar_patterns if item.bar_subject_id == ids["bar1"]]) == 2
    melody_bar_two = next(item for item in snapshot.bar_patterns
                          if item.track_subject_id == ids["melody_track"] and
                          item.bar_subject_id == ids["bar2"])
    altered = replace(melody_bar_two, topology_sha256="a" * 64)
    changed = reattested(snapshot, bar_patterns=tuple(
        altered if (item.track_subject_id, item.bar_subject_id) ==
        (altered.track_subject_id, altered.bar_subject_id) else item
        for item in snapshot.bar_patterns))
    emission = local_repeated_pattern_adapter(changed)
    registry = ProtectionEvidenceRegistry(changed.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["m1"], "LOCAL_REPEATED_PATTERN") == "CLEAR"
    assert sparse_rule_status(registry, ids["m5"], "LOCAL_REPEATED_PATTERN") == "CLEAR"


def test_factory_reference_rule_is_only_a_post_model_deferred_interface():
    snapshot, ids = source_fixture()
    emission = factory_reference_conflict_deferred(snapshot)
    assert emission.run.run_status == "DEFERRED_POST_MODEL"
    assert emission.run.contract.adapter_class == "POST_MODEL_REQUIRED"
    assert emission.groups == () and emission.memberships == () and emission.partition is None
    registry = ProtectionEvidenceRegistry(snapshot.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["scope"], "FACTORY_REFERENCE_CONFLICT") == "DEFERRED"


@pytest.mark.parametrize("kind", [
    "SIX_SONG_DELAY_TERCA", "OPTIMIZER_OUTPUT", "REPAIRED_OUTPUT", "UNKNOWN",
])
def test_forbidden_and_unknown_source_classes_are_rejected_before_adapter_work(kind):
    with pytest.raises(ValueError, match="Forbidden or unknown|Unknown source lineage|Forbidden lineage class"):
        source_fixture(source_kind=kind)


def test_forbidden_sha_and_manifest_flags_cannot_be_bypassed_by_renaming():
    for flag in ("is_optimizer_output", "is_repaired_output", "is_six_song_delay_terca"):
        manifest = {"source_class": "FACTORY_RAW", flag: True, "filename": "renamed.mid"}
        with pytest.raises(ValueError, match="cannot enter"):
            source_fixture(manifest=manifest)


def test_cross_source_human_and_rx_claim_memberships_are_rejected():
    snapshot, ids = source_fixture()
    human = replace(snapshot.human_components[0], source_sha256=OTHER)
    with pytest.raises(ValueError, match="another source"):
        reattested(snapshot, human_components=(human,))
    foreign_claims = (RxDncClaim((1, 2, 3), "CONFIRMED_RX_COMPLETE", EVIDENCE,
                                 "manual:foreign", (OTHER,)),)
    foreign_claim = RxDncEvidenceSnapshot(RX_DNC_EVIDENCE_VERSION,
                                          rx_dnc_claims_sha256(foreign_claims),
                                          foreign_claims)
    with pytest.raises(ValueError, match="exact Program observation"):
        replace(snapshot, rx_evidence=foreign_claim)


def test_public_adapter_records_have_no_destructive_capability_fields():
    forbidden = {"target", "candidate", "proposal", "repair", "apply", "commit", "mutation"}
    record_types = (
        TrackObservation, NoteObservation, PhraseObservation, SectionObservation,
        BoundaryObservation, BarPatternObservation, RxSubjectObservation, RxDncClaim,
        HumanValidatedComponent,
    )
    for record_type in record_types:
        names = {item.name.lower() for item in fields(record_type)}
        assert not names.intersection(forbidden)
    names = {item.name.lower() for item in fields(AdapterEmission)}
    assert "mutation_capability" in names
    snapshot, _ids = source_fixture()
    assert all(item.mutation_capability == "NONE" for item in
               build_pre_model_adapter_emissions(snapshot))


def test_missing_forged_or_wrong_version_core_attestation_is_hard_failure():
    snapshot, _ids = source_fixture()
    with pytest.raises(ValueError, match="Missing core extraction attestations"):
        replace(snapshot, extraction_attestations=snapshot.extraction_attestations[:-1])
    first = snapshot.extraction_attestations[0]
    forged = replace(first, semantic_sha256="0" * 64)
    with pytest.raises(ValueError, match="attestation mismatch"):
        replace(snapshot, extraction_attestations=(forged, *snapshot.extraction_attestations[1:]))
    wrong = replace(first, extractor_version="UNVERSIONED")
    with pytest.raises(ValueError, match="attestation mismatch"):
        replace(snapshot, extraction_attestations=(wrong, *snapshot.extraction_attestations[1:]))
    assert first.extractor_version == EXTRACTOR_VERSION_BY_DOMAIN[first.domain]


def test_snapshot_freezes_registry_nested_maps_and_is_input_order_invariant():
    snapshot, ids = source_fixture()
    original_digest = snapshot.semantic_sha256
    ids["input_registry"].add_subject(StableSubject("NOTE", SOURCE, {"note_id": "late-input"}))
    assert snapshot.recompute_semantic_sha256() == original_digest
    original_registry = snapshot.subject_registry
    with pytest.raises(TypeError, match="immutable"):
        original_registry.add_subject(StableSubject("NOTE", SOURCE, {"note_id": "late"}))
    with pytest.raises(TypeError):
        snapshot.source_manifest["nested"] = "changed"
    reversed_snapshot = reattested(snapshot,
        tracks=tuple(reversed(snapshot.tracks)), notes=tuple(reversed(snapshot.notes)),
        phrases=tuple(reversed(snapshot.phrases)), sections=tuple(reversed(snapshot.sections)),
        boundaries=tuple(reversed(snapshot.boundaries)),
        bar_patterns=tuple(reversed(snapshot.bar_patterns)),
        rx_subjects=tuple(reversed(snapshot.rx_subjects)),
        human_components=tuple(reversed(snapshot.human_components)))
    assert reversed_snapshot.semantic_sha256 == snapshot.semantic_sha256
    assert [item.run.run_id for item in build_pre_model_adapter_emissions(reversed_snapshot)] == [
        item.run.run_id for item in build_pre_model_adapter_emissions(snapshot)]
    object.__setattr__(snapshot, "tracks", snapshot.tracks[:-1])
    with pytest.raises(ValueError, match="digest is stale"):
        build_pre_model_adapter_emissions(snapshot)
    assert ids["scope"]


def test_note_bar_onset_meter_boundary_and_pattern_relationships_are_proven():
    snapshot, _ids = source_fixture()
    wrong_meter_note = replace(snapshot.notes[0], meter_segment_id="a" * 64)
    with pytest.raises(ValueError, match="stable BAR"):
        reattested(snapshot, notes=(wrong_meter_note, *snapshot.notes[1:]))
    wrong_onset = replace(snapshot.notes[0], start_tick=snapshot.notes[0].start_tick + 1)
    with pytest.raises(ValueError, match="ONSET_CLUSTER"):
        reattested(snapshot, notes=(wrong_onset, *snapshot.notes[1:]))
    wrong_pattern = replace(snapshot.bar_patterns[0], meter_segment_id="b" * 64)
    with pytest.raises(ValueError, match="pattern meter"):
        reattested(snapshot, bar_patterns=(wrong_pattern, *snapshot.bar_patterns[1:]))
    non_touching = replace(snapshot.boundaries[0], affected_subject_ids=(snapshot.notes[-1].note_subject_id,))
    with pytest.raises(ValueError, match="boundary edge|actual boundary tick"):
        reattested(snapshot, boundaries=(non_touching,))


def test_rx_registry_digest_and_trigger_address_are_cryptographically_bound():
    snapshot, ids = source_fixture()
    claim = RxDncClaim((1, 2, 3), "CONFIRMED_RX_COMPLETE", EVIDENCE,
                       "manual:bound", (ids["g1"],))
    with pytest.raises(ValueError, match="semantic digest mismatch"):
        RxDncEvidenceSnapshot(RX_DNC_EVIDENCE_VERSION, "0" * 64, (claim,))
    cross_address = RxDncClaim((1, 2, 4), "CONFIRMED_RX_COMPLETE", EVIDENCE,
                               "manual:wrong-address", (ids["g1"],))
    evidence = RxDncEvidenceSnapshot(RX_DNC_EVIDENCE_VERSION,
                                     rx_dnc_claims_sha256((cross_address,)), (cross_address,))
    with pytest.raises(ValueError, match="address contradicts"):
        replace(snapshot, rx_evidence=evidence)
    non_rx_other = RxDncClaim((1, 2, 4), "CONFIRMED_NON_RX", EVIDENCE,
                              "manual:other-address")
    evidence = RxDncEvidenceSnapshot(RX_DNC_EVIDENCE_VERSION,
                                     rx_dnc_claims_sha256((non_rx_other,)), (non_rx_other,))
    guarded = replace(snapshot, rx_evidence=evidence)
    emission = rx_dnc_adapter(guarded)
    registry = ProtectionEvidenceRegistry(guarded.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["g1"], "RX_DNC") == "EVIDENCE_UNJOINABLE"


def test_guitar_exact_non_guitar_is_not_applicable_and_command_candidate_is_ambiguous():
    snapshot, ids = source_fixture()
    emission = next(item for item in build_pre_model_adapter_emissions(snapshot)
                    if item.run.contract.rule_key == "GUITAR_MODE")
    registry = ProtectionEvidenceRegistry(snapshot.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["melody_track"], "GUITAR_MODE") == "NOT_APPLICABLE"
    guitar = next(item for item in snapshot.tracks if item.track_subject_id == ids["guitar_track"])
    candidate = replace(guitar, track_type="REGULAR", track_type_status="EXACT")
    guarded = reattested(snapshot, tracks=tuple(
        candidate if item.track_subject_id == candidate.track_subject_id else item
        for item in snapshot.tracks))
    emission = next(item for item in build_pre_model_adapter_emissions(guarded)
                    if item.run.contract.rule_key == "GUITAR_MODE")
    registry = ProtectionEvidenceRegistry(guarded.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["guitar_track"], "GUITAR_MODE") == "AMBIGUOUS"


def test_human_grace_requires_exact_kind_membership_and_single_track_join():
    with pytest.raises(ValueError, match="kind GRACE"):
        source_fixture(grace_component_kind="TURN")
    snapshot, ids = source_fixture()
    mismatched = replace(snapshot.human_components[0],
                         member_subject_ids=(ids["m4"], ids["m5"]))
    with pytest.raises(ValueError, match="exactly match"):
        reattested(snapshot, human_components=(mismatched,))
    cross_track = replace(snapshot.human_components[0], member_subject_ids=(ids["g1"],))
    with pytest.raises(ValueError, match="exactly match|one exact track"):
        reattested(snapshot, human_components=(cross_track,))


def test_source_guard_policy_is_mandatory_and_blocks_renamed_or_mislabeled_lineage():
    snapshot, _ids = source_fixture()
    with pytest.raises(TypeError, match="SourceGuardPolicy is mandatory"):
        replace(snapshot, source_guard_policy=None)
    with pytest.raises(ValueError, match="exact six-song SHA set"):
        SourceGuardPolicy(SOURCE_GUARD_POLICY_VERSION, SIX_SONG_FORBIDDEN_SHA256S[:-1],
                          SOURCE_LINEAGE_VERIFIER_VERSION, LINEAGE_CLASS_MATRIX_VERSION,
                          lineage_class_matrix_sha256(), "0" * 64)
    forbidden_sha = SIX_SONG_FORBIDDEN_SHA256S[0]
    forbidden_lineage = trusted_source_lineage_snapshot((
        SourceLineageRecord(forbidden_sha, "FACTORY_RAW", ()),))
    with pytest.raises(ValueError, match="Forbidden six-song SHA"):
        replace(snapshot, source_sha256=forbidden_sha, source_lineage=forbidden_lineage,
                source_manifest={"source_class": "FACTORY_RAW", "filename": "renamed.mid",
                                 "lineage_sha256": forbidden_lineage.semantic_sha256})
    optimizer_lineage = trusted_source_lineage_snapshot((
        SourceLineageRecord(SOURCE, "FACTORY_RAW", ()),))
    assert optimizer_lineage.record_for(SOURCE).lineage_class == "FACTORY_RAW"
    with pytest.raises(ValueError, match="Forbidden lineage class"):
        trusted_source_lineage_snapshot((
            SourceLineageRecord(SOURCE, "OPTIMIZER_OUTPUT", ()),))
    with pytest.raises(TypeError, match="canonical semantic records"):
        TrustedSourceLineageSnapshot(verified=True)


def test_section_attestation_cannot_omit_real_note_or_track_bar_membership():
    snapshot, ids = source_fixture()
    melody = next(item for item in snapshot.sections
                  if item.track_subject_id == ids["melody_track"])
    omitted_note_map = dict(melody.note_ids_by_bar)
    omitted_note_map[ids["bar1"]] = tuple(
        item for item in omitted_note_map[ids["bar1"]] if item != ids["m4"])
    omitted_note = replace(melody, note_ids_by_bar=omitted_note_map)
    with pytest.raises(ValueError, match="complete track membership universe"):
        reattested(snapshot, sections=tuple(
            omitted_note if item.track_subject_id == ids["melody_track"] else item
            for item in snapshot.sections))
    omitted_bar = replace(melody, ordered_bar_ids=(ids["bar1"],),
                          note_ids_by_bar={ids["bar1"]: melody.note_ids_by_bar[ids["bar1"]]})
    with pytest.raises(ValueError, match="complete track/bar universe"):
        reattested(snapshot, sections=tuple(
            omitted_bar if item.track_subject_id == ids["melody_track"] else item
            for item in snapshot.sections))


def test_rx_v1_rejects_event_or_component_subject_even_with_address_claim():
    snapshot, ids = source_fixture()
    event_rx = RxSubjectObservation(ids["command"], ids["program_segment"],
                                    "PROGRAM_EXACT", 1, 2, 3)
    with pytest.raises(ValueError, match="NOTE subject"):
        reattested(snapshot, rx_subjects=(event_rx,))
    component_rx = RxSubjectObservation(ids["grace"], ids["program_segment"],
                                        "PROGRAM_EXACT", 1, 2, 3)
    with pytest.raises(ValueError, match="NOTE subject"):
        reattested(snapshot, rx_subjects=(component_rx,))


def test_exact_guitar_role_with_unproven_track_type_is_ambiguous_applicable():
    snapshot, ids = source_fixture()
    melody = next(item for item in snapshot.tracks
                  if item.track_subject_id == ids["melody_track"])
    guitar_role = replace(melody, role="GUITAR", role_status="EXACT",
                          track_type="UNKNOWN", track_type_status="UNKNOWN")
    guarded = reattested(snapshot, tracks=tuple(
        guitar_role if item.track_subject_id == ids["melody_track"] else item
        for item in snapshot.tracks))
    emission = next(item for item in build_pre_model_adapter_emissions(guarded)
                    if item.run.contract.rule_key == "GUITAR_MODE")
    registry = ProtectionEvidenceRegistry(guarded.subject_registry)
    emission.install(registry)
    assert sparse_rule_status(registry, ids["melody_track"], "GUITAR_MODE") == "AMBIGUOUS"


def test_local_repeat_requires_complete_track_bar_pair_universe():
    snapshot, ids = source_fixture()
    same_global_bar = [item for item in snapshot.bar_patterns
                       if item.bar_subject_id == ids["bar1"]]
    assert {item.track_subject_id for item in same_global_bar} == {
        ids["melody_track"], ids["guitar_track"]}
    missing_guitar_pair = tuple(item for item in snapshot.bar_patterns
                                if not (item.track_subject_id == ids["guitar_track"] and
                                        item.bar_subject_id == ids["bar1"]))
    with pytest.raises(ValueError, match="BAR_PATTERNS"):
        reattested(snapshot, bar_patterns=missing_guitar_pair)


def test_lineage_snapshot_rejects_forbidden_parent_and_transitive_grandparent():
    snapshot, _ids = source_fixture()
    forbidden = SIX_SONG_FORBIDDEN_SHA256S[0]
    direct = trusted_source_lineage_snapshot((
        SourceLineageRecord(forbidden, "FACTORY_RAW", ()),
        SourceLineageRecord(SOURCE, "FACTORY_RAW", (forbidden,)),
    ))
    with pytest.raises(ValueError, match="Forbidden six-song SHA exists in source lineage"):
        replace(snapshot, source_lineage=direct,
                source_manifest={"source_class": "FACTORY_RAW",
                                 "lineage_sha256": direct.semantic_sha256})
    intermediate = "a" * 64
    transitive = trusted_source_lineage_snapshot((
        SourceLineageRecord(forbidden, "FACTORY_RAW", ()),
        SourceLineageRecord(intermediate, "FACTORY_RAW", (forbidden,)),
        SourceLineageRecord(SOURCE, "FACTORY_RAW", (intermediate,)),
    ))
    with pytest.raises(ValueError, match="Forbidden six-song SHA exists in source lineage"):
        replace(snapshot, source_lineage=transitive,
                source_manifest={"source_class": "FACTORY_RAW",
                                 "lineage_sha256": transitive.semantic_sha256})


def test_lineage_factory_recomputes_ids_digest_and_rejects_forged_verified_claims():
    record = SourceLineageRecord(SOURCE, "FACTORY_RAW", ())
    semantic = dict(record.semantic_record)
    forged_id = dict(semantic, record_id="0" * 64)
    with pytest.raises(ValueError, match="record ID mismatch"):
        TrustedSourceLineageSnapshot.from_semantic_records(
            (forged_id,), lineage_inventory_sha256((forged_id,)))
    forged_verified = dict(semantic, verified=True)
    with pytest.raises(ValueError, match="semantic record fields"):
        TrustedSourceLineageSnapshot.from_semantic_records(
            (forged_verified,), lineage_inventory_sha256((forged_verified,)))
    with pytest.raises(ValueError, match="inventory digest mismatch"):
        TrustedSourceLineageSnapshot.from_semantic_records((semantic,), "0" * 64)


def test_lineage_factory_rejects_missing_parent_and_cycle_but_accepts_valid_factory_dag():
    missing = SourceLineageRecord(SOURCE, "FACTORY_RAW", (OTHER,))
    with pytest.raises(ValueError, match="parent is missing"):
        trusted_source_lineage_snapshot((missing,))
    cycle = (
        SourceLineageRecord(SOURCE, "FACTORY_RAW", (OTHER,)),
        SourceLineageRecord(OTHER, "FACTORY_RAW", (SOURCE,)),
    )
    with pytest.raises(ValueError, match="cycle"):
        trusted_source_lineage_snapshot(cycle)
    valid = trusted_source_lineage_snapshot((
        SourceLineageRecord(OTHER, "FACTORY_RAW", ()),
        SourceLineageRecord(SOURCE, "FACTORY_RAW", (OTHER,)),
    ))
    assert valid.ancestor_closure(SOURCE) == tuple(sorted((SOURCE, OTHER)))
    snapshot, _ids = source_fixture()
    rebuilt = replace(snapshot, source_lineage=valid,
                      source_manifest={"source_class": "FACTORY_RAW",
                                       "lineage_sha256": valid.semantic_sha256})
    assert build_pre_model_adapter_emissions(rebuilt)


@pytest.mark.parametrize(("child_class", "parent_class"), [
    (child, parent)
    for child in ("FACTORY_RAW", "GOLD_REFERENCE_RAW", "HUMAN_VALIDATED_RAW", "SYNTHETIC_TEST")
    for parent in ("FACTORY_RAW", "GOLD_REFERENCE_RAW", "HUMAN_VALIDATED_RAW", "SYNTHETIC_TEST")
    if child != parent
])
def test_lineage_matrix_rejects_every_direct_cross_authority_edge(child_class, parent_class):
    parent_id = OTHER
    with pytest.raises(ValueError, match="Illegal lineage parent class"):
        trusted_source_lineage_snapshot((
            SourceLineageRecord(parent_id, parent_class, ()),
            SourceLineageRecord(SOURCE, child_class, (parent_id,)),
        ))


def test_lineage_matrix_rejects_transitive_cross_class_and_is_canonical_immutable():
    ancestor = "a" * 64
    intermediate = "b" * 64
    with pytest.raises(ValueError, match="Illegal lineage parent class|Illegal transitive"):
        trusted_source_lineage_snapshot((
            SourceLineageRecord(ancestor, "GOLD_REFERENCE_RAW", ()),
            SourceLineageRecord(intermediate, "FACTORY_RAW", (ancestor,)),
            SourceLineageRecord(SOURCE, "FACTORY_RAW", (intermediate,)),
        ))
    with pytest.raises(TypeError):
        ALLOWED_LINEAGE_PARENT_CLASSES["FACTORY_RAW"] = ("GOLD_REFERENCE_RAW",)
    policy = trusted_source_guard_policy()
    assert policy.lineage_matrix_version == LINEAGE_CLASS_MATRIX_VERSION
    assert policy.lineage_matrix_sha256 == lineage_class_matrix_sha256()
    with pytest.raises(ValueError, match="matrix digest mismatch"):
        replace(policy, lineage_matrix_sha256="0" * 64)


@pytest.mark.parametrize("lineage_class", [
    "FACTORY_RAW", "GOLD_REFERENCE_RAW", "HUMAN_VALIDATED_RAW", "SYNTHETIC_TEST",
])
def test_lineage_matrix_accepts_only_same_class_dags(lineage_class):
    parent_id = OTHER
    lineage = trusted_source_lineage_snapshot((
        SourceLineageRecord(parent_id, lineage_class, ()),
        SourceLineageRecord(SOURCE, lineage_class, (parent_id,)),
    ))
    assert lineage.ancestor_closure(SOURCE) == tuple(sorted((SOURCE, parent_id)))
    snapshot, _ids = source_fixture(source_kind=lineage_class)
    rebuilt = replace(snapshot, source_lineage=lineage,
                      source_manifest={"source_class": lineage_class,
                                       "lineage_sha256": lineage.semantic_sha256})
    assert build_pre_model_adapter_emissions(rebuilt)