# Windows install/run scripts audit — 2026-08-14

## Decision

- `install.bat`: implementation/static validation **PASS**;
- `run.bat`: implementation/static validation **PASS**;
- real Windows `cmd.exe`/Tk execution: **PARTIAL / pending user machine**.

The scripts do not contain MIDI writer, Change Engine or Enhance commands.

## install.bat

The installer:

1. changes to its own project directory;
2. finds `py -3` or `python`;
3. requires Python 3.11 or newer;
4. verifies `tkinter` before creating the environment;
5. creates project-local `.venv`;
6. uses only `.venv\Scripts\python.exe` afterwards;
7. installs pinned `pypdf 6.16.0` from local `vendor/` with `--no-index`,
   `--require-hashes` and `requirements-k01.txt`;
8. optionally installs `numpy`, `mido`, `pretty_midi` and `music21`;
9. supports `install.bat minimal` to skip optional packages;
10. runs K01 generator and G00 registry `--check`;
11. imports Tk/GUI and verifies that K01 exposes 1,071 entries;
12. writes an installation marker only after all mandatory gates pass.

Optional library failure is reported as a warning because the built-in parser
and GUI can work without those libraries. Mandatory K01/registry/Tk failure
blocks installation completion.

## run.bat

Default mode launches the GUI with project-local `pythonw.exe`.

Additional modes:

```bat
run.bat console
run.bat check
```

`console` keeps error output visible. `check` reruns K01, G00 and GUI/K01 smoke
checks. The launcher refuses to use a global Python when `.venv` is missing.

## Static tests

```bash
python -m pytest -q tests/test_windows_batch_scripts.py
```

Result: **3 passed**.

The tests verify Windows CRLF encoding, Python/Tk/version gates, local venv,
local hash-pinned K01 wheel, optional dependency path, registry checks,
pythonw/console/check launch modes and absence of destructive/MIDI-output
commands.

## User validation required

On the Windows machine:

1. extract the complete project to a normal directory;
2. install official Python 3.11+ with “Add Python to PATH”;
3. run `install.bat`;
4. retain the complete console output if a gate fails;
5. run `run.bat check`;
6. run `run.bat console` for the first GUI launch.

D01/D02 can receive full runtime certification only after those commands pass
on the actual Windows environment.
