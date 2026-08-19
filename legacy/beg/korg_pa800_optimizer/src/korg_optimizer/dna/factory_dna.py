"""FactoryDNARecord definitions and knowledge.db storage/lookup.

Records which SourceFiles (and their source_kind) contributed to each
pattern -- see docs/DATABASE_ARCHITECTURE.md factory_dna table and
docs/GOLD_DNA_SPECIFICATION.md "synthetic-exclusion gate".

Owning vertical: B.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

EXTRACTOR_VERSION = "0.1.0"


@dataclass(frozen=True)
class FactoryDNARecord:
    rule_id: str
    category: str  # rhythm | velocity | timing | arrangement
    style_section: str | None
    channel: int | None
    channel_b: int | None
    metrics: dict[str, Any]
    derived_from_evidence_ids: list[int]
    source_kind_composition: dict[str, int]
    occurrence_count: int
    confidence: float
    computed_at: str
    extractor_version: str = EXTRACTOR_VERSION

    @property
    def metrics_json(self) -> str:
        return json.dumps(self.metrics, sort_keys=True)

    @property
    def derived_from_evidence_ids_json(self) -> str:
        return json.dumps(sorted(set(self.derived_from_evidence_ids)))

    @property
    def source_kind_composition_json(self) -> str:
        return json.dumps(self.source_kind_composition, sort_keys=True)


def _row_to_record(row: sqlite3.Row) -> FactoryDNARecord:
    return FactoryDNARecord(
        rule_id=row["rule_id"],
        category=row["category"],
        style_section=row["style_section"],
        channel=row["channel"],
        channel_b=row["channel_b"],
        metrics=json.loads(row["metrics_json"]),
        derived_from_evidence_ids=json.loads(row["derived_from_evidence_ids"]),
        source_kind_composition=json.loads(row["source_kind_composition"]),
        occurrence_count=row["occurrence_count"],
        confidence=row["confidence"],
        computed_at=row["computed_at"],
        extractor_version=row["extractor_version"],
    )


def save_factory_dna(conn: sqlite3.Connection, records: list[FactoryDNARecord]) -> None:
    """Replace the entire factory_dna table with ``records``.

    knowledge.db is derived/rebuildable (docs/DATABASE_ARCHITECTURE.md
    "full-rebuild semantics") -- this is a full rebuild, not an upsert.
    A UNIQUE(rule_id) violation indicates a bug (duplicate group key),
    not a legitimate update path.
    """
    with conn:
        conn.execute("DELETE FROM factory_dna")
        conn.executemany(
            """
            INSERT INTO factory_dna
                (rule_id, category, style_section, channel, channel_b, metrics_json,
                 derived_from_evidence_ids, source_kind_composition, occurrence_count,
                 confidence, computed_at, extractor_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.rule_id,
                    r.category,
                    r.style_section,
                    r.channel,
                    r.channel_b,
                    r.metrics_json,
                    r.derived_from_evidence_ids_json,
                    r.source_kind_composition_json,
                    r.occurrence_count,
                    r.confidence,
                    r.computed_at,
                    r.extractor_version,
                )
                for r in records
            ],
        )


def load_factory_dna(
    conn: sqlite3.Connection,
    *,
    category: str | None = None,
    style_section: str | None = None,
    channel: int | None = None,
) -> list[FactoryDNARecord]:
    query = "SELECT * FROM factory_dna WHERE 1=1"
    params: list[Any] = []
    if category is not None:
        query += " AND category = ?"
        params.append(category)
    if style_section is not None:
        query += " AND style_section = ?"
        params.append(style_section)
    if channel is not None:
        query += " AND channel = ?"
        params.append(channel)
    query += " ORDER BY rule_id"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_record(row) for row in rows]


def get_by_rule_id(conn: sqlite3.Connection, rule_id: str) -> FactoryDNARecord | None:
    row = conn.execute("SELECT * FROM factory_dna WHERE rule_id = ?", (rule_id,)).fetchone()
    return _row_to_record(row) if row is not None else None


def load_factory_dna_with_ids(conn: sqlite3.Connection) -> list[tuple[int, FactoryDNARecord]]:
    """Like ``load_factory_dna`` but also returns each row's primary
    key -- needed by gold/promotion.py for ``promoted_from_factory_dna_id``.
    """
    rows = conn.execute("SELECT * FROM factory_dna ORDER BY id").fetchall()
    return [(row["id"], _row_to_record(row)) for row in rows]
