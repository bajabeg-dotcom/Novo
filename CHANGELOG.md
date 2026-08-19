# 0.28.0 (u toku) - Consolidation

Faza A i pocetak faze B iz PLAN_REVIZIJE.md.

## Dodano
- `src/` layout i editable instalacija; paket se ucitava iz bilo kojeg cwd.
- `tests/`: 155 testova pisanih za v0.27.0 API (SMF round-trip, export
  garancije, CLI ugovor, forenzicke invarijante, ugovor o ocuvanju).
- `legacy/`: arhiva 5 prethodnih repozitorija, 4.685 fajlova + MANIFEST.md
  sa SHA-256 svakog izuzetog velikog fajla.
- `evidence/`: K01 Pa800 Factory registar (1.071 adresa) i Oscilatori.txt.
- `tools/forensics/`: nezavisni SMF parser i forenzicki alati za korpus i bazu.
- `FORENZIKA.md`, `PLAN_REVIZIJE.md`, `ANALIZA_I_REVIZIJA.md`.
- `ci/ci.yml`: matrica Python 3.11-3.13 x Ubuntu/Windows.
- `tests/regression/test_preservation_contract.py`: 20 testova koji trajno
  zakljucavaju ocuvanje trackova, nota, lyricsa, pitch benda i sustaina.
  Ukljucuje reprodukciju incidenta "Nevera moja" (16/8.340 -> 7/4.492).
- `tests/regression/test_rx_trigger_zones.py`: 15 testova RX trigger zona;
  fiksira granicu na "od 96 (C7) ukljucivo".
- `NEDOVRSENO.md`: radni spisak nedovrsenog sa statusom svake stavke.
- `profiles/rx.py`: RX oscillator profile schema, 12 profila iz
  `evidence/oscilatori/Oscilatori.txt` (Finger/Picked/SlapFing/SlapPick Bass RX,
  Clean Guitar RX1-RX6, Dist Guitar RX1/RX2, Power Chords). Svaki nosi
  velocity/key zone, switch pragove, evidence status i izvor.
- `optimize/rx_guard.py`: velocity izmjene se provjeravaju protiv
  oscilatorskih zona. Apsolutni okidaci (C7-G9) se ne diraju; izmjena koja bi
  promijenila artikulaciju se skrati na granicu zone ili odbaci; profil ispod
  `documented` ne moze odobriti automatsku izmjenu.
- `optimize/leveling.py`: konzervativni CC7 output leveling za originalne
  trackove. Cetiri zastite: namjerno tihi layer se ne dize, bass/kick masking,
  anti-clipping budzet i ogranicenje pomaka (light/balanced/strong). Velocity
  se nikada ne dira.
- Ruff lint konfiguracija: strogo na novom kodu, postupno na naslijedjenom.
  `ruff check .` prolazi bez greske.
- CI dobija tri nova joba: lint, coverage prag (70 % na kriticnim modulima,
  trenutno 81 %) i zaseban job za regresijski ugovor o ocuvanju.

## Popravljeno
- CLI vise ne izbacuje Python traceback na ocekivane greske (nepostojeca
  datoteka, neispravan SMF). Sada kratka poruka i izlazni kod 2.
  `PA800_ENHANCER_TRACEBACK=1` vraca puni traceback za debugiranje.
- Dokumentacija: guitar RX noise zona je "od 96 (C7)", ne "iznad 96".

## Promijenjeno
- `VelocityRangeModule` prima `rx_profile` i postuje oscilatorske zone.
  Bez profila ponasanje je nepromijenjeno.
- `optimize_conservatively` prima `drum_kit`; podrazumijevani kit se ucitava
  iz `config/performance-defaults.json` uz provjeru dokaza. Svako mapiranje
  nosi `evidence_status` i `evidence_source`, a svaki preskoceni kanal nosi
  `reason`.
- Ispravka praga: SlapFing/SlapPick Bass RX radni oscilator prelazi na 87,
  ne 94. Ceka PCG/Sound Edit potvrdu na uredjaju.

## Popravljene rupe
- **N1**: drum adresa 120.0.4 vise nije hardkodirana. Dolazi iz konfiguracije
  i odbija se ako je status ispod `documented` ili ako nema navedenog izvora.
- **N2**: konzervativni i velocity optimizer sada citaju RX oscillator profile.

# Changelog

## 0.14.0 - 2026-08-19

- Added beat-synchronous harmony evidence and bass-aware chord inference.
- Added duration-weighted key posteriors and modulation windows.
- Added confidence-gated unknown chords and adjacent-segment smoothing.
- Added idempotent schema-5 harmony persistence and the `harmony` CLI command.

## 0.13.0 - 2026-08-19

- Added cwd-independent resource resolution and Windows user-data fallback.
- Added versioned SHA-256 artifact manifests and CLI integrity auditing.
- Added schema-5 music evidence tables for songs, sections, tracks, chords,
  Factory style elements, annotations and leakage-safe dataset groups.
- Marked the existing GRU model as experimental in the artifact manifest.

## 0.12.0 - 2026-08-19

- Added Factory Var1–Var4 section growth to generated arrangements.
- Added pop, ballad, dance, folk and rock CPU generation presets.
- Added preset tempo, density, swing and drum-fill strength controls.
- Added GUI style selection and regression coverage for density differences.

## 0.11.0 - 2026-08-19

- Added bar-synchronized song form for every generated role.
- Added section dynamics and phrase-ending Factory-style drum fills.
- Made `--notes` a predictable density control by stretching material across the form.
- Aligned all track and metadata End-of-Track events to the requested bar length.

## 0.10.0 - 2026-08-19

- Migrated DNA storage to schema 4 with 2,899 separate bass references.
- Added five-role harmonic arrangement and selectable major/minor tonal center.
- Added I–V–vi–IV bass movement and Factory-style root/fifth/octave power chords.
- Added voice-safe same-pitch retrigger rendering with clean MIDI validation.

## 0.9.0 - 2026-08-19

- Added CPU-only PyTorch role-conditioned MIDI generator.
- Added Gold-weighted nested-ZIP training, checkpoint/resume and deterministic sampling.
- Added solo, accompaniment, drums and guitar generation with Factory safety ranges.
- Added validated CLI generation and GUI Generate–Optimize–Export workflow.

## 0.8.0 - 2026-08-19

- Added schema-v3 SQLite DNA evidence storage with every Gold/Factory source alias.
- Added separate solo, accompaniment, drums and guitar/power-chord fingerprints.
- Added confidence-gated Gold matching and natural velocity/articulation correction.
- Integrated DNA evidence into the GUI Import–Optimize–Export workflow.
- Added `dna-learn`, `dna-audit` and `dna-optimize` automation commands.
- Added optional SciPy, scikit-learn and music21 DNA dependencies.
- Declared a CPU PyTorch generator dependency group as the foundation for
  role-conditioned MIDI generation.

## 0.7.0 - 2026-08-19

- Added a Factory-evidenced performance strategy with Pop Std. Kit RX as the
  default drum kit address and Factory Power Chords as a dedicated guitar
  mode.
- Added groove-level drum-element, fill/break and guitar-role policies.
- Simplified the primary desktop workflow to Import, Optimize and Export.
- Added background GUI performance optimization, preview, blocker reporting
  and sequential undoable application.

## 0.6.0 - 2026-08-19

- Added safe directory-wide performance preview and apply automation.
- Added per-file continuation, ready/exported/blocked/failed/skipped states,
  hashes, timing, change counts and unmatched-address reporting.
- Preserved relative input directory structure in a separate output tree.
- Added overwrite protection and rejected output directories nested beneath
  the input tree to prevent recursive self-processing.

## 0.5.0 - 2026-08-19

- Added one-command performance projection combining minimum-duration repair,
  catalog-backed velocity and a second-pass articulation analysis.
- Added atomic JSON performance reports with source/intermediate/final model
  revisions, segment evidence, validation counts and export blockers.
- Fixed semantic event ordering after timing changes for every transactional
  module.
- Added safe one-tick repair for unambiguous zero-duration notes, including
  End-of-Track extension when required.

## 0.4.0 - 2026-08-19

- Added catalog-backed automatic articulation analysis and reversible apply.
- Added conservative grace-note, trill, repeated-note/tremolo, staccato and
  monophonic legato classification.
- Added instrument-specific articulation attack profiles for all supported
  instrument families.
- Protected polyphonic chord transitions, unknown addresses and notes outside
  learned Factory key ranges from timing changes.

## 0.3.0 - 2026-08-19

- Added Gold/Factory reference learning keyed by CC0/CC32/Program/channel.
- Added automatic instrument-segment resolution and catalog-backed velocity
  shaping without using the target song's original velocity as the baseline.
- Added instrument families for piano, mallet, organ, guitar, bass, strings,
  choir, brass, woodwind, lead, pad, ethnic instruments, percussion, drums and
  effects.
- Added conservative monophonic trill detection and protected key ranges.
- Generated 1,227 learned profiles from 3,393 local Gold/Factory references.

## 0.2.0 - 2026-08-19

- Added bounded corpus analysis for MIDI files, directories, ZIP archives and
  nested ZIP archives, with an atomic schema-versioned JSON report.
- Added cross-platform rejection of absolute, drive-relative, UNC and
  parent-traversing hardware fixture paths.
- Added Windows/Linux CI for Python 3.11-3.13 and a reproducible package build
  job.
- Established a baseline over 3,556 reference MIDI files: every file parses
  without an uncontrolled failure.

## 0.1.0

- Initial dependency-free Pa800 MIDI inspection, transactional optimization,
  project recovery, profile evidence and hardware verification foundation.
# 0.26.0

- Added evidence-gated Gold velocity and articulation transfer on top of Factory timing.
- Added exact Factory style selection and schema-2 performance reference artifact.
- Integrated Gold transfer into gated Factory preview export with auditable evidence.
# 0.26.1

- Added density-aware role mixer automation; sparse bass receives CC7/CC11
  headroom while drums, percussion, guitars and accompaniment remain balanced.
# 0.26.2

- Added MIDI output leveling from per-role median velocity and arrangement density.
- Added section-aware CC11 automation while preserving Gold note dynamics.
# 0.26.3

- Connected GUI Optimize to the complete Factory arrangement, Gold performance
  transfer, musical gate, MIDI validation and adaptive mastering workflow.
- Added exact Factory style prompt and an auditable GUI mixer summary.
# 0.26.4

- Added automatic Factory style selection from MIDI meter, melodic/drum density,
  off-16th groove, channel coverage and an optional genre token in the filename.
- Gold references remain the performance-DNA layer after Factory style selection.
# 0.27.0

- Made conservative track-preserving optimization the default GUI Optimize path.
- Factory evidence now maps GM sounds to Pa800 banks without replacing notes,
  timing, lyrics, pitch bends or track structure.
- Duplicate instrument layers rotate through distinct evidence-ranked Factory
  variants; initialization bank selects are ordered before program changes.
- Full Factory re-arrangement is no longer invoked by standard GUI Optimize.
