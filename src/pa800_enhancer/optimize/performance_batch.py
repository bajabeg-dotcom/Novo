from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ..app import EnhancerApplication


BATCH_REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    source: str
    output: str
    status: str
    source_sha256: str | None
    output_sha256: str | None
    repair_changes: int
    velocity_changes: int
    articulation_changes: int
    unmatched_addresses: tuple[str, ...]
    blockers: tuple[str, ...]
    elapsed_ms: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PerformanceBatchReport:
    schema_version: int
    input_directory: str
    output_directory: str
    apply: bool
    total: int
    ready: int
    exported: int
    blocked: int
    failed: int
    skipped: int
    elapsed_ms: float
    items: tuple[BatchItemResult, ...]

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


class PerformanceBatchRunner:
    def __init__(self, app: EnhancerApplication | None = None) -> None:
        self.app = app or EnhancerApplication()

    def run(
        self,
        input_directory: Path,
        output_directory: Path,
        catalog,
        *,
        apply: bool = False,
        overwrite: bool = False,
        seed: int = 0,
    ) -> PerformanceBatchReport:
        source_root = input_directory.resolve()
        output_root = output_directory.resolve()
        if not source_root.is_dir():
            raise ValueError(f"batch input is not a directory: {input_directory}")
        if source_root == output_root or _is_relative_to(output_root, source_root):
            raise ValueError("batch output must be outside the input directory")
        midi_files = sorted(
            path for path in source_root.rglob("*")
            if path.is_file() and path.suffix.lower() in (".mid", ".midi")
        )
        started = time.perf_counter()
        items: list[BatchItemResult] = []
        for index, source in enumerate(midi_files):
            relative = source.relative_to(source_root)
            output = output_root / relative.parent / f"{source.stem}.performance.mid"
            item_started = time.perf_counter()
            try:
                if apply and output.exists() and not overwrite:
                    items.append(BatchItemResult(
                        str(source), str(output), "skipped", None, None, 0, 0, 0, (), (),
                        round((time.perf_counter() - item_started) * 1000, 3), "output already exists",
                    ))
                    continue
                song = self.app.import_midi(source)
                result = self.app.run_performance_pipeline(song, catalog, seed=seed + index)
                unmatched = tuple(sorted(set(result.velocity.unmatched_addresses) | set(result.articulation.unmatched_addresses)))
                if result.blockers:
                    status = "blocked"
                    output_hash = None
                elif apply:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    self.app.export_midi(result.projected_song, output)
                    status = "exported"
                    output_hash = hashlib.sha256(output.read_bytes()).hexdigest()
                else:
                    status = "ready"
                    output_hash = None
                items.append(BatchItemResult(
                    str(source), str(output), status, song.source_sha256, output_hash,
                    len(result.repairs.changes), len(result.velocity.changes.changes),
                    len(result.articulation.changes.changes), unmatched, result.blockers,
                    round((time.perf_counter() - item_started) * 1000, 3),
                ))
            except Exception as error:
                items.append(BatchItemResult(
                    str(source), str(output), "failed", None, None, 0, 0, 0, (), (),
                    round((time.perf_counter() - item_started) * 1000, 3),
                    f"{type(error).__name__}: {error}",
                ))
        return PerformanceBatchReport(
            BATCH_REPORT_SCHEMA_VERSION, str(source_root), str(output_root), apply,
            len(items), sum(item.status == "ready" for item in items),
            sum(item.status == "exported" for item in items),
            sum(item.status == "blocked" for item in items),
            sum(item.status == "failed" for item in items),
            sum(item.status == "skipped" for item in items),
            round((time.perf_counter() - started) * 1000, 3), tuple(items),
        )


def write_batch_report(report: PerformanceBatchReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        temporary.write_text(report.dumps(), encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
