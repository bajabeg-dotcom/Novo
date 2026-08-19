# KORG PA800 GM → RX Musical Intelligence Optimizer

Deterministic, evidence-based system that imports MIDI, identifies
instruments, extracts and validates musical "DNA" from real KORG PA800
Factory material, maps General MIDI instruments to KORG RX/DNC
articulations under a strict safety engine, applies safe/explainable
optimization, validates the result, and exports KORG-safe MIDI.

This is **not** a generic MIDI editor and **not** an AI system that
mutates MIDI on its own judgment. Every change the optimizer makes must
be traceable to evidence, a named rule, and a confidence score — see
`docs/PROJECT_GOAL.md` and `docs/ARCHITECTURE.md`.

## Status

Phases 0-6 implemented: bootstrap, MIDI Core, Database, Factory
ingestion, Factory Evidence (Vertical A), Factory DNA, and Gold DNA
(Vertical B). The package imports, hashes, and catalogs real KORG
PA800 Factory Style MIDI (3211 files across 248 styles) and Golden
Dataset performance recordings (182 files) into `evidence.db`;
extracts per-track/file-level structural evidence; computes Rhythm,
Velocity, Timing, and Arrangement DNA (`knowledge.db`'s `factory_dna`,
793 rows from the real corpus); and promotes qualifying patterns to
Gold DNA (`gold_dna`, 476 real, evidence-backed rules so far).

A local **web GUI** exists (`python app.py`) as a read-only "Evidence &
Analysis" preview: upload any `.mid` file and see its structural
validation and raw track/evidence facts. **There is still no
optimizer** — no GM/RX mapping, no Instrument Identity, no RX safety
engine — so the GUI has no "Optimize" action yet, and Gold DNA rules
aren't consumable by anything downstream until Phase 7+ exists.
Vertical C's modules (`musical/`, `mapping/`, `rx/`, `optimizer/`,
`validation/`, `export/`) remain docstring stubs. See `docs/ROADMAP.md`
for the full phase plan and `docs/VERTICAL_DECOMPOSITION.md` for how
future implementation work is split and coordinated.

## Relationship to other packages in this repository

This package is **fully independent**. It does not import from, depend
on, or share a database/runtime with `src/factory_intelligence/` (a
separate read-only Factory MIDI analysis layer using synthetic test
data) or `x10_think_midi/` (a separate rule-based humanization engine).
Ideas from those packages may inform design discussion, but no code is
reused directly — see `docs/PROJECT_GOAL.md` §3.

## Layout

- `install.bat`, `run.bat` — Windows setup/launch scripts (see "Getting started")
- `docs/` — architecture, data model, and specification documents (start here)
- `src/korg_optimizer/` — the package itself, organized by responsibility
  (`midi/`, `factory/`, `dna/`, `gold/`, `musical/`, `mapping/`, `rx/`,
  `optimizer/`, `validation/`, `export/`, `gui/`, `audit/`, `infrastructure/`)
- `data/` — factory evidence (`synthetic/` vs `real/`, kept structurally
  separate — see `docs/DATABASE_ARCHITECTURE.md`), golden datasets, mappings
- `tests/` — unit, integration, regression, golden, and fixture data
- `hardware-tests/` — physical KORG PA800 validation packages (Phase 19+)
- `output/`, `reports/` — generated artifacts (gitignored)

## Getting started

**Windows**: run `install.bat` once, then `run.bat` to start the web
GUI at http://127.0.0.1:5000/ (opens automatically in your browser).
These scripts were written and syntax-checked but **not run on an
actual Windows machine** (none was available in this environment) —
please report any issue.

**Manually / other platforms**:

```bash
pip install -e korg_pa800_optimizer/

python korg_pa800_optimizer/app.py
# -> opens http://127.0.0.1:5000/ in your browser: upload a .mid file to analyze it

# Optional: ingest the real Factory Style corpus and Golden Dataset into evidence.db
python -m korg_optimizer.factory.real_dataset
python -m korg_optimizer.factory.synthetic_dataset
python -m korg_optimizer.infrastructure.golden_dataset

# Optional: compute Factory DNA and promote qualifying patterns to Gold DNA
python -m korg_optimizer.dna.extraction
python -m korg_optimizer.gold.promotion

pytest korg_pa800_optimizer/tests/unit korg_pa800_optimizer/tests/integration
```

There is no CLI (`cli.py`) yet, and the web GUI is analysis-only (no
"Optimize" action) — see `docs/ROADMAP.md`.
