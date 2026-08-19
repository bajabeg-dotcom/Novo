from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from context_classifier import ContextClassifier, classify_style_element
from style_loader import StyleWorksLoader, sha256_path


ROOT = Path(__file__).resolve().parents[1]
FACTORY_ARCHIVE = ROOT / "prism-uploads" / "Split Factory Styles.zip"
EXPECTED_SHA256 = "ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e"
EXPECTED_MIDI_FILES = 3_211
EXPECTED_TRACK_SLICES = 65_021
EXPECTED_STATUS_COUNTS = {
    "CLASSIFIED": 27_121,
    "UNCERTAIN": 37_850,
    "BLOCKED": 50,
}


class ContextClassifierCorpusTests(unittest.TestCase):
    def test_full_factory_archive_reproduces_registered_m07_counts(self) -> None:
        """Recompute the M07 smoke result without modifying the source ZIP."""

        self.assertTrue(FACTORY_ARCHIVE.is_file(), f"Nedostaje corpus: {FACTORY_ARCHIVE}")
        before_hash = sha256_path(FACTORY_ARCHIVE)
        self.assertEqual(before_hash, EXPECTED_SHA256)

        loader = StyleWorksLoader()
        classifier = ContextClassifier()
        midi_files = 0
        track_slices = 0
        status_counts: Counter[str] = Counter()

        with ZipFile(FACTORY_ARCHIVE) as archive:
            for member in archive.infolist():
                if member.is_dir() or not member.filename.lower().endswith((".mid", ".midi")):
                    continue
                midi_files += 1
                element = loader.load_element_bytes(
                    archive.read(member), member_name=member.filename
                )
                results = classify_style_element(element, classifier)
                track_slices += len(results)
                status_counts.update(result.status.value for result in results)

        after_hash = sha256_path(FACTORY_ARCHIVE)
        self.assertEqual(after_hash, before_hash, "Classifier je promijenio izvorni ZIP")
        self.assertEqual(midi_files, EXPECTED_MIDI_FILES)
        self.assertEqual(track_slices, EXPECTED_TRACK_SLICES)
        self.assertEqual(dict(status_counts), EXPECTED_STATUS_COUNTS)


if __name__ == "__main__":
    unittest.main()