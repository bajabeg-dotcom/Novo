# Databases

Runtime location for `evidence.db`, `knowledge.db`, and `runtime.db`
(see `docs/DATABASE_ARCHITECTURE.md`). `*.db`/`*.sqlite`/`*.sqlite3`
files here are gitignored — only this README is tracked.

`evidence.db` is now created here on demand by
`infrastructure/database/connection.get_connection` +
`ensure_schema` (called automatically by `factory/real_dataset.py`,
`factory/synthetic_dataset.py`, and `infrastructure/golden_dataset.py`
when run without an explicit connection) — populated with the real
Factory Style and Golden Dataset evidence described in
`data/factory/real/README.md` and `data/golden/README.md`. It is not
committed to git (gitignored, regenerable by re-running ingestion).
`knowledge.db` and `runtime.db` remain undefined — those schemas
belong to Vertical B / Vertical C (Phase 5+).
