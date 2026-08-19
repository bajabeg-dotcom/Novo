import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .models import (
    HARDWARE_TEST_SCHEMA_VERSION,
    AssertionObservation,
    AudioReference,
    DeviceUnderTest,
    HardwareAssertion,
    HardwareFixture,
    HardwareTestCase,
    HardwareTestCycle,
)


ASSERTION_KINDS = {
    "sound_identity",
    "drum_note",
    "controller",
    "sysex",
    "initialization",
    "round_trip",
    "rx_dnc",
    "audible_behavior",
}
CYCLE_STATUSES = {"pending", "passed", "failed"}
OBSERVATION_STATUSES = {"passed", "failed", "not_tested"}
TOP_LEVEL_KEYS = {
    "schema_version",
    "case_version",
    "case_id",
    "title",
    "fixture",
    "device",
    "assertions",
    "cycles",
    "extensions",
}


class HardwareTestFormatError(ValueError):
    pass


def _is_unsafe_relative_path(value: str) -> bool:
    """Reject rooted and parent-traversing paths on every supported host OS."""
    if "\x00" in value:
        return True
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    return (
        windows_path.is_absolute()
        or bool(windows_path.drive)
        or posix_path.is_absolute()
        or ".." in windows_path.parts
        or ".." in posix_path.parts
    )


