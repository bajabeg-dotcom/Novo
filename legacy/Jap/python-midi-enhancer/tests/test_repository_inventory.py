from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.repository_inventory import build_inventory


class RepositoryInventoryTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    def _fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "registry").mkdir()
        (root / "tests").mkdir()
        (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "tests" / "test_module.py").write_text(
            "def test_module_present():\n    assert True\n", encoding="utf-8"
        )
        registry = {
            "registry_version": "0.1.0",
            "records": [
                {
                    "id": "MOD-001",
                    "kind": "MODULE",
                    "external_id": "M01",
                    "title": "Fixture module",
                    "path": "module.py",
                    "implementation": {"state": "PASS"},
                },
                {
                    "id": "TEST-001",
                    "kind": "TEST",
                    "title": "test_module_present",
                    "path": "tests/test_module.py",
                    "implementation": {"state": "PASS"},
                },
            ],
        }
        (root / "registry" / "master_registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        (root / "MODULE_LOG.md").write_text(
            "# Log\n\n## Trenutno stanje\n\n"
            "| ID | Modul | Status |\n|---|---|---|\n"
            "| M01 | Fixture | PASS |\n\n## Next\n",
            encoding="utf-8",
        )
        self._git(root, "init", "-b", "main")
        self._git(root, "config", "user.name", "Test")
        self._git(root, "config", "user.email", "test@example.invalid")
        self._git(root, "add", ".")
        self._git(root, "commit", "-m", "fixture")
        return temporary, root

    def test_passes_when_documented_artifacts_are_in_git_tree(self) -> None:
        temporary, root = self._fixture()
        self.addCleanup(temporary.cleanup)
        report = build_inventory(
            root,
            root / "registry" / "master_registry.json",
            root / "MODULE_LOG.md",
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["unique_documented_artifacts"], 2)

    def test_reports_documented_file_missing_from_git_tree(self) -> None:
        temporary, root = self._fixture()
        self.addCleanup(temporary.cleanup)
        (root / "untracked.py").write_text("VALUE = 2\n", encoding="utf-8")
        registry_path = root / "registry" / "master_registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["records"][0]["path"] = "untracked.py"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        report = build_inventory(root, registry_path, root / "MODULE_LOG.md")
        self.assertEqual(report["status"], "FAIL")
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("MISSING_FROM_GIT_TREE", codes)

    def test_reports_module_log_id_missing_from_registry(self) -> None:
        temporary, root = self._fixture()
        self.addCleanup(temporary.cleanup)
        module_log = root / "MODULE_LOG.md"
        module_log.write_text(
            module_log.read_text(encoding="utf-8").replace(
                "| M01 | Fixture | PASS |", "| M01 | Fixture | PASS |\n| K99 | Missing | FAIL |"
            ),
            encoding="utf-8",
        )
        report = build_inventory(
            root,
            root / "registry" / "master_registry.json",
            module_log,
        )
        self.assertEqual(report["status"], "FAIL")
        finding = next(
            item for item in report["findings"]
            if item["code"] == "MODULE_LOG_ID_MISSING_FROM_REGISTRY"
        )
        self.assertEqual(finding["record_ids"], ("K99",))


if __name__ == "__main__":
    unittest.main()
