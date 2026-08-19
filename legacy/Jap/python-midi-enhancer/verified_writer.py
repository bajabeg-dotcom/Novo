"""Atomic no-overwrite writer for independently verified MIDI bytes.

W01 accepts only a PASS VerificationResult, rechecks the original source on
disk, writes same-directory temporary files, and publishes MIDI plus JSON report
with hard-link create-if-absent semantics. Any failure removes artifacts created
by that call. The original file is never opened for writing.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from change_engine import ChangeExecutionResult, ChangeExecutionStatus
from change_plan import ChangePlan, PlanState
from change_verifier import VerificationResult, VerificationStatus
from style_loader import StandardMidiLoader


class VerifiedWriterError(ValueError):
    """Raised when a save gate or filesystem operation fails."""


class WriteStatus(str, Enum):
    SAVED = "SAVED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True, slots=True)
class VerifiedWriteResult:
    status: WriteStatus
    source_path: str
    output_midi_path: str
    output_report_path: str
    source_sha256: str
    output_sha256: str
    report_sha256: str
    plan_id: str
    request_id: str
    mutation_count: int
    saved_at: str
    rollback_available: bool


class AtomicVerifiedWriter:
    """Publish only verified bytes to new files; never overwrite any path."""

    def write(
        self,
        *,
        source_path: str | Path,
        output_midi_path: str | Path,
        output_report_path: str | Path,
        plan: ChangePlan,
        execution: ChangeExecutionResult,
        verification: VerificationResult,
        saved_at: str,
    ) -> VerifiedWriteResult:
        source = Path(source_path)
        output = Path(output_midi_path)
        report = Path(output_report_path)
        _validate_timestamp(saved_at)
        self._validate_paths(source, output, report)
        self._validate_chain(plan, execution, verification)
        assert verification.verified_bytes is not None
        verified_bytes = verification.verified_bytes
        verified_hash = hashlib.sha256(verified_bytes).hexdigest()
        if verified_hash != verification.output_sha256:
            raise VerifiedWriterError("verified bytes SHA-256 mismatch")
        # Reparse immediately before any filesystem publication.
        StandardMidiLoader().load_bytes(verified_bytes, source_name="<verified-writer>")

        source_before = _sha256_file(source)
        if source_before != verification.source_sha256:
            raise VerifiedWriterError("source file SHA-256 changed before save")
        if source.read_bytes() != execution.original_bytes:
            raise VerifiedWriterError("source file bytes differ from Change Engine original")

        report_data = self._report_data(
            source=source,
            output=output,
            report=report,
            plan=plan,
            execution=execution,
            verification=verification,
            saved_at=saved_at,
        )
        report_bytes = (
            json.dumps(report_data, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        report_hash = hashlib.sha256(report_bytes).hexdigest()

        temp_midi: Path | None = None
        temp_report: Path | None = None
        midi_published = False
        report_published = False
        try:
            temp_midi = _write_temp(output.parent, output.name, verified_bytes)
            temp_report = _write_temp(report.parent, report.name, report_bytes)
            # os.link is an atomic create-if-absent operation on supported local
            # filesystems. It cannot overwrite an existing destination.
            os.link(temp_midi, output)
            midi_published = True
            os.link(temp_report, report)
            report_published = True
            temp_midi.unlink()
            temp_midi = None
            temp_report.unlink()
            temp_report = None
            _fsync_directory(output.parent)

            if _sha256_file(output) != verified_hash:
                raise VerifiedWriterError("published MIDI SHA-256 mismatch")
            if _sha256_file(report) != report_hash:
                raise VerifiedWriterError("published report SHA-256 mismatch")
            source_after = _sha256_file(source)
            if source_after != source_before:
                raise VerifiedWriterError("source file changed during save")
        except Exception as exc:
            if report_published:
                _safe_unlink_if_hash(report, report_hash)
            if midi_published:
                _safe_unlink_if_hash(output, verified_hash)
            if temp_report is not None:
                _safe_unlink(temp_report)
            if temp_midi is not None:
                _safe_unlink(temp_midi)
            if isinstance(exc, VerifiedWriterError):
                raise
            raise VerifiedWriterError(f"atomic save failed: {type(exc).__name__}: {exc}") from exc

        return VerifiedWriteResult(
            status=WriteStatus.SAVED,
            source_path=str(source.resolve()),
            output_midi_path=str(output.resolve()),
            output_report_path=str(report.resolve()),
            source_sha256=source_before,
            output_sha256=verified_hash,
            report_sha256=report_hash,
            plan_id=plan.plan_id,
            request_id=execution.request.request_id,
            mutation_count=verification.expected_mutation_count,
            saved_at=saved_at,
            rollback_available=True,
        )

    def rollback(self, result: VerifiedWriteResult) -> VerifiedWriteResult:
        if result.status is not WriteStatus.SAVED or not result.rollback_available:
            raise VerifiedWriterError("write result is not eligible for rollback")
        output = Path(result.output_midi_path)
        report = Path(result.output_report_path)
        if not output.is_file() or not report.is_file():
            raise VerifiedWriterError("rollback output/report file is missing")
        if _sha256_file(output) != result.output_sha256:
            raise VerifiedWriterError("rollback refused: output MIDI was modified")
        if _sha256_file(report) != result.report_sha256:
            raise VerifiedWriterError("rollback refused: output report was modified")
        # Delete report first; if MIDI deletion then fails, the MIDI remains as a
        # complete verified artifact rather than an orphaned report claim.
        report.unlink()
        try:
            output.unlink()
        except Exception as exc:
            raise VerifiedWriterError(
                f"rollback partially failed; verified MIDI remains: {type(exc).__name__}: {exc}"
            ) from exc
        _fsync_directory(output.parent)
        return replace(result, status=WriteStatus.ROLLED_BACK, rollback_available=False)

    @staticmethod
    def _validate_paths(source: Path, output: Path, report: Path) -> None:
        if not source.is_file():
            raise VerifiedWriterError(f"source file does not exist: {source}")
        if source.suffix.lower() not in {".mid", ".midi"}:
            raise VerifiedWriterError("source file must use .mid or .midi")
        if output.suffix.lower() not in {".mid", ".midi"}:
            raise VerifiedWriterError("output MIDI must use .mid or .midi")
        if not output.stem.lower().endswith("_enhanced"):
            raise VerifiedWriterError("output MIDI name must end with _enhanced")
        if report.suffix.lower() != ".json":
            raise VerifiedWriterError("output report must use .json")
        if source.resolve() in {output.resolve(), report.resolve()}:
            raise VerifiedWriterError("output/report path must differ from source")
        if output.resolve() == report.resolve():
            raise VerifiedWriterError("MIDI and report paths must differ")
        if output.parent.resolve() != report.parent.resolve():
            raise VerifiedWriterError("MIDI and report must use the same output directory")
        if not output.parent.is_dir():
            raise VerifiedWriterError("output directory does not exist")
        if output.exists() or report.exists():
            raise VerifiedWriterError("output MIDI or report already exists; overwrite is forbidden")

    @staticmethod
    def _validate_chain(
        plan: ChangePlan,
        execution: ChangeExecutionResult,
        verification: VerificationResult,
    ) -> None:
        if plan.state is not PlanState.APPROVED:
            raise VerifiedWriterError("writer requires fully approved Change Plan")
        if execution.status is not ChangeExecutionStatus.PENDING_VERIFICATION:
            raise VerifiedWriterError("writer requires pending Change Engine result")
        if execution.verified or execution.save_authorized:
            raise VerifiedWriterError("Change Engine must not self-authorize save")
        if verification.status is not VerificationStatus.PASS:
            raise VerifiedWriterError("writer requires Verifier PASS")
        if not verification.save_authorized or verification.verified_bytes is None:
            raise VerifiedWriterError("Verifier did not authorize verified bytes")
        if not (
            plan.plan_id == execution.plan_id == verification.plan_id
            and plan.source_sha256 == execution.source_sha256 == verification.source_sha256
        ):
            raise VerifiedWriterError("plan/execution/verification identity mismatch")
        if execution.output_sha256 != verification.output_sha256:
            raise VerifiedWriterError("execution/verification output hash mismatch")
        if len(execution.applied_mutations) != verification.expected_mutation_count:
            raise VerifiedWriterError("verified mutation count mismatch")

    @staticmethod
    def _report_data(
        *,
        source: Path,
        output: Path,
        report: Path,
        plan: ChangePlan,
        execution: ChangeExecutionResult,
        verification: VerificationResult,
        saved_at: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "status": "PASS",
            "saved_at": saved_at,
            "writer": "W01_ATOMIC_VERIFIED_WRITER",
            "source": {
                "path": str(source.resolve()),
                "sha256": verification.source_sha256,
                "preserved": True,
            },
            "output": {
                "midi_path": str(output.resolve()),
                "report_path": str(report.resolve()),
                "sha256": verification.output_sha256,
                "new_file_only": True,
            },
            "plan": {
                "plan_id": plan.plan_id,
                "state": plan.state.value,
                "proposal_ids": [item.proposal_id for item in plan.proposals],
                "apply_authorized_field": plan.apply_authorized,
            },
            "execution": {
                "request_id": execution.request.request_id,
                "actor": execution.request.actor,
                "requested_at": execution.request.requested_at,
                "authorized_rule_ids": list(execution.request.authorized_rule_ids),
                "risk_acknowledgements": list(execution.request.risk_acknowledgements),
                "status": execution.status.value,
            },
            "verification": {
                "status": verification.status.value,
                "save_authorized": verification.save_authorized,
                "mutation_count": verification.expected_mutation_count,
                "changed_byte_count": verification.actual_changed_byte_count,
                "changed_byte_offsets": list(verification.changed_byte_offsets),
                "verified_mutation_ids": list(verification.verified_mutation_ids),
            },
            "changes": [
                {
                    "mutation_id": item.mutation_id,
                    "proposal_id": item.proposal_id,
                    "event_ref": list(item.event_ref),
                    "field": item.field.value,
                    "absolute_byte_offset": item.absolute_byte_offset,
                    "old_value": item.old_value,
                    "new_value": item.new_value,
                }
                for item in execution.applied_mutations
            ],
            "safety": {
                "source_overwritten": False,
                "output_preexisted": False,
                "atomic_create_if_absent": True,
                "automatic_enhance": False,
            },
        }


def _write_temp(directory: Path, final_name: str, data: bytes) -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{final_name}.", suffix=".tmp", dir=directory
    )
    path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        _safe_unlink(path)
        raise
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65_536), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _safe_unlink_if_hash(path: Path, expected_hash: str) -> None:
    try:
        if path.is_file() and _sha256_file(path) == expected_hash:
            path.unlink()
    except OSError:
        pass


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerifiedWriterError("invalid writer timestamp") from exc
    if parsed.tzinfo is None:
        raise VerifiedWriterError("writer timestamp requires timezone")
