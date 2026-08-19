"""Small real-data smoke test for the extraction pipeline. Uses a
handful of real Factory Style files (referenced from
tests.unit.factory.samples, not duplicated) -- not the full 3211-file
corpus, which is too slow for the regular test suite. Full-corpus
extraction is run manually via
``python -m korg_optimizer.dna.extraction``.
"""

from __future__ import annotations

import shutil

from korg_optimizer.dna import extraction
from korg_optimizer.factory import real_dataset
from korg_optimizer.infrastructure.database import connection as db
from korg_optimizer.infrastructure.database.schema import KNOWLEDGE_DB_DDL, KNOWLEDGE_DB_SCHEMA_VERSION

from tests.unit.factory.samples import FACTORY_STYLES_ROOT, SECTION_SAMPLES

# Every DNA group requires >=2 distinct contributing files
# (MIN_GROUP_SOURCE_FILES). SECTION_SAMPLES/TRACK_COUNT_SAMPLES are all
# from the same style ("50's  Fox") except one entry, so picking an
# arbitrary slice of them yields exactly one file per (style_section,
# channel) group -- not enough. Build an explicit set spanning two
# different styles on the same sections instead.
_TWO_STYLE_SAMPLES = {
    "fox_var1": SECTION_SAMPLES["Var1"],
    "dance_var1": FACTORY_STYLES_ROOT / "60's Dance" / "60's Dance_Var1.mid",
    "fox_break": SECTION_SAMPLES["Break"],
    "dance_break": FACTORY_STYLES_ROOT / "60's Dance" / "60's Dance_Break.mid",
}


def test_extraction_against_small_real_sample_produces_plausible_rows(tmp_path):
    factory_dir = tmp_path / "real"
    factory_dir.mkdir()
    for name, path in _TWO_STYLE_SAMPLES.items():
        shutil.copy(path, factory_dir / f"{name}_{path.name}")

    evidence_conn = db.get_connection(tmp_path / "evidence.db")
    db.ensure_schema(evidence_conn)
    summary = real_dataset.import_real_dataset(factory_dir, evidence_conn)
    assert summary.errors == []
    assert summary.imported > 0

    knowledge_conn = db.get_connection(tmp_path / "knowledge.db")
    db.ensure_schema(knowledge_conn, KNOWLEDGE_DB_DDL, schema_version=KNOWLEDGE_DB_SCHEMA_VERSION)

    row_count = extraction.extract_and_save(evidence_conn, knowledge_conn)
    assert row_count > 0

    rows = knowledge_conn.execute("SELECT * FROM factory_dna").fetchall()
    assert len(rows) == row_count

    categories = {row["category"] for row in rows}
    assert categories <= {"rhythm", "velocity", "timing", "arrangement"}

    for row in rows:
        assert 0.0 <= row["confidence"] <= 1.0
        assert row["occurrence_count"] > 0
        import json

        composition = json.loads(row["source_kind_composition"])
        assert composition.get("SYNTHETIC", 0) == 0
        assert composition.get("REAL", 0) > 0

    evidence_conn.close()
    knowledge_conn.close()


def test_extraction_is_idempotent_on_rerun(tmp_path):
    factory_dir = tmp_path / "real"
    factory_dir.mkdir()
    for name, path in _TWO_STYLE_SAMPLES.items():
        shutil.copy(path, factory_dir / f"{name}_{path.name}")

    evidence_conn = db.get_connection(tmp_path / "evidence.db")
    db.ensure_schema(evidence_conn)
    real_dataset.import_real_dataset(factory_dir, evidence_conn)

    knowledge_conn = db.get_connection(tmp_path / "knowledge.db")
    db.ensure_schema(knowledge_conn, KNOWLEDGE_DB_DDL, schema_version=KNOWLEDGE_DB_SCHEMA_VERSION)

    first_count = extraction.extract_and_save(evidence_conn, knowledge_conn)
    second_count = extraction.extract_and_save(evidence_conn, knowledge_conn)

    assert first_count == second_count
    total_rows = knowledge_conn.execute("SELECT COUNT(*) FROM factory_dna").fetchone()[0]
    assert total_rows == first_count  # full rebuild, not accumulation

    evidence_conn.close()
    knowledge_conn.close()
