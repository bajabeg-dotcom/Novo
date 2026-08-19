# Solo Specification

## What Solo DNA must understand (once implemented)

Monophony, phrase structure, register, interval content, direction,
legato, pitch bend, modulation, expression, aftertouch, ornaments,
trills, and RX articulation usage on the track identified as the
melodic/solo source of a piece.

Solo is treated as the **master melodic source** — other engines
(harmony/Terca, delay) reference it, not the other way around.

## Preservation mode (default)

When a track is identified as Solo:
- **no pitch change**
- **no structural rewrite**
- **no unauthorized articulation change**

A protected Solo event must remain protected through the entire
pipeline. Any optimizer stage that touches a Solo-owned event without
an explicit, evidence-backed, user-visible exception is a defect.

## Detection criteria

Not yet defined at the algorithmic level — this is Vertical B work for
Phase 9 (`docs/ROADMAP.md`). This document exists now so that when that
work begins, "Solo" has an agreed meaning (monophonic, melodic-lead
role) that Vertical A's `musical role` classification
(`docs/DATA_MODEL.md` `MusicalRole`) and Vertical C's RX Safety Engine
(`docs/RX_SPECIFICATION.md`) can both rely on without re-deriving it.

## Status

`src/korg_optimizer/musical/solo_dna.py` is a docstring-only stub.
