# Database Architecture

Storage engine: SQLite. Rationale for consolidation into **three**
physical database files rather than one-per-logical-layer (the spec
explicitly warns against making 15 databases just because it's
possible, §45):

| Database | Nature | Owner (writes) |
|---|---|---|
| `evidence.db` | Append-only, immutable once written | Vertical A |
| `knowledge.db` | Derived/rebuildable from evidence.db at any time | Vertical B (dna/gold/musical tables), Vertical C (mapping/rx tables) |
| `runtime.db` | Per-run, mutable, gitignored | Vertical C (writes), Vertical A (owns table definitions since it owns `infrastructure/database/schema.py`) |

This split follows the actual lifecycle difference between the data:
evidence must never be edited after import (raw preservation
guarantee); knowledge is a rebuildable projection of evidence plus
validated rules (so it can be dropped and regenerated); runtime data is
disposable per optimization run and must never be mistaken for
evidence or knowledge.

Raw MIDI bytes are stored **on the filesystem, not as DB blobs**
(`data/factory/{synthetic,real}/...`), referenced by path + SHA-256
hash in `evidence.db`. This keeps the "raw preservation" guarantee
transparent and inspectable outside the database, and avoids DB bloat.

## `evidence.db`

```sql
CREATE TABLE source_files (
    id              INTEGER PRIMARY KEY,
    file_path       TEXT NOT NULL UNIQUE,
    sha256_hash     TEXT NOT NULL,
    source_kind     TEXT NOT NULL CHECK (source_kind IN ('SYNTHETIC', 'REAL')),
    format          TEXT NOT NULL DEFAULT 'mid',
    imported_at     TEXT NOT NULL,
    parser_version  TEXT NOT NULL,
    byte_size       INTEGER NOT NULL,
    notes           TEXT
);

CREATE TABLE factory_evidence (
    id                      INTEGER PRIMARY KEY,
    source_file_id          INTEGER NOT NULL REFERENCES source_files(id),
    track_index             INTEGER,        -- NULL for the file-level summary row
    style_name               TEXT,           -- parent directory name, verbatim; NULL for non-Style evidence
    style_section             TEXT,           -- one of Break/End1-3/Fill1-2/Intro1-3/Var1-4, or NULL
    section_evidence_level    TEXT CHECK (section_evidence_level IN ('CONFIRMED', 'INFERRED', 'UNKNOWN')),
    event_summary_json       TEXT NOT NULL,
    extracted_at             TEXT NOT NULL,
    extractor_version        TEXT NOT NULL
);

CREATE INDEX idx_factory_evidence_source ON factory_evidence(source_file_id);

CREATE TABLE golden_files (
    id           INTEGER PRIMARY KEY,
    file_path    TEXT NOT NULL UNIQUE,
    sha256_hash  TEXT NOT NULL,
    byte_size    INTEGER NOT NULL,
    imported_at  TEXT NOT NULL,
    notes        TEXT
);

CREATE INDEX idx_golden_files_hash ON golden_files(sha256_hash);

CREATE TABLE schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT NOT NULL
);
```

`source_kind` is `NOT NULL` and constrained by `CHECK` — there is no
way to insert a row without declaring synthetic vs. real. See
`docs/GOLD_DNA_SPECIFICATION.md` for how this propagates into the
Gold DNA promotion gate.

**`factory_evidence` row shape**: one row per track (`track_index` =
0..N-1) carrying that track's raw facts (channel, note count,
pitch/velocity range, CC numbers used, raw program changes, sysex
count, track name — no GM/RX interpretation, that belongs to Vertical
C's Instrument Identity/RX work, Phase 7-8), plus one additional
file-level row (`track_index = NULL`) carrying `style_name`/
`style_section`/`section_evidence_level` and an aggregate summary
(format, ppq, track count, channels used, duration). Section is
derived from the **filename**, not MIDI content, since KORG Style
Element exports encode it that way (`<StyleName>_<Section>.mid`) — see
`docs/MIDI_MODEL.md` for the parsing rule and its one documented
real-data quirk (filename/directory-name mismatches, recorded raw via
an `event_summary_json.style_name_filename_mismatch` flag, never
guessed at or corrected).

