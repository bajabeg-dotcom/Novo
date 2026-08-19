# C01/V01 in-memory Change Engine and independent Verifier audit — 2026-08-14

## Decision

- C01 in-memory byte-preserving Change Engine: **PASS** for bounded scope.
- V01 independent Change Verifier: **PASS** for bounded scope.
- Disk writer and filesystem save gate: **NO-GO / not implemented**.

## Execution authorization

The engine requires both:

1. a fully USER-approved immutable Change Plan;
2. a separate `ChangeExecutionRequest` created by actor `USER` with an
   ISO-8601 timezone timestamp.

Plan ID, source SHA-256 and the exact approved proposal set must match. The
source byte hash is checked before a working copy exists.

## Byte-preserving engine

The first engine scope supports only:

- Control Change `data[1]`;
- Program Change `data[0]`.

It parses the original with `StandardMidiLoader`, independently locates track
bodies and exact event data offsets, verifies each raw event SHA-256 and old
value, and changes a `bytearray` copy. It does not reserialize tracks.

Therefore delta VLQ, explicit/running status form, event order, track length,
meta/SysEx data and all unapproved bytes remain unchanged.

The engine result is always:

```text
status = PENDING_VERIFICATION
verified = false
save_authorized = false
```

Rollback returns the exact original bytes and source SHA-256.

## Independent verifier

The verifier does not call the Change Engine byte-offset helpers. It reparses
both byte streams and independently verifies:

- source/output hashes;
- SMF format, division, tracks, header extra and trailing bytes;
- track/event counts and end ticks;
- event references, delta/absolute ticks, kind, status and running-status form;
- channel, meta type, payload and byte boundaries;
- exact old/new event data values;
- complete byte-diff offset set;
- applied-mutation records;
- absence of every unapproved raw-event change.

Only a clean PASS returns `verified_bytes` and `save_authorized=true`. A FAIL
returns no verified bytes.

## Tests

```bash
python -m pytest -q tests/test_change_engine_verifier.py
```

Dedicated result: **6 passed**.

Full command:

```bash
DISPLAY=:107 python -m pytest -q
```

Full result: **117 passed, 3,240 subtests passed, 0 failed, 0 skipped** in
241.59 seconds.

Covered cases:

- exact CC32 and Program Change patch in a working copy;
- successful independent verification;
- Note events unchanged;
- running-status CC32 preserved;
- exact rollback;
- unapproved plan and non-USER execution blocked;
- tampered source blocked before execution;
- additional unauthorized note-velocity byte detected;
- forged applied byte offset detected;
- truncated/unparsable output detected.

## Next gate

A future writer may accept only `VerificationResult.status == PASS` and its
`verified_bytes`. It must use a new output filename, atomic temporary-file
replacement, no-overwrite semantics, output SHA-256 and a JSON report. Until
that writer and filesystem failure tests pass, no MIDI file may be saved.
