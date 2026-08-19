# WP-X10-013C — Independent Architecture Audit

Datum: 12. august 2026.  
Predmet: Schema-v2 Factory Calibration Envelope  
Pregledano: `WP-X10-013C_ARCHITECT.md`, prihvaćeni schema-v2/WP-012C kod u `rhythm_context.py`, `rhythm_context_join.py`, `rhythm_context_models.py`, `rhythm_multimodal.py` i `rhythm_reference_conflict.py`  
Audit uloga: ChatGPT Audit  
Status: `BLOCKED_PENDING_ARCHITECT_ADDENDUM`

## Sažetak

Scope je pravilno ograničen na Factory-only, immutable i `ANALYZE_ONLY` calibration opis. Architect je ispravno prepoznao da prihvaćeni WP-012D ključ nije upotrebljiv za calibration:

```text
event_slot_key = hash(exact_context_key, note_number, onset_phase)
```

Prihvaćeni `exact_context_key` dodatno uključuje `topology_sha256`, a postojeći topology sadrži onset intervale. Novi paralelni structural registry je zato obavezan; legacy ključevi smiju ostati samo provenance locatori.

Implementacija ipak ne smije početi prema verziji 1 ugovora. Jedna semantička kontradikcija i više nedovoljno definisanih identity/mathematical gateova omogućili bi različite, pojedinačno “usklađene” implementacije sa različitim rezultatima.

## Kritični blocker

### B1 — Reference istovremeno ne smije i smije mijenjati delta granicu

Sekcije 3 i 13 propisuju da Gold/reference:

- dolazi tek nakon immutable Factory envelopea;
- ne mijenja Factory support ili delta granice;
- ne utiče na Factory semantic digest.

Sekcija 11, međutim, dozvoljava `maximum_allowed_delta=AVAILABLE` samo ako reference nije contradiction/partial/deferred. Time reference mijenja availability iste granice i efektivno mijenja Factory calibration rezultat.

Obavezna korekcija:

1. Factory delta-bound vrijednost i Factory availability moraju se izračunati isključivo iz Factory/LOSO/protection podataka.
2. Reference status mora biti zaseban post-envelope overlay koji može dati review/block za budući paket, ali ne smije promijeniti Factory bound red, vrijednost, status ili digest.
3. Ako se želi reference-qualified izvedeni status, mora imati zasebnu tabelu/natural key i semantiku koja nije Factory calibration bound.

Dok se ovo ne razdvoji, storage i digest contract nisu jednoznačni.

## Obavezni identity i alignment gateovi

### B2 — `calibration_context_key` nema potpuno zatvoren canonical payload

Tekst navodi dimenzije, ali ne zaključava:

- closed role/instrument identity enum i tačno ponašanje za unknown/ambiguous identitet;
- tempo-regime funkciju, granice i version digest;
- section/style/CV normalization i dokaz da provenance locator nije dio identity vrijednosti;
- definiciju `track-channel structural role`;
- transposition/inversion politiku za voice topology;
- dozvoljenu listu structural tokena.

Addendum mora dati canonical JSON payload sa obaveznim poljima, closed enumima, normalization pravilima i primjerima positive/negative equivalence. Missing ili ambiguous vrijednost mora dati `STRUCTURAL_CONTEXT_UNPROVEN`, ne fallback grupu.

### B3 — Structural alignment digest može sakriti timing leakage

Zabrana naziva `phase/tick/IOI` nije dovoljna. Digest može indirektno commitovati legacy `exact_context_key`, `topology_sha256`, original `event_slot_key`, cluster tick ili membership digest koji uključuje fazu.

Potrebno je razdvojiti:

```text
identity_semantic_payload
provenance_membership_payload
```

Samo prvi smije učestvovati u `calibration_context_key` i `structural_event_slot_key`. Drugi se čuva i digestuje radi audita, ali ne utiče na identity. Validator mora rekonstruktivno provjeriti dozvoljeni field dependency, ne samo statički tražiti zabranjene riječi.

### B4 — Cluster/voice/pitch poravnanje nije algoritamski određeno

`onset_cluster_ordinal`, `canonical_voice_signature`, `pitch_or_drum_lane_identity` i `structural_alignment_digest` nemaju zaključan algoritam. Posebno nisu određeni:

- apsolutni pitch naspram transposition-normalized offseta;
- canonical anchor za akord i inversion;
- duplicate unison note, isti pitch u dva voicea i drum lane;
- akord sa različitim spellingom/voicingom;
- simultani chord naspram razloženog chord-a;
- cluster split/merge, crossing i insert/delete ornamental voice;
- više istih structural slotova u jednom source/bar instanceu.

Conservative v1 pravilo treba biti exact-only: cluster je skup stvarno simultanih NOTE_ON stable eventova; nema epsilon mergea. Jedinstveno bipartite/ordinal poravnanje mora imati tačno jedan dokaziv mapping. Svaki tie, split/merge, crossing, duplicate signature ili cardinality mismatch daje ambiguity i nula calibration observations za taj stratum.

### B5 — Cross-file grouping mora dokazati source identity i lineage prije registryja

Svaki structural context/slot membership mora zadržati schema-v2 trusted lineage provjeru: Factory RAW root, puni ancestor closure, source class, manifest/digest parity, zabranu šest song SHA vrijednosti, optimizer/repaired/unknown i cross-authority ancestry. Synthetic fixtures ne smiju dobiti production Factory status.

Cross-file key collision nije dovoljan dokaz članstva. Potrebni su source-local recomputation record, source/bar/note/cluster stable-subject FK i many-to-one membership digest. Jedan `(source_sha, bar_id, structural_slot_key)` smije imati najviše jednu resolved observation; inače ambiguity.

## Model i component provenance gateovi

### B6 — “Reproduce 012C pa refituj” traži novi verified snapshot ugovor

Postojeći WP-012C `assess_multimodal` zahtijeva jedan legacy `exact_context_key` i jedan phase-bearing `event_slot_key`. Njegov stored component se zato ne može direktno koristiti za novi cross-variation structural universe.

Addendum mora zaključati dva odvojena dokaza:

1. byte-for-byte reprodukciju prihvaćenog 012C snapshot/modela kao input-integrity dokaz;
2. novi Factory-only structural-slot refit snapshot sa svojim observation-universe, config i semantic digestom.

Novi refit smije ponovo koristiti isti zaključani numerical model algorithm, ali njegov component ID nije legacy component ID. Potreban je zaseban structural model/component natural key i potpuna hard-membership provenance. Cross-component membership, posterior tie, missing assignment ili nepotpuno pokriće mora blokirati envelope.

### B7 — LOSO component matching cost nije definisan

“Directed matching cost” i “strict interval winner” nisu dovoljni za reproduktivan rezultat. Mora se zaključati cost vector/formula, Decimal/rational enclosure, assignment algoritam, tie pravilo i poređenje component counta. Mean-only matching nije dovoljno jer bliske komponente mogu zamijeniti scale/support/membership strukturu.

Preporučeni minimum je versioned lexicographic ili certified composite cost nad circular mean distance, scale interval, support relationship i source-balanced hard-membership summary. Bez jedinstvenog strict winnera fold je unstable.

## Circular support i robust-statistics gateovi

### B8 — “Point support arc” mora razlikovati point set, union i enclosing arc

Najkraći enclosing circular arc može prikriti velike praznine i disconnected support. Za svaki envelope treba posebno čuvati:

- exact observed phase multiset/set;
- union per-observation resolution arcs;
- connected components te unije;
- optional unique shortest enclosing arc.

Jednaki largest-gap kandidati, antipodal/polukružni slučaj, radius `>= 1/2`, full-circle coverage ili više connected segmenata moraju dati non-unique/review. Canonical split na nuli mora biti jednoznačan. Linearni min/max preko wrapa je zabranjen.

### B9 — Source balancing i quantile tie pravila moraju biti potpuno versioned

Equal-source masa je dobar zahtjev, ali addendum mora zaključati:

- deduplikaciju observationa i `(source, bar, slot)` uniqueness;
- exact mass `1/S` i raspodjelu unutar sourcea;
- effective sample size formulu;
- medoid tie ponašanje;
- weighted quantile left/right-closed semantiku;
- interval rezultat kod cumulative tiea;
- MAD centar i IQR subtraction enclosure.

Dominant-source share mora biti iz source-balanced ili jasno imenovanog bar-count prostora; postojeći WP-012C kod koristi bar share za dominance, pa se taj izbor mora eksplicitno zaključati umjesto implicitnog nasljeđivanja.

### B10 — Exact repeat nije zero uncertainty

