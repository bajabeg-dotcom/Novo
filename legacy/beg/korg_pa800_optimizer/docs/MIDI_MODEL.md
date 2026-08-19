# MIDI Model

## Raw vs. Normalized

**Raw import**: when a `.mid` file is imported, its bytes are never
modified. The importer computes a SHA-256 hash, records file metadata
(source path, import timestamp, parser version), and stores the file
under `data/factory/{synthetic,real}/` (or wherever the caller directs
for non-factory input) exactly as received. This raw copy is the
permanent source of truth for that file.

**Normalized model**: a derived, in-memory (and DB-summarized)
representation built from the raw file, sufficient to reconstruct the
original without loss of any relevant information (see round-trip
requirement below). The normalized model is what all analysis and
optimization code operates on — raw bytes are never touched again after
import.

## What must be represented

Standard MIDI File format 0 and format 1: tracks, ticks, PPQ, tempo map,
time signature, Note On/Off (with velocity), Control Change, Pitch
Bend, Program Change, Bank Select (MSB/LSB), Channel/Polyphonic
Aftertouch, NRPN, RPN, SysEx.

## Round-trip requirement

Import -> normalize -> export (with no optimization applied) must
reproduce a MIDI file that is musically equivalent to the original
(same notes, timing, controller data) even if not byte-identical.

**Implemented.** `midi/normalized_model.py` wraps each raw
`mido.Message`/`mido.MetaMessage` in a `NormalizedEvent` (message +
absolute tick) rather than re-inventing a parallel dataclass per
message type — this guarantees zero information loss for every message
type mido supports (Note On/Off, CC, Pitch Bend, Program Change, Bank
Select, Aftertouch, SysEx, all meta events) without a second model that
could silently drop a field. NRPN/RPN are not first-class MIDI message
types — they are a convention built from a sequence of plain Control
Change messages, so preserving every CC losslessly preserves NRPN/RPN
sequences for free; semantic interpretation of what a sequence *means*
is deferred to Vertical C (`mapping/`, `rx/`, Phase 7-8). `midi/writer.py`
reconstructs an SMF from a normalized model, preserving track count and
order. The round-trip test (`tests/unit/midi/test_writer_roundtrip.py`)
runs against both format-1 (real Factory Style, `data/factory/real/`)
and format-0 (real Golden Dataset song performances,
`data/golden/songs/`) samples, asserting equivalence of notes, CC
(incl. raw NRPN/RPN constituent CCs), program changes, pitch bend,
sysex, and tempo/time-signature maps.

## Preservation-mode semantics

Certain track roles default to **preservation mode**, meaning:
- no pitch change,
- no onset/duration change,
- no unauthorized articulation change.

This applies by default to:
- **Solo** tracks (see `docs/SOLO_SPECIFICATION.md`),
- existing **Terca** (harmonized third) tracks,
- existing **Delay** tracks.

A protected event must remain protected through the entire pipeline —
downstream optimizer stages must check preservation status before
proposing any change, not just at the end.

## KORG-safe export contract

Export must produce a Standard MIDI File (format 0 or format 1,
depending on what the use case requires) that:
- preserves all preservation-mode content unchanged,
- only contains RX/DNC triggers that passed the RX Safety Engine
  (see `docs/RX_SPECIFICATION.md`),
- never silently strips SysEx or other data unless an explicit,
  documented project rule says to (see spec §41) — no undocumented
  data loss.

`midi/writer.py` (implemented, see above) provides the write mechanism
Vertical C's future `export/korg_safe_export.py` will call; the
preservation-mode and RX-safety enforcement described above are not
implemented yet (Vertical B/C, Phase 9+ and Phase 8) — this section
remains the agreed contract for when they are.

## Status

`midi/raw_import.py`, `midi/normalized_model.py`, `midi/writer.py`, and
`midi/validators.py` are implemented (hash-only raw import; format 0/1
normalized model; SMF writer; structural validators covering PPQ,
format, `end_of_track` presence, channel range, and delta-time
ordering). Verified against the real Factory Style corpus (3211 files,
format 1, 4-50 tracks) and the real Golden Dataset (182 files, format
0, single track/16 channels) — see `docs/DATABASE_ARCHITECTURE.md` for
where that real evidence now lives.
