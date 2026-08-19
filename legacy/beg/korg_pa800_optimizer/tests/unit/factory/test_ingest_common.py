"""Tests for the shared ingestion helper used by both real_dataset.py
and synthetic_dataset.py -- source_kind is always hardcoded by the
caller, never accepted as a parameter to `ingest`/`upsert_source_file`,
and a changed hash at an already-imported path raises
EvidenceIntegrityError rather than silently updating.
"""

from __future__ import annotations

import inspect
import shutil

import pytest

from korg_optimizer.factory import _ingest_common
from korg_optimizer.factory import real_dataset, synthetic_dataset
from korg_optimizer.infrastructure.database import connection as db
from korg_optimizer.midi import raw_import

from tests.unit.factory.samples import CLEAN_SAMPLE


@pytest.fixture()
def conn(tmp_path):
    c = db.get_connection(tmp_path / "evidence.db")
    db.ensure_schema(c)
    yield c
    c.close()


def test_ingest_never_accepts_source_kind_from_a_public_dataset_caller():
    real_sig = inspect.signature(real_dataset.import_real_dataset)
    synthetic_sig = inspect.signature(synthetic_dataset.import_synthetic_dataset)
    assert "source_kind" not in real_sig.parameters
    assert "source_kind" not in synthetic_sig.parameters


def test_real_dataset_hardcodes_source_kind_real(tmp_path, conn):
    factory_dir = tmp_path / "real"
    factory_dir.mkdir()
    shutil.copy(CLEAN_SAMPLE, factory_dir / "sample.mid")

    summary = real_dataset.import_real_dataset(factory_dir, conn)

    assert summary.imported == 1
    assert summary.errors == []
    row = conn.execute("SELECT source_kind FROM source_files").fetchone()
    assert row["source_kind"] == "REAL"


def test_synthetic_dataset_hardcodes_source_kind_synthetic(tmp_path, conn):
    synthetic_dir = tmp_path / "synthetic"
    synthetic_dir.mkdir()
    shutil.copy(CLEAN_SAMPLE, synthetic_dir / "sample.mid")

    summary = synthetic_dataset.import_synthetic_dataset(synthetic_dir, conn)

    assert summary.imported == 1
    row = conn.execute("SELECT source_kind FROM source_files").fetchone()
    assert row["source_kind"] == "SYNTHETIC"


def test_reimport_of_unchanged_file_is_a_noop(tmp_path, conn):
    factory_dir = tmp_path / "real"
    factory_dir.mkdir()
    shutil.copy(CLEAN_SAMPLE, factory_dir / "sample.mid")

    first = real_dataset.import_real_dataset(factory_dir, conn)
    second = real_dataset.import_real_dataset(factory_dir, conn)

    assert first.imported == 1
    assert second.imported == 0
    assert second.unchanged == 1
    total = conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
    assert total == 1


def test_changed_hash_at_existing_path_raises_integrity_error(tmp_path, conn):
    record = raw_import.import_file(CLEAN_SAMPLE)
    status, _id = _ingest_common.upsert_source_file(conn, "some/path.mid", record, "REAL")
    assert status == "imported"
    conn.commit()

    fake_record = raw_import.SourceFileRecord(
        path=record.path, sha256_hash="deadbeef" * 8, byte_size=record.byte_size
    )
    with pytest.raises(_ingest_common.EvidenceIntegrityError):
        _ingest_common.upsert_source_file(conn, "some/path.mid", fake_record, "REAL")


def test_integrity_violation_during_batch_ingest_is_recorded_not_raised(tmp_path, conn):
    factory_dir = tmp_path / "real"
    factory_dir.mkdir()
    target = factory_dir / "sample.mid"
    shutil.copy(CLEAN_SAMPLE, target)
    real_dataset.import_real_dataset(factory_dir, conn)

    # Mutate the file in place to simulate a post-import content change.
    target.write_bytes(target.read_bytes() + b"\x00")
    summary = real_dataset.import_real_dataset(factory_dir, conn)

    assert summary.imported == 0
    assert summary.unchanged == 0
    assert len(summary.errors) == 1
    assert "hash changed" in summary.errors[0]
