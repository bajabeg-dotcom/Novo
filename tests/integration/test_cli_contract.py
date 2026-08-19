"""B7 -- ugovor CLI sloja.

Dvije tvrdnje koje moraju vaziti za svaku komandu:
  1. `--help` radi (komanda je registrovana i parser je ispravan);
  2. bez `--apply` ulazna datoteka se NE mijenja.

Druga tvrdnja je sustinska sigurnosna garancija cijelog projekta.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys

import pytest

COMMANDS = [
    "inspect", "validate", "rhythms", "parameters", "sysex", "initialization",
    "programs", "init-update", "sound-map", "drum-map", "expression", "curves",
    "export", "optimize", "velocity-shape", "velocity-auto", "articulation-auto",
    "performance-auto", "performance-batch", "auto", "project", "recover",
    "resample", "profile", "hardware", "database", "policy", "windows-scripts",
    "ui", "corpus", "reference-learn", "dna-learn", "dna-optimize", "dna-audit",
    "generator-train", "generator-generate", "artifacts", "harmony", "structure",
    "energy-map", "factory-song-plan", "factory-arrange-preview",
    "factory-retrieve", "factory-index", "factory-package",
]

READ_ONLY_COMMANDS = [
    "inspect", "validate", "rhythms", "parameters", "sysex",
    "initialization", "structure",
]


def run(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pa800_enhancer", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=180,
        check=False,
    )


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestRegistration:
    def test_top_level_help(self) -> None:
        result = run("--help")
        assert result.returncode == 0
        assert "pa800-enhancer" in result.stdout

    @pytest.mark.parametrize("command", COMMANDS)
    def test_command_help(self, command: str) -> None:
        result = run(command, "--help")
        assert result.returncode == 0, f"{command} --help nije uspjelo: {result.stderr[:200]}"

    def test_command_list_is_complete(self) -> None:
        """Ako neko doda komandu a ne i test, ovo pada."""
        result = run("--help")
        listed = {
            token.strip()
            for token in result.stdout.split("{", 1)[-1].split("}", 1)[0].split(",")
        }
        missing = listed - set(COMMANDS)
        assert not missing, f"neregistrovane u testu: {sorted(missing)}"


class TestReadOnlyContract:
    """Nijedna analiticka komanda ne smije dirati ulaznu datoteku."""

    @pytest.mark.parametrize("command", READ_ONLY_COMMANDS)
    def test_input_unchanged(self, command: str, multi_track_midi) -> None:
        before = sha256(multi_track_midi)
        run(command, str(multi_track_midi))
        assert sha256(multi_track_midi) == before, f"{command} je izmijenio ulaz"

    def test_preview_without_apply_leaves_input(self, multi_track_midi) -> None:
        before = sha256(multi_track_midi)
        run("optimize", str(multi_track_midi), "--grid", "16")
        assert sha256(multi_track_midi) == before

    def test_curves_preview_leaves_input(self, multi_track_midi) -> None:
        before = sha256(multi_track_midi)
        run("curves", str(multi_track_midi), "--tolerance", "1.0")
        assert sha256(multi_track_midi) == before


class TestApplyRequiresOutput:
    """--apply bez izlazne putanje mora pasti, ne prepisati original."""

    def test_optimize_apply_without_output_fails(self, multi_track_midi) -> None:
        before = sha256(multi_track_midi)
        result = run("optimize", str(multi_track_midi), "--grid", "16", "--apply")
        assert result.returncode != 0
        assert sha256(multi_track_midi) == before

    def test_curves_apply_without_output_fails(self, multi_track_midi) -> None:
        before = sha256(multi_track_midi)
        result = run("curves", str(multi_track_midi), "--tolerance", "1.0", "--apply")
        assert result.returncode != 0
        assert sha256(multi_track_midi) == before


class TestExportCommand:
    def test_export_preserve_is_byte_identical(self, multi_track_midi, tmp_path) -> None:
        out = tmp_path / "copy.mid"
        result = run("export", str(multi_track_midi), str(out), "--mode", "preserve")
        assert result.returncode == 0
        assert out.read_bytes() == multi_track_midi.read_bytes()

    def test_export_does_not_overwrite_input(self, multi_track_midi) -> None:
        before = sha256(multi_track_midi)
        run("export", str(multi_track_midi), str(multi_track_midi), "--mode", "preserve")
        assert sha256(multi_track_midi) == before


class TestErrorHandling:
    def test_missing_file_fails_cleanly(self, tmp_path) -> None:
        result = run("inspect", str(tmp_path / "nema.mid"))
        assert result.returncode != 0
        assert "Traceback" not in result.stderr, "greska mora biti obradjena, ne raw traceback"

    def test_non_midi_fails_cleanly(self, tmp_path) -> None:
        bogus = tmp_path / "bogus.mid"
        bogus.write_bytes(b"ovo nije midi")
        result = run("inspect", str(bogus))
        assert result.returncode != 0
        assert "Traceback" not in result.stderr
