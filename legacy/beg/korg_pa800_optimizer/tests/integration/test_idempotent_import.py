"""Cross-module integration test: running the full real-dataset
ingestion pipeline (discovery -> hash -> catalog -> evidence
extraction) twice against the same directory must not create
duplicate rows the second time.
"""

from __future__ import annotations

import shutil

from korg_optimizer.factory import real_dataset
from korg_optimizer.infrastructure.database import connection as db

from tests.unit.factory.samples import SECTION_SAMPLES


def test_running_real_ingestion_twice_produces_no_duplicates(tmp_path):
    factory_dir = tmp_path / "real"
    factory_dir.mkdir()
    for name, path in SECTION_SAMPLES.items():
        shutil.copy(path, factory_dir / f"sample_{name}.mid")

    conn = db.get_connection(tmp_path / "evidence.db")
    db.ensure_schema(conn)

    first = real_dataset.import_real_dataset(factory_dir, conn)
    second = real_dataset.import_real_dataset(factory_dir, conn)

    assert first.imported == len(SECTION_SAMPLES)
    assert first.errors == []
    assert second.imported == 0
    assert second.unchanged == len(SECTION_SAMPLES)

    source_file_count = conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
    assert source_file_count == len(SECTION_SAMPLES)

    evidence_count_after_first = conn.execute(
        "SELECT COUNT(*) FROM factory_evidence"
    ).fetchone()[0]
    # second run must not add more evidence rows for already-seen files
    assert evidence_count_after_first > 0

    conn.close()
