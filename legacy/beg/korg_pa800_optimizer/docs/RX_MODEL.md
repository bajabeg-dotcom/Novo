# RX Model (schema / data shape)

Behavioral rules for how RX facts are used are in
`docs/RX_SPECIFICATION.md`. This document defines the shape and
tagging discipline of RX-related data. Physical columns are in
`docs/DATABASE_ARCHITECTURE.md` (`rx_articulations`, `gm_rx_mapping`).

## Articulation trigger taxonomy

An RX/DNC articulation is triggered by exactly one of:
- **Key switch** — a specific note outside the playable range used as a trigger
- **Controller (CC)** — a specific CC number/value range
- **Velocity range** — a specific velocity band on an otherwise normal note
- **NRPN** — non-registered parameter number/value
- **RPN** — registered parameter number/value
- **SysEx** — a system-exclusive message

Every `RxArticulation` record must state exactly which trigger type it
uses and the exact trigger value(s) — never a vague description.

## Field-level tagging rules

Every field that encodes a specific Korg-specific value (a trigger
value, an address, a program number, a mapping target) carries its own
`evidence_level`:

- `CONFIRMED` — observed directly in real Factory MIDI evidence, in
  official KORG documentation, or via physical PA800 testing.
- `INFERRED` — reasoned/generalized from confirmed facts (e.g. a
  pattern seen across many confirmed instances, generalized to a
  related instrument not yet directly observed).
- `UNKNOWN` — no basis. Must never be presented as usable and must
  never be acted on by the RX Safety Engine or Optimizer.

## Candidate discovery scope (not implemented yet)

The system must be able to discover new articulation patterns in
Factory Evidence, not just match a fixed hand-authored list. Categories
to look for once Factory ingestion exists (Phase 8, per
`docs/ROADMAP.md`): noise slide, slide, finger slide, pick slide, fret
noise, string noise, attack/release noise, hammer-on, pull-off, bend,
vibrato, tremolo, harmonic, mute, dead note, ghost note, fall, scoop,
grace note, trill, turn, mordent — and anything else the data actually
supports, without being limited to this list.

## Negative rules

Every `RxArticulation` should record contexts in which it must **not**
trigger (`negative_rules`), since avoiding accidental activation is as
important as enabling intentional use — see the RX Safety Engine in
`docs/RX_SPECIFICATION.md`.
