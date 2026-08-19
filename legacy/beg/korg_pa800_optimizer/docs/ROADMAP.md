# Roadmap

## Phase order

This is the authoritative 21-phase implementation order (source: the
project's master specification, "Implementation Order" section).
Phases are numbered independently of the pre-implementation Discovery
work described in `docs/PROJECT_GOAL.md` / this Phase 0-1 skeleton,
which precedes Phase 0 conceptually but is tracked as "Phase 0-1" work
in this repository's history for simplicity.

| # | Phase |
|---|---|
| 0 | Project bootstrap |
| 1 | MIDI Core |
| 2 | Database architecture |
| 3 | Factory ingestion |
| 4 | Factory Evidence |
| 5 | Factory DNA |
| 6 | Gold DNA |
| 7 | Instrument Identity |
| 8 | RX/DNC engine |
| 9 | Solo DNA |
| 10 | Harmony |
| 11 | Song Layer |
| 12 | Ornament Mining |
| 13 | Trill Mining |
| 14 | Guitar/Strumming |
| 15 | Optimizer |
| 16 | Validation |
| 17 | GUI |
| 18 | CLI |
| 19 | Hardware Test Framework |
| 20 | Full integration |
| 21 | Release certification |

## Phase-gate rule

**Do not advance to the next phase just because code exists for it.**
Each phase must be:

- **IMPLEMENTED** — working code exists
- **TESTED** — unit + relevant integration/regression tests pass
- **DOCUMENTED** — the relevant doc(s) in `docs/` reflect what was
  actually built, not just what was planned
- **AUDITED** — reviewed against the source-of-truth hierarchy and
  no-invented-data rule in `docs/PROJECT_GOAL.md`

A phase that is merely "implemented" is not done.

## Current status

- **Phase 0 (Project bootstrap)**: IMPLEMENTED, DOCUMENTED. Directory
  skeleton, `pyproject.toml`, package installs in isolation.
- **Phase 1 (MIDI Core)**: IMPLEMENTED, TESTED, DOCUMENTED. `midi/`
  (raw import, normalized model, writer, validators) built on `mido`;
  round-trip test passes against real format-0 and format-1 samples.
  See `docs/MIDI_MODEL.md` "Status".
- **Phase 2 (Database architecture)**: IMPLEMENTED, TESTED, DOCUMENTED.
  `evidence.db` schema (`source_files`, `factory_evidence`,
  `golden_files`, `schema_version`) created and idempotent; FK
  enforcement and constraints verified by tests. `knowledge.db` /
  `runtime.db` remain undefined (Vertical B/C, Phase 5+). See
  `docs/DATABASE_ARCHITECTURE.md` "Status".
- **Phase 3 (Factory ingestion)**: IMPLEMENTED, TESTED. Real Factory
  Style corpus (3211 files) and Golden Dataset (182 files) ingested;
  re-running ingestion is idempotent (verified against the full real
  corpus, not just test fixtures); a changed hash at an
  already-imported path raises `EvidenceIntegrityError` rather than
  silently updating.
- **Phase 4 (Factory Evidence)**: IMPLEMENTED, TESTED. Per-track and
  file-level evidence extraction, including filename-derived
  style/section parsing with the documented mismatch-flag behavior
  (208 of 3211 real files). Not yet independently AUDITED by a
  separate review pass.
- **Phase 5 (Factory DNA)**: IMPLEMENTED, TESTED. `dna/extraction.py`
  computes Rhythm, Velocity, Timing, and Arrangement DNA (density,
  subdivision, syncopation, swing, groove, velocity distribution/
  accents/dynamic contour, note duration/gate ratio, channel activity
  ratio, channel-pair co-activity, per-section aggregate behavior) from
  the real Factory Style corpus, grouped only by structural
  already-CONFIRMED facts (filename-derived section, raw MIDI channel
  — no instrument identity exists yet, Phase 7). Melody DNA and true
  Harmony DNA deferred to Solo DNA (Phase 9) / Harmony (Phase 10). Run
  against the full real 3211-file corpus in ~29s: 793 `factory_dna`
  rows, confidence range 0.01-0.86 (median ~0.65). Not yet
  independently AUDITED.
- **Phase 6 (Gold DNA)**: IMPLEMENTED, TESTED. `gold/promotion.py`
  evaluates every `factory_dna` row (synthetic-exclusion gate +
  size/consistency thresholds, tiered by category — see
  `docs/GOLD_DNA_SPECIFICATION.md`), `gold/gold_dna.py` stores one
  `gold_dna` row per evaluated candidate (row-per-attempt semantics,
  full auditability), `gold/registry.py` exposes only genuinely
  promoted rules. Run against the real Factory DNA above: 476 of 793
  candidates promoted (0 blocked by the synthetic gate — extraction
  only ever sources `REAL` evidence — 317 blocked by threshold). Not
  yet independently AUDITED.
- **Phase 7+ (Instrument Identity onward)**: not started -- Vertical C
  territory, all modules remain docstring stubs. This includes
  **Phase 15 (Optimizer)**: there is no GM→RX mapping, RX safety
  engine, or optimization logic anywhere in this codebase yet.
- **Phase 17 (GUI) — partially started, out of order, scope-limited.**
  A local web GUI (`gui/web_app.py`, Flask) exists: upload a `.mid`
  file, see structural validation and raw per-track/file-level facts
  via the already-implemented Phase 1-4 pipeline. It deliberately has
  **no "Optimize" action** — Phase 15 doesn't exist yet, and giving the
  GUI a button that doesn't do what it says would violate
  `docs/PROJECT_GOAL.md`'s no-invented-behavior rule. This GUI work was
  pulled forward (out of the normal 0→21 order) at the user's explicit
  request for an inspectable, runnable deliverable at this stage; it
  does not change the phase-gate rule for Phase 15 itself, which still
  requires real Gold DNA/RX/mapping work before an "Optimize" action
  can honestly exist.

Real data now backing this work: `data/factory/real/Workspace_Styles/`
(3211 real KORG Factory Style `.mid` files) and `data/golden/songs/`
(182 real live-performance `.mid` recordings, catalogued but not yet
analyzed) -- see `docs/PROJECT_GOAL.md` "Evidence status".

## What blocks Phase 7+ from starting productively

Nothing structural -- real Gold DNA now exists in `knowledge.db` for
Vertical C to build Instrument Identity (Phase 7) and the GM->RX
mapping/RX Safety Engine (Phase 8) against, once it's ready to
interpret Program Change values (deliberately left raw/uninterpreted
by Phase 4/5). Golden Dataset material (`data/golden/songs/`) is
catalogued but not yet musically analyzed or tagged
(GOOD/EDGE_CASE/CONFIRMED_*) -- that tagging work is part of Phase 9+
once Solo/Harmony/Ornament/Trill DNA modules exist to do it.
