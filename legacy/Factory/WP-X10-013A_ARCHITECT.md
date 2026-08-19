# WP-X10-013A — Architect Work-Package Contract

Datum: 12. august 2026.  
Verzija: 1  
Capability: `ANALYZE_ONLY`  
Naziv: Evidence-bound Candidate and Non-mutating Simulation Foundation  
Status: `ARCHITECT_READY`

## ARCHITECT_BRIEF

WP-X10-013A uvodi odvojeni, deterministički temelj za predstavljanje timing hipoteze i provjeru njenog efekta u nemutirajućem shadow modelu. Paket ne popravlja MIDI, ne zapisuje novi MIDI, ne daje korisničko `Apply`, ne rangira više popravki i ne proširuje capability iznad `ANALYZE_ONLY`.

Osnovni sigurnosni princip je:

```text
NO PROVEN TARGET
→ TARGET_WITHHELD
→ NO SIMULATION OF CHANGE
→ PRESERVE
```

`ANALYZE_ALLOWED` iz schema-v2 je samo ulazna dozvola za dalje dokazivanje. Nije dokaz anomalije, nije target i nije repair dozvola.

Paket smije proizvesti:

- immutable candidate hypothesis vezanu za stable subject;
- eksplicitni anomaly/target proof status;
- tačan racionalni target i tick samo kada puni ugovor dokaza prolazi;
- nemutirajući before/after semantic shadow rezultat;
- validation i rejection razloge;
- audit/provenance zapis.

## SCOPE

1. Odvojeni schema/API sloj za candidate hypothesis i simulation rezultat; prihvaćeni schema-v2 ostaje read-only i ne mijenja značenje.
2. Stable-ID kandidat samo za atomsku translaciju jednog postojećeg `NOTE` subjekta u vremenu.
3. Promjena, kada je dokaziva, pomjera Note On i njegov povezani Note Off za isti cijeli broj tickova; pitch, channel, track, velocity i duration ostaju identični.
4. Event-level anomaly proof koji odvojeno dokazuje:
   - da je original izvan dozvoljenog Factory ponašanja;
   - da odstupanje nije zaštitna/muzička namjera;
   - da postoji jedinstven dokaziv target.
5. `TARGET_WITHHELD` kao normalan i očekivan rezultat za nedovoljan, višemodalan, konfliktan, neinteger ili nekalibrisan slučaj.
6. Čista, nemutirajuća simulacija jedne dokazano targetirane note nad immutable semantic snapshotom.
7. Before/after validacija lokalnog bara, susjeda, note-paira, patterna, groove modea, granica i non-target pariteta.
8. Deterministički audit i canonical semantic digest.

## NON_GOALS

WP-X10-013A ne implementira:

- MIDI byte mutation, encode, export, overwrite, temp MIDI ili output MIDI;
- `Apply`, `Commit`, `Accept selected`, rollback izvršenja ili transaction journal za stvarnu izmjenu;
- automatski ili ručni repair capability;
- velocity, duration, pitch, controller, Program/Bank ili structural candidate;
- dodavanje/brisanje note ili događaja;
- više-note, chord, bar, pattern ili section cascade candidate;
- globalno rangiranje, best-candidate izbor ili repair budget potrošnju;
- grid/nearest-step target, quantize, random/humanize ili fiksni timing prag;
- učenje iz candidatea, simulacije ili korisničkog inputa;
- retroaktivno mijenjanje Factory/Gold DNA, schema-v2 authorizationa ili protection rezultata;
- GUI preview, dry-run export, certification ili Pa800/release odluku.

Nazivi `candidate`, `target` i `simulation` smiju postojati samo u novom 013A sloju. Ne dodaju se u prihvaćeni 012D schema-v2 niti mijenjaju njegov `ANALYZE_ONLY/NONE` capability zapis.

## DEPENDENCIES

Obavezne zavisnosti:

- QA-accepted WP-X10-012A/B/C/D;
- schema-v2 `source_context_v2`, stable subject/edge, exact context, adapter coverage, Factory model, reference relationship i final authorization zapisi;
- immutable source SHA-256 i trusted lineage digest;
- canonical build/config/protection/model/reference digesti;
- stable `NOTE` → `EVENT` i context/bar/track-channel veze;
- exact meter/bar tick granice i integer PPQ/tick reprezentacija;
- versioned, robust calibration envelope koji daje minimum meaningful i maximum allowed delta za isti exact context.

