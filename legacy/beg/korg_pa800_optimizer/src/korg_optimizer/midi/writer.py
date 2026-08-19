"""Writes a normalized model back out to a Standard MIDI File.

Used by export.korg_safe_export for the final KORG-safe write and by
the round-trip test (docs/MIDI_MODEL.md, docs/TEST_STRATEGY.md).
Preserves the original track count and order -- a deliberate choice
that keeps channel/track mapping stable for evidence extraction
(factory/evidence_source.py's per-track rows assume this).

Owning vertical: A.
"""

from __future__ import annotations

from pathlib import Path

import mido

from .normalized_model import NormalizedMidiFile


def write(normalized: NormalizedMidiFile, dest_path: str | Path) -> None:
    """Write ``normalized`` to ``dest_path`` as a Standard MIDI File.

    Each track's events are assumed to already be in non-decreasing
    ``abs_tick`` order (true for anything produced by
    ``NormalizedMidiFile.from_mido``/``from_file``); delta times are
    recomputed from that order rather than re-sorted, so ties at the
    same tick keep their original relative order.
    """
    dest_path = Path(dest_path)
    midi_file = mido.MidiFile(type=normalized.format, ticks_per_beat=normalized.ppq)

    for track in normalized.tracks:
        mido_track = mido.MidiTrack()
        prev_tick = 0
        for event in track.events:
            delta = event.abs_tick - prev_tick
            mido_track.append(event.message.copy(time=delta))
            prev_tick = event.abs_tick
        midi_file.tracks.append(mido_track)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    midi_file.save(str(dest_path))