**`golden_files`** is a deliberately separate, minimal manifest table
for Golden Dataset material (`data/golden/songs/`) — full-band live
performance recordings, structurally distinct from Factory Style
evidence. It is **not** `source_files` (whose `source_kind` CHECK
constraint can only represent `SYNTHETIC`/`REAL` Factory material, not
this) and it carries no `evidence_level` — it makes no musical claims,
it only catalogs what's on disk (path, hash, size). See
`docs/PROJECT_GOAL.md` decisions log and
`docs/VERTICAL_DECOMPOSITION.md` for the `data/golden/**` ownership
assignment. Per-file curation (GOOD/EDGE_CASE/CONFIRMED_* tagging, per
`data/golden/README.md`) is deferred to Vertical B, Phase 9+.

## `knowledge.db`

```sql
CREATE TABLE factory_dna (
    id                          INTEGER PRIMARY KEY,
    rule_id                     TEXT NOT NULL UNIQUE,
    category                    TEXT NOT NULL,   -- rhythm|velocity|timing|arrangement (melody|harmony reserved, unpopulated -- see Solo DNA/Harmony, Phase 9-10)
    style_section               TEXT,            -- grouping key: one of the 13 Style Element section tokens, or NULL for ungrouped
    channel                     INTEGER,         -- grouping key: raw 0-indexed MIDI channel; NULL for section-only rows
    channel_b                   INTEGER,         -- grouping key: second channel, layer_interaction pair rows only; else NULL
    metrics_json                TEXT NOT NULL,   -- computed statistics, category-specific shape -- see docs/GOLD_DNA_MODEL.md
    derived_from_evidence_ids   TEXT NOT NULL,   -- JSON array of factory_evidence.id
    source_kind_composition     TEXT NOT NULL,   -- JSON, e.g. {"REAL": 42, "SYNTHETIC": 0}
    occurrence_count            INTEGER NOT NULL,
    confidence                  REAL NOT NULL,
    computed_at                 TEXT NOT NULL,
    extractor_version           TEXT NOT NULL
);

CREATE INDEX idx_factory_dna_category ON factory_dna(category);
CREATE INDEX idx_factory_dna_section_channel ON factory_dna(style_section, channel);

CREATE TABLE gold_dna (
    id                          INTEGER PRIMARY KEY,
    rule_id                     TEXT NOT NULL UNIQUE,
    category                    TEXT NOT NULL,
    source_count                INTEGER NOT NULL,
    occurrence_count            INTEGER NOT NULL,
    confidence                  REAL NOT NULL,
    evidence_level              TEXT NOT NULL CHECK (evidence_level IN ('CONFIRMED', 'INFERRED', 'UNKNOWN')),
    supporting_examples         TEXT NOT NULL,   -- JSON
    contradicting_examples      TEXT NOT NULL,   -- JSON
    promoted_from_factory_dna_id INTEGER REFERENCES factory_dna(id),
    promoted_at                 TEXT,
    promotion_blocked_reason    TEXT             -- NULL unless promotion was rejected (e.g. synthetic evidence, below threshold)
);

CREATE INDEX idx_gold_dna_category ON gold_dna(category);

CREATE TABLE rx_articulations (
    id                  INTEGER PRIMARY KEY,
    canonical_name      TEXT NOT NULL,
    category            TEXT NOT NULL,
    instrument          TEXT,
    trigger_type        TEXT NOT NULL,  -- keyswitch|cc|velocity_range|nrpn|rpn|sysex
    trigger_value_json  TEXT NOT NULL,
    korg_model          TEXT NOT NULL DEFAULT 'PA800',
    evidence_level      TEXT NOT NULL CHECK (evidence_level IN ('CONFIRMED', 'INFERRED', 'UNKNOWN')),
    source_document_ref TEXT
);

CREATE TABLE gm_rx_mapping (
    id                       INTEGER PRIMARY KEY,
    gm_msb                   INTEGER,
    gm_lsb                   INTEGER,
    gm_program               INTEGER NOT NULL,
    factory_target           TEXT,
    rx_target_id             INTEGER REFERENCES rx_articulations(id),
    confidence               REAL NOT NULL,
    evidence_level           TEXT NOT NULL CHECK (evidence_level IN ('CONFIRMED', 'INFERRED', 'UNKNOWN')),
    instrument_identity_json TEXT
);

-- musical_* tables (instrument identity, solo/harmony/ornament/trill DNA)
-- share the same evidence_level + provenance discipline; exact columns
-- are defined by Vertical B per docs/SOLO_SPECIFICATION.md,
-- docs/ORNAMENT_SPECIFICATION.md, docs/TRILL_SPECIFICATION.md when that
-- work begins (Phase 9-14). Not created yet.
```

