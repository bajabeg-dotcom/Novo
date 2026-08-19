from __future__ import annotations

import struct
import unittest

from change_engine import BytePreservingChangeEngine, ChangeExecutionError, create_execution_request
from change_plan import UserDecision
from contextual_profile_builder import (
    ContextualProfileBuilder,
    ProfileKey,
    ProfileObservation,
)
from profile_suggest_engine import (
    ExactContextualProfileMatcher,
    ProfileVelocitySuggestor,
    SuggestionConfig,
    SuggestionStatus,
)
from style_loader import StandardMidiLoader

SHA = "b" * 64


def key(**changes) -> ProfileKey:
    values = dict(
        source_kind="FACTORY_STYLE",
        address="121.0.33",
        item_kind="FACTORY_SOUND",
        function="ACCOMP_CHORDAL",
        element="VARIATION_1",
        cv=1,
        structural_role="ACC1",
        encoding="ORDINARY_MIDI",
        fixed_intro_ending_candidate=False,
    )
    values.update(changes)
    return ProfileKey(**values)


def observation(index: int, profile_key: ProfileKey | None = None) -> ProfileObservation:
    profile_key = profile_key or key()
    velocities = (50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 60, 70)
    return ProfileObservation(
        source_id="FACTORY",
        source_sha256=SHA,
        source_kind=profile_key.source_kind,
        member_name=f"Style{index}/Style{index}_Var1.mid",
        style_name=f"Style{index}",
        key=profile_key,
        official_name="Finger Bass GM",
        segment_status="READY",
        measurement_status="READY",
        velocities=velocities,
        pitches=tuple(range(48, 60)),
        duration_beats=(0.5,) * len(velocities),
        density_per_beat=2.0,
        maximum_sounding_polyphony=3,
        maximum_onset_polyphony=3,
        controller_event_counts=(),
    )


def catalog(profile_key: ProfileKey | None = None, observations: int = 3):
    profile_key = profile_key or key()
    return ContextualProfileBuilder().build_from_observations(
        tuple(observation(index, profile_key) for index in range(observations)),
        source_id="FACTORY",
        source_path="factory.zip",
        source_sha256=SHA,
        source_kind=profile_key.source_kind,
    )


def midi_events(velocities: tuple[int, ...]):
    events = [b"\x00\xc0\x21"]
    for index, velocity in enumerate(velocities):
        pitch = 60 + index
        events.append(bytes([0, 0x90, pitch, velocity]))
        events.append(bytes([24, 0x80, pitch, 0]))
    events.append(b"\x00\xff\x2f\x00")
    body = b"".join(events)
    source = (
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192)
        + b"MTrk" + struct.pack(">I", len(body)) + body
    )
    model = StandardMidiLoader().load_bytes(source, source_name="suggest.mid")
    return source, model, model.tracks[0].events


