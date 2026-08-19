# Gold DNA Model (schema)

Behavioral/promotion rules are in `docs/GOLD_DNA_SPECIFICATION.md`.
Physical columns are in `docs/DATABASE_ARCHITECTURE.md` (`gold_dna`
table). This document defines the field-level meaning.

## Fields

| Field | Meaning |
|---|---|
| `rule_id` | Stable, unique identifier for this rule |
| `category` | One of: rhythm, velocity, timing, melody, harmony, arrangement, ornament, trill, solo, delay, terca, guitar, etc. |
| `source_count` | Number of distinct Factory `SourceFile`s that contributed evidence |
| `occurrence_count` | Number of individual pattern occurrences observed across those sources |
| `confidence` | Numeric score in `[0, 1]` reflecting statistical strength of the pattern -- see "Confidence formula" below |
| `evidence_level` | `CONFIRMED` / `INFERRED` / `UNKNOWN`, per `docs/DATA_MODEL.md` |
| `supporting_examples` | Concrete references (source file + location) that support the rule |
| `contradicting_examples` | Concrete references that contradict or complicate the rule — Gold DNA must record disagreement, not hide it |

## What Gold DNA is not

Gold DNA is **not** a "magic AI knowledge base." Every rule must be
traceable back through Factory DNA to specific Factory Evidence
records (`derived_from_evidence_ids` / `promoted_from_factory_dna_id`).
A Gold DNA rule with no supporting examples is not a valid rule.

## Real vs. synthetic evidence

A Gold DNA rule may never be promoted from Factory DNA whose evidence
chain includes any `source_kind = SYNTHETIC` `SourceFile`. See
`docs/GOLD_DNA_SPECIFICATION.md` for the enforcement mechanism.

## `evidence_level` convention

A successfully promoted rule's `evidence_level` is always `INFERRED`,
**never `CONFIRMED`** -- per the source-of-truth hierarchy in
`docs/PROJECT_GOAL.md`, `CONFIRMED` is reserved for direct observation
(physical PA800 hardware, official KORG documentation, or Factory
Evidence itself). A statistically-aggregated cross-file pattern, even
one derived entirely from real evidence, is one inference step beyond
that. A blocked candidate's `evidence_level` is `UNKNOWN` (no valid
claim exists) with `promotion_blocked_reason` set.

## Confidence formula (implemented by `dna/extraction.py` and reused
verbatim by `gold/promotion.py`'s threshold checks)

```
size_component = min(1.0, occurrence_count / SATURATION_N)
CV = |stddev / mean|  (0.0 if mean and stddev both ~0; 1.0 if mean ~0 but stddev isn't), clamped to [0, 5.0]
consistency_component = 1 / (1 + CV)
confidence = round(clamp(size_component * consistency_component, 0.0, 1.0), 4)
```

For categorical metrics (e.g. the dominant rhythmic subdivision),
`consistency_component` is instead the winning label's share of all
observations (`mode_count / total_count`).

`SATURATION_N` (the occurrence_count at which `size_component` reaches
1.0) is tiered by what `occurrence_count` counts for that row:

| Tier | Categories | `SATURATION_N` |
|---|---|---|
| `note_level` | rhythm, velocity, timing (`occurrence_count` = total notes in the group) | 5000 |
| `track_level` | arrangement `channel_profile` (tracks) / `section_behavior` (files) | 100 |
| `pair_level` | arrangement `layer_interaction` (channel-pair file-instances) | 50 |

These are documented v1 heuristics sized against the real corpus's
scale (248 styles × up to 13 sections), not derived from any
Korg-specific fact -- retune if a real confidence-distribution check
shows they're badly calibrated (see `docs/ROADMAP.md` "Phase 5/6
results" for the actual distribution observed against the full real
corpus).

Each `factory_dna` row bundles several sub-metrics (e.g. a `rhythm` row
carries density, subdivision, syncopation, swing, and groove together
-- see `docs/DATABASE_ARCHITECTURE.md` "metrics_json convention"), but
the row's single stored `confidence`/`occurrence_count` reflect one
designated *primary* metric per category: `rhythm` → density,
`velocity` → the raw velocity distribution, `timing` → note duration
distribution, `arrangement.channel_profile`/`layer_interaction` →
activity_ratio/co_activity, `arrangement.section_behavior` → density.

## Supporting / contradicting examples -- implemented, with a documented scope limit

`supporting_examples` are up to 10 real, traceable
`{source_file_id, file_path, style_name}` records drawn from the
promoted rule's `derived_from_evidence_ids` (the lowest-id contributing
files, for deterministic/reproducible output).

**Scope limit**: these are *not* literally "the instances closest to
the group's mean" -- computing that would require retaining
per-instance raw values through promotion, which `factory_dna.metrics_json`
does not do this session (it stores only aggregate statistics).
`contradicting_examples` is correspondingly always an empty list this
session -- this is a documented scope limitation ("not attempted"),
not a fabricated "no contradictions were found" claim. A future
session wanting genuine outlier detection would need to extend
`factory_dna`'s per-group state to retain a bounded sample of raw
per-instance values (density/velocity/etc.) through to promotion time.
