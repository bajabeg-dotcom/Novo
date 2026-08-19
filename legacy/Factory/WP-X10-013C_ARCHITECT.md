# WP-X10-013C — Architect Work-Package Contract

Datum: 12. august 2026.  
Verzija: 1  
Naziv: Schema-v2 Factory Calibration Envelope  
Capability: `ANALYZE_ONLY`  
Mutation capability: `NONE`  
Status: `ARCHITECT_READY`

## 1. Svrha

WP-X10-013C gradi immutable, versioned i schema-v2 vezan opis opaženog Factory timing ponašanja za jedan tačno određeni:

```text
calibration_context_key + structural_event_slot_key + Factory component
```

Paket odgovara samo na pitanje:

> Koje su Factory-observed faze, varijacija i rezolucijska neizvjesnost unutar ovog dokazanog konteksta i stabilne modalne komponente?

Ne odgovara na pitanja:

```text
Da li je USER_INPUT nota anomalija?
Na koji tick je treba pomjeriti?
Da li promjena poboljšava MIDI?
Da li je repair dozvoljen?
```

Rezultat je calibration envelope, ne target, tolerancija za automatsku izmjenu niti repair prag. Ne smije samostalno pretvoriti `ANALYZE_ALLOWED` u anomaly, candidate, proposal ili change dozvolu.

## 1.1 Kritični schema-v2 identity prerequisite

Inventar prihvaćenog WP-012D koda pokazuje da postojeći `EVENT_SLOT_V2` nije podoban calibration ključ:

```text
event_slot_key = hash(exact_context_key, note_number, onset_phase)
```

Onset faza je upravo veličina čiju distribuciju calibration treba mjeriti. Grupisanje po tom ključu razdvaja timing varijante u različite slotove, a off-phase budući USER_INPUT ne može pronaći isti slot bez circularnog korištenja sopstvene faze. Postojeći `exact_context_key` dodatno uključuje timing-sensitive topology hash i zato se ne smije nekritički koristiti kao jedini cross-variation calibration partition.

Zato 013C ima obavezni prvi analyze-only identity podpaket:

```text
013C-S — PHASE_INDEPENDENT_STRUCTURAL_SLOT_REGISTRY
```

013C-S ne mijenja, migrira niti reinterpretira WP-012D `event_slot_key` ili `exact_context_key`. Materijalizuje paralelne ključeve samo za calibration.

### `calibration_context_key`

Hashuje samo exact dokazive netiming dimenzije:

- role i Program/Bank instrument identitet;
- style/section/section number/CV sa provenanceom;
- meter i versioned tempo-regime ugovor;
- track-channel structural role;
- phase-independent voice topology: ordered cluster cardinalities, pitch/voice offsets i eksplicitno odobreni structural tokeni;
- identity contract/config digest.

Ne smije hashovati onset tick, tick-in-bar, absolute phase, IOI vrijednost, nearest-grid poziciju, velocity niti USER_INPUT podatak. Duration je po defaultu isključena; smije postati structural kategorija samo posebnim auditovanim ugovorom koji dokazuje da ne sadrži vrijednost koju envelope modelira.

### `structural_event_slot_key`

Hashuje:

```text
[
  structural_slot_contract_version,
  calibration_context_key,
  onset_cluster_ordinal,
  cluster_cardinality,
  canonical_voice_signature,
  pitch_or_drum_lane_identity,
  structural_alignment_digest
]
```

Onset faza i IOI su zabranjeni inputi. Cluster ordinal je dozvoljen samo kada phase-independent structural alignment daje jedan jedinstven slot. Crossing, merged/split cluster, duplicate voice signature, ambiguous ordinal ili različit broj structural slotova daje `STRUCTURAL_SLOT_AMBIGUOUS` i blokira calibration za taj context.

Svaki novi ključ mora imati many-to-one provenance prema originalnim WP-012D exact-context/event-slot/note/cluster/bar zapisima. Calibration observation se prihvata samo ako se iz frozen stable-subject grafa deterministički ponovo izračuna isti structural key.

