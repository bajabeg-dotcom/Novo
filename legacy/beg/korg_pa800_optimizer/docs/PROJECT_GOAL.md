# Project Goal

## Purpose

Build a KORG PA800-specific, deterministic musical intelligence system
that can take a General MIDI file, understand it musically and
structurally, and produce a KORG-optimized MIDI file that makes safe,
evidence-based use of the PA800's RX/DNC articulations — without ever
guessing at Korg-specific behavior it cannot prove.

This is explicitly **not**:
- a generic MIDI editor,
- a MIDI humanizer that applies generic randomized "feel",
- an AI system that mutates MIDI based on its own unverified judgment.

It **is** an evidence-based decision system: every transformation it
applies must be traceable to a rule, the rule must be traceable to
evidence, and the evidence must be traceable to a source whose
authority is known (see Source Hierarchy below).

## Problem statement

General MIDI (GM) files do not know anything about the KORG PA800's
RX/DNC articulation layer (slides, noise, hammer-ons, mutes, and other
instrument-specific playing techniques triggered by velocity ranges,
key switches, or controller values on specific PA800 sound programs).
Naively remapping GM programs to PA800 sounds, or humanizing velocity
and timing without awareness of RX triggers, risks:
- activating articulations the arranger never intended,
- destroying deliberately-programmed structure (existing solos,
  harmonized "Terca" tracks, delay tracks),
- producing output that sounds wrong or breaks on real hardware in ways
  that are invisible in software.

The optimizer's job is to close this gap safely: identify what is
actually GM-safe to change, identify what must be preserved, and only
apply RX-aware, musically-validated, explainable transformations.

## Relationship to other packages in this repository

| Package | Relationship |
|---|---|
| `src/factory_intelligence/` | Separate, untouched. A read-only Factory MIDI *analysis* layer using a synthetic (seed=42) test dataset. No code sharing, no shared runtime or database. May be referenced for design ideas only. |
| `x10_think_midi/` | Separate, untouched. A rule-based MIDI humanization/articulation engine with its own GUI, engines, and persistence. No code sharing. Its RX/articulation engine design may inform discussion but is not imported. |

`korg_pa800_optimizer/` is a fully independent Python package: its own
`pyproject.toml`, its own `src/korg_optimizer/` source tree, its own
databases, its own tests. Nothing here imports from, and nothing
outside this directory imports from, `korg_optimizer`.

## Source-of-truth hierarchy

When two sources disagree, the **higher authority always wins**, and a
lower-authority source may never override a higher one:

