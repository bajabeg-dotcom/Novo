"""RX profili i velocity guard -- stavka 2.2 i rupa N2.

Kljucna tvrdnja: na RX zvuku velocity bira oscilator, tj. artikulaciju.
Optimizer koji to ignorise tiho mijenja nacin sviranja.
"""

from __future__ import annotations

import pytest

from pa800_enhancer.optimize.rx_guard import (
    GuardVerdict,
    RxVelocityGuard,
    VelocityProposal,
)
from pa800_enhancer.profiles.rx import (
    TRIGGER_ZONE_LOW,
    OscillatorZone,
    RxProfileError,
    RxSoundProfile,
    builtin_rx_profiles,
    is_absolute_trigger_note,
)


@pytest.fixture(scope="module")
def profiles():
    return builtin_rx_profiles()


@pytest.fixture(scope="module")
def finger_bass(profiles):
    return profiles.by_id("finger-bass-rx")


@pytest.fixture(scope="module")
def clean_guitar(profiles):
    return profiles.by_id("clean-guitar-rx1")


class TestProfileSet:
    def test_expected_profiles_exist(self, profiles) -> None:
        ids = {p.profile_id for p in profiles}
        assert "finger-bass-rx" in ids
        assert "picked-bass-rx" in ids
        assert "slapfing-bass-rx" in ids
        assert "slappick-bass-rx" in ids
        assert "dist-guitar-rx" in ids
        assert "power-chords" in ids
        assert len(profiles.by_family("guitar")) == 8  # 6 clean + dist + power

    def test_nothing_claims_hardware_confirmation(self, profiles) -> None:
        """P0 2.1: bez uredjaja nema `hardware_confirmed`."""
        for profile in profiles:
            assert profile.evidence_status != "hardware_confirmed"

    def test_every_profile_cites_evidence(self, profiles) -> None:
        for profile in profiles:
            assert profile.evidence, f"{profile.profile_id} nema izvor"


class TestZoneValidation:
    def test_rejects_inverted_velocity_range(self) -> None:
        with pytest.raises(RxProfileError):
            OscillatorZone(1, "bad", velocity_min=100, velocity_max=50)

    def test_rejects_velocity_zero(self) -> None:
        with pytest.raises(RxProfileError):
            OscillatorZone(1, "bad", velocity_min=0, velocity_max=50)

    def test_rejects_unknown_evidence_status(self) -> None:
        with pytest.raises(RxProfileError):
            RxSoundProfile(
                profile_id="x",
                display_name="x",
                family="bass",
                zones=(OscillatorZone(1, "z", 1, 127),),
                evidence_status="izmisljeno",
            )

    def test_rejects_profile_without_zones(self) -> None:
        with pytest.raises(RxProfileError):
            RxSoundProfile(
                profile_id="x", display_name="x", family="bass", zones=()
            )


class TestBassZones:
    """Finger Bass RX: Gliss 1-22, Stop 23-52, Radni 53-113, Harm 114-127."""

    @pytest.mark.parametrize(
        "velocity,expected",
        [(1, "Gliss"), (22, "Gliss"), (23, "Stop"), (52, "Stop"),
         (53, "Radni"), (113, "Radni"), (114, "Harm"), (127, "Harm")],
    )
    def test_zone_boundaries(self, finger_bass, velocity, expected) -> None:
        zone = finger_bass.zone_for(40, velocity)
        assert zone is not None
        assert zone.name == expected

    def test_slap_uses_corrected_switch_87(self, profiles) -> None:
        """Ispravka iz Oscilatori.txt: prag je 87, ne 94."""
        slap = profiles.by_id("slapfing-bass-rx")
        radni = next(z for z in slap.zones if z.name.startswith("Radni"))
        assert radni.switch == 87

    def test_slap_documents_pending_hardware_check(self, profiles) -> None:
        slap = profiles.by_id("slapfing-bass-rx")
        assert "PCG" in slap.notes or "Sound Edit" in slap.notes


class TestTriggerZone:
    def test_c7_is_trigger_on_every_rx_sound(self, profiles) -> None:
        for profile in profiles:
            if profile.profile_id == "power-chords":
                continue  # nema noise sloj
            assert profile.is_trigger_note(TRIGGER_ZONE_LOW), profile.profile_id

    def test_b6_is_still_musical(self, finger_bass, clean_guitar) -> None:
        assert not finger_bass.is_trigger_note(95)
        assert not clean_guitar.is_trigger_note(95)

    def test_musical_zones_exclude_noise(self, finger_bass) -> None:
        names = {z.name for z in finger_bass.musical_zones()}
        assert "Noise" not in names
        assert len(finger_bass.musical_zones()) == 4

    def test_helper_without_profile(self) -> None:
        assert is_absolute_trigger_note(96, "guitar")
        assert is_absolute_trigger_note(96, "bass")
        assert not is_absolute_trigger_note(95, "guitar")
        assert is_absolute_trigger_note(23, "guitar")  # niski fret sampleovi
        assert not is_absolute_trigger_note(60, "accompaniment")


