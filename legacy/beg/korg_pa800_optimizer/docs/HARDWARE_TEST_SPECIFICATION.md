# Hardware Test Specification

## Status: NOT YET AVAILABLE

No physical KORG PA800 hardware testing has been performed for this
project. Every fact that would require hardware confirmation (actual
RX trigger behavior, actual sound response, actual factory mapping
behavior) is `UNKNOWN` until directly tested — see the evidence
hierarchy in `docs/PROJECT_GOAL.md`. Statistical inference from Factory
MIDI evidence, no matter how strong, produces at best `INFERRED` facts,
never `CONFIRMED` hardware facts.

## Status separation

Every optimization result must be able to report one of:
- `SOFTWARE_PASS` — passed all software validation gates
- `PENDING_HARDWARE` — software-validated, not yet hardware-tested
- `HARDWARE_PASS` — confirmed on physical PA800 hardware
- `HARDWARE_FAIL` — failed on physical PA800 hardware (must be
  investigated and the responsible Gold DNA rule / RX mapping revised
  or demoted)

A `SOFTWARE_PASS` must never be presented or reported as equivalent to
a `HARDWARE_PASS`.

## `hardware-tests/` directory purpose

Once implemented (Phase 19, `docs/ROADMAP.md`), each hardware test
package will contain: the test MIDI file, the expected mapping,
expected behavior description, a hash of the test file, step-by-step
test instructions for a human operator with the physical PA800, and
fields to record the result and notes. Not created in this Phase 0-1
skeleton beyond the directory placeholder.

## Status

`hardware-tests/` currently contains only a placeholder README.
