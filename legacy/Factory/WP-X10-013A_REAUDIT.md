# WP-X10-013A — Re-audit suženog Withheld-only ugovora

Datum: 12. august 2026.  
Predmet: `WP-X10-013A_ARCHITECT_ADDENDUM.md`  
Capability: `ANALYZE_ONLY / mutation NONE`

## SCOPE_REVIEW

Architect addendum normativno zamjenjuje sve dijelove prvog 013A briefa koji su dopuštali exact target, anomaly-positive odluku ili shadow change simulation. Novi paket je ograničen na readiness assessment postojećih QA-prihvaćenih schema-v2 corpus zapisa.

Jedini dozvoljeni rezultat je:

```text
WITHHELD_ONLY
TARGET = ABSENT
CHANGE = NONE
MIDI_OUTPUT = NONE
```

Ova granica je kompatibilna sa X10 ugovorima i prihvaćenim WP-012A/B/C/D slojevima.

## PREVIOUS_BLOCKER_RESOLUTION

### B1/C2 — Lifecycle kontradikcija: RESOLVED

Candidate assessment, no-change simulation, identity validation i build run sada su odvojeni immutable redovi sa jednosmjernim FK lancem. Nema statusnog prelaska iz targeta u simulation, nema updatea accepted assessmenta i nema target provenancea koji bi nestao pri promjeni statusa.

### B2/C1 — Local repeat naspram `ANALYZE_ALLOWED`: RESOLVED

013A više ne koristi `LOCAL_REPEATED_PATTERN` kao target dokaz i ne mijenja WP-012B protection semantiku. Detected repeat ostaje preserve/protection rezultat. `ANALYZE_ALLOWED` se mapira samo u `READINESS_INPUT_ANALYZE_ALLOWED`, koji je i dalje withheld.

### B3/C3 — USER_INPUT authority: RESOLVED

Paket izričito analizira samo postojeće schema-v2 corpus snapshot zapise kao `CORPUS_READINESS_ASSESSMENT`. Ne uvodi `USER_INPUT` i ne predstavlja Factory corpus note kao korisnički MIDI. Budući user-input contract je pravilno odgođen u novi paket.

### B4/G1/G2 — Calibration i local target proof: RESOLVED BY PROHIBITION

Calibration envelope, minimum/maximum delta, leave-one-target-out comparison i exact target contract nisu dependency ovog suženog paketa. Njihovo odsustvo se eksplicitno evidentira kao withheld reason. Schema/API ne smiju imati target, tick, delta ili candidate value polja.

### B5/G4/G5 — Change validation metrike i shadow closure: RESOLVED BY PROHIBITION

Nema change simulation, overlay grafa, improvement/distance/cost/budget metrike ni lokalnog target closurea. Simulation je isključivo identity proof sa nula promijenjenih eventa i polja. Whole-input byte/semantic/subject digesti moraju ostati jednaki.

### G6 — Storage lifecycle i atomicity: RESOLVED

Addendum zaključava append-only temp full-build, odvojene lifecycle tabele, canonical digest, integrity/FK provjeru, atomic replace i byte-identično očuvanje prethodne accepted baze pri grešci.

## REMAINING_IMPLEMENTATION_LOCKS

Sljedeće nisu arhitektonski blockeri, ali Lead plan i testovi ih moraju eksplicitno zaključati.

### L1 — Assessment universe mora biti potpun i dokaziv

Assessment universe treba definisati kao tačno sve redove iz QA-prihvaćene schema-v2 `analysis_authorization` tabele, ne proizvoljan podskup svih `stable_subjects`.

Za svaki assessment mora važiti:

- subject type je `NOTE`;
- source, note subject i event slot odgovaraju istom authorization redu;
- nema missing ili extra assessmenta;
- per-source i total count se reconciliiraju sa frozen schema-v2 snapshotom.

Non-NOTE stable subject nema 012D authorization i ne smije dobiti fabricirani readiness assessment.

### L2 — `schema_v2_authorization_id` je locator, ne postojeći DB ID

WP-012D nema posebnu authorization ID kolonu; natural key je composite `(source_sha256, note_subject_id, event_slot_key)`. Implementacija ne smije izmišljati ili upisivati novi ID u schema-v2.

