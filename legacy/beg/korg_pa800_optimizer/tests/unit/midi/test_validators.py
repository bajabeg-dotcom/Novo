from __future__ import annotations

from korg_optimizer.midi.normalized_model import NormalizedMidiFile
from korg_optimizer.midi.validators import is_valid, validate_structure

from tests.unit.factory.samples import CLEAN_SAMPLE, GOLDEN_SAMPLE


def test_real_factory_style_file_is_structurally_valid():
    n = NormalizedMidiFile.from_file(CLEAN_SAMPLE)
    issues = validate_structure(n)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert errors == []
    assert is_valid(n)


def test_real_golden_song_is_structurally_valid():
    n = NormalizedMidiFile.from_file(GOLDEN_SAMPLE)
    assert is_valid(n)


def test_invalid_ppq_flagged():
    n = NormalizedMidiFile.from_file(CLEAN_SAMPLE)
    n.ppq = 0
    issues = validate_structure(n)
    assert any(i.severity == "ERROR" and "ppq" in i.message for i in issues)


def test_unsupported_format_flagged():
    n = NormalizedMidiFile.from_file(CLEAN_SAMPLE)
    n.format = 2
    issues = validate_structure(n)
    assert any(i.severity == "ERROR" and "format" in i.message for i in issues)
    assert not is_valid(n)


def test_missing_end_of_track_is_a_warning_not_an_error():
    n = NormalizedMidiFile.from_file(CLEAN_SAMPLE)
    for track in n.tracks:
        track.events = [e for e in track.events if e.message.type != "end_of_track"]
    issues = validate_structure(n)
    assert all(i.severity != "ERROR" for i in issues)
    assert any(i.severity == "WARNING" and "end_of_track" in i.message for i in issues)
