# WP-X10-013C-S — Complete-Proof Review of RETURN Findings

Datum: 12. august 2026.  
Uloga: nezavisni read-only proof/test reviewer  
Standard: `prism-uploads/MASTER PROMPT — COMPLETE PROOF - NO UNPROVEN CLAIMS AUDIT.md`  
Scope: samo tri trust nalaza iz `WP-X10-013C_S_QA.md`  
Status paketa: `RETURN`

## Izvršivost i stvarni execution path

Pregledani su:

- `rxoptimizer/rhythm_structural_slots.py`;
- `tests/test_rhythm_structural_slots.py`;
- Architect, Addendum, Audit, Re-audit, Lead i prethodni QA zapis.

Stvarni testni put je:

```text
source_fixture
→ caller gradi StableSubjectRegistry + lineage + source manifest
→ caller gradi CalibrationContextPrimitives/StructuralVoicePrimitive
→ FactoryStructuralSource
→ build_structural_registry
→ _validate_source
→ _context_base
→ _validate_bar_provenance
→ _bar_tokens / _cluster_token
→ calibration_context_identity / structural_slot_identity
→ SQLite structural_* redovi
```

Repo pretraga nije pronašla production poziv `build_structural_registry`; funkciju trenutno pozivaju ciljani testovi. Zato je tvrdnja da je 013C-S dostupan kroz stvarni CLI/GUI/build pipeline:

```text
NOT PROVABLE FROM CURRENT EVIDENCE / DEAD PRODUCTION INTEGRATION
```

Ovo ne negira pronađene trust greške: one su reprodukovane direktno na javnom builder API-ju koji paket predlaže kao osnovu za kasniji envelope.

Pokrenuto:

```text
python3 -m pytest -q -W error tests/test_rhythm_structural_slots.py
18 passed
```

Isti suite prolazi iako naredne adversarial probe dokazuju sva tri propusta. Sam broj prolaznih testova zato nije dokaz trust ugovora.

---

## CLAIM 1 — Calibration context nastaje samo iz frozen, accepted Factory provenancea

### CLAIM

Svako identity-kritično polje (`Bank MSB/LSB`, Program, instrument identity, style, section number, CV, meter, tempo regime, track-channel role i voice policy) mora biti rekonstruisano iz accepted immutable Factory/schema-v2 zapisa. Caller ne smije promijeniti polje i dobiti resolved production structural key.

### EVIDENCE

`FactoryStructuralSource.context` je direktni caller input (`rhythm_structural_slots.py:228-245`). `_context_base()` sva njegova polja unosi u identity (`255-274`). `_validate_bar_provenance()` poredi samo:

- `TrackObservation.role` sa `source.context.role` (`414-416`);
- `SectionObservation.section` sa `source.context.section` (`417-421`).

Ne postoji poređenje ostalih identity polja sa accepted schema-v2/RAW zapisom.

Izvršena adversarial proba zadržala je isti snapshot, role i section, a promijenila:

```text
bank_msb=99
bank_lsb=88
program=77
instrument_identity_key=FORGED_IDENTITY
style_name=Forged Style
section_no=9
cv=7
meter=7/8
microseconds_per_quarter=400000
track_channel_role=DRUM_TRACK
```

Rezultat:

```text
resolved_memberships = 1
status = STRUCTURAL_SLOT_RESOLVED
```

Stored `identity_json` sadrži sve lažne vrijednosti. Posebna proba promijenila je samo `voice_policy` u `EXACT_DRUM_LANE`; i ona je dala resolved membership i promijenila voice signature.

### POSTOJEĆI TESTOVI

`test_closed_context_domains_fail_unproven_before_materialization` provjerava samo da token izvan closed role domene (`UNKNOWN`) daje unproven. Ne provjerava validan, ali netačan caller token.

`test_style_and_tempo_identity_are_canonical` dokazuje samo normalizaciju ekvivalentnog style stringa. Ne dokazuje izvor istine.

`source_fixture` sam pravi `TrackObservation` i `SectionObservation` iz istog caller contexta. Test fixture zato može učiniti laž self-consistentnom i sakriti mismatch.

### WHAT BUG ESCAPES

Implementacija može prihvatiti bilo koji domain-valid Bank/Program/style/CV/meter/tempo/track role/voice policy. Svi postojeći testovi i dalje prolaze dok laž ulazi u calibration key.

### STATUS

```text
FAIL — adversarially reproduced
```

### OBAVEZNI NOVI TESTOVI

1. Iz accepted frozen anchor fixturea napraviti jednu validnu notu/bar, zatim parametrizovano promijeniti svako identity polje zasebno. Očekivanje: hard reject ili `STRUCTURAL_CONTEXT_UNPROVEN`, nula context/slot/membership redova.
2. Promijeniti dvije ili više vrijednosti tako da su domain-valid i međusobno konzistentne; rezultat i dalje mora biti odbijen prema anchoru.
3. Mutirati frozen accepted zapis nakon otvaranja/read snapshot-a; build mora otkriti byte/semantic digest mismatch.
4. Dokazati pozitivni put samo iz rekonstrukcije: caller ne predaje gotov context ili predaje očekivanje koje se byte-for-byte poredi sa rekonstruisanim contextom.
5. Meter i tempo moraju biti vezani za segment aktivan na konkretnoj noti/bar-u, a Program/Bank za stvarni NOTE_ON segment; source-level default nije dovoljan.

