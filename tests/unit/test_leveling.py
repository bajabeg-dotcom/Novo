"""Konzervativni output leveling -- stavka 2.4.

Najvazniji test u modulu je `TestIntentionalQuietLayer`: normalizator koji
"popravi" namjerno tih layer unistava aranzman. Ta zastita mora drzati.
"""

from __future__ import annotations

import pytest

from pa800_enhancer.optimize.leveling import (
    LOUDNESS_BUDGET,
    MAX_DELTA,
    VOLUME_CEILING,
    VOLUME_FLOOR,
    ChannelStatistics,
    Intensity,
    collect_channel_statistics,
    level_song,
    plan_leveling,
)
from pa800_enhancer.smf.reader import SmfReader
from tests.conftest import build_midi


def stat(
    channel: int,
    role: str,
    velocity: float,
    *,
    density: float = 2.0,
    pitch: float = 60,
    volume: int | None = 100,
    notes: int = 50,
) -> ChannelStatistics:
    return ChannelStatistics(
        channel=channel,
        role=role,
        note_count=notes,
        velocity_median=velocity,
        velocity_peak=int(min(127, velocity + 20)),
        density_per_beat=density,
        pitch_median=pitch,
        current_volume=volume,
    )


class TestIntentionalQuietLayer:
    """Namjerno tih layer se NE dize -- najvaznije pravilo modula."""

    def test_quiet_layer_is_protected(self) -> None:
        stats = (
            stat(1, "accompaniment", 100),
            stat(2, "accompaniment", 100),
            stat(3, "accompaniment", 45),  # echo/doubling layer
        )

        plan = plan_leveling(stats)

        quiet = next(d for d in plan.decisions if d.channel == 3)
        assert quiet.protected
        assert not quiet.is_change
        assert "namjerno tih" in quiet.reason

    def test_protected_layer_survives_budget_reduction(self) -> None:
        stats = (
            stat(1, "bass", 120, volume=122),
            stat(2, "drums", 120, volume=122),
            stat(3, "guitar", 120, volume=122),
            stat(4, "accompaniment", 50, volume=80),  # tihi layer
        )

        plan = plan_leveling(stats)

        quiet = next(d for d in plan.decisions if d.channel == 4)
        assert quiet.protected
        assert quiet.proposed_volume == 80, "budzet ne smije dirati zasticeni layer"

    def test_uniformly_quiet_song_is_not_all_protected(self) -> None:
        """Ako su SVI tihi, to je stil pjesme, ne layer odnos."""
        stats = (
            stat(1, "accompaniment", 50),
            stat(2, "guitar", 52),
            stat(3, "bass", 48),
        )

        plan = plan_leveling(stats)

        assert not plan.protected, "nijedan nije relativno tisi od ostalih"

    def test_borderline_layer_is_not_over_protected(self) -> None:
        """Na 80 % medijana kanal jos nije 'namjerno tih'."""
        stats = (
            stat(1, "accompaniment", 100),
            stat(2, "accompaniment", 100),
            stat(3, "accompaniment", 80),
        )

        plan = plan_leveling(stats)

        assert not any(d.protected for d in plan.decisions)


class TestBassKickMasking:
    def test_low_drums_do_not_rise_against_bass(self) -> None:
        stats = (
            stat(9, "bass", 90, pitch=40, volume=100),
            stat(10, "drums", 92, pitch=38, volume=100),  # kick registar
        )

        plan = plan_leveling(stats)

        drums = next(d for d in plan.decisions if d.channel == 10)
        assert drums.proposed_volume <= drums.current_volume
        assert "prostor bassu" in drums.reason

    def test_bass_gains_headroom_when_kick_present(self) -> None:
        stats = (
            stat(9, "bass", 90, pitch=40, volume=100),
            stat(10, "drums", 92, pitch=38, volume=100),
        )

        plan = plan_leveling(stats)

        bass = next(d for d in plan.decisions if d.channel == 9)
        assert bass.proposed_volume > bass.current_volume
        assert "maskiranja" in bass.reason

    def test_high_drums_are_not_treated_as_kick(self) -> None:
        stats = (
            stat(9, "bass", 90, pitch=40),
            stat(10, "drums", 90, pitch=70),  # hat/ride registar
        )

        plan = plan_leveling(stats)

        drums = next(d for d in plan.decisions if d.channel == 10)
        assert "prostor bassu" not in drums.reason


