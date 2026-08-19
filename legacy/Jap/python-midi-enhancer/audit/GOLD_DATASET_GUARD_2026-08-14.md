# G02 Gold Dataset Contamination Guard audit — 2026-08-14

## Decision

**PASS** for structural contamination, deduplication and source-disjoint split.

M07 statistical confidence calibration remains **BLOCKED** because no
independent human role-label manifest exists.

## Registered sources

- Factory ZIP SHA-256:
  `ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`
- DNA ZIP SHA-256:
  `125f4486625db44f7cdd49bd670aff252a961c88ea14741ec970ec3ae5eec85a`
- Nested Gold ZIP SHA-256:
  `da7d5dd6fac74d4d6a35d5d3bdacc4cabe988873ec0472529e9c6ef2a9b77e5e`

All ZIP member paths are checked for absolute and parent traversal paths. The
archives are read in place and not extracted over source data.

## Factory contamination exclusion

The DNA outer package contains `Split Factory Styles.zip` with the exact
registered Factory SHA-256. G02 marks it:

```text
EXACT_FACTORY_ARCHIVE_CONTAMINATION_EXCLUDED
```

It never enters Gold counts or evaluation records.

## Content deduplication

Factory:

- files: 3,211
- unique content hashes: 3,187
- internal duplicate hash groups: 24

Gold:

- valid MIDI files: 182
- canonical unique content hashes: 181
- internal duplicate groups: 1

The Gold duplicate group contains:

- `Gold DNA/JOZA TUZNI-KNINDZA UZIVO.MID`
- `Gold DNA/JOZA TUZNI-KNINDZA UZIVO (2).MID`

The lexicographically first member becomes canonical and the other remains in
provenance.

## Cross-source guard

Factory–Gold individual MIDI hash overlap: **0**.

The deduplicated Gold evaluation set contains:

- 181 MIDI files
- 5,028,387 parsed events
- 2,263,727 Note On events

Manifest digest:
`62a0ac2ceb1ccf301c99e5a0c65a4d3febd3d6b46f14543b8b9e9898c60bb2e1`.

The split is explicit:

```text
TRAIN/REFERENCE: FACTORY_STYLE_REFERENCE_ONLY
EVALUATION:      GOLD_DNA_DEDUPLICATED_ONLY
```

Both source archive hashes remain unchanged.

## Calibration blocker

Gold provides musical MIDI files but no separately human-verified per-part
labels for chordal, riff, solo, Guitar Mode, fixed, Drum/Perc/Bass or Unknown.
Therefore accuracy, precision, recall and probability calibration cannot be
computed honestly. M07 confidence remains a deterministic heuristic score, not
a statistical probability.

## Tests

```bash
python -m pytest -q tests/test_gold_dataset_guard.py
```

Result: **3 passed, 3 subtests passed**.

Full command:

```bash
DISPLAY=:112 python -m pytest -q
```

Full result: **142 passed, 3,255 subtests passed, 0 failed, 0 skipped** in
421.49 seconds.

Tests cover the real source manifest, deterministic repeat build and unsafe ZIP
path rejection.
