# M01/M06 parser parity audit — 2026-08-14

## Decision

**PASS** for the directly tested core read-only parity scope.

The parsers remain separate implementations. This guard is the approved
alternative to immediate physical unification, but it does not certify every
SMF feature, writer behavior or round-trip output.

## Structural gates aligned

Both `MidiAnalyzer` and `StandardMidiLoader` now:

- require at least one declared track;
- require exactly one track for SMF Format 0;
- reject PPQ division zero;
- accept only SMPTE frame codes -24, -25, -29 and -30;
- reject SMPTE ticks-per-frame zero;
- report a missing End-of-Track event;
- reject malformed headers, tracks, VLQs, running status, SysEx, system status
  and invalid channel data used by the test matrix.

## Parity fingerprint

The executable oracle compares:

- format, track count, division and SHA-256;
- per-track end ticks;
- event-kind counts;
- closed notes and the analyzer's documented synthetic representation of
  unterminated Note On events;
- tempo, meter and key-signature data;
- track names;
- programs, controllers and pitch-bend counts;
- byte reconstruction for the byte-preserving parser.

## First corpus finding

The first full corpus run reported 410 differences. Investigation showed that
the parsed MIDI events agreed: those files contain unmatched Note On events.
`MidiAnalyzer` intentionally exposes each as an `unterminated_notes` item ending
at the track boundary, while `StandardMidiLoader` keeps the raw Note On event
without manufacturing a Note Off.

The test oracle was corrected to derive the analyzer view from the preserved
events. Production source events were not changed or normalized.

## Tests

File: `tests/test_parser_parity.py`

Covered cases:

1. event-rich valid SMF with running status, SysEx, meta events, Bank Select,
   Program Change, sustain, poly/channel aftertouch, pitch bend and Note On zero;
2. malformed acceptance matrix;
3. missing End-of-Track reporting;
4. valid SMPTE division;
5. all 3,211 Factory MIDI members.

Dedicated command:

```bash
python -m pytest -q tests/test_parser_parity.py
```

Result: **5 passed, 3,223 subtests passed** in 31.16 seconds.

Full command:

```bash
python -m pytest -q
```

Result: **74 passed, 3,229 subtests passed, 0 failed, 0 skipped** in
235.43 seconds.

Factory archive SHA-256 before and after:
`ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`.

## Remaining boundary

Physical parser unification can still be considered later, especially before a
writer is introduced. The current PASS only means that the tested core
interpretation is equal; unknown writer/round-trip behavior remains NO-GO.
