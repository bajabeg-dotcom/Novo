from dataclasses import replace

import pytest

from rxoptimizer.rhythm_subject_registry import (
    SUBJECT_CONTRACT_VERSION,
    StableSubject,
    StableSubjectEdge,
    StableSubjectRegistry,
    canonical_json,
    stable_subject_id,
)


SOURCE = "1" * 64
METER = "2" * 64
EVENT_1 = "a" * 64
EVENT_2 = "b" * 64
NOTE_1 = "c" * 64
NOTE_2 = "d" * 64


def subject(subject_type, **key):
    return StableSubject(subject_type, SOURCE, key)


def test_stable_subject_id_is_canonical_repeatable_and_type_scoped():
    left = stable_subject_id("NOTE", SOURCE, {"track": 2, "members": ["b", "a"]})
    right = stable_subject_id("NOTE", SOURCE, {"members": ["b", "a"], "track": 2})
    assert left == right
    assert left != stable_subject_id("EVENT", SOURCE, {"track": 2, "members": ["b", "a"]})
    assert left != stable_subject_id("NOTE", SOURCE, {"track": 2, "members": ["a", "b"]})
    assert left != stable_subject_id("NOTE", SOURCE, {"track": 2, "members": ["b", "a"]}, "V2")


def test_onset_cluster_membership_is_sorted_but_phrase_and_component_order_is_semantic():
    first = stable_subject_id("ONSET_CLUSTER", SOURCE, {
        "track_index": 0, "channel": 1, "meter_segment_id": METER, "tick": 10,
        "on_event_ids": [EVENT_2, EVENT_1]})
    second = stable_subject_id("ONSET_CLUSTER", SOURCE, {
        "track_index": 0, "channel": 1, "meter_segment_id": METER, "tick": 10,
        "on_event_ids": [EVENT_1, EVENT_2]})
    assert first == second
    phrase = {"track_index": 0, "channel": 1, "meter_segment_id": METER,
              "ordered_note_ids": [NOTE_1, NOTE_2]}
    assert stable_subject_id("PHRASE", SOURCE, phrase) != stable_subject_id(
        "PHRASE", SOURCE, {**phrase, "ordered_note_ids": [NOTE_2, NOTE_1]})
    component = {"track_index": 0, "channel": 1, "meter_segment_id": METER,
                 "component_kind": "TRILL", "ordered_note_ids": [NOTE_1, NOTE_2]}
    assert stable_subject_id("COMPONENT", SOURCE, component) != stable_subject_id(
        "COMPONENT", SOURCE, {**component, "ordered_note_ids": [NOTE_2, NOTE_1]})
    with pytest.raises(ValueError, match="duplicates"):
        stable_subject_id("ONSET_CLUSTER", SOURCE, {
            "track_index": 0, "channel": 1, "meter_segment_id": METER, "tick": 10,
            "on_event_ids": [EVENT_1, EVENT_1]})
    with pytest.raises(ValueError, match="canonical fields"):
        stable_subject_id("PHRASE", SOURCE, {"start_tick": 0, "end_tick": 10})


@pytest.mark.parametrize(("subject_type", "bad_key"), [
    ("ONSET_CLUSTER", [EVENT_1]),
    ("PHRASE", "alias"),
    ("COMPONENT", (NOTE_1, NOTE_2)),
])
def test_structural_subjects_reject_non_mapping_natural_keys(subject_type, bad_key):
    with pytest.raises(ValueError, match="must be a mapping"):
        stable_subject_id(subject_type, SOURCE, bad_key)


def test_structural_subjects_reject_aliases_nonstable_members_and_bad_coordinates():
    with pytest.raises(ValueError, match="canonical fields"):
        stable_subject_id("ONSET_CLUSTER", SOURCE, {
            "track_index": 0, "channel": 1, "meter_segment_id": METER, "tick": 10,
            "members": [EVENT_1]})
    with pytest.raises(ValueError, match="stable membership ID"):
        stable_subject_id("PHRASE", SOURCE, {
            "track_index": 0, "channel": 1, "meter_segment_id": METER,
            "ordered_note_ids": ["n1"]})
    with pytest.raises(ValueError, match="channel"):
        stable_subject_id("COMPONENT", SOURCE, {
            "track_index": 0, "channel": 16, "meter_segment_id": METER,
            "component_kind": "TRILL", "ordered_note_ids": [NOTE_1]})


def test_natural_keys_reject_float_empty_unknown_and_noncanonical_values():
    with pytest.raises(ValueError, match="floats"):
        subject("NOTE", phase=0.5)
    with pytest.raises(ValueError, match="empty"):
        StableSubject("NOTE", SOURCE, {})
    with pytest.raises(ValueError, match="Unknown"):
        StableSubject("UNKNOWN", SOURCE, {"id": 1})
    with pytest.raises(ValueError, match="Unsupported"):
        StableSubject("NOTE", SOURCE, {"set": {1, 2}})
    with pytest.raises(ValueError, match="mapping keys"):
        StableSubject("NOTE", SOURCE, {1: "invalid"})
    with pytest.raises(ValueError, match="lowercase"):
        StableSubject("NOTE", "A" * 64, {"id": 1})