Ako 013C-S nije implementiran, auditovan i QA-prihvaćen, envelope build mora završiti:

```text
CALIBRATION_BLOCKED_PHASE_DEPENDENT_SLOT_IDENTITY
```

Legacy `rhythm_calibration.sqlite3`, postojeći phase-bearing `event_slot_key` i synthetic manual mapping nisu autoritativna zamjena.

## 2. Granica paketa

### U scopeu

1. Read-only učitavanje QA-prihvaćenog schema-v2 Factory modela i frozen Factory observations iz WP-012C/012D.
2. Phase-independent structural slot registry i Factory-only calibration po calibration contextu, structural event slotu i odabranoj Factory komponenti.
3. Source-balanced robustna kružna distribucija opaženih reduced-rational faza.
4. Posebno evidentiranje empirijskog supporta, resolution hull-a, disperzije, percentile/MAD/IQR statistike i source/bar sufficiencyja.
5. Leave-one-source-out stabilnost cijelog envelopea i njegovih komponenti.
6. Fail-closed razdvajanje multimodalnih komponenti; nema spajanja modova u jedan širok envelope.
7. Opcionalni `minimum_meaningful_delta` i `maximum_allowed_delta` samo kada su matematički i empirijski dokazivi po ovom ugovoru.
8. Post-envelope Gold/reference support ili conflict procjena bez refita Factory envelopea.
9. Protection/negative status koji može samo blokirati ili označiti review; nikad odobriti promjenu.
10. Deterministički, atomski i disk-backed SQLite full build, provenance, canonical digest i read-only query API.

### Izvan scopea

WP-X10-013C ne implementira:

- USER_INPUT ingest, join, phase scoring ili poređenje sa envelopeom;
- anomaly proof, anomaly score ili outlier odluku za korisničku notu;
- target phase/tick, candidate value, delta za konkretnu notu ili ranking;
- leave-one-target-out lokalno poređenje;
- proposal, simulation, validation promjene, dry-run, preview, apply ili rollback;
- MIDI parser→writer put, encoder, export ili bilo kakav MIDI output;
- velocity/duration/pitch/controller calibration;
- grid, nearest-step, quantize, random/humanize ili sintetičku fazu;
- učenje iz Gold/reference, USER_INPUT, optimizer outputa, repaired outputa ili šest Delay/Terca pjesama;
- mijenjanje WP-012A/B/C/D ili WP-013A/B accepted baza i truth tableova.

Zabranjena schema/API imena uključuju:

```text
target_tick
target_phase
candidate_value
user_input_score
anomaly_score
proposed_delta
shadow_tick
repair_allowed
apply
commit
output_midi
```

## 3. Autoritet i source granice

### Factory fit autoritet

Envelope se smije fitovati samo iz observations koje istovremeno imaju:

- `authority=FACTORY`;
- `source_quality=NORMAL`;
- `context_status=EXACT_CONTEXT_MATCH`;
- trusted `FACTORY_RAW` root i puni ancestor closure;
- isti phase-independent calibration context i structural event slot;
- membership u jednoj verified Factory komponenti refitovanoj nad structural-slot universeom po neizmijenjenom WP-012C model ugovoru;
- stable subject/event/bar provenance i validne FK veze;
- source koji nije šest-song, optimizer, repaired, unknown ili cross-authority lineage.

Factory `RARE`, `OUTLIER` i `INVALID` nisu fit observations. Mogu se samo brojati u odvojenom non-authoritative review sažetku ako je njihova lineage i klasifikacija dokaziva; ne ulaze u envelope niti sufficiency.

### Gold/reference

Gold/reference se obrađuje tek nakon finalizacije Factory envelopea:

```text
Factory observations
→ immutable Factory envelope
→ optional reference support/conflict assessment
```

Reference nikada:

- ne mijenja component mean, scale, support hull ili delta granice;
- ne povećava Factory distinct-source/bar sufficiency;
- ne popunjava missing Factory komponentu;
- ne pretvara unavailable/unstable Factory envelope u available;
- ne predstavlja exact-target vote.