---

## CLAIM 2 — `FACTORY_RAW/NORMAL` dolazi samo iz accepted immutable corpusa

### CLAIM

Self-consistent lineage objekat i string `NORMAL` nisu autoritet. Svaki production source mora imati dokazivu membership/parity vezu prema accepted schema-v2/corpus manifestu i quality registryju.

### EVIDENCE

`FactoryStructuralSource.quality_status` je caller string sa jedinom provjerom `== "NORMAL"` (`228-245`). `_validate_source()` rekonstruiše caller-provided lineage i provjerava njegovu internu konzistentnost (`364-396`), ali ne pita accepted corpus da li source SHA zaista postoji kao Factory i da li je kvalitet NORMAL.

Test helper `source_fixture` računa proizvoljan SHA iz taga, zatim sam pravi:

```text
SourceLineageRecord(source_sha, "FACTORY_RAW", ())
source_manifest={"source_class":"FACTORY_RAW", ...}
FactoryStructuralSource(..., quality_status="NORMAL")
```

Izvršena adversarial proba sa tagom `self-labelled-arbitrary-bytes`, bez accepted corpus zapisa, dala je:

```text
resolved_memberships = 1
source_registry = (FACTORY_RAW, NORMAL)
```

### POSTOJEĆI TESTOVI

`test_untrusted_authority_is_rejected_before_database` mijenja `source_kind` u `SYNTHETIC_TEST`. On dokazuje da otvoreno pogrešna etiketa ne prolazi, ali ne testira napadača koji proizvoljan/sintetički izvor označi dozvoljenom etiketom `FACTORY_RAW`.

Svi pozitivni testovi koriste upravo self-labeled synthetic fixture. Oni ne mogu dokazati production Factory authority.

### WHAT BUG ESCAPES

Mutacija ili napadački caller može generisati novi random SHA, self-signed lineage DAG i manifest, postaviti `NORMAL`, pa dobiti production membership. Test koji samo provjerava odbijanje literalnog `SYNTHETIC_TEST` ostaje zelen.

### STATUS

```text
FAIL — adversarially reproduced
```

### OBAVEZNI NOVI TESTOVI

1. Self-labeled `FACTORY_RAW/NORMAL` source koji ne postoji u accepted corpus manifestu mora biti odbijen prije structural materializationa.
2. Postojeći Factory SHA sa forged source class, member path, raw byte digest, schema-v2 digest, corpus-generation digest ili manifest digest mora biti odbijen.
3. Postojeći Factory SHA sa caller `NORMAL`, ali accepted quality `RARE`, `OUTLIER` ili `INVALID`, mora biti odbijen/isključen; caller string ne smije pobijediti registry.
4. Quality lookup mora biti na odgovarajućem source/track/channel/context nivou. Source sa jednim NORMAL i jednim OUTLIER trackom ne smije globalno pretvoriti oba u NORMAL.
5. Accepted manifest/quality DB moraju se otvoriti read-only; pre/post semantic i byte digest parity mora biti provjerena.
6. Synthetic test fixture smije raditi samo kroz eksplicitni non-production test authority/adaptor koji nikad ne izdaje production `FACTORY_RAW` sufficiency.
7. Missing accepted anchor mora blokirati build; ne smije postojati fallback na caller lineage.

---

## CLAIM 3 — Duplicate/unison se razrješava samo frozen timing-free voice projekcijom

### CLAIM

Duplicate pitch/unison smije dobiti unique voice order samo iz allowlisted stable NOTE prirodnog ključa koji dokazivo ne sadrži tick, phase, IOI, duration, event/parser order niti digest koji ih commit-tuje. Bez takvog dokaza subset je ambiguous.

### EVIDENCE

`StructuralVoicePrimitive.voice_token` je običan caller string (`157-174`). Validator provjerava regex i nekoliko zabranjenih substringova. `_cluster_token()` duplicate note smatra resolved ako tokeni samo nisu `None` i međusobno su različiti, a zatim njima sortira glasove (`277-292`). `_validate_voice_paths()` isti token koristi za crossing odluku (`306-314`).

Izvršena adversarial proba sa unison tokenima:

```text
V000123
V000124
```

dala je:

```text
resolved_memberships = 2
status = STRUCTURAL_SLOT_RESOLVED
```

Tokeni mogu kodirati onset tick ili parser/event ordinal bez ijedne zabranjene riječi. Nijedna frozen NOTE natural-key vrijednost se ne poredi sa tokenom.

### POSTOJEĆI TESTOVI

`test_duplicate_unison_without_timing_free_discriminator_is_ambiguous` ispravno pokriva samo `None` tokene.

`test_duplicate_unison_with_unique_structural_tokens_is_resolved` je suprotan potrebnom trust dokazu: proizvoljni caller tokeni `VOICE_A/VOICE_B` se očekuju kao resolved bez provenance verifikacije.

