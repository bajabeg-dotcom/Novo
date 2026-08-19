# M05 GUI runtime audit — 2026-08-14

## Decision

**PASS** for the automated Tk virtual-display scope.

Certification remains **PARTIAL** for native desktop packaging, human UX,
accessibility and real user interaction.

## Environment

- OS: Debian GNU/Linux 13 (trixie)
- Python Tk/Tcl: 8.6 / 8.6
- system `$DISPLAY`: absent
- system Xvfb: absent
- free workspace storage before setup: approximately 20 GiB

A workspace-only Xvfb runtime was created from official Debian apt packages.
No system package was installed or modified. Package files, extracted content
and the runtime manifest are under `loaded-data/xvfb-runtime/`, which is
runtime data and not production source code.

Packages:

- `xvfb` 2:21.1.16-1.3+deb13u3
- `xserver-common` 2:21.1.16-1.3+deb13u3
- `xkb-data` 2.42-1
- `x11-xkb-utils` 7.7+9
- `libxfont2` 1:2.0.6-1+deb13u1
- `libfontenc1` 1:1.1.8-1+b2
- `libunwind8` 1.8.1-0.1

Every downloaded `.deb` SHA-256 is recorded in
`loaded-data/xvfb-runtime/MANIFEST.json`.

The Debian Xvfb binary contains compiled absolute `/usr/bin` and
`/usr/share/X11/xkb` paths. A local copy was patched only to use `/tmp/xb` and
`/tmp/xkb` symlinks pointing to the extracted workspace runtime. Original Xvfb
SHA-256:
`14e8ec7d8209bbaf105f9ade27a80b65f01709346690d18fbadb6116ada34912`.
Local patched copy SHA-256:
`55f1307458dca0da274dd54b8d3f6532ee5ca8b1c6f617b5176e2fca55276e22`.

## Direct Tk smoke result

Xvfb ran on display `:102`. The test created:

- a real `tkinter.Tk` root;
- window title `Prism MIDI Enhancer`;
- geometry `1360x900`;
- one `MidiEnhancerApp` instance;
- all 16 `TrackCard` widgets.

The root was updated and destroyed cleanly.

## Automated tests

File: `tests/test_gui_runtime.py`

The tests use a real Tk display and application widgets. They verify:

1. Format 0 analysis is rendered into summary fields and channel slots;
2. all 16 cards exist and the first card receives the analyzed note;
3. JSON export writes a new report and leaves the MIDI bytes unchanged;
4. Format 2 is shown as `PER SEQUENCE` and `PARTIAL / READ-ONLY`;
5. Format 2 cards are labeled `Sequence 1` and `Sequence 2`.

Command:

```bash
DISPLAY=:102 python -m pytest -q tests/test_gui_runtime.py tests/test_midi_modules.py
```

Initial result: **5 passed**, including **2/2 real GUI runtime tests**.

Full command with the display active:

```bash
DISPLAY=:102 python -m pytest -q
```

Result: **76 passed, 3,229 subtests passed, 0 failed, 0 skipped** in
234.64 seconds.

## Remaining scope

This test does not simulate every file dialog, long-running background import,
window-manager behavior, screen scaling, keyboard navigation, accessibility,
native installer or a human usability review. Those remain release tasks and
do not block independent K01 read-only development.