Dozvoljeni reference rezultat je samo support/conflict/review prema rezolucijski proširenom Factory supportu.

## 4. Obavezne zavisnosti i frozen input

Paket zavisi od QA-prihvaćenih WP-012A/B/C/D i mora zaključati:

- schema-v2 semantic digest, schema version i build/config digest;
- Factory source manifest i trusted lineage DAG digest;
- stable subject i edge universe digest;
- originalnu exact-context/event-slot definiciju i provenance digest;
- QA-prihvaćen calibration-context/structural-slot registry digest;
- Factory observation universe digest;
- reproducirani `VerifiedFactoryAssessment` semantic digest;
- component membership, hard-observation ID-jeve i component semantic zapis;
- protection config, adapter run, coverage i aggregate digeste;
- optional reference observation/relationship digest;
- calibration contract/config/enum registry digest.

Model se prije calibrationa ponovo deterministički izračunava iz frozen Factory observations. Stored model/component zapis mora odgovarati byte-for-byte reproduciranom WP-012C rezultatu. Mismatch abortuje build; nema povjerenja u sam stored token ili semantic JSON. Pošto prihvaćeni WP-012C model trenutno koristi phase-bearing slot particiju, 013C zatim mora reproducibilno primijeniti isti zaključani model ugovor nad 013C-S structural-slot observation universeom. Stored 012C komponenta je provenance/safety input, ne dozvola da se phase-bearing particija zadrži. Refit ne mijenja WP-012C bazu.

Input baze se otvaraju read-only. Build ne smije dodavati calibration redove u schema-v2 bazu.

## 5. Calibration natural key i particionisanje

Jedan envelope natural key je:

```text
[
  calibration_contract_version,
  schema_v2_semantic_digest,
  calibration_context_key,
  structural_event_slot_key,
  original_context_membership_digest,
  factory_model_id,
  factory_component_id,
  factory_component_semantic_digest,
  calibration_config_digest
]
```

Svaka Factory komponenta dobija zaseban envelope. `ASSESSED_MULTIMODAL` sa K komponenti daje K odvojenih redova ili review status; nikada jedan union/min-max envelope preko svih komponenti. Komponente se fituju nad structural-slot universeom; komponenta iz phase-bearing legacy slot grupe ne smije se samo prekopirati.

Observations ne smiju pripadati dvjema komponentama. Posterior tie, missing hard assignment, component collapse, unstable component matching ili LOSO component permutation koja nije jedinstveno razrješiva daje unavailable/review, ne prošireni envelope.

## 6. Exact numeric contract

### Faze i udaljenosti

- Svaka onset faza je reduced `Fraction` modulo 1.
- Binary float je zabranjen u semantic inputu, fitu, poređenju i storageu.
- Kružna udaljenost je exact rational:

```text
d(a,b) = min(|a-b|, 1-|a-b|)
```

- Decimal statistike koriste zaključanu precision/rounding konfiguraciju usklađenu sa WP-012C.
- Exp/ln, probability ili interval comparison, ako se koriste, moraju koristiti certified outward Decimal enclosure; overlap znači `UNCERTAIN`, nikad tihi tie-break.
- Svaki rational se čuva kao numerator/denominator sa denominatorom > 0; canonical reduction se ponovo provjerava pri čitanju.

### Resolution-aware observation interval

Za observation fazu `p` i stvarnu half-tick rezoluciju `r`, elementary support je kružni zatvoreni luk:

```text
I(p,r) = circular_arc(center=p, radius=r)
```

Rezolucija se izvodi iz stvarnog PPQ-a i bar lengtha konkretnog observationa. Ne smije se zamijeniti globalnim epsilonom. Wrap preko nule čuva se kao jedan kružni luk sa canonical split reprezentacijom.

Empirijski point support i resolution-expanded support moraju ostati odvojeni. Prošireni luk ne smije biti prikazan kao opažena Factory faza.

