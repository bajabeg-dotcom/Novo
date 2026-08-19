"""Shared ingestion logic for real_dataset.py and synthetic_dataset.py.

Not part of the public factory/ API. Each dataset module hardcodes its
own ``source_kind`` at its own public call site -- this module never
accepts ``source_kind`` from an external caller, preserving the
"mislabeling requires editing the wrong file" safety property from
docs/GOLD_DNA_SPECIFICATION.md's synthetic-exclusion design.

On each newly-imported file, also extracts and stores Factory Evidence
(factory/evidence_source.py) -- Phase 3 (ingestion) and Phase 4
(evidence) are wired together here since both are Vertical A's scope
for this session.

Owning vertical: A.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from . import discovery, evidence_source
from ..infrastructure import config
from ..midi import raw_import
from ..midi.normalized_model import NormalizedMidiFile

PARSER_VERSION = "0.1.0"


class EvidenceIntegrityError(Exception):
    """Raised when a previously-imported file's content hash has
    changed. evidence.db is append-only / immutable once written (raw
    preservation guarantee) -- a changed hash at an already-imported
    path means the file was edited or replaced after import, which
    must surface loudly rather than being silently absorbed as an
    update.
    """


@dataclass
class ImportSummary:
    imported: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(config.PACKAGE_ROOT))
    except ValueError:
        return str(path)


def upsert_source_file(
    conn: sqlite3.Connection,
    rel_path: str,
    record: raw_import.SourceFileRecord,
    source_kind: str,
) -> tuple[str, int]:
    """Insert or verify a ``source_files`` row. Returns
    ``("imported" | "unchanged", source_file_id)``.

    Raises ``EvidenceIntegrityError`` if a row already exists at this
    path with a different hash.
    """
    existing = conn.execute(
        "SELECT id, sha256_hash FROM source_files WHERE file_path = ?",
        (rel_path,),
    ).fetchone()

    if existing is None:
        cursor = conn.execute(
            """
            INSERT INTO source_files
                (file_path, sha256_hash, source_kind, format, imported_at, parser_version, byte_size)
            VALUES (?, ?, ?, 'mid', ?, ?, ?)
            """,
            (
                rel_path,
                record.sha256_hash,
                source_kind,
                datetime.now(timezone.utc).isoformat(),
                PARSER_VERSION,
                record.byte_size,
            ),
        )
        return "imported", cursor.lastrowid

    if existing["sha256_hash"] == record.sha256_hash:
        return "unchanged", existing["id"]

    raise EvidenceIntegrityError(
        f"{rel_path}: hash changed since import "
        f"(was {existing['sha256_hash']}, now {record.sha256_hash})"
    )


def ingest(root: str | Path, conn: sqlite3.Connection, *, source_kind: str) -> ImportSummary:
    """Walk ``root`` for .mid files, hash + catalog each into
    ``source_files`` (hardcoding ``source_kind``), and extract Factory
    Evidence for newly-imported files. One bad file does not abort the
    batch -- its error is recorded and ingestion continues.
    """
    summary = ImportSummary()
    for path in discovery.discover_files(root):
        try:
            record = raw_import.import_file(path)
            rel_path = _relative_path(path)
            status, source_file_id = upsert_source_file(conn, rel_path, record, source_kind)
            if status == "imported":
                summary.imported += 1
                normalized = NormalizedMidiFile.from_file(path, source_file_id=source_file_id)
                records = evidence_source.extract_evidence(
                    normalized, source_file_id, file_path=path
                )
                evidence_source.save_evidence(conn, records)
            else:
                summary.unchanged += 1
        except Exception as exc:  # one bad file must not abort the batch
            summary.errors.append(f"{path}: {exc}")
    conn.commit()
    return summary
