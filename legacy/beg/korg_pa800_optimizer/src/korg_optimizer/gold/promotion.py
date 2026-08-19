"""Promotes FactoryDNA to GoldDNA, enforcing the synthetic-exclusion
gate: rejects promotion when any contributing source is
source_kind=SYNTHETIC. See docs/GOLD_DNA_SPECIFICATION.md.

Row-per-attempt semantics: every evaluated factory_dna row gets
exactly one gold_dna row, whether promoted or blocked (see
docs/GOLD_DNA_SPECIFICATION.md "row-per-attempt semantics" for why --
this resolves an ambiguity in the original doc wording and gives full
auditability of every promotion attempt).

Owning vertical: B.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .gold_dna import GoldDNARule, save_gold_dna
from ..dna.factory_dna import FactoryDNARecord, load_factory_dna_with_ids

MAX_SUPPORTING_EXAMPLES = 10

# Beyond the mandatory synthetic-exclusion gate, a factory_dna row must
# also clear these size/consistency thresholds to be promoted. Tiered
# by the granularity of what occurrence_count actually counts for that
# category (see docs/GOLD_DNA_MODEL.md "confidence formula" for the
# matching SATURATION_N tiers used when the row's confidence was
# originally computed).
PROMOTION_THRESHOLDS: dict[str, dict[str, float]] = {
    "note_level": {"min_occurrence_count": 30, "min_source_count": 10, "min_confidence": 0.6},
    "track_level": {"min_occurrence_count": 10, "min_source_count": 10, "min_confidence": 0.6},
    "pair_level": {"min_occurrence_count": 5, "min_source_count": 5, "min_confidence": 0.6},
}

_NOTE_LEVEL_CATEGORIES = {"rhythm", "velocity", "timing"}


def _tier_for(record: FactoryDNARecord) -> str:
    if record.category in _NOTE_LEVEL_CATEGORIES:
        return "note_level"
    if record.metrics.get("sub_category") == "layer_interaction":
        return "pair_level"
    return "track_level"  # arrangement.channel_profile / section_behavior


@dataclass
class PromotionSummary:
    evaluated: int = 0
    promoted: int = 0
    blocked_synthetic: int = 0
    blocked_threshold: int = 0


def check_synthetic_exclusion(record: FactoryDNARecord) -> str | None:
    """Return a blocking reason if any contributing source is
    SYNTHETIC, else None. Unconditional -- no threshold can override
    this gate.
    """
    synthetic_count = record.source_kind_composition.get("SYNTHETIC", 0)
    if synthetic_count > 0:
        total = sum(record.source_kind_composition.values())
        return f"{synthetic_count} of {total} contributing sources are SYNTHETIC"
    return None


def check_thresholds(record: FactoryDNARecord) -> str | None:
    """Return a blocking reason if the row is below its tier's
    minimum occurrence_count/source_count/confidence, else None.
    """
    tier = _tier_for(record)
    thresholds = PROMOTION_THRESHOLDS[tier]
    source_count = len(record.derived_from_evidence_ids)

    reasons = []
    if record.occurrence_count < thresholds["min_occurrence_count"]:
        reasons.append(
            f"occurrence_count {record.occurrence_count} < {thresholds['min_occurrence_count']} ({tier})"
        )
    if source_count < thresholds["min_source_count"]:
        reasons.append(f"source_count {source_count} < {thresholds['min_source_count']} ({tier})")
    if record.confidence < thresholds["min_confidence"]:
        reasons.append(f"confidence {record.confidence} < {thresholds['min_confidence']} ({tier})")
    return "; ".join(reasons) if reasons else None


def _build_supporting_examples(
    evidence_conn: sqlite3.Connection, evidence_ids: list[int], limit: int = MAX_SUPPORTING_EXAMPLES
) -> list[dict]:
    """Up to ``limit`` real, traceable {source_file_id, file_path,
    style_name} examples from the rule's contributing evidence.

    Simplification, documented in docs/GOLD_DNA_SPECIFICATION.md: these
    are the lowest-id contributing files (deterministic, reproducible),
    not literally "closest to the group mean" -- computing that would
    require retaining per-instance raw values through promotion, which
    factory_dna's aggregate-only metrics_json does not do this session.
    ``contradicting_examples`` is correspondingly always empty this
    session (not a claim that no contradictions exist -- a documented
    scope limit, not a fabricated "none found" result).
    """
    if not evidence_ids:
        return []
    chosen = sorted(evidence_ids)[:limit]
    placeholders = ",".join("?" * len(chosen))
    rows = evidence_conn.execute(
        f"""
        SELECT fe.id AS evidence_id, fe.style_name AS style_name,
               sf.id AS source_file_id, sf.file_path AS file_path
        FROM factory_evidence fe
        JOIN source_files sf ON sf.id = fe.source_file_id
        WHERE fe.id IN ({placeholders})
        ORDER BY fe.id
        """,
        chosen,
    ).fetchall()
    return [
        {
            "source_file_id": row["source_file_id"],
            "file_path": row["file_path"],
            "style_name": row["style_name"],
        }
        for row in rows
    ]


def evaluate_promotion(
    record: FactoryDNARecord, factory_dna_id: int, evidence_conn: sqlite3.Connection
) -> GoldDNARule:
    """Evaluate one factory_dna row for promotion. Always returns a
    GoldDNARule -- promoted (evidence_level=INFERRED, promoted_at set)
    or blocked (evidence_level=UNKNOWN, promotion_blocked_reason set).
    """
    now = datetime.now(timezone.utc).isoformat()
    source_count = len(record.derived_from_evidence_ids)

    blocked_reason = check_synthetic_exclusion(record) or check_thresholds(record)

    if blocked_reason is None:
        supporting = _build_supporting_examples(evidence_conn, record.derived_from_evidence_ids)
        return GoldDNARule(
            rule_id=record.rule_id,
            category=record.category,
            source_count=source_count,
            occurrence_count=record.occurrence_count,
            confidence=record.confidence,
            evidence_level="INFERRED",
            supporting_examples=supporting,
            contradicting_examples=[],
            promoted_from_factory_dna_id=factory_dna_id,
            promoted_at=now,
            promotion_blocked_reason=None,
        )

    return GoldDNARule(
        rule_id=record.rule_id,
        category=record.category,
        source_count=source_count,
        occurrence_count=record.occurrence_count,
        confidence=record.confidence,
        evidence_level="UNKNOWN",
        supporting_examples=[],
        contradicting_examples=[],
        promoted_from_factory_dna_id=factory_dna_id,
        promoted_at=None,
        promotion_blocked_reason=blocked_reason,
    )


def promote_all(knowledge_conn: sqlite3.Connection, evidence_conn: sqlite3.Connection) -> PromotionSummary:
    """Evaluate every factory_dna row and rewrite gold_dna (full
    rebuild) with exactly one row per evaluated factory_dna row.
    """
    summary = PromotionSummary()
    rules: list[GoldDNARule] = []

    for factory_dna_id, record in load_factory_dna_with_ids(knowledge_conn):
        summary.evaluated += 1
        rule = evaluate_promotion(record, factory_dna_id, evidence_conn)
        rules.append(rule)
        if rule.is_promoted:
            summary.promoted += 1
        elif rule.promotion_blocked_reason and "SYNTHETIC" in rule.promotion_blocked_reason:
            summary.blocked_synthetic += 1
        else:
            summary.blocked_threshold += 1

    save_gold_dna(knowledge_conn, rules)
    return summary


if __name__ == "__main__":
    from ..infrastructure import config
    from ..infrastructure.database import connection as db_connection

    evidence_connection = db_connection.get_connection(config.EVIDENCE_DB_PATH)
    knowledge_connection = db_connection.get_connection(config.KNOWLEDGE_DB_PATH)

    result = promote_all(knowledge_connection, evidence_connection)
    print(
        f"evaluated={result.evaluated} promoted={result.promoted} "
        f"blocked_synthetic={result.blocked_synthetic} blocked_threshold={result.blocked_threshold}"
    )

    evidence_connection.close()
    knowledge_connection.close()
