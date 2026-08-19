# Song Layer Specification

## Scope distinction

Two kinds of input MIDI matter to this project, and they must not be
conflated:

- **Factory Style MIDI** — KORG PA800 Style pattern material (Factory
  Evidence source, per `docs/DATA_MODEL.md`). Read-only, used to derive
  Factory DNA / Gold DNA. See `docs/DATABASE_ARCHITECTURE.md`.
- **Song MIDI** — arbitrary GM MIDI files the optimizer is asked to
  process (import -> optimize -> export). This is the actual product
  input; it is not evidence.

## Song layer understanding (once implemented)

For a Song MIDI file, the system must identify and reason about
interacting layers: Solo, Bass, Drums, Chord/Pad, Harmony/Terca, Delay,
Guitar, Brass/Strings/Percussion, and Unknown — see `MusicalRole` in
`docs/DATA_MODEL.md`. Layer interaction (e.g. how a Delay track relates
in timing/pitch to the Solo it echoes) informs both preservation rules
and, in Generative Mode, generation constraints.

## Status

Not implemented in this Phase 0-1 skeleton. Song-layer role
classification depends on Solo/Harmony/Ornament/Trill DNA modules,
which are docstring-only stubs at this phase (Vertical B,
`docs/ROADMAP.md` Phase 9-14).
