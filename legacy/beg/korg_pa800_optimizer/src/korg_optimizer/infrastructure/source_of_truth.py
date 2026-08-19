"""Shared CONFIRMED / INFERRED / UNKNOWN evidence-level tagging.

Central place for the evidence-level enum used throughout the project
per the source-of-truth hierarchy in docs/PROJECT_GOAL.md: higher
authority (CONFIRMED) must never be silently overridden by a lower one
(INFERRED, UNKNOWN).

Owning vertical: A.
"""

from __future__ import annotations

from enum import Enum


class EvidenceLevel(str, Enum):
    """A claim's basis, from strongest to weakest authority."""

    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


_AUTHORITY_RANK = {
    EvidenceLevel.UNKNOWN: 0,
    EvidenceLevel.INFERRED: 1,
    EvidenceLevel.CONFIRMED: 2,
}


def is_at_least(level: EvidenceLevel | str, minimum: EvidenceLevel | str) -> bool:
    """True if ``level`` meets or exceeds ``minimum`` on the
    CONFIRMED > INFERRED > UNKNOWN authority scale.
    """
    return _AUTHORITY_RANK[EvidenceLevel(level)] >= _AUTHORITY_RANK[EvidenceLevel(minimum)]
