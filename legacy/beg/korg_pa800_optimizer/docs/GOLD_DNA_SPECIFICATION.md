# Gold DNA Specification (promotion pipeline)

Field-level schema is in `docs/GOLD_DNA_MODEL.md`.

## Promotion pipeline

```
FACTORY EVIDENCE (per-file, real .mid content)
       |
FACTORY DNA (statistical/structural pattern across evidence)
       |
   [ SYNTHETIC-EXCLUSION GATE ]
       |
    GOLD DNA (validated, generalized rule)
```

## Synthetic-exclusion gate

Before any `FactoryDNA` row may be promoted to `GoldDNA`:

1. Inspect `factory_dna.source_kind_composition` (JSON breakdown of how
   many contributing `SourceFile`s were `REAL` vs `SYNTHETIC`).
2. If the composition includes **any** `SYNTHETIC` count greater than
   zero, promotion is rejected: `gold_dna.promotion_blocked_reason` is
   set to a specific explanation (e.g. `"3 of 12 contributing sources
   are SYNTHETIC"`).
3. Only Factory DNA computed entirely from `REAL` evidence may be
   promoted.

This is why `factory/synthetic_dataset.py` and `factory/real_dataset.py`
are kept as two separate loader modules (see
`docs/DATABASE_ARCHITECTURE.md` and `docs/VERTICAL_DECOMPOSITION.md`)
rather than one parameterized loader — mislabeling data requires
visibly importing the wrong module, which is a much easier mistake to
catch in review than a mismatched flag/parameter. In practice,
`dna/extraction.py` only ever aggregates over `source_kind='REAL'`
Factory Style evidence, so this gate is currently a belt-and-suspenders
check rather than one that fires in normal operation -- it's still
implemented and tested (`tests/unit/gold/test_promotion.py`) because it
is the mechanism that makes the synthetic/real separation an
enforced invariant, not just a convention.

## Promotion thresholds (beyond the synthetic-exclusion gate)

A `factory_dna` row must also clear size/consistency thresholds, tiered
by what its `occurrence_count` counts (see `docs/GOLD_DNA_MODEL.md`
"Confidence formula" for the matching `SATURATION_N` tiers):

| Tier | `min_occurrence_count` | `min_source_count` | `min_confidence` |
|---|---|---|---|
| `note_level` (rhythm, velocity, timing) | 30 | 10 | 0.6 |
| `track_level` (arrangement channel_profile, section_behavior) | 10 | 10 | 0.6 |
| `pair_level` (arrangement layer_interaction) | 5 | 5 | 0.6 |

`source_count` is the number of *distinct* contributing `SourceFile`s
(`len(derived_from_evidence_ids)`), distinct from `occurrence_count`
(which counts finer-grained instances -- notes, tracks, or file-pairs).
Requiring `source_count >= 10` for note/track-level tiers guards
against one unusually busy style dominating a bucket. All three
thresholds and the synthetic gate must hold simultaneously. These are
documented v1 heuristics (`gold/promotion.py`
`PROMOTION_THRESHOLDS`), not derived from any Korg-specific fact.

## Row-per-attempt semantics

Every evaluated `factory_dna` row produces **exactly one** `gold_dna`
row, whether promoted or blocked — this resolves an earlier ambiguity
in this document (which said both "a reason is set" and "no row is
created" for a blocked promotion, which cannot both be literally true
of the same row). The resolution implemented in `gold/promotion.py`:

- **Promoted**: `promoted_at` set, `evidence_level="INFERRED"`,
  `promotion_blocked_reason=NULL`.
- **Blocked** (synthetic-tainted or below threshold):
  `promotion_blocked_reason=<specific reason>`, `promoted_at=NULL`,
  `evidence_level="UNKNOWN"`.

This gives full auditability — every candidate rule's fate is queryable
in `gold_dna`, not silently dropped — while `gold/registry.py` (the
consumer-facing interface other modules will use, once they exist)
only ever returns rows where `promoted_at IS NOT NULL`, so blocked
candidates never leak into anything downstream as if they were valid.

## Status

**Implemented and run against the real corpus.** `dna/extraction.py`
computes Rhythm, Velocity, Timing, and Arrangement DNA (density,
subdivision, syncopation, swing, groove, velocity distribution/accents/
dynamic contour, note duration/gate ratio, channel activity ratio,
channel-pair co-activity, and per-section aggregate behavior — see
`docs/DATABASE_ARCHITECTURE.md` "factory_dna grouping keys" for the
`(style_section, channel[, channel_b])` grouping scheme) from the real
3211-file Factory Style corpus. `gold/promotion.py` evaluates every
resulting `factory_dna` row. Melody DNA and true Harmony DNA remain out
of scope (Solo DNA/Harmony, Phase 9-10).
