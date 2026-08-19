"""Hashes and catalogs Golden Dataset material (data/golden/songs/)
into the golden_files table plus a regenerated MANIFEST.json.

This is a manifest/catalog only -- no MIDI parsing, no musical
analysis, no evidence_level claim. Deliberately kept structurally
separate from factory/ (the Factory Evidence pipeline -- Golden
material is not Factory Style evidence) and from gold/ (Vertical B's
validated-rule promotion pipeline -- entirely out of scope here). See
docs/DATABASE_ARCHITECTURE.md and docs/VERTICAL_DECOMPOSITION.md.

Note: this module intentionally does its own tiny directory walk
rather than importing factory/discovery.py, since infrastructure/ must
not depend on factory/ per docs/ARCHITECTURE.md's allowed-dependency
direction rules (infrastructure is foundational to factory, not the
other way around).

Owning vertical: A (cataloging only; gold/** promotion-pipeline
ownership by Vertical B is unaffected).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config, hashing
from .database import connection as db_connection


def _discover_mid_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() == ".mid":
            yield path


@dataclass
class GoldenImportSummary:
    imported: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)


def catalog_golden_dataset(
    root: str | Path = config.GOLDEN_SONGS_ROOT,
    conn: sqlite3.Connection | None = None,
    *,
    manifest_path: str | Path | None = None,
) -> GoldenImportSummary:
    """Hash + catalog every .mid file under ``root`` into
    ``golden_files``, then regenerate a human-readable MANIFEST.json
    alongside it. One bad file does not abort the batch.
    """
    root = Path(root)
    owns_conn = conn is None
    if owns_conn:
        conn = db_connection.get_connection(config.EVIDENCE_DB_PATH)
        db_connection.ensure_schema(conn)

    summary = GoldenImportSummary()
    manifest_entries: list[dict] = []

    try:
        for path in _discover_mid_files(root):
            try:
                sha256_hash = hashing.sha256_file(path)
                byte_size = path.stat().st_size
                try:
                    rel_path = str(path.relative_to(config.PACKAGE_ROOT))
                except ValueError:
                    rel_path = str(path)

                existing = conn.execute(
                    "SELECT sha256_hash FROM golden_files WHERE file_path = ?",
                    (rel_path,),
                ).fetchone()

                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO golden_files (file_path, sha256_hash, byte_size, imported_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (rel_path, sha256_hash, byte_size, datetime.now(timezone.utc).isoformat()),
                    )
                    summary.imported += 1
                elif existing["sha256_hash"] == sha256_hash:
                    summary.unchanged += 1
                else:
                    raise ValueError(f"{rel_path}: hash changed since cataloging")

                manifest_entries.append(
                    {"filename": path.name, "sha256": sha256_hash, "byte_size": byte_size}
                )
            except Exception as exc:
                summary.errors.append(f"{path}: {exc}")
        conn.commit()
    finally:
        if owns_conn:
            conn.close()

    dest_manifest = Path(manifest_path) if manifest_path is not None else root / "MANIFEST.json"
    manifest_entries.sort(key=lambda e: e["filename"])
    dest_manifest.write_text(json.dumps(manifest_entries, indent=2) + "\n", encoding="utf-8")

    return summary


if __name__ == "__main__":
    result = catalog_golden_dataset()
    print(f"imported={result.imported} unchanged={result.unchanged} errors={len(result.errors)}")
    for err in result.errors:
        print(f"  ERROR: {err}")
