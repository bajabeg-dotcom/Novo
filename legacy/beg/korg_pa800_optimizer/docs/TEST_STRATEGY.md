# Test Strategy

## Test pyramid

- **Unit tests** (`tests/unit/<module>/`) — one subtree per Vertical-owned
  module group, per `docs/VERTICAL_DECOMPOSITION.md`.
- **Integration tests** (`tests/integration/`) — cross-module pipeline
  behavior (e.g. import -> evidence -> DNA).
- **Regression tests** (`tests/regression/`) — the P0 gate list in
  `docs/VALIDATION_SPECIFICATION.md`, run on every change.
- **Golden dataset tests** (`tests/golden/`) — behavior against curated
  real-world examples once a Golden Dataset exists (`data/golden/`).
- **Property tests** — invariants that must hold for any valid input
  (e.g. "preservation-mode events are never mutated"), to be introduced
  alongside the modules they test.
- **MIDI round-trip tests** — import -> normalize -> export (no
  optimization) must be musically lossless; see
  `docs/MIDI_MODEL.md`.
- **Database integrity tests** — foreign keys, constraints, idempotent
  import.

## Fixture conventions

- `tests/fixtures/synthetic/` — synthetic MIDI for pipeline/unit tests only.
- `tests/fixtures/trills/`, `tests/fixtures/ornaments/` — positive and
  negative (false-positive) examples per `docs/TRILL_SPECIFICATION.md`
  and `docs/ORNAMENT_SPECIFICATION.md`.
- `tests/fixtures/solo/`, `tests/fixtures/harmony/` — examples for
  Solo DNA and Harmony DNA validation.

## Hard rule: synthetic data is never Gold DNA evidence

This is the single most important testable invariant in the project.
Once `gold/promotion.py` exists (Phase 6), a CI-level test must assert:

> No row in `gold_dna` may have a `promoted_from_factory_dna_id` whose
> `factory_dna.source_kind_composition` contains any `SYNTHETIC` count
> greater than zero.

This test does not exist yet in this Phase 0-1 skeleton (there is no
`gold_dna` table populated yet), but it is recorded here as a required
test before Phase 6 can be considered done, per the phase-gate rule in
`docs/ROADMAP.md`.

## Per-vertical coverage expectation

Each vertical (`docs/VERTICAL_DECOMPOSITION.md`) is responsible for
unit coverage of the modules it owns, plus contributing to shared
integration/regression suites for cross-vertical contracts it produces
or consumes (e.g. Vertical A's normalized MIDI model shape, consumed by
B and C).

## Negative-case testing

Every detector (trill, ornament, RX safety, instrument identity) must
have negative-case tests proving it correctly does *not* fire, not just
positive-case tests proving it does. This mirrors the project's overall
bias toward preservation over generation when evidence is insufficient.
