# WP-X10-013B — Architect Work-Package Contract

Datum: 12. august 2026.  
Verzija: 1  
Capability: `ANALYZE_ONLY`  
Mutation capability: `NONE`  
Naziv: Immutable USER_INPUT Snapshot and Authority Separation  
Status: `ARCHITECT_READY`

## 1. Cilj

WP-X10-013B uvodi zaseban, immutable i privatnosti svjestan snapshot stvarnog korisničkog MIDI inputa. Paket dokazuje identitet originalnih uploadovanih bajtova, gradi kanonski parse-derived stable-subject graf i trajno odvaja korisnički input od Factory, Gold/reference, Human evidence i training autoriteta.

Paket ne odlučuje da li je događaj anomalija i ne predlaže promjenu. Njegov jedini semantički rezultat je dokaziv, read-only `USER_INPUT` snapshot ili fail-closed/excluded ingest rezultat.

Obavezna sposobnost ostaje:

```text
CAPABILITY = ANALYZE_ONLY
MUTATION = NONE
MODEL_AUTHORITY = NONE
EVIDENCE_AUTHORITY = NONE
TRAINING_ELIGIBILITY = NEVER
MIDI_OUTPUT = NONE
```

## 2. Scope

WP-X10-013B smije implementirati samo:

1. prijem jednog sealed MIDI byte streama preko platformskog upload handlea;
2. SHA-256 i veličinu originalnih, neizmijenjenih bajtova prije parsiranja;
3. pre-parse source guard i klasifikaciju zabranjenog inputa;
4. immutable content snapshot za dozvoljen `USER_INPUT`;
5. jedan deterministički parse originalnih snapshot bajtova;
6. kanonski parse manifest i stable-subject/edge graf u zasebnom USER_INPUT authority domenu;
7. upload/session provenance kroz opaque relativne locatore bez apsolutnog filesystem patha;
8. read-only verification API;
9. atomski build, rollback i eksplicitne retention/purge granice;
10. audit dokaz da snapshot nije upisan u corpus, evidence, training, calibration, consensus ili proposal bazu.

Dozvoljena acceptance oznaka je samo:

```text
013B_USER_INPUT_SNAPSHOT_ACCEPTED
```

## 3. Non-goals

WP-X10-013B ne implementira i njegov schema/API ne smije sadržati:

- calibration envelope, tolerance ili minimum/maximum delta;
- anomaly score, anomaly proof ili anomaly-positive status;
- candidate, proposal, target phase/tick, derived tick ili `delta_ticks`;
- local comparison, leave-one-target-out ili Factory distance odluku;
- simulation promjene, shadow graph, overlay ili before/after improvement;
- repair, apply, commit, reject, rollback stvarne promjene ili repair budget;
- MIDI writer, encoder, exporter ili output `.mid`/`.midi` artefakt;
- Factory/Gold fit, model update, evidence promotion ili training ingest;
- automatsko prepoznavanje da je USER_INPUT zapravo Factory/Gold dokaz;
- RX Noise, artikulacijski ili Pa800 evidence promotion;
- GUI odluku o targetu, preview ili certification;
- Delay/Terca analizu šest pjesama; ona ostaje u postojećoj, zasebnoj i strogo ograničenoj ruti.

013B ne mijenja QA-prihvaćene WP-012A/B/C/D ni WP-013A schema, digeste, authorization ili source authority pravila.

## 4. Authority separation contract

### 4.1 Zatvoreni authority domeni

```text
FACTORY_RAW          → Factory model/evidence autoritet po postojećim pravilima
GOLD_REFERENCE_RAW   → support/conflict autoritet po postojećim pravilima
HUMAN_VALIDATED_RAW  → samo eksplicitni Human Owner evidence
SYNTHETIC_TEST       → software test, nikad muzički dokaz
USER_INPUT_RAW       → objekt analize, nikad dokaz ili training
```

`USER_INPUT_RAW` je zaseban authority domen. Byte-identičnost sa nekim Factory/Gold fajlom ne mijenja njegovu klasu i ne daje mu corpus/evidence prava. Filename, korisnička oznaka, Bank/Program, track name, directory, postojeći corpus membership ili model sličnost ne smiju promovirati authority.

### 4.2 Neautoritativni origin

Direktan upload dokazuje samo:

