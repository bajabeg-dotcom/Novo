from __future__ import annotations

import unittest
from pathlib import Path

from tools.workspace_persistence_probe import verify_checkpoint

ROOT = Path(__file__).resolve().parents[1]


class WorkspacePersistenceTests(unittest.TestCase):
    def test_checkpointed_python_test_and_commit_are_present(self) -> None:
        result = verify_checkpoint(ROOT / "audit" / "PERSISTENCE_CHECKPOINT.json", ROOT)
        self.assertEqual(result["status"], "PASS")
        paths = {item["path"] for item in result["verified_files"]}
        self.assertIn("tools/workspace_persistence_probe.py", paths)
        self.assertIn("tests/test_workspace_persistence.py", paths)


if __name__ == "__main__":
    unittest.main()