class TestAntiClipping:
    def test_budget_reduces_overloaded_mix(self) -> None:
        """Sve uloge sa visokim ciljem (bass 114) prelaze budzet od 112."""
        stats = tuple(
            stat(c, "bass", 120, pitch=40, volume=122) for c in range(1, 6)
        )

        plan = plan_leveling(stats, intensity=Intensity.STRONG)

        assert plan.budget_applied
        average = sum(d.proposed_volume for d in plan.decisions) / len(plan.decisions)
        assert average <= LOUDNESS_BUDGET + 1

    def test_role_targets_alone_usually_stay_in_budget(self) -> None:
        """Zdrav miks ne treba budzet -- ciljevi uloga ga vec drze."""
        stats = tuple(
            stat(c, "guitar", 100, volume=122) for c in range(1, 6)
        )

        plan = plan_leveling(stats, intensity=Intensity.STRONG)

        assert not plan.budget_applied
        assert all(d.proposed_volume <= 104 for d in plan.decisions)

    def test_quiet_mix_needs_no_budget(self) -> None:
        stats = (stat(1, "accompaniment", 70, volume=90),)

        plan = plan_leveling(stats)

        assert not plan.budget_applied

    def test_never_below_floor(self) -> None:
        stats = tuple(stat(c, "guitar", 127, volume=122) for c in range(1, 9))

        plan = plan_leveling(stats, intensity=Intensity.STRONG)

        for decision in plan.decisions:
            assert decision.proposed_volume >= VOLUME_FLOOR


class TestNoSuddenJumps:
    @pytest.mark.parametrize("mode", ["light", "balanced", "strong"])
    def test_delta_respects_intensity(self, mode: str) -> None:
        stats = (stat(1, "bass", 90, volume=VOLUME_FLOOR),)

        plan = plan_leveling(stats, intensity=mode)

        assert abs(plan.decisions[0].delta) <= MAX_DELTA[mode]

    def test_light_moves_less_than_strong(self) -> None:
        stats = (stat(1, "bass", 90, volume=80),)

        light = plan_leveling(stats, intensity="light").decisions[0]
        strong = plan_leveling(stats, intensity="strong").decisions[0]

        assert abs(light.delta) < abs(strong.delta)

    def test_never_above_ceiling(self) -> None:
        stats = (stat(1, "bass", 90, volume=VOLUME_CEILING),)

        plan = plan_leveling(stats, intensity="strong")

        assert plan.decisions[0].proposed_volume <= VOLUME_CEILING


class TestVelocityIsNeverTouched:
    def test_plan_only_describes_cc7(self) -> None:
        """Plan ne smije sadrzavati nikakvu velocity izmjenu."""
        stats = (stat(1, "bass", 90), stat(2, "guitar", 100))

        plan = plan_leveling(stats)

        for decision in plan.decisions:
            assert hasattr(decision, "proposed_volume")
            assert not hasattr(decision, "velocity")

    def test_level_song_does_not_mutate(self, multi_track_midi) -> None:
        song = SmfReader().read(multi_track_midi)
        before = [
            (e.absolute_tick, e.channel, bytes(e.data))
            for t in song.tracks
            for e in t.events
        ]

        level_song(song)

        after = [
            (e.absolute_tick, e.channel, bytes(e.data))
            for t in song.tracks
            for e in t.events
        ]
        assert after == before, "planiranje ne smije mijenjati pjesmu"


class TestStatisticsCollection:
    def test_reads_channels_from_song(self, multi_track_midi) -> None:
        song = SmfReader().read(multi_track_midi)

        stats = collect_channel_statistics(song)

        assert stats
        assert all(s.note_count > 0 for s in stats)

    def test_picks_up_existing_cc7(self) -> None:
        data = build_midi(
            fmt=0,
            ppq=192,
            tracks=[
                [
                    (0, bytes([0xB0, 7, 88])),
                    (0, bytes([0x90, 60, 100])),
                    (192, bytes([0x80, 60, 0])),
                ]
            ],
        )
        song = SmfReader().parse(data)

        stats = collect_channel_statistics(song)

        assert stats[0].current_volume == 88

    def test_channel_10_defaults_to_drums(self) -> None:
        data = build_midi(
            fmt=0,
            ppq=192,
            tracks=[[(0, bytes([0x99, 36, 100])), (192, bytes([0x89, 36, 0]))]],
        )
        song = SmfReader().parse(data)

        stats = collect_channel_statistics(song)

        assert stats[0].channel == 10
        assert stats[0].role == "drums"

    def test_empty_song_produces_empty_plan(self, simple_midi) -> None:
        song = SmfReader().read(simple_midi)
        plan = plan_leveling(())

        assert plan.decisions == ()
        assert plan.summary()["channels"] == 0


class TestPlanSummary:
    def test_summary_reports_counts(self) -> None:
        stats = (
            stat(1, "bass", 100, volume=90),
            stat(2, "accompaniment", 40, volume=70),
        )

        summary = plan_leveling(stats).summary()

        assert summary["channels"] == 2
        assert summary["protected"] == 1
        assert summary["intensity"] == "balanced"
