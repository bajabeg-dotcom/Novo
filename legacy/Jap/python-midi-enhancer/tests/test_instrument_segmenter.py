from __future__ import annotations

import hashlib
import struct
import unittest

from instrument_segmenter import (
    AddressStatus,
    InstrumentSegmenter,
    SegmentationInput,
    SegmentationStatus,
    segment_style_track,
)
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


def note_on(delta: int, pitch: int, channel: int = 0) -> bytes:
    return vlq(delta) + bytes([0x90 | channel, pitch, 90])


def note_off(delta: int, pitch: int, channel: int = 0) -> bytes:
    return vlq(delta) + bytes([0x80 | channel, pitch, 0])


class InstrumentSegmenterTests(unittest.TestCase):
    def test_splits_complete_addresses_and_profiles_each_segment(self) -> None:
        source = midi([track([
            b"\x00\xb0\x00\x01", b"\x00\xb0\x20\x02", b"\x00\xc0\x0a",
            note_on(0, 60), note_off(96, 60), b"\x00\xc0\x14",
            note_on(0, 64), note_off(96, 64),
        ])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentSegmenter().segment(SegmentationInput(
            model.sha256, model.tracks[0].events, model.ticks_per_beat, window_end_tick=384
        ))

        self.assertEqual(result.status, SegmentationStatus.READY)
        self.assertEqual([segment.address.value for segment in result.segments], ["1.2.10", "1.2.20"])
        self.assertEqual([segment.measurement.note_count for segment in result.segments], [1, 1])
        self.assertTrue(all(segment.identity_status == "UNRESOLVED" for segment in result.segments))

    def test_bank_change_applies_only_at_next_program_change(self) -> None:
        source = midi([track([
            b"\x00\xb0\x00\x01", b"\x00\xb0\x20\x02", b"\x00\xc0\x0a",
            note_on(0, 60), note_off(48, 60), b"\x00\xb0\x00\x03",
            note_on(48, 62), note_off(48, 62), b"\x00\xc0\x14",
            note_on(0, 64), note_off(48, 64),
        ])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentSegmenter().segment(SegmentationInput(
            model.sha256, model.tracks[0].events, model.ticks_per_beat, window_end_tick=384
        ))

        self.assertEqual(result.segments[0].address.value, "1.2.10")
        self.assertEqual(result.segments[1].address.value, "3.2.20")
        self.assertEqual(result.segments[0].measurement.note_count, 2)

    def test_incomplete_address_is_partial_not_guessed(self) -> None:
        source = midi([track([b"\x00\xc0\x0a", note_on(0, 60), note_off(96, 60)])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentSegmenter().segment(SegmentationInput(
            model.sha256, model.tracks[0].events, model.ticks_per_beat, window_end_tick=192
        ))

        self.assertEqual(result.status, SegmentationStatus.PARTIAL)
        self.assertEqual(result.segments[0].address.status, AddressStatus.INCOMPLETE)
        self.assertIsNone(result.segments[0].address.value)

    def test_note_crossing_program_boundary_is_flagged(self) -> None:
        source = midi([track([
            b"\x00\xb0\x00\x01", b"\x00\xb0\x20\x02", b"\x00\xc0\x0a",
            note_on(0, 60), b"\x60\xc0\x14", note_off(96, 60),
        ])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentSegmenter().segment(SegmentationInput(
            model.sha256, model.tracks[0].events, model.ticks_per_beat, window_end_tick=384
        ))

        self.assertEqual(result.status, SegmentationStatus.PARTIAL)
        self.assertEqual(result.segments[0].crossing_boundary_note_count, 1)
        self.assertTrue(any("prelaze" in item for item in result.segments[0].warnings))

    def test_open_note_crossing_program_boundary_is_flagged(self) -> None:
        source = midi([track([
            b"\x00\xb0\x00\x01", b"\x00\xb0\x20\x02", b"\x00\xc0\x0a",
            note_on(0, 60), b"\x60\xc0\x14",
        ])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentSegmenter().segment(SegmentationInput(
            model.sha256, model.tracks[0].events, model.ticks_per_beat, window_end_tick=384
        ))

        self.assertEqual(result.status, SegmentationStatus.PARTIAL)
        self.assertEqual(result.segments[0].crossing_boundary_note_count, 1)
        self.assertTrue(any("prelaze" in item for item in result.segments[0].warnings))

    def test_same_tick_event_order_defines_boundary(self) -> None:
        source = midi([track([
            b"\x00\xb0\x00\x01", b"\x00\xb0\x20\x02", b"\x00\xc0\x0a",
            note_on(96, 60), note_off(0, 60), b"\x00\xc0\x14",
            note_on(0, 64), note_off(96, 64),
        ])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentSegmenter().segment(SegmentationInput(
            model.sha256, model.tracks[0].events, model.ticks_per_beat, window_end_tick=384
        ))

        self.assertEqual(result.segments[0].measurement.pitch_minimum, 60)
        self.assertEqual(result.segments[1].measurement.pitch_minimum, 64)

    def test_multiple_channels_are_partitioned_but_result_is_partial(self) -> None:
        source = midi([track([
            b"\x00\xc0\x0a", note_on(0, 60, 0), note_off(48, 60, 0),
            b"\x00\xc1\x14", note_on(0, 65, 1), note_off(48, 65, 1),
        ])])
        model = StandardMidiLoader().load_bytes(source)
        result = InstrumentSegmenter().segment(SegmentationInput(
            model.sha256, model.tracks[0].events, model.ticks_per_beat, window_end_tick=192
        ))

        self.assertEqual(result.status, SegmentationStatus.PARTIAL)
        self.assertEqual(result.musical_channels, (1, 2))
        self.assertEqual({segment.channel for segment in result.segments}, {1, 2})
        self.assertEqual(
            [segment.ordinal for segment in result.segments],
            list(range(1, len(result.segments) + 1)),
        )
        self.assertEqual(
            len({segment.ordinal for segment in result.segments}),
            len(result.segments),
        )

    def test_cross_track_same_channel_program_tick_is_partial(self) -> None:
        source = midi([
            track([
                b"\x00\xb0\x00\x01", b"\x00\xb0\x20\x02", b"\x00\xc0\x0a",
                note_on(0, 60), note_off(96, 60),
            ]),
            track([vlq(96) + b"\xc0\x14", note_on(0, 64), note_off(96, 64)]),
        ])
        model = StandardMidiLoader().load_bytes(source)
        events = tuple(event for midi_track in model.tracks for event in midi_track.events)
        result = InstrumentSegmenter().segment(SegmentationInput(
            model.sha256, events, model.ticks_per_beat, window_end_tick=384
        ))

        self.assertEqual(result.status, SegmentationStatus.PARTIAL)
        self.assertTrue(any("drugog tracka" in warning for warning in result.warnings))

    def test_style_adapter_respects_valid_window_and_source_hash(self) -> None:
        source = midi([
            track([b"\x00\xff\x58\x04\x04\x02\x18\x08"]),
            track([
                b"\x00\xff\x03\x08ACC1 CV1", b"\x00\xff\x01\x051 Bar",
                b"\x00\xbb\x00\x01", b"\x00\xbb\x20\x02", b"\x00\xcb\x18",
                note_on(0, 60, 11), note_off(96, 60, 11), note_on(672, 72, 11),
            ]),
        ])
        element = StyleWorksLoader().load_element_bytes(
            source, member_name="Styles/Test/Test_Var1.mid"
        )
        result = segment_style_track(element, element.tracks[1])

        self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0].measurement.note_count, 1)
        self.assertEqual(result.segments[0].address.value, "1.2.24")


if __name__ == "__main__":
    unittest.main()