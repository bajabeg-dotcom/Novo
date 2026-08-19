# WP-X10-013C — Independent Re-audit

Datum: 12. august 2026.  
Pregledano: `WP-X10-013C_ARCHITECT.md`, `WP-X10-013C_AUDIT.md`, `WP-X10-013C_ARCHITECT_ADDENDUM.md` i prihvaćeni WP-012C/012D kod  
Audit uloga: ChatGPT Audit  
Status: `AUDIT_REVIEWED`

## Zaključak

Architect addendum verzija 2 razrješava nalaze B1–B13 dovoljno precizno da implementacija može početi strogo propisanim redoslijedom:

```text
013C-S structural registry
→ nezavisni 013C-S QA
→ structural Factory refit
→ envelope/statistics/LOSO
→ obavezni NULL delta redovi
→ odvojeni reference overlay
→ finalni QA
```

Paket ostaje `ANALYZE_ONLY/NONE`. Ne postoji USER_INPUT fitting, anomaly odluka, target, proposal, simulation, MIDI writer niti output put.

## Re-audit B1–B13

### B1 — Factory/reference kontradikcija: RESOLVED

Factory envelope, status, bound redovi i Factory semantic digest zamrzavaju se prije čitanja reference. Reference ima zaseban overlay natural key i zaseban digest root. Ne smije izmijeniti nijedan Factory red ili availability status.

Oba v1 bounda su obavezno:

```text
status = UNAVAILABLE_FORMULA_NOT_CONTRACTED
value = NULL
authorizes_change = false
```

### B2 — Canonical calibration context: RESOLVED

Addendum daje canonical ASCII JSON payload, closed identity domene, exact tempo bucket formulu, style normalization, meter/role/instrument/section/CV ponašanje i fail-closed `STRUCTURAL_CONTEXT_UNPROVEN` rezultat.

### B3 — Hidden timing leakage: RESOLVED uz Lock L1–L3

Identity i provenance payload su odvojeni. Legacy `exact_context_key`, `topology_sha256`, phase-bearing `event_slot_key`, tick/phase/IOI i svaki digest koji ih commit-tuje zabranjeni su u identityju. Identity se rekonstruiše isključivo iz primitive allowliste; caller digest nije autoritet.

### B4 — Cluster/voice/pitch alignment: RESOLVED uz Lock L4–L6

Cluster je exact simultaneous NOTE_ON skup bez epsilon mergea. Cross-file alignment zahtijeva potpuno jednaku sekvencu cluster cardinality + voice signature tokena. Transposition je dozvoljen preko lowest-pitch anchora; inversion, split/merge, arpeggiation, insert/delete, crossing i nerazrješiv duplicate/unison daju ambiguity.

### B5 — Source identity/cross-file membership: RESOLVED

Svaki source prolazi trusted Factory RAW lineage validator prije registryja. Key collision nije membership dokaz; potreban je source-local recomputation red i stable-subject FK lanac. Synthetic i drugi authority izvori ne ulaze u production Factory sufficiency.

### B6 — Structural refit/component provenance: RESOLVED

Legacy WP-012C reproduction je samo input-integrity dokaz. Novi structural model ima novi observation universe, model/component ID i semantic digest. Legacy component ID ne daje membership pravo. Hard assignments moraju potpuno i disjointno pokriti universe.

### B7 — LOSO matching: RESOLVED uz Lock L7

Cost dimenzije, certified intervals, exhaustive permutation i strict no-tie pravilo su versioned. Split/merge, interval overlap ili više pobjednika daju unstable.

### B8 — Circular support: RESOLVED

Odvojeno se čuvaju exact point set/multiset, per-observation resolution arcs, canonical union/connected components i optional unique enclosing arcs. Wrap, equal-largest-gap, antipodal, disconnected i full-circle slučajevi imaju fail-closed statuse.

### B9 — Source balancing/quantile semantika: RESOLVED

Masa je exact `1/S`, odnosno `1/(S*n_s)` po observationu. `n_eff`, medoid, weighted quantile tie interval, MAD/IQR i dvije odvojene dominance metrike su zaključani.

### B10 — Exact repeat/resolution: RESOLVED

Point disperzija može biti nula, ali stvarni per-observation half-tick arcs ostaju measurement uncertainty. Coarse PPQ ne daje lažnu preciznost. Nijedan v1 delta bound ne postaje nula ili available.

### B11 — Delta formule: RESOLVED

Formule nisu prihvaćene i zato schema mora enforced držati oba bounda unavailable/NULL. Nema config, callback ili synthetic bypassa. Buduća formula zahtijeva novi versioned paket.

### B12 — `LOCAL_REPEATED_PATTERN`: RESOLVED

Detected/ambiguous slučaj ide samo u `LOCAL_REPEAT_REVIEW_STRATUM`, ne povećava generic sufficiency, ne ulazi u robust stats/LOSO i ne proizvodi bound ili target dokaz.

