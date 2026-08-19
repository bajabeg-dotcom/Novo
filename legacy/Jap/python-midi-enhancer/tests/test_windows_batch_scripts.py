from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowsBatchScriptTests(unittest.TestCase):
    def read_batch(self, name: str) -> tuple[bytes, str]:
        raw = (ROOT / name).read_bytes()
        self.assertIn(b"\r\n", raw)
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"), f"{name} must use CRLF")
        return raw, raw.decode("utf-8")

    def test_install_uses_local_venv_and_pinned_local_k01_wheel(self) -> None:
        _raw, script = self.read_batch("install.bat")
        self.assertIn('set "ROOT=%~dp0"', script)
        self.assertIn("sys.version_info >= (3, 11)", script)
        self.assertIn('import tkinter', script)
        self.assertIn('-m venv "%ROOT%.venv"', script)
        self.assertIn('"%ROOT%.venv\\Scripts\\python.exe"', script)
        self.assertIn("--no-index", script)
        self.assertIn('--find-links="%ROOT%vendor"', script)
        self.assertIn("--require-hashes", script)
        self.assertIn('requirements-k01.txt', script)
        self.assertIn('requirements-optional.txt', script)
        self.assertIn('generate_pa800_factory.py" --check', script)
        self.assertIn('build_registry.py" --check', script)
        self.assertIn("len(load_factory_registry().entries) == 1071", script)
        self.assertNotIn("pip install --user", script.lower())
        self.assertNotIn("setx ", script.lower())

    def test_run_uses_only_venv_and_supports_console_and_check_modes(self) -> None:
        _raw, script = self.read_batch("run.bat")
        self.assertIn('.venv\\Scripts\\python.exe', script)
        self.assertIn('.venv\\Scripts\\pythonw.exe', script)
        self.assertIn('if /I "%~1"=="console"', script)
        self.assertIn('if /I "%~1"=="check"', script)
        self.assertIn('start "Python MIDI Enhancer"', script)
        self.assertIn('midi_gui.py', script)
        self.assertIn('Prvo pokreni install.bat', script)
        self.assertNotIn("python midi_gui.py", script.lower())

    def test_scripts_never_reference_midi_output_or_destructive_commands(self) -> None:
        combined = "\n".join(
            self.read_batch(name)[1].lower() for name in ("install.bat", "run.bat")
        )
        for forbidden in (
            "del ", "erase ", "format ", "rd /s", "rmdir /s",
            "_enhanced.mid", "change_engine", "apply_authorized=true",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