## 7. Source-balanced robustna statistika

Calibration nasljeđuje WP-012C equal-source princip:

1. Svaki distinct Factory source dobija jednaku ukupnu masu.
2. Observations unutar sourcea dijele njegovu masu; source sa mnogo barova ne smije dominirati.
3. Bar identity ostaje `(source_sha256, bar_id)` i duplikat ne povećava masu.
4. Hard component membership iz verified modela zaključava observation universe prije statistike.

Po komponenti se materijalizuju najmanje:

- broj distinct source fajlova i source-balanced effective sample size;
- broj distinct barova i observations;
- exact set opaženih rational faza sa source/bar countovima;
- source-balanced circular medoid, samo kao descriptivni centar;
- weighted circular absolute-deviation distribucija od component centra;
- conservative median, MAD, Q1, Q3, IQR, P05 i P95 udaljenosti;
- exact point support arc i resolution-expanded support arc;
- minimum/maximum half-tick resolution;
- dominant source share i sufficiency status;
- zero-variation/degenerate status;
- model/component/observation/config digesti.

Percentili koriste versioned deterministic weighted quantile pravilo sa exact rational cumulative source massom. Interpolacija koja stvara neopaženu phase granicu nije dozvoljena. Quantile rezultat je opažena rational distance ili conservative interval između susjednih opaženih vrijednosti, nikad binary64 broj.

Sve statistike grupišu se po `calibration_context_key + structural_event_slot_key`. Originalni `exact_context_key + event_slot_key` ostaje samo locator/provenance član i ne određuje calibration grupu.

## 8. Closed envelope statusi

```text
CALIBRATION_AVAILABLE_UNIMODAL
CALIBRATION_AVAILABLE_COMPONENT
CALIBRATION_DEGENERATE_EXACT
CALIBRATION_INSUFFICIENT_FACTORY_SOURCES
CALIBRATION_INSUFFICIENT_BARS
CALIBRATION_SOURCE_DOMINANCE_REVIEW
CALIBRATION_MODEL_UNSTABLE
CALIBRATION_COMPONENT_UNSTABLE
CALIBRATION_LOSO_UNSTABLE
CALIBRATION_NUMERICAL_REVIEW
CALIBRATION_PROTECTION_BLOCKED
CALIBRATION_REFERENCE_CONFLICT_REVIEW
CALIBRATION_BLOCKED_PHASE_DEPENDENT_SLOT_IDENTITY
CALIBRATION_UNAVAILABLE
```

Samo prva tri statusa mogu sadržati descriptive envelope. Čak i tada capability ostaje `ANALYZE_ONLY/NONE`.

`CALIBRATION_DEGENERATE_EXACT` znači da observations daju jednu exact point fazu uz eksplicitnu measurement resolution. Ne znači nultu grešku, univerzalnu toleranciju niti automatski target.

## 9. Leave-one-source-out stabilnost

Za najmanje četiri distinct Factory sourcea obavezno se radi exhaustive LOSO. Za svaki izostavljeni source:

1. ponovo se fituje Factory model iz preostalih sourcea;
2. komponenta se mapira na full-model komponentu samo ako directed matching cost ima jedinstven strict interval winner;
3. ponovo se izračuna calibration envelope iz preostalih hard members;
4. porede se component count, component identity, support arc, robust stats i delta-bound availability.

LOSO prolaz zahtijeva:

- isti dokazivi modalni/component status;
- jedinstveno component mapping razrješenje u svakom foldu;
- nijedan fold bez source/bar sufficiencyja;
- nijedan fold sa posterior tie, numerical uncertainty ili component collapse;
- full-envelope point support i svaki LOSO point support imaju nonempty empirical/resolution-aware odnos propisan configom;
- delta-bound status se ne mijenja iz available u unavailable niti obrnuto;
- available granice ostaju unutar certified stability intervala definisanog configom.

Ako distinct sourcea ima 3, osnovni model može biti sufficient po WP-012C, ali 013C envelope ostaje `CALIBRATION_LOSO_UNSTABLE`/unavailable za delta granice jer exhaustive LOSO ugovor zahtijeva najmanje 4.

LOSO ne koristi Gold/reference.

## 10. Minimum meaningful delta

`minimum_meaningful_delta` je opcionalna calibration rezolucijska granica, ne repair minimum. Smije postojati samo ako se može dokazati bez USER_INPUT-a i bez izmišljene tolerancije.

Dozvoljena semantika:

> Najmanja kružna fazna razlika koju ovaj Factory envelope može pouzdano razlikovati od kombinovane measurement resolution i empirijske within-component varijacije.

Da bi bila `AVAILABLE`, mora vrijediti:

1. calibration status je available i LOSO stable;
2. component nije multimodalno pomiješan;
3. measurement-resolution hull i source-balanced within-component deviation imaju finite certified upper bound;
4. isti bound je stabilan u svim LOSO foldovima;
5. konačna vrijednost je conservative upper envelope tih uncertainty boundova;
6. vrijednost je positive exact rational ili outward Decimal interval čiji je lower endpoint > 0;
7. config verzija zaključava formulu, quantile level, inclusion of half-tick resolution i tie/overlap ponašanje.

Ako empirical variation ima samo exact repeats, minimalna granica se ne postavlja na nulu. Može se zasnovati samo na stvarnoj resolution granici; ako ni ona nije potpuno dokaziva, status je `MINIMUM_MEANINGFUL_UNAVAILABLE`.

Zabranjeno je:

- hardkodirati jedan tick, 1/16 ili drugi grid prag;
- koristiti component scale/mean bez certified resolution/LOSO dokaza;
- proglasiti razliku ispod granice validnom ili iznad granice anomalijom;
- pretvoriti granicu u target permission.

## 11. Maximum allowed delta

`maximum_allowed_delta` je strože opcionalan. U 013C znači samo:

> Najveća kružna udaljenost unutar koje postoje kompletni, stabilni Factory observations iste komponente i calibration-context/structural-slot particije, uz konzervativnu measurement-resolution ekspanziju.

Ne znači da je bilo kakva buduća translacija do te udaljenosti sigurna ili dozvoljena.

Može biti `AVAILABLE` samo kada:

1. envelope i svi LOSO foldovi su available/stable;
2. komponenta ima jedinstven canonical support arc kraći od polukruga;
3. nema disconnected support segmenta unutar iste komponente nakon resolution ekspanzije;
4. support boundary je podržan dovoljnim brojem distinct Factory sourcea, ne jednim ekstremnim sourceom;
5. reference nije u `POTENTIAL_CONTRADICTION` ili partial/deferred statusu;
6. protection/negative review ne pokazuje da support miješa različite muzičke namjere;
7. conservative full/LOSO intersection daje nonempty granicu;
8. formula i boundary source-sufficiency su version-locked.

Konačna granica je conservative intersection full-model i svih LOSO component support radijusa, ne maximum opaženog outliera. Ako je luk >= 1/2, wrap je nejedinstven, support je disconnected, boundary source support nedovoljan ili intervali overlapuju na način koji ne daje jedinstvenu granicu, rezultat je `MAXIMUM_ALLOWED_UNAVAILABLE`.

Naziv ostaje historical contract naziv; API mora uz njega vratiti:

```text
semantic_scope = DESCRIPTIVE_FACTORY_ENVELOPE_ONLY
authorizes_change = false
```

## 12. Protection i negative interaction

Calibration se gradi iz model observations, ali ne smije zaobići zaštitni sloj.

Obavezni gateovi:

- incomplete/partial/deferred core adapter coverage za calibration observation universe blokira envelope;
- observation sa `GUITAR_MODE`, `RX_DNC`, `ORNAMENT_TRILL_GRACE`, `DRUM_FLAM_ROLL_GHOST`, `CROSS_BAR`, `SECTION_TRANSITION` ili `TEMPO_METER_BOUNDARY` detected/ambiguous statusom ne smije se tiho apsorbovati u generički envelope;
- `LOCAL_REPEATED_PATTERN` detected status se ne reinterpretira kao target evidence; 013C smije samo zabilježiti odvojeni descriptive calibration stratum ako Architect/Audit potvrde da ne slabi postojeći preserve status;
- `FACTORY_REFERENCE_CONFLICT` se procjenjuje post-envelope i može samo dati conflict/review;
- negative corpus mora uključiti validnu syncopation, anticipation, pickup, fill, ornament, flam/roll/ghost, Guitar Mode i circular-wrap slučajeve.

Protection ne daje pozitivno odobrenje. `CLEAR` znači samo da taj gate nije blokirao opis Factory distribucije.

## 13. Reference assessment

Reference procjena koristi frozen Factory envelope i resolution-aware circular lukove.

Closed statusi:

```text
REFERENCE_NOT_EVALUATED
REFERENCE_NO_EVIDENCE
REFERENCE_INSUFFICIENT
REFERENCE_SUPPORTS_FACTORY_ENVELOPE
REFERENCE_PARTIAL_SUPPORT
REFERENCE_POTENTIAL_CONTRADICTION
REFERENCE_DEFERRED_FACTORY_UNSTABLE
```

Reference observation mora reproducibilno mapirati isti calibration context i structural event slot. Source balancing je odvojen od Factory mase. Rezultat samo opisuje odnos prema Factory envelopeu; ne mijenja njegov semantic digest ni granice.

## 14. Storage contract

Nova baza, preporučeno `rhythm_calibration_envelope.sqlite3`, je odvojena od legacy `rhythm_calibration.sqlite3`.

Minimalne semantic tabele:

### `calibration_structural_contexts` i `calibration_structural_slots`

- phase-independent canonical natural key i contract version;
- exact metadata/structural tokeni i provenance locatori;
- original schema-v2 context/event-slot/note/cluster/bar membership digest;
- alignment status i ambiguity reasons;
- enforced zabrana phase/tick/IOI/USER_INPUT identity polja;
- semantic digest.

### `calibration_runs`

- run/contract/schema/config verzije i digesti;
- frozen schema-v2/model/protection/lineage input digesti;
- terminal status;
- `capability=ANALYZE_ONLY`, `mutation_capability=NONE`;
- run semantic digest.

### `factory_calibration_envelopes`

- natural key i FK na run/model/context/slot/component;
- closed calibration status;
- source/bar/observation sufficiency;
- component i observation universe digest;
- descriptive center/dispersion/support serialization;
- capability lock i semantic digest.

### `factory_phase_support`

- exact rational phase;
- distinct source/bar counts;
- exact source-balanced mass;
- resolution arc i provenance digest;
- FK na envelope.

### `loso_calibration_folds`

- held-out source SHA;
- reproduced model/component mapping;
- fold status, statistics, support i digest;
- FK na envelope.

### `calibration_delta_bounds`

- bound type `MINIMUM_MEANINGFUL` ili `MAXIMUM_ALLOWED`;
- status `AVAILABLE`/`UNAVAILABLE`/`REVIEW`;
- exact rational ili Decimal interval samo za `AVAILABLE`;
- formula/config/provenance/LOSO digest;
- `semantic_scope=DESCRIPTIVE_FACTORY_ENVELOPE_ONLY`;
- `authorizes_change=0` enforced CHECK.

### `calibration_reference_assessments`

- Factory envelope FK;
- reference universe/config digest;
- closed status, reasons i semantic digest;
- bez FK ili polja koje mijenja Factory envelope sadržaj.

### `calibration_negative_validations`

- case ID/class, expected/actual status, registry digest i result digest.

Svi semantic redovi su insert-only u temp full build-u. Production query API nema update/delete. Build koristi temp SQLite, integrity/FK/digest/enum/reproduction provjere i tek zatim atomic replace. Failed build ne ostavlja accepted semantic red i čuva prethodni target byte-identično.

