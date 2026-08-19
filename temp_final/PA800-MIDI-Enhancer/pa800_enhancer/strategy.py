from dataclasses import dataclass
from pathlib import Path
from .resources import ResourceResolver


@dataclass(frozen=True, slots=True)
class MidiAddress:
    bank_msb: int
    bank_lsb: int
    program: int
    channel: int | None = None

    @property
    def key(self) -> str:
        suffix = f":ch{self.channel}" if self.channel is not None else ""
        return f"{self.bank_msb}:{self.bank_lsb}:{self.program}{suffix}"


@dataclass(frozen=True, slots=True)
class PerformanceDefaults:
    default_drum_kit_name: str
    default_drum_kit: MidiAddress
    factory_power_chord_name: str
    factory_power_chord: MidiAddress
    reference_catalog: str
    require_catalog_evidence: bool = True
    factory_power_chord_velocity_switches: bool = False


DEFAULT_PERFORMANCE_STRATEGY = PerformanceDefaults(
    default_drum_kit_name="Pop Std. Kit RX",
    default_drum_kit=MidiAddress(120, 0, 4, 10),
    factory_power_chord_name="Power Chords",
    factory_power_chord=MidiAddress(121, 4, 30),
    reference_catalog=str(
        ResourceResolver().find(Path("data/performance-reference-catalog.json"), required=False)
        or ResourceResolver().locations().performance_catalog
    ),
)
