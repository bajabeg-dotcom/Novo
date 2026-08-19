-- Vertical B proposal: initial knowledge.db schema (factory_dna, gold_dna).
--
-- Applied directly into infrastructure/database/schema.py's
-- KNOWLEDGE_DB_DDL (rather than left as a pending file) because this
-- session implements both Vertical A's schema.py and Vertical B's
-- dna/gold modules together -- recorded here in the normal
-- migration-proposal format anyway, per docs/VERTICAL_DECOMPOSITION.md.
--
-- See docs/DATABASE_ARCHITECTURE.md for the authoritative schema,
-- rationale for the style_section/channel/channel_b grouping-key
-- columns, the metrics_json convention, and full-rebuild semantics.

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT NOT NULL
);

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
);

CREATE INDEX IF NOT EXISTS idx_factory_dna_category ON factory_dna(category);
CREATE INDEX IF NOT EXISTS idx_factory_dna_section_channel ON factory_dna(style_section, channel);

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
);

CREATE INDEX IF NOT EXISTS idx_gold_dna_category ON gold_dna(category);