013A treba koristiti canonical external locator izveden iz:

```text
[
  source_sha256,
  note_subject_id,
  event_slot_key,
  authorization_row_semantic_digest
]
```

uz recomputed schema-v2 semantic digest. Locator i authorization row digest ulaze u assessment natural key/provenance.

### L3 — Exhaustive authorization mapping

Lead mora zapisati totalnu tabelu za svih 012D closed authorization statusa prema:

- jednom 013A eligibility statusu;
- dozvoljenom anomaly-negative statusu;
- obaveznom minimalnom withheld reason setu.

Posebno treba odvojiti reference conflict od reference partial/deferred/uninformative slučaja kroz reason set, čak i ako dijele širi eligibility bucket. Unknown ili unmapped status hard-failuje.

### L4 — Identity digest scope

Before/after provjera mora recomputeovati, a ne samo prepisati stored digest. Versioned validator registry mora definisati najmanje:

- RAW/source byte SHA gdje su source bytes dostupni frozen buildu;
- schema-v2 whole-file byte SHA;
- recomputed schema-v2 semantic digest svih semantic tabela;
- stable subject + edge universe digest;
- source manifest i trusted-lineage digest;
- 013A zabranu output artefakta.

Jednakost dva polja koja su oba kopirana iz istog input reda nije identity proof.

### L5 — Semantic forbidden-key guard

Zabrana target/change polja mora važiti za SQL schema, canonical JSON payload, public API i nested metadata, ne samo za nazive Python atributa. Test mora ubaciti zabranjeni ključ u ugniježđeni payload i očekivati hard fail.

### L6 — Read-only i mutation guard

Schema-v2 i evidence/model baze treba otvoriti SQLite read-only URI režimom gdje je podržano. Test mora potvrditi:

- hash prije/poslije;
- write pokušaj odbijen;
- 013A runtime nema import/poziv MIDI writer/encoder/export putanje;
- nema `.mid`/`.midi` ili drugog output artefakta;
- failure briše temp 013A bazu i ne mijenja prethodni target.

## RISKS_REVIEW

Prethodni false-repair rizici više nisu aktivni u 013A jer paket nema target, promjenu, score ili repair permission. Glavni preostali rizik je lažno predstavljanje readiness assessmenta kao proposal readinessa. To je zatvoreno ako UI/API/report dosljedno koriste `CORPUS_READINESS_ASSESSMENT`, `WITHHELD_ONLY` i `013A_WITHHELD_FOUNDATION_ACCEPTED`, bez riječi koje impliciraju actionable target.

Assessment zapisi ne smiju postati Factory/Gold evidence, training input niti osnova za kasniji silent promotion. Budući paket mora ponovo zaključati snapshot i dokazati sve odgođene prerequisites.

## ACCEPTANCE_GATE

Implementacija može ići u Lead/Implementer samo pod sljedećim zaključavanjem:

1. Addendum v2 ima precedencu nad konfliktnim exact-target/change dijelovima Architect v1.
2. WP-012A/B/C/D fajlovi i digesti ostaju read-only.
3. Assessment universe i authorization locator slijede L1–L2.
4. Mapping je totalan i versioned prema L3.
5. Identity validacija stvarno recomputeuje pune digeste prema L4.
6. Forbidden-key, read-only, no-output, determinism, atomic rollback i exhaustive enum testovi slijede L5–L6.
7. Svaki red ostaje withheld sa najmanje jednim razlogom; `ANALYZE_ALLOWED` nikad ne postaje anomaly-positive, target-ready ili simulation-of-change status.
8. Jedina tehnička acceptance oznaka je `013A_WITHHELD_FOUNDATION_ACCEPTED`.

## REAUDIT_VERDICT

Architect addendum je uklonio sve ranije blockere tako što je paket sveo na immutable, deterministički i provenance-bound withheld-only readiness sloj. Ne izmišlja user input, kalibraciju, anomaly proof, target ili promjenu i ne reinterpretira accepted protection/authorization ugovore.

Uz obavezne Lead/QA implementacione lockove L1–L6, paket je spreman za tehničku podjelu i implementaciju. Ovaj verdict ne odobrava exact target, change simulation, proposal, MIDI output, apply, repair niti release.

```text
AUDIT_REVIEWED
```