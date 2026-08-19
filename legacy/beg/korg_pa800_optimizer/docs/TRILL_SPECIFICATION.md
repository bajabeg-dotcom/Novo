# Trill Specification

## Pattern

A trill is a rapid, sustained alternation between two adjacent (or
otherwise interval-defined) pitches: `N1 -> N2 -> N1 -> N2 -> N1 ...`.
Detecting this pattern is not sufficient by itself — the detector must
also analyze pitch interval, repetition count, timing regularity,
duration, velocity profile, harmonic context, and phrase position
before classifying an alternation as a true trill.

## Required disambiguation

The detector must be able to distinguish a trill from:
- scale run
- arpeggio
- melody repetition (a written-out motif, not an ornament)
- tremolo (single-note or non-adjacent-interval repeated attack)
- drum roll
- normal accompaniment pattern

## Trill model (once implemented)

Per detected trill instance:

| Field | Meaning |
|---|---|
| `main_note`, `neighbor_note` | The two pitches involved |
| `interval` | Interval between them |
| `direction` | Upper or lower neighbor |
| `repetition_count` | Number of alternations |
| `total_duration`, `average_duration` | Timing |
| `onset_spacing`, `timing_variance` | Regularity of the alternation |
| `velocity_mean`, `velocity_variance` | Dynamic profile |
| `chord`, `scale` | Harmonic context at the time |
| `phrase_position` | Where in the phrase the trill occurs |
| `confidence`, `evidence_level` | Per `docs/DATA_MODEL.md` |

## Trill Gold DNA (once implemented)

Aggregated across confirmed Factory trill occurrences: interval
distribution, repetition-count distribution, timing distribution,
velocity profile, tempo relation, harmonic context, phrase-position
tendency, start/exit behavior, and per-instrument/per-style behavior.
Subject to the same synthetic-exclusion promotion gate as all Gold DNA
(`docs/GOLD_DNA_SPECIFICATION.md`).

## False-positive fixture requirement

Same categories as `docs/ORNAMENT_SPECIFICATION.md`: scale run,
arpeggio, repeated melody, tremolo, drum roll, normal accompaniment,
two-note motif — plus at least one confirmed true trill example. Fixture
location (created empty in this skeleton): `tests/fixtures/trills/`.
The detector must demonstrably reject the negative fixtures, not just
accept the positive one.

## Status

`src/korg_optimizer/musical/trill_dna.py` is a docstring-only stub.
Per `docs/ROADMAP.md`, implemented at Phase 13, after Ornament Mining
(Phase 12) and Harmony (Phase 10).
