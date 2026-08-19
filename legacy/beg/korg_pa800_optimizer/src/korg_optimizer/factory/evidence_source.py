"""Extracts factory_evidence records (raw structural facts) from an
imported MIDI file. See docs/DATA_MODEL.md "evidence" and
docs/DATABASE_ARCHITECTURE.md.

Explicitly out of scope: any GM/RX interpretation of Program Change
values -- program numbers are stored raw. Instrument identity and RX
mapping are Vertical C's concern (Phase 7-8).

Owning vertical: A.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..midi.normalized_model import NormalizedMidiFile

EXTRACTOR_VERSION = "0.1.0"

# The 13 KORG Style Element section tokens (docs/DATABASE_ARCHITECTURE.md).
SECTION_TOKENS = (
    "Break",
    "End1",
    "End2",
    "End3",
    "Fill1",
    "Fill2",
    "Intro1",
    "Intro2",
    "Intro3",
    "Var1",
    "Var2",
    "Var3",
    "Var4",
)


@dataclass
class FactoryEvidenceRecord:
    source_file_id: int | None  # None for ad-hoc analysis not backed by a source_files row (e.g. gui/analysis.py)
    track_index: int | None
    style_name: str | None
    style_section: str | None
    section_evidence_level: str | None
    event_summary: dict[str, Any] = field(default_factory=dict)
    extracted_at: str = ""
    extractor_version: str = EXTRACTOR_VERSION

    @property
    def event_summary_json(self) -> str:
        return json.dumps(self.event_summary, sort_keys=True)


def parse_style_section(file_path: Path) -> tuple[str, str | None, str, bool]:
    """Derive ``(style_name, style_section, evidence_level,
    filename_mismatch)`` from a Factory Style file's directory name and
    filename.

    ``style_name`` is the parent directory name, taken verbatim
    (always CONFIRMED -- it's a direct filesystem fact). The section is
    found by matching the right-most ``_<token>`` suffix of the
    filename (minus extension) against the 13 known Style Element
    tokens; this resolves all files in the real Factory Style corpus
    with zero unparseable cases. When no token matches, section and
    evidence_level are UNKNOWN -- never guessed.

    ``filename_mismatch`` is True when the filename's prefix (the part
    before the matched section token) differs from ``style_name`` --
    e.g. a `_3_4_` time-signature-variant qualifier, or a style whose
    true name contains a character (like `/`) that was mangled
    inconsistently between its directory and filename during export.
    This is recorded raw, never interpreted or corrected -- see
    docs/PROJECT_GOAL.md decisions log.
    """
    style_name = file_path.parent.name
    stem = file_path.stem

    for token in SECTION_TOKENS:
        suffix = "_" + token
        if stem.endswith(suffix):
            prefix = stem[: -len(suffix)]
            mismatch = prefix != style_name
            return style_name, token, "CONFIRMED", mismatch

    return style_name, None, "UNKNOWN", False


def _track_summary(track) -> dict[str, Any]:
    note_pitches: list[int] = []
    note_velocities: list[int] = []
    cc_numbers: set[int] = set()
    program_changes: list[dict[str, Any]] = []
    sysex_count = 0
    channel: int | None = None

    for event in track.events:
        msg = event.message
        if msg.type == "sysex":
            sysex_count += 1
            continue
        if getattr(msg, "is_meta", False):
            continue

        ch = getattr(msg, "channel", None)
        if ch is not None:
            channel = ch

        if msg.type == "note_on" and msg.velocity > 0:
            note_pitches.append(msg.note)
            note_velocities.append(msg.velocity)
        elif msg.type == "control_change":
            cc_numbers.add(msg.control)
        elif msg.type == "program_change":
            program_changes.append(
                {"abs_tick": event.abs_tick, "channel": msg.channel, "program": msg.program}
            )

    return {
        "channel": channel,
        "track_name": track.name,
        "note_count": len(note_pitches),
        "pitch_range": [min(note_pitches), max(note_pitches)] if note_pitches else None,
        "velocity_range": [min(note_velocities), max(note_velocities)]
        if note_velocities
        else None,
        "cc_numbers_used": sorted(cc_numbers),
        "program_changes": program_changes,
        "sysex_count": sysex_count,
    }


def extract_evidence(
    normalized: NormalizedMidiFile,
    source_file_id: int | None,
    *,
    file_path: Path | None = None,
) -> list[FactoryEvidenceRecord]:
    """Build factory_evidence rows for one imported file: one per-track
    row (raw per-track facts) plus, when ``file_path`` is given, one
    file-level row (``track_index=None``) carrying style/section
    metadata parsed from the filename.
    """
    now = datetime.now(timezone.utc).isoformat()
    records: list[FactoryEvidenceRecord] = []

    for track in normalized.tracks:
        records.append(
            FactoryEvidenceRecord(
                source_file_id=source_file_id,
                track_index=track.index,
                style_name=None,
                style_section=None,
                section_evidence_level=None,
                event_summary=_track_summary(track),
                extracted_at=now,
            )
        )

    if file_path is not None:
        style_name, style_section, section_evidence_level, mismatch = parse_style_section(
            Path(file_path)
        )
        channels_used = sorted(
            {
                getattr(event.message, "channel", None)
                for track in normalized.tracks
                for event in track.events
                if getattr(event.message, "channel", None) is not None
            }
        )
        duration_ticks = max(
            (event.abs_tick for track in normalized.tracks for event in track.events),
            default=0,
        )
        records.append(
            FactoryEvidenceRecord(
                source_file_id=source_file_id,
                track_index=None,
                style_name=style_name,
                style_section=style_section,
                section_evidence_level=section_evidence_level,
                event_summary={
                    "format": normalized.format,
                    "ppq": normalized.ppq,
                    "track_count": len(normalized.tracks),
                    "channels_used": channels_used,
                    "duration_ticks": duration_ticks,
                    "style_name_filename_mismatch": mismatch,
                },
                extracted_at=now,
            )
        )

    return records


def save_evidence(conn: sqlite3.Connection, records: list[FactoryEvidenceRecord]) -> None:
    for r in records:
        conn.execute(
            """
            INSERT INTO factory_evidence
                (source_file_id, track_index, style_name, style_section,
                 section_evidence_level, event_summary_json, extracted_at, extractor_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r.source_file_id,
                r.track_index,
                r.style_name,
                r.style_section,
                r.section_evidence_level,
                r.event_summary_json,
                r.extracted_at,
                r.extractor_version,
            ),
        )
    conn.commit()