- koji byte stream je platforma primila;
- kojem opaque session/upload locatoru pripada;
- kada je retention lifecycle započet kao nesemantička operativna činjenica.

Korisnička tvrdnja da je fajl originalan, Factory, Gold, nepopravljan ili ručno validiran nije trusted lineage dokaz. Snapshot se zato klasifikuje kao `USER_INPUT_RAW` sa `origin_trust=UNVERIFIED_USER_ORIGIN`.

### 4.3 Jednosmjerna zabrana promocije

Nijedan 013B red, subject, event, nota, hash, statistika ili izvedena vrijednost ne smije biti upisana ili korištena kao input u:

```text
factory.sqlite3
gold_dna.sqlite3
rhythm_validation.sqlite3 corpus quality
rhythm_calibration.sqlite3
rhythm_consensus.sqlite3
rhythm_context_qualified.sqlite3 Factory/reference observations
Evidence Registry claim/observation
model training/refit
negative corpus authority
Pa800 evidence promotion
```

Budući paket smije read-only porediti USER_INPUT sa prihvaćenim modelom, ali USER_INPUT nikada ne ulazi u fit, sufficient-source count, support arc, calibration distribution ili leave-one-out reference populaciju.

Svaki authority cross-write je hard fail i test blocker.

## 5. Šest-song i forbidden-source contract

Tačan skup šest SHA-256 vrijednosti iz prihvaćenog `SourceGuardPolicy` provjerava se nad originalnim upload bajtovima prije MIDI parsiranja i nezavisno od filenamea, ekstenzije ili preimenovanja.

Ako SHA pripada tom skupu, generalni 013B/X10 rezultat je:

```text
classification = EXCLUDED_SIX_SONG_GENERAL_X10
general_x10_allowed = false
allowed_external_route = DELAY_TERCA_RELATIONSHIP_ONLY
subject_graph_status = NOT_CREATED
```

Takav fajl se ne parsira za generalni X10 subject graf, ne ulazi u calibration/anomaly/proposal i ne dobija USER_INPUT analyze-ready snapshot. Minimalni exclusion receipt smije čuvati samo contract/policy digest, opaque upload/session locator, SHA, byte count, reason i retention status.

Postojeća Delay/Terca ruta ostaje van ovog paketa. 013B joj ne prosljeđuje događaje automatski i ne reinterpretira njene rezultate.

Poznati optimizer/repaired output SHA ili trusted forbidden lineage, ako su platformi dostupni kroz prihvaćeni guard registry, daju `EXCLUDED_FORBIDDEN_SOURCE`. Odsustvo provjerljivog lineagea se ne predstavlja kao clean lineage: dozvoljen direktni upload ostaje `UNVERIFIED_USER_ORIGIN`.

## 6. Input i byte-identity contract

### 6.1 Prihvat inputa

Builder prima sealed platform upload handle ili byte-stream capability. Ne prima proizvoljni korisnički filesystem path, URL, archive member path ili mutable parser object.

Prije parsiranja mora:

1. sekvencijalno pročitati originalni stream u privatni temp artifact;
2. izračunati SHA-256 i byte count tokom istog prolaza;
3. završiti i zatvoriti temp artifact;
4. ponovo izračunati SHA-256 iz temp artifacta;
5. zahtijevati byte-for-byte hash i veličinsku jednakost;
6. tek onda izvršiti source guard i eventualni parse.

Nema normalizacije headera, EOT-a, running statusa, texta, SysExa ili ekstenzije. Identitet je identitet originalnih uploadovanih bajtova.

### 6.2 Byte identity

```text
artifact_content_id = SHA256([
  "X10_USER_INPUT_CONTENT_V1",
  raw_byte_sha256,
  raw_byte_count
])
```

Content ID ne daje authority i nije globalni existence oracle. API ne smije potvrditi drugom session/owneru da isti hash već postoji. Cross-session dedup nije dio 013B ugovora.

Prije i poslije parsiranja, prije atomic replacea i pri svakom `verify` pozivu ponovo se provjeravaju raw SHA i byte count. Mismatch abortuje build ili označava snapshot neupotrebljivim bez pokušaja popravke.

## 7. Upload/session locator i privacy contract

Semantički locator sadrži samo:

```text
owner_scope_id
session_locator_id
upload_locator_id
```

