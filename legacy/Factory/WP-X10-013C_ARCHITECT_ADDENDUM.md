# WP-X10-013C — Architect Addendum

Datum: 12. august 2026.  
Verzija: 2  
Capability: `ANALYZE_ONLY`  
Mutation capability: `NONE`  
Status: `ARCHITECT_READY`

## 1. Svrha i precedence

Ovaj dodatak zatvara nalaze `WP-X10-013C_AUDIT.md`. Kada postoji razlika, ovaj dokument ima precedence nad verzijom 1 Architect ugovora.

WP-X10-013C ostaje strogo Factory calibration paket. Ne procjenjuje USER_INPUT, anomaliju, candidate ili target i ne proizvodi simulation/MIDI output.

## 2. Razdvajanje Factory envelopea i reference overlaya

Factory rezultat je završen prije čitanja reference observationa:

```text
Factory structural registry
→ Factory structural refit
→ Factory envelope + LOSO + Factory bound rows
→ freeze Factory semantic digest
→ optional reference overlay
```

Reference ne smije promijeniti Factory envelope red, status, sufficiency, bound red, vrijednost ili digest.

Factory delta redovi u v1 su obavezno:

```text
minimum_meaningful_delta_status = UNAVAILABLE_FORMULA_NOT_CONTRACTED
minimum_meaningful_delta_value = NULL
maximum_allowed_delta_status = UNAVAILABLE_FORMULA_NOT_CONTRACTED
maximum_allowed_delta_value = NULL
authorizes_change = false
```

Reference overlay ima zaseban natural key:

```text
[reference_overlay_contract_version, factory_envelope_digest,
 reference_universe_digest, reference_config_digest]
```

Dozvoljeni overlay statusi su `NO_REFERENCE`, `INSUFFICIENT_REFERENCE`, `SUPPORT`, `PARTIAL_SUPPORT`, `CONFLICT` i `REVIEW`. Overlay može samo preporučiti da naredni paket withheld/review-a Factory envelope. Ne mijenja Factory availability.

## 3. Canonical phase-independent calibration context

### 3.1 Closed identity domeni

`calibration_context_key` se računa iz canonical ASCII JSON payload-a:

```json
{
  "contract": "X10_CALIBRATION_CONTEXT_V1",
  "role": "<closed role token>",
  "instrument": {"bank_msb": 0, "bank_lsb": 0, "program": 0,
                  "identity_key": "<canonical instrument identity>"},
  "style": {"name_key": "<NFKC/casefold/space-normalized>",
             "section": "<closed section token>", "section_no": 0,
             "cv_status": "NONE|EXACT", "cv": null},
  "meter": {"numerator": 4, "denominator": 4},
  "tempo_regime": {"contract": "X10_TEMPO_REGIME_V1", "lower_inclusive": 120,
                   "upper_exclusive": 130},
  "track_channel_role": "<closed structural role>",
  "bar_structure": {"cluster_cardinalities": [1, 3],
                    "voice_signatures": [[0], [0, 4, 7]]},
  "config_sha256": "..."
}
```

Closed role/track-role tokeni dolaze iz versioned registryja derived iz prihvaćenih role modela; unknown, conflicting ili alias-necanonical vrijednost daje `STRUCTURAL_CONTEXT_UNPROVEN`. Section tokeni su `INTRO`, `VARIATION`, `FILL`, `BREAK`, `ENDING`, `OTHER_EXACT`. Missing section number za numerisanu sekciju je unproven. CV je ili exact integer ili `NONE`; unknown nije fallback.

Style name koristi Unicode NFKC, casefold, trim i collapse ASCII/Unicode whitespace. Locator/method/provenance nije dio identity payload-a, ali se obavezno čuva u zasebnom provenance payload-u.

Tempo regime je deterministički integer BPM floor-bucket širine 10 BPM, izveden exact rational formulom iz `microseconds_per_quarter`:

```text
bpm = 60_000_000 / microseconds_per_quarter
bucket_lower = 10 * floor(bpm / 10)
bucket_upper = bucket_lower + 10
```

Poređenje i floor se rade exact rational aritmetikom. Tempo <= 0, missing ili boundary koji nije exact daje unproven. Config zaključava širinu i formulu.

### 3.2 Transposition i voice policy

V1 dozvoljava transposition equivalence, ali ne inversion equivalence. Za svaki simultaneous onset cluster:

- `anchor_pitch` je najniži pitch za melodic/non-drum role;
- voice signature je sortirani multiset `pitch-anchor_pitch`;
- duplicate/unison offset je dozvoljen u payload-u, ali dvije iste note koje se ne mogu jedinstveno vezati za stable NOTE subject daju ambiguity pri slot mappingu;
- inversion mijenja offset multiset i zato ne kolidira;
- drum signature koristi exact drum note/lane, bez transpositiona;
- različit cluster cardinality, voice offset multiset ili drum lane ne kolidira.

