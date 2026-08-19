from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .smf.reader import SmfReader
from .validation.validator import SongValidator


@dataclass(frozen=True, slots=True)
class CorpusEntry:
    locator: str
    sha256: str
    size: int
    status: str
    elapsed_ms: float
    format_type: int | None = None
    tracks: int | None = None
    division: int | None = None
    issue_counts: dict[str, int] | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CorpusReport:
    schema_version: int
    sources: tuple[str, ...]
    total_midi: int
    parsed: int
    failed: int
    blocked: int
    with_issues: int
    elapsed_ms: float
    issue_counts: dict[str, int]
    entries: tuple[CorpusEntry, ...]

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"


class CorpusRunner:
    def __init__(
        self,
        reader: SmfReader | None = None,
        validator: SongValidator | None = None,
        *,
        max_archive_entries: int = 10_000,
        max_nested_depth: int = 2,
        max_archive_uncompressed_size: int = 512 * 1024 * 1024,
    ) -> None:
        self.reader = reader or SmfReader()
        self.validator = validator or SongValidator()
        self.max_archive_entries = max_archive_entries
        self.max_nested_depth = max_nested_depth
        self.max_archive_uncompressed_size = max_archive_uncompressed_size

    def run(self, sources: Iterable[Path]) -> CorpusReport:
        source_paths = tuple(Path(item) for item in sources)
        started = time.perf_counter()
        entries = tuple(self._analyze(locator, data) for locator, data in self._iter_sources(source_paths))
        issue_counts: Counter[str] = Counter()
        for entry in entries:
            issue_counts.update(entry.issue_counts or {})
        return CorpusReport(
            schema_version=1,
            sources=tuple(str(path) for path in source_paths),
            total_midi=len(entries),
            parsed=sum(entry.status != "parse_failed" for entry in entries),
            failed=sum(entry.status == "parse_failed" for entry in entries),
            blocked=sum(entry.status == "blocked" for entry in entries),
            with_issues=sum(bool(entry.issue_counts) for entry in entries),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            issue_counts=dict(sorted(issue_counts.items())),
            entries=entries,
        )

    def iter_midi(self, sources: Iterable[Path]):
        """Yield stable locator/bytes pairs for bounded corpus consumers."""
        yield from self._iter_sources(tuple(Path(item) for item in sources))

    def _iter_sources(self, sources: tuple[Path, ...]):
        for source in sources:
            if source.is_dir():
                for item in sorted(source.rglob("*")):
                    if not item.is_file():
                        continue
                    if item.suffix.lower() in (".mid", ".midi"):
                        yield str(item), item.read_bytes()
                    elif zipfile.is_zipfile(item):
                        yield from self._iter_zip(item.read_bytes(), str(item), 0)
            elif zipfile.is_zipfile(source):
                yield from self._iter_zip(source.read_bytes(), str(source), 0)
            elif source.suffix.lower() in (".mid", ".midi"):
                yield str(source), source.read_bytes()
            else:
                raise ValueError(f"unsupported corpus source: {source}")

    def _iter_zip(self, data: bytes, locator: str, depth: int):
        if depth > self.max_nested_depth:
            raise ValueError(f"nested ZIP depth exceeds configured limit: {locator}")
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as error:
            raise ValueError(f"invalid ZIP archive: {locator}") from error
        with archive:
            infos = archive.infolist()
            if len(infos) > self.max_archive_entries:
                raise ValueError(f"ZIP entry count exceeds configured limit: {locator}")
            if sum(info.file_size for info in infos) > self.max_archive_uncompressed_size:
                raise ValueError(f"ZIP expanded size exceeds configured limit: {locator}")
            for info in infos:
                if info.is_dir():
                    continue
                child = f"{locator}!/{info.filename}"
                suffix = Path(info.filename).suffix.lower()
                if suffix in (".mid", ".midi"):
                    if info.file_size > self.reader.max_file_size:
                        yield child, b""
                    else:
                        yield child, archive.read(info)
                elif suffix == ".zip":
                    if info.file_size > self.max_archive_uncompressed_size:
                        raise ValueError(f"nested ZIP exceeds configured size limit: {child}")
                    yield from self._iter_zip(archive.read(info), child, depth + 1)

    def _analyze(self, locator: str, data: bytes) -> CorpusEntry:
        started = time.perf_counter()
        digest = hashlib.sha256(data).hexdigest()
        try:
            song = self.reader.parse(data)
            issues = self.validator.validate(song)
            counts = Counter(issue.code for issue in issues)
            blocked = any(issue.blocks_export for issue in issues)
            return CorpusEntry(
                locator=locator,
                sha256=digest,
                size=len(data),
                status="blocked" if blocked else "parsed",
                elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
                format_type=song.header.format_type,
                tracks=len(song.tracks),
                division=song.header.division,
                issue_counts=dict(sorted(counts.items())),
            )
        except Exception as error:
            return CorpusEntry(
                locator=locator,
                sha256=digest,
                size=len(data),
                status="parse_failed",
                elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
                error=f"{type(error).__name__}: {error}",
            )


def write_corpus_report(report: CorpusReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        temporary.write_text(report.dumps(), encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
