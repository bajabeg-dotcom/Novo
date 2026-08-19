"""SQLite connection management, generic across evidence.db and
knowledge.db (runtime.db connection helpers will be added by Vertical
C when its schema exists, Phase 15+) -- ``ensure_schema`` accepts
whichever DDL list and schema version are asked for.

Owning vertical: A.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .schema import EVIDENCE_DB_DDL, EVIDENCE_DB_SCHEMA_VERSION


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enforced and
    dict-like row access. Creates parent directories if needed.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(
    conn: sqlite3.Connection,
    ddl_statements: list[str] = EVIDENCE_DB_DDL,
    *,
    schema_version: int = EVIDENCE_DB_SCHEMA_VERSION,
) -> None:
    """Idempotently create tables/indexes. Safe to call on every
    startup -- uses ``CREATE ... IF NOT EXISTS`` throughout. Records
    the initial schema version once, on first creation. Pass
    ``ddl_statements=KNOWLEDGE_DB_DDL, schema_version=KNOWLEDGE_DB_SCHEMA_VERSION``
    for knowledge.db.
    """
    with conn:
        for statement in ddl_statements:
            conn.execute(statement)
        row = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()
        if row[0] == 0:
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (schema_version, datetime.now(timezone.utc).isoformat()),
            )


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on exception."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