Timestamp, apsolutni path i performance metričke vrijednosti nisu dio semantic digesta.

## 15. Read-only API contract

Dozvoljeni API:

```text
get_calibration_run(run_id)
get_factory_envelopes(calibration_context_key, structural_event_slot_key)
get_structural_slot_provenance(structural_event_slot_key)
get_factory_component_envelope(model_id, component_id)
get_phase_support(envelope_id)
get_loso_folds(envelope_id)
get_delta_bounds(envelope_id)
get_reference_assessment(envelope_id)
verify_calibration_database(path)
```

Svaki payload mora vratiti capability/mutation lock i provenance/config digest. API ne prima USER_INPUT notu, observed user phase ili desired tick. Nema endpointa `score`, `compare_user`, `target`, `propose`, `simulate`, `repair` ili `export`.

## 16. Fail-closed ponašanje

Hard fail/abort:

- schema/model/component/observation/config/lineage digest mismatch;
- model koji nije potpuno reproducibilan;
- non-Factory ili non-NORMAL observation u fit universeu;
- cross-context, cross-slot ili cross-component membership;
- phase/tick/IOI vrijednost u calibration-context ili structural-slot identityju;
- korištenje postojećeg phase-bearing `EVENT_SLOT_V2` kao calibration grouping ključa;
- ambiguous cluster/voice alignment predstavljen kao resolved structural slot;
- forbidden six-song, optimizer/repaired ili cross-authority lineage;
- unknown enum/version, binary float semantic input ili noncanonical rational;
- posterior tie, component overlap ili LOSO mapping predstavljen kao resolved;
- delta bound value prisutan kada status nije `AVAILABLE`;
- `authorizes_change != 0` ili capability različit od `ANALYZE_ONLY/NONE`;
- Gold/reference uključen u Factory fit ili sufficiency;
- USER_INPUT podatak, score ili subject u calibration bazi;
- source/model/protection DB mutation;
- partial replace, integrity/FK/digest failure;
- MIDI writer/encoder/export/output poziv.

Normalan rezultat, ne greška:

- insufficient Factory source/bar count;
- degenerate exact repeat;
- unavailable minimum/maximum delta;
- multimodal component review;
- LOSO instability;
- reference absent/insufficient/conflicting;
- protection/negative review;
- zero production anomaly/target/candidate count.

## 17. Test contract

### Unit i mathematical

- exact rational circular distance i wrap oko 0/1;
- phase-independent structural slot identity: timing-varijantne Factory note moraju dobiti isti structural slot;
- promjena samo onset phase/IOI-ja ne smije promijeniti structural key;
- cluster split/merge/crossing i duplicate voice signature moraju dati ambiguity;
- per-observation half-tick resolution;
- deterministic equal-source weighting i duplicate-bar rejection;
- weighted median/MAD/IQR/percentile canonical tie ponašanje;
- support arc sa wrapom, disconnected supportom i polukrugom;
- outward Decimal interval i overlap→review;
- minimum meaningful available/unavailable/zero-variation slučajevi;
- maximum allowed available/disconnected/multimodal/insufficient-boundary-source slučajevi;
- unknown enum, float, noncanonical rational i unavailable-with-value rejection.

### Model/component integrity

- byte-for-byte WP-012C model reproduction;
- forged stored assessment/component/observation rejection;
- multi-component separation i zabrana union envelopea;
- posterior tie, component collapse i ambiguous mapping fail-closed;
- same context/different slot i same slot/different context izolacija.
- regresija koja dokazuje da phase-bearing WP-012D slot nije prihvaćen kao 013C grouping ključ;

### LOSO

- stable unimodal/component fixture;
- 3-source model daje delta-bound unavailable;
- held-out source component split/merge;
- component permutation sa unique i non-unique mappingom;
- support/bound interval overlap i near-tie review;
- dominant source i fold sufficiency failure.

### Source/provenance

