# WP-X10-013A — Independent Architecture Audit

Datum: 12. august 2026.  
Predmet: `WP-X10-013A_ARCHITECT.md` naspram X10 ugovora i QA-prihvaćenih WP-012A/B/C/D slojeva  
Capability granica: `ANALYZE_ONLY / mutation NONE`

## GAPS

### G1 — Ne postoji prihvaćen schema-v2 calibration envelope

Architect ispravno zabranjuje hardkodirani prag, ali obavezna zavisnost još nije implementirana u WP-012A–D. Postojeći `rhythm_calibration.sqlite3` i `rxoptimizer/rhythm_calibration.py` eksplicitno ne proizvode target, koriste legacy lokalne profile i nemaju versioned `minimum_meaningful_delta` / `maximum_allowed_delta` vezan za schema-v2 exact context, event slot, source/config digest i stable subject.

Bez novog calibration ugovora svaki stvarni kandidat mora završiti kao `TARGET_WITHHELD_CALIBRATION_UNAVAILABLE`. Synthetic fixture može testirati API, ali ne smije prikriti da produkcijski target proof trenutno nema autoritativan calibration input.

### G2 — Nedostaje schema-v2 local-pattern target proof

WP-012B čuva samo structural repeat membership preko jednakih bar rhythm/topology hashova. Ne čuva versioned, leave-one-out poravnanje oštećene instance, per-slot phase membership, unique local target, niti digest koji dokazuje da se target nije izveo iz same anomalne note.

013A zato nema prihvaćen izvor za tvrdnje:

- najmanje dvije druge exact instance ne podržavaju original;
- sve validne lokalne instance daju jednu istu phase vrijednost;
- target slot je poravnat bez circularnog korištenja pokvarenog onseta u fingerprintu.

### G3 — User-input snapshot nije definisan

Prihvaćeni schema-v2 `source_context_v2` dopušta samo `FACTORY_RAW` i `GOLD_REFERENCE_RAW`. Architect govori o kandidatu na "Factory-valid user inputu", ali ne definiše novi immutable `USER_INPUT` source class, njegov lineage policy, quality semantiku, exact-context extraction, vezu prema read-only Factory model bazi niti authorization truth table.

Bez toga nije jasno da li 013A analizira Factory corpus note ili stvarni korisnički MIDI. Kandidat za budući repair mora biti vezan za zaseban user-input snapshot; korisnički input ne smije biti predstavljen kao `FACTORY_RAW`.

### G4 — Simulation metric contract nije matematički zaključan

Pojmovi `Factory support improves`, `local repeated-pattern distance`, `groove-mode tuple does not worsen`, `pattern fingerprint`, `modification cost` i `minimal among equivalent translations` nemaju verziju, ulazni universe, tačnu formulu, numeric representation, interval/tie ponašanje ni canonical serialization.

WP-012C zahtijeva rational/Decimal i certified interval odluke. 013A ne smije vratiti `SIMULATION_VALIDATED` na osnovu binary64 scorea, neversioniranog kompozitnog scorea ili poređenja sa epsilonom.

### G5 — Minimal shadow closure nije dovoljna za globalnu parity tvrdnju

"Affected bar + neighbour closure" može provjeriti lokalne odnose, ali samo po sebi ne dokazuje parity svih non-target događaja, EOT-relative stanje, udaljeni same-note par, sustain/controller ordering ili svaki događaj preko čijeg ticka translacija prelazi.

Potreban je whole-source immutable semantic manifest i target-overlay dokaz: kompletan source universe ostaje isti, a samo dva odobrena event polja dobijaju shadow vrijednost. Lokalni graf onda služi za muzičke validatore, ne kao jedini dokaz globalne parity.

### G6 — Audit storage i atomic replace nisu dovoljno razdvojeni

Dokument traži immutable candidate, simulation rezultat, audit zapis i atomic target database, ali ne zaključava append-only tablice, FK smjer, natural keys i zabranu `UPDATE/DELETE`. Nije definisano da li failed run ostavlja terminal audit red ili u potpunosti ne ostavlja novi semantic output.

## RISKS

### R1 — False repair kroz circular local-pattern dokaz

Ako rhythm/topology fingerprint uključuje onset strukturu koja je predmet procjene, anomalna instanca može ispasti iz grupe prije evaluacije ili se target može birati iz grupe konstruisane nakon hipotetičke promjene. To proizvodi selection bias i lažno "strogo poboljšanje".

Local scope mora biti frozen prije targeta, imati leave-one-target-out alignment i dokaz da slot identity ne zavisi od candidate phase vrijednosti.

### R2 — Unimodal Factory model ne znači jedinstven opaženi target

`ASSESSED_UNIMODAL` dokazuje stabilan jedan mod, ne jednu tačnu rational phase vrijednost. Komponenta može sadržati više validnih opaženih faza. Mean/medoid/component center nije automatski target. Ako Factory i local dokazi ne daju jednu identičnu opaženu phase vrijednost, obavezan rezultat je multiple-target/insufficient-evidence withholding.

