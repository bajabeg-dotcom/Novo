from dataclasses import dataclass, field
from typing import Any


PROFILE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class RhythmProfile:
    profile_id: str
    display_name: str
    meters: tuple[tuple[int, int], ...]
    groupings: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ProfileSource:
    source_id: str
    kind: str
    title: str
    locator: str = ""
    captured_at: str | None = None
    sha256: str | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Evidence:
    source_ids: tuple[str, ...]
    status: str = "documented"
    tested_os_version: str | None = None
    tested_at: str | None = None
    test_reference: str | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class SoundProfile:
    sound_id: str
    display_name: str
    bank_msb: int
    bank_lsb: int
    program: int
    family: str = "unknown"
    note_range: tuple[int, int] | None = None
    mode: str = "unknown"
    evidence: dict[str, Evidence] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DrumNoteProfile:
    note: int
    display_name: str
    family: str = "unknown"
    velocity_layers: tuple[tuple[int, int, str], ...] = ()
    choke_group: str | None = None
    evidence: dict[str, Evidence] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DrumKitProfile:
    kit_id: str
    display_name: str
    bank_msb: int
    bank_lsb: int
    program: int
    notes: dict[int, DrumNoteProfile] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DeviceProfile:
    profile_id: str
    model: str = "Korg Pa800"
    os_version: str | None = None
    profile_version: str = "0.1.0"
    schema_version: int = PROFILE_SCHEMA_VERSION
    musical_resources_version: str | None = None
    sources: dict[str, ProfileSource] = field(default_factory=dict)
    sounds: dict[str, SoundProfile] = field(default_factory=dict)
    drum_kits: dict[str, DrumKitProfile] = field(default_factory=dict)
    rhythm_profiles: dict[str, RhythmProfile] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)
