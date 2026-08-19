from __future__ import annotations

import hashlib
import struct
import unittest

from measure_phrase_analyzer import AnalysisStatus, MeasurePhraseAnalyzer, analyze_style_track
from style_loader import StandardMidiLoader, StyleWorksLoader


def vlq(value: int) -> bytes:
    result = [value & 0x7F]
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))


def track(events: list[bytes]) -> bytes:
    body = b"".join(events + [b"\x00\xff\x2f\x00"])
    return b"MTrk" + struct.pack(">I", len(body)) + body


def midi(tracks: list[bytes], division: int = 192) -> bytes:
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), division) + b"".join(tracks)


def meter(delta: int, numerator: int, denominator_power: int) -> bytes:
    return vlq(delta) + b"\xff\x58\x04" + bytes([numerator, denominator_power, 24, 8])


def tempo(delta: int, microseconds: int) -> bytes:
    return vlq(delta) + b"\xff\x51\x03" + microseconds.to_bytes(3, "big")


def note(delta: int, pitch: int, channel: int = 0, velocity: int = 90) -> bytes:
    return vlq(delta) + bytes([0x90 | channel, pitch, velocity])


def note_off(delta: int, pitch: int, channel: int = 0, velocity: int = 0) -> bytes:
    return vlq(delta) + bytes([0x80 | channel, pitch, velocity])


class MeasurePhraseAnalyzerTests(unittest.TestCase):
    def test_builds_tempo_meter_map_and_event_positions(self) -> None:
        conductor = track([
            meter(0, 4, 2), tempo(0, 500_000), tempo(384, 600_000), meter(384, 3, 2),
        ])
        music = track([note(0, 60), note(192, 62), note(576, 64), note(192, 65)])
        model = StandardMidiLoader().load_bytes(midi([conductor, music]))
        result = MeasurePhraseAnalyzer().analyze(model, window_end_tick=1344)

        self.assertEqual(result.status, AnalysisStatus.READY)
        self.assertEqual([round(point.bpm) for point in result.tempo_points], [120, 100])
        self.assertEqual([(point.tick, point.numerator) for point in result.meter_points], [(0, 4), (768, 3)])
        note_positions = [item for item in result.event_positions if item.kind == "note_on"]
        self.assertEqual(
            [(item.absolute_tick, item.measure, item.beat) for item in note_positions],
            [(0, 1, 1), (192, 1, 2), (768, 2, 1), (960, 2, 2)],
        )

    def test_detects_exact_repeated_measures(self) -> None:
        conductor = track([meter(0, 4, 2)])
        music = track([
            note(0, 60), note(192, 64), note(576, 60), note(192, 64),
        ])
        model = StandardMidiLoader().load_bytes(midi([conductor, music]))
        result = MeasurePhraseAnalyzer().analyze(model, window_end_tick=1536)

        self.assertEqual(len(result.repeated_measure_groups), 1)
        self.assertEqual(result.repeated_measure_groups[0].measures, (1, 2))

    def test_exact_repeat_includes_velocity_duration_and_note_off_semantics(self) -> None:
        conductor = track([meter(0, 4, 2), tempo(0, 500_000)])
        music = track([
            note(0, 60, velocity=30), note_off(96, 60, velocity=20),
            note(672, 60, velocity=120), note_off(96, 60, velocity=20),
            note(672, 60, velocity=30), note_off(192, 60, velocity=20),
            note(576, 60, velocity=30), note(96, 60, velocity=0),
        ])
        model = StandardMidiLoader().load_bytes(midi([conductor, music]))
        result = MeasurePhraseAnalyzer().analyze(model, window_end_tick=3072)

        self.assertEqual(result.repeated_measure_groups, ())

    def test_marks_long_gap_as_phrase_candidate_not_fact(self) -> None:
        conductor = track([meter(0, 4, 2)])
        music = track([note(0, 60), note(96, 62), note(672, 65)])
        model = StandardMidiLoader().load_bytes(midi([conductor, music]))
        result = MeasurePhraseAnalyzer().analyze(model, window_end_tick=1536)

        self.assertEqual(result.phrase_boundaries[0].reason, "FIRST_ONSET")
        self.assertEqual(result.phrase_boundaries[1].reason, "LONG_GAP_CANDIDATE")
        self.assertEqual(result.phrase_boundaries[1].confidence, 70)
        self.assertEqual(result.phrase_boundaries[1].tick, 768)

    def test_conflicting_meter_blocks_timeline(self) -> None:
        first = track([meter(0, 4, 2)])
        second = track([meter(0, 3, 2), note(0, 60)])
        model = StandardMidiLoader().load_bytes(midi([first, second]))
        result = MeasurePhraseAnalyzer().analyze(model, window_end_tick=768)

        self.assertEqual(result.status, AnalysisStatus.BLOCKED)
        self.assertEqual(result.measures, ())
        self.assertTrue(any("Konflikt Time Signature" in item for item in result.warnings))

    def test_conflicting_tempo_inside_window_blocks_timeline(self) -> None:
        first = track([meter(0, 4, 2), tempo(0, 500_000)])
        second = track([tempo(0, 600_000), note(0, 60)])
        model = StandardMidiLoader().load_bytes(midi([first, second]))
        result = MeasurePhraseAnalyzer().analyze(model, window_end_tick=768)

        self.assertEqual(result.status, AnalysisStatus.BLOCKED)
        self.assertTrue(any("Konflikt Set Tempo" in item for item in result.warnings))

    def test_conflict_after_window_does_not_block_timeline(self) -> None:
        first = track([meter(0, 4, 2), tempo(0, 500_000), tempo(768, 600_000)])
        second = track([note(0, 60), tempo(768, 700_000)])
        model = StandardMidiLoader().load_bytes(midi([first, second]))
        result = MeasurePhraseAnalyzer().analyze(model, window_end_tick=768)

        self.assertNotEqual(result.status, AnalysisStatus.BLOCKED)
        self.assertFalse(any("Konflikt Set Tempo" in item for item in result.warnings))
        self.assertEqual([(point.tick, round(point.bpm)) for point in result.tempo_points], [(0, 120)])

    def test_nonzero_window_preserves_meter_phase(self) -> None:
        conductor = track([meter(0, 4, 2), tempo(0, 500_000)])
        music = track([note(192, 60)])
        model = StandardMidiLoader().load_bytes(midi([conductor, music]))
        result = MeasurePhraseAnalyzer().analyze(
            model,
            musical_events=model.tracks[1].events,
            window_start_tick=192,
            window_end_tick=768,
        )

        position = next(item for item in result.event_positions if item.kind == "note_on")
        self.assertEqual((position.measure, position.beat, position.tick_in_beat), (1, 2, 0))
        self.assertEqual((result.measures[0].start_tick, result.measures[0].end_tick), (0, 768))

    def test_style_adapter_respects_valid_window_and_preserves_source_hash(self) -> None:
        source = midi([
            track([meter(0, 4, 2)]),
            track([
                b"\x00\xff\x03\x08ACC1 CV1",
                b"\x00\xff\x01\x051 Bar",
                note(0, 60, 11), note(768, 72, 11),
            ]),
        ])
        element = StyleWorksLoader().load_element_bytes(
            source, member_name="Styles/Test/Test_Var1.mid"
        )
        result = analyze_style_track(element, element.tracks[1])

        self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(sum(item.note_count for item in result.measure_contents), 1)
        self.assertEqual(result.window_end_tick, 768)
        self.assertIn("Analyze-only", result.protections[0])


if __name__ == "__main__":
    unittest.main()