Ako calibration envelope sa dokazivim provenanceom nije dostupan, kandidat ostaje `TARGET_WITHHELD_CALIBRATION_UNAVAILABLE`. WP-013A ne smije izmišljati prag.

Source granice ostaju iste:

```text
Factory NORMAL  → jedini target autoritet
Factory RARE/OUTLIER/INVALID → preserve/review, nikad target
Gold/reference → support/conflict samo; nikad target autoritet
šest songova → samo Delay/Terca relationship, nikad 013A evidence
optimizer/repaired output → nikad evidence
synthetic fixture → test ugovor, nikad Factory dokaz
```

## DATA CONTRACT

### Immutable input snapshot

013A run mora zaključati:

- source SHA-256, source class i lineage digest;
- schema-v2 semantic digest i build/config digeste;
- exact context, stable subject i edge digeste;
- relevant adapter run/coverage/protection digeste;
- Factory observation/model/component i reference digeste;
- local repeated-pattern i calibration digeste;
- original note/event vrijednosti i evidence locatore.

Svaki mismatch, missing row, broken FK, changed digest ili stale snapshot abortuje run. Nema best-effort joina.

### Candidate natural key

Candidate ID je SHA-256 canonical JSON-a:

```text
[
  candidate_contract_version,
  source_sha256,
  stable_note_subject_id,
  exact_context_id,
  event_slot_id,
  input_snapshot_digest,
  anomaly_proof_digest,
  target_proof_digest
]
```

Jedan natural key smije imati samo jedan canonical sadržaj. Kontradikcija je hard fail.

### Closed candidate states

```text
NOT_EVALUATED
INELIGIBLE_INPUT
ANOMALY_NOT_PROVEN
ANOMALY_CONFLICT
TARGET_WITHHELD_INSUFFICIENT_EVIDENCE
TARGET_WITHHELD_MULTIPLE_VALID_TARGETS
TARGET_WITHHELD_CALIBRATION_UNAVAILABLE
TARGET_WITHHELD_NONINTEGER_TICK
TARGET_WITHHELD_PROTECTION_OR_BOUNDARY_RISK
TARGET_PROVEN_EXACT
SIMULATION_REJECTED
SIMULATION_VALIDATED
```

Unknown status je hard fail. Status ne nosi repair permission.

### Candidate payload

Obavezna polja:

- stable note/on-event/off-event ID;
- original on/off tick, duration, bar i exact event slot;
- input/schema/config/model/calibration/protection digesti;
- anomaly class/status, dokaz i rejection reasons;
- target status;
- Factory, local-pattern i optional reference evidence locatori;
- target phase kao reduced rational i target tick samo za `TARGET_PROVEN_EXACT`;
- signed `delta_ticks` i derived off tick samo za `TARGET_PROVEN_EXACT`;
- modification cost i budget impact kao analiza, bez potrošnje budžeta;
- simulation status/digest i validation status;
- immutable `capability=ANALYZE_ONLY`, `mutation_capability=NONE`.

Za svaki drugi status target phase, target tick, derived off tick i delta moraju biti SQL/API `NULL`, ne sentinel `0`.

## RULE CONTRACT

013A koristi zaseban versioned rule registry. Svako pravilo mora sadržati:

- rule ID/version/owner/status;
- exact scope i required stable subject types;
- required input/config/evidence digeste;
- source/file/bar/sample sufficiency;
- anomaly predicate;
- target proof predicate;
- protected/negative predicates;
- allowed hypothetical fields (`on_tick`, `off_tick` samo kao jednaka translacija);
- calibration dependency;
- simulation validators;
- conflict precedence i test IDs.

Precedence:

```text
hard integrity/source failure
→ protection/boundary failure
→ anomaly conflict
→ target ambiguity/insufficiency
→ calibration failure
→ simulation/validation failure
→ validated hypothesis
```

Neriješen konflikt uvijek daje withheld/reject, nikad tie-break target.

## ANOMALY PROOF CONTRACT

`ANOMALY_PROVEN` zahtijeva istovremeno:

1. schema-v2 final authorization je `ANALYZE_ALLOWED` za isti exact context i subject;
2. source je Factory-valid user input, a reference model dolazi samo iz trusted Factory NORMAL lineagea;
3. svi core protection adapteri su complete i clear/not-applicable; nema protected, ambiguous, partial, deferred ili external-evidence gap statusa;
4. Factory model je sufficient, stable i unimodal za isti exact event slot;
5. originalna reduced rational phase je dokazivo izvan conservative Factory support enclosure, uključujući stvarnu half-tick rezoluciju;
6. isti lokalni repeated-pattern scope ima najmanje dvije druge exact instance i one ne podržavaju originalnu fazu;
7. neighbour, onset-cluster, previous/next same-note, cross-bar, section i tempo/meter boundary analiza ne daje muzički-intent ili ordering konflikt;
8. Gold/reference, ako je sufficient, nije u kontradikciji sa Factory zaključkom;
9. negative-corpus pravila ne klasifikuju događaj kao validnu syncopation, anticipation, pickup, fill, ornament, Guitar Mode, RX/DNC ili drum-articulation strukturu.

Original koji je samo udaljen od model mean-a nije anomalija. Grid odstupanje nije anomalija. `ANALYZE_ALLOWED` nije anomalija.

Ako ijedna tačka nije dokazana, status je `ANOMALY_NOT_PROVEN` ili `ANOMALY_CONFLICT`, a target ostaje `NULL`.

## EXACT TARGET PROOF CONTRACT

Tačan target je dozvoljen samo poslije `ANOMALY_PROVEN` i samo ako svi uslovi prolaze:

1. Target phase je stvarno opažena reduced rational Factory faza; ne smije biti zaokruženi model mean, grid pozicija ili sintetička interpolacija.
2. Ista phase vrijednost ima cross-file Factory sufficiency i prolazi postojeći source-dominance gate.
3. Ista phase vrijednost je jedinstveni rezultat lokalnih repeated-pattern instanci istog stable track/channel, pattern/topology, exact context i event slota.
4. Factory component membership i local-pattern dokaz se poklapaju byte-for-byte po phase vrijednosti; više validnih phase vrijednosti znači `TARGET_WITHHELD_MULTIPLE_VALID_TARGETS`.
5. Sufficient Gold/reference, ako postoji, mora podržavati phase; odsutan/insufficient reference ne daje target dokaz, ali ne mora sam blokirati kada su Factory i local dokaz potpuni.
6. Target rational phase se u stvarnom input bar-u pretvara u tačan integer tick bez round/floor/ceil operacije.
7. Signed delta je nenulti, najmanje `minimum_meaningful_delta` i najviše `maximum_allowed_delta` iz version-compatible calibration envelopea istog exact contexta.
8. Translacija Note On/Off ne prelazi bar/section/tempo/meter boundary, ne mijenja onset-cluster semantiku, ne preskače susjeda i ne stvara same-note overlap, negative duration ili order konflikt.
9. Nema drugog jednako validnog targeta, rule konflikta ili budget konflikta.

Ovaj ugovor ne tvrdi da je target spreman za primjenu. On samo dozvoljava `TARGET_PROVEN_EXACT` i nemutirajuću simulaciju.

## SIMULATION CONTRACT

Simulation engine je čista funkcija:

```text
immutable semantic snapshot + one TARGET_PROVEN_EXACT candidate
→ immutable shadow event graph + metrics
```

Obavezna ograničenja:

- ne poziva MIDI encoder/writer i ne zapisuje `.mid`/`.midi` fajl;
- ne mijenja input bytes, parser objekte, schema-v2 bazu ili evidence/model baze;
- kopira samo minimalni affected bar + neighbour closure u shadow reprezentaciju;
- hipotetički mijenja isključivo on/off tick iste note za isti delta;
- ne simulira dva kandidata zajedno;
- ne koristi rezultat kao training/evidence;
- svaki run je determinističan i canonical serializable;
- exception ne ostavlja parcijalni semantic output.

Simulation bez `TARGET_PROVEN_EXACT` mora biti odbijena prije konstrukcije shadow grafa.

## VALIDATION CONTRACT

Simulation dobija `SIMULATION_VALIDATED` samo ako svi validator statusi prolaze:

- stable subject i note pair ostaju isti;
- pitch/channel/track/velocity/duration i svi non-target događaji imaju semantic parity;
- event order, EOT-relative granice i note-on/off semantika ostaju validni;
- nema overlap, unmatched, duplicate ili negative-duration problema;
- target phase tačno odgovara proven rational phase;
- Factory support se poboljšava, bez izlaska iz calibration envelopea;
- local repeated-pattern distance se strogo poboljšava;
- groove-mode tuple i topology/pattern fingerprint se ne pogoršavaju;
- syncopation, cluster, neighbour, cross-bar i boundary klasifikacije se ne mijenjaju;
- modification cost je minimalan među dokazivo ekvivalentnim translacijama;
- candidate i simulation digesti su reproducibilni.

`equal`, `unknown`, numerical uncertainty ili validator disagreement nisu poboljšanje i daju `SIMULATION_REJECTED`.

## FAIL-CLOSED BEHAVIOR

### Hard fail / abort

- source/SHA/lineage/schema/config/digest mismatch;
- broken stable subject/edge/FK ili contradictory natural key;
- forbidden six-song/optimizer/repaired lineage;
- unknown enum/rule/version ili nondeterministic serialization;
- schema-v2 mutation;
- MIDI encoder/writer/output poziv;
- target polja prisutna bez `TARGET_PROVEN_EXACT`;
- target nije observed rational Factory phase;
- rounded/noninteger tick predstavljen kao exact;
- input bytes ili evidence/model snapshot promijenjeni;
- partial database replace ili integrity failure.

### Preserve / withheld / reject

- non-exact/RARE/OUTLIER/INVALID input;
- protection, boundary, RX/DNC ili Factory/reference konflikt;
- insufficient/unstable/multimodal/degenerate evidence;
- anomaly nije dokazana;
- local pattern nije unique/sufficient;
- calibration nije version-compatible;
- više validnih targeta ili neinteger tick;
- simulation ne daje strogo poboljšanje;
- bilo kakva dilema o musical intentu.

## AUDIT CONTRACT

Svaki run čuva:

- canonical input snapshot digest;
- candidate/anomaly/target proof digeste;
- sve source, model, rule i config verzije;
- exact evidence locatore i negative/protection razloge;
- before/after semantic metrics;
- validator matrix;
- rejected/withheld status;
- capability `ANALYZE_ONLY`, mutation `NONE`;
- terminal run status i semantic digest.

Audit zapis nije repair journal i nije dozvola za kasniji silent apply.

## TEST CONTRACT

Obavezni test slojevi:

1. **Positive contract fixtures**: samo sintetički, potpuno dokazani single-note exact target slučajevi.
2. **Negative Factory fixtures**: validni microtiming, swing, syncopation, anticipation, pickup, fill, ornament, Guitar Mode, RX/DNC i drum strukture moraju završiti bez targeta.
3. **Ambiguity**: dva Factory/local targeta, multimodal, degenerate, near-tie, insufficient source/bar i reference conflict.
4. **Resolution**: PPQ mismatch, rational target koji nije integer tick, half-tick enclosure i boundary edge.
5. **Identity/integrity**: stale digest, forged subject/edge, source class mismatch, forbidden lineage i cross-source join.
6. **Simulation semantics**: note-pair equal translation, unchanged duration/non-target hash, overlap/order/cluster rejection.
7. **Mutation guards**: encoder/writer/output calls, input byte mutation i schema-v2 write pokušaji moraju failovati.
8. **Determinism**: input/rule/source order permutacije daju isti candidate, simulation i semantic digest.
9. **Atomicity**: exception/failure čuva prethodni accepted 013A target database byte-identično.
10. **Full regression**: cijeli pytest sa warning-as-error, SQLite integrity/FK i `git diff --check`.

Synthetic positive fixture dokazuje software contract, ne Factory muzičku istinu i ne smije ući u corpus evidence.

## FILE OWNERSHIP RECOMMENDATIONS