Sva tri su opaque, ne-prazna i validirana platform identifiers. Ne sadrže username, email, originalni filename, apsolutni path, host path, temp path, URL, IP adresu ili filesystem inode.

Dozvoljeni operativni locator je relativan, npr. content-store key pod session scopeom. On nije dio javnog payload-a i ne smije počinjati `/`, sadržati drive prefix, `..`, URI scheme ili symlink-resolved host path.

Originalni display filename je opcionalni nesemantički privatni metadata zapis. Default je ne čuvati ga. Ako ga Human Owner omogući, mora biti basename-only, sanitizovan, access-controlled i izostavljen iz digesta, logova i standardnog API odgovora.

MIDI text/meta i SysEx payload mogu sadržati privatne podatke. Zato:

- raw sadržaj ostaje samo u access-controlled content artifactu;
- semantic DB ne čuva puni text, lyric, copyright, marker, cue ili SysEx payload;
- graph smije čuvati event kind, length i payload SHA-256 kada je potreban identitet;
- API ne vraća raw payload po defaultu;
- exception/log ne smije sadržati raw bytes, MIDI text, originalni filename ili host path;
- 013B nema mrežni export niti telemetry sadržaja.

Hash se tretira kao osjetljiv locator i vraća se samo autorizovanom owner/session scopeu.

## 8. Canonical parse contract

### 8.1 Parser granica

Dozvoljen snapshot se parsira tačno jednom iz verificiranog immutable artifacta. Parser/config/version digest je obavezan. Callback ne dobija mutable stream, filesystem path niti mogućnost ponovnog parsiranja.

Declared valid MIDI mora proći postojeću semantičku parser validaciju. Parse failure ne proizvodi djelimični subject graf. Rezultat je exclusion/failure receipt `INVALID_OR_UNSUPPORTED_MIDI`, a prethodni accepted snapshot ostaje netaknut.

### 8.2 Kanonski event identitet

USER_INPUT koristi odvojeni contract version `X10_USER_INPUT_SUBJECT_V1`; subject ID se ne dijeli sa Factory/Gold registryjem.

EVENT natural key mora sadržati samo parse-derived kanonske vrijednosti:

```text
authority_domain = USER_INPUT
format_track_index
track_event_ordinal
absolute_tick
event_kind
channel_or_null
status_or_meta_type
canonical_data_digest
```

`track_event_ordinal` dolazi iz stvarnog parsiranog reda događaja u tracku. Runtime object ID, float sort instability, filename i path su zabranjeni. `canonical_data_digest` pokriva puni event semantic payload bez izlaganja privatnog raw text/SysEx sadržaja.

### 8.3 NOTE i graph identitet

NOTE natural key sadrži authority domen, stable on-event ID, stable off-event ID ili eksplicitni unmatched status, channel i pitch. Note pairing koristi versioned deterministic pairing contract; ambiguous/unmatched slučaj se ne popravlja.

Obavezni minimalni subjecti:

```text
EVENT
NOTE
TRACK_CHANNEL
```

Obavezne minimalne veze:

```text
TRACK_CHANNEL_CONTAINS_EVENT
TRACK_CHANNEL_CONTAINS_NOTE
NOTE_HAS_ON_EVENT
NOTE_HAS_OFF_EVENT  # samo kada je dokaziv
```

`PROGRAM_SEGMENT`, `BAR`, `ONSET_CLUSTER`, `BOUNDARY` i `EXACT_CONTEXT` smiju se materijalizovati samo iz prihvaćenih RAW-derived exact ugovora. Default, conflict ili unspecified kontekst ostaje eksplicitno unproven; ne izmišlja se exact subject.

Subject graph digest pokriva contract/parser/config version, authority domen, sve natural keys, semantic payload digeste i sve edgeove. Kontradiktorni natural key, cross-source edge, cross-authority edge, ciklus gdje je zabranjen ili nedostajući parent je hard fail.

### 8.4 Snapshot natural key

```text
snapshot_id = SHA256([
  "X10_USER_INPUT_SNAPSHOT_V1",
  owner_scope_id,
  session_locator_id,
  upload_locator_id,
  raw_byte_sha256,
  parser_config_sha256,
  subject_graph_sha256
])
```

