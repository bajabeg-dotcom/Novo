"""RX trigger zone -- stavke 2.2 i 10 iz spiska nedovrsenog.

Dvije odvojene tvrdnje:

1. Granica RX guitar noise zone je **od 96 (C7) ukljucivo**, ne "iznad 96".
   Dokumentacija je na jednom mjestu tvrdila `iznad 96`; kod je ispravan i
   ovaj test to trajno fiksira.

2. Konzervativni optimizer **jos ne cita** oscillator konfiguraciju.
   To je poznata rupa (spisak 2.2: "Opci velocity optimizer jos ne cita tu
   konfiguraciju"). Zabiljezena je kao strict xfail, pa ce test sam
   prijaviti kad se rupa zatvori.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

CONFIG = Path(__file__).resolve().parents[2] / "config" / "performance-defaults.json"

# MIDI note number 96 == C7 u Pa800/Korg notaciji koju koristi config.
RX_GUITAR_TRIGGER_LOW = 96
RX_GUITAR_TRIGGER_HIGH = 127  # G9 je iznad MIDI opsega; 127 je stvarni maksimum


@pytest.fixture(scope="module")
def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


class TestTriggerBoundary:
    """Granica je inkluzivna: 95 nije trigger, 96 jeste."""

    def _is_trigger(self, pitch: int, role: str = "guitar") -> bool:
        # Ista formula kao arranging/factory_source.py:69
        return role in {"drums", "percussion"} or (
            role == "guitar" and (pitch < 24 or pitch >= RX_GUITAR_TRIGGER_LOW)
        )

    @pytest.mark.parametrize("pitch", [24, 60, 90, 94, 95])
    def test_below_c7_is_musical(self, pitch: int) -> None:
        assert not self._is_trigger(pitch), f"nota {pitch} nije trigger zona"

    @pytest.mark.parametrize("pitch", [96, 97, 108, 120, 127])
    def test_from_c7_upward_is_trigger(self, pitch: int) -> None:
        assert self._is_trigger(pitch), f"nota {pitch} MORA biti trigger zona"

    def test_boundary_is_inclusive_not_exclusive(self) -> None:
        """Explicitno protiv formulacije 'iznad 96'."""
        assert self._is_trigger(96), (
            "96 (C7) je UNUTAR trigger zone; dokumentacija koja kaze "
            "'iznad 96' je netacna"
        )
        assert not self._is_trigger(95)

    def test_very_low_guitar_notes_are_also_triggers(self) -> None:
        """Ispod 24 su fret/slide sampleovi, takodjer ne harmonija."""
        assert self._is_trigger(23)
        assert not self._is_trigger(24)


class TestConfiguredOscillators:
    def test_dist_guitar_noise_zone_starts_at_c7(self, config: dict) -> None:
        noise = [
            osc
            for osc in config["dist_guitar_rx"]["oscillators"]
            if osc.get("absolute_trigger")
        ]
        assert len(noise) == 1
        assert noise[0]["key_min"] == "C7"
        assert noise[0]["key_max"] == "G9"

    def test_dist_guitar_velocity_split_is_contiguous(self, config: dict) -> None:
        """1-87 mute, 88-127 distortion: bez rupe i bez preklapanja."""
        layers = [
            osc
            for osc in config["dist_guitar_rx"]["oscillators"]
            if not osc.get("absolute_trigger")
        ]
        spans = sorted((o["velocity_min"], o["velocity_max"]) for o in layers)

        assert spans[0][0] == 1
        assert spans[-1][1] == 127
        for (_, previous_max), (next_min, _) in itertools.pairwise(spans):
            assert next_min == previous_max + 1, "velocity zone moraju biti susjedne"

    def test_power_chord_layers_span_full_velocity(self, config: dict) -> None:
        """PowerChord: oba sloja 1-127; velocity je dinamika, ne artikulacija."""
        power = config["power_chord"]
        assert power["velocity_switches_articulation"] is False
        for layer in power["oscillators"]:
            assert layer["velocity_min"] == 1
            assert layer["velocity_max"] == 127

    def test_evidence_status_is_not_hardware_confirmed(self, config: dict) -> None:
        """Nijedan zvuk jos nije potvrdjen na uredjaju (P0 2.1)."""
        for key in ("default_drum_kit", "power_chord"):
            assert config[key]["status"] != "hardware_confirmed"


class TestOptimizerIsOscillatorAware:
    """Rupa N2 je zatvorena: velocity optimizer sada postuje RX zone.

    Testira se PONASANJE, ne prisustvo teksta u izvoru.
    """

    def _context(self, song):
        from pa800_enhancer.optimize.base import OptimizationContext
        from pa800_enhancer.profiles.models import DeviceProfile

        return OptimizationContext(song=song, device_profile=DeviceProfile("test"))

    def test_velocity_module_respects_articulation_zones(self) -> None:
        """Clamp na 127 ne smije preskociti iz Radni u Harm zonu."""
        from pa800_enhancer.optimize.velocity import VelocityRangeModule
        from pa800_enhancer.profiles.rx import builtin_rx_profiles
        from pa800_enhancer.smf.reader import SmfReader
        from tests.conftest import build_midi

        # Nota na velocity 90 = Radni zona (53-113) na Finger Bass RX.
        data = build_midi(
            fmt=0,
            ppq=192,
            tracks=[[(0, bytes([0x90, 40, 90])), (192, bytes([0x80, 40, 0]))]],
        )
        song = SmfReader().parse(data)
        bass = builtin_rx_profiles().by_id("finger-bass-rx")

        module = VelocityRangeModule(minimum=120, maximum=127, rx_profile=bass)
        changes = module.suggest(self._context(song))

        assert len(changes.changes) == 1
        # Bez RX svijesti bilo bi 120 (i preslo u Harm); sa njom staje na 113.
        assert changes.changes[0].new_value == 113

    def test_velocity_module_never_touches_trigger_notes(self) -> None:
        from pa800_enhancer.optimize.velocity import VelocityRangeModule
        from pa800_enhancer.profiles.rx import builtin_rx_profiles
        from pa800_enhancer.smf.reader import SmfReader
        from tests.conftest import build_midi

        # Nota 100 = C7+, apsolutni okidac.
        data = build_midi(
            fmt=0,
            ppq=192,
            tracks=[[(0, bytes([0x90, 100, 20])), (192, bytes([0x80, 100, 0]))]],
        )
        song = SmfReader().parse(data)
        bass = builtin_rx_profiles().by_id("finger-bass-rx")

        module = VelocityRangeModule(minimum=64, maximum=127, rx_profile=bass)
        changes = module.suggest(self._context(song))

        assert changes.changes == [], "trigger nota se ne smije mijenjati"

    def test_without_rx_profile_behaviour_is_unchanged(self) -> None:
        """Regresija: stari put mora raditi tacno kao prije."""
        from pa800_enhancer.optimize.velocity import VelocityRangeModule
        from pa800_enhancer.smf.reader import SmfReader
        from tests.conftest import build_midi

        data = build_midi(
            fmt=0,
            ppq=192,
            tracks=[[(0, bytes([0x90, 40, 90])), (192, bytes([0x80, 40, 0]))]],
        )
        song = SmfReader().parse(data)

        module = VelocityRangeModule(minimum=120, maximum=127)
        changes = module.suggest(self._context(song))

        assert len(changes.changes) == 1
        assert changes.changes[0].new_value == 120
