import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..smf.errors import SmfError
from ..smf.reader import SmfReader
from ..validation.validator import SongValidator
from .loader import HardwareTestLoader
from .models import (
    AssertionObservation,
    AudioReference,
    HardwareTestCase,
    HardwareTestCycle,
)


@dataclass(frozen=True, slots=True)
class HardwareCycleRecord:
    case: HardwareTestCase
    cycle: int
    cycle_status: str
    case_status: str
    output_midi_sha256: str
    manifest_sha256: str


def record_hardware_cycle(
    case: HardwareTestCase,
    *,
    cycle: int,
    status: str,
    tested_at: str,
    tester: str,
    output_midi_path: Path,
    observations: dict[str, Any],
    log: tuple[str, ...],
    notes: str = "",
    audio_reference: AudioReference | None = None,
) -> HardwareCycleRecord:
    if cycle not in (1, 2):
        raise ValueError("hardware cycle must be 1 or 2")
    if status not in {"passed", "failed"}:
        raise ValueError("completed hardware cycle status must be passed or failed")
    existing = next(item for item in case.cycles if item.cycle == cycle)
    if existing.status != "pending":
        raise ValueError(f"hardware cycle {cycle} is already completed")
    if cycle == 2:
        first = next(item for item in case.cycles if item.cycle == 1)
        if first.status == "pending":
            raise ValueError("hardware cycle 1 must be completed before cycle 2")
    if not tester.strip():
        raise ValueError("tester must not be empty")
    cleaned_log = tuple(item.strip() for item in log if item.strip())
    if not cleaned_log:
        raise ValueError("hardware cycle requires at least one log entry")

    try:
        midi_bytes = output_midi_path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read output MIDI {output_midi_path}: {error}") from error
    digest = hashlib.sha256(midi_bytes).hexdigest()
    try:
        song = SmfReader().parse(midi_bytes)
    except SmfError as error:
        raise ValueError(f"output MIDI is not a valid SMF: {error}") from error
    blockers = [issue for issue in SongValidator().validate(song) if issue.blocks_export]
    if blockers:
        messages = "; ".join(f"{item.code}: {item.message}" for item in blockers)
        raise ValueError(f"output MIDI failed validation: {messages}")

    assertion_ids = {item.assertion_id for item in case.assertions}
    unknown = set(observations) - assertion_ids
    missing = assertion_ids - set(observations)
    if unknown:
        raise ValueError(f"observations reference unknown assertions: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"observations are missing assertions: {', '.join(sorted(missing))}")
    parsed_observations = {
        assertion_id: _observation(assertion_id, observations[assertion_id])
        for assertion_id in sorted(assertion_ids)
    }
    updated_cycle = HardwareTestCycle(
        cycle=cycle,
        status=status,
        tested_at=tested_at,
        tester=tester.strip(),
        output_midi_sha256=digest,
        observations=parsed_observations,
        log=cleaned_log,
        audio_reference=audio_reference,
        notes=notes,
    )
    cycles = tuple(
        updated_cycle if item.cycle == cycle else item for item in case.cycles
    )
    loader = HardwareTestLoader()
    validated = loader.loads(loader.dumps(replace(case, cycles=cycles)))
    return HardwareCycleRecord(
        case=validated,
        cycle=cycle,
        cycle_status=updated_cycle.status,
        case_status=validated.status,
        output_midi_sha256=digest,
        manifest_sha256=loader.digest(validated),
    )


def _observation(assertion_id: str, value: Any) -> AssertionObservation:
    if not isinstance(value, dict):
        raise ValueError(f"observation {assertion_id} must be a JSON object")
    status = value.get("status")
    if status not in {"passed", "failed", "not_tested"}:
        raise ValueError(f"observation {assertion_id} has invalid status: {status}")
    actual = value.get("actual", "")
    notes = value.get("notes", "")
    if not isinstance(actual, str) or not isinstance(notes, str):
        raise ValueError(f"observation {assertion_id} actual/notes must be strings")
    return AssertionObservation(status=status, actual=actual, notes=notes)
