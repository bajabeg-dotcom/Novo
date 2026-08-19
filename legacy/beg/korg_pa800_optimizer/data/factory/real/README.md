# Real Factory Data

Real KORG PA800 factory `.mid` material goes here. Loaded via
`factory/real_dataset.py`, which hardcodes `source_kind=REAL` on every
record it produces — these files are the only legitimate source of
Factory Evidence for Factory DNA / Gold DNA (`docs/PROJECT_GOAL.md`,
`docs/GOLD_DNA_SPECIFICATION.md`).

Only `.mid` files are accepted (no `.sty`/`.set` proprietary binary
formats).

## `Workspace_Styles/`

3211 real KORG Style Element `.mid` files across 248 factory styles,
`<StyleName>/<StyleName>_<Section>.mid` (section ∈ Break, End1-3,
Fill1-2, Intro1-3, Var1-4 — KORG's own export convention). Ingested
into `evidence.db` (`source_files` + per-track/file-level
`factory_evidence`, including filename-derived `style_name`/
`style_section`) by `factory/real_dataset.py` — see
`docs/DATABASE_ARCHITECTURE.md`. 208 of the 3211 files have a
filename/directory-name disagreement (mostly `_3_4_`
time-signature-variant qualifiers, plus one style whose true name
contains `/`); this is recorded raw via a
`style_name_filename_mismatch` flag, never interpreted or corrected —
see `docs/PROJECT_GOAL.md` decisions log.