Duration, velocity, onset tick, phase, IOI i accent nisu structural identity tokeni.

## 4. Structural slot algorithm

V1 cluster je exact skup NOTE_ON stable eventova sa identičnim integer tickom u jednom source/bar/track/channelu. Nema epsilon mergea.

Bar clusteri se poredaju po stvarnom event orderu samo radi source-local ordinala. Cross-file structural alignment koristi sequence alignment nad isključivo cluster cardinality + canonical voice signature tokenima. Dozvoljen je samo exact sequence identity sa istim brojem cluster tokena; insert/delete, split/merge, arpeggiated naspram simultaneous chord-a ili različit token daje `STRUCTURAL_ALIGNMENT_AMBIGUOUS` i nula observations za cijeli stratum.

`structural_event_slot_key` payload je:

```json
{
  "contract": "X10_STRUCTURAL_SLOT_V1",
  "calibration_context_key": "...",
  "cluster_ordinal": 0,
  "cluster_cardinality": 3,
  "voice_signature": [0, 4, 7],
  "voice_ordinal": 1,
  "voice_offset_or_drum_lane": 4,
  "identity_config_sha256": "..."
}
```

Za chord note `voice_ordinal` je ordinal u sorted `(pitch, stable_note_natural_key_without_timing)` skupu. Ako duplicate pitch/unison ne daje unique order bez timing-bearing/event-ID tie-breaka, cijeli duplicate subset je ambiguous. Voice crossing između structurally compared instances, cardinality mismatch ili više resolved observations za `(source_sha, bar_subject_id, structural_event_slot_key)` daje ambiguity.

### Identity/provenance separation

Identity payload smije zavisiti samo od allowlisted semantic fields gore. Zaseban provenance payload čuva originalne schema-v2 context/event-slot, stable NOTE/EVENT/CLUSTER/BAR FK, source SHA i membership digest. Legacy `exact_context_key`, `topology_sha256`, `event_slot_key`, tick/phase/IOI ili digest koji ih commit-tuje nikada ne ulazi u identity payload.

Validator rekonstruiše identity direktno iz allowlisted primitive fields. Ne prihvata caller-supplied nested digest kao identity input. Dependency tracing test mijenja svaki forbidden primitive i dokazuje da identity ostaje isti, te mijenja svaki identity primitive i dokazuje očekivanu promjenu.

## 5. Source membership i lineage

Prije structural registryja svaki source ponovo prolazi accepted schema-v2 trusted-lineage validator:

- root SHA/class i source manifest parity;
- puni ancestor closure i lineage matrix;
- `FACTORY_RAW`, quality `NORMAL`;
- zabrana šest song SHA vrijednosti, optimizer/repaired/unknown i cross-authority ancestry;
- canonical registry/subject/edge digest parity.

Svako membership mapiranje ima source-local recomputation red i FK na source, bar, onset cluster, NOTE i NOTE_ON EVENT. Cross-file key collision nije membership dokaz. Synthetic fixture ima `SYNTHETIC_GUARD_FIXTURE` authority i nikad production Factory sufficiency.

Jedan `(source_sha, bar_subject_id, structural_event_slot_key)` smije imati tačno jedan resolved observation. Zero ili multiple je ambiguity, ne deduplikacija.

## 6. Novi structural refit snapshot

Dva dokaza su odvojena:

1. `legacy_input_integrity`: byte-for-byte reprodukcija accepted WP-012C snapshot/modela iz njegovog originalnog universea;
2. `structural_factory_assessment`: novi Factory-only model refit nad phase-independent structural-slot universeom.

Structural assessment ponovo koristi neizmijenjen numerical algoritam i config iz WP-012C, ali ima nove natural keys:

```text
structural_model_id = hash(model_contract, calibration_context_key,
                           structural_event_slot_key,
                           structural_observation_universe_digest, config_digest)
structural_component_id = hash(structural_model_id, canonical_component_payload)
```

Snapshot čuva kompletan observation universe, hard memberships, posterior assignment, source/bar sets, config i semantic digest. Legacy component ID nije structural component ID i ne daje membership autoritet.

Svaki observation mora imati tačno jednu hard assignment za available model. Posterior tie, missing/duplicate assignment, cross-component membership, component collapse ili incomplete observation coverage blokira envelope.

## 7. Versioned LOSO component matching

LOSO refituje structural model nakon izostavljanja jednog Factory sourcea. Fold component count mora biti jednak full component countu; split/merge odmah daje unstable.

Za svaki full/fold component par računa se certified lexicographic cost vector:

```text
(
  circular_mean_distance_interval,
  absolute_scale_difference_interval,
  support_symmetric_difference_mass_interval,
  source_balanced_membership_profile_distance_interval
)
```

- mean distance je circular rational pretvoren u outward Decimal interval;
- scale difference koristi stored certified Decimal interval;
- support difference je source-balanced masa exact phase pointova prisutnih samo u jednom supportu;
- membership profile distance poredi sorted phase→exact-mass mape, missing phase masa je 0.

Assignment koristi exhaustive permutation za zaključani mali `k` domen WP-012C. Jedan permutation je pobjednik samo ako je na prvom različitom lexicographic elementu njegov upper endpoint strogo manji od lower endpointa svakog konkurenta. Interval overlap, potpuno jednak vector ili više pobjednika znači `LOSO_COMPONENT_MATCH_AMBIGUOUS`. Nema ID/ordinal tie-breaka.

Cost formula/config ima version/digest i ulazi u fold/envelope digest.

## 8. Circular support contract

Envelope zasebno čuva:

1. exact observed phase multiset i set;
2. per-observation closed resolution arcs;
3. canonical union tih arcs i njegove connected components;
4. optional unique shortest enclosing arc exact point seta;
5. optional unique shortest enclosing arc resolution uniona.

Arcs se normalizuju u `[0,1)` kao sorted non-overlapping half-open segmenti plus explicit closed-endpoint metadata. Wrap arc se canonical dijeli na `[0,u]` i `[l,1)`. Touching closed arcs se spajaju; pravi gap ostaje gap.

Unique shortest enclosing arc dobija se komplementom jedinstvenog najvećeg exact circular gap-a. Dva jednaka najveća gap-a, antipodal set, polukružna nejedinstvenost ili multiple candidates daje `ENCLOSING_ARC_NON_UNIQUE`. Resolution radius `>=1/2` ili union bez gap-a daje `FULL_CIRCLE_COVERAGE`. Više union connected components ostaje `DISCONNECTED_SUPPORT`; enclosing arc ga ne smije sakriti.

Linearni min/max preko wrapa je zabranjen.

## 9. Exact source-balanced statistics

### Deduplikacija i masa

Observation natural key je `(source_sha, bar_subject_id, structural_event_slot_key)`. Duplicate key sa istim sadržajem je contract duplicate i ne ulazi dvaput; različit sadržaj je hard contradiction.

Za `S` sourcea, svaki source ima exact masu `1/S`. Ako source ima `n_s` unique observations, svaka ima masu `1/(S*n_s)`. Total je exact 1.

Effective sample size je:

```text
n_eff = 1 / sum_i(w_i^2)
```

kao exact Fraction, uz Decimal prikaz samo outward/enclosed.

### Medoid i quantile

Circular medoid kandidati su samo observed phases. Cost je exact weighted zbir circular distance. Jedinstveni minimum je medoid; tie daje `ROBUST_CENTER_NON_UNIQUE` i blokira center-dependent stats/bounds. Nema smallest-phase tie-breaka.

Za sorted exact values `x_i` sa massom `w_i`, weighted quantile `Q(p)` koristi left-continuous inverse CDF: prvi `x_i` gdje cumulative mass `>= p`. Ako cumulative mass tačno jednaka `p` i sljedeća vrijednost postoji, semantic rezultat je closed interval `[x_i,x_{i+1}]`, ne interpolirana tačka. Q1/P05/P50/P95/Q3 koriste exact p Fraction.

MAD se računa nad exact circular distances od unique medoid-a istim quantile pravilom. IQR je outward interval subtraction `Q3 - Q1`; ako quantile ima interval, sve endpoint kombinacije se konzervativno obuhvataju.

Dominant-source share ima dvije odvojene metrike:

- `source_balanced_mass_share`, koja je uvijek `1/S` po sourceu;
- `raw_bar_share = source_unique_bar_count / total_unique_bar_count`, korišten za postojeći WP-012C dominance/sufficiency prag.

Ne smiju se zamijeniti ili zajedno nazvati `dominant_source_share` bez prostora mjere.

## 10. Exact repeat i resolution uncertainty

Ako exact point set ima jednu fazu i point MAD/IQR su nula, status je `CALIBRATION_DEGENERATE_EXACT_RESOLUTION_ONLY`.

Resolution union se i dalje računa iz stvarnih per-observation half-tick arcs. Coarse PPQ daje širi uncertainty. Point uncertainty nije measurement uncertainty. Nijedan delta bound nije nula niti available u v1.

## 11. Delta bounds v1

Audit nije prihvatio formule. Zato oba historical bounda u svakom envelopeu imaju obavezni NULL contract iz sekcije 2. Nema config opcije, callbacka ili synthetic bypassa koji ih može učiniti available.

Schema CHECK zahtijeva:

```text
status LIKE 'UNAVAILABLE_%'
value_numerator IS NULL
value_denominator IS NULL
value_decimal_lower IS NULL
value_decimal_upper IS NULL
authorizes_change = 0
```

Buduci formula paket mora imati novi contract/version i novi Architect/Audit/QA; ne smije retroaktivno ažurirati accepted 013C redove.

## 12. Protection i LOCAL_REPEATED_PATTERN

Za generic envelope svi core adapteri moraju imati complete resolved coverage nad tačnim structural observation universeom. Detected, ambiguous, partial, deferred, dependency gap ili evidence-unjoinable observation ne ulazi u generic envelope.

`LOCAL_REPEATED_PATTERN=DETECTED` ili `AMBIGUOUS` u v1 ide samo u `LOCAL_REPEAT_REVIEW_STRATUM`. Taj stratum:

- ne povećava generic Factory source/bar sufficiency;
- ne ulazi u Factory generic robust stats ili LOSO;
- ne stvara delta bound;
- ne postaje target/local-comparison evidence;
- čuva preserve/review provenance za budući odvojeni ugovor.

`CLEAR` znači samo odsustvo tog bloka.

## 13. Storage dopune

Factory semantic tabele i reference overlay tabele imaju odvojene digest rootove:

```text
factory_calibration_semantic_digest
reference_overlay_semantic_digest
```

Factory root ne uključuje reference redove ni reference config. Reference root commit-tuje frozen Factory root kao input.

Obavezne dodatne tabele:

- `structural_context_registry`;
- `structural_slot_registry`;
- `structural_slot_memberships`;
- `structural_factory_models`;
- `structural_factory_components`;
- `structural_component_memberships`;
- `factory_calibration_envelopes`;
- `factory_phase_point_support`;
- `factory_resolution_arc_union`;
- `factory_loso_folds`;
- `factory_delta_bounds` sa enforced NULL v1;
- `local_repeat_review_strata`;
- `reference_calibration_overlays`.

Identity semantic JSON i provenance membership JSON su zasebne kolone/digesti. FK vežu svaki membership za originalni source/bar/cluster/note/event stable subject.

## 14. Obavezni testovi

Pored verzije 1, acceptance zahtijeva:

1. Različite onset faze/IOI sa istom dozvoljenom structural semantikom daju isti structural slot, dok identity JSON nema legacy timing-bearing digest.
2. Nested/caller digest koji commit-tuje phase/tick/IOI se odbija; identity se rekonstruiše iz primitive allowliste.
3. Explicitne transposition-positive i inversion/voice-structure-negative fixture.
4. Simultaneous chord i arpeggiated/split chord se ne spajaju.
5. Duplicate unison, crossing, cluster insert/delete/split/merge daju ambiguity.
6. Isti structural hash iz netrusted/drugog authority sourcea ne daje membership.
7. Structural refit odbija forged legacy component membership i čuva potpuno hard-assignment pokriće.
8. LOSO unique/non-unique mapping, interval near-tie i split/merge.
9. Point set, resolution union, connected components, wrap, antipodal, equal-largest-gap, disconnected i full-circle slučajevi.
10. Jedan veliki source ne dominira tri mala; duplicate bar ne povećava masu; quantile cumulative tie vraća interval.
11. Exact repeat sa različitim PPQ ima nultu point disperziju i nenultu resolution uncertainty.
12. Reference absent/permuted/conflicting ne mijenja nijedan Factory red, bound status/value ili Factory digest.
13. Oba delta bounda su uvijek unavailable/NULL i `authorizes_change=0`.
14. `LOCAL_REPEATED_PATTERN` ostaje odvojeni review stratum.
15. Database/API scan potvrđuje nula USER_INPUT, anomaly, target, proposal, simulation, writer ili MIDI output površina.

## 15. Revidirani acceptance redoslijed

```text
Architect addendum
→ Audit re-review
→ 013C-S structural registry implementation
→ independent 013C-S QA
→ structural Factory refit
→ Factory envelope/support/statistics/LOSO
→ frozen NULL delta rows
→ optional separate reference overlay
→ storage/API verification
→ independent final QA
```

013C tehnički ACCEPT ostaje samo:

```text
013C_FACTORY_CALIBRATION_ENVELOPE_ACCEPTED
```

Ne znači USER_INPUT comparison, anomaly, target, proposal, simulation, repair ili release.

## ARCHITECT VERDICT

```text
ARCHITECT_READY
```