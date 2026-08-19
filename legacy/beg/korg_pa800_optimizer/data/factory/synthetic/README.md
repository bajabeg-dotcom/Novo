# Synthetic Factory Data

Pipeline / unit-test fixtures only. Files placed here are loaded via
`factory/synthetic_dataset.py`, which hardcodes
`source_kind=SYNTHETIC` on every record it produces.

**Never used as Gold DNA evidence.** See
`docs/GOLD_DNA_SPECIFICATION.md` "synthetic-exclusion gate" and
`docs/PROJECT_GOAL.md` "Evidence status: synthetic vs. real Factory
data".

Contains 3 minimal, deterministic `.mid` files freshly generated via
`mido` (not copied from `factory_intelligence`'s dataset): a
single-track format-0 file (notes, CC, program change, pitch bend,
tempo/time-signature meta), a two-track format-1 file (multi-track
round-trip coverage), and a format-0 file exercising SysEx and
aftertouch. Identical copies live under `tests/fixtures/synthetic/`
for MIDI Core unit tests that don't want to go through the ingestion
pipeline.