### Codex Implementer — novi 013A core

```text
rxoptimizer/rhythm_candidate.py
rxoptimizer/rhythm_simulation.py
rxoptimizer/rhythm_proposal_models.py
tests/test_rhythm_candidate.py
tests/test_rhythm_simulation.py
tests/test_rhythm_proposal_models.py
tests/fixtures/x10_proposal_simulation/
```

### Codex Lead — integration nakon QA

```text
analysis/agent_work_packages.json
COMPLETION_REPORT.md
SESSION_CHECKPOINT.md
```

### Read-only u WP-013A

```text
rxoptimizer/rhythm_context_models.py
rxoptimizer/rhythm_context_join.py
rxoptimizer/rhythm_protection.py
rxoptimizer/rhythm_protection_adapters.py
rxoptimizer/rhythm_multimodal.py
rxoptimizer/rhythm_reference_conflict.py
rxoptimizer/rhythm_subject_registry.py
rxoptimizer/midi.py
```

Promjena bilo kojeg read-only interfejsa zahtijeva novi integration addendum i re-audit prije implementacije.

## ACCEPTANCE_CRITERIA

WP-X10-013A može dobiti tehnički `ACCEPT` samo ako:

1. capability svuda ostaje `ANALYZE_ONLY/NONE` i schema-v2 je byte/semantic nepromijenjen;
2. nema MIDI encoder/writer/export putanje niti output MIDI artefakta;
3. candidate je vezan za stable note/on/off/event slot i frozen schema-v2 digest;
4. svi statusi/rule/config domeni su zatvoreni i versioned;
5. anomaly proof ne koristi grid, globalni mean ili distance sam kao dokaz;
6. default i svaki nedokazan slučaj imaju `NULL` target/delta polja;
7. `TARGET_PROVEN_EXACT` prolazi kompletan Factory + local pattern + calibration + protection ugovor;
8. target je opažena rational Factory faza i mapira se bez zaokruživanja na integer input tick;
9. Gold/reference ne kreira niti pomjera target;
10. šest songova i optimizer/repaired lineage su zabranjeni prije candidate analize;
11. simulacija prihvata samo jedan `TARGET_PROVEN_EXACT` kandidat i mijenja samo shadow on/off tick istim delta;
12. non-target semantic parity, duration, ordering, overlap, pattern, groove, syncopation i boundary validatori prolaze;
13. nejasno/equal/numerički nesigurno poboljšanje se odbija;
14. dva identična runa i permutirani input order daju isti candidate/simulation/digest;
15. failure je atomski i čuva prethodni output;
16. positive, negative, ambiguity, adversarial, mutation-guard i full regression testovi prolaze sa warning-as-error;
17. nezavisni Codex QA vraća isključivo `ACCEPT`, `RETURN` ili `BLOCK`, bez otvorenog critical/high nalaza za `ACCEPT`.

Tehnički `ACCEPT` znači samo da je analyze-only foundation ispravan. Ne znači da postoji dry run, preview, manual repair, auto-repair, Pa800 dokaz ili release.

## HUMAN_DECISIONS_REQUIRED

Human Owner zadržava odluku o:

- budućem prelasku iz `ANALYZE_ONLY` u `PROPOSAL_ONLY`;
- dozvoli da se validated simulation prikaže kao korisnički actionable proposal;
- repair budget pragovima i acceptable false-repair pragu;
- manual apply/commit/rollback capabilityju;
- Pa800 A/B, certification i releaseu.

Za WP-013A nije potrebna nova Pa800 odluka jer paket ne proizvodi niti mijenja MIDI.

## REMAINING PACKAGES

Nakon WP-013A i dalje ostaju zasebni, novi ugovori:

1. multi-candidate ranking, cascade analysis i session repair budget;
2. dry-run/preview report i GUI bez apply capabilityja;
3. manual decision, immutable byte snapshot, commit/export i rollback;
4. negative/adversarial/corruption KPI i false/missed repair mjerenje;
5. safe auto-repair gate;
6. Pa800 blind A/B i certification/release.

Nijedan od tih paketa nije implicitno odobren ovim dokumentom.

## Architect verdict

```text
ARCHITECT_READY
```