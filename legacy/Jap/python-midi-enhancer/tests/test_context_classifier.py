from __future__ import annotations

import struct
import unittest
from dataclasses import replace

from context_classifier import (
    ClassificationStatus,
    ContextClassifier,
    EditPolicy,
    Encoding,
    FunctionLabel,
    StructuralRole,
    classify_style_element,
    style_classification_input,
)
from style_loader import StyleWorksLoader


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


def meta_text(meta_type: int, text: str) -> bytes:
    payload = text.encode("ascii")
    return b"\x00\xff" + bytes([meta_type]) + vlq(len(payload)) + payload


def note(tick_delta: int, channel: int, pitch: int, velocity: int = 90) -> bytes:
    return vlq(tick_delta) + bytes([0x90 | channel, pitch, velocity])


def style_element(
    musical_events: list[bytes], *, suffix: str = "Var1", role_name: str = "ACC1 CV1",
    sound: str = "Steel Guitar", bars_texts: tuple[str, ...] = ("1 Bar",), channel: int = 11,
    program: int = 24,
):
    conductor = track([b"\x00\xff\x58\x04\x04\x02\x18\x08"])
    headers = [meta_text(3, role_name), meta_text(1, sound)]
    headers.extend(meta_text(1, value) for value in bars_texts)
    # Caller note helpers may use any channel; this PC establishes a guitar sound.
    headers.append(b"\x00" + bytes([0xC0 | channel, program]))
    return StyleWorksLoader().load_element_bytes(
        midi([conductor, track(headers + musical_events)]),
        member_name=f"Styles/Test/Test_{suffix}.mid",
    )


