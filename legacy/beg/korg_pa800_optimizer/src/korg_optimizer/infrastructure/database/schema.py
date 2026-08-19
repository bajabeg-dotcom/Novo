"""evidence.db and knowledge.db schema (DDL).

evidence.db (EVIDENCE_DB_DDL) is owned exclusively by Vertical A.
knowledge.db (KNOWLEDGE_DB_DDL: factory_dna, gold_dna) is owned by
Vertical B (factory_dna, gold_dna) per docs/DATABASE_ARCHITECTURE.md
"Ownership / write access per Vertical" -- added here directly (rather
than as a migrations/ proposal file) because this session implements
both verticals' work; see
infrastructure/database/migrations/vertical_b_knowledge_db.sql for the
change recorded in the normal proposal format regardless. runtime.db
remains undefined (Vertical C, Phase 15+).

Other verticals propose further changes as migration files under
infrastructure/database/migrations/, never by editing this file
directly. See docs/VERTICAL_DECOMPOSITION.md and
docs/DATABASE_ARCHITECTURE.md for the full schema and rationale.

Owning vertical: A (evidence.db), B (knowledge.db).
"""

from __future__ import annotations

EVIDENCE_DB_SCHEMA_VERSION = 1
KNOWLEDGE_DB_SCHEMA_VERSION = 1

EVIDENCE_DB_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER NOT NULL,
        applied_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_files (
        id              INTEGER PRIMARY KEY,
        file_path       TEXT NOT NULL UNIQUE,
        sha256_hash     TEXT NOT NULL,
        source_kind     TEXT NOT NULL CHECK (source_kind IN ('SYNTHETIC', 'REAL')),
        format          TEXT NOT NULL DEFAULT 'mid',
        imported_at     TEXT NOT NULL,
        parser_version  TEXT NOT NULL,
        byte_size       INTEGER NOT NULL,
        notes           TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_files_hash ON source_files(sha256_hash)",
    """
    CREATE TABLE IF NOT EXISTS factory_evidence (
        id                      INTEGER PRIMARY KEY,
        source_file_id          INTEGER NOT NULL REFERENCES source_files(id),
        track_index             INTEGER,
        style_name               TEXT,
        style_section             TEXT,
        section_evidence_level    TEXT CHECK (section_evidence_level IN ('CONFIRMED', 'INFERRED', 'UNKNOWN')),
        event_summary_json       TEXT NOT NULL,
        extracted_at             TEXT NOT NULL,
        extractor_version        TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_factory_evidence_source ON factory_evidence(source_file_id)",
    """
    CREATE TABLE IF NOT EXISTS golden_files (
        id           INTEGER PRIMARY KEY,
        file_path    TEXT NOT NULL UNIQUE,
        sha256_hash  TEXT NOT NULL,
        byte_size    INTEGER NOT NULL,
        imported_at  TEXT NOT NULL,
        notes        TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_golden_files_hash ON golden_files(sha256_hash)",
]

# knowledge.db: derived/rebuildable from evidence.db (Factory DNA, Gold
# DNA). See docs/DATABASE_ARCHITECTURE.md for the grouping-key columns
# (style_section/channel/channel_b), metrics_json convention, and
# full-rebuild semantics (dna.extraction.extract_and_save and
# gold.promotion.promote_all both DELETE + re-INSERT their table on
# every run -- this is not an append-only evidence store).
KNOWLEDGE_DB_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER NOT NULL,
        applied_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS factory_dna (
        id                          INTEGER PRIMARY KEY,
        rule_id                     TEXT NOT NULL UNIQUE,
        category                    TEXT NOT NULL,
        style_section               TEXT,
        channel                     INTEGER,
        channel_b                   INTEGER,
        metrics_json                TEXT NOT NULL,
        derived_from_evidence_ids   TEXT NOT NULL,
        source_kind_composition     TEXT NOT NULL,
        occurrence_count            INTEGER NOT NULL,
        confidence                  REAL NOT NULL,
        computed_at                 TEXT NOT NULL,
        extractor_version           TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_factory_dna_category ON factory_dna(category)",
    "CREATE INDEX IF NOT EXISTS idx_factory_dna_section_channel ON factory_dna(style_section, channel)",
    """
    CREATE TABLE IF NOT EXISTS gold_dna (
        id                            INTEGER PRIMARY KEY,
        rule_id                       TEXT NOT NULL UNIQUE,
        category                      TEXT NOT NULL,
        source_count                  INTEGER NOT NULL,
        occurrence_count              INTEGER NOT NULL,
        confidence                    REAL NOT NULL,
        evidence_level                TEXT NOT NULL CHECK (evidence_level IN ('CONFIRMED', 'INFERRED', 'UNKNOWN')),
        supporting_examples           TEXT NOT NULL,
        contradicting_examples        TEXT NOT NULL,
        promoted_from_factory_dna_id  INTEGER REFERENCES factory_dna(id),
        promoted_at                   TEXT,
        promotion_blocked_reason      TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_gold_dna_category ON gold_dna(category)",
]
