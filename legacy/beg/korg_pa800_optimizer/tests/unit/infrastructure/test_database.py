from __future__ import annotations

import sqlite3

import pytest

from korg_optimizer.infrastructure.database import connection as db


@pytest.fixture()
def conn(tmp_path):
    c = db.get_connection(tmp_path / "evidence.db")
    db.ensure_schema(c)
    yield c
    c.close()


def test_ensure_schema_creates_expected_tables(conn):
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"source_files", "factory_evidence", "golden_files", "schema_version"} <= tables


def test_ensure_schema_is_idempotent(conn):
    db.ensure_schema(conn)  # second call must not raise or duplicate rows
    count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert count == 1


def test_foreign_key_violation_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO factory_evidence
                (source_file_id, event_summary_json, extracted_at, extractor_version)
            VALUES (999, '{}', 'x', 'x')
            """
        )
        conn.commit()


def test_source_files_path_is_unique(conn):
    conn.execute(
        """
        INSERT INTO source_files
            (file_path, sha256_hash, source_kind, imported_at, parser_version, byte_size)
        VALUES ('a.mid', 'hash1', 'REAL', 'x', 'x', 10)
        """
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO source_files
                (file_path, sha256_hash, source_kind, imported_at, parser_version, byte_size)
            VALUES ('a.mid', 'hash2', 'REAL', 'x', 'x', 20)
            """
        )
        conn.commit()


def test_source_kind_must_be_synthetic_or_real(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO source_files
                (file_path, sha256_hash, source_kind, imported_at, parser_version, byte_size)
            VALUES ('b.mid', 'hash', 'BOGUS', 'x', 'x', 10)
            """
        )
        conn.commit()


def test_golden_files_path_is_unique(conn):
    conn.execute(
        "INSERT INTO golden_files (file_path, sha256_hash, byte_size, imported_at) "
        "VALUES ('song.mid', 'hash1', 10, 'x')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO golden_files (file_path, sha256_hash, byte_size, imported_at) "
            "VALUES ('song.mid', 'hash2', 20, 'x')"
        )
        conn.commit()
