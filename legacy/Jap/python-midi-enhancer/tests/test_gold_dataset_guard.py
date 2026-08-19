from __future__ import annotations

import io
import unittest
from pathlib import Path
from zipfile import ZipFile

from gold_dataset_guard import (
    DNA_SHA256,
    FACTORY_SHA256,
    GOLD_NESTED_SHA256,
    GoldDatasetError,
    GoldDatasetGuard,
    manifest_digest,
    render_manifest,
    validate_safe_zip_names,
)

FACTORY = Path("prism-uploads/Split Factory Styles.zip")
DNA = Path("prism-uploads/DNA.zip")
EXPECTED_EVENTS = 5_028_387
EXPECTED_NOTE_ONS = 2_263_727
EXPECTED_DIGEST = "62a0ac2ceb1ccf301c99e5a0c65a4d3febd3d6b46f14543b8b9e9898c60bb2e1"


class GoldDatasetGuardTests(unittest.TestCase):
    @unittest.skipUnless(FACTORY.is_file() and DNA.is_file(), "Factory/DNA izvori nisu dostupni")
    def test_real_sources_are_disjoint_deduplicated_and_read_only(self) -> None:
        factory_before = FACTORY.read_bytes()
        dna_before = DNA.read_bytes()
        manifest = GoldDatasetGuard().build(FACTORY, DNA)

        self.assertEqual(manifest.factory_source_sha256, FACTORY_SHA256)
        self.assertEqual(manifest.dna_source_sha256, DNA_SHA256)
        self.assertEqual(manifest.gold_nested_sha256, GOLD_NESTED_SHA256)
        self.assertEqual(manifest.factory_file_count, 3211)
        self.assertEqual(manifest.factory_unique_hash_count, 3187)
        self.assertEqual(manifest.factory_duplicate_groups, 24)
        self.assertEqual(manifest.gold_file_count, 182)
        self.assertEqual(manifest.gold_unique_file_count, 181)
        self.assertEqual(len(manifest.gold_duplicate_groups), 1)
        group = manifest.gold_duplicate_groups[0]
        self.assertEqual(
            {group.canonical_member, *group.duplicate_members},
            {
                "Gold DNA/JOZA TUZNI-KNINDZA UZIVO.MID",
                "Gold DNA/JOZA TUZNI-KNINDZA UZIVO (2).MID",
            },
        )
        self.assertEqual(manifest.cross_source_duplicate_hashes, ())
        self.assertEqual(len(manifest.excluded_containers), 1)
        self.assertEqual(
            manifest.excluded_containers[0].reason,
            "EXACT_FACTORY_ARCHIVE_CONTAMINATION_EXCLUDED",
        )
        self.assertEqual(manifest.evaluation_event_count, EXPECTED_EVENTS)
        self.assertEqual(manifest.evaluation_note_on_count, EXPECTED_NOTE_ONS)
        self.assertEqual(manifest.contamination_status, "PASS")
        self.assertEqual(manifest.split_status, "PASS_SOURCE_DISJOINT")
        self.assertEqual(manifest.m07_calibration_status, "BLOCKED")
        self.assertIn("human-verified", manifest.m07_calibration_reason)
        self.assertEqual(manifest_digest(manifest), EXPECTED_DIGEST)
        self.assertEqual(len({item.sha256 for item in manifest.evaluation_files}), 181)
        self.assertTrue(all(item.member_name.startswith("Gold DNA/") for item in manifest.evaluation_files))
        self.assertEqual(FACTORY.read_bytes(), factory_before)
        self.assertEqual(DNA.read_bytes(), dna_before)

    @unittest.skipUnless(FACTORY.is_file() and DNA.is_file(), "Factory/DNA izvori nisu dostupni")
    def test_manifest_generation_is_deterministic(self) -> None:
        first = GoldDatasetGuard().build(FACTORY, DNA)
        second = GoldDatasetGuard().build(FACTORY, DNA)
        self.assertEqual(render_manifest(first), render_manifest(second))
        self.assertEqual(manifest_digest(first), manifest_digest(second))

    def test_unsafe_zip_member_paths_are_rejected(self) -> None:
        for member in ("../escape.mid", "/absolute.mid", "safe/../../escape.mid"):
            with self.subTest(member=member):
                buffer = io.BytesIO()
                with ZipFile(buffer, "w") as archive:
                    archive.writestr(member, b"MThd")
                buffer.seek(0)
                with ZipFile(buffer) as archive:
                    with self.assertRaisesRegex(GoldDatasetError, "unsafe"):
                        validate_safe_zip_names(archive)


if __name__ == "__main__":
    unittest.main()
