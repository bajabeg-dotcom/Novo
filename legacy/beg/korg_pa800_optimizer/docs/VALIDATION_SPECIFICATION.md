# Validation Specification

## Severity tiers

- **P0** — release-blocking. Any P0 failure means the build is not
  releasable, full stop (see Release Gates below).
- **P1** — must be triaged before release but does not by itself block
  a build if explicitly accepted/waived.
- **P2** — advisory, tracked but non-blocking.

## Validation categories (once implemented)

- **MIDI**: valid structure, event ordering, timing, PPQ, tracks, channels.
- **Musical**: harmony validity, range, density, phrase coherence, voice leading.
- **RX**: instrument identity correctness, velocity safety, unsupported
  mapping usage, accidental articulation activation.
- **Preservation**: Solo, existing Terca, existing Delay, and any other
  explicitly protected events remain unchanged.

## P0 gate list (regression must fail the build if any of these occur)

- Protected Solo pitch changed while in preservation mode
- Existing Terca pitch changed while in preservation mode
- Existing Delay structure destroyed
- An unsupported/unconfirmed RX articulation activated
- Factory evidence altered (raw preservation guarantee broken)
- A mutation with no corresponding change-log entry (silent mutation)
- Database integrity failure (corrupted evidence/knowledge data)

## Release gates

A release is not permitted if any of the following are true:
- P0 failures exist
- regression tests are broken
- a mapping the system relies on has `evidence_level = UNKNOWN` and is
  used anyway
- silent mutations are found
- database corruption is found
- unsafe RX activation is found
- Factory data corruption is found

Hardware validation may remain `PENDING_HARDWARE` at release time as
long as it is clearly labeled as such — see
`docs/HARDWARE_TEST_SPECIFICATION.md`. A software PASS is not a
hardware PASS.

## Status

`src/korg_optimizer/validation/regression_gates.py` and `report.py` are
docstring-only stubs. Implemented at Phase 16 per `docs/ROADMAP.md`,
after the Optimizer (Phase 15) exists to validate against.