class ContextClassifierTests(unittest.TestCase):
    def test_structural_roles_are_style_context_not_core_channel_rules(self) -> None:
        element = style_element(
            [note(0, 9, 36), note(96, 9, 38)], role_name="DRUM CV1", sound="Kit", channel=9
        )
        source = style_classification_input(element, element.tracks[1])
        result = ContextClassifier().classify(source)
        self.assertEqual(source.structural_role, StructuralRole.DRUM)
        self.assertEqual(result.structural_role, StructuralRole.DRUM)
        self.assertEqual(result.function, FunctionLabel.RHYTHM_DRUM)
        self.assertEqual(result.edit_policy, EditPolicy.SAFE_BOUNDED)

    def test_same_guitar_sound_has_chordal_and_solo_contexts(self) -> None:
        chordal = style_element([
            note(0, 11, 52), note(0, 11, 55), note(0, 11, 59),
            note(192, 11, 53), note(0, 11, 57), note(0, 11, 60),
        ])
        solo = style_element([
            note(0, 11, 64), note(96, 11, 67), note(96, 11, 69), note(96, 11, 71),
            vlq(0) + bytes([0xE0 | 11, 0, 72]),
        ])
        classifier = ContextClassifier()
        chord_result = classifier.classify(style_classification_input(chordal, chordal.tracks[1]))
        solo_result = classifier.classify(style_classification_input(solo, solo.tracks[1]))
        self.assertEqual(chord_result.function, FunctionLabel.RHYTHM_GUITAR)
        self.assertEqual(solo_result.function, FunctionLabel.SOLO_CANDIDATE)
        self.assertEqual(chord_result.encoding, Encoding.ORDINARY_MIDI)
        self.assertEqual(solo_result.encoding, Encoding.ORDINARY_MIDI)

    def test_low_guitar_riff_is_not_guitar_mode_without_source_evidence(self) -> None:
        element = style_element([
            note(0, 11, 28), note(96, 11, 31), note(96, 11, 28), note(96, 11, 31),
            note(96, 11, 28), note(96, 11, 31),
        ])
        result = ContextClassifier().classify(style_classification_input(element, element.tracks[1]))
        self.assertEqual(result.encoding, Encoding.ORDINARY_MIDI)
        self.assertEqual(result.function, FunctionLabel.ACCOMP_LINE_RIFF)

    def test_source_guitar_mode_evidence_does_not_force_rhythm_function(self) -> None:
        element = style_element([
            note(0, 11, 64), note(96, 11, 67), note(96, 11, 69), note(96, 11, 71),
            vlq(0) + bytes([0xE0 | 11, 0, 72]),
        ])
        source = replace(
            style_classification_input(element, element.tracks[1]),
            encoding_hint=Encoding.GUITAR_MODE_CANDIDATE,
            encoding_evidence=("potvrđeni vanjski Track Type=Gtr",),
        )
        result = ContextClassifier().classify(source)
        self.assertEqual(result.encoding, Encoding.GUITAR_MODE_CANDIDATE)
        self.assertEqual(result.function, FunctionLabel.SOLO_CANDIDATE)
        self.assertEqual(result.edit_policy, EditPolicy.DO_NOT_TOUCH)

    def test_high_rx_notes_do_not_create_guitar_mode_false_positive(self) -> None:
        element = style_element([
            note(0, 11, 52), note(0, 11, 55), note(0, 11, 59),
            note(96, 11, 100), note(96, 11, 101),
        ])
        result = ContextClassifier().classify(style_classification_input(element, element.tracks[1]))
        self.assertEqual(result.encoding, Encoding.ORDINARY_MIDI)
        self.assertTrue(result.rx_high_note_ambiguous)
        self.assertEqual(result.edit_policy, EditPolicy.DO_NOT_TOUCH)
        self.assertTrue(any("RX Noise" in item for item in result.evidence.protections))

    def test_fixed_intro_flag_is_orthogonal_and_scoped(self) -> None:
        intro = style_element(
            [note(0, 11, 52), note(0, 11, 55), note(0, 11, 59)], suffix="Intro1"
        )
        intro_result = ContextClassifier().classify(style_classification_input(intro, intro.tracks[1]))
        self.assertEqual(intro_result.function, FunctionLabel.RHYTHM_GUITAR)
        self.assertTrue(intro_result.fixed_intro_ending_candidate)
        self.assertEqual(intro_result.edit_policy, EditPolicy.DO_NOT_TOUCH)

        variation = style_element(
            [note(0, 11, 52), note(0, 11, 55), note(0, 11, 59)], suffix="Var1"
        )
        variation_result = ContextClassifier().classify(
            style_classification_input(variation, variation.tracks[1])
        )
        self.assertFalse(variation_result.fixed_intro_ending_candidate)

    def test_fixed_flag_excludes_rhythm_bass_and_empty_tracks(self) -> None:
        cases = (
            style_element(
                [note(0, 9, 36)], suffix="Intro1", role_name="DRUM CV1",
                sound="Kit", channel=9, program=80,
            ),
            style_element(
                [note(0, 10, 60)], suffix="Intro1", role_name="PERC CV1",
                sound="Perc", channel=10, program=80,
            ),
            style_element(
                [note(0, 8, 40)], suffix="Intro1", role_name="BASS CV1",
                sound="Bass", channel=8, program=32,
            ),
            style_element([], suffix="Intro1"),
        )
        for element in cases:
            result = ContextClassifier().classify(
                style_classification_input(element, element.tracks[1])
            )
            self.assertFalse(result.fixed_intro_ending_candidate)

    def test_blocked_element_is_not_editable(self) -> None:

        blocked = style_element(
            [note(0, 11, 52)], suffix="Break", bars_texts=("1 Bar", "5 Bars")
        )
        results = classify_style_element(blocked)
        self.assertTrue(all(item.status is ClassificationStatus.BLOCKED for item in results))
        self.assertTrue(all(item.edit_policy is EditPolicy.DO_NOT_TOUCH for item in results))

    def test_drum_perc_and_bass_precede_texture_heuristics(self) -> None:
        cases = (
            ("DRUM CV1", 9, FunctionLabel.RHYTHM_DRUM),
            ("PERC CV1", 10, FunctionLabel.RHYTHM_PERC),
            ("BASS CV1", 8, FunctionLabel.BASS_ACCOMP),
        )
        for role_name, channel, expected in cases:
            with self.subTest(role=role_name):
                element = style_element(
                    [note(0, channel, 40), note(0, channel, 47), note(0, channel, 52)],
                    role_name=role_name, sound="Neutral", channel=channel, program=80,
                )
                result = ContextClassifier().classify(
                    style_classification_input(element, element.tracks[1])
                )
                self.assertEqual(result.function, expected)

    def test_repeated_ostinato_is_riff_but_varied_line_is_solo(self) -> None:
        ostinato = style_element(
            [
                note(0, 11, 60), note(96, 11, 64), note(96, 11, 60), note(96, 11, 64),
                note(96, 11, 60), note(96, 11, 64),
            ], sound="Synth", program=80,
        )
        solo = style_element(
            [
                note(0, 11, 60), note(96, 11, 62), note(96, 11, 65), note(96, 11, 69),
                note(96, 11, 71), vlq(0) + bytes([0xE0 | 11, 0, 72]),
            ], sound="Synth", program=80,
        )
        classifier = ContextClassifier()
        riff_result = classifier.classify(style_classification_input(ostinato, ostinato.tracks[1]))
        solo_result = classifier.classify(style_classification_input(solo, solo.tracks[1]))
        self.assertEqual(riff_result.function, FunctionLabel.ACCOMP_LINE_RIFF)
        self.assertEqual(solo_result.function, FunctionLabel.SOLO_CANDIDATE)

    def test_ppq_scaled_strum_cluster_is_not_slow_arpeggio(self) -> None:
        strum = style_element([
            note(0, 11, 52), note(2, 11, 55), note(2, 11, 59),
            note(188, 11, 53), note(2, 11, 57), note(2, 11, 60),
        ])
        arpeggio = style_element([
            note(0, 11, 52), note(24, 11, 55), note(24, 11, 59), note(24, 11, 64),
        ])
        classifier = ContextClassifier()
        strum_result = classifier.classify(style_classification_input(strum, strum.tracks[1]))
        arp_result = classifier.classify(style_classification_input(arpeggio, arpeggio.tracks[1]))
        self.assertEqual(strum_result.features.onset_cluster_tolerance_ticks, 4)
        self.assertEqual(strum_result.function, FunctionLabel.RHYTHM_GUITAR)
        self.assertNotEqual(arp_result.function, FunctionLabel.RHYTHM_GUITAR)

    def test_rx_policy_cannot_relax_fixed_intro_protection(self) -> None:
        element = style_element([
            note(0, 11, 52), note(0, 11, 55), note(0, 11, 59),
            note(96, 11, 53), note(0, 11, 57), note(96, 11, 100),
        ], suffix="Intro1")
        result = ContextClassifier().classify(style_classification_input(element, element.tracks[1]))
        self.assertTrue(result.fixed_intro_ending_candidate)
        self.assertTrue(result.rx_high_note_ambiguous)
        self.assertEqual(result.edit_policy, EditPolicy.DO_NOT_TOUCH)

    def test_rx_policy_cannot_relax_guitar_mode_protection(self) -> None:
        element = style_element([
            note(0, 11, 60), note(96, 11, 62), note(96, 11, 64),
            note(96, 11, 65), note(96, 11, 67), note(96, 11, 100),
        ])
        source = replace(
            style_classification_input(element, element.tracks[1]),
            encoding_hint=Encoding.GUITAR_MODE_CANDIDATE,
            encoding_evidence=("potvrđeni vanjski Track Type=Gtr",),
        )
        result = ContextClassifier().classify(source)
        self.assertTrue(result.rx_high_note_ambiguous)
        self.assertEqual(result.edit_policy, EditPolicy.DO_NOT_TOUCH)

    def test_multiple_musical_channels_block_classification(self) -> None:
        element = style_element([
            note(0, 11, 52), note(96, 12, 55),
        ])
        result = ContextClassifier().classify(style_classification_input(element, element.tracks[1]))
        self.assertEqual(result.status, ClassificationStatus.BLOCKED)
        self.assertEqual(result.function, FunctionLabel.UNKNOWN)
        self.assertEqual(result.edit_policy, EditPolicy.DO_NOT_TOUCH)
        self.assertEqual(result.features.musical_channels, (11, 12))


if __name__ == "__main__":
    unittest.main()