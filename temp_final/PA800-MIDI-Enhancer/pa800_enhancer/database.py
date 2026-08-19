import sqlite3
import json
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .hardware.loader import HardwareTestLoader
from .profiles.loader import DeviceProfileLoader
from .dna import DnaMatch, RoleFingerprint, SongFingerprint, role_distance
from .resources import ResourceResolver


DATABASE_SCHEMA_VERSION = 5
_RESOURCE_RESOLVER = ResourceResolver()
DEFAULT_DATABASE_PATH = (
    _RESOURCE_RESOLVER.find(Path("data/pa800-enhancer.db"), required=False)
    or _RESOURCE_RESOLVER.locations().database
)


@dataclass(frozen=True, slots=True)
class DatabaseStatus:
    path: str
    schema_version: int
    profile_count: int
    hardware_test_count: int
    fingerprint_count: int = 0
    fingerprint_role_count: int = 0


@dataclass(frozen=True, slots=True)
class DatabaseImportResult:
    record_type: str
    record_id: str
    record_version: str
    sha256: str
    action: str
    imported_at: str


class LocalDatabase:
    """Versioned SQLite catalog for profiles and hardware-test records."""

    def initialize(self, path: Path = DEFAULT_DATABASE_PATH) -> DatabaseStatus:
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS app_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS device_profiles (
                        profile_id TEXT NOT NULL,
                        profile_version TEXT NOT NULL,
                        schema_version INTEGER NOT NULL,
                        sha256 TEXT NOT NULL UNIQUE,
                        json_text TEXT NOT NULL,
                        imported_at TEXT NOT NULL,
                        PRIMARY KEY (profile_id, profile_version)
                    );

                    CREATE TABLE IF NOT EXISTS hardware_tests (
                        case_id TEXT NOT NULL,
                        case_version TEXT NOT NULL,
                        status TEXT NOT NULL
                            CHECK (status IN ('pending', 'passed', 'failed')),
                        manifest_sha256 TEXT NOT NULL UNIQUE,
                        json_text TEXT NOT NULL,
                        imported_at TEXT NOT NULL,
                        PRIMARY KEY (case_id, case_version)
                    );

                    CREATE INDEX IF NOT EXISTS idx_device_profiles_sha256
                        ON device_profiles (sha256);
                    CREATE INDEX IF NOT EXISTS idx_hardware_tests_status
                        ON hardware_tests (status);

                    CREATE TABLE IF NOT EXISTS midi_fingerprints (
                        fingerprint_id TEXT PRIMARY KEY,
                        schema_version INTEGER NOT NULL,
                        source_sha256 TEXT NOT NULL,
                        source_locator TEXT NOT NULL,
                        corpus_kind TEXT NOT NULL CHECK (corpus_kind IN ('gold', 'factory', 'target')),
                        ppq INTEGER NOT NULL,
                        end_tick INTEGER NOT NULL,
                        imported_at TEXT NOT NULL,
                        UNIQUE(source_sha256, corpus_kind)
                    );

                    CREATE TABLE IF NOT EXISTS midi_fingerprint_roles (
                        fingerprint_id TEXT NOT NULL REFERENCES midi_fingerprints(fingerprint_id) ON DELETE CASCADE,
                        role TEXT NOT NULL CHECK (role IN ('solo', 'accompaniment', 'bass', 'drums', 'guitar')),
                        note_count INTEGER NOT NULL,
                        vector_json TEXT NOT NULL,
                        features_json TEXT NOT NULL,
                        PRIMARY KEY (fingerprint_id, role)
                    );

                    CREATE INDEX IF NOT EXISTS idx_fingerprint_kind
                        ON midi_fingerprints (corpus_kind);
                    CREATE INDEX IF NOT EXISTS idx_fingerprint_role
                        ON midi_fingerprint_roles (role);

                    CREATE TABLE IF NOT EXISTS midi_fingerprint_sources (
                        source_locator TEXT NOT NULL,
                        corpus_kind TEXT NOT NULL CHECK (corpus_kind IN ('gold', 'factory', 'target')),
                        source_sha256 TEXT NOT NULL,
                        fingerprint_id TEXT NOT NULL REFERENCES midi_fingerprints(fingerprint_id) ON DELETE CASCADE,
                        imported_at TEXT NOT NULL,
                        PRIMARY KEY (source_locator, corpus_kind)
                    );
                    CREATE INDEX IF NOT EXISTS idx_fingerprint_source_hash
                        ON midi_fingerprint_sources (source_sha256);

                    CREATE TABLE IF NOT EXISTS music_sources (
                        source_id TEXT PRIMARY KEY,
                        sha256 TEXT NOT NULL,
                        locator TEXT NOT NULL,
                        archive_chain_json TEXT NOT NULL DEFAULT '[]',
                        corpus_kind TEXT NOT NULL CHECK (corpus_kind IN ('gold','factory','target','generated')),
                        evidence_status TEXT NOT NULL CHECK (evidence_status IN ('experimental','candidate','approved','rejected')),
                        UNIQUE (sha256, locator)
                    );
                    CREATE TABLE IF NOT EXISTS music_songs (
                        song_id TEXT PRIMARY KEY,
                        source_id TEXT NOT NULL REFERENCES music_sources(source_id) ON DELETE CASCADE,
                        ppq INTEGER, end_tick INTEGER NOT NULL,
                        tempo_bpm REAL, meter_numerator INTEGER, meter_denominator INTEGER,
                        key_label TEXT, key_confidence REAL CHECK (key_confidence BETWEEN 0 AND 1),
                        style_family_id TEXT,
                        analysis_schema INTEGER NOT NULL,
                        analysis_json TEXT NOT NULL DEFAULT '{}'
                    );
                    CREATE TABLE IF NOT EXISTS music_sections (
                        section_id TEXT PRIMARY KEY,
                        song_id TEXT NOT NULL REFERENCES music_songs(song_id) ON DELETE CASCADE,
                        section_type TEXT NOT NULL,
                        variation_level INTEGER CHECK (variation_level BETWEEN 1 AND 4),
                        start_tick INTEGER NOT NULL, end_tick INTEGER NOT NULL,
                        confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
                        evidence_json TEXT NOT NULL DEFAULT '{}',
                        CHECK (end_tick > start_tick)
                    );
                    CREATE TABLE IF NOT EXISTS music_tracks (
                        track_segment_id TEXT PRIMARY KEY,
                        song_id TEXT NOT NULL REFERENCES music_songs(song_id) ON DELETE CASCADE,
                        track_index INTEGER NOT NULL, channel INTEGER NOT NULL CHECK (channel BETWEEN 1 AND 16),
                        start_tick INTEGER NOT NULL, end_tick INTEGER NOT NULL,
                        role TEXT NOT NULL,
                        bank_msb INTEGER, bank_lsb INTEGER, program INTEGER,
                        role_confidence REAL NOT NULL CHECK (role_confidence BETWEEN 0 AND 1),
                        evidence_json TEXT NOT NULL DEFAULT '{}',
                        CHECK (end_tick >= start_tick)
                    );
                    CREATE TABLE IF NOT EXISTS music_chords (
                        chord_id TEXT PRIMARY KEY,
                        song_id TEXT NOT NULL REFERENCES music_songs(song_id) ON DELETE CASCADE,
                        start_tick INTEGER NOT NULL, end_tick INTEGER NOT NULL,
                        root_pitch_class INTEGER CHECK (root_pitch_class BETWEEN 0 AND 11),
                        quality TEXT, bass_pitch_class INTEGER CHECK (bass_pitch_class BETWEEN 0 AND 11),
                        confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
                        evidence_json TEXT NOT NULL DEFAULT '{}',
                        CHECK (end_tick > start_tick)
                    );
                    CREATE TABLE IF NOT EXISTS style_families (
                        style_family_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL, meter TEXT, tempo_min REAL, tempo_max REAL,
                        evidence_status TEXT NOT NULL CHECK (evidence_status IN ('experimental','candidate','approved','rejected')),
                        metadata_json TEXT NOT NULL DEFAULT '{}'
                    );
                    CREATE TABLE IF NOT EXISTS style_elements (
                        style_element_id TEXT PRIMARY KEY,
                        style_family_id TEXT NOT NULL REFERENCES style_families(style_family_id) ON DELETE CASCADE,
                        song_id TEXT REFERENCES music_songs(song_id) ON DELETE SET NULL,
                        element_type TEXT NOT NULL,
                        variation_level INTEGER CHECK (variation_level BETWEEN 1 AND 4),
                        start_tick INTEGER NOT NULL, end_tick INTEGER NOT NULL,
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        CHECK (end_tick > start_tick)
                    );
                    CREATE TABLE IF NOT EXISTS dataset_groups (
                        group_id TEXT PRIMARY KEY,
                        split TEXT NOT NULL CHECK (split IN ('train','validation','test','excluded')),
                        grouping_reason TEXT NOT NULL,
                        split_seed INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS dataset_members (
                        group_id TEXT NOT NULL REFERENCES dataset_groups(group_id) ON DELETE CASCADE,
                        source_id TEXT NOT NULL REFERENCES music_sources(source_id) ON DELETE CASCADE,
                        PRIMARY KEY (group_id, source_id),
                        UNIQUE (source_id)
                    );
                    CREATE TABLE IF NOT EXISTS music_annotations (
                        annotation_id TEXT PRIMARY KEY,
                        entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
                        annotation_type TEXT NOT NULL, value_json TEXT NOT NULL,
                        origin TEXT NOT NULL CHECK (origin IN ('automatic','manual','imported')),
                        confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
                        reviewer TEXT, created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_music_sources_corpus ON music_sources(corpus_kind);
                    CREATE INDEX IF NOT EXISTS idx_music_sections_song_tick ON music_sections(song_id,start_tick);
                    CREATE INDEX IF NOT EXISTS idx_music_tracks_song_role ON music_tracks(song_id,role);
                    CREATE INDEX IF NOT EXISTS idx_music_chords_song_tick ON music_chords(song_id,start_tick);
                    CREATE INDEX IF NOT EXISTS idx_style_elements_family_type ON style_elements(style_family_id,element_type);
                    CREATE INDEX IF NOT EXISTS idx_annotations_entity ON music_annotations(entity_type,entity_id);
                    INSERT OR IGNORE INTO midi_fingerprint_sources
                        (source_locator, corpus_kind, source_sha256, fingerprint_id, imported_at)
                        SELECT source_locator, corpus_kind, source_sha256, fingerprint_id, imported_at
                        FROM midi_fingerprints;
                    """
                )
                stored = connection.execute(
                    "SELECT value FROM app_metadata WHERE key = 'schema_version'"
                ).fetchone()
                if stored is not None and int(stored[0]) > DATABASE_SCHEMA_VERSION:
                    raise RuntimeError(
                        f"database schema {stored[0]} is newer than supported "
                        f"schema {DATABASE_SCHEMA_VERSION}"
                    )
                if stored is not None and int(stored[0]) < 4:
                    connection.executescript(
                        """
                        ALTER TABLE midi_fingerprint_roles RENAME TO midi_fingerprint_roles_v3;
                        CREATE TABLE midi_fingerprint_roles (
                            fingerprint_id TEXT NOT NULL REFERENCES midi_fingerprints(fingerprint_id) ON DELETE CASCADE,
                            role TEXT NOT NULL CHECK (role IN ('solo', 'accompaniment', 'bass', 'drums', 'guitar')),
                            note_count INTEGER NOT NULL,
                            vector_json TEXT NOT NULL,
                            features_json TEXT NOT NULL,
                            PRIMARY KEY (fingerprint_id, role)
                        );
                        INSERT INTO midi_fingerprint_roles SELECT * FROM midi_fingerprint_roles_v3;
                        DROP TABLE midi_fingerprint_roles_v3;
                        CREATE INDEX idx_fingerprint_role ON midi_fingerprint_roles (role);
                        """
                    )
                connection.execute(
                    """
                    INSERT INTO app_metadata (key, value) VALUES ('schema_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (str(DATABASE_SCHEMA_VERSION),),
                )
        return self.status(path)

    def status(self, path: Path = DEFAULT_DATABASE_PATH) -> DatabaseStatus:
        if not path.is_file():
            raise FileNotFoundError(f"database does not exist: {path}")
        try:
            with closing(
                sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            ) as connection:
                row = connection.execute(
                    "SELECT value FROM app_metadata WHERE key = 'schema_version'"
                ).fetchone()
                if row is None:
                    raise RuntimeError("database has no schema_version metadata")
                version = int(row[0])
                if version > DATABASE_SCHEMA_VERSION:
                    raise RuntimeError(
                        f"database schema {version} is newer than supported "
                        f"schema {DATABASE_SCHEMA_VERSION}"
                    )
                profile_count = connection.execute(
                    "SELECT COUNT(*) FROM device_profiles"
                ).fetchone()[0]
                hardware_test_count = connection.execute(
                    "SELECT COUNT(*) FROM hardware_tests"
                ).fetchone()[0]
                fingerprint_count = connection.execute(
                    "SELECT COUNT(*) FROM midi_fingerprints"
                ).fetchone()[0]
                fingerprint_role_count = connection.execute(
                    "SELECT COUNT(*) FROM midi_fingerprint_roles"
                ).fetchone()[0]
        except sqlite3.DatabaseError as error:
            raise RuntimeError(f"invalid database {path}: {error}") from error
        return DatabaseStatus(
            path=str(path),
            schema_version=version,
            profile_count=profile_count,
            hardware_test_count=hardware_test_count,
            fingerprint_count=fingerprint_count,
            fingerprint_role_count=fingerprint_role_count,
        )

    def import_fingerprint(
        self,
        fingerprint: SongFingerprint,
        source_locator: str,
        corpus_kind: str,
        path: Path = DEFAULT_DATABASE_PATH,
    ) -> str:
        if corpus_kind not in {"gold", "factory", "target"}:
            raise ValueError("corpus_kind must be gold, factory or target")
        self.initialize(path)
        imported_at = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys = ON")
                previous = connection.execute(
                    "SELECT fingerprint_id FROM midi_fingerprints WHERE source_sha256=? AND corpus_kind=?",
                    (fingerprint.source_sha256, corpus_kind),
                ).fetchone()
                if previous and previous[0] != fingerprint.fingerprint_id:
                    connection.execute("DELETE FROM midi_fingerprints WHERE fingerprint_id=?", previous)
                connection.execute(
                    """INSERT INTO midi_fingerprints
                       (fingerprint_id, schema_version, source_sha256, source_locator,
                        corpus_kind, ppq, end_tick, imported_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(source_sha256, corpus_kind) DO UPDATE SET
                         fingerprint_id=excluded.fingerprint_id,
                         source_locator=excluded.source_locator,
                         ppq=excluded.ppq, end_tick=excluded.end_tick,
                         imported_at=excluded.imported_at""",
                    (fingerprint.fingerprint_id, fingerprint.schema_version,
                     fingerprint.source_sha256, source_locator, corpus_kind,
                     fingerprint.ppq, fingerprint.end_tick, imported_at),
                )
                connection.execute(
                    "DELETE FROM midi_fingerprint_roles WHERE fingerprint_id = ?",
                    (fingerprint.fingerprint_id,),
                )
                connection.executemany(
                    """INSERT INTO midi_fingerprint_roles
                       (fingerprint_id, role, note_count, vector_json, features_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    [
                        (fingerprint.fingerprint_id, role.role, role.note_count,
                         json.dumps(role.vector(), separators=(",", ":")),
                         json.dumps(asdict(role), separators=(",", ":")))
                        for role in fingerprint.roles
                    ],
                )
                connection.execute(
                    """INSERT INTO midi_fingerprint_sources
                       (source_locator, corpus_kind, source_sha256, fingerprint_id, imported_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(source_locator, corpus_kind) DO UPDATE SET
                         source_sha256=excluded.source_sha256,
                         fingerprint_id=excluded.fingerprint_id,
                         imported_at=excluded.imported_at""",
                    (source_locator, corpus_kind, fingerprint.source_sha256,
                     fingerprint.fingerprint_id, imported_at),
                )
        return fingerprint.fingerprint_id

    def find_fingerprint_id(self, source_sha256: str, corpus_kind: str,
                            path: Path = DEFAULT_DATABASE_PATH) -> str | None:
        self.initialize(path)
        with closing(sqlite3.connect(path)) as connection:
            row = connection.execute(
                "SELECT fingerprint_id FROM midi_fingerprints WHERE source_sha256=? AND corpus_kind=?",
                (source_sha256, corpus_kind),
            ).fetchone()
        return str(row[0]) if row else None

    def fingerprint_index(self, path: Path = DEFAULT_DATABASE_PATH) -> dict[tuple[str, str], str]:
        self.initialize(path)
        with closing(sqlite3.connect(path)) as connection:
            return {
                (str(source_hash), str(kind)): str(fingerprint_id)
                for source_hash, kind, fingerprint_id in connection.execute(
                    "SELECT source_sha256, corpus_kind, fingerprint_id FROM midi_fingerprints"
                )
            }

    def link_fingerprint_sources(
        self, sources: list[tuple[str, str, str, str]],
        path: Path = DEFAULT_DATABASE_PATH,
    ) -> None:
        """Link (locator, kind, sha256, fingerprint_id) evidence in one transaction."""
        if not sources:
            return
        self.initialize(path)
        imported_at = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.executemany(
                    """INSERT INTO midi_fingerprint_sources
                       (source_locator, corpus_kind, source_sha256, fingerprint_id, imported_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(source_locator, corpus_kind) DO UPDATE SET
                         source_sha256=excluded.source_sha256,
                         fingerprint_id=excluded.fingerprint_id,
                         imported_at=excluded.imported_at""",
                    [(*source, imported_at) for source in sources],
                )

    def link_fingerprint_source(self, fingerprint_id: str, source_locator: str,
                                source_sha256: str, corpus_kind: str,
                                path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.initialize(path)
        imported_at = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute(
                    """INSERT INTO midi_fingerprint_sources
                       (source_locator, corpus_kind, source_sha256, fingerprint_id, imported_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(source_locator, corpus_kind) DO UPDATE SET
                         source_sha256=excluded.source_sha256,
                         fingerprint_id=excluded.fingerprint_id,
                         imported_at=excluded.imported_at""",
                    (source_locator, corpus_kind, source_sha256, fingerprint_id, imported_at),
                )

    def nearest_fingerprints(
        self,
        fingerprint: SongFingerprint,
        *,
        corpus_kind: str = "gold",
        path: Path = DEFAULT_DATABASE_PATH,
    ) -> tuple[DnaMatch, ...]:
        self.initialize(path)
        matches: list[DnaMatch] = []
        with closing(sqlite3.connect(path)) as connection:
            for query in fingerprint.roles:
                rows = connection.execute(
                    """SELECT f.fingerprint_id, f.source_locator, f.corpus_kind, r.features_json
                       FROM midi_fingerprint_roles r
                       JOIN midi_fingerprints f USING (fingerprint_id)
                       WHERE f.corpus_kind = ? AND r.role = ?""",
                    (corpus_kind, query.role),
                ).fetchall()
                candidates = []
                for fingerprint_id, locator, kind, features_json in rows:
                    raw = json.loads(features_json)
                    for key in ("onset_grid", "pitch_classes", "drum_classes"):
                        raw[key] = tuple(raw[key])
                    candidate = RoleFingerprint(**raw)
                    candidates.append(DnaMatch(fingerprint_id, locator, kind, query.role,
                                               role_distance(query, candidate), candidate))
                if candidates:
                    matches.append(min(candidates, key=lambda item: item.distance))
        return tuple(matches)

    def import_profile(
        self, profile_path: Path, path: Path = DEFAULT_DATABASE_PATH
    ) -> DatabaseImportResult:
        loader = DeviceProfileLoader()
        profile = loader.load(profile_path)
        return self._upsert(
            path=path,
            table="device_profiles",
            id_column="profile_id",
            version_column="profile_version",
            record_type="device_profile",
            record_id=profile.profile_id,
            record_version=profile.profile_version,
            digest=loader.digest(profile),
            json_text=loader.dumps(profile),
            extra_columns=("schema_version",),
            extra_values=(profile.schema_version,),
        )

    def import_hardware_test(
        self, manifest_path: Path, path: Path = DEFAULT_DATABASE_PATH
    ) -> DatabaseImportResult:
        loader = HardwareTestLoader()
        case = loader.load(manifest_path)
        return self._upsert(
            path=path,
            table="hardware_tests",
            id_column="case_id",
            version_column="case_version",
            record_type="hardware_test",
            record_id=case.case_id,
            record_version=case.case_version,
            digest=loader.digest(case),
            json_text=loader.dumps(case),
            extra_columns=("status",),
            extra_values=(case.status,),
            digest_column="manifest_sha256",
        )

    def _upsert(
        self,
        *,
        path: Path,
        table: str,
        id_column: str,
        version_column: str,
        record_type: str,
        record_id: str,
        record_version: str,
        digest: str,
        json_text: str,
        extra_columns: tuple[str, ...],
        extra_values: tuple[object, ...],
        digest_column: str = "sha256",
    ) -> DatabaseImportResult:
        self.initialize(path)
        imported_at = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                existing = connection.execute(
                    f"SELECT {digest_column}, imported_at FROM {table} "
                    f"WHERE {id_column} = ? AND {version_column} = ?",
                    (record_id, record_version),
                ).fetchone()
                if existing is not None and existing[0] == digest:
                    return DatabaseImportResult(
                        record_type=record_type,
                        record_id=record_id,
                        record_version=record_version,
                        sha256=digest,
                        action="unchanged",
                        imported_at=existing[1],
                    )
                action = "inserted" if existing is None else "updated"
                columns = (
                    id_column,
                    version_column,
                    *extra_columns,
                    digest_column,
                    "json_text",
                    "imported_at",
                )
                values = (
                    record_id,
                    record_version,
                    *extra_values,
                    digest,
                    json_text,
                    imported_at,
                )
                assignments = ", ".join(
                    f"{column} = excluded.{column}" for column in columns[2:]
                )
                placeholders = ", ".join("?" for _ in columns)
                connection.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) "
                    f"VALUES ({placeholders}) "
                    f"ON CONFLICT({id_column}, {version_column}) "
                    f"DO UPDATE SET {assignments}",
                    values,
                )
        return DatabaseImportResult(
            record_type=record_type,
            record_id=record_id,
            record_version=record_version,
            sha256=digest,
            action=action,
            imported_at=imported_at,
        )