### R3 — Reference support arc je preslab za exact-target podršku

WP-012C `REFERENCE_SUPPORT` znači da reference observation ulazi u Factory empirical support arc. To ne dokazuje da reference podržava baš target rational phase. Architectova rečenica "reference mora podržavati phase" mora koristiti novi exact-target relationship ili biti preformulisana kao non-contradiction gate. Postojeći broad support status se ne smije predstaviti kao exact target vote.

### R4 — Atomskа translacija može promijeniti širu semantiku

Jednak on/off delta čuva duration, ali može promijeniti cluster membership, ordering prema controllerima, note-off/note-on same-tick redoslijed, sustain interpretaciju, voice-leading i pattern membership. Provjera samo neposrednog previous/next note susjeda nije dovoljna; mora obuhvatiti sve događaje i granice u pređenom tick intervalu.

### R5 — Synthetic positive može postati lažni readiness signal

Synthetic fixture smije dokazati samo software contract. Acceptance/report mora odvojeno pokazati broj stvarnih corpus/user kandidata po withheld reasonu i ne smije proglasiti target generation operativnim dok G1–G3 nisu zatvoreni stvarnim, trusted inputima.

### R6 — Candidate budget polja mogu prerano sugerisati repair dozvolu

`budget impact` i "minimal cost" još nemaju session ranking/budget ugovor, koji je eksplicitno naredni paket. U 013A treba ih svesti na neutralne, versioned descriptive metrics ili ih izostaviti; ne smiju odlučivati target ili validation status.

## CONTRADICTIONS

### C1 — `LOCAL_REPEATED_PATTERN` istovremeno blokira i zahtijeva target proof

WP-012B adapter za exact local repeat emituje `DETECTED` membership za note ponovljenog patterna. WP-012 authorization tada vraća protection/preserve, ne `ANALYZE_ALLOWED`.

013A anomaly proof istovremeno zahtijeva:

1. schema-v2 `ANALYZE_ALLOWED` za istu note/subject; i
2. najmanje dvije druge exact local repeated-pattern instance kao obavezan anomaly/target dokaz.

U sadašnjem ugovoru note koja ima traženi local-repeat dokaz tipično ne može dobiti `ANALYZE_ALLOWED`. Ovo nije implementacioni detalj nego nedostižan contract path. Ne smije se riješiti slabljenjem protectiona. Potreban je novi read-only distinction, npr. `LOCAL_REPEAT_VALID_ORIGINAL_PROTECTED` naspram `LOCAL_REPEAT_COMPARISON_EVIDENCE`, sa novim auditom authorization truth tablea.

### C2 — Jedan status domen miješa candidate i simulation lifecycle

Closed candidate states sadrže i `TARGET_PROVEN_EXACT` i `SIMULATION_VALIDATED/REJECTED`. Istovremeno payload pravilo kaže da target/delta polja smiju biti non-NULL samo kada je status `TARGET_PROVEN_EXACT`; za svaki drugi status moraju biti NULL.

Posljedica: `SIMULATION_VALIDATED` ne može sačuvati target koji je simuliran. Ako se isti candidate red ažurira, krši immutable candidate i canonical-content uniqueness; ako se kreira novi sadržaj sa istim natural keyem, nastaje kontradikcija.

Mora se razdvojiti najmanje na:

- immutable `candidate_hypothesis` + `anomaly_status` + `target_status`;
- immutable `simulation_run` sa svojim ID-em i FK na exact candidate;
- immutable `validation_result` sa FK na simulation;
- terminal run/audit status odvojen od sva tri.

### C3 — Source authority formulacija je kontradiktorna

"Source je Factory-valid user input" spaja dvije različite authority klase. User input nikad nije Factory evidence. Ispravno razdvajanje je: candidate source = immutable `USER_INPUT`; target authority = trusted Factory NORMAL model/observations; Gold/reference = support/conflict; user input nikad ne trenira niti potvrđuje Factory target.

### C4 — `ANALYZE_ONLY` payload koristi repair-like `budget impact`

Architect kaže da 013A ne troši repair budget i ne rangira candidate, ali obavezni payload uključuje budget impact i validation traži minimal cost među translacijama. Bez zasebnog descriptive-only contracta ovo uvodi dio narednog ranking/budget paketa u 013A.

## DEPENDENCIES

Prije production-capable exact targeta moraju postojati i biti version-locked:

1. schema-v2 user-input snapshot/lineage/authorization addendum;
2. schema-v2 calibration envelope builder sa exact context/event-slot provenanceom;
3. leave-one-target-out local pattern comparison model sa stable slot membershipom;
4. clarification/addendum za `LOCAL_REPEATED_PATTERN` protection versus comparison evidence;
5. odvojeni candidate/simulation/validation schema i lifecycle;
6. exact-target reference relationship ili eksplicitno non-contradiction-only pravilo;
7. mathematical simulation metric registry sa rational/Decimal interval semantics;
8. whole-source semantic parity manifest i crossed-interval closure;
9. append-only/atomic database contract i terminal failure semantics;
10. novi negative/adversarial fixtures za source-class confusion, circular grouping, repeated-pattern protection conflict i metric near-ties.

WP-012A–D moraju ostati read-only. Bilo kakva promjena 012B protection semantics ili 012D authorizationa zahtijeva integration addendum, re-audit i novi nezavisni QA; 013A ne smije ih tiho reinterpretirati.

## BLOCKERS

### B1 — Contract lifecycle je interno nekonzistentan

C2 onemogućava canonical immutable zapis validirane simulacije sa target provenanceom.

### B2 — Obavezni local proof i `ANALYZE_ALLOWED` put su trenutno međusobno isključivi

C1 znači da pozitivni production path nije dokazano reachable kroz prihvaćeni WP-012 truth table.

### B3 — Ne postoji user-input source contract

Bez G3/C3 nije dozvoljeno vezati candidate za stvarni ulazni MIDI niti user input predstaviti kao Factory corpus.

### B4 — Ne postoji prihvaćen calibration envelope

Bez G1 svaki stvarni target mora ostati withheld. Implementacija koja proizvodi non-NULL target prije tog dependencyja krši X10 Calibration Contract.

### B5 — Validation odluka nema zaključane metrike

Bez G4 nije dokazivo šta znači strict improvement, equal, disagreement ili numerical uncertainty.

## RECOMMENDED_GATES

### Gate A — Architect addendum prije Lead plana

Addendum mora:

- razdvojiti candidate, simulation, validation i run statuse/tablice;
- zatvoriti C1 bez slabljenja postojeće protection sigurnosti;
- definisati `USER_INPUT` snapshot i authority separation;
- proglasiti production target disabled dok calibration/local-pattern dependencies nisu QA-accepted;
- ukloniti ili descriptive-only zaključati budget/cost polja.

### Gate B — Calibration + local comparison subpackage

Poseban analyze-only subpackage mora proizvesti immutable, versioned:

- minimum meaningful i maximum allowed delta envelope;
- exact-context/event-slot/source/config digeste;
- leave-one-target-out local comparison scope;
- unique phase set i ambiguity status;
- testove koji dokazuju da target note nije korištena za vlastito opravdanje.

### Gate C — Reachability proof

Prije Implementera napraviti truth-table test na ugovornom nivou koji dokazuje da je svaki status reachable, posebno:

```text
ANALYZE_ALLOWED
+ local comparison evidence
+ protection clear
+ Factory sufficient unimodal
+ calibration available
→ TARGET_PROVEN_EXACT ili eksplicitni WITHHELD razlog
```

Synthetic positive mora koristiti isti javni contract path, bez test-only bypassa.

### Gate D — Simulation metric registry

Svaki validator mora imati ID/version, exact inputs, numeric representation, conservative comparison pravilo, unknown/tie status i digest. `equal`, interval overlap ili missing metric daju reject/preserve.

### Gate E — Whole-source parity and mutation guard

Shadow engine mora biti overlay nad frozen whole-source manifestom. Testovi moraju dokazati:

- input/schema/model DB hash prije i poslije;
- tačno dva dozvoljena shadow polja;
- parity svih drugih polja/događaja;
- closure svih događaja pređenih translacijom;
- zabranu importa/poziva MIDI writer/encoder/export putanje;
- atomic failure bez parcijalnog accepted semantic outputa.

### Gate F — Staged acceptance

Preporučene odvojene oznake:

1. `013A_SCHEMA_FOUNDATION_ACCEPTED` — može čuvati withheld candidate i odbiti simulation;
2. `013A_TARGET_PROOF_ACCEPTED` — tek poslije calibration/local/user-input gateova;
3. `013A_SIMULATION_ACCEPTED` — tek poslije metric/parity gateova.

Nijedna oznaka ne mijenja `ANALYZE_ONLY/NONE` niti odobrava proposal, apply, MIDI output ili release.

## AUDIT VERDICT

Sigurnosni smjer Architect dokumenta je ispravan: default preserve, Factory-only target authority, NULL target za nedokazane slučajeve, single-note shadow translacija i stroga zabrana mutacije/exporta. Međutim, C1 i C2 su direktne contract kontradikcije, a B3–B5 su obavezne nedostajuće zavisnosti za positive target/simulation acceptance.

WP-X10-013A zato nije spreman za Lead/Implementer u sadašnjoj verziji. Dozvoljen je samo Architect addendum i ugovorni reachability rad; production code za exact target ili validated simulation ne treba početi.

```text
BLOCKED
```