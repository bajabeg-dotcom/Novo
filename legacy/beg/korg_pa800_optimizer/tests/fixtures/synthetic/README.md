# Synthetic Test Fixtures

Pipeline/unit-test MIDI fixtures (owned by Vertical A). Distinct from
`data/factory/synthetic/` — these are for exercising `midi/` and
`factory/` code paths directly, not for DNA/Gold DNA.

Contains the same 3 minimal, deterministic `.mid` files as
`data/factory/synthetic/` (format-0 notes/CC/program-change/pitch-bend,
format-1 two-track, format-0 sysex/aftertouch) — kept in both places so
low-level MIDI Core unit tests don't have to go through the ingestion
pipeline just to get a fixture.
