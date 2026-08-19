# Ornament Specification

## Scope (once implemented)

Automatic discovery of ornamentation patterns in Factory Evidence and
Song MIDI, not limited to a fixed hand-authored list. Categories to
look for: trill, upper/lower trill, mordent, inverted mordent, turn,
inverted turn, grace note, acciaccatura, appoggiatura, neighbor note,
passing ornament, tremolo, repeated-note ornament, slide, bend, fall,
scoop, hammer-on, pull-off — and any other pattern the data supports.

Trill detection specifically has its own document:
`docs/TRILL_SPECIFICATION.md`, since it is the most failure-prone
category (see false-positive requirement below).

## False-positive test requirement

Ornament detection (like trill detection) must be validated against
fixtures that are deliberately **not** ornaments, so the detector
proves it can tell the difference rather than over-firing on anything
fast or repetitive:

- scale run
- arpeggio
- repeated melody / motif
- tremolo (as pure texture, not an intentional ornament)
- drum roll
- normal accompaniment pattern

Fixture location (created empty in this skeleton, populated when
Vertical B implements this phase): `tests/fixtures/ornaments/`.

## Status

`src/korg_optimizer/musical/ornament_dna.py` is a docstring-only stub.
Depends on Factory DNA / Gold DNA infrastructure (Phase 5-6) and
harmonic context (Phase 10) per `docs/ROADMAP.md`; implemented at
Phase 12.
