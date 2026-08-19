# Import and repository audit — 2026-08-14

## Scope

This audit checks the Google Drive ZIP as actually extracted. It does not accept
`main.tex`, `MODULE_LOG.md`, or historical test counts as proof that code is
present or correct.

## Source archive

- Downloaded filename: `New Project (1).zip`
- SHA-256: `80e05a0c2ecedf70bd5785fcabf68d7c5ec687fa008c274969fa29f89431de20`
- ZIP entries: 39
- Unsafe absolute or `..` paths: 0
- Git metadata in archive: absent

The downloaded ZIP was removed after safe extraction to avoid duplicating a
62 MiB binary in the persistent workspace.

## Verified local evidence hashes

- `Pa800-201UM-ENG.pdf`: `b7df16fb0113d998a6411ea1c28971707021da8bc0b728aff98eafcceb57c71b`
- `Pa800_AE_E.pdf`: `6bcda56658a89eda31e9fe62a2b744df5cecaaf478e050d3256ad6440c0d413e`
- `Split Factory Styles.zip`: `ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`
- `DNA.zip`: `125f4486625db44f7cdd49bd670aff252a961c88ea14741ec970ec3ae5eec85a`
- `Valja.rar`: `57b54dc69fa6aee21cf71e4324a2d1588c97a6016f2ae01514df29e9c1b63e32`

## Actual code inventory at import

Present production files include M01–M10 implementations documented by the
archive, including:

- `midi_enhancer.py`, `midi_instruments.py`, `midi_gui.py`;
- `style_loader.py`, `context_classifier.py`;
- `measure_phrase_analyzer.py`, `instrument_measurement_engine.py`;
- `instrument_segmenter.py`;
- `registry/build_registry.py` and G00 registry data.

The archive does **not** contain a separate K01 Factory Sound/Drum Kit registry
generator, canonical K01 address JSON, K01 lookup module, K02 identity resolver,
or K01/K02 dedicated tests. Therefore K01 remains `FAIL`, K02 remains
`BLOCKED`, and K03/Change/Writer/Verifier/Enhance remain `NO-GO`.

## First complete test run

Command:

```bash
python -m pytest -q
```

Initial result: **59 passed, 2 failed** in 197.33 seconds.

Both failures were packaging/integrity defects, not MIDI algorithm failures:

1. two UTF-8 evidence filenames were stored in the ZIP without usable filename
   metadata and extracted as CP437 mojibake, so G00 could not find DATA-007;
2. `registry/MASTER_REGISTRY.md` lacked the generator's final newline.

The filenames were losslessly recovered by CP437-byte to UTF-8 decoding, and
the Markdown was regenerated with `registry/build_registry.py`. The ten G00
tests then passed.

After the A01 checkpoint and A02 inventory were added, the final command

```bash
python -m pytest -q
```

completed with **65 passed, 6 subtests passed, 0 failed, 0 skipped** in
195.99 seconds. This is RUN-008 in G00. It does not certify K01/K02, writer,
Enhance, hardware behavior, audio quality, or an interactive GUI session.

## GUI finding

`tkinter` imports successfully (`Tk 8.6`, Tcl `8.6.16`) and the registered GUI
import test passes. Creating a Tk root is blocked because this headless
workspace has no `$DISPLAY`. The old statement “tkinter is unavailable” is
false; only the interactive GUI runtime test remains blocked here.

## Documentation conflicts

- `main.tex` claims K01 is present and `PASS`, but no K01 production artifact or
  test exists in the imported snapshot.
- `main.tex` says `instrument_segmenter.py` is absent, while the file and nine
  dedicated tests are present.
- `MODULE_LOG.md` and the G00 registry correctly describe K01 as failed and M10
  as present, but historical GUI wording incorrectly blamed missing `tkinter`.

Narrative status text is being corrected to the actual snapshot. Historical
runs remain historical and are not treated as current proof.

## Git and persistence gate

A new local Git repository was initialized because the ZIP had no `.git`
metadata. Large evidence binaries remain local and hash-verified but are
ignored by Git to avoid duplicating roughly 62 MiB in Git objects.

A01 creates a checkpoint referencing a commit that contains a new Python probe
and its integration test. A01 must remain `PARTIAL` until the same checkpoint
passes after the next user message or workspace reload.

A02 provides an executable inventory comparison against `git ls-tree`. Its
presence result does not certify behavior or musical correctness.
