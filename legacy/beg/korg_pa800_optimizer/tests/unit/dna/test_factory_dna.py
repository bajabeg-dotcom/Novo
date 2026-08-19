from __future__ import annotations

import sqlite3

import pytest

from korg_optimizer.dna.factory_dna import (
    FactoryDNARecord,
    get_by_rule_id,
    load_factory_dna,
    load_factory_dna_with_ids,
    save_factory_dna,
)
from korg_optimizer.infrastructure.database import connection as db
from korg_optimizer.infrastructure.database.schema import KNOWLEDGE_DB_DDL, KNOWLEDGE_DB_SCHEMA_VERSION


@pytest.fixture()
def conn(tmp_path):
    c = db.get_connection(tmp_path / "knowledge.db")
    db.ensure_schema(c, KNOWLEDGE_DB_DDL, schema_version=KNOWLEDGE_DB_SCHEMA_VERSION)
    yield c
    c.close()


def _sample_record(rule_id: str = "dna.rhythm.section.Var1.ch9") -> FactoryDNARecord:
    return FactoryDNARecord(
        rule_id=rule_id,
        category="rhythm",
        style_section="Var1",
        channel=9,
        channel_b=None,
        metrics={"density": {"mean": 2.0, "stddev": 0.5}},
        derived_from_evidence_ids=[3, 1, 2],
        source_kind_composition={"REAL": 42},
        occurrence_count=500,
        confidence=0.75,
        computed_at="2026-01-01T00:00:00+00:00",
    )


def test_save_and_load_round_trip(conn):
    record = _sample_record()
    save_factory_dna(conn, [record])

    loaded = load_factory_dna(conn)
    assert len(loaded) == 1
    assert loaded[0].rule_id == record.rule_id
    assert loaded[0].metrics == record.metrics
    assert loaded[0].derived_from_evidence_ids == [1, 2, 3]  # sorted, deduped
    assert loaded[0].source_kind_composition == {"REAL": 42}


def test_save_is_a_full_rebuild_not_an_upsert(conn):
    save_factory_dna(conn, [_sample_record("dna.rhythm.section.Var1.ch9")])
    save_factory_dna(conn, [_sample_record("dna.rhythm.section.Var2.ch9")])

    loaded = load_factory_dna(conn)
    assert len(loaded) == 1
    assert loaded[0].rule_id == "dna.rhythm.section.Var2.ch9"


def test_unique_rule_id_enforced_within_one_save(conn):
    with pytest.raises(sqlite3.IntegrityError):
        save_factory_dna(conn, [_sample_record("dup"), _sample_record("dup")])


def test_load_factory_dna_filters(conn):
    save_factory_dna(
        conn,
        [
            _sample_record("a"),
            FactoryDNARecord(
                rule_id="b",
                category="velocity",
                style_section="Break",
                channel=11,
                channel_b=None,
                metrics={},
                derived_from_evidence_ids=[9],
                source_kind_composition={"REAL": 5},
                occurrence_count=10,
                confidence=0.1,
                computed_at="2026-01-01T00:00:00+00:00",
            ),
        ],
    )
    assert len(load_factory_dna(conn, category="velocity")) == 1
    assert len(load_factory_dna(conn, style_section="Var1")) == 1
    assert len(load_factory_dna(conn, channel=11)) == 1
    assert len(load_factory_dna(conn)) == 2


def test_get_by_rule_id(conn):
    save_factory_dna(conn, [_sample_record("known")])
    assert get_by_rule_id(conn, "known") is not None
    assert get_by_rule_id(conn, "missing") is None


def test_load_factory_dna_with_ids_returns_primary_keys(conn):
    save_factory_dna(conn, [_sample_record("a"), _sample_record("b")])
    pairs = load_factory_dna_with_ids(conn)
    assert len(pairs) == 2
    ids = [p[0] for p in pairs]
    assert len(set(ids)) == 2  # distinct primary keys
    assert all(isinstance(i, int) for i in ids)
