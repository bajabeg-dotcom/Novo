# Architecture

See `docs/PROJECT_GOAL.md` for purpose and source hierarchy first.

## Pipeline overview

```
IMPORT MIDI
   -> RAW PRESERVATION (hash original, never mutate)
   -> IDENTITY (instrument identity per Program Change/Bank Select segment)
   -> STRUCTURE (sections, roles: solo/bass/drums/chord/pad/etc.)
   -> MUSICAL ANALYSIS (Solo DNA, harmony, ornaments, trills, song layers)
   -> RX SAFETY (identity lock -> safety check, before any optimization)
   -> FACTORY DNA / GOLD DNA lookup
   -> OPTIMIZATION (deterministic, explainable, reversible)
   -> MUSICAL VALIDATION / RX VALIDATION / STRUCTURAL VALIDATION
   -> AUDIT TRAIL (every change logged: track/event/before/after/rule/reason/confidence/source)
   -> EXPORT (KORG-safe MIDI)
```

## Four knowledge layers

```
FACTORY EVIDENCE  -- what Korg factory MIDI actually contains (raw, per-file)
      |
FACTORY DNA       -- statistical/structural patterns found across evidence
      |
GOLD DNA          -- validated, generalized rules the engine may act on
      |
DECISION ENGINE   -- deterministic system that decides what may change
```

A rule may not skip layers: the Decision Engine only consults Gold DNA
(never raw Factory Evidence directly), and Gold DNA may only be
promoted from Factory DNA that is itself derived from real
(`source_kind=REAL`) evidence — see `docs/GOLD_DNA_SPECIFICATION.md`.

## Module -> responsibility -> owning vertical

| Module (`src/korg_optimizer/...`) | Responsibility | Vertical |
|---|---|---|
| `infrastructure/` | config, logging, hashing, source-of-truth tagging helpers, database connection/schema | A |
| `midi/` | raw import (immutable), normalized event model, MIDI writer, structural validators | A |
| `factory/` | Factory file discovery/ingestion, evidence extraction, synthetic vs. real dataset loaders | A |
| `audit/` | audit trail storage/query | A |
| `dna/` | Factory DNA extraction (rhythm, velocity, timing, melody, harmony, arrangement) | B |
| `gold/` | Gold DNA registry and promotion pipeline (Factory DNA -> Gold DNA) | B |
| `musical/` | instrument identity, Solo DNA, harmony/scale/chord analysis, ornament DNA, trill DNA | B |
| `mapping/` | GM -> RX mapping table and lookup | C |
| `rx/` | RX/DNC articulation model, RX safety engine | C |
| `optimizer/` | optimization engine, humanization, ornament/trill/harmony/delay generation (generative modes), change log | C |
| `validation/` | regression gates (P0/P1/P2), validation reports | C |
| `export/` | KORG-safe MIDI export | C |
| `gui/` | GUI (Safe Mode / Expert Mode / Generative Mode) | C |
| `cli.py`, `app.py` | shared entrypoints | C |

See `docs/VERTICAL_DECOMPOSITION.md` for exact path ownership used to
avoid collisions between parallel future work sessions.

## Allowed dependency direction

To keep the system explainable and prevent accidental coupling:

- `infrastructure`, `midi`, `factory` are foundational: they must not
  import from `dna`, `gold`, `musical`, `mapping`, `rx`, `optimizer`,
  `validation`, `export`, or `gui`.
- `dna` may depend on `midi`/`factory`/`infrastructure` only.
- `gold` may depend on `dna` and the layers below it.
- `musical` may depend on `gold`, `dna`, `midi`, `factory`, `infrastructure`.
- `mapping` and `rx` may depend on `gold`, `musical`, and the layers below.
- `optimizer` may depend on `rx`, `mapping`, `musical`, `dna`, `gold`,
  `midi`, `factory`, `infrastructure` — it is the layer that actually
  applies decisions.
- `validation` may depend on any of the above (it checks the result of
  everything).
- `export` depends on `midi` and `validation` results.
- `gui` and `cli.py` / `app.py` are the **only** modules allowed to
  call into `optimizer.engine` as an entrypoint — this is the
  CLI/GUI shared-engine contract below. Neither `gui` nor `cli.py` may
  contain optimizer logic of its own.

**Documented temporary exception**: `optimizer.engine` does not exist
yet (Phase 15). Until it does, `gui/analysis.py` calls `midi/` and
`factory/` directly for **read-only analysis only** — no mutation, no
DB writes, no claim of optimization. This is scoped narrowly (analysis
display only) precisely so it doesn't become a second, competing
decision path once the real optimizer is built — when `optimizer.engine`
lands, `gui/` must be updated to call it instead of `midi`/`factory`
directly for anything beyond this preview.

## CLI/GUI shared-engine contract

`optimizer/engine.py` defines the single call surface for running the
full pipeline (import -> ... -> export). `cli.py` and `gui/web_app.py`
(the active web GUI; `gui/main_window.py` remains an unused stub for a
possible future native desktop GUI) must both call this same engine —
they differ only in how they collect input and present output. No optimizer
decision logic may be duplicated or reimplemented in either the CLI or
GUI layer.

## Determinism and no-silent-mutation principles

- Default optimizer behavior is deterministic: no randomness, no
  unsupported RX activation, no unproven sound swaps.
- If humanization is used, it must be reproducible (e.g. seeded).
- Every mutation must produce an audit entry: track, event, before,
  after, rule, reason, confidence, source. No exceptions.
- When evidence is insufficient to justify a change, the system must
  preserve the original rather than generate — see spec principle:
  "PRESERVATION OVER UNSAFE GENERATION."
