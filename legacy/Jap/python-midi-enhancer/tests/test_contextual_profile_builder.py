from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from contextual_profile_builder import (
    ContextualProfileBuilder,
    ContextualProfileError,
    ProfileKey,
    ProfileObservation,
    catalog_digest,
    render_catalog,
)

FACTORY_ARCHIVE = Path("prism-uploads/Split Factory Styles.zip")
FACTORY_SHA256 = "ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e"
EXPECTED_OBSERVATIONS = 29_603
EXPECTED_PROFILES = 13_821
EXPECTED_DIGEST = "33a9b42601bd7612f51312e4c2985bd483f49281edfaa2710d65bcf84998f4b5"


def observation(
    *,
    source_kind: str = "FACTORY_STYLE",
    function: str = "ACCOMP_CHORDAL",
    element: str = "VARIATION_1",
    cv: int = 1,
    member: str = "Style/Style_Var1.mid",
    style: str = "Style",
    velocities: tuple[int, ...] = (60, 80),
    durations: tuple[float, ...] = (0.5, 1.0),
) -> ProfileObservation:
    sha = "a" * 64
    key = ProfileKey(
        source_kind=source_kind,
        address="121.0.33",
        item_kind="FACTORY_SOUND",
        function=function,
        element=element,
        cv=cv,
        structural_role="ACC1",
        encoding="ORDINARY_MIDI",
        fixed_intro_ending_candidate=element in {"INTRO_1", "ENDING_1"},
    )
    return ProfileObservation(
        source_id="SOURCE",
        source_sha256=sha,
        source_kind=source_kind,
        member_name=member,
        style_name=style,
        key=key,
        official_name="Finger Bass GM",
        segment_status="READY",
        measurement_status="READY",
        velocities=velocities,
        pitches=(48, 52),
        duration_beats=durations,
        density_per_beat=1.5,
        maximum_sounding_polyphony=2,
        maximum_onset_polyphony=2,
        controller_event_counts=((64, 2),),
    )


class ContextualProfileBuilderTests(unittest.TestCase):
    def test_same_key_aggregates_exact_distributions_and_provenance(self) -> None:
        builder = ContextualProfileBuilder()
        observations = (
            observation(),
            observation(
                member="Style2/Style2_Var1.mid",
                style="Style2",
                velocities=(100,),
                durations=(2.0,),
            ),
        )
        catalog = builder.build_from_observations(
            observations,
            source_id="SOURCE",
            source_path="factory.zip",
            source_sha256="a" * 64,
            source_kind="FACTORY_STYLE",
        )
        self.assertEqual(catalog.observation_count, 2)
        self.assertEqual(catalog.profile_count, 1)
        profile = catalog.profiles[0]
        self.assertEqual(profile.observation_count, 2)
        self.assertEqual(profile.style_count, 2)
        self.assertEqual(profile.member_count, 2)
        self.assertEqual(profile.note_count, 3)
        self.assertEqual(profile.velocity.minimum, 60.0)
        self.assertEqual(profile.velocity.maximum, 100.0)
        self.assertEqual(profile.velocity.mean, 80.0)
        self.assertEqual(profile.velocity.median, 80.0)
        self.assertEqual(profile.duration_beats.median, 1.0)
        self.assertEqual(profile.controller_event_counts, ((64, 4),))
        self.assertEqual(profile.safety_policy, "REFERENCE_ONLY_NO_SUGGEST_AUTHORIZATION")
        self.assertEqual(len(profile.source_members), 2)

    def test_function_element_cv_and_source_kind_never_mix(self) -> None:
        factory = (
            observation(function="ACCOMP_CHORDAL", element="VARIATION_1", cv=1),
            observation(function="SOLO_CANDIDATE", element="VARIATION_1", cv=1),
            observation(function="ACCOMP_CHORDAL", element="INTRO_1", cv=1),
            observation(function="ACCOMP_CHORDAL", element="VARIATION_1", cv=2),
        )
        catalog = ContextualProfileBuilder().build_from_observations(
            factory,
            source_id="SOURCE",
            source_path="factory.zip",
            source_sha256="a" * 64,
            source_kind="FACTORY_STYLE",
        )
        self.assertEqual(catalog.profile_count, 4)
        self.assertEqual(len({item.profile_id for item in catalog.profiles}), 4)

        gold = ContextualProfileBuilder().build_from_observations(
            (observation(source_kind="GOLD_DNA"),),
            source_id="SOURCE",
            source_path="gold.zip",
            source_sha256="a" * 64,
            source_kind="GOLD_DNA",
        )
        self.assertNotEqual(catalog.profiles[0].profile_id, gold.profiles[0].profile_id)
        self.assertEqual(gold.source_kind, "GOLD_DNA")

    def test_mixed_or_conflicting_provenance_is_rejected(self) -> None:
        builder = ContextualProfileBuilder()
        with self.assertRaisesRegex(ContextualProfileError, "provenance"):
            builder.build_from_observations(
                (observation(source_kind="GOLD_DNA"),),
                source_id="SOURCE",
                source_path="factory.zip",
                source_sha256="a" * 64,
                source_kind="FACTORY_STYLE",
            )
        first = observation()
        conflicting = replace(first, official_name="Wrong")
        with self.assertRaisesRegex(ContextualProfileError, "official names"):
            builder.build_from_observations(
                (first, conflicting),
                source_id="SOURCE",
                source_path="factory.zip",
                source_sha256="a" * 64,
                source_kind="FACTORY_STYLE",
            )

    def test_render_and_digest_are_deterministic(self) -> None:
        inputs = (
            observation(member="B/B_Var1.mid", style="B", velocities=(90,)),
            observation(member="A/A_Var1.mid", style="A", velocities=(70,)),
        )
        builder = ContextualProfileBuilder()
        first = builder.build_from_observations(
            inputs,
            source_id="SOURCE",
            source_path="factory.zip",
            source_sha256="a" * 64,
            source_kind="FACTORY_STYLE",
        )
        second = builder.build_from_observations(
            tuple(reversed(inputs)),
            source_id="SOURCE",
            source_path="factory.zip",
            source_sha256="a" * 64,
            source_kind="FACTORY_STYLE",
        )
        self.assertEqual(render_catalog(first), render_catalog(second))
        self.assertEqual(catalog_digest(first), catalog_digest(second))

    @unittest.skipUnless(FACTORY_ARCHIVE.is_file(), "Factory corpus nije dostupan")
    def test_full_factory_catalog_is_deterministic_and_read_only(self) -> None:
        before = FACTORY_ARCHIVE.read_bytes()
        catalog = ContextualProfileBuilder().build_factory_archive(FACTORY_ARCHIVE)
        self.assertEqual(catalog.source_sha256, FACTORY_SHA256)
        self.assertEqual(catalog.source_kind, "FACTORY_STYLE")
        self.assertEqual(catalog.observation_count, EXPECTED_OBSERVATIONS)
        self.assertEqual(catalog.profile_count, EXPECTED_PROFILES)
        self.assertEqual(catalog_digest(catalog), EXPECTED_DIGEST)
        self.assertTrue(all(
            item.key.source_kind == "FACTORY_STYLE"
            and item.safety_policy == "REFERENCE_ONLY_NO_SUGGEST_AUTHORIZATION"
            for item in catalog.profiles
        ))
        self.assertEqual(FACTORY_ARCHIVE.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
