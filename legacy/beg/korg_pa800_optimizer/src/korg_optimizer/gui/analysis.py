"""Read-only MIDI analysis for the web GUI.

Runs an uploaded file through the existing, implemented Phase 1-4
pipeline (raw hash -> normalized model -> structural validation ->
Factory Evidence extraction) and returns a plain-dict result the
templates can render. Does not write to evidence.db and does not
catalog the file as SYNTHETIC/REAL/Golden -- an arbitrary user-uploaded
song is "Song MIDI" (docs/SONG_LAYER_SPECIFICATION.md), not Factory or
Golden material, so this is deliberately ephemeral, read-only analysis.

There is no optimization step here because none exists yet
(docs/ROADMAP.md Phase 5+, Vertical B/C) -- this module must never
imply otherwise. See docs/ARCHITECTURE.md for why this is a documented,
temporary exception to the "gui only calls optimizer.engine" rule: with
no optimizer implemented, the GUI calls midi/ and factory/ directly for
analysis only, and applies no mutation.

Owning vertical: C (GUI), calling into Vertical A's already-implemented
midi/ and factory/ modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..factory.evidence_source import extract_evidence
from ..infrastructure.hashing import sha256_file
from ..midi.normalized_model import NormalizedMidiFile
from ..midi.validators import validate_structure


def _ticks_to_seconds(tempo_map, ppq: int, target_tick: int) -> float:
    """Convert an absolute tick position to seconds using the file's
    tempo map (defaulting to 120 BPM before the first tempo event, or
    if there is no tempo map at all). Display convenience only -- not
    part of the core normalized model.
    """
    default_tempo = 500_000  # microseconds per quarter note = 120 BPM
    seconds = 0.0
    prev_tick = 0
    prev_tempo = default_tempo
    for entry in tempo_map:
        if entry.abs_tick >= target_tick:
            break
        seconds += (entry.abs_tick - prev_tick) / ppq * (prev_tempo / 1_000_000)
        prev_tick = entry.abs_tick
        prev_tempo = entry.tempo
    seconds += (target_tick - prev_tick) / ppq * (prev_tempo / 1_000_000)
    return seconds


def analyze_uploaded_file(path: Path, *, original_filename: str) -> dict[str, Any]:
    """Analyze an uploaded MIDI file and return a rendering-ready dict.

    Never mutates ``path``. Never writes to any database.
    """
    sha256_hash = sha256_file(path)
    byte_size = path.stat().st_size

    normalized = NormalizedMidiFile.from_file(path)
    issues = validate_structure(normalized)
    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    records = extract_evidence(normalized, source_file_id=None, file_path=path)
    file_level = next((r for r in records if r.track_index is None), None)
    track_records = sorted(
        (r for r in records if r.track_index is not None), key=lambda r: r.track_index
    )

    duration_ticks = (file_level.event_summary.get("duration_ticks", 0) if file_level else 0)
    duration_seconds = _ticks_to_seconds(normalized.tempo_map, normalized.ppq, duration_ticks)

    tracks = []
    for record in track_records:
        summary = record.event_summary
        tracks.append(
            {
                "index": record.track_index,
                "name": summary.get("track_name"),
                "channel": summary.get("channel"),
                "note_count": summary.get("note_count", 0),
                "pitch_range": summary.get("pitch_range"),
                "velocity_range": summary.get("velocity_range"),
                "cc_numbers_used": summary.get("cc_numbers_used", []),
                "program_changes": summary.get("program_changes", []),
                "sysex_count": summary.get("sysex_count", 0),
            }
        )

    return {
        "original_filename": original_filename,
        "sha256_hash": sha256_hash,
        "byte_size": byte_size,
        "format": normalized.format,
        "ppq": normalized.ppq,
        "track_count": len(normalized.tracks),
        "duration_ticks": duration_ticks,
        "duration_seconds": duration_seconds,
        "tempo_events": len(normalized.tempo_map),
        "time_signature_events": len(normalized.time_signature_map),
        "style_name": file_level.style_name if file_level else None,
        "style_section": file_level.style_section if file_level else None,
        "section_evidence_level": file_level.section_evidence_level if file_level else "UNKNOWN",
        "style_name_filename_mismatch": (
            file_level.event_summary.get("style_name_filename_mismatch", False)
            if file_level
            else False
        ),
        "validation_errors": [i.message for i in errors],
        "validation_warnings": [i.message for i in warnings],
        "is_valid": not errors,
        "tracks": tracks,
    }
