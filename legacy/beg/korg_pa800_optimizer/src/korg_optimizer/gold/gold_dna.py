"""GoldDNARule definitions and knowledge.db storage/lookup.

Field-level schema in docs/GOLD_DNA_MODEL.md. Every rule row (promoted
or blocked) is written by gold/promotion.py -- see
docs/GOLD_DNA_SPECIFICATION.md "row-per-attempt semantics" for why a
blocked candidate still gets a row here (full auditability of every
promotion attempt), rather than only successful promotions.

Owning vertical: B.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

EVIDENCE_LEVELS = ("CONFIRMED", "INFERRED", "UNKNOWN")


@dataclass(frozen=True)
class GoldDNARule:
    rule_id: str
    category: str
    source_count: int
    occurrence_count: int
    confidence: float
    evidence_level: str  # INFERRED if promoted, UNKNOWN if blocked -- never CONFIRMED (see docs/GOLD_DNA_MODEL.md)
    supporting_examples: list[dict[str, Any]]
    contradicting_examples: list[dict[str, Any]]
    promoted_from_factory_dna_id: int | None
    promoted_at: str | None
    promotion_blocked_reason: str | None

    @property
    def supporting_examples_json(self) -> str:
        return json.dumps(self.supporting_examples, sort_keys=True)

    @property
    def contradicting_examples_json(self) -> str:
        return json.dumps(self.contradicting_examples, sort_keys=True)

    @property
    def is_promoted(self) -> bool:
        return self.promoted_at is not None


def _row_to_rule(row: sqlite3.Row) -> GoldDNARule:
    return GoldDNARule(
        rule_id=row["rule_id"],
        category=row["category"],
        source_count=row["source_count"],
        occurrence_count=row["occurrence_count"],
        confidence=row["confidence"],
        evidence_level=row["evidence_level"],
        supporting_examples=json.loads(row["supporting_examples"]),
        contradicting_examples=json.loads(row["contradicting_examples"]),
        promoted_from_factory_dna_id=row["promoted_from_factory_dna_id"],
        promoted_at=row["promoted_at"],
        promotion_blocked_reason=row["promotion_blocked_reason"],
    )


def save_gold_dna(conn: sqlite3.Connection, rules: list[GoldDNARule]) -> None:
    """Replace the entire gold_dna table with ``rules`` (full rebuild,
    same semantics as dna.factory_dna.save_factory_dna).
    """
    with conn:
        conn.execute("DELETE FROM gold_dna")
        conn.executemany(
            """
            INSERT INTO gold_dna
                (rule_id, category, source_count, occurrence_count, confidence, evidence_level,
                 supporting_examples, contradicting_examples, promoted_from_factory_dna_id,
                 promoted_at, promotion_blocked_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.rule_id,
                    r.category,
                    r.source_count,
                    r.occurrence_count,
                    r.confidence,
                    r.evidence_level,
                    r.supporting_examples_json,
                    r.contradicting_examples_json,
                    r.promoted_from_factory_dna_id,
                    r.promoted_at,
                    r.promotion_blocked_reason,
                )
                for r in rules
            ],
        )


def load_gold_dna(
    conn: sqlite3.Connection, *, category: str | None = None, promoted_only: bool = False
) -> list[GoldDNARule]:
    query = "SELECT * FROM gold_dna WHERE 1=1"
    params: list[Any] = []
    if category is not None:
        query += " AND category = ?"
        params.append(category)
    if promoted_only:
        query += " AND promoted_at IS NOT NULL"
    query += " ORDER BY rule_id"
    return [_row_to_rule(row) for row in conn.execute(query, params).fetchall()]


def get_by_rule_id(conn: sqlite3.Connection, rule_id: str) -> GoldDNARule | None:
    row = conn.execute("SELECT * FROM gold_dna WHERE rule_id = ?", (rule_id,)).fetchone()
    return _row_to_rule(row) if row is not None else None