### B13 — Authority separation: RESOLVED

Gold/reference je post-envelope odvojena masa i digest. Ne ulazi u Factory model, statistics, LOSO, sufficiency ili bound. USER_INPUT i downstream actionable semantika ostaju izvan scopea.

## Obavezni implementation lockovi

### L1 — Primitive-only identity builder

Public/internal identity builder ne smije primiti generic mapping ili caller-supplied digest. Mora primiti typed/closed primitive fields, sam napraviti canonical payload i odbiti unknown/extra field. `identity_config_sha256` smije commitovati samo validated closed identity config čija schema sama zabranjuje timing/provenance input.

### L2 — Timing-invariance test je topology-preserving

Promjena onset tick/phase/IOI mora zadržati isti structural key samo kada ne mijenja:

- exact cluster membership;
- cluster order;
- cluster cardinality;
- canonical voice signature.

Ako timing promjena razdvoji simultani cluster, spoji cluster, promijeni redoslijed ili izazove crossing, rezultat mora biti ambiguity/unproven, ne isti resolved slot. Test ne smije zahtijevati isti ključ kroz stvarnu structural promjenu.

### L3 — No digest smuggling

Dependency validator mora provjeravati reconstructed primitive dataflow. Statički forbidden-token scan nije dovoljan. Provenance/member digest može biti FK/audit input, ali nikad ancestor identity digesta.

### L4 — Source-local ordinal nije samostalan cross-file dokaz

Cluster ordinal smije ući u slot payload tek nakon dokazane exact token-sequence identity cijelog bar structurea. Sam event/tick order ne daje cross-file alignment.

### L5 — Duplicate/unison fail-closed

`stable_note_natural_key_without_timing` mora biti eksplicitna allowlisted projekcija. Ne smije koristiti event ID, NOTE ID, source-local parser order, onset/off tick, duration ili hash koji ih commit-tuje. Ako isti pitch/offset i preostali structural primitive ne daju unique voice mapping, cijeli duplicate subset je ambiguous.

### L6 — One observation per source/bar/slot

Za resolved structural slot dozvoljena je tačno jedna observation po `(source_sha, bar_subject_id, structural_event_slot_key)`. Zero znači absent; multiple ili contradictory duplicate znači ambiguity/hard fail i nijedan red ne ulazi u fit.

### L7 — Canonical LOSO permutation comparison

Implementacija mora version-lockovati kako se pair cost vectori agregiraju u permutation cost. Dozvoljeno je npr. canonical full-component-order concatenation ili exact per-dimension sum, ali odabrana formula mora biti zapisana u config/digest i testirana. Ne smije postojati implicitni Python tuple/order/ID tie-break. Dok formula nije eksplicitna u kodnom contractu, LOSO rezultat mora biti unstable.

### L8 — Factory digest independence

Test mora izgraditi isti Factory input sa: bez reference, permutovanom reference, support reference i conflict reference. Svaki Factory semantic red, Factory bound red i Factory digest moraju ostati byte-identični. Mijenjati se smije samo reference overlay root.

### L9 — Enforced NULL bounds

SQLite CHECK, semantic validator i read-only API moraju zajedno dokazati:

```text
status LIKE 'UNAVAILABLE_%'
all value columns IS NULL
authorizes_change = 0
```

Forbidden je i sakrivena numeric bound vrijednost u semantic JSON/reason/config payloadu.

### L10 — Capability/static surface

Schema, API i config ne smiju primati ili emitovati USER_INPUT phase, anomaly, target, candidate, proposal, simulation, repair, apply, writer ili MIDI output podatak. Performance/nonsemantic metričke vrijednosti ne ulaze u semantic digest.

## QA gateovi

013C-S QA mora posebno potvrditi:

1. topology-preserving timing varijante daju isti key;
2. nested digest ne može prenijeti timing;
3. simultaneous/arpeggiated, inversion, crossing, split/merge i duplicate slučajevi fail-closed;
4. lineage i stable-subject provenance se rekonstruišu, ne vjeruju stored tokenu;
5. nema Factory model/envelope implementacije prije prihvaćenog registryja.

Finalni QA mora potvrditi:

1. structural refit full hard-membership coverage;
2. source balancing, circular support i exact-repeat resolution;
3. exhaustive LOSO i ambiguous permutation handling;
4. oba delta reda uvijek unavailable/NULL;
5. reference ne mijenja Factory root;
6. local-repeat review isolation;
7. deterministic atomic build, FK/integrity/digest, read-only API;
8. `pytest -W error`, compile i `git diff --check`.

## Re-audit verdict

```text
AUDIT_REVIEWED
```

Implementacija je odobrena samo unutar addenduma i lockova L1–L10. Ovo nije odobrenje za USER_INPUT comparison, anomaly, target, proposal, simulation, MIDI mutation/output, certification ili release.