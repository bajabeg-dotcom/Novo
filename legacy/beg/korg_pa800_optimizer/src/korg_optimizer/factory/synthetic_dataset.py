"""Loader for SYNTHETIC test MIDI under data/factory/synthetic/.

Hardcodes source_kind=SYNTHETIC at the call site -- never accepts
source_kind as a caller-supplied parameter, so pipeline/unit-test data
can never be mistaken for Factory Evidence. See
docs/GOLD_DNA_SPECIFICATION.md "synthetic-exclusion gate".

Owning vertical: A.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import _ingest_common
from ..infrastructure import config
from ..infrastructure.database import connection as db_connection

ImportSummary = _ingest_common.ImportSummary
EvidenceIntegrityError = _ingest_common.EvidenceIntegrityError


def import_synthetic_dataset(
    root: str | Path = config.FACTORY_SYNTHETIC_ROOT,
    conn: sqlite3.Connection | None = None,
) -> ImportSummary:
    """Ingest synthetic .mid fixtures under ``root`` into evidence.db,
    hardcoding source_kind='SYNTHETIC'.
    """
    owns_conn = conn is None
    if owns_conn:
        conn = db_connection.get_connection(config.EVIDENCE_DB_PATH)
        db_connection.ensure_schema(conn)
    try:
        return _ingest_common.ingest(root, conn, source_kind="SYNTHETIC")
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    result = import_synthetic_dataset()
    print(f"imported={result.imported} unchanged={result.unchanged} errors={len(result.errors)}")
    for err in result.errors:
        print(f"  ERROR: {err}")