**`factory_dna` grouping keys**: since no instrument identity exists yet
(Phase 7), rows are grouped only by structural facts that are already
CONFIRMED — the filename-derived `style_section` and the raw 0-indexed
MIDI `channel` (never by any assumed instrument role). Two shapes:
- **Group A** `(style_section, channel)` — e.g. "what does a typical
  `Var1`-section channel-11 track look like across the whole corpus."
  Used by `rhythm`, `velocity`, `timing`, and `arrangement`'s
  `channel_profile` sub-category (`channel_b` NULL).
- **Group A′** `(style_section, channel, channel_b)`, canonical
  `channel < channel_b` — `arrangement`'s `layer_interaction`
  sub-category only (co-activity between a channel pair).
- **Group B** `style_section` alone (`channel`/`channel_b` both NULL) —
  `arrangement`'s `section_behavior` sub-category (e.g. "how does
  `Break` differ from `Var1` structurally," not channel-specific).

**`metrics_json` convention**: multiple related sub-metrics for one
`(category, group)` are bundled into a single row rather than one row
per sub-metric (e.g. one `rhythm` row for `Var1`/ch11 carries density,
subdivision, syncopation, swing, and groove together) — this keeps
`occurrence_count`/`confidence`/`derived_from_evidence_ids` meaningful
as *one* rule about *one* pattern, and avoids a 5x row-count explosion.
`arrangement` rows additionally carry `metrics_json.sub_category`
(`"channel_profile"` | `"layer_interaction"` | `"section_behavior"`)
to discriminate its three grouping shapes without extra columns. Exact
per-category metric fields and their formulas are documented in
`docs/GOLD_DNA_MODEL.md` (kept there, not here, since they're a
statistical/modeling concern rather than a storage concern).

**Full-rebuild semantics**: unlike `evidence.db` (append-only,
immutable), `knowledge.db` is explicitly *derived and rebuildable* —
`dna.extraction.extract_and_save` and `gold.promotion.promote_all` each
`DELETE FROM <table>` then re-`INSERT` on every run. A `UNIQUE(rule_id)`
violation during a rebuild indicates a bug (duplicate group key), not a
legitimate update path.

**Known limitation, not yet fixed**: `evidence.db` and `knowledge.db`
currently share one hardcoded `SCHEMA_VERSION` default in
`infrastructure/database/connection.ensure_schema` unless the caller
passes `schema_version=` explicitly (which `dna`/`gold` code does, via
`KNOWLEDGE_DB_SCHEMA_VERSION`) — both happen to be version `1` today,
so this works, but the two schemas' versions are independent going
forward and must each be bumped and passed explicitly when either
changes.

## `runtime.db`

