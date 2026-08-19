# S01 Exact Contextual Profile Velocity Suggest audit — 2026-08-14

## Decision

**PASS** for the bounded Suggest-only scope.

S01 cannot be applied by C01 and does not authorize automatic Enhance.

## Exact matching

S01 refuses every fallback. A match requires equal:

- source kind;
- full K01 address;
- Factory item kind;
- M07 function;
- Style Element;
- CV;
- structural role;
- encoding;
- fixed Intro/Ending flag.

Factory and Gold source kinds never mix. Any mismatch returns `NO_PROFILE`.

## Reference support

Conservative named defaults:

- minimum observations: 3;
- minimum distinct Styles: 2;
- minimum reference notes: 32;
- outlier tolerance beyond p10/p90: 4 velocity units;
- maximum single adjustment: 8 units;
- maximum mutations per proposal: 32.

Invalid configuration is rejected rather than silently clipped.

Of 13,821 R01 profiles, 1,687 pass reference/context prefiltering:

- chordal: 293
- line/riff: 18
- bass: 372
- drum: 419
- rhythm guitar: 325
- percussion: 255
- solo candidate: 5

This is not the number of suggestions. The imported source, context and actual
outliers must still pass every gate.

## Context gates

- K02 identity must be `FACTORY_CONFIRMED`;
- M07 status must be `CLASSIFIED`;
- encoding must be `ORDINARY_MIDI`;
- function cannot be `UNKNOWN`;
- fixed Intro/Ending candidate is blocked;
- `DO_NOT_TOUCH` is blocked;
- the user must explicitly enable S01.

## Suggestion behavior

Only Note On velocities farther than the configured tolerance outside the
exact profile p10–p90 interval become candidates. Each is moved by at most 8
units toward the interval. Pitch, timing, duration, note order and all unlisted
velocity values remain outside the plan.

The proposal is `INFERRED`, carries M07 confidence, `MEDIUM` risk, R01 profile
ID/support/percentiles, exact event mutations and a warning that
velocity-switch/RX thresholds are unknown.

Even after USER approval, C01 rejects Note On `data[1]`; S01 is deliberately
non-applicable until a separate specialized velocity Change/Verifier scope is
implemented.

## Tests

```bash
python -m pytest -q tests/test_profile_suggest_engine.py
```

Result: **6 passed, 10 subtests passed**.

Full command:

```bash
DISPLAY=:111 python -m pytest -q
```

Full result: **139 passed, 3,252 subtests passed, 0 failed, 0 skipped** in
302.44 seconds.

Coverage includes bounded outlier planning, every contextual key mismatch,
insufficient reference, user/context/fixed blocking, no-outlier,
too-many-outliers, invalid config and explicit C01 Apply rejection.