Isti frozen ingest manifest i isti bajtovi daju isti snapshot ID i semantic digest. Drugi upload/session dobija zaseban snapshot instance čak i kada su bajtovi jednaki.

## 9. Source classification contract

Zatvoreni terminalni ingest statusi su:

```text
SNAPSHOT_ACCEPTED_USER_INPUT
EXCLUDED_SIX_SONG_GENERAL_X10
EXCLUDED_FORBIDDEN_SOURCE
INVALID_OR_UNSUPPORTED_MIDI
BYTE_IDENTITY_FAILED
PRIVACY_POLICY_REJECTED
BUILD_FAILED_ATOMIC_ROLLBACK
```

Samo `SNAPSHOT_ACCEPTED_USER_INPUT` ima subject graf i read-only analysis handoff capability. I tada važi:

```text
source_class = USER_INPUT_RAW
origin_trust = UNVERIFIED_USER_ORIGIN
evidence_authority = NONE
model_authority = NONE
training_eligibility = NEVER
capability = ANALYZE_ONLY
mutation_capability = NONE
```

Unknown status ili kontradiktorna kombinacija je hard fail.

## 10. Storage contract

013B koristi zaseban storage boundary, preporučeno jedan atomic snapshot paket po uploadu:

```text
private immutable raw artifact
user_input_snapshot.sqlite3
optional nonsemantic lifecycle metadata
```

Minimalne semantic tabele:

- `snapshot_runs`: contract/schema/parser/config, terminal status i capability;
- `user_input_artifacts`: raw SHA/count, content ID i authority status;
- `user_input_origins`: opaque owner/session/upload locator i origin trust;
- `user_input_source_classification`: guard policy, exclusion/acceptance status i reason;
- `user_input_parse_manifests`: format/division/track/event counts i parser digest;
- `user_input_subjects` i `user_input_subject_edges`;
- `snapshot_authority_policy`: explicit no-evidence/no-training assertions i policy digest;
- `snapshot_semantic_digest`.

Raw artifact bytes, host path, display filename, timestamp i performance metrike nisu semantic DB payload.

Sve semantic tabele su insert-only u temp buildu. Accepted snapshot nema update/delete API, trigger ili background enrichment. FK, CHECK, natural-key uniqueness, integrity i canonical digest moraju proći prije atomic publisha.

Content artifact i SQLite snapshot postaju vidljivi kao jedna commit jedinica preko staged directory/package renamea ili ekvivalentne platform atomic publish primitive. Greška uklanja temp paket i čuva prethodni accepted paket byte-identično.

## 11. Immutability i read-only API contract

Dozvoljeni API surface:

```text
create_user_input_snapshot(sealed_upload_handle, opaque_locator, policy)
get_user_input_snapshot_manifest(snapshot_id)
list_user_input_subjects(snapshot_id, page_token)
get_user_input_subject(snapshot_id, subject_id)
verify_user_input_snapshot(snapshot_id)
request_user_input_snapshot_purge(snapshot_id)
```

Read API otvara SQLite sa `mode=ro`/`query_only` gdje platforma dopušta i provjerava owner/session authorization prije hash/subject odgovora.

Nema:

```text
update_snapshot
patch_subject
promote_to_evidence
add_to_training
reclassify_as_factory
calculate_calibration
score_anomaly
create_candidate
simulate_change
write_midi
export_midi
```

Javni payload ne vraća apsolutne pathove, raw artifact key, raw text/SysEx, filename po defaultu, model/evidence claim niti target/proposal polje.

## 12. Retention i deletion contract

Immutability važi tokom cijelog životnog vijeka snapshot paketa. Retention istek ili korisnički zahtjev ne mijenja redove prihvaćenog SQLite snapshota.

Lifecycle controller izvan semantic snapshota radi:

1. owner/session authorization;
2. provjeru da nema aktivnog analyze leasea;
3. označavanje paketa `PURGE_REQUESTED` u odvojenom operativnom registru;
4. uklanjanje cijelog raw + SQLite paketa, bez djelimičnog brisanja;
5. uklanjanje svih cache/spool kopija pod istim snapshot ID-em;
6. minimalni purge receipt prema Human Owner privacy politici.

Purge receipt ne smije zadržati MIDI sadržaj, subject graf, filename ili host path. Da li smije zadržati salted/audit snapshot ID i koliko dugo je Human Owner odluka. 013B ne obećava kriptografski secure erase izvan garancija filesystem/platforme; to ograničenje mora biti dokumentovano.

Snapshot bez definisane retention policy verzije ne može biti prihvaćen. Default treba biti najkraći operativno dovoljan retention, bez automatskog trajnog čuvanja.

## 13. Determinism i performance contract

- jedan upload stream copy/hash prolaz plus jedan independent verification hash;
- najviše jedan MIDI parse za accepted input;
- disk-backed spool; nema `list(all_events)` za cijeli corpus više uploadova;
- memory granica je jedan source plus aktivni graph batch;
- canonical track/event/subject/edge insert order;
- timestamp, temp path, process ID, SQLite rowid i performance metrike ne ulaze u semantic digest;
- dva builda istog frozen ingest manifesta daju isti subject graph i semantic digest;
- dozvoljena permutacija metadata map ordera ne mijenja digest;
- report odvojeno navodi byte count, parse count, event/note/edge counts, peak batch, spool/final bytes i semantic digest;
- `parse_count` je `0` za pre-parse exclusions i `1` za accepted snapshot.

## 14. Fail-closed contract

### Hard fail / atomic rollback

- upload handle nije sealed ili se bytes promijene tokom copy/verify;
- raw SHA/count mismatch;
- source guard/policy digest mismatch;
- poznati forbidden input pokušava dobiti accepted graph;
- parser/config version nije zaključan;
- drugi parse istog inputa u istom buildu;
- event/note identity ili pairing kontradikcija;
- cross-source/cross-authority subject edge;
- unknown enum, broken FK, digest ili SQLite integrity;
- apsolutni path, traversal, URI ili raw private payload u semantic/public polju;
- USER_INPUT upis u Factory/Gold/evidence/training/model/calibration storage;
- input/raw artifact/schema mutation;
- MIDI writer/encoder/export poziv ili output artefakt;
- partial publish ili nedeterministički semantic digest.

### Normalni excluded rezultat

- SHA pripada šest-song skupu;
- poznata forbidden source klasa;
- invalid/unsupported MIDI;
- privacy/retention policy nije prihvatljiv.

Excluded rezultat nije analyze-ready snapshot i ne smije se tiho pretvoriti u success.

## 15. Test contract

### Identity i parser

- exact raw-byte SHA/count prije i poslije copya/parsa;
- single-parse counter;
- deterministic event ordinal i subject/edge digest;
- running status, same-tick order, format 0/1, multi-track, tempo/meter changes;
- matched, overlapping same-pitch, unmatched i zero-velocity note-off slučajevi;
- SysEx/meta text privacy hashing bez plaintext API leakagea;
- invalid header, truncated event, SMPTE/unsupported division i parser exception rollback.

### Authority i contamination

- USER_INPUT nikad ne ulazi u Factory/Gold/reference observation ili fit;
- byte-identičan Factory fixture ostaje `USER_INPUT_RAW`;
- fake filename/source-class/metadata ne mijenja authority;
- attempted evidence/training promotion API ne postoji ili hard-failuje;
- synthetic fixture je označen test-only i ne može se predstaviti kao production snapshot.

### Six-song/forbidden guards

- svih šest tačnih SHA vrijednosti, uključujući preimenovane fajlove, daju pre-parse exclusion;
- njihov `parse_count=0` i subject graph ne postoji;
- Delay/Terca route label ne daje general X10 capability;
- optimizer/repaired known lineage/hash je excluded;
- missing lineage ne dobija `TRUSTED_CLEAN`, nego `UNVERIFIED_USER_ORIGIN`.

### Privacy i locator

- apsolutni POSIX/Windows path, URI, `..`, symlink escape i filename injection se odbijaju;
- log/exception/API nema raw text, SysEx, filename ili host path;
- owner/session isolation sprečava cross-session hash/existence disclosure;
- standard API ne vraća raw artifact key;
- metadata map order i display-name promjena ne mijenjaju semantic digest.

### Storage, determinism i purge

