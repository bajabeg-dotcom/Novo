# RX Specification (behavior)

Schema/data shape is in `docs/RX_MODEL.md`. This document defines the
RX Safety Engine's behavior — one of the highest-priority (P0)
components of the whole system, per the master spec.

## Pipeline position

```
INSTRUMENT IDENTITY
       |
   RX SAFETY
       |
  OPTIMIZATION
```

RX Safety runs **before** any velocity, timing, or humanization change
is applied. No optimizer stage may bypass it.

## Decision rules

For any proposed change to a note/event on a track whose instrument
identity has RX-capable articulations:

1. If the change could plausibly move a value into a range that
   triggers an RX articulation the arranger did not intend
   (unconfirmed context, or confirmed-but-contextually-wrong trigger):
   **BLOCK** the change, or substitute a value confirmed safe.
2. If the instrument identity itself is not confirmed as RX-capable
   (i.e. `UNKNOWN` or only weakly `INFERRED`), default to **BLOCK**
   any change that could interact with RX-relevant ranges — treat
   unknown as unsafe, not as "probably fine."
3. Only `CONFIRMED` RX mappings and `CONFIRMED` (or clearly
   evidence-backed `INFERRED`) safety contexts may result in
   **ALLOW**.

In short: `UNKNOWN` never triggers. Absence of evidence is treated as
absence of permission, not as permission by default.

## Relationship to Instrument Identity

RX Safety cannot run without a resolved `InstrumentIdentity` for the
segment being evaluated (see `docs/DATA_MODEL.md`). If identity is
`UNKNOWN`, RX Safety defaults to maximally conservative: preserve
original values, do not attempt RX-aware optimization on that segment.

## Not implemented in this Phase 0-1 skeleton

`src/korg_optimizer/rx/safety_engine.py` is a docstring-only stub. Real
logic depends on `mapping/gm_to_rx.py` (GM -> RX mapping table) and
`musical/instrument_identity.py`, both themselves stubs at this phase.
See `docs/ROADMAP.md` Phase 7-9.