class ProfileSuggestEngineTests(unittest.TestCase):
    def test_exact_profile_match_creates_bounded_suggest_plan_only(self) -> None:
        source, model, events = midi_events((20, 70, 120))
        result = ProfileVelocitySuggestor().suggest(
            catalog=catalog(),
            key=key(),
            source_sha256=model.sha256,
            events=events,
            identity_status="FACTORY_CONFIRMED",
            classification_status="CLASSIFIED",
            classification_confidence=82,
            edit_policy="SAFE_BOUNDED",
            user_enabled_rule=True,
        )
        self.assertEqual(result.status, SuggestionStatus.SUGGEST_PLAN_READY)
        self.assertIsNotNone(result.plan)
        self.assertFalse(result.apply_supported)
        self.assertFalse(result.plan.apply_authorized)
        proposal = result.plan.proposals[0]
        self.assertEqual(proposal.rule_id, "S01.PROFILE_VELOCITY_OUTLIER")
        self.assertEqual(proposal.confidence_percent, 82.0)
        self.assertEqual(len(proposal.mutations), 2)
        self.assertEqual(
            {(item.old_value, item.new_value) for item in proposal.mutations},
            {(20, 28), (120, 112)},
        )
        self.assertEqual(source, bytes(source))

        approved = result.plan.record_decision(
            proposal.proposal_id,
            UserDecision.APPROVE,
            decided_at="2026-08-14T17:00:00+02:00",
        )
        request = create_execution_request(
            approved, requested_at="2026-08-14T17:01:00+02:00"
        )
        with self.assertRaisesRegex(ChangeExecutionError, "lacks rule authorization"):
            BytePreservingChangeEngine().execute(
                plan=approved, request=request, source_bytes=source
            )

    def test_context_key_mismatch_never_falls_back(self) -> None:
        source_catalog = catalog()
        matcher = ExactContextualProfileMatcher()
        mismatches = (
            key(function="SOLO_CANDIDATE"),
            key(element="INTRO_1"),
            key(cv=2),
            key(structural_role="ACC2"),
            key(encoding="GUITAR_MODE_CANDIDATE"),
            key(source_kind="GOLD_DNA"),
        )
        for mismatch in mismatches:
            with self.subTest(key=mismatch):
                result = matcher.match(source_catalog, mismatch)
                self.assertEqual(result.status, SuggestionStatus.NO_PROFILE)
                self.assertIsNone(result.profile)

    def test_insufficient_reference_blocks_suggestion(self) -> None:
        weak = catalog(observations=1)
        result = ExactContextualProfileMatcher().match(weak, key())
        self.assertEqual(result.status, SuggestionStatus.INSUFFICIENT_REFERENCE)
        self.assertTrue(result.reasons)

    def test_protected_context_and_user_disabled_rule_are_blocked(self) -> None:
        _source, model, events = midi_events((20, 70))
        base = dict(
            catalog=catalog(), key=key(), source_sha256=model.sha256, events=events,
            identity_status="FACTORY_CONFIRMED", classification_status="CLASSIFIED",
            classification_confidence=80, edit_policy="SAFE_BOUNDED",
            user_enabled_rule=True,
        )
        cases = (
            {"identity_status": "UNKNOWN"},
            {"classification_status": "UNCERTAIN"},
            {"edit_policy": "DO_NOT_TOUCH"},
            {"user_enabled_rule": False},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                result = ProfileVelocitySuggestor().suggest(**{**base, **changes})
                self.assertEqual(result.status, SuggestionStatus.CONTEXT_BLOCKED)
                self.assertIsNone(result.plan)

        fixed_key = key(fixed_intro_ending_candidate=True)
        fixed = ProfileVelocitySuggestor().suggest(
            **{**base, "catalog": catalog(fixed_key), "key": fixed_key}
        )
        self.assertEqual(fixed.status, SuggestionStatus.CONTEXT_BLOCKED)

    def test_no_outliers_and_too_many_outliers_do_not_create_plan(self) -> None:
        _source, model, normal_events = midi_events((60, 70, 80))
        normal = ProfileVelocitySuggestor().suggest(
            catalog=catalog(), key=key(), source_sha256=model.sha256,
            events=normal_events, identity_status="FACTORY_CONFIRMED",
            classification_status="CLASSIFIED", classification_confidence=80,
            edit_policy="SAFE_BOUNDED", user_enabled_rule=True,
        )
        self.assertEqual(normal.status, SuggestionStatus.NO_OUTLIERS)
        self.assertIsNone(normal.plan)

        _source, model, outlier_events = midi_events((10, 15, 120))
        config = SuggestionConfig(maximum_mutations=1)
        crowded = ProfileVelocitySuggestor(config).suggest(
            catalog=catalog(), key=key(), source_sha256=model.sha256,
            events=outlier_events, identity_status="FACTORY_CONFIRMED",
            classification_status="CLASSIFIED", classification_confidence=80,
            edit_policy="SAFE_BOUNDED", user_enabled_rule=True,
        )
        self.assertEqual(crowded.status, SuggestionStatus.TOO_MANY_OUTLIERS)
        self.assertIsNone(crowded.plan)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ExactContextualProfileMatcher(SuggestionConfig(minimum_notes=0))
        with self.assertRaises(ValueError):
            ProfileVelocitySuggestor(SuggestionConfig(maximum_adjustment=33))


if __name__ == "__main__":
    unittest.main()
