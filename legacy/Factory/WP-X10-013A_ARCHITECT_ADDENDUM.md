# WP-X10-013A — Architect Addendum

Datum: 12. august 2026.  
Verzija: 2  
Capability: `ANALYZE_ONLY`  
Naziv: Immutable Withheld-only Proposal Assessment Foundation  
Status: `ARCHITECT_READY`

## Svrha i zamjena prethodnog scopea

Ovaj dodatak zatvara blokere iz `WP-X10-013A_AUDIT.md` i zamjenjuje sve dijelove prvog Architect briefa koji su dozvoljavali exact target ili shadow change simulation.

WP-X10-013A smije samo:

- materijalizovati immutable candidate-assessment zapis za postojeći schema-v2 stable subject;
- objasniti zašto anomaly/target nije dokaziv;
- zaključati input, provenance i dependency digeste;
- proizvesti no-change simulation zapis koji dokazuje identitet prije/poslije;
- validirati da nije nastala nikakva semantička ili byte promjena.

Obavezni rezultat je:

```text
WITHHELD_ONLY
TARGET = ABSENT
CHANGE = NONE
MIDI_OUTPUT = NONE
```

## Revidirani scope

1. Odvojeni 013A analyze-only schema/API; WP-012A/B/C/D ostaju read-only.
2. Candidate assessment predstavlja spremnost stable subjecta za neki budući proposal ugovor. Nije actionable proposal.
3. Closed eligibility, anomaly-not-proven i withheld reason klasifikacija izvedena samo iz već prihvaćenih schema-v2 činjenica i eksplicitno nedostajućih zavisnosti.
4. Frozen input manifest sa source/schema/config/lineage/subject/protection/model/reference digestima.
5. No-change simulation koja postavlja `changed_event_count=0`, `changed_field_count=0`, ne konstruiše overlay i dokazuje identične before/after digeste.
6. Deterministički full-rebuild, canonical serialization, SQLite integrity/FK i atomic replace.

## Stroge zabrane

013A nema:

- target phase, target tick, derived tick, delta ili candidate value;
- non-NULL ili sentinel target polje;
- shadow event graph, target overlay ili hipotetičku promjenu;
- anomaly-positive status;
- `SIMULATION_VALIDATED` za promjenu;
- USER_INPUT source klasu ili pretpostavku da corpus note predstavlja korisnički MIDI;
- calibration minimum/maximum delta, cost, score, improvement ili budget metriku;
- local-pattern target, leave-one-target-out zaključak ili reinterpretaciju `LOCAL_REPEATED_PATTERN` protectiona;
- MIDI parse→write, encode, export, output ili mutation putanju;
- update prihvaćenog assessmenta, apply, commit, repair ili rollback promjene.

Schema i javni payload ne smiju sadržati ključeve/kolone:

```text
target_phase
target_tick
derived_tick
delta_ticks
candidate_value
shadow_tick
repair_budget
modification_cost
improvement_score
```

## Source i authority ugovor

013A analizira samo snapshot zapise koji već postoje u QA-prihvaćenom schema-v2 buildu. Oni se označavaju kao:

```text
CORPUS_READINESS_ASSESSMENT
```

To nije `USER_INPUT` i nije repair session. Factory corpus ostaje model/evidence autoritet unutar postojećih pravila; Gold/reference ostaje support/conflict; nijedan assessment zapis ne postaje evidence.

Šest Delay/Terca pjesama, optimizer output i repaired output ostaju zabranjeni preko postojećeg trusted-lineage gatea. 013A mora ponovo verifikovati source/root/class/ancestor digeste prije materijalizacije.

## Lifecycle ugovor

Candidate, simulation, validation i build lifecycle su odvojeni i immutable.

### `assessment_runs`

Jedan red po uspješnom atomic buildu:

- run ID i contract/schema/config version;
- frozen input/schema-v2 semantic digest;
- source/subject count;
- terminal status `COMPLETED_WITHHELD_ONLY`;
- capability `ANALYZE_ONLY`, mutation `NONE`;
- run semantic digest.

Failed build ne zamjenjuje prethodnu bazu i ne ostavlja semantic red u accepted targetu. Vraća canonical failure report izvan accepted baze.

### `input_snapshots`

Immutable source-level manifest:

- source SHA/class/kind/member path;
- trusted lineage i source manifest digest;
- schema-v2/build/config/protection/model/reference digesti;
- stable subject/edge universe digest;
- before byte SHA i before semantic digest.

### `candidate_assessments`

Jedan immutable natural key:

```text
[
  assessment_contract_version,
  input_snapshot_id,
  stable_subject_id,
  schema_v2_authorization_id
]
```

Obavezna polja su subject type/ID, source/context/event-slot veze gdje postoje, eligibility status, anomaly status, withheld reason set, exact provenance locatori i dependency digest. Target/change polja ne postoje.

### `no_change_simulations`

Poseban immutable red sa FK na assessment:

- simulation status `NO_CHANGE_IDENTITY_PROVEN`;
- before/after byte SHA jednaki;
- before/after semantic digest jednaki;
- before/after subject-universe digest jednaki;
- `changed_event_count=0`;
- `changed_field_count=0`;
- `output_artifact_status=NOT_CREATED`;
- simulation digest.

### `identity_validations`

Poseban immutable red sa FK na no-change simulation:

- validation status `IDENTITY_VALIDATED`;
- byte parity, semantic parity, subject/FK parity i no-output guard rezultati;
- validator registry/config digest;
- validation digest.

Nijedan lifecycle red se ne ažurira u drugi status. Novi run dobija novi run ID; natural-key kontradikcija je hard fail.

## Zatvoreni statusi i reason domeni

### Eligibility

```text
INELIGIBLE_INVALID_SOURCE
INELIGIBLE_SOURCE_QUALITY
INELIGIBLE_CONTEXT_UNPROVEN
INELIGIBLE_PROTECTION
INELIGIBLE_FACTORY_EVIDENCE
INELIGIBLE_MODALITY
INELIGIBLE_REFERENCE_CONFLICT
READINESS_INPUT_ANALYZE_ALLOWED
```

Posljednji status znači samo da je 012D analiza dozvoljena; ne znači anomaly ili target readiness.

### Anomaly status

```text
ANOMALY_NOT_EVALUATED_INELIGIBLE
ANOMALY_NOT_PROVEN_CONTRACT_UNAVAILABLE
```

013A nema `ANOMALY_PROVEN`.

### Withheld reasons

Najmanje jedan razlog je obavezan za svaki assessment:

```text
SOURCE_NOT_USER_INPUT
SCHEMA_V2_AUTHORIZATION_NOT_ALLOWED
PROTECTION_OR_MUSICAL_INTENT_PRESERVED
FACTORY_EVIDENCE_INSUFFICIENT_OR_UNSTABLE
REFERENCE_CONFLICT_OR_DEFERRED
CALIBRATION_ENVELOPE_UNAVAILABLE
LOCAL_COMPARISON_MODEL_UNAVAILABLE
ANOMALY_PROOF_CONTRACT_UNAVAILABLE
EXACT_TARGET_CONTRACT_UNAVAILABLE
CHANGE_SIMULATION_CONTRACT_UNAVAILABLE
```

Razlozi se mogu kombinovati. Unknown enum, prazan reason set ili status/reason nedosljednost je hard fail.

## Assessment mapping ugovor

013A ne izračunava novu muzičku anomaliju. Deterministički mapira postojeći 012D final authorization i dependency availability:

- svaki 012D preserve/review/excluded status prelazi u odgovarajući `INELIGIBLE_*` status;
- `ANALYZE_ALLOWED` prelazi samo u `READINESS_INPUT_ANALYZE_ALLOWED`;
- anomaly status je uvijek jedan od dva negative/unevaluated statusa;
- `SOURCE_NOT_USER_INPUT`, calibration, local comparison, anomaly-proof, exact-target i change-simulation dependency razlozi ostaju eksplicitni;
- nijedan mapping ne slabi protection niti mijenja 012D truth table.

Time je zatvorena kontradikcija `LOCAL_REPEATED_PATTERN`: detected repeat ostaje protection/preserve. 013A ga ne koristi kao target dokaz i ne pokušava pozitivan reachability put.

## No-change simulation i identity validation

No-change simulation nije shadow change. Ona dokazuje da assessment pipeline nema mutacijski efekat:

```text
frozen whole-source manifest
→ assessment only
→ same frozen whole-source manifest
```

Obavezno:

- before/after SHA i semantic digest se računaju nezavisno;
- subject/edge universe i sve schema-v2 semantic tabele ostaju identične;
- nema promijenjenog eventa ili polja;
- nema output MIDI patha, bytesa ili artefakta;
- nema importa/poziva MIDI writer/encoder/export funkcije;
- input i sve evidence/model baze se otvaraju read-only gdje platforma dopušta;
- mismatch abortuje cijeli build.

No-change simulation ne smije koristiti pojmove `improved`, `worse`, `distance`, `cost` ili `budget`.

## Append-only i atomic storage ugovor

- Schema koristi samo insert tokom temp full-builda; produkcijski API nema update/delete metodu.
- FK smjer je `run → input snapshot → assessment → no-change simulation → identity validation`.
- Svaki child pripada istom runu i source snapshotu kao parent.
- Canonical digest pokriva sve semantic tabele, closed enum/config hash i FK prirodne ključeve.
- Build se vrši u temp SQLite fajlu; tek nakon integrity, FK, digest i identity validation prolaza radi se atomic replace.
- Greška briše temp fajl i čuva prethodni accepted output byte-identično.
- Timestamp, apsolutni path i izmjerene performance metrike nisu dio semantic identiteta.

## Fail-closed ugovor

Hard fail:

- source/lineage/schema/config/digest mismatch;
- forbidden source ili cross-authority ancestry;
- unknown/duplicate/unreachable enum;
- broken stable subject/edge/FK;
- natural-key kontradikcija;
- prazan withheld reason set;
- bilo koje target/delta/shadow/cost/budget polje;
- input/schema/model mutation;
- writer/encoder/export poziv ili output artefakt;
- before/after identity mismatch;
- nondeterministički row order/digest;
- partial target replace.

Normalan rezultat, ne greška:

- ineligible subject;
- `ANALYZE_ALLOWED` subject koji je i dalje withheld zbog nedostajućih narednih ugovora;
- odsutna kalibracija/local comparison/user-input/change simulation sposobnost.

## Acceptance kriteriji

WP-X10-013A može dobiti tehnički `ACCEPT` samo ako:

1. capability je svuda `ANALYZE_ONLY`, mutation `NONE`;
2. WP-012A/B/C/D fajlovi, schema, authorization i digesti ostaju nepromijenjeni;
3. schema/API nema target phase/tick/delta, shadow value, cost, budget ili improvement polja;
4. nema USER_INPUT klase niti corpus-as-user-input predstavljanja;
5. svaki stable assessment ima immutable snapshot, stable subject, 012D authorization provenance i najmanje jedan withheld reason;
6. `ANALYZE_ALLOWED` nikad ne proizvodi anomaly-positive ili target-ready status;
7. candidate assessment, no-change simulation, identity validation i run statusi/tabele su odvojeni;
8. no-change simulation dokazuje `changed_event_count=0`, `changed_field_count=0`, jednake byte/semantic/subject digeste i `NOT_CREATED` output;
9. nema MIDI writer/encoder/export importa ili poziva u 013A runtime putu;
10. source/lineage/forbidden guards ponovo prolaze za svaki snapshot;
11. full-build je disk-backed, canonical, deterministic i atomic;
12. dva builda i sve dozvoljene input-order permutacije daju isti semantic digest;
13. failure čuva prethodnu bazu byte-identično i ne ostavlja accepted partial audit red;
14. SQL CHECK/FK/integrity, enum reachability i natural-key contradiction testovi prolaze;
15. adversarial testovi odbijaju forged digest, target key injection, empty reason set, lifecycle overwrite, update/delete, mutation i output artefakt;
16. targeted i puni pytest prolaze sa warning-as-error;
17. nezavisni QA vraća `ACCEPT`, `RETURN` ili `BLOCK`, a `ACCEPT` nema otvoren critical/high nalaz.

Dozvoljena acceptance oznaka je samo:

```text
013A_WITHHELD_FOUNDATION_ACCEPTED
```

Ne koriste se `TARGET_PROOF_ACCEPTED` ili `SIMULATION_ACCEPTED` za change simulation.

## Odgođeni paketi i eksplicitni prerequisites

Exact target i change simulation ostaju zabranjeni dok zasebni Architect/Audit/Lead/QA paketi ne prihvate:

1. immutable `USER_INPUT` snapshot, lineage i authority separation;
2. schema-v2 calibration envelope sa exact context/event-slot provenanceom;
3. leave-one-target-out local comparison model bez circular selection biasa;
4. novi read-only distinction između protection repeat membershipa i comparison evidencea;
5. exact anomaly proof i exact-target relationship;
6. mathematical metric registry sa rational/Decimal interval semantikom;
7. whole-source overlay/parity i crossed-interval closure;
8. tek zatim non-mutating change simulation;
9. kasnije multi-candidate ranking/budget, preview/dry-run i manual commit/rollback.

Nijedan prerequisite nije implicitno odobren ovim addendumom.

## Human Owner odluke

Human Owner ne mora donositi novu Pa800 odluku za withheld-only 013A. Human odobrenje će biti potrebno prije actionable proposal capabilityja, manual apply/commit, auto-repaira, certificationa i releasea.

## Architect verdict

```text
ARCHITECT_READY
```