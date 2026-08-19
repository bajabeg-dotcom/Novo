from __future__ import annotations

import struct
import unittest

from change_plan import MutationField, PlanState, RiskLevel, UserDecision
from instrument_identity_resolver import InstrumentIdentityResolver
from instrument_segmenter import InstrumentSegmenter, SegmentationInput
from k03_sound_replacement import K03ProposalError, K03SoundReplacementBuilder
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


def midi(events: list[bytes]) -> bytes:
    item = track(events)
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, 192) + item


def note_on(delta: int = 0, pitch: int = 60) -> bytes:
    return vlq(delta) + bytes([0x90, pitch, 90])


def note_off(delta: int = 96, pitch: int = 60) -> bytes:
    return vlq(delta) + bytes([0x80, pitch, 0])


def addressed(cc00: int, cc32: int, pc: int, pitch: int = 60) -> list[bytes]:
    return [
        bytes([0, 0xB0, 0, cc00]),
        bytes([0, 0xB0, 32, cc32]),
        bytes([0, 0xC0, pc]),
        note_on(pitch=pitch),
        note_off(pitch=pitch),
    ]


def pipeline(source: bytes):
    model = StandardMidiLoader().load_bytes(source, source_name="k03.mid")
    events = model.tracks[0].events
    segmentation = InstrumentSegmenter().segment(SegmentationInput(
        source_sha256=model.sha256,
        events=events,
        ticks_per_beat=model.ticks_per_beat,
        window_end_tick=384,
    ))
    identities = InstrumentIdentityResolver().resolve(segmentation)
    return model, events, segmentation, identities


class K03SoundReplacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = K03SoundReplacementBuilder()

    def test_same_bank_user_selected_target_creates_pc_only_suggest_plan(self) -> None:
        source = midi(addressed(121, 0, 33))
        model, events, segmentation, identities = pipeline(source)
        plan = self.builder.build_plan(
            segmentation=segmentation,
            identities=identities,
            events=events,
            segment_ordinal=1,
            target_address="121.0.34",
            user_selected=True,
        )
        self.assertEqual(plan.phase, "SUGGEST")
        self.assertEqual(plan.state, PlanState.AWAITING_CONFIRMATION)
        self.assertFalse(plan.apply_authorized)
        proposal = plan.proposals[0]
        self.assertEqual(proposal.risk, RiskLevel.MEDIUM)
        self.assertEqual(proposal.rule_id, "K03.USER_SELECTED_FACTORY_REPLACEMENT")
        self.assertEqual(len(proposal.mutations), 1)
        mutation = proposal.mutations[0]
        self.assertEqual(mutation.event_kind, "program_change")
        self.assertEqual(mutation.field, MutationField.DATA_0)
        self.assertEqual((mutation.old_value, mutation.new_value), (33, 34))
        self.assertEqual(model.sha256, segmentation.source_sha256)
        self.assertEqual(source, midi(addressed(121, 0, 33)))
        self.assertTrue(all(segment.identity_status == "UNRESOLVED" for segment in segmentation.segments))

    def test_exclusive_boundary_can_change_bank_and_program(self) -> None:
        source = midi(addressed(121, 0, 33))
        _model, events, segmentation, identities = pipeline(source)
        plan = self.builder.build_plan(
            segmentation=segmentation,
            identities=identities,
            events=events,
            segment_ordinal=1,
            target_address="121.1.34",
            user_selected=True,
        )
        mutations = plan.proposals[0].mutations
        self.assertEqual(len(mutations), 2)
        self.assertEqual(
            {(item.event_kind, item.field, item.old_value, item.new_value) for item in mutations},
            {
                ("control_change", MutationField.DATA_1, 0, 1),
                ("program_change", MutationField.DATA_0, 33, 34),
            },
        )

    def test_shared_or_inherited_bank_event_blocks_bank_change(self) -> None:
        source = midi(
            addressed(121, 0, 33)
            + [bytes([0, 0xC0, 34]), note_on(pitch=62), note_off(pitch=62)]
        )
        _model, events, segmentation, identities = pipeline(source)
        self.assertEqual(len(segmentation.segments), 2)
        with self.assertRaisesRegex(K03ProposalError, "shared"):
            self.builder.build_plan(
                segmentation=segmentation,
                identities=identities,
                events=events,
                segment_ordinal=1,
                target_address="121.1.33",
                user_selected=True,
            )

    def test_user_drum_slot_can_propose_factory_drum_but_not_sound(self) -> None:
        source = midi(addressed(120, 64, 12))
        _model, events, segmentation, identities = pipeline(source)
        plan = self.builder.build_plan(
            segmentation=segmentation,
            identities=identities,
            events=events,
            segment_ordinal=1,
            target_address="120.0.5",
            user_selected=True,
        )
        self.assertEqual(plan.proposals[0].risk, RiskLevel.HIGH)
        self.assertEqual(len(plan.proposals[0].mutations), 2)
        with self.assertRaisesRegex(K03ProposalError, "incompatible"):
            self.builder.build_plan(
                segmentation=segmentation,
                identities=identities,
                events=events,
                segment_ordinal=1,
                target_address="121.0.33",
                user_selected=True,
            )

    def test_conflict_incomplete_unknown_and_missing_user_selection_are_blocked(self) -> None:
        cases = [
            (midi(addressed(120, 0, 57)), "120.0.5", True, "CONFLICT"),
            (midi([bytes([0, 0xC0, 33]), note_on(), note_off()]), "121.0.34", True, "complete"),
            (midi(addressed(122, 0, 1)), "121.0.34", True, "UNKNOWN"),
            (midi(addressed(121, 0, 33)), "121.0.34", False, "explicitly selected"),
        ]
        for source, target, selected, message in cases:
            with self.subTest(message=message):
                _model, events, segmentation, identities = pipeline(source)
                with self.assertRaisesRegex(K03ProposalError, message):
                    self.builder.build_plan(
                        segmentation=segmentation,
                        identities=identities,
                        events=events,
                        segment_ordinal=1,
                        target_address=target,
                        user_selected=selected,
                    )

    def test_same_or_nonfactory_target_is_rejected(self) -> None:
        source = midi(addressed(121, 0, 33))
        _model, events, segmentation, identities = pipeline(source)
        with self.assertRaisesRegex(K03ProposalError, "equals"):
            self.builder.build_plan(
                segmentation=segmentation,
                identities=identities,
                events=events,
                segment_ordinal=1,
                target_address="121.0.33",
                user_selected=True,
            )
        with self.assertRaisesRegex(K03ProposalError, "exact K01"):
            self.builder.build_plan(
                segmentation=segmentation,
                identities=identities,
                events=events,
                segment_ordinal=1,
                target_address="122.0.1",
                user_selected=True,
            )

    def test_user_approval_still_does_not_authorize_apply(self) -> None:
        source = midi(addressed(121, 0, 33))
        _model, events, segmentation, identities = pipeline(source)
        plan = self.builder.build_plan(
            segmentation=segmentation,
            identities=identities,
            events=events,
            segment_ordinal=1,
            target_address="121.0.34",
            user_selected=True,
        )
        approved = plan.record_decision(
            plan.proposals[0].proposal_id,
            UserDecision.APPROVE,
            decided_at="2026-08-14T13:00:00+02:00",
        )
        self.assertEqual(approved.state, PlanState.APPROVED)
        self.assertFalse(approved.apply_authorized)
        self.assertEqual(source, midi(addressed(121, 0, 33)))


if __name__ == "__main__":
    unittest.main()
