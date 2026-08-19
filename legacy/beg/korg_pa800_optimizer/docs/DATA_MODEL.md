# Data Model (conceptual)

This document describes entities and relationships independent of
storage engine. Physical schema (SQLite tables/columns) lives in
`docs/DATABASE_ARCHITECTURE.md`.

## CONFIRMED / INFERRED / UNKNOWN

Any field that represents a claim about Korg-specific behavior (an RX
trigger, a mapping, an articulation, a factory sound identity, a piece
of hardware behavior) must carry an `evidence_level` value:

- `CONFIRMED` — directly observed in Factory Evidence, official Korg
  documentation, or physical PA800 hardware testing.
- `INFERRED` — reasoned from confirmed facts or statistical patterns,
  but not directly observed. Must be labeled as such everywhere it is
  displayed or used in a decision.
- `UNKNOWN` — no basis exists. The Decision Engine must never act on an
  `UNKNOWN` fact as if it were true; default behavior is to preserve
  original MIDI rather than guess.

## Entities by logical layer

### source
- **SourceFile** — a single imported `.mid` file: path, SHA-256 hash,
  `source_kind` (`SYNTHETIC` | `REAL`), import timestamp, parser
  version, byte size. Immutable once recorded.

### evidence
- **FactoryEvidence** — structural/event facts extracted from a
  SourceFile: tracks, sections (intro/variation/fill/break/ending/
  count-in, only where evidence supports it), instrument segments
  (Program Change/Bank Select ranges), articulation occurrences.
  References the SourceFile it came from (provenance is mandatory).
  For the real Factory Style corpus, "section" is derived from the
  **filename** (KORG's own `<StyleName>_<Section>.mid` export
  convention), not from MIDI content — see `docs/DATABASE_ARCHITECTURE.md`
  and `docs/MIDI_MODEL.md` for the parsing rule and its one documented
  real-data quirk (filename/directory-name mismatches, recorded raw,
  never guessed at). Content-derived section detection for other future
  evidence sources remains future work.
- **GoldenFile** — a cataloged (hashed, path-recorded) file under
  `data/golden/` (e.g. real live-performance song recordings). Distinct
  from FactoryEvidence/SourceFile: it carries no `evidence_level` and
  makes no musical claim, it's a manifest entry only. Per-file curation
  (GOOD/EDGE_CASE/CONFIRMED_* tagging) is deferred to Vertical B,
  Phase 9+ — see `docs/DATABASE_ARCHITECTURE.md` `golden_files`.

### factory (DNA)
- **FactoryDNA** — a statistical/structural pattern computed across one
  or more FactoryEvidence records: rhythm DNA, velocity DNA, timing
  DNA, melody DNA, harmony DNA, arrangement DNA. Records which
  SourceFiles (and their `source_kind`) contributed.

### gold
- **GoldDNARule** — a validated, generalized rule promoted from
  FactoryDNA. Fields: `rule_id`, `category`, `source_count`,
  `occurrence_count`, `confidence`, `evidence_level`,
  `supporting_examples`, `contradicting_examples`. May only be promoted
  from FactoryDNA whose evidence chain contains zero `SYNTHETIC`
  SourceFiles (see `docs/GOLD_DNA_SPECIFICATION.md`).

### mapping
- **GmRxMapping** — gm_msb, gm_lsb, gm_program -> factory_target,
  rx_target, confidence, evidence_level, `instrument_identity`
  reference. Unconfirmed mappings must never be presented or used as
  confirmed.

### rx
- **RxArticulation** — canonical_name, category, instrument, trigger
  (key switch / CC / velocity range / NRPN / RPN / SysEx), timing,
  duration, velocity, pitch, context, negative_rules (contexts where it
  must NOT trigger), factory_occurrences, confidence, evidence_level.

### musical
- **InstrumentIdentity** — per Program Change/Bank Select segment: GM
  family, possible RX candidate (if any), `evidence_level`.
- **SoloDNA**, **HarmonyDNA** (chord/scale/key context, time-aware),
  **OrnamentDNA**, **TrillDNA** — see their respective SPECIFICATION
  docs for field-level detail.
- **MusicalRole** — per-track classification (Solo, Bass, Drums, Chord,
  Pad, Guitar, Brass, Strings, Percussion, Harmony, Terca, Delay,
  Unknown) with a confidence value. `Unknown` must never be forced into
  a classification.

### optimization
- **OptimizationRun** — one execution of the pipeline against one input
  file: engine version, mode (Safe/Generative), timestamp.
- **ChangeLogEntry** — one mutation: track, event, before, after, rule,
  reason, confidence, source. This is the mechanism that makes
  "no silent mutation" enforceable and auditable.

### audit
- **AuditTrailEntry** — action-level record (e.g. "PRESERVE" decisions,
  not just mutations) tying an OptimizationRun to specific evidence and
  rules consulted, for full explainability.

### validation
- **ValidationResult** — one gate check (MIDI structural, musical, RX,
  preservation) per OptimizationRun: gate name, status
  (PASS/FAIL/SKIP), severity (P0/P1/P2), details.

## Cross-references

- Physical schema: `docs/DATABASE_ARCHITECTURE.md`
- MIDI-specific modeling detail: `docs/MIDI_MODEL.md`
- RX-specific modeling detail: `docs/RX_MODEL.md`
- Gold DNA field-level schema: `docs/GOLD_DNA_MODEL.md`
