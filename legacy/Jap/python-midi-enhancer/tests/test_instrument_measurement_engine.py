from __future__ import annotations

import hashlib
import struct
import unittest

from instrument_measurement_engine import (
    InstrumentMeasurementEngine,
    MeasurementInput,
    MeasurementStatus,
    measure_style_track,
)
from measure_phrase_analyzer import MeasurePhraseAnalyzer
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


def meter(delta: int = 0) -> bytes:
    return vlq(delta) + b"\xff\x58\x04\x04\x02\x18\x08"


def tempo(delta: int = 0) -> bytes:
    return vlq(delta) + b"\xff\x51\x03\x07\xa1\x20"


def note_on(delta: int, pitch: int, velocity: int, channel: int = 0) -> bytes:
    return vlq(delta) + bytes([0x90 | channel, pitch, velocity])


def note_off(delta: int, pitch: int, channel: int = 0) -> bytes:
    return vlq(delta) + bytes([0x80 | channel, pitch, 0])


class InstrumentMeasurementEngineTests(unittest.TestCase):
    def test_derives_velocity_duration_polyphony_and_controllers(self) -> None:
        source = midi([
            track([meter(), tempo()]),
            track([
                note_on(0, 60, 40), note_on(0, 64, 80),
                b"\x00\xb0\x40\x7f", note_off(192, 60), note_off(0, 64),
                note_on(0, 67, 100), b"\x00\xe0\x00\x40",
                b"\x00\xa0\x43\x20", b"\x00\xd0\x30", note_off(96, 67),
            ]),
        ])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentMeasurementEngine().measure(MeasurementInput(
            model.sha256, model.tracks[1].events, model.ticks_per_beat, window_end_tick=768
        ))

        self.assertEqual(result.status, MeasurementStatus.READY)
        self.assertEqual(result.note_count, 3)
        self.assertEqual(result.closed_note_count, 3)
        self.assertAlmostEqual(result.velocity.mean or 0, 220 / 3)
        self.assertEqual(result.duration_beats.median, 1.0)
        self.assertEqual(result.maximum_sounding_polyphony, 2)
        self.assertEqual(result.maximum_exact_onset_polyphony, 2)
        self.assertEqual(result.controller_measurements[0].controller, 64)
        self.assertEqual(result.pitch_bend_count, 1)
        self.assertEqual(result.poly_aftertouch_count, 1)
        self.assertEqual(result.channel_aftertouch_count, 1)

    def test_rejects_foreign_or_mismatched_timeline_provenance(self) -> None:
        source = midi([
            track([meter(), tempo()]),
            track([note_on(0, 60, 80), note_off(96, 60)]),
        ])
        model = StandardMidiLoader().load_bytes(source)
        events = model.tracks[1].events
        timeline = MeasurePhraseAnalyzer().analyze(
            model, musical_events=events, window_end_tick=768
        )
        engine = InstrumentMeasurementEngine()

        cases = (
            MeasurementInput(
                "0" * 64, events, model.ticks_per_beat,
                window_end_tick=768, timeline=timeline,
            ),
            MeasurementInput(
                model.sha256, events, 96,
                window_end_tick=768, timeline=timeline,
            ),
            MeasurementInput(
                model.sha256, events, model.ticks_per_beat,
                window_end_tick=384, timeline=timeline,
            ),
        )
        for case in cases:
            with self.subTest(case=case):
                result = engine.measure(case)
                self.assertEqual(result.status, MeasurementStatus.BLOCKED)
                self.assertEqual(result.measure_measurements, ())
                self.assertEqual(result.phrase_measurements, ())
                self.assertTrue(any("ne pripada" in item for item in result.warnings))

    def test_multitrack_notes_are_paired_per_track_and_profile_is_blocked(self) -> None:
        source = midi([
            track([note_on(0, 60, 70), note_off(192, 60)]),
            track([note_on(96, 60, 90), note_off(192, 60)]),
        ])
        model = StandardMidiLoader().load_bytes(source)
        events = model.tracks[0].events + model.tracks[1].events
        result = InstrumentMeasurementEngine().measure(MeasurementInput(
            model.sha256, events, model.ticks_per_beat, window_end_tick=384
        ))

        self.assertEqual(result.status, MeasurementStatus.BLOCKED)
        self.assertEqual(result.closed_note_count, 2)
        self.assertEqual(result.duration_ticks.minimum, 192)
        self.assertEqual(result.duration_ticks.maximum, 192)
        self.assertTrue(any("više fizičkih trackova" in item for item in result.warnings))

    def test_density_requires_explicit_confirmed_window_end(self) -> None:
        source = midi([track([note_on(0, 60, 80), note_off(192, 60)])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentMeasurementEngine().measure(MeasurementInput(
            model.sha256, model.tracks[0].events, model.ticks_per_beat
        ))

        self.assertEqual(result.status, MeasurementStatus.PARTIAL)
        self.assertIsNone(result.density_per_beat)
        self.assertTrue(any("Gustoća nije izvedena" in item for item in result.warnings))

    def test_creates_measure_profiles_from_m08_timeline(self) -> None:
        source = midi([
            track([meter(), tempo()]),
            track([
                note_on(0, 60, 50), note_off(96, 60),
                note_on(672, 62, 70), note_off(192, 62),
            ]),
        ])
        model = StandardMidiLoader().load_bytes(source)
        events = model.tracks[1].events
        timeline = MeasurePhraseAnalyzer().analyze(model, musical_events=events, window_end_tick=1536)
        result = InstrumentMeasurementEngine().measure(MeasurementInput(
            model.sha256, events, model.ticks_per_beat, window_end_tick=1536, timeline=timeline
        ))

        self.assertEqual([item.note_count for item in result.measure_measurements], [1, 1])
        self.assertEqual(result.measure_measurements[0].duration_beats.mean, 0.5)
        self.assertEqual(result.measure_measurements[1].velocity.mean, 70)

    def test_creates_phrase_profiles_from_inferred_boundaries(self) -> None:
        source = midi([
            track([meter(), tempo()]),
            track([
                note_on(0, 60, 50), note_off(48, 60),
                note_on(48, 62, 60), note_off(48, 62),
                note_on(624, 65, 90), note_off(96, 65),
            ]),
        ])
        model = StandardMidiLoader().load_bytes(source)
        events = model.tracks[1].events
        timeline = MeasurePhraseAnalyzer().analyze(model, musical_events=events, window_end_tick=1536)
        result = InstrumentMeasurementEngine().measure(MeasurementInput(
            model.sha256, events, model.ticks_per_beat, window_end_tick=1536, timeline=timeline
        ))

        self.assertEqual(len(result.phrase_measurements), 2)
        self.assertEqual(result.phrase_measurements[0].note_count, 2)
        self.assertEqual(result.phrase_measurements[1].boundary_reason, "LONG_GAP_CANDIDATE")
        self.assertEqual(result.phrase_measurements[1].boundary_confidence, 70)

    def test_unmatched_notes_make_profile_partial(self) -> None:
        source = midi([track([meter(), tempo()]), track([
            note_off(0, 59), note_on(0, 60, 80),
        ])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentMeasurementEngine().measure(MeasurementInput(
            model.sha256, model.tracks[1].events, model.ticks_per_beat, window_end_tick=768
        ))

        self.assertEqual(result.status, MeasurementStatus.PARTIAL)
        self.assertEqual(result.open_note_count, 1)
        self.assertEqual(result.orphan_note_off_count, 1)
        self.assertEqual(result.duration_beats.count, 0)

    def test_blocked_timeline_preserves_global_metrics_but_blocks_use(self) -> None:
        source = midi([
            track([meter(), tempo()]),
            track([b"\x00\xff\x58\x04\x03\x02\x18\x08", note_on(0, 60, 80)]),
        ])
        model = StandardMidiLoader().load_bytes(source)
        events = model.tracks[1].events
        timeline = MeasurePhraseAnalyzer().analyze(model, musical_events=events, window_end_tick=768)
        result = InstrumentMeasurementEngine().measure(MeasurementInput(
            model.sha256, events, model.ticks_per_beat, window_end_tick=768, timeline=timeline
        ))

        self.assertEqual(result.status, MeasurementStatus.BLOCKED)
        self.assertEqual(result.note_count, 1)
        self.assertEqual(result.measure_measurements, ())

    def test_style_adapter_inherits_context_protections_and_valid_window(self) -> None:
        source = midi([
            track([meter(), tempo()]),
            track([
                b"\x00\xff\x03\x08ACC1 CV1", b"\x00\xff\x01\x051 Bar",
                b"\x00\xff\x01\x0cSteel Guitar", b"\x00\xcb\x18",
                note_on(0, 52, 70, 11), note_off(96, 52, 11),
                note_on(672, 100, 110, 11),
            ]),
        ])
        element = StyleWorksLoader().load_element_bytes(
            source, member_name="Styles/Test/Test_Intro1.mid"
        )
        result = measure_style_track(element, element.tracks[1])

        self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(result.note_count, 1)
        self.assertEqual(result.inherited_edit_policy.value, "DO_NOT_TOUCH")
        self.assertTrue(any("Fixed Intro/Ending" in item for item in result.protections))
        self.assertTrue(any("Analyze-only" in item for item in result.protections))


if __name__ == "__main__":
    unittest.main()