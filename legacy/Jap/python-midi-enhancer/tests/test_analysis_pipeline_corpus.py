from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from instrument_identity_resolver import InstrumentIdentityResolver
from instrument_measurement_engine import measure_style_track
from instrument_segmenter import segment_style_track
from measure_phrase_analyzer import analyze_style_track
from style_loader import StyleWorksLoader, sha256_path


ROOT = Path(__file__).resolve().parents[1]
FACTORY_ARCHIVE = ROOT / "prism-uploads" / "Split Factory Styles.zip"
EXPECTED_SHA256 = "ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e"
EXPECTED_MIDI_FILES = 3_211
EXPECTED_TRACK_SLICES = 65_021
EXPECTED_SEGMENTS = 82_917
EXPECTED_M08 = {"BLOCKED": 50, "READY": 64_971}
EXPECTED_M09 = {"BLOCKED": 50, "PARTIAL": 37_382, "READY": 27_589}
EXPECTED_M10 = {"BLOCKED": 50, "PARTIAL": 64_971}
EXPECTED_RESULT_DIGEST = "a0a3d7a9b03aa53cf23bd3819e4168c04c11bf5a9dbd8f408f2978cd51a0b821"
EXPECTED_K02 = {
    "NO_PROGRAM": 53_292,
    "FACTORY_CONFIRMED": 29_604,
    "CONFLICT": 15,
    "INCOMPLETE_ADDRESS": 6,
}
EXPECTED_K02_VIA_REMAP = 0
EXPECTED_K02_DIGEST = "5245ec7ac6c66e7642c5748accdaa5a5188b807b11a2057b3651f0e4ef450227"


class AnalysisPipelineCorpusTests(unittest.TestCase):
    def test_m08_m09_m10_full_factory_corpus_is_deterministic_and_read_only(self) -> None:
        """Recompute registered M08-M10 outcomes for every Factory track slice."""

        self.assertTrue(FACTORY_ARCHIVE.is_file(), f"Nedostaje corpus: {FACTORY_ARCHIVE}")
        before_hash = sha256_path(FACTORY_ARCHIVE)
        self.assertEqual(before_hash, EXPECTED_SHA256)

        loader = StyleWorksLoader()
        m08_counts: Counter[str] = Counter()
        m09_counts: Counter[str] = Counter()
        m10_counts: Counter[str] = Counter()
        result_digest = hashlib.sha256()
        k02_digest = hashlib.sha256()
        k02_counts: Counter[str] = Counter()
        k02_via_remap = 0
        identity_resolver = InstrumentIdentityResolver()
        midi_files = 0
        track_slices = 0
        segments = 0

        with ZipFile(FACTORY_ARCHIVE) as archive:
            for member in archive.infolist():
                if member.is_dir() or not member.filename.lower().endswith((".mid", ".midi")):
                    continue
                element = loader.load_element_bytes(
                    archive.read(member), member_name=member.filename
                )
                midi_files += 1
                for track_slice in element.tracks:
                    timeline = analyze_style_track(element, track_slice)
                    measurement = measure_style_track(element, track_slice)
                    segmentation = segment_style_track(element, track_slice)
                    identity = identity_resolver.resolve(segmentation)
                    track_slices += 1
                    segments += len(segmentation.segments)
                    self.assertIs(identity.original_result, segmentation)
                    self.assertTrue(all(
                        segment.identity_status == "UNRESOLVED"
                        for segment in segmentation.segments
                    ))
                    for resolved in identity.identities:
                        k02_counts[resolved.status.value] += 1
                        k02_via_remap += int(resolved.via_remap)
                        k02_digest.update(json.dumps(
                            [
                                member.filename,
                                track_slice.physical_track,
                                track_slice.channel,
                                resolved.segment_ordinal,
                                resolved.status.value,
                                resolved.requested_address,
                                resolved.effective_address,
                                resolved.official_name,
                                resolved.rule_id,
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode("utf-8"))
                    m08_counts[timeline.status.value] += 1
                    m09_counts[measurement.status.value] += 1
                    m10_counts[segmentation.status.value] += 1
                    result_digest.update(json.dumps(
                        [
                            member.filename,
                            track_slice.physical_track,
                            track_slice.channel,
                            timeline.status.value,
                            measurement.status.value,
                            segmentation.status.value,
                            len(segmentation.segments),
                        ],
                        separators=(",", ":"),
                    ).encode("utf-8"))

        self.assertEqual(sha256_path(FACTORY_ARCHIVE), before_hash)
        self.assertEqual(midi_files, EXPECTED_MIDI_FILES)
        self.assertEqual(track_slices, EXPECTED_TRACK_SLICES)
        self.assertEqual(segments, EXPECTED_SEGMENTS)
        self.assertEqual(dict(m08_counts), EXPECTED_M08)
        self.assertEqual(dict(m09_counts), EXPECTED_M09)
        self.assertEqual(dict(m10_counts), EXPECTED_M10)
        self.assertEqual(result_digest.hexdigest(), EXPECTED_RESULT_DIGEST)
        self.assertEqual(dict(k02_counts), EXPECTED_K02)
        self.assertEqual(k02_via_remap, EXPECTED_K02_VIA_REMAP)
        self.assertEqual(k02_digest.hexdigest(), EXPECTED_K02_DIGEST)


if __name__ == "__main__":
    unittest.main()