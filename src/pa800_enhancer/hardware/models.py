from dataclasses import dataclass, field
from typing import Any


HARDWARE_TEST_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class HardwareFixture:
    path: str
    sha256: str
    license: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class DeviceUnderTest:
    model: str
    os_version: str
    musical_resources_version: str | None
    state: dict[str, str]
    serial_number: str | None = None


@dataclass(frozen=True, slots=True)
class HardwareAssertion:
    assertion_id: str
    kind: str
    expected: dict[str, Any]
    description: str = ""


@dataclass(frozen=True, slots=True)
class AssertionObservation:
    status: str
    actual: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class AudioReference:
    locator: str
    sha256: str | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class HardwareTestCycle:
    cycle: int
    status: str
    tested_at: str | None = None
    tester: str | None = None
    output_midi_sha256: str | None = None
    observations: dict[str, AssertionObservation] = field(default_factory=dict)
    log: tuple[str, ...] = ()
    audio_reference: AudioReference | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class HardwareTestCase:
    case_id: str
    case_version: str
    title: str
    fixture: HardwareFixture
    device: DeviceUnderTest
    assertions: tuple[HardwareAssertion, ...]
    cycles: tuple[HardwareTestCycle, ...]
    schema_version: int = HARDWARE_TEST_SCHEMA_VERSION
    extensions: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        statuses = {cycle.status for cycle in self.cycles}
        if "failed" in statuses:
            return "failed"
        if statuses == {"passed"} and len(self.cycles) == 2:
            return "passed"
        return "pending"


@dataclass(frozen=True, slots=True)
class HardwarePreflight:
    case_id: str
    case_version: str
    case_status: str
    manifest_sha256: str
    device_model: str
    os_version: str
    musical_resources_version: str | None
    fixture_path: str
    fixture_sha256: str | None
    smf_format: int | None
    division: int | None
    track_count: int | None
    event_count: int | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers
