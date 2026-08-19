# Korg Pa800 MIDI Enhancer

Critical databases, catalogs and models are tracked by `data/artifact-manifest.json`.
Verify them before training or release:

```powershell
python -m pa800_enhancer artifacts audit data/artifact-manifest.json --root .
```

Set `PA800_ENHANCER_HOME` to use a portable resource pack from any working
directory. Without a portable pack, writable data defaults to the current
Windows user application-data directory.

Dependency-free Python MVP for inspecting, validating and safely exporting
Standard MIDI Files used in Korg Pa800 workflows.

## Gold/Factory DNA workflow

Build or refresh the evidence database from nested reference archives:

```powershell
python -m pa800_enhancer dna-learn "prism-uploads/DNA.zip (2)" --database data/pa800-enhancer.db
python -m pa800_enhancer dna-audit --database data/pa800-enhancer.db
```

Preview a confidence-gated correction, then explicitly apply it:

```powershell
python -m pa800_enhancer dna-optimize song.mid --database data/pa800-enhancer.db
python -m pa800_enhancer dna-optimize song.mid --database data/pa800-enhancer.db --apply --output song.optimized.mid
```

The fingerprint separates solo, accompaniment, drums and guitar. It records
source SHA-256 and locator evidence, onset rhythm, pitch/register, dynamics,
duration/articulation, chord density, syncopation, repetitions, trills, pitch
classes and drum-family usage. GUI optimization runs safe repairs and
instrument shaping first, applies sufficiently close Gold-role matches, and
validates the complete result before export.

## CPU MIDI generator

```powershell
python -m pa800_enhancer generator-train "prism-uploads/DNA.zip (2)" --checkpoint data/models/midi-gru.pt --epochs 10 --threads 2
python -m pa800_enhancer generator-generate --checkpoint data/models/midi-gru.pt --output generated.mid --roles solo accompaniment bass drums guitar --notes 256 --bars 32 --style folk --key D --scale minor
```

The PyTorch GRU runs on CPU, supports checkpoint resume, deterministic seeds,
temperature/top-k sampling and separate role conditioning. Every generated file
is re-imported and validated before it is accepted. The desktop File menu also
provides **Generate MIDI with CPU model** and opens the result directly in the
normal Optimize–Export workflow.

## Commands

On Windows, materialize the batch files with
`python -m pa800_enhancer windows-scripts .`, then run `install.bat` once. It
installs the local package for the current user and creates
`data\pa800-enhancer.db`. Afterwards, `run.bat` starts the graphical desktop
interface; an
optional MIDI path can be passed as its argument. The source templates are
stored as package data so environments that filter executable files can still
ship and recreate them exactly.

Paths passed to the application may be entered with or without surrounding
quotes. This is useful for Windows paths containing spaces, for example
`"C:\Users\Baja\Desktop\Song file.mid"`.

```text
python -m pa800_enhancer inspect song.mid
python -m pa800_enhancer validate song.mid
python -m pa800_enhancer rhythms song.mid
python -m pa800_enhancer parameters song.mid
python -m pa800_enhancer programs song.mid --profile profiles/pa800-template.json
python -m pa800_enhancer initialization song.mid
python -m pa800_enhancer init-update song.mid --channel 1 --cc0 0 --cc32 1 --program 2
python -m pa800_enhancer init-update song.mid --channel 1 --volume 100 --apply --output updated.mid
python -m pa800_enhancer sound-map song.mid --profile profile.json --program-event t0:e2 --target-voice piano
python -m pa800_enhancer sound-map song.mid --profile profile.json --program-event t0:e2 --target-voice piano --apply --output mapped.mid
python -m pa800_enhancer drum-map song.mid --profile profile.json --program-event t0:e2 --target-kit kit --source-note 35 --target-note 36
python -m pa800_enhancer drum-map song.mid --profile profile.json --program-event t0:e2 --target-kit kit --source-note 35 --target-note 36 --apply --output drums-mapped.mid
python -m pa800_enhancer curves song.mid --tolerance 1.0
python -m pa800_enhancer curves song.mid --tolerance 1.0 --apply --output song-thinned.mid
python -m pa800_enhancer sysex song.mid
python -m pa800_enhancer expression song.mid --max-error-db 0.5
python -m pa800_enhancer expression song.mid --channel 1 --apply --output song-expression.mid
python -m pa800_enhancer auto song.mid --policy policies/assisted.json --report song.auto-report.json
python -m pa800_enhancer auto song.mid --policy policies/assisted.json --approve controller-thinning:t0:ch1:cc11 --apply --output song-pa800.mid --report song.auto-report.json
python -m pa800_enhancer auto song.mid --policy policies/pa800-ready.json --profile profiles/pa800-confirmed.json --init 1,program=2,cc7=100 --sound-map t0:e2=piano --report song.auto-report.json
python -m pa800_enhancer optimize song.mid --grid 16
python -m pa800_enhancer optimize song.mid --grid 16 --apply --output song-pa800.mid
python -m pa800_enhancer velocity-shape song.mid --family strings --seed 0
python -m pa800_enhancer velocity-shape song.mid --family strings --seed 0 --apply --output shaped.mid
python -m pa800_enhancer velocity-shape song.mid --family strings --catalog data/performance-reference-catalog.json --address 0:0:48:ch1 --apply --output shaped.mid
python -m pa800_enhancer velocity-auto song.mid --catalog data/performance-reference-catalog.json
python -m pa800_enhancer velocity-auto song.mid --catalog data/performance-reference-catalog.json --apply --output shaped.mid
python -m pa800_enhancer articulation-auto song.mid --catalog data/performance-reference-catalog.json
python -m pa800_enhancer articulation-auto song.mid --catalog data/performance-reference-catalog.json --apply --output articulated.mid
python -m pa800_enhancer performance-auto song.mid --catalog data/performance-reference-catalog.json --report song.performance.json
python -m pa800_enhancer performance-auto song.mid --catalog data/performance-reference-catalog.json --apply --output performance.mid --report song.performance.json
python -m pa800_enhancer performance-batch input-midi output-midi --catalog data/performance-reference-catalog.json --report batch.preview.json
python -m pa800_enhancer performance-batch input-midi output-midi --catalog data/performance-reference-catalog.json --apply --report batch.apply.json
python -m pa800_enhancer export song.mid song-copy.mid --mode preserve
python -m pa800_enhancer export song.mid song-edited.mid --mode segment-preserve
python -m pa800_enhancer export song.mid song-normalized.mid --mode canonical
python -m pa800_enhancer project song.mid song.pa800-project.json
python -m pa800_enhancer recover song.pa800-project.json
python -m pa800_enhancer resample song.mid song-384.mid --ppq 384
python -m pa800_enhancer profile validate profiles/pa800-template.json
python -m pa800_enhancer profile show profiles/pa800-template.json
python -m pa800_enhancer profile promote-hardware profiles/pa800-template.json hardware-tests/piano-001.json profiles/pa800-confirmed.json --voice-id piano --new-profile-id pa800-confirmed --new-version 1.0.0
python -m pa800_enhancer profile schema
python -m pa800_enhancer hardware validate hardware-tests/sound-piano.json
python -m pa800_enhancer hardware show hardware-tests/sound-piano.json
python -m pa800_enhancer hardware generate sound hardware-tests --case-id piano-001 --cc0 0 --cc32 1 --program 2 --expected-name Piano --os-version 1.60 --resources-version 1.60
python -m pa800_enhancer hardware generate drum hardware-tests --case-id kick-001 --cc0 120 --cc32 0 --program 0 --note 36 --expected-name Kick --expected-kit-name "Test Kit" --os-version 1.60 --resources-version 1.60
python -m pa800_enhancer hardware record-cycle hardware-tests/piano-001.json hardware-tests/piano-001-cycle1.json --cycle 1 --status passed --tested-at 2026-08-19 --tester operator --output-midi pa800-output.mid --observations observations.json --log "Loaded, saved and reloaded"
python -m pa800_enhancer hardware schema
python -m pa800_enhancer database init data/pa800-enhancer.db
python -m pa800_enhancer database status data/pa800-enhancer.db
python -m pa800_enhancer database import-profile profiles/pa800-template.json --database data/pa800-enhancer.db
python -m pa800_enhancer database import-hardware hardware-tests/piano-001.json --database data/pa800-enhancer.db
python -m pa800_enhancer policy create policies/assisted.json --policy-id assisted --version 1.0.0 --mode assisted --package full_assisted
python -m pa800_enhancer policy create policies/pa800-ready.json --policy-id pa800-ready --version 1.0.0 --mode assisted --package pa800_ready --profile-id pa800-confirmed --profile-sha256 SHA256
python -m pa800_enhancer policy validate policies/assisted.json
python -m pa800_enhancer policy show policies/assisted.json
python -m pa800_enhancer policy schema
python -m pa800_enhancer windows-scripts .
python -m pa800_enhancer corpus prism-uploads --output data/corpus-report.json
python -m pa800_enhancer reference-learn prism-uploads --output data/performance-reference-catalog.json
python -m pa800_enhancer ui song.mid
```

`corpus` recursively analyzes MIDI files in directories, individual MIDI
files, ZIP archives and nested ZIP archives. Archive detection uses content,
not only the filename extension. It writes an atomic, schema-versioned JSON
report containing hashes, parse/validation status, timing and aggregated issue
codes. Parse failures are isolated to their entry, while `--fail-on-blocked`
can additionally make validation blockers fail a CI or release gate. Corpus
files remain external reference material and are not copied into the package.

The dependency-free Tk desktop interface provides Open MIDI, summary,
validation findings, ranked rhythm candidates, basic optimization suggestions,
explicit multi-selection review, atomic apply, undo/redo, project save and
validated MIDI export. `run.bat` opens the same interface without requiring a
terminal command. After updating an older checkout, regenerate the launchers
with `python -m pa800_enhancer windows-scripts . --overwrite`. `install.bat`
also verifies that the selected Python installation includes Tcl/Tk support.

`preserve` writes the exact imported bytes and refuses a changed semantic
model. `segment-preserve` rebuilds changed deltas/messages while retaining
reusable original headers, chunks and event encodings. `canonical` writes a
normalized SMF representation, while `auto` selects the safest available
mode. Every export is reparsed, validated and receives a neighboring
`.report.json` report with input/output hashes.

Approved edits are converted to atomic `ChangeTransaction`/`ChangeGroup`
objects. Preconditions, model revisions, duplicate targets and event/track
locks are checked before mutation. `CommandHistory` provides undo/redo,
named checkpoints and rollback of all transactions produced by one module.
Project schema v2 persists command/redo history, checkpoints and event/track
locks. Atomic autosaves rotate three generations by default; `recover` selects
the newest valid generation while ignoring malformed autosave files.

Device profile schema v1 stores device/OS/resource identity, sounds, drum kits,
rhythms and field-level evidence. Every sound/kit address requires an evidence
reference; hardware-confirmed data additionally requires a device-test source,
tested OS, date and test reference. The loader rejects invalid MIDI ranges,
duplicate voice addresses, overlapping velocity layers and unsupported schema
versions. `profiles/pa800-template.json` deliberately contains no unverified
Pa800 bank or drum mappings.

`profile promote-hardware` accepts only a hardware case whose two complete
cycles passed every assertion. It writes a new profile identity/version,
records the canonical manifest digest as a `device_test` source and promotes
one selected sound or drum-note assertion to `hardware_confirmed`. The source
profile is never overwritten, and device/OS/resource mismatches are blocked.

Hardware-test schema v1 describes one short, hash-pinned SMF fixture, the exact
Pa800 OS/resources and device state, structured expected assertions, and two
import--export--device cycles. Each completed cycle requires a tester, ISO test
date, output MIDI hash, non-empty log and an observation for every assertion;
it may also reference a control audio recording. A case becomes `passed` only
when both cycles pass. `hardware validate` resolves the fixture relative to its
manifest, verifies its SHA-256, parses and validates the SMF, and reports the
canonical manifest hash and blockers without treating a software preflight as
a hardware confirmation.

`hardware generate` creates a deterministic format-0 sound or drum probe at
384 PPQ. The fixture contains one 4/4 initialization bar followed by one test
note, while its generated manifest remains pending and explicitly marks the
address/name pair as a hypothesis. Existing files are not overwritten unless
`--overwrite` is supplied.

`hardware record-cycle` records one completed device cycle into a new manifest.
It hashes, parses and validates the actual output MIDI, requires an observation
for every assertion and keeps cycle ordering. Cycle 2 cannot be recorded before
cycle 1. The input manifest is never overwritten; a case becomes `passed` only
after both recorded cycles and all observations pass.