`CALIBRATION_DEGENERATE_EXACT` smije imati point variation nula, ali measurement uncertainty mora ostati union stvarnih half-tick resolution lukova. `minimum_meaningful_delta` ne smije biti nula. Coarse PPQ mora proizvesti širu resolution uncertainty, ne lažnu preciznost.

## Delta-bound gateovi

### B11 — Formule za minimum i maximum još nisu implementabilni ugovor

Pojmovi “combined uncertainty”, “conservative upper envelope”, “boundary support sufficient” i “stability interval” nemaju tačne formule/pragove. Različite implementacije mogu dati različite available vrijednosti.

Do Architect addenduma oba bounda moraju biti obavezno:

```text
status = UNAVAILABLE
value = NULL
authorizes_change = false
```

Alternativno, addendum mora dati exact versioned formule, quantile nivoe, source-boundary minimum, full/LOSO intersection operaciju i interval overlap pravilo. `maximum_allowed` ostaje opisni historical naziv; nikad nije dozvola translacije.

## Protection i authority gateovi

### B12 — `LOCAL_REPEATED_PATTERN` nema odobrenu positive calibration semantiku

Tekst uslovno dopušta odvojeni stratum “ako Architect/Audit potvrde”. Ovaj audit ne potvrđuje automatsko uključivanje. Za WP-013C v1 `LOCAL_REPEATED_PATTERN=DETECTED/AMBIGUOUS` treba očuvati kao separate review/preserve stratum ili blokirati generic envelope. Ne smije povećati sufficiency niti postati target evidence.

Svi ostali core adapteri moraju imati complete resolved coverage nad tačnim observation universeom. `CLEAR` je odsustvo tog bloka, ne positive authorization.

### B13 — Reference mora ostati odvojena masa i post-envelope procjena

Gold/reference:

- ne ulazi u structural Factory model fit, robust stats, LOSO ili sufficiency;
- ne spašava insufficient Factory;
- koristi isti phase-independent structural join samo uz vlastiti trusted lineage;
- ne mijenja Factory envelope/delta digest;
- može samo proizvesti odvojeni support/conflict/review zapis.

USER_INPUT, USER_INPUT subject/phase, anomaly score, leave-one-target-out, target i proposal nisu dozvoljeni ni kao optional callback/config payload.

## Required acceptance tests prije QA

Pored Architect liste, obavezni su:

1. dvije Factory izvedbe sa različitim onset fazama/IOI dobijaju isti structural slot, dok identity payload byte-for-byte ne sadrži legacy timing-bearing digest;
2. različit pitch/voice structure ne kolidira, a transposition politika ima eksplicitne positive/negative fixtures;
3. simultaneous chord i arpeggiated/split chord ne spajaju se fallback tolerancijom;
4. duplicate voice/unison i crossing daju ambiguity;
5. isti structural hash iz netrusted ili drugog authority izvora ne daje membership;
6. structural refit snapshot ne prihvata forged legacy component membership;
7. exact repeats sa različitim PPQ imaju nultu point disperziju, ali nenultu resolution uncertainty;
8. wrap, antipodal, equal-largest-gap, disconnected-union i full-circle support slučajevi;
9. jedan veliki source ne dominira tri mala i duplicate bar ne povećava masu;
10. LOSO unique/non-unique component mapping i fold split/merge;
11. Reference permutacija/odsustvo/kontradikcija ne mijenja Factory envelope ili Factory bound digest;
12. oba delta bounda su NULL dok njihove formule nisu version-lockovane;
13. static + dynamic dependency test odbija phase/tick/IOI skriven kroz nested token ili digest;
14. database/API scan potvrđuje nula USER_INPUT, anomaly, target, proposal, simulation, MIDI writer/output površina.

## Zavisnosti i dozvoljeni redoslijed

```text
Architect addendum za B1–B12
→ Audit re-review
→ 013C-S structural registry implementacija
→ nezavisni QA za 013C-S
→ Factory structural refit + envelope
→ LOSO/support/statistics
→ optional post-envelope reference assessment
→ storage/API verification
→ nezavisni finalni QA
```

Envelope implementacija ne smije preteći prihvaćeni structural registry. Proposal/anomaly/USER_INPUT comparison ostaju izvan paketa.

## Audit verdict

```text
BLOCKED
```

Razlog nije širina cilja nego nedovoljno zaključana semantika i kontradikcija B1. Nakon kratkog Architect addenduma koji razriješi B1–B12, paket se može vratiti na `AUDIT_REVIEWED` bez promjene osnovnog Factory-only smjera.