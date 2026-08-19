# Golden Dataset

Curated representative examples used for regression testing (see
`docs/TEST_STRATEGY.md`). Intended subfolders (created when populated,
per the master spec): `styles/`, `instruments/`, `guitar/`, `bass/`,
`drums/`, `brass/`, `sax/`, `strings/`, `solo/`, `harmony/`, `delay/`,
`ornament/`, `trill/`. Each example is tagged GOOD / EDGE_CASE /
NEGATIVE / CONFIRMED_ARTICULATION / CONFIRMED_TRILL / CONFIRMED_RX.

## `songs/`

182 real full-band live-performance `.mid` recordings (format 0,
single track, all 16 channels interleaved) — real reference material
for future Solo/Harmony/Ornament/Trill DNA work. Cataloged (hashed,
manifested into `golden_files` + `songs/MANIFEST.json`) by
`infrastructure/golden_dataset.py`, but **not yet tagged** into the
GOOD/EDGE_CASE/CONFIRMED_* taxonomy above or split into the other
subfolders — that requires musical analysis and is deferred to
Vertical B, Phase 9+ (`docs/ROADMAP.md`). This is a manifest-only
catalog, not a claim about musical quality or correctness.

The other subfolders listed above remain empty at this phase.
