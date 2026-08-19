"""Application path configuration.

All paths are resolved relative to the ``korg_pa800_optimizer`` package
root so the package works the same regardless of the caller's current
working directory. Every constant here is a plain ``pathlib.Path`` that
callers (including tests) may override by passing an explicit path
instead of the default.

Owning vertical: A.
"""

from __future__ import annotations

from pathlib import Path

# korg_pa800_optimizer/src/korg_optimizer/infrastructure/config.py
# parents[0]=infrastructure  [1]=korg_optimizer  [2]=src  [3]=korg_pa800_optimizer
PACKAGE_ROOT = Path(__file__).resolve().parents[3]

DATA_ROOT = PACKAGE_ROOT / "data"
FACTORY_ROOT = DATA_ROOT / "factory"
FACTORY_REAL_ROOT = FACTORY_ROOT / "real"
FACTORY_SYNTHETIC_ROOT = FACTORY_ROOT / "synthetic"

GOLDEN_ROOT = DATA_ROOT / "golden"
GOLDEN_SONGS_ROOT = GOLDEN_ROOT / "songs"

DATABASES_ROOT = DATA_ROOT / "databases"
EVIDENCE_DB_PATH = DATABASES_ROOT / "evidence.db"
KNOWLEDGE_DB_PATH = DATABASES_ROOT / "knowledge.db"

# runtime.db path is not defined here yet -- its schema belongs to
# Vertical C (Phase 15+), per docs/DATABASE_ARCHITECTURE.md
# "Ownership / write access per Vertical".