```sql
CREATE TABLE optimization_runs (
    id                  INTEGER PRIMARY KEY,
    input_file_hash     TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    engine_version      TEXT NOT NULL,
    mode                TEXT NOT NULL CHECK (mode IN ('SAFE', 'GENERATIVE')),
    deterministic_seed  TEXT
);

CREATE TABLE change_log (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES optimization_runs(id),
    track       INTEGER NOT NULL,
    event_index INTEGER NOT NULL,
    before_json TEXT NOT NULL,
    after_json  TEXT NOT NULL,
    rule_id     TEXT NOT NULL,
    reason      TEXT NOT NULL,
    confidence  REAL NOT NULL,
    source      TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);

CREATE TABLE audit_trail (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES optimization_runs(id),
    action      TEXT NOT NULL,   -- e.g. PRESERVE, APPLY, BLOCK
    actor       TEXT NOT NULL,
    before_hash TEXT,
    after_hash  TEXT,
    timestamp   TEXT NOT NULL
);

CREATE TABLE validation_results (
    id           INTEGER PRIMARY KEY,
    run_id       INTEGER NOT NULL REFERENCES optimization_runs(id),
    gate_name    TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'SKIP')),
    is_p0        INTEGER NOT NULL DEFAULT 0,
    details_json TEXT
);
```

`runtime.db` files live under `data/databases/` and are gitignored —
they are disposable per run, unlike `evidence.db` (never regenerate
without re-import) and `knowledge.db` (regenerable from evidence, but
treated as a checked-in build artifact once real evidence exists).

## Ownership / write access per Vertical

| Table group | Written by |
|---|---|
| `source_files`, `factory_evidence`, `golden_files` | Vertical A only |
| `factory_dna`, musical_* tables | Vertical B only |
| `gold_dna` | Vertical B (promotion logic), read by C |
| `rx_articulations`, `gm_rx_mapping` | Vertical C only |
| `optimization_runs`, `change_log` | Vertical C (written during optimization) |
| `audit_trail` | Vertical A's `audit/trail.py` module (storage), populated via calls from Vertical C |
| `validation_results` | Vertical C |

`infrastructure/database/schema.py` (table DDL) is owned by Vertical A.
Other verticals never edit it directly — they propose additions as
migration files under `infrastructure/database/migrations/`, which
Vertical A (or whoever is acting as integration coordinator for that
session) reviews and merges. See `docs/VERTICAL_DECOMPOSITION.md`.

## Integrity requirements (future phases, recorded now)

- Foreign keys enforced (`PRAGMA foreign_keys = ON`).
- Indexes on all foreign key columns and on `sha256_hash`.
- Unique constraints as shown above (`file_path`, `rule_id`).
- Schema version tracked in the `schema_version` table — implemented as
  of `evidence.db`'s initial schema (version 1), inserted once by
  `infrastructure/database/connection.ensure_schema`.
- Import must be idempotent: re-importing a `SourceFile` with an
  already-seen hash must be a no-op, not a duplicate row. If a
  previously-imported path's content hash has changed, this is treated
  as an integrity violation (`EvidenceIntegrityError`), not a silent
  update — `evidence.db` is append-only/immutable, so a changed file at
  an already-imported path means the source was edited or replaced
  after import.

## Status

`evidence.db` (schema above) is implemented:
`source_files`, `factory_evidence`, `golden_files`, and
`schema_version` are created by
`infrastructure/database/schema.py`/`connection.py` and populated by
`factory/real_dataset.py`, `factory/synthetic_dataset.py`, and
`infrastructure/golden_dataset.py`.

`knowledge.db`'s `factory_dna` and `gold_dna` tables are now
implemented too: `factory_dna` is populated by
`dna/extraction.extract_and_save` (run against the real Factory Style
corpus in `evidence.db`), and `gold_dna` by
`gold/promotion.promote_all`. `rx_articulations`, `gm_rx_mapping`, and
the `musical_*` tables remain undefined (Vertical C/B, Phase 7-14).
`runtime.db` remains entirely undefined (Vertical C, Phase 15+).