1. Physical PA800 Evidence (actual hardware behavior, observed and logged)
2. Official KORG Documentation
3. Factory MIDI / Style Evidence (real Korg factory `.mid` content — see note below)
4. Factory-derived DNA (statistical/structural patterns extracted from #3)
5. Gold DNA (validated, generalized rules promoted from #4)
6. Explicitly marked Inference

Every fact the system stores or reports must be tagged one of:
`CONFIRMED` (direct evidence), `INFERRED` (reasoned but not directly
evidenced), or `UNKNOWN` (no basis — must not be acted on as fact).
Nothing Korg-specific (RX address, Program Change, Bank Select, CC,
NRPN, RPN, SysEx, articulation trigger, key switch, velocity zone,
factory sound mapping, or hardware behavior) may ever be invented.

## Evidence status: synthetic vs. real Factory data

**Real Factory Evidence now exists.** As of 2026-08-11, the user
supplied two real KORG PA800 datasets, verified and ingested:

1. **Real Factory Style evidence** (3211 `.mid` files, 248 styles,
   `data/factory/real/Workspace_Styles/<StyleName>/<StyleName>_<Section>.mid`)
   — real KORG Style Element exports (format 1, channels 9-16, section
   encoded in filename per KORG's own export convention). This is the
   real Factory Evidence source for Factory DNA / Gold DNA once
   Vertical B's Phase 5-6 work begins.
2. **Golden Dataset material** (182 `.mid` files,
   `data/golden/songs/`) — real full-band live-performance recordings
   (format 0, single track, all 16 channels interleaved). Explicitly
   **not** Factory Evidence and **not** written to the `gold_dna`
   table — see the decisions log below and
   `docs/DATABASE_ARCHITECTURE.md` `golden_files`.

The sibling `factory_intelligence` package's dataset remains
**synthetic** (fixed-seed, pipeline-test-only) and is not used by this
package. This package's own `data/factory/synthetic/` holds a handful
of minimal, freshly-generated synthetic fixtures for pipeline/unit
testing only.

This has one binding architectural consequence, enforced structurally
(not just documented) throughout this project: **synthetic data may be
used for pipeline and unit testing only, and must never be treated as
Factory Evidence for the purposes of Factory DNA or Gold DNA.** See
`docs/DATABASE_ARCHITECTURE.md` and `docs/GOLD_DNA_SPECIFICATION.md`
for the enforcement mechanism. Only `.mid` files are accepted as
Factory evidence input (proprietary `.sty`/`.set` binary formats are
out of scope).

## Decisions log

| Date | Decision | Rationale |
|---|---|---|
| 2026-08-11 | Only `.mid` accepted as Factory evidence format | Real Korg data will arrive as exported/binary `.mid`; `.sty`/`.set` are proprietary binary formats out of scope |
| 2026-08-11 | `korg_pa800_optimizer/` is a fully independent new package, no reuse of `factory_intelligence` or `x10_think_midi` code | User decision — avoids coupling an evidence-based system to code built under different assumptions/goals |
| 2026-08-11 | This build session covers Phase 0-1 (bootstrap, discovery, architecture, stub skeleton) only | Spec's own phase-gate rule (§59): don't advance phases just because code exists. Full 21-phase implementation is deliberately out of scope here |
| 2026-08-11 | Synthetic dataset structurally walled off from Gold DNA (separate loader modules, `source_kind` schema column, promotion gate) | Prevents evidence-based claims from silently resting on non-Korg data |
| 2026-08-11 | Real Factory Style data (3211 files) and Golden Dataset song performances (182 files) ingested; Vertical A's Phase 1-4 (MIDI Core, Database, Factory ingestion, Factory Evidence) implemented with real logic | User-supplied real data made this the natural next step, per the phase-gate rule -- code now matches evidence that actually exists |
| 2026-08-11 | User's own "Gold DNA" folder name (182 real song performances) renamed in-repo to `data/golden/songs/` | Avoids colliding with this project's own `gold_dna` concept (validated derived rules) -- these are raw performance recordings, catalogued in a separate `golden_files` table, never written to `gold_dna` |
| 2026-08-11 | `factory_evidence` extended with `style_name`/`style_section`/`section_evidence_level` columns; filename/directory-name disagreements (208 of 3211 real files -- `_3_4_` time-signature qualifiers and one style whose name contains `/` and was mangled inconsistently between folder and filename) recorded raw via an `event_summary_json.style_name_filename_mismatch` flag, never interpreted or corrected | Section is filename-derived, not content-derived, for this dataset; per the "never invent Korg data" rule, disagreements are recorded, not resolved by guessing |
| 2026-08-11 | New `infrastructure/golden_dataset.py` module + `data/golden/**` ownership added to Vertical A (cataloging only) in `docs/VERTICAL_DECOMPOSITION.md` | Filled a genuine ownership gap -- Golden material isn't Factory Evidence (`factory/`) and isn't a Gold DNA rule (`gold/`, Vertical B) |
| 2026-08-11 | Phase 5 (Factory DNA) scoped to Rhythm/Velocity/Timing/Arrangement DNA only this session; Melody DNA and true Harmony DNA deferred to Solo DNA (Phase 9) / Harmony (Phase 10) | User decision -- those two categories need note-sequence/interval and key-context infrastructure that doesn't exist yet; grafting an ad hoc version on now risked inventing an analysis method the project hasn't committed to |
| 2026-08-11 | `knowledge.db` created (`factory_dna`, `gold_dna`); `factory_dna` extended with `style_section`/`channel`/`channel_b` grouping-key columns and `metrics_json`, beyond the originally drafted schema | No instrument identity exists yet (Phase 7), so grouping is by structural, already-CONFIRMED facts only (filename-derived section, raw MIDI channel) -- never an assumed instrument role. Run against the real 3211-file corpus: 793 factory_dna rows, confidence range 0.01-0.86 |
| 2026-08-11 | Phase 6 (Gold DNA promotion) run in the same session against the real Factory DNA above: 476 of 793 candidates promoted (0 blocked by the synthetic gate, since extraction only ever sources REAL evidence; 317 blocked by size/consistency thresholds) | User explicitly asked for "Gold DNA," not just Factory DNA sitting unpromoted -- completes the real Evidence -> Factory DNA -> Gold DNA chain end to end |
| 2026-08-11 | Gold DNA row-per-attempt semantics resolved (one `gold_dna` row per evaluated `factory_dna` row, promoted or blocked) + `supporting_examples`/`contradicting_examples` scoped down to real-but-simple (first-N traceable files / always empty, not true outlier ranking) | Resolves a self-contradiction in the original `GOLD_DNA_SPECIFICATION.md` wording; true "closest/furthest from mean" ranking would require retaining per-instance raw values through promotion, which `factory_dna`'s aggregate-only schema doesn't do this session -- documented as a scope limit, not fabricated as a finished analysis |

## Non-goals for the Phase 1-4 session (historical, now superseded where noted)

- ~~No Factory DNA extraction, Gold DNA promotion~~ -- **done as of the
  Phase 5-6 session below.** Instrument Identity and RX/mapping logic
  (Phase 7+) still don't exist -- `musical/`, `mapping/`, `rx/`,
  `optimizer/`, `validation/`, `export/` remain untouched docstring
  stubs. `gui/` and `cli.py`/`app.py` have a read-only analysis preview
  (see the GUI session's own decisions, not repeated here) but no
  optimizer action, since `optimizer/engine.py` still doesn't exist.
- No GM/RX interpretation of Program Change values in Factory Evidence
  -- program numbers are stored raw (Phase 7-8 territory, still true).
- No per-file GOOD/EDGE_CASE/CONFIRMED_* tagging of Golden Dataset
  material -- still true; that requires musical analysis (Vertical B,
  Phase 9+); Golden material remains catalog-only.

## Non-goals for the Phase 5-6 session (Factory DNA + Gold DNA)

- No Melody DNA or true Harmony DNA (key/chord relations over time) --
  deferred to Solo DNA (Phase 9) / Harmony (Phase 10).
- No Instrument Identity, GM->RX mapping, RX safety engine, or
  Optimizer logic (Phase 7+) -- `musical/`, `mapping/`, `rx/`,
  `optimizer/`, `validation/`, `export/` remain untouched docstring
  stubs.
- No true outlier ranking for `contradicting_examples` (see the
  decisions log entry above) -- documented scope limit, not a
  fabricated "none found" result.
- Golden Dataset material (`data/golden/songs/`) is explicitly not part
  of Factory DNA extraction -- DNA is computed only from Factory Style
  evidence, per the existing architecture.

## Definition of done for the Phase 5-6 session

`dna/extraction.py` and `dna/factory_dna.py` implement real Rhythm/
Velocity/Timing/Arrangement DNA extraction (no longer docstring stubs),
run successfully against the full real 3211-file Factory Style corpus
in well under a minute, and are idempotent (full-rebuild semantics
verified by re-running). `gold/promotion.py`, `gold/gold_dna.py`, and
`gold/registry.py` implement the promotion pipeline including the
synthetic-exclusion gate and size/consistency thresholds, run
successfully against the real Factory DNA produced above, and produce
genuinely promoted Gold DNA rules (476 of 793 evaluated). All new
formulas are unit-tested against hand-computable values; the
synthetic-exclusion invariant and row-per-attempt semantics are
explicitly tested. `pytest` passes in full. The root project and
Vertical A's/GUI's existing work remain untouched. `musical/`,
`mapping/`, `rx/`, `optimizer/`, `validation/`, `export/`, `gui/`
optimizer logic, `cli.py` remain untouched docstring stubs -- no
Vertical C scope creep.
