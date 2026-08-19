"""SHA-256 file and content hashing.

Used for raw MIDI preservation (docs/MIDI_MODEL.md) and idempotent
Factory import (docs/DATABASE_ARCHITECTURE.md).

Owning vertical: A.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the hex-encoded SHA-256 digest of the file at ``path``.

    Reads in fixed-size chunks so large files don't need to be loaded
    into memory at once. Never opens the file for writing.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()
