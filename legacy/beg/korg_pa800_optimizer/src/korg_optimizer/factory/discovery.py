"""Discovers candidate .mid files on disk (idempotent import,
duplicate detection via hash happens downstream in _ingest_common).
See docs/DATABASE_ARCHITECTURE.md "Integrity requirements".

Owning vertical: A.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator


def discover_files(root: str | Path, *, suffix: str = ".mid") -> Iterator[Path]:
    """Recursively yield files under ``root`` whose extension matches
    ``suffix``, case-insensitively (real Factory exports mix `.mid`
    and `.MID`). Yields in a stable (sorted) order.
    """
    root = Path(root)
    if not root.exists():
        return
    suffix_lower = suffix.lower()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() == suffix_lower:
            yield path
