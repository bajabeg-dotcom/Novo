from __future__ import annotations

import pytest

from korg_optimizer.dna.factory_dna import FactoryDNARecord, save_factory_dna
from korg_optimizer.gold import promotion
from korg_optimizer.gold.gold_dna import get_by_rule_id, load_gold_dna
from korg_optimizer.infrastructure.database import connection as db
from korg_optimizer.infrastructure.database.schema import (
    EVIDENCE_DB_DDL,
    EVIDENCE_DB_SCHEMA_VERSION,
    KNOWLEDGE_DB_DDL,
    KNOWLEDGE_DB_SCHEMA_VERSION,
)


@pytest.fixture()
def knowledge_conn(tmp_path):
    c = db.get_connection(tmp_path / "knowledge.db")
    db.ensure_schema(c, KNOWLEDGE_DB_DDL, schema_version=KNOWLEDGE_DB_SCHEMA_VERSION)
    yield c
    c.close()


@pytest.fixture()
def evidence_conn(tmp_path):
    c = db.get_connection(tmp_path / "evidence.db")
    db.ensure_schema(c, EVIDENCE_DB_DDL, schema_version=EVIDENCE_DB_SCHEMA_VERSION)
    yield c
    c.close()


def _note_level_record(
    rule_id: str,
    *,
    source_kind_composition: dict[str, int],
    occurrence_count: int = 1000,
    source_count: int = 20,
    confidence: float = 0.9,
) -> FactoryDNARecord:
    return FactoryDNARecord(
        rule_id=rule_id,
        category="rhythm",
        style_section="Var1",
        channel=9,
        channel_b=None,
        metrics={"density": {"mean": 2.0, "stddev": 0.1}},
        derived_from_evidence_ids=list(range(1, source_count + 1)),
        source_kind_composition=source_kind_composition,
        occurrence_count=occurrence_count,
        confidence=confidence,
        computed_at="2026-01-01T00:00:00+00:00",
    )


def test_synthetic_exclusion_gate_blocks_promotion(knowledge_conn, evidence_conn):
    record = _note_level_record("synth_tainted", source_kind_composition={"REAL": 9, "SYNTHETIC": 3})
    save_factory_dna(knowledge_conn, [record])

    summary = promotion.promote_all(knowledge_conn, evidence_conn)

    assert summary.blocked_synthetic == 1
    assert summary.promoted == 0
    rule = get_by_rule_id(knowledge_conn, "synth_tainted")
    assert rule.promoted_at is None
    assert rule.evidence_level == "UNKNOWN"
    assert "SYNTHETIC" in rule.promotion_blocked_reason


def test_real_only_record_promotes_successfully(knowledge_conn, evidence_conn):
    record = _note_level_record("real_only", source_kind_composition={"REAL": 30})
    save_factory_dna(knowledge_conn, [record])

    summary = promotion.promote_all(knowledge_conn, evidence_conn)

    assert summary.promoted == 1
    assert summary.blocked_synthetic == 0
    rule = get_by_rule_id(knowledge_conn, "real_only")
    assert rule.promoted_at is not None
    assert rule.evidence_level == "INFERRED"
    assert rule.promotion_blocked_reason is None


def test_below_threshold_all_real_is_blocked_not_synthetic(knowledge_conn, evidence_conn):
    record = _note_level_record(
        "too_small", source_kind_composition={"REAL": 3}, occurrence_count=5, source_count=3
    )
    save_factory_dna(knowledge_conn, [record])

    summary = promotion.promote_all(knowledge_conn, evidence_conn)

    assert summary.blocked_threshold == 1
    assert summary.blocked_synthetic == 0
    rule = get_by_rule_id(knowledge_conn, "too_small")
    assert rule.promoted_at is None
    assert rule.evidence_level == "UNKNOWN"
    assert "occurrence_count" in rule.promotion_blocked_reason or "source_count" in rule.promotion_blocked_reason


def test_arrangement_layer_interaction_uses_pair_level_tier(knowledge_conn, evidence_conn):
    record = FactoryDNARecord(
        rule_id="pair_rule",
        category="arrangement",
        style_section="Var1",
        channel=9,
        channel_b=11,
        metrics={"sub_category": "layer_interaction", "co_activity": {"mean": 0.5, "stddev": 0.05}},
        derived_from_evidence_ids=list(range(1, 6)),
        source_kind_composition={"REAL": 5},
        occurrence_count=5,
        confidence=0.9,
        computed_at="2026-01-01T00:00:00+00:00",
    )
    save_factory_dna(knowledge_conn, [record])
    summary = promotion.promote_all(knowledge_conn, evidence_conn)
    assert summary.promoted == 1  # 5/5 clears the (lower) pair_level thresholds


def test_row_per_attempt_semantics_one_gold_row_per_factory_dna_row(knowledge_conn, evidence_conn):
    save_factory_dna(
        knowledge_conn,
        [
            _note_level_record("a", source_kind_composition={"REAL": 30}),
            _note_level_record("b", source_kind_composition={"REAL": 1, "SYNTHETIC": 1}),
            _note_level_record("c", source_kind_composition={"REAL": 1}, occurrence_count=1, source_count=1),
        ],
    )
    promotion.promote_all(knowledge_conn, evidence_conn)
    all_rules = load_gold_dna(knowledge_conn)
    assert {r.rule_id for r in all_rules} == {"a", "b", "c"}
    assert sum(1 for r in all_rules if r.is_promoted) == 1


def test_synthetic_exclusion_invariant_no_promoted_rule_traces_to_synthetic_evidence(
    knowledge_conn, evidence_conn
):
    """Verbatim CI invariant from docs/TEST_STRATEGY.md: no promoted
    gold_dna row may reference a factory_dna row whose evidence chain
    contains any SYNTHETIC-sourced record.
    """
    save_factory_dna(
        knowledge_conn,
        [
            _note_level_record("clean", source_kind_composition={"REAL": 50}),
            _note_level_record("tainted", source_kind_composition={"REAL": 40, "SYNTHETIC": 1}),
        ],
    )
    promotion.promote_all(knowledge_conn, evidence_conn)

    rows = knowledge_conn.execute(
        """
        SELECT fd.source_kind_composition
        FROM gold_dna gd
        JOIN factory_dna fd ON fd.id = gd.promoted_from_factory_dna_id
        WHERE gd.promoted_at IS NOT NULL
        """
    ).fetchall()
    import json

    for row in rows:
        composition = json.loads(row["source_kind_composition"])
        assert composition.get("SYNTHETIC", 0) == 0


def test_registry_never_exposes_blocked_rules(knowledge_conn, evidence_conn):
    from korg_optimizer.gold import registry

    save_factory_dna(
        knowledge_conn,
        [
            _note_level_record("promoted_one", source_kind_composition={"REAL": 30}),
            _note_level_record("blocked_one", source_kind_composition={"REAL": 1, "SYNTHETIC": 1}),
        ],
    )
    promotion.promote_all(knowledge_conn, evidence_conn)

    assert registry.get_rule(knowledge_conn, "promoted_one") is not None
    assert registry.get_rule(knowledge_conn, "blocked_one") is None
    assert all(r.is_promoted for r in registry.get_rules_by_category(knowledge_conn, "rhythm"))
