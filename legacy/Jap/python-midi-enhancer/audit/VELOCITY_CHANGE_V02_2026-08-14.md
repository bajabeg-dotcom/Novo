# V02 Specialized S01 Note On Velocity Apply audit — 2026-08-14

## Decision

**PASS** for the bounded, explicit USER-acknowledged S01 velocity scope.

Automatic velocity Apply and automatic Enhance remain prohibited.

## Authorization chain

V02 requires all of the following:

1. user explicitly enabled S01;
2. exact R01 profile/context match;
3. P02 allowed the S01 Suggest plan;
4. user approved the immutable plan;
5. user separately acknowledged unknown velocity-switch/RX threshold risk;
6. user created a specialized execution request.

A generic execution request still fails with `S01 Note On Apply lacks rule
authorization`.

The specialized request records:

```text
authorized_rule_ids = S01.PROFILE_VELOCITY_OUTLIER
risk_acknowledgements = UNKNOWN_VELOCITY_SWITCH_RX_THRESHOLDS
```

## Independent engine/verifier gates

Both C01 and V01 enforce specialized constraints:

- event kind must be `note_on`;
- field must be `data[1]`;
- rule must be S01;
- specialized rule authorization must exist;
- risk acknowledgement must exist;
- old/new velocity must remain in 1–127;
- Note On zero/off semantics cannot change;
- adjustment cannot exceed 8 units;
- one execution cannot exceed 32 velocity mutations.

V01 independently rejects a result if the acknowledgement is removed after C01
execution.

## Byte preservation

The end-to-end test changes velocities 20→28 and 120→112. The second Note On
uses running status, which remains running status after the byte patch. Pitch,
note count, order, timing and Note Off events remain identical.

## W01 report and rollback

The verified result can be saved only through W01. The JSON report includes the
authorized rule and risk acknowledgement. Filesystem rollback removes the new
MIDI/JSON and the original source remains byte-identical.

## Tests

```bash
python -m pytest -q tests/test_velocity_change_scope.py
```

Result: **4 passed, 2 subtests passed**.

Full command:

```bash
DISPLAY=:113 python -m pytest -q
```

Full result: **146 passed, 3,257 subtests passed, 0 failed, 0 skipped** in
391.22 seconds.

Coverage includes full S01→V02→C01→V01→W01→rollback, missing acknowledgement,
generic-request block, velocity zero, adjustment above 8 and forged
acknowledgement detection.

## Remaining boundary

V02 is not yet connected to the GUI. GUI integration must display the exact
profile, p10/p90, event diff, risk warning and a dedicated acknowledgement
control separate from ordinary plan approval.