- temp SQLite/content package + atomic publish;
- injected failure u svakoj build fazi čuva prethodni accepted paket byte-identično;
- read-only/query-only verification i mutation pokušaji;
- FK/CHECK/natural-key contradiction/integrity testovi;
- dva builda i input-order permutacije daju isti digest;
- purge uklanja cijeli paket i cache/spool, nikad dio semantic grafa;
- aktivni lease blokira purge;
- retention expiry ne mijenja snapshot prije whole-package purgea;
- nijedan test ne proizvodi `.mid`/`.midi` output.

### Regression

- targeted WP-013B testovi;
- puni pytest sa warning-as-error;
- Python compile i `git diff --check`;
- accepted WP-012A/B/C/D i WP-013A digesti/schema/API ostaju nepromijenjeni.

## 16. Acceptance kriteriji

WP-X10-013B može dobiti tehnički `ACCEPT` samo ako:

1. capability je svuda `ANALYZE_ONLY`, mutation `NONE`;
2. accepted output je samo immutable USER_INPUT snapshot ili zatvoren excluded rezultat;
3. originalni bajtovi imaju dokazanu before/copy/after SHA i count jednakost;
4. accepted snapshot se parsira tačno jednom iz immutable artifacta;
5. canonical USER_INPUT subject graf je parse-derived, determinističan i authority-namespaced;
6. upload/session locator je opaque, owner-scoped i bez apsolutnog patha;
7. plaintext MIDI text/SysEx, filename i host path ne cure u semantic DB/log/public API;
8. USER_INPUT nikad nije Factory/Gold/Human evidence, model, calibration ili training input;
9. svih šest song SHA vrijednosti su pre-parse excluded za generalni X10, uz samo vanjsku Delay/Terca route oznaku;
10. missing origin lineage ostaje `UNVERIFIED_USER_ORIGIN`, ne trusted clean;
11. schema/API nema calibration, anomaly, candidate, target, delta, simulation promjene ili output MIDI;
12. storage je immutable, read-only, deterministic i atomic;
13. failure čuva prethodni accepted paket byte-identično;
14. retention policy je versioned, a deletion uklanja cijeli snapshot paket bez parcijalne mutacije;
15. SQL CHECK/FK/integrity, natural-key, privacy, authority i adversarial testovi prolaze;
16. targeted i puni pytest prolaze sa warning-as-error;
17. nezavisni QA daje `ACCEPT`, `RETURN` ili `BLOCK`, a `ACCEPT` nema otvoren critical/high nalaz.

Tehnički ACCEPT nije odobrenje za calibration, anomaly proof, proposal, MIDI promjenu, Pa800 evidence ili release.

## 17. Predloženo vlasništvo fajlova

Implementer, samo nakon Audit/Lead locka:

```text
rxoptimizer/rhythm_user_input_snapshot.py
tests/test_rhythm_user_input_snapshot.py
tests/fixtures/x10_user_input/  # samo sintetički/minimalni fixtures
```

Lead integration nakon QA:

```text
analysis/agent_work_packages.json
SESSION_CHECKPOINT.md
COMPLETION_REPORT.md
```

WP-012A/B/C/D, WP-013A, optimizer, Factory/Gold builderi i MIDI writer ostaju read-only/out-of-scope.

## 18. Human Owner odluke

Prije Lead implementation locka Human Owner mora potvrditi:

1. default retention trajanje za raw artifact i semantic snapshot;
2. da li je raw artifact potreban nakon uspješnog parsea ili se čuva samo do kraja buduće analyze sesije;
3. da li se display filename uopšte čuva; preporuka je `NE` po defaultu;
4. da li je cross-session dedup zabranjen; preporuka je `ZABRANJEN` radi privacy isolationa;
5. minimalni sadržaj i retention purge receipta;
6. platformsku garanciju atomic publish/purge i dokumentovanu granicu secure erasea;
7. maksimalnu veličinu upload MIDI-ja i session storage kvotu;
8. da Delay/Terca routing šest pjesama ostaje eksplicitna ručna/odvojena akcija, bez automatskog prosljeđivanja;
9. ko smije otvoriti raw artifact i da standardni X10 API ostaje manifest/subject-only;
10. da USER_INPUT nikada ne postaje training/evidence bez potpuno novog Human-approved work-packagea — preporuka je trajna zabrana.

Ove odluke ne smiju se pretpostaviti iz filenamea, postojećeg corpusa ili tehničkog QA ACCEPT-a.

## 19. Architect verdict

```text
ARCHITECT_READY
```