- forbidden šest-song SHA sa `parse_count=0` za calibration fit;
- optimizer/repaired/unknown/cross-authority ancestor rejection;
- missing ancestor closure, class mismatch i manifest forgery;
- Factory RARE/OUTLIER/INVALID isključenje;
- Gold/reference ne mijenja Factory envelope ili digest;
- synthetic fixture nikad ne dobija Factory production authority.

### Protection/negative

- syncopation, anticipation, pickup, fill i boundary wrap se ne spljoštavaju;
- Guitar Mode, RX/DNC, ornament i drum articulation ne ulaze u generički clear envelope;
- partial/deferred adapter blokira;
- reference conflict samo mijenja reference/review status;
- `LOCAL_REPEATED_PATTERN` ne postaje target proof.

### Storage/API

- deterministic rebuild iz permutovanog input reda;
- canonical semantic digest i closed enum registry;
- SQLite integrity/FK i append-only schema;
- failed build čuva prethodni output byte-identično;
- read-only API nema user scoring/target/proposal/simulation/output surface;
- static forbidden-token/schema scan;
- static i dynamic scan da structural identity nema phase/tick/IOI field dependency;
- `pytest -W error`, compile i `git diff --check`.

### Adversarial

- jedan source sa hiljadama observations ne dominira tri manja sourcea;
- circular phases s obje strane nule ne postaju širok linearni interval;
- dva bliska moda ne daju jedan širok maximum delta;
- extremni observation iz jednog sourcea ne određuje boundary;
- coarse PPQ ne daje lažnu preciznost;
- Gold masa ne spašava insufficient Factory;
- LOSO fold sa numerical uncertainty ne dobija available bound;
- forged capability, `authorizes_change=1` ili target-like payload hard failuje.

## 18. Acceptance kriteriji

WP-X10-013C može dobiti tehnički `ACCEPT` samo ako:

1. Architect i Audit potvrde bounded Factory-calibration-only scope.
2. Phase-independent structural slot registry je implementiran, auditovan i QA-prihvaćen; timing varijanta ne mijenja slot identity.
3. Factory envelope koristi samo trusted NORMAL Factory observations iz jednog calibration-context/structural-slot/component universea.
4. WP-012C model ugovor se reproducira i refituje nad structural-slot universeom bez mijenjanja accepted 012C baze.
5. Source balancing, exact rational phases, resolution arcs i robust stats su versioned i reproducibilni.
6. Multimodalne komponente ostaju odvojene; instability/tie/collapse daje review/unavailable.
7. Exhaustive LOSO je implementiran i fail-closed.
8. Minimum meaningful i maximum allowed delta su nullable, dokazivi samo pod strogim uslovima i uvijek `authorizes_change=false`.
9. Gold/reference se obrađuje poslije Factory envelopea i ne utiče na fit/sufficiency/granice.
10. Protection i negative slučajevi ne mogu povećati capability ili proizvesti target.
11. Storage je immutable full-build, deterministički, atomic i integrity/FK/digest validan.
12. Public API je read-only i nema USER_INPUT scoring, anomaly, target, proposal, simulation ili output put.
13. Targeted, full pytest sa warning-as-error, compile i diff check prolaze.
14. Nezavisni Codex QA vrati `ACCEPT`.

Tehnički ACCEPT znači samo:

```text
013C_FACTORY_CALIBRATION_ENVELOPE_ACCEPTED
```

Ne znači anomaly proof, exact target, candidate, simulation, repair, Pa800 dokaz, certification ili release.

## 19. Predaja narednom paketu

Naredni paket smije čitati accepted calibration envelope samo kroz read-only verified API. Prije bilo kakvog USER_INPUT poređenja mora zasebno definisati:

- immutable USER_INPUT→calibration-context/structural-slot/component join;
- leave-one-target-out local comparison;
- anomaly proof i conservative comparison registry;
- razliku između descriptive Factory envelopea i actionable target ugovora.

013C nikad ne proizvodi ili naslućuje taj target.

## ARCHITECT VERDICT

```text
ARCHITECT_READY
```