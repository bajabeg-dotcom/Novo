from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from pa800_registry import (
    EXPECTED_TOTAL_ADDRESSES,
    Pa800RegistryError,
    load_factory_registry,
)
from registry.generate_pa800_factory import (
    DEFAULT_MANUAL,
    DEFAULT_OUTPUT,
    K01GenerationError,
    generate_registry,
    render_registry,
)


class Pa800FactoryRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        load_factory_registry.cache_clear()

    def test_generator_reproduces_canonical_json_exactly(self) -> None:
        generated = render_registry(generate_registry(DEFAULT_MANUAL))
        canonical = DEFAULT_OUTPUT.read_text(encoding="utf-8")
        self.assertEqual(generated, canonical)
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            first.write_text(generated, encoding="utf-8")
            second.write_text(render_registry(generate_registry(DEFAULT_MANUAL)), encoding="utf-8")
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_counts_addresses_and_sources_are_complete(self) -> None:
        data = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        counts = data["counts"]
        self.assertEqual(counts["factory_sound_addresses"], 1006)
        self.assertEqual(counts["named_drum_kit_addresses"], 65)
        self.assertEqual(counts["unique_drum_kit_names"], 64)
        self.assertEqual(counts["total_unique_addresses"], EXPECTED_TOTAL_ADDRESSES)
        addresses = [item["address"] for item in data["records"]]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertEqual(sum(item["kind"] == "FACTORY_SOUND" for item in data["records"]), 1006)
        self.assertEqual(sum(item["kind"] == "FACTORY_DRUM_KIT" for item in data["records"]), 65)
        for record in data["records"]:
            self.assertTrue(record["sources"])
            for source in record["sources"]:
                self.assertEqual(source["pdf_page"], source["printed_page"] + 4)

    def test_read_only_lookup_uses_full_address(self) -> None:
        registry = load_factory_registry()
        bass = registry.lookup(121, 0, 33)
        kit = registry.lookup_address("120.0.5")
        self.assertIsNotNone(bass)
        self.assertEqual(bass.name, "Finger Bass GM")
        self.assertEqual(bass.kind, "FACTORY_SOUND")
        self.assertEqual(bass.printed_pages, (282,))
        self.assertIsNotNone(kit)
        self.assertEqual(kit.name, "Standard Kit RX1")
        self.assertEqual(kit.kind, "FACTORY_DRUM_KIT")
        self.assertEqual(kit.printed_pages, (295,))
        self.assertEqual(len(registry.entries), EXPECTED_TOTAL_ADDRESSES)
        with self.assertRaises(FrozenInstanceError):
            bass.name = "Changed"  # type: ignore[misc]
        with self.assertRaises(Pa800RegistryError):
            registry.lookup_address("121.0")
        with self.assertRaises(Pa800RegistryError):
            registry.lookup(128, 0, 0)

    def test_drum_duplicate_name_is_preserved_as_two_addresses(self) -> None:
        registry = load_factory_registry()
        first = registry.lookup_address("120.0.48")
        second = registry.lookup_address("120.0.49")
        self.assertEqual(first.name, "Orchestra Kit GM")
        self.assertEqual(second.name, "Orchestra Kit GM")
        self.assertNotEqual(first.address, second.address)

    def test_57_58_named_remap_overlap_remains_conflict(self) -> None:
        registry = load_factory_registry()
        self.assertEqual(registry.lookup_address("120.0.57").name, "SFX Kit 2")
        self.assertEqual(registry.lookup_address("120.0.58").name, "Synth Kit")
        rule_57 = registry.remap_evidence_for_pc(57)
        rule_59 = registry.remap_evidence_for_pc(59)
        self.assertEqual(len(rule_57), 1)
        self.assertEqual(rule_57[0].status, "CONFLICT")
        self.assertEqual(rule_57[0].conflicts_with_named_pcs, (57, 58))
        self.assertEqual(rule_57[0].non_conflicting_source_pcs, (59, 60, 61, 62, 63))
        self.assertEqual(rule_57[0].policy, "PRESERVE_NAMED_DO_NOT_APPLY_REMAP")
        self.assertEqual(rule_59, rule_57)

    def test_user_range_confirms_location_not_content(self) -> None:
        registry = load_factory_registry()
        self.assertTrue(registry.is_user_drum_slot(120, 64, 0))
        self.assertTrue(registry.is_user_drum_slot(120, 64, 63))
        self.assertFalse(registry.is_user_drum_slot(120, 64, 64))
        self.assertIsNone(registry.lookup(120, 64, 0))

    def test_wrong_manual_hash_is_rejected(self) -> None:
        source = DEFAULT_MANUAL.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed.pdf"
            changed.write_bytes(source[:-1] + bytes([source[-1] ^ 0x01]))
            with self.assertRaisesRegex(K01GenerationError, "SHA-256 mismatch"):
                generate_registry(changed)


if __name__ == "__main__":
    unittest.main()
