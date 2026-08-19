from __future__ import annotations

import hashlib
import struct
import unittest

from instrument_identity_resolver import IdentityStatus, InstrumentIdentityResolver
from instrument_segmenter import InstrumentSegmenter, SegmentationInput
from style_loader import StandardMidiLoader


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


def midi(events: list[bytes], division: int = 192) -> bytes:
    midi_track = track(events)
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, division) + midi_track


def note_on(delta: int = 0, pitch: int = 60) -> bytes:
    return vlq(delta) + bytes([0x90, pitch, 90])


def note_off(delta: int = 96, pitch: int = 60) -> bytes:
    return vlq(delta) + bytes([0x80, pitch, 0])


def addressed_events(cc00: int, cc32: int, pc: int, pitch: int = 60) -> list[bytes]:
    return [
        bytes([0, 0xB0, 0, cc00]),
        bytes([0, 0xB0, 32, cc32]),
        bytes([0, 0xC0, pc]),
        note_on(pitch=pitch),
        note_off(pitch=pitch),
    ]


def segment_source(source: bytes):
    model = StandardMidiLoader().load_bytes(source, source_name="k02.mid")
    result = InstrumentSegmenter().segment(SegmentationInput(
        source_sha256=model.sha256,
        events=model.tracks[0].events,
        ticks_per_beat=model.ticks_per_beat,
        window_end_tick=384,
    ))
    return model, result


class InstrumentIdentityResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = InstrumentIdentityResolver()

    def test_exact_factory_sound_and_drum_addresses_are_confirmed(self) -> None:
        for address, expected_name, expected_kind in (
            ((121, 0, 33), "Finger Bass GM", "FACTORY_SOUND"),
            ((120, 0, 5), "Standard Kit RX1", "FACTORY_DRUM_KIT"),
        ):
            with self.subTest(address=address):
                source = midi(addressed_events(*address))
                _model, segmentation = segment_source(source)
                segment = segmentation.segments[0]
                identity = self.resolver.resolve_segment(segment)
                self.assertEqual(identity.status, IdentityStatus.FACTORY_CONFIRMED)
                self.assertEqual(identity.requested_address, ".".join(map(str, address)))
                self.assertEqual(identity.effective_address, identity.requested_address)
                self.assertEqual(identity.official_name, expected_name)
                self.assertEqual(identity.item_kind, expected_kind)
                self.assertFalse(identity.via_remap)
                self.assertEqual(identity.rule_id, "K02.EXACT_FACTORY_ADDRESS")
                self.assertIs(identity.original_segment, segment)
                self.assertEqual(segment.identity_status, "UNRESOLVED")

    def test_incomplete_address_and_no_program_are_not_guessed(self) -> None:
        incomplete = midi([bytes([0, 0xC0, 33]), note_on(), note_off()])
        _model, result = segment_source(incomplete)
        identity = self.resolver.resolve_segment(result.segments[0])
        self.assertEqual(identity.status, IdentityStatus.INCOMPLETE_ADDRESS)
        self.assertIsNone(identity.requested_address)
        self.assertIsNone(identity.factory_entry)

        no_program = midi([note_on(), note_off()])
        _model, result = segment_source(no_program)
        identity = self.resolver.resolve_segment(result.segments[0])
        self.assertEqual(identity.status, IdentityStatus.NO_PROGRAM)
        self.assertEqual(identity.rule_id, "K02.NO_PROGRAM")
        self.assertIsNone(identity.effective_address)

    def test_user_slot_location_and_unknown_complete_address_are_separate(self) -> None:
        user_source = midi(addressed_events(120, 64, 12))
        _model, user_result = segment_source(user_source)
        user = self.resolver.resolve_segment(user_result.segments[0])
        self.assertEqual(user.status, IdentityStatus.USER_SLOT_CONFIRMED)
        self.assertEqual(user.requested_address, "120.64.12")
        self.assertEqual(user.item_kind, "USER_DRUM_KIT_SLOT")
        self.assertIsNone(user.official_name)
        self.assertIsNone(user.factory_entry)

        unknown_source = midi(addressed_events(122, 0, 1))
        _model, unknown_result = segment_source(unknown_source)
        unknown = self.resolver.resolve_segment(unknown_result.segments[0])
        self.assertEqual(unknown.status, IdentityStatus.UNKNOWN)
        self.assertEqual(unknown.requested_address, "122.0.1")
        self.assertIsNone(unknown.effective_address)
        self.assertIn("nagađati", " ".join(unknown.protections).lower())

    def test_nonconflicting_drum_remap_preserves_requested_and_target(self) -> None:
        source = midi(addressed_events(120, 0, 59))
        _model, result = segment_source(source)
        identity = self.resolver.resolve_segment(result.segments[0])
        self.assertEqual(identity.status, IdentityStatus.FACTORY_CONFIRMED)
        self.assertEqual(identity.requested_address, "120.0.59")
        self.assertEqual(identity.effective_address, "120.0.56")
        self.assertEqual(identity.official_name, "SFX Kit GM")
        self.assertTrue(identity.via_remap)
        self.assertEqual(identity.rule_id, "K02.CONFIRMED_DRUM_REMAP")
        self.assertEqual(identity.candidate_addresses, ("120.0.59", "120.0.56"))

    def test_named_57_58_remap_overlap_is_conflict(self) -> None:
        for pc, name in ((57, "SFX Kit 2"), (58, "Synth Kit")):
            with self.subTest(pc=pc):
                source = midi(addressed_events(120, 0, pc))
                _model, result = segment_source(source)
                identity = self.resolver.resolve_segment(result.segments[0])
                self.assertEqual(identity.status, IdentityStatus.CONFLICT)
                self.assertEqual(identity.requested_address, f"120.0.{pc}")
                self.assertIsNone(identity.effective_address)
                self.assertEqual(identity.official_name, name)
                self.assertEqual(identity.evidence_status, "CONFLICT")
                self.assertEqual(
                    identity.candidate_addresses,
                    tuple(sorted((f"120.0.{pc}", "120.0.56"), key=lambda x: tuple(map(int, x.split("."))))),
                )
                self.assertEqual(identity.remap_evidence[0].conflicts_with_named_pcs, (57, 58))

    def test_batch_resolution_preserves_m10_result_and_source(self) -> None:
        source = midi(
            addressed_events(121, 0, 33, pitch=48)
            + [bytes([0, 0xC0, 34]), note_on(pitch=50), note_off(pitch=50)]
        )
        model, segmentation = segment_source(source)
        before = segmentation
        resolution = self.resolver.resolve(segmentation)

        self.assertIs(resolution.original_result, segmentation)
        self.assertEqual(segmentation, before)
        self.assertEqual(model.sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(resolution.source_sha256, model.sha256)
        self.assertEqual(len(resolution.identities), 2)
        self.assertTrue(all(item.original_segment.identity_status == "UNRESOLVED" for item in resolution.identities))
        self.assertTrue(all("read-only" in item.lower() for item in resolution.protections[:1]))


if __name__ == "__main__":
    unittest.main()
