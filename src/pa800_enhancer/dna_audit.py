from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from .database import DEFAULT_DATABASE_PATH, LocalDatabase


@dataclass(frozen=True, slots=True)
class DnaDatabaseAudit:
    schema_version: int
    source_count: int
    unique_fingerprints: int
    gold_sources: int
    factory_sources: int
    role_fingerprints: int
    total_notes: int
    role_coverage: dict[str, dict[str, int]]
    complete_role_sources: int
    missing_role_sources: dict[str, int]
    duplicate_content_groups: int
    evidence_fields: tuple[str, ...]


def audit_database(path: Path = DEFAULT_DATABASE_PATH) -> DnaDatabaseAudit:
    status = LocalDatabase().status(path)
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
        kinds = dict(connection.execute(
            "SELECT corpus_kind, COUNT(*) FROM midi_fingerprint_sources GROUP BY corpus_kind"
        ))
        source_count = connection.execute("SELECT COUNT(*) FROM midi_fingerprint_sources").fetchone()[0]
        coverage: dict[str, dict[str, int]] = {}
        for role, sources, notes in connection.execute(
            "SELECT role, COUNT(*), SUM(note_count) FROM midi_fingerprint_roles GROUP BY role"
        ):
            coverage[role] = {"sources": int(sources), "notes": int(notes or 0)}
        complete = connection.execute(
            "SELECT COUNT(*) FROM (SELECT fingerprint_id FROM midi_fingerprint_roles GROUP BY fingerprint_id HAVING COUNT(*) = 5)"
        ).fetchone()[0]
        missing = {
            role: connection.execute(
                """SELECT COUNT(*) FROM midi_fingerprints f WHERE NOT EXISTS
                   (SELECT 1 FROM midi_fingerprint_roles r WHERE r.fingerprint_id=f.fingerprint_id AND r.role=?)""",
                (role,),
            ).fetchone()[0]
            for role in ("solo", "accompaniment", "bass", "drums", "guitar")
        }
        duplicate_groups = connection.execute(
            "SELECT COUNT(*) FROM (SELECT source_sha256 FROM midi_fingerprint_sources GROUP BY source_sha256 HAVING COUNT(*) > 1)"
        ).fetchone()[0]
    return DnaDatabaseAudit(
        status.schema_version, int(source_count), status.fingerprint_count, kinds.get("gold", 0),
        kinds.get("factory", 0), status.fingerprint_role_count,
        sum(item["notes"] for item in coverage.values()), coverage, int(complete),
        missing, int(duplicate_groups),
        ("source_locator", "source_sha256", "corpus_kind", "role", "note_count",
         "feature_vector", "feature_statistics", "match_distance"),
    )
