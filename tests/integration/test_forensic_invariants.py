"""B8 -- zakljucavanje nalaza iz FORENZIKA.md.

Ovi testovi pretvaraju izmjerene cinjenice u regresijsku zastitu. Ako se
ponasanje uparivaca ili sadrzaj baze promijeni, ovdje puca.

Testovi koji trebaju vanjski korpus ili bazu se preskacu kada nisu
dostupni, pa suite ostaje upotrebljiv i bez 68 MB podataka.
"""

from __future__ import annotations

import collections
import os
import sqlite3
from pathlib import Path

import pytest

from pa800_enhancer.analysis.notes import pair_notes
from pa800_enhancer.smf.reader import SmfReader

DB_ENV = "PA800_TEST_DATABASE"

# Izmjereno 19.08.2026. -- vidi FORENZIKA.md
EXPECTED_FINGERPRINTS = 3368
EXPECTED_SOURCES = 3393
EXPECTED_ROLES = 14369
EXPECTED_ROLE_NOTES = 3653509
EXPECTED_FACTORY_SOURCES = 3211
EXPECTED_GOLD_SOURCES = 182
EXPECTED_DUPLICATE_GROUPS = 25
EXPECTED_VECTOR_DIMENSION = 48


@pytest.fixture
def database() -> sqlite3.Connection:
    value = os.environ.get(DB_ENV)
    if not value or not Path(value).is_file():
        pytest.skip(f"{DB_ENV} nije postavljen na postojecu bazu")
    return sqlite3.connect(f"file:{value}?mode=ro", uri=True)


class TestUnpairedNoteBehaviour:
    """Viseci Note On se ne uparuje -- uzrok gubitka od 0,99 %."""

    def test_dangling_note_is_dropped(self, dangling_note_midi) -> None:
        song = SmfReader().read(dangling_note_midi)
        notes, unmatched = pair_notes(song)

        assert len(notes) == 1, "samo zatvorena nota postaje Note"
        assert len(unmatched) == 1, "viseci Note On ostaje neuparen"

    def test_unmatched_events_are_reported_not_hidden(
        self, dangling_note_midi
    ) -> None:
        """Kljucno: informacija o gubitku POSTOJI u API-ju.

        Nalaz iz forenzike nije da se note gube nego da se gubitak ne
        prijavljuje na visim slojevima. Ovaj test cuva donji sloj ispravnim.
        """
        song = SmfReader().read(dangling_note_midi)
        _notes, unmatched = pair_notes(song)

        assert unmatched, "pair_notes mora vratiti neuparene dogadjaje"
        assert all(hasattr(e, "absolute_tick") for e in unmatched)

    def test_balanced_file_loses_nothing(self, multi_track_midi) -> None:
        song = SmfReader().read(multi_track_midi)
        notes, unmatched = pair_notes(song)

        assert len(unmatched) == 0
        assert len(notes) == 2


@pytest.mark.corpus
class TestDatabaseInvariants:
    def test_row_counts(self, database: sqlite3.Connection) -> None:
        def count(table: str) -> int:
            return database.execute(f"select count(*) from {table}").fetchone()[0]

        assert count("midi_fingerprints") == EXPECTED_FINGERPRINTS
        assert count("midi_fingerprint_sources") == EXPECTED_SOURCES
        assert count("midi_fingerprint_roles") == EXPECTED_ROLES

    def test_total_role_notes(self, database: sqlite3.Connection) -> None:
        total = database.execute(
            "select sum(note_count) from midi_fingerprint_roles"
        ).fetchone()[0]
        assert total == EXPECTED_ROLE_NOTES

    def test_corpus_split(self, database: sqlite3.Connection) -> None:
        rows = dict(
            database.execute(
                "select corpus_kind, count(*) from midi_fingerprint_sources group by 1"
            )
        )
        assert rows["factory"] == EXPECTED_FACTORY_SOURCES
        assert rows["gold"] == EXPECTED_GOLD_SOURCES

    def test_integrity_is_clean(self, database: sqlite3.Connection) -> None:
        assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert database.execute("PRAGMA foreign_key_check").fetchall() == []

    def test_no_orphan_rows(self, database: sqlite3.Connection) -> None:
        orphans = database.execute(
            """select count(*) from midi_fingerprint_roles r
               left join midi_fingerprints f on f.fingerprint_id = r.fingerprint_id
               where f.fingerprint_id is null"""
        ).fetchone()[0]
        assert orphans == 0

    def test_duplicate_groups_are_deduplicated(
        self, database: sqlite3.Connection
    ) -> None:
        """25 grupa duplikata dijeli otisak, ali zadrzava sve lokatore."""
        shared = database.execute(
            """select count(*) from (
                   select fingerprint_id from midi_fingerprint_sources
                   group by 1 having count(*) > 1)"""
        ).fetchone()[0]
        assert shared == EXPECTED_DUPLICATE_GROUPS

    def test_roles_are_valid(self, database: sqlite3.Connection) -> None:
        roles = {
            r[0]
            for r in database.execute(
                "select distinct role from midi_fingerprint_roles"
            )
        }
        assert roles == {"solo", "accompaniment", "bass", "drums", "guitar"}

    def test_no_empty_roles(self, database: sqlite3.Connection) -> None:
        empty = database.execute(
            "select count(*) from midi_fingerprint_roles where note_count <= 0"
        ).fetchone()[0]
        assert empty == 0

    def test_vector_dimension_is_constant(
        self, database: sqlite3.Connection
    ) -> None:
        import json

        dims = collections.Counter(
            len(json.loads(row[0]))
            for row in database.execute(
                "select vector_json from midi_fingerprint_roles limit 500"
            )
        )
        assert list(dims) == [EXPECTED_VECTOR_DIMENSION]

    def test_no_nan_in_vectors(self, database: sqlite3.Connection) -> None:
        import json
        import math

        for (raw,) in database.execute(
            "select vector_json from midi_fingerprint_roles limit 500"
        ):
            for value in json.loads(raw):
                assert not math.isnan(value)
                assert not math.isinf(value)


@pytest.mark.corpus
class TestCorpusInvariants:
    def test_every_file_parses(self, corpus_root: Path) -> None:
        reader = SmfReader()
        failures = []
        for path in sorted(corpus_root.rglob("*.mid"))[:200]:
            try:
                reader.read(path)
            except Exception as error:  # noqa: BLE001 - test prijavljuje sve
                failures.append((path.name, str(error)))
        assert not failures, f"neuspjeli fajlovi: {failures[:5]}"