class TestArticulationDetection:
    def test_change_within_zone_is_safe(self, finger_bass) -> None:
        assert not finger_bass.articulation_changes(40, 60, 100)  # oba Radni

    def test_crossing_zone_is_detected(self, finger_bass) -> None:
        assert finger_bass.articulation_changes(40, 110, 120)  # Radni -> Harm
        assert finger_bass.articulation_changes(40, 50, 60)    # Stop -> Radni

    def test_identical_velocity_is_never_a_change(self, finger_bass) -> None:
        assert not finger_bass.articulation_changes(40, 90, 90)

    def test_safe_span_matches_zone(self, finger_bass) -> None:
        assert finger_bass.safe_velocity_span(40, 90) == (53, 113)
        assert finger_bass.safe_velocity_span(40, 120) == (114, 127)

    def test_clamp_stops_at_zone_edge(self, finger_bass) -> None:
        # Zeljeni 127 iz Radni zone staje na 113.
        assert finger_bass.clamp_velocity(40, 90, 127) == 113
        assert finger_bass.clamp_velocity(40, 90, 100) == 100

    def test_power_chord_velocity_is_pure_dynamics(self, profiles) -> None:
        """Oba sloja 1-127: nijedna izmjena ne mijenja artikulaciju."""
        power = profiles.by_id("power-chords")
        assert not power.articulation_changes(50, 1, 127)
        assert power.safe_velocity_span(50, 64) == (1, 127)


class TestVelocityGuard:
    def test_blocks_trigger_notes(self, finger_bass) -> None:
        guard = RxVelocityGuard()
        proposal = VelocityProposal("e1", note=100, old_velocity=80, new_velocity=110)

        decision = guard.review_one(proposal, finger_bass)

        assert decision.verdict is GuardVerdict.BLOCKED_TRIGGER
        assert decision.applied_velocity == 80
        assert not decision.is_change

    def test_allows_change_inside_zone(self, finger_bass) -> None:
        guard = RxVelocityGuard()
        proposal = VelocityProposal("e1", note=40, old_velocity=60, new_velocity=100)

        decision = guard.review_one(proposal, finger_bass)

        assert decision.verdict is GuardVerdict.ALLOWED
        assert decision.applied_velocity == 100

    def test_clamps_instead_of_switching_articulation(self, finger_bass) -> None:
        guard = RxVelocityGuard(allow_clamping=True)
        proposal = VelocityProposal("e1", note=40, old_velocity=90, new_velocity=127)

        decision = guard.review_one(proposal, finger_bass)

        assert decision.verdict is GuardVerdict.CLAMPED
        assert decision.applied_velocity == 113, "staje na granicu Radni zone"

    def test_blocks_when_clamping_disabled(self, finger_bass) -> None:
        guard = RxVelocityGuard(allow_clamping=False)
        proposal = VelocityProposal("e1", note=40, old_velocity=90, new_velocity=127)

        decision = guard.review_one(proposal, finger_bass)

        assert decision.verdict is GuardVerdict.BLOCKED_ARTICULATION
        assert decision.applied_velocity == 90

    def test_blocks_insufficient_evidence(self) -> None:
        weak = RxSoundProfile(
            profile_id="guess",
            display_name="Guess",
            family="bass",
            zones=(OscillatorZone(1, "a", 1, 60), OscillatorZone(2, "b", 61, 127)),
            evidence_status="hypothesis",
            evidence=("nagadjanje",),
        )
        guard = RxVelocityGuard()
        decision = guard.review_one(
            VelocityProposal("e1", note=40, old_velocity=30, new_velocity=90), weak
        )

        assert decision.verdict is GuardVerdict.BLOCKED_EVIDENCE
        assert decision.applied_velocity == 30

    def test_no_profile_still_blocks_trigger_by_role(self) -> None:
        guard = RxVelocityGuard()
        proposal = VelocityProposal(
            "e1", note=100, old_velocity=80, new_velocity=110, role="guitar"
        )

        decision = guard.review_one(proposal, None)

        assert decision.verdict is GuardVerdict.BLOCKED_TRIGGER


class TestGuardReport:
    def test_report_separates_outcomes(self, finger_bass) -> None:
        guard = RxVelocityGuard()
        proposals = [
            VelocityProposal("safe", 40, 60, 100),      # allowed
            VelocityProposal("edge", 41, 90, 127),      # clamped
            VelocityProposal("noise", 100, 80, 110),    # blocked trigger
        ]

        report = guard.review(proposals, default_profile=finger_bass)

        assert len(report.decisions) == 3
        assert len(report.clamped) == 1
        assert len(report.blocked) == 1
        assert report.summary()["blocked_absolute_trigger"] == 1

    def test_per_event_profiles(self, profiles) -> None:
        guard = RxVelocityGuard()
        bass = profiles.by_id("finger-bass-rx")
        power = profiles.by_id("power-chords")
        proposals = [
            VelocityProposal("b", 40, 90, 127),
            VelocityProposal("p", 40, 90, 127),
        ]

        report = guard.review(
            proposals, profile_for={"b": bass, "p": power}
        )

        by_id = {d.proposal.event_id: d for d in report.decisions}
        assert by_id["b"].verdict is GuardVerdict.CLAMPED
        assert by_id["p"].verdict is GuardVerdict.ALLOWED
