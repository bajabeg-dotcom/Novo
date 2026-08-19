from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "registry"
SPEC = importlib.util.spec_from_file_location(
    "build_registry", REGISTRY_DIR / "build_registry.py"
)
assert SPEC is not None and SPEC.loader is not None
build_registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_registry)


class MasterRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = build_registry.load_registry(REGISTRY_DIR / "master_registry.json")

    def test_registry_validates_and_ids_are_unique(self) -> None:
        records = build_registry.validate_registry(self.data)
        ids = [record["id"] for record in records]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("MOD-010", ids)
        self.assertIn("EVID-001", ids)

    def test_all_references_resolve(self) -> None:
        records = build_registry.validate_registry(self.data)
        ids = {record["id"] for record in records}
        for record in records:
            self.assertTrue(set(record["refs"]) <= ids, record["id"])

    def test_duplicate_and_unknown_reference_are_rejected(self) -> None:
        duplicate = copy.deepcopy(self.data)
        duplicate["records"].append(copy.deepcopy(duplicate["records"][0]))
        with self.assertRaisesRegex(build_registry.RegistryError, "duplicate id"):
            build_registry.validate_registry(duplicate)

        dangling = copy.deepcopy(self.data)
        dangling["records"][0]["refs"] = ["MISSING-999"]
        with self.assertRaisesRegex(build_registry.RegistryError, "unknown refs"):
            build_registry.validate_registry(dangling)

    def test_four_status_axes_are_independent_and_required(self) -> None:
        records = build_registry.validate_registry(self.data)
        gui = next(record for record in records if record["id"] == "MOD-005")
        self.assertEqual(gui["implementation"]["state"], "PASS")
        self.assertEqual(gui["validation"]["state"], "PASS")
        self.assertEqual(gui["certification"]["state"], "PARTIAL")

        missing_axis = copy.deepcopy(self.data)
        del missing_axis["records"][0]["certification"]
        with self.assertRaisesRegex(build_registry.RegistryError, "missing"):
            build_registry.validate_registry(missing_axis)

    def test_idea_catalogs_cannot_look_like_active_rules(self) -> None:
        records = build_registry.validate_registry(self.data)
        catalogs = [record for record in records if record["lifecycle"] == "IDEA_CATALOG"]
        self.assertEqual({record["id"] for record in catalogs}, {"DATA-007", "DATA-008"})
        for record in catalogs:
            self.assertEqual(record["kind"], "RESOURCE")
            self.assertEqual(record["implementation"]["state"], "NONE")
            self.assertEqual(record["validation"]["state"], "NONE")
            self.assertEqual(record["certification"]["state"], "NONE")

        activated = copy.deepcopy(self.data)
        catalog = next(
            record for record in activated["records"] if record["id"] == "DATA-007"
        )
        catalog["implementation"]["state"] = "PASS"
        with self.assertRaisesRegex(build_registry.RegistryError, "must remain NONE"):
            build_registry.validate_registry(activated)

    def test_kind_namespace_is_enforced(self) -> None:
        invalid = copy.deepcopy(self.data)
        invalid["records"][0]["id"] = "MOD-999"
        for record in invalid["records"]:
            record["refs"] = ["MOD-999" if ref == "DATA-001" else ref for ref in record["refs"]]
        with self.assertRaisesRegex(build_registry.RegistryError, "requires DATA- prefix"):
            build_registry.validate_registry(invalid)

    def test_workspace_paths_hashes_and_test_tokens_are_verified(self) -> None:
        build_registry.validate_workspace(self.data, ROOT)

        wrong_hash = copy.deepcopy(self.data)
        resource = next(
            record for record in wrong_hash["records"] if record["id"] == "DATA-001"
        )
        resource["sha256"] = "0" * 64
        with self.assertRaisesRegex(build_registry.RegistryError, "sha256 mismatch"):
            build_registry.validate_workspace(wrong_hash, ROOT)

        missing_test = copy.deepcopy(self.data)
        test = next(
            record for record in missing_test["records"] if record["id"] == "TEST-001"
        )
        test["title"] = "test_method_that_does_not_exist"
        with self.assertRaisesRegex(build_registry.RegistryError, "test token"):
            build_registry.validate_workspace(missing_test, ROOT)

    def test_dna_bundle_factory_member_is_exact_registered_duplicate(self) -> None:
        factory = next(
            record for record in self.data["records"] if record["id"] == "DATA-003"
        )
        with ZipFile(ROOT / "prism-uploads" / "DNA.zip") as archive:
            member_hash = hashlib.sha256(
                archive.read("Split Factory Styles.zip")
            ).hexdigest()
        self.assertEqual(member_hash, factory["sha256"])

    def test_schema_is_local_documentation_of_required_axes(self) -> None:
        schema = json.loads((REGISTRY_DIR / "schema.json").read_text(encoding="utf-8"))
        required = set(schema["$defs"]["record"]["required"])
        self.assertTrue({"evidence", "implementation", "validation", "certification"} <= required)
        self.assertFalse(schema["$defs"]["record"]["additionalProperties"])

    def test_generated_markdown_is_current_and_deterministic(self) -> None:
        expected = build_registry.render_markdown(self.data)
        actual = (REGISTRY_DIR / "MASTER_REGISTRY.md").read_text(encoding="utf-8")
        self.assertEqual(actual, expected)
        self.assertEqual(expected, build_registry.render_markdown(self.data))
        self.assertIn("IDEA_CATALOG", actual)
        self.assertIn("Četiri statusne osi", actual)


if __name__ == "__main__":
    unittest.main()