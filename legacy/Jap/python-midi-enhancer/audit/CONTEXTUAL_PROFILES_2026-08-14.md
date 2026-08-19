# R01 Factory Contextual Profile Builder audit — 2026-08-14

## Decision

**PASS** for the read-only Factory empirical reference scope.

Profiles do not authorize Suggest, Change or Enhance.

## Isolation key

Every profile is separated by:

- source kind (`FACTORY_STYLE`);
- full effective K01 address and Factory item kind;
- M07 musical function;
- Style Element;
- CV;
- structural role (`DRUM`, `PERC`, `BASS`, `ACC1`–`ACC5`, etc.);
- encoding;
- fixed Intro/Ending candidate flag.

Changing any key component creates a different profile and profile ID. Factory
and Gold/DNA source kinds cannot enter the same catalog/profile.

## Accepted observations

An observation requires:

- K02 `FACTORY_CONFIRMED` identity;
- exact K01 entry and effective address;
- at least one Note On;
- non-BLOCKED M10 segment;
- non-BLOCKED M09 measurement.

Conflict, Incomplete Address, No Program and unusable confirmed segments are
counted but excluded.

## Profile contents

- exact empirical velocity percentiles;
- pitch percentiles and range;
- closed-note duration-beat percentiles;
- density distribution;
- maximum sounding and onset polyphony;
- controller event counts;
- segment/measurement quality counts;
- member/style provenance;
- stable deterministic profile ID;
- `DERIVED_EMPIRICAL` evidence status;
- `REFERENCE_ONLY_NO_SUGGEST_AUTHORIZATION` policy.

## Full Factory result

- valid segment observations: **29,603**
- isolated contextual profiles: **13,821**
- digest:
  `33a9b42601bd7612f51312e4c2985bd483f49281edfaa2710d65bcf84998f4b5`

Profiles by M07 function:

- `ACCOMP_CHORDAL`: 3,754
- `ACCOMP_LINE_RIFF`: 1,759
- `SOLO_CANDIDATE`: 1,305
- `RHYTHM_GUITAR`: 2,383
- `BASS_ACCOMP`: 945
- `RHYTHM_DRUM`: 806
- `RHYTHM_PERC`: 765
- `UNKNOWN`: 2,104

Excluded identity/quality counts:

- `CONFLICT`: 15
- `INCOMPLETE_ADDRESS`: 6
- `NO_PROGRAM`: 53,292
- unusable confirmed segment: 1

The Factory ZIP SHA-256 remains unchanged:
`ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`.

## Tests

```bash
python -m pytest -q tests/test_contextual_profile_builder.py
```

Result: **5 passed**, including the full Factory build.

Full command:

```bash
DISPLAY=:110 python -m pytest -q
```

Full result: **133 passed, 3,242 subtests passed, 0 failed, 0 skipped** in
308.25 seconds.

The unit cases prove exact aggregation and separation by function, Element, CV
and source kind, reject provenance/name conflicts and verify deterministic
output independent of observation order.

## Next gate

A future Suggest rule must request an exact matching profile key and still pass
context, evidence, risk and user-confirmation policy. R01 alone never creates a
proposal.
