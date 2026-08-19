"""Structural MIDI validation: event ordering, timing, PPQ, tracks,
channels. Feeds the "MIDI" validation category in
docs/VALIDATION_SPECIFICATION.md -- musical/RX validation categories
are Vertical C's concern (Phase 16), not this module's.

Owning vertical: A.
"""

from __future__ import annotations

from dataclasses import dataclass

from .normalized_model import SUPPORTED_FORMATS, NormalizedMidiFile


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "ERROR" | "WARNING"
    message: str


def validate_structure(normalized: NormalizedMidiFile) -> list[ValidationIssue]:
    """Structural checks only -- does not interpret musical content."""
    issues: list[ValidationIssue] = []

    if normalized.ppq <= 0:
        issues.append(ValidationIssue("ERROR", f"invalid ppq: {normalized.ppq}"))
    if normalized.format not in SUPPORTED_FORMATS:
        issues.append(
            ValidationIssue("ERROR", f"unsupported format: {normalized.format}")
        )
    if not normalized.tracks:
        issues.append(ValidationIssue("ERROR", "no tracks present"))

    for track in normalized.tracks:
        has_end_of_track = False
        prev_tick = 0
        for event in track.events:
            if event.abs_tick < prev_tick:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"track {track.index}: negative delta at tick {event.abs_tick}",
                    )
                )
            prev_tick = event.abs_tick

            msg = event.message
            if getattr(msg, "is_meta", False) and msg.type == "end_of_track":
                has_end_of_track = True

            channel = getattr(msg, "channel", None)
            if channel is not None and not (0 <= channel <= 15):
                issues.append(
                    ValidationIssue(
                        "ERROR", f"track {track.index}: invalid channel {channel}"
                    )
                )

        if not has_end_of_track:
            issues.append(
                ValidationIssue(
                    "WARNING", f"track {track.index}: missing end_of_track meta event"
                )
            )

    return issues


def is_valid(normalized: NormalizedMidiFile) -> bool:
    """True if there are no ERROR-severity issues (WARNINGs are allowed)."""
    return not any(issue.severity == "ERROR" for issue in validate_structure(normalized))