class HardwareTestLoader:
    def load(self, path: Path) -> HardwareTestCase:
        try:
            return self.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise HardwareTestFormatError(f"cannot read hardware test {path}: {error}") from error

    def loads(self, text: str) -> HardwareTestCase:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise HardwareTestFormatError(f"invalid hardware test JSON: {error}") from error
        return self.from_data(data)

    def from_data(self, data: object) -> HardwareTestCase:
        root = self._object(data, "hardware test root")
        unknown = set(root) - TOP_LEVEL_KEYS
        if unknown:
            raise HardwareTestFormatError(f"unknown top-level fields: {', '.join(sorted(unknown))}")
        version = self._integer(root.get("schema_version"), "schema_version")
        if version != HARDWARE_TEST_SCHEMA_VERSION:
            raise HardwareTestFormatError(
                f"hardware test schema {version} is not supported; expected {HARDWARE_TEST_SCHEMA_VERSION}"
            )

        fixture_data = self._object(root.get("fixture"), "fixture")
        fixture = HardwareFixture(
            path=self._text(fixture_data.get("path"), "fixture.path"),
            sha256=self._sha256(fixture_data.get("sha256"), "fixture.sha256"),
            license=self._text(fixture_data.get("license"), "fixture.license"),
            description=self._optional_text(fixture_data.get("description"), "fixture.description") or "",
        )
        if _is_unsafe_relative_path(fixture.path):
            raise HardwareTestFormatError(
                "fixture.path must stay relative to the test manifest directory"
            )

        device_data = self._object(root.get("device"), "device")
        state_data = self._object(device_data.get("state"), "device.state")
        if not state_data:
            raise HardwareTestFormatError("device.state must record at least one device setting")
        state = {self._text(key, "device.state key"): self._text(value, f"device.state.{key}") for key, value in state_data.items()}
        device = DeviceUnderTest(
            model=self._text(device_data.get("model"), "device.model"),
            os_version=self._text(device_data.get("os_version"), "device.os_version"),
            musical_resources_version=self._optional_text(
                device_data.get("musical_resources_version"), "device.musical_resources_version"
            ),
            state=state,
            serial_number=self._optional_text(device_data.get("serial_number"), "device.serial_number"),
        )

        assertions = self._assertions(root.get("assertions"))
        cycles = self._cycles(root.get("cycles"), assertions)
        return HardwareTestCase(
            case_id=self._text(root.get("case_id"), "case_id"),
            case_version=self._text(root.get("case_version"), "case_version"),
            title=self._text(root.get("title"), "title"),
            fixture=fixture,
            device=device,
            assertions=assertions,
            cycles=cycles,
            schema_version=version,
            extensions=self._object(root.get("extensions", {}), "extensions"),
        )

    def _assertions(self, value: object) -> tuple[HardwareAssertion, ...]:
        assertions = []
        seen = set()
        for index, raw in enumerate(self._array(value, "assertions")):
            path = f"assertions[{index}]"
            item = self._object(raw, path)
            assertion_id = self._text(item.get("assertion_id"), f"{path}.assertion_id")
            if assertion_id in seen:
                raise HardwareTestFormatError(f"duplicate assertion_id: {assertion_id}")
            seen.add(assertion_id)
            kind = self._text(item.get("kind"), f"{path}.kind")
            if kind not in ASSERTION_KINDS:
                raise HardwareTestFormatError(f"{path}.kind is not recognized: {kind}")
            expected = self._object(item.get("expected"), f"{path}.expected")
            if not expected:
                raise HardwareTestFormatError(f"{path}.expected must not be empty")
            assertions.append(
                HardwareAssertion(
                    assertion_id=assertion_id,
                    kind=kind,
                    expected=expected,
                    description=self._optional_text(item.get("description"), f"{path}.description") or "",
                )
            )
        if not assertions:
            raise HardwareTestFormatError("assertions must not be empty")
        return tuple(assertions)

    def _cycles(
        self, value: object, assertions: tuple[HardwareAssertion, ...]
    ) -> tuple[HardwareTestCycle, ...]:
        assertion_ids = {item.assertion_id for item in assertions}
        cycles = []
        for index, raw in enumerate(self._array(value, "cycles")):
            path = f"cycles[{index}]"
            item = self._object(raw, path)
            cycle_number = self._integer(item.get("cycle"), f"{path}.cycle")
            status = self._text(item.get("status"), f"{path}.status")
            if status not in CYCLE_STATUSES:
                raise HardwareTestFormatError(f"{path}.status is not recognized: {status}")
            observations = self._observations(item.get("observations", {}), path)
            unknown = set(observations) - assertion_ids
            if unknown:
                raise HardwareTestFormatError(f"{path} references unknown assertions: {', '.join(sorted(unknown))}")
            tested_at = self._optional_text(item.get("tested_at"), f"{path}.tested_at")
            tester = self._optional_text(item.get("tester"), f"{path}.tester")
            output_midi_sha256 = self._optional_sha256(
                item.get("output_midi_sha256"), f"{path}.output_midi_sha256"
            )
            log = tuple(
                self._text(entry, f"{path}.log")
                for entry in self._array(item.get("log", []), f"{path}.log")
            )
            if tested_at is not None:
                try:
                    date.fromisoformat(tested_at)
                except ValueError as error:
                    raise HardwareTestFormatError(f"{path}.tested_at must be an ISO date") from error
            if status != "pending":
                if not tested_at or not tester or not output_midi_sha256 or not log:
                    raise HardwareTestFormatError(
                        f"{path} completed cycle requires tested_at, tester, "
                        "output_midi_sha256 and a non-empty log"
                    )
                missing = assertion_ids - set(observations)
                if missing:
                    raise HardwareTestFormatError(f"{path} lacks observations for: {', '.join(sorted(missing))}")
                if status == "passed" and any(item.status != "passed" for item in observations.values()):
                    raise HardwareTestFormatError(f"{path} cannot pass unless every assertion passed")
                if status == "failed" and not any(item.status == "failed" for item in observations.values()):
                    raise HardwareTestFormatError(f"{path} failed cycle requires at least one failed assertion")
            audio = self._audio(item.get("audio_reference"), path)
            cycles.append(
                HardwareTestCycle(
                    cycle=cycle_number,
                    status=status,
                    tested_at=tested_at,
                    tester=tester,
                    output_midi_sha256=output_midi_sha256,
                    observations=observations,
                    log=log,
                    audio_reference=audio,
                    notes=self._optional_text(item.get("notes"), f"{path}.notes") or "",
                )
            )
        if sorted(item.cycle for item in cycles) != [1, 2]:
            raise HardwareTestFormatError("cycles must contain exactly cycle 1 and cycle 2")
        return tuple(sorted(cycles, key=lambda item: item.cycle))

    def _observations(self, value: object, path: str) -> dict[str, AssertionObservation]:
        result = {}
        for assertion_id, raw in self._object(value, f"{path}.observations").items():
            item = self._object(raw, f"{path}.observations.{assertion_id}")
            status = self._text(item.get("status"), f"{path}.observations.{assertion_id}.status")
            if status not in OBSERVATION_STATUSES:
                raise HardwareTestFormatError(
                    f"{path}.observations.{assertion_id}.status is not recognized: {status}"
                )
            result[assertion_id] = AssertionObservation(
                status=status,
                actual=self._optional_text(item.get("actual"), f"{path}.observations.{assertion_id}.actual") or "",
                notes=self._optional_text(item.get("notes"), f"{path}.observations.{assertion_id}.notes") or "",
            )
        return result

    def _audio(self, value: object, path: str) -> AudioReference | None:
        if value is None:
            return None
        item = self._object(value, f"{path}.audio_reference")
        return AudioReference(
            locator=self._text(item.get("locator"), f"{path}.audio_reference.locator"),
            sha256=self._optional_sha256(item.get("sha256"), f"{path}.audio_reference.sha256"),
            notes=self._optional_text(item.get("notes"), f"{path}.audio_reference.notes") or "",
        )

    def dumps(self, case: HardwareTestCase, *, indent: int = 2) -> str:
        return json.dumps(asdict(case), ensure_ascii=False, indent=indent, sort_keys=True) + "\n"

    def digest(self, case: HardwareTestCase) -> str:
        canonical = json.dumps(asdict(case), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _object(value: object, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise HardwareTestFormatError(f"{path} must be a JSON object")
        return value

    @staticmethod
    def _array(value: object, path: str) -> list[Any]:
        if not isinstance(value, list):
            raise HardwareTestFormatError(f"{path} must be a JSON array")
        return value

    @staticmethod
    def _text(value: object, path: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise HardwareTestFormatError(f"{path} must be a non-empty string")
        return value

    @staticmethod
    def _optional_text(value: object, path: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise HardwareTestFormatError(f"{path} must be a string or null")
        return value

    @staticmethod
    def _integer(value: object, path: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise HardwareTestFormatError(f"{path} must be an integer")
        return value

    def _sha256(self, value: object, path: str) -> str:
        result = self._text(value, path).lower()
        if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
            raise HardwareTestFormatError(f"{path} must contain 64 hexadecimal characters")
        return result

    def _optional_sha256(self, value: object, path: str) -> str | None:
        return None if value is None else self._sha256(value, path)
