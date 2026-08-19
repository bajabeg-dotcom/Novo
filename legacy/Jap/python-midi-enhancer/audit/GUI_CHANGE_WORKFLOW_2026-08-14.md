# G01/M05 bounded GUI Change workflow audit — 2026-08-14

## Decision

**PASS** for the automated bounded virtual-display scope.

Native Windows human UX/accessibility remains pending. Automatic Suggest and
Enhance remain disabled.

## Architecture

Musical/safety rules are not implemented in Tk callbacks. The GUI uses
`GuiChangeWorkflow`, a testable controller over M10, K01, K02, K03-P, P01/P02,
C01, V01 and W01.

Import remains Analyze-only. It may prepare the immutable segmentation and
identity model, but it does not create a preview, decision, execution request,
working copy or output file.

## Eligible options

The dialog exposes only:

- K02 `FACTORY_CONFIRMED` segments;
- K02 `USER_SLOT_CONFIRMED` Drum Kit locations;
- compatible exact K01 Factory targets.

Unknown, Conflict, Incomplete Address and No Program segments are not offered.
Factory Sound/Drum Kit type compatibility is enforced by the backend.

## Explicit GUI stages

1. User opens `Factory Sound…`.
2. User selects an M10/K02 segment.
3. User selects a K01 target.
4. `Preview exact diff` displays source/target address, segment/channel/ticks,
   risk, plan ID, every event-field old/new value and protections.
5. `USER Approve + Verify` shows a separate yes/no confirmation.
6. C01 creates only a working copy and V01 verifies it.
7. Save activates only after V01 PASS.
8. W01 proposes a new `_enhanced.mid` path and creates MIDI plus JSON.
9. Rollback requires another USER confirmation and is hash guarded.

Changing the selection invalidates previous preview/verification/save state.

## Backend tests

```bash
python -m pytest -q tests/test_gui_change_workflow.py
```

The five tests cover eligible segments and 1,006 compatible Sound targets,
full preview→approve→verify→save→rollback, stage/USER gates, Unknown exclusion
and shared Bank Select blocking.

## Real Tk test

Under the local Xvfb display, `tests/test_gui_runtime.py` now also:

- imports a Factory-addressed MIDI;
- enables the Factory button;
- opens the real Toplevel dialog;
- selects `121.0.34` as target;
- renders exact diff text;
- records USER approval;
- receives Verifier PASS;
- saves MIDI and JSON;
- rolls both outputs back;
- confirms the original source bytes remain unchanged.

Dedicated combined result:

```text
8 passed
```

Full command:

```bash
DISPLAY=:109 python -m pytest -q
```

Full result: **128 passed, 3,242 subtests passed, 0 failed, 0 skipped** in
236.29 seconds.

## Remaining boundary

This scope does not automatically rank or suggest Factory targets. The user
must choose the target. Native Windows scaling, keyboard navigation,
accessibility and real-device listening remain release tasks.
