from __future__ import annotations

import json
import shutil

from korg_optimizer.infrastructure import golden_dataset
from korg_optimizer.infrastructure.database import connection as db

from tests.unit.factory.samples import GOLDEN_NEAR_DUPLICATE, GOLDEN_SAMPLE


def _conn(tmp_path):
    c = db.get_connection(tmp_path / "evidence.db")
    db.ensure_schema(c)
    return c


def test_catalog_golden_dataset_writes_manifest_and_table(tmp_path):
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    shutil.copy(GOLDEN_SAMPLE, songs_dir / GOLDEN_SAMPLE.name)
    shutil.copy(GOLDEN_NEAR_DUPLICATE, songs_dir / GOLDEN_NEAR_DUPLICATE.name)

    conn = _conn(tmp_path)
    summary = golden_dataset.catalog_golden_dataset(songs_dir, conn)

    assert summary.imported == 2
    assert summary.errors == []

    rows = conn.execute("SELECT file_path, sha256_hash FROM golden_files").fetchall()
    assert len(rows) == 2

    manifest = json.loads((songs_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    assert len(manifest) == 2
    assert {"filename", "sha256", "byte_size"} <= manifest[0].keys()
    conn.close()


def test_catalog_golden_dataset_is_idempotent(tmp_path):
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    shutil.copy(GOLDEN_SAMPLE, songs_dir / GOLDEN_SAMPLE.name)

    conn = _conn(tmp_path)
    first = golden_dataset.catalog_golden_dataset(songs_dir, conn)
    second = golden_dataset.catalog_golden_dataset(songs_dir, conn)

    assert first.imported == 1
    assert second.imported == 0
    assert second.unchanged == 1
    conn.close()
