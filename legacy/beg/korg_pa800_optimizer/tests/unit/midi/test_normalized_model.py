from __future__ import annotations

from korg_optimizer.midi.normalized_model import NormalizedMidiFile

from tests.unit.factory.samples import CLEAN_SAMPLE, GOLDEN_SAMPLE, TRACK_COUNT_SAMPLES


def test_format1_factory_style_parses():
    n = NormalizedMidiFile.from_file(CLEAN_SAMPLE)
    assert n.format == 1
    assert n.ppq == 192
    assert len(n.tracks) > 0
    assert n.tempo_map, "expected at least one tempo event"


def test_format0_golden_song_parses():
    n = NormalizedMidiFile.from_file(GOLDEN_SAMPLE)
    assert n.format == 0
    assert n.ppq == 384
    assert len(n.tracks) == 1
    channels = {
        event.message.channel
        for event in n.tracks[0].events
        if hasattr(event.message, "channel")
    }
    assert channels, "expected channel-carrying messages"


def test_track_count_matches_expected_spread():
    for expected_count, path in TRACK_COUNT_SAMPLES.items():
        n = NormalizedMidiFile.from_file(path)
        assert len(n.tracks) == expected_count, path


def test_events_within_a_track_are_tick_ordered():
    n = NormalizedMidiFile.from_file(CLEAN_SAMPLE)
    for track in n.tracks:
        ticks = [e.abs_tick for e in track.events]
        assert ticks == sorted(ticks)


def test_rejects_unsupported_format():
    import types

    import pytest

    fake = types.SimpleNamespace(type=2, ticks_per_beat=480, tracks=[])
    with pytest.raises(ValueError, match="unsupported MIDI format"):
        NormalizedMidiFile.from_mido(fake)