def test_registry_edges_enforce_registered_type_source_and_no_self_cycle():
    registry = StableSubjectRegistry()
    track = registry.add_subject(subject("TRACK_CHANNEL", track=0, channel=1))
    note = registry.add_subject(subject("NOTE", note_id="n1"))
    edge = StableSubjectEdge("TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, note.subject_id, SOURCE)
    assert registry.add_edge(edge) == edge
    assert registry.add_edge(edge) == edge  # idempotent
    with pytest.raises(ValueError, match="requires"):
        registry.add_edge(StableSubjectEdge("NOTE_HAS_ON_EVENT", track.subject_id, note.subject_id, SOURCE))
    with pytest.raises(ValueError, match="self-cycle"):
        StableSubjectEdge("TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, track.subject_id, SOURCE)


def test_edge_contract_version_must_match_both_endpoints():
    registry = StableSubjectRegistry()
    track = registry.add_subject(StableSubject("TRACK_CHANNEL", SOURCE, {"track": 0}, "V2"))
    note = registry.add_subject(StableSubject("NOTE", SOURCE, {"note": 60}, "V2"))
    with pytest.raises(ValueError, match="contract versions"):
        registry.add_edge(StableSubjectEdge(
            "TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, note.subject_id, SOURCE,
            contract_version=SUBJECT_CONTRACT_VERSION))


def test_registry_rejects_cross_source_and_missing_endpoints():
    registry = StableSubjectRegistry()
    track = registry.add_subject(subject("TRACK_CHANNEL", track=0, channel=1))
    other = StableSubject("NOTE", "2" * 64, {"note_id": "n2"})
    registry.add_subject(other)
    with pytest.raises(ValueError, match="Cross-source"):
        registry.add_edge(StableSubjectEdge(
            "TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, other.subject_id, SOURCE))
    missing = "3" * 64
    with pytest.raises(ValueError, match="endpoints"):
        registry.add_edge(StableSubjectEdge(
            "TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, missing, SOURCE))


def test_multiple_memberships_are_preserved_and_digest_is_insert_order_independent():
    def build(reverse=False):
        registry = StableSubjectRegistry()
        note = subject("NOTE", note_id="n1")
        note_two = subject("NOTE", note_id="n2")
        registry.extend_subjects(reversed([note, note_two]) if reverse else [note, note_two])
        phrase = subject("PHRASE", track_index=0, channel=1, meter_segment_id=METER,
                         ordered_note_ids=[note.subject_id, note_two.subject_id])
        component = subject("COMPONENT", track_index=0, channel=1,
                            meter_segment_id=METER, component_kind="TRILL",
                            ordered_note_ids=[note.subject_id, note_two.subject_id])
        items = [phrase, component]
        registry.extend_subjects(reversed(items) if reverse else items)
        edges = [
            StableSubjectEdge("PHRASE_CONTAINS_NOTE", phrase.subject_id, note.subject_id, SOURCE),
            StableSubjectEdge("COMPONENT_CONTAINS_NOTE", component.subject_id, note.subject_id, SOURCE),
        ]
        for edge in reversed(edges) if reverse else edges:
            registry.add_edge(edge)
        return registry
    first, second = build(), build(True)
    assert len(first.edges) == 2
    assert first.semantic_digest() == second.semantic_digest()


def test_registry_structural_members_must_exist_same_source_version_and_type():
    registry = StableSubjectRegistry()
    event = registry.add_subject(subject("EVENT", event_id="on-1", event_kind="NOTE_ON"))
    note = registry.add_subject(subject("NOTE", note_id="n1"))
    cluster = subject("ONSET_CLUSTER", track_index=0, channel=1, meter_segment_id=METER,
                      tick=10, on_event_ids=[event.subject_id])
    assert registry.add_subject(cluster) == cluster
    phrase = subject("PHRASE", track_index=0, channel=1, meter_segment_id=METER,
                     ordered_note_ids=[note.subject_id])
    assert registry.add_subject(phrase) == phrase

    missing = subject("PHRASE", track_index=0, channel=1, meter_segment_id=METER,
                      ordered_note_ids=["f" * 64])
    with pytest.raises(ValueError, match="already be registered"):
        registry.add_subject(missing)

    wrong_type = subject("PHRASE", track_index=0, channel=1, meter_segment_id=METER,
                         ordered_note_ids=[event.subject_id])
    with pytest.raises(ValueError, match="stable type"):
        registry.add_subject(wrong_type)

    off_event = registry.add_subject(subject("EVENT", event_id="off-1", event_kind="NOTE_OFF"))
    off_cluster = subject("ONSET_CLUSTER", track_index=0, channel=1, meter_segment_id=METER,
                          tick=20, on_event_ids=[off_event.subject_id])
    with pytest.raises(ValueError, match="canonical NOTE_ON"):
        registry.add_subject(off_cluster)

    other_event = registry.add_subject(StableSubject(
        "EVENT", "3" * 64, {"event_id": "x", "event_kind": "NOTE_ON"}))
    cross_source = subject("ONSET_CLUSTER", track_index=0, channel=1, meter_segment_id=METER,
                           tick=10, on_event_ids=[other_event.subject_id])
    with pytest.raises(ValueError, match="another source"):
        registry.add_subject(cross_source)

    v2_note = registry.add_subject(StableSubject("NOTE", SOURCE, {"note_id": "v2"}, "V2"))
    version_mismatch = subject("COMPONENT", track_index=0, channel=1,
                               meter_segment_id=METER, component_kind="TRILL",
                               ordered_note_ids=[v2_note.subject_id])
    with pytest.raises(ValueError, match="version mismatch"):
        registry.add_subject(version_mismatch)


def test_subject_record_and_canonical_json_do_not_depend_on_python_identity():
    first = subject("BAR", meter_segment_id="m1", start_tick=0, end_tick=1920)
    second = subject("BAR", end_tick=1920, start_tick=0, meter_segment_id="m1")
    assert first == second
    assert first.subject_id == second.subject_id
    assert canonical_json(first.semantic_record) == canonical_json(second.semantic_record)
    assert first.contract_version == SUBJECT_CONTRACT_VERSION