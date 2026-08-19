# P01/P02 Immutable Change Plan and Policy audit — 2026-08-14

## Decision

- P01 Immutable Change Plan: **PASS** for the bounded data/decision scope.
- P02 Suggest Policy Engine: **PASS** for the bounded Suggest validation scope.

Neither module contains a MIDI writer or can authorize Apply. K03, Change
Engine and Verifier remain NO-GO.

## Exact mutation contract

Every proposed event-field mutation stores:

- physical track index and event index;
- absolute tick, event kind and MIDI channel;
- exact field (`data[0]` or `data[1]`);
- expected old and proposed new 7-bit value;
- SHA-256 of the raw source event;
- deterministic mutation ID.

No-op and out-of-range values are rejected. The same event field cannot occur
in multiple proposals in one plan.

## Proposal contract

Every proposal requires:

- stable proposal ID derived from source hash, rule and exact mutations;
- named rule ID and explicit version;
- title and description;
- input measurements with units and evidence status;
- evidence references;
- confidence percentage only for `INFERRED` evidence;
- risk level;
- expected difference and protections;
- explicit user confirmation requirement.

`CONFLICT`, `UNKNOWN`, `UNSUPPORTED` and `BLOCKING` cases cannot enter an
allowed Suggest plan.

## Decision separation

A plan starts in `SUGGEST` / `AWAITING_CONFIRMATION`. Only actor `USER` may add
an `APPROVE` or `REJECT` record, and the provided ISO-8601 timestamp must
include a timezone. Decisions are appended as immutable history.

An approved plan still has:

```text
apply_authorized = false
```

This is intentional: approval is evidence for a future Change Engine, not a
MIDI operation.

## Policy checks

The Policy Engine verifies:

- registered rule ID and matching version;
- rule maximum risk;
- whether inferred evidence is permitted;
- blocking evidence references;
- source event presence;
- event reference, tick, kind, channel, old value and raw SHA-256;
- allowed event kinds and fields;
- mandatory user confirmation.

A policy verdict only means `SUGGEST_ALLOWED` or `BLOCKED`; it never means
Apply.

## Tests

```bash
python -m pytest -q tests/test_change_plan.py tests/test_policy_engine.py
```

Dedicated result: **12 passed, 3 subtests passed**.

Full command:

```bash
DISPLAY=:105 python -m pytest -q
```

Full result: **101 passed, 3,236 subtests passed, 0 failed, 0 skipped** in
238.08 seconds.

Coverage includes deterministic IDs/JSON, explicit decision history, timezone
validation, inferred confidence rules, duplicate/no-op/range rejection,
changed or missing source events, evidence/risk/version/rule blocking and
persistent Apply prohibition.

## Next gate

The next module may create a K03 proposal only from a user-selected target
Factory address and an exact safe M10/K02 segment. It must still produce a
Suggest-only plan; writer and verifier remain separate future modules.
