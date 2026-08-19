"""Raw MIDI import: hash and record source metadata without ever
mutating the original file's bytes.

Contract: this module never opens a file for writing and never moves
or renames anything -- placing a file under its canonical location
(e.g. data/factory/real/) is the caller's responsibility (in practice,
git). This keeps the "raw preservation" guarantee absolute: import can
never be the thing that alters a source file. See docs/MIDI_MODEL.md
"Raw vs. Normalized" and docs/DATABASE_ARCHITECTURE.md source_files
table.

Owning vertical: A.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..infrastructure import hashing


@dataclass(frozen=True)
class SourceFileRecord:
    """Facts about one file on disk, computed without modifying it."""

    path: Path
    sha256_hash: str
    byte_size: int


def import_file(path: str | Path) -> SourceFileRecord:
    """Compute a SHA-256 hash and byte size for the file at ``path``.

    Read-only: does not copy, move, or modify ``path`` in any way.
    """
    path = Path(path)
    return SourceFileRecord(
        path=path,
        sha256_hash=hashing.sha256_file(path),
        byte_size=path.stat().st_size,
    )
