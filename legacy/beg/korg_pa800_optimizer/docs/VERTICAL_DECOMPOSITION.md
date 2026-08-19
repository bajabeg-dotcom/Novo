# Vertical Decomposition

## Purpose

This document exists so that future sessions can parallelize real
implementation work (Phase 1 onward, per `docs/ROADMAP.md`) across
multiple Claude Code Agent-tool subagents — one per vertical — with
zero path collisions. There is no external multi-agent "Coordinator"
tool available in this repository; parallel work is realized by
spawning one subagent per vertical via Claude Code's own Agent tool,
each briefed with this document and given a complete vertical goal
(not a list of small tasks).

## Vertical ownership

| Vertical | Exclusive write paths | Docs owned |
|---|---|---|
| **A — Core / MIDI / Database / Factory** | `src/korg_optimizer/infrastructure/**`, `src/korg_optimizer/midi/**`, `src/korg_optimizer/factory/**`, `src/korg_optimizer/audit/**`, `data/factory/**`, `data/golden/**` (cataloging only -- see below), `tests/unit/infrastructure/**`, `tests/unit/midi/**`, `tests/unit/factory/**`, `tests/fixtures/synthetic/**` | `docs/DATA_MODEL.md`, `docs/DATABASE_ARCHITECTURE.md`, `docs/MIDI_MODEL.md` |
| **B — Musical Intelligence** | `src/korg_optimizer/dna/**`, `src/korg_optimizer/gold/**`, `src/korg_optimizer/musical/**`, `tests/unit/dna/**`, `tests/unit/gold/**`, `tests/unit/musical/**`, `tests/fixtures/trills/**`, `tests/fixtures/ornaments/**`, `tests/fixtures/solo/**`, `tests/fixtures/harmony/**` | `docs/GOLD_DNA_MODEL.md`, `docs/GOLD_DNA_SPECIFICATION.md`, `docs/SOLO_SPECIFICATION.md`, `docs/SONG_LAYER_SPECIFICATION.md`, `docs/ORNAMENT_SPECIFICATION.md`, `docs/TRILL_SPECIFICATION.md` |
| **C — RX / Optimizer / Validation / GUI** | `src/korg_optimizer/mapping/**`, `src/korg_optimizer/rx/**`, `src/korg_optimizer/optimizer/**`, `src/korg_optimizer/validation/**`, `src/korg_optimizer/export/**`, `src/korg_optimizer/gui/**`, `tests/unit/rx/**`, `tests/unit/optimizer/**`, `tests/unit/validation/**`, `tests/unit/export/**`, `tests/regression/**`, `hardware-tests/**` | `docs/RX_MODEL.md`, `docs/RX_SPECIFICATION.md`, `docs/VALIDATION_SPECIFICATION.md`, `docs/HARDWARE_TEST_SPECIFICATION.md` |

**Self-check performed**: the path lists above are pairwise disjoint —
no directory is listed under two verticals.

**`data/golden/**` note (added 2026-08-11)**: this was a genuine
ownership gap in the original table — Golden Dataset material (real
song/performance recordings, e.g. `data/golden/songs/`) is neither
Factory Style evidence (`factory/`) nor a validated Gold DNA rule
(`gold/`, Vertical B's promotion-pipeline territory). It's assigned to
Vertical A for **cataloging only** (hash + manifest via
`infrastructure/golden_dataset.py`, storing into the `golden_files`
table — see `docs/DATABASE_ARCHITECTURE.md`). Musical analysis and
per-file tagging (GOOD/EDGE_CASE/CONFIRMED_*) of this material remains
Vertical B's, Phase 9+ — this note does not grant Vertical A any claim
over `gold/**` or musical-DNA extraction from Golden material.

## Coordinator-only / shared files (no vertical owns these directly)

- `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/PROJECT_GOAL.md`,
  `docs/TEST_STRATEGY.md`, this file — edited only by whoever is acting
  as integration coordinator for a given session, after reading current
  content.
- `src/korg_optimizer/infrastructure/database/schema.py` — owned by
  Vertical A. Other verticals never edit it directly; they add proposed
  DDL as new files under `infrastructure/database/migrations/
  vertical_b_*.sql` / `vertical_c_*.sql` for the coordinator (or
  Vertical A) to review and fold in.
- `korg_pa800_optimizer/pyproject.toml` dependencies — each vertical
  proposes additions via its own `requirements/vertical_{a,b,c}.txt`
  fragment (create this directory when first needed); the coordinator
  merges into `pyproject.toml`.
- `src/korg_optimizer/__init__.py` (package version) — coordinator-only.
- Cross-vertical data contracts — e.g. `midi/normalized_model.py`'s
  track/event shape (defined by A, consumed by B and C) and
  `optimizer/change_log.py`'s record shape (defined by C, consumed by
  A's `audit/trail.py` for storage). The defining vertical owns the
  file; other verticals import/consume it but do not modify it.
  Disagreements go through the coordinator, not direct edits to a file
  another vertical owns.

## Sequencing for future sessions

1. This Phase 0-1 skeleton must be committed first — it is the
   contract all verticals build against.
2. Vertical A goes first for real implementation work, since B and C
   both depend on its `midi`/`factory`/`infrastructure` primitives
   (normalized MIDI model, database connection/schema, evidence
   ingestion).
3. Once A's primitives exist and are merged, B and C may run
   concurrently, each as its own Agent-tool subagent / branch.
4. Before merging concurrent work, check path overlap against the
   ownership table above (e.g. `git diff --stat`) — any file outside a
   vertical's declared ownership is a collision to resolve before
   merge, not after.

## Collision handling

If two sessions genuinely need to touch the same file (a Coordinator-
only file, or a cross-vertical contract file under active
renegotiation): re-read the file's current content before editing,
make the smallest patch that achieves the goal, never blindly overwrite
the other side's change, and never use a destructive merge. If a real
hunk-level collision is found, pause and resolve it explicitly rather
than picking a side silently.

## Per-vertical test scope

Each vertical runs its own `tests/unit/<owned>/**` subtree plus a
shared "does everything still import cleanly" smoke check
(`python -c "import korg_optimizer"` and equivalent per-subpackage
imports) before considering its work session complete.
