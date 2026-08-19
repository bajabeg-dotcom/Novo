# K02 Instrument Identity Resolver audit — 2026-08-14

## Decision

**PASS** for the bounded read-only K02 identity scope.

K02 does not mutate M10, MIDI events or the source file. It does not authorize
K03 replacement, Change, Writer or Enhance.

## Inputs

- immutable `InstrumentSegment` values produced by M10;
- exact K01 Factory registry and remap evidence;
- complete `CC00.CC32.PC` snapshots or explicit M10 incomplete/no-program
  states.

No value is inherited from another channel, CV, track, file or Style element.
Missing CC00/CC32 values are not replaced with GM defaults.

## Implemented statuses

- `FACTORY_CONFIRMED`: exact K01 address or one unambiguous official remap;
- `USER_SLOT_CONFIRMED`: User Drum Kit location only, with unknown name/content;
- `UNKNOWN`: complete address without K01, User-range or usable remap evidence;
- `CONFLICT`: named address overlapping official remap evidence;
- `INCOMPLETE_ADDRESS`: Program Change exists but bank address is incomplete;
- `NO_PROGRAM`: events occur before a Program Change.

Every result records a stable rule ID, evidence status, requested address,
effective address when known, Factory entry, remap evidence, warnings,
protections and the exact original M10 segment.

The original segment retains `identity_status="UNRESOLVED"`; K02 returns a
separate immutable identity value.

## Remap behavior

- `120.0.59` is confirmed through the non-overlapping part of the official
  remap row and reports effective address `120.0.56 — SFX Kit GM`.
- Both requested and effective addresses remain visible.
- No MIDI address is rewritten.
- `120.0.57` and `120.0.58` return `CONFLICT`; named and remap candidates are
  both preserved and no winner is selected.

## Dedicated tests

File: `tests/test_instrument_identity_resolver.py`

The six tests pass through the real `StandardMidiLoader` and M10 segmenter
before K02. They cover exact Factory Sound/Drum Kit, User location, unknown
complete address, incomplete address, no program, confirmed remap, 57–58
conflict, batch resolution and input/source immutability.

```bash
python -m pytest -q tests/test_instrument_identity_resolver.py
```

Dedicated result: **6 passed**.

## Full Factory corpus integration

The existing M08–M10 corpus test now also resolves every M10 segment through
K02. Across 3,211 MIDI files and 65,021 track slices:

- M10/K02 segments: **82,917**;
- `FACTORY_CONFIRMED`: **29,604**;
- `CONFLICT`: **15**;
- `INCOMPLETE_ADDRESS`: **6**;
- `NO_PROGRAM`: **53,292**;
- `USER_SLOT_CONFIRMED`: **0** in this Factory corpus;
- `UNKNOWN`: **0** in this Factory corpus;
- confirmed remap uses: **0** in this Factory corpus.

K02 deterministic digest:
`5245ec7ac6c66e7642c5748accdaa5a5188b807b11a2057b3651f0e4ef450227`.

The original Factory ZIP SHA-256 remains
`ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`.

Full command with the GUI display active:

```bash
DISPLAY=:104 python -m pytest -q
```

Full result: **89 passed, 3,233 subtests passed, 0 failed, 0 skipped** in
243.18 seconds.

## Next gate

K01 and K02 identity are now available. K03 remains NO-GO until an immutable
Policy/Change Plan, explicit user confirmation contract, Change Engine and
independent Verifier are implemented and tested.