`test_voice_crossing_is_fail_closed` vjeruje istim caller tokenima za crossing. On dokazuje konzistentnost stringova, ne njihovo porijeklo.

### WHAT BUG ESCAPES

Bilo koji opaque token koji zadovolji regex — uključujući enkodiran tick, parser order, source-local counter ili hash takvih podataka — razrješava unison i utiče na crossing. Substring denylist ne može dokazati data lineage.

### STATUS

```text
FAIL — adversarially reproduced
```

### OBAVEZNI NOVI TESTOVI

1. `V000123/V000124`, base36 parser ordinal, truncated hash ticka i hash event ID-a moraju dati `STRUCTURAL_DUPLICATE_AMBIGUOUS` ako nisu rekonstruisani iz frozen allowlisted projekcije.
2. Caller-provided token različit od recomputeovanog frozen tokena mora hard failovati.
3. NOTE natural key koji sadrži samo opaque `note_id`/digest bez dokazive field projection ne smije automatski postati voice discriminator.
4. Pozitivni unison fixture mora sadržati eksplicitna, auditovana structural voice polja u frozen registryju; verifier ih rekonstruiše i dokazuje odsustvo timing/event-order zavisnosti.
5. Isti structural voice kroz više barova/sourceova mora imati stabilan ordinal; crossing, collision, duplicate projection ili missing projection daje ambiguity.
6. Permutovanje parser/event input reda uz identičan musical structure ne smije promijeniti token, slot ili membership digest.

---

## Mutation plan

Acceptance nije dozvoljen samo na osnovu novih happy-path testova. Sljedeće kontrolisane mutacije moraju oboriti ciljane testove:

| Mutacija implementacije | Test koji mora pasti |
|---|---|
| Zamijeni reconstructed Bank/Program sa caller vrijednošću | per-field context forgery test |
| Preskoči style/section-no/CV parity | corresponding per-field test |
| Koristi source-level meter/tempo umjesto aktivnog segmenta | segment-boundary fixture |
| Prihvati domain-valid drugi track role/voice policy | track-role/policy forgery test |
| Ukloni accepted-corpus membership lookup, zadrži self-consistent lineage | self-labeled Factory rejection test |
| Uvijek postavi quality `NORMAL` | accepted RARE/OUTLIER/INVALID fixtures |
| Dozvoli missing manifest/quality anchor fallback | missing-anchor test |
| Vrati na regex-only `voice_token` validaciju | encoded tick/parser-order tests |
| Sortiraj unison po event ID-u, NOTE ID-u ili input redoslijedu | event-order permutation test |
| Prihvati opaque hash kao timing-free projekciju | hash-smuggling fixture |
| Preskoči stored DB semantic re-verification prije read API-ja | post-build row mutation/verifier test |

Ako bilo koja od ovih mutacija preživi, odgovarajući trust claim ostaje `UNPROVEN`, bez obzira na ukupni broj prolaznih testova.

## Minimalni acceptance checklist za novi QA prolaz

- [ ] Production execution path ili eksplicitno označen izolovani library status je dokumentovan bez tvrdnje o runtime integraciji.
- [ ] Builder zahtijeva neforgeable/read-only accepted corpus/schema-v2 anchor; missing anchor blokira.
- [ ] Source SHA/class/manifest/generation/schema digest parity se ponovo računa, ne vjeruje caller tokenu.
- [ ] `NORMAL` quality se čita iz accepted registryja na tačnom track/channel/context nivou.
- [ ] Svako calibration context polje je rekonstruisano iz frozen provenancea ili daje `STRUCTURAL_CONTEXT_UNPROVEN`.
- [ ] Caller context ne može uticati na identity osim kao byte-equal očekivanje prema rekonstrukciji.
- [ ] Voice discriminator je typed allowlisted projection sa dokazivim field lineageom; opaque digest/string nije dovoljan.
- [ ] Duplicate/unison bez verified projekcije uvijek ostaje ambiguous.
- [ ] Full stored verifier ponovo računa semantic root, canonical JSON, closed enum domene, FK/integrity i source/context/token provenance.
- [ ] Adversarial fixturei iz sva tri odjeljka prolaze sa očekivanim odbijanjem.
- [ ] Svaka mutacija iz mutation plana ubija najmanje jedan test.
- [ ] Targeted i full `pytest -W error`, compile i `git diff --check` prolaze.
- [ ] Nezavisni QA vrati `ACCEPT` tek nakon pregleda stvarnih assertiona i adversarial rezultata.

## Konačni proof verdict

| Trust claim | Status |
|---|---|
| Context identity je reconstructed iz frozen Factory provenancea | `FAIL` |
| `FACTORY_RAW/NORMAL` je vezan za accepted corpus/quality registry | `FAIL` |
| Unison discriminator je verified timing-free projection | `FAIL` |
| Production CLI/GUI/build reachability 013C-S | `NOT PROVABLE FROM CURRENT EVIDENCE` |

```text
WP-X10-013C-S = RETURN
013C envelope implementation = BLOCKED
release/certification implication = NONE
```
