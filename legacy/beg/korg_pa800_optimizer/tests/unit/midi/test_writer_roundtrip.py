"""MIDI round-trip test: import -> normalize -> write -> re-parse.

Per docs/MIDI_MODEL.md, equivalence (not byte-identity) is required:
notes, CC (including raw NRPN/RPN constituent CCs), program changes,
pitch bend, sysex, and tempo/time-signature maps must all survive.
Run against both format-0 (Golden) and format-1 (Factory Style) real
files, per docs/TEST_STRATEGY.md.
"""

from __future__ import annotations

import mido
import pytest

from korg_optimizer.midi.normalized_model import NormalizedMidiFile
from korg_optimizer.midi.writer import write

from tests.unit.factory.samples import ALL_FACTORY_SAMPLES, GOLDEN_SAMPLE


def _facts(midi_file: mido.MidiFile) -> dict:
    notes = []
    ccs = []
    programs = []
    pitchbends = []
    sysex = []
    tempos = []
    time_sigs = []
    for track in midi_file.tracks:
        t = 0
        for msg in track:
            t += msg.time
            if msg.type in ("note_on", "note_off"):
                is_off = msg.type == "note_off" or msg.velocity == 0
                notes.append((t, msg.channel, msg.note, msg.velocity, is_off))
            elif msg.type == "control_change":
                ccs.append((t, msg.channel, msg.control, msg.value))
            elif msg.type == "program_change":
                programs.append((t, msg.channel, msg.program))
            elif msg.type == "pitchwheel":
                pitchbends.append((t, msg.channel, msg.pitch))
            elif msg.type == "sysex":
                sysex.append((t, tuple(msg.data)))
            elif msg.is_meta and msg.type == "set_tempo":
                tempos.append((t, msg.tempo))
            elif msg.is_meta and msg.type == "time_signature":
                time_sigs.append((t, msg.numerator, msg.denominator))
    return dict(
        notes=sorted(notes),
        ccs=sorted(ccs),
        programs=sorted(programs),
        pitchbends=sorted(pitchbends),
        sysex=sorted(sysex),
        tempos=sorted(tempos),
        time_sigs=sorted(time_sigs),
    )


def _assert_roundtrip(path, tmp_path):
    normalized = NormalizedMidiFile.from_file(path)
    out_path = tmp_path / "roundtrip.mid"
    write(normalized, out_path)

    original = mido.MidiFile(str(path))
    roundtripped = mido.MidiFile(str(out_path))

    assert original.type == roundtripped.type
    assert original.ticks_per_beat == roundtripped.ticks_per_beat
    assert len(original.tracks) == len(roundtripped.tracks)
    assert _facts(original) == _facts(roundtripped)


@pytest.mark.parametrize("path", ALL_FACTORY_SAMPLES, ids=lambda p: p.name)
def test_roundtrip_format1_factory_style(path, tmp_path):
    _assert_roundtrip(path, tmp_path)


def test_roundtrip_format0_golden_song(tmp_path):
    _assert_roundtrip(GOLDEN_SAMPLE, tmp_path)