The local database uses Python's built-in SQLite support, so it adds no package
dependency. Schema v1 stores application metadata and empty catalogs prepared
for validated device profiles and two-cycle hardware-test records. Repeating
`database init` is safe and does not delete existing catalog rows.
`database import-profile` and `database import-hardware` run the strict JSON
loaders before storing canonical JSON and its SHA-256 digest. Reimporting
identical content returns `unchanged`; changed content with the same identity
and version updates one catalog row rather than creating a duplicate.

Auto-policy schema v1 records the automation mode (`analyze_only`, `safe_auto`,
`assisted` or `verified_batch`), package, deterministic seed, goals, numeric
error budgets, locks, module thresholds and an optional exact device-profile
identity/hash. The policy evaluator classifies every proposal as read-only,
automatic, review-required or blocked. Safe automation is limited to enabled
low-risk proposals inside the confidence boundary. Verified batch mode may
apply a higher-risk proposal only when its complete transaction SHA-256 is an
exact match for a previously approved fingerprint; any changed event, value or
precondition invalidates that approval.

The proposal adapter layer now converts initialization updates, controller
thinning, CC7/CC11 conversion, sound mapping and per-note drum mapping into one
deterministic `ProposalRegistry`. Every entry retains finding identifiers,
evidence references, transaction fingerprint, affected tracks/channels, drum
notes and normalized message kinds. Policy locks therefore block changes by
event, track, channel, drum note or message kind before simulation or mutation.
Blocked analyzer plans remain visible as blocked proposals instead of silently
disappearing from the combined plan.

`ProposalSimulator` applies the policy-selected subset only to a cloned song
and records one checkpoint before the first transaction. It verifies selected
dependencies, rebases each already-fingerprinted transaction onto the current
projected revision, reruns summary, validation, controller, NRPN/RPN, SysEx and
initialization analysis, and emits deterministic before/after hashes plus
numeric deltas for events, notes, controllers, programs, SysEx, polyphony,
duration and blockers. Any failed transaction or newly introduced export
blocker rolls the complete simulation back to the original snapshot.

The unified `auto` command generates controller-thinning and CC7/CC11
proposals automatically and can additionally accept initialization, sound and
drum mapping requests. Preview mode writes the complete report without changing
the MIDI. `--approve PROPOSAL_ID` or `--interactive` authorizes review-required
groups; `--apply` additionally requires a new output path. Before commit the
input and proposal-plan revisions are checked again. A successful commit writes
the validated MIDI, its normal export report, a rotating project autosave with
undo history, and a canonical auto report containing policy/profile hashes,
all decisions, proposal fingerprints, numerical A/B data and output SHA-256.

The read-only program resolver follows persistent CC0/CC32 state per MIDI
channel and resolves each Program Change against one selected profile. It
reports implicit bank defaults, unknown addresses, cross-track bank sequences,
profile/target OS or resource mismatches, and evidence below a requested
minimum status. It never rewrites a bank or program.

The read-only initialization-bar analyzer measures the first bar from the
meter map, locates the first Note On, classifies recognized reset/bank/program/
mix events, and checks the expected per-channel order. Unknown SysEx,
cross-track initialization, backward ordering and a musical start away from
the exact second-bar boundary remain explicit warnings or blockers. Detection
never adds, moves or removes an event.

`init-update` builds a high-risk preview against a probable existing
initialization bar. It can update only existing Program Change and approved
CC0/32/7/10/11/91/93 values; missing, duplicate, ambiguous or stale targets
are blocked. Application requires `--apply` and a new output path and remains
one atomic, undoable transaction per channel.

`sound-map` builds a high-risk preview for one existing Program Change and a
profile voice. By default the target identity must be hardware-confirmed. The
first implementation updates only an explicit, same-track CC0/CC32/Program
Change group and blocks implicit banks, channel/voice-kind mismatches and bank
events shared by multiple selections. Application requires `--apply`, writes a
new file and remains one atomic, undoable transaction.

`drum-map` combines a channel-10 Drum Kit address update with per-note mapping
inside that Program Change interval. Every matched Note On and its exact Note
Off are changed together. Ambiguous/unmatched pairs, notes crossing the next
kit change, an already-used target note and unconfirmed kit/note identities are
blocked. The complete kit-and-note edit is one explicitly approved, undoable
high-risk transaction.

## Tests

```text
python -m unittest discover -v
```
