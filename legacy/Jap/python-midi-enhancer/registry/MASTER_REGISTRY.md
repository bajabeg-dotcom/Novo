# MASTER REGISTRY

> Generirano iz `registry/master_registry.json`; ne uređivati ručno.

Registry verzija: `0.17.1`  
Stanje na datum: `2026-08-14`  
Broj zapisa: `143`

Četiri statusne osi su namjerno neovisne: dokaz, implementacija, validacija i certifikacija.

## CLAIM

| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |
|---|---|---|---|---|---|---|---|
| `CLAIM-001` | M06 Factory corpus rezultat | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-006`, `DATA-003`, `TEST-006`, `RUN-001`, `EVID-001` |
| `CLAIM-002` | M07 Factory corpus smoke rezultat | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-007`, `DATA-003`, `TEST-024`, `RUN-002`, `EVID-002` |

### CLAIM-001 — M06 Factory corpus rezultat

Loader je obradio 3.211/3.211 MIDI datoteka, 252 Style skupa (230 potpunih, 22 nepotpuna) uz nepromijenjen izvorni ZIP hash.

- Dokaz: **CONFIRMED** — Rezultat je vezan uz točno identificirani corpus, kod, test i zapisani run.
- Implementacija: **PASS** — Mjerenje proizvodi M06 loader/report pipeline.
- Validacija: **PASS** — Puni archive corpus test prolazi.
- Certifikacija: **PASS** — Tvrdnja je certificirana samo za DATA-003 hash i trenutačni M06 scope.
- Opažanja: `3211` MIDI datoteka

### CLAIM-002 — M07 Factory corpus smoke rezultat

Classifier je bez iznimke obradio 3.211 MIDI datoteka i proizveo 65.021 track-slice rezultat: 27.121 CLASSIFIED, 37.850 UNCERTAIN i 50 BLOCKED.

- Dokaz: **CONFIRMED** — Rezultat je vezan uz registrirani corpus, M07 kod i zapisani smoke test.
- Implementacija: **PASS** — Mjerenje proizvodi M07 classifier pipeline.
- Validacija: **PASS** — Unit suite i puni corpus smoke test prolaze.
- Certifikacija: **PASS** — Tvrdnja je certificirana samo za DATA-003 hash i read-only M07 scope.
- Opažanja: `65021` track-slice rezultat

## DECISION

| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |
|---|---|---|---|---|---|---|---|
| `DEC-001` | Humanize mora biti kontekstualan i analyze-first | `ACTIVE` | `PARTIAL` | `PARTIAL` | `NONE` | `NONE` | `DATA-003`, `DATA-004`, `MOD-008` |
| `DEC-002` | Balkan Drum Kit profil nije globalni default | `PROPOSED` | `PARTIAL` | `NONE` | `NONE` | `NONE` | `DATA-001`, `DATA-006` |
| `DEC-003` | User/Unknown Sound zamjenjuje samo korisnik | `PROPOSED` | `PARTIAL` | `PARTIAL` | `NONE` | `NONE` | `MOD-005`, `MOD-009`, `MOD-011`, `MOD-012`, `MOD-018`, `MOD-019`, `MOD-020`, `MOD-023`, `MOD-024`, `MOD-025` |
| `DEC-004` | G00 ograničeni Evidence Register prije M08 | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-007`, `DATA-008`, `MOD-010`, `TEST-023` |
| `DEC-005` | Moduli slijede dependency DAG, ne jedan linearni lanac | `ACTIVE` | `CONFIRMED` | `PASS` | `PARTIAL` | `PARTIAL` | `MOD-005`, `MOD-006`, `MOD-007`, `MOD-009` |

### DEC-001 — Humanize mora biti kontekstualan i analyze-first

Performance Humanization neće koristiti slijepi slučajni pomak; prvo zahtijeva timeline, ulogu, geste i referentne profile.

- Dokaz: **PARTIAL** — Odluka je utemeljena na sigurnosnim pravilima projekta i korisnički odobrenim referentnim corpusima.
- Implementacija: **PARTIAL** — M08 timeline, M09 mjerenje i M10 segmentacija implementirani su; transformation pipeline još ne postoji.
- Validacija: **NONE** — Nema transformation A/B testova jer writer nije implementiran.
- Certifikacija: **NONE** — Automatski Humanize nije autoriziran.

### DEC-002 — Balkan Drum Kit profil nije globalni default

Pop Std. Kit RX može biti preporuka unutar Balkan Pa800 profila, dok generički default čuva izvorni kit i dopušta GUI izbor.

- Dokaz: **PARTIAL** — Korisnička preferencija i resurs postoje, ali univerzalna prikladnost nije dokazana.
- Implementacija: **NONE** — Profil i GUI izbor nisu implementirani.
- Validacija: **NONE** — Nema map-consistency ni audio/hardware testa.
- Certifikacija: **NONE** — Nije certificiran kao globalni default.

### DEC-003 — User/Unknown Sound zamjenjuje samo korisnik

GUI treba nuditi Factory Sound po vremenskom instrument-segmentu; primjena je eksplicitna, reverzibilna i mijenja samo CC00/CC32/PC.

- Dokaz: **PARTIAL** — Workflow je korisnički zahtjev; K01 Factory identitet je dostupan, ali odluka o zamjeni ovisi o K02 i korisničkoj potvrdi.
- Implementacija: **PARTIAL** — Bounded K03 backend radi za potvrđeni Factory ili User Drum source i exact existing events; UNKNOWN/insertion/shared-bank i GUI workflow ostaju izvan scopea.
- Validacija: **NONE** — Nema writer/verifier testova.
- Certifikacija: **NONE** — Instrument replacement nije autoriziran.

### DEC-004 — G00 ograničeni Evidence Register prije M08

Uvodi se kanonski JSON za G00 registry zapise i generirani Markdown prikaz; MODULE_LOG.md i main.tex ostaju narativna dokumentacija, a napredni dokumenti IDEA_CATALOG.

- Dokaz: **CONFIRMED** — Opseg je eksplicitno potvrđen prije implementacije.
- Implementacija: **PASS** — G00 datoteke i validator su implementirani.
- Validacija: **PASS** — Registry invariant suite prolazi.
- Certifikacija: **PASS** — Odluka je izvršena za registry zapise; nije tvrdnja da je sva projektna dokumentacija generirana iz JSON-a.

### DEC-005 — Moduli slijede dependency DAG, ne jedan linearni lanac

Novi modul smije krenuti kada su svi njegovi deklarirani preduvjeti PASS; nepovezani BLOCKED ili FAIL modul ne zaustavlja drugu neovisnu granu.

- Dokaz: **CONFIRMED** — M05 i K01 su blokirani/neuspješni dok su neovisni M06 i M07 valjano završeni.
- Implementacija: **PASS** — Pravilo je uneseno u projektnu dokumentaciju i registry veze.
- Validacija: **PARTIAL** — Reference modula postoje, ali automatski topološki scheduler još nije implementiran.
- Certifikacija: **PARTIAL** — Certificirana je governance odluka, ne automatizirani dependency engine.

## EVIDENCE

| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |
|---|---|---|---|---|---|---|---|
| `EVID-001` | M06 reproducibility bundle | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-001`, `DATA-003`, `MOD-006`, `RUN-001` |
| `EVID-002` | M07 reproducibility bundle | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-001`, `DATA-003`, `MOD-007`, `TEST-024`, `RUN-002` |

### EVID-001 — M06 reproducibility bundle

Veza između Factory arhiva, službenih stranica, loader koda, pet testova i registriranog test runa.

- Dokaz: **CONFIRMED** — Svi članovi bundlea imaju stabilne ID-jeve i lokalni provenance.
- Implementacija: **PASS** — Povezani M06 modul postoji.
- Validacija: **PASS** — Povezani testovi i corpus run prolaze.
- Certifikacija: **PASS** — Dovoljno za ograničeni M06 PASS, ne za druge optimizacijske funkcije.

### EVID-002 — M07 reproducibility bundle

Veza između Factory arhiva, službenih stranica, classifier koda, 14 unit testova i reproducibilnog corpus testa.

- Dokaz: **CONFIRMED** — Svi članovi bundlea imaju stabilne ID-jeve i lokalni provenance.
- Implementacija: **PASS** — Povezani M07 modul postoji.
- Validacija: **PASS** — Povezani unit testovi i corpus smoke test prolaze.
- Certifikacija: **PASS** — Dovoljno za ograničeni read-only M07 PASS; ne autorizira Enhance.

## ISSUE

| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |
|---|---|---|---|---|---|---|---|
| `ISSUE-001` | Headless GUI display blocker — solved with local Xvfb | `SUPERSEDED` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-005`, `TEST-003`, `TEST-049` |
| `ISSUE-002` | K01 produkcijski modul i test — resolved | `SUPERSEDED` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-009`, `MOD-017`, `DATA-001`, `DATA-009`, `TEST-050` |
| `ISSUE-003` | Fox Shuffle Break konflikt broja taktova | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-003`, `MOD-006`, `TEST-007` |
| `ISSUE-004` | Valja RAR5 sadržaj nije analiziran | `BLOCKED` | `CONFIRMED` | `BLOCKED` | `BLOCKED` | `NONE` | `DATA-005` |
| `ISSUE-005` | M01 Format 2 test gap — resolved | `SUPERSEDED` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-001`, `MOD-002`, `TEST-047` |
| `ISSUE-006` | Dvostruka SMF parser logika — parity guard implemented | `SUPERSEDED` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-001`, `MOD-006`, `TEST-048`, `DATA-003` |
| `ISSUE-007` | M07 score nije kalibrirana pouzdanost | `ACTIVE` | `CONFIRMED` | `PASS` | `PARTIAL` | `NONE` | `MOD-007` |
| `ISSUE-008` | DNA Factory container duplikat — resolved | `SUPERSEDED` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-003`, `DATA-004`, `MOD-029`, `TEST-061` |
| `ISSUE-009` | M07 statistical calibration lacks human ground truth | `BLOCKED` | `CONFIRMED` | `BLOCKED` | `BLOCKED` | `NONE` | `MOD-007`, `MOD-029`, `DATA-004`, `TEST-061` |

### ISSUE-001 — Headless GUI display blocker — solved with local Xvfb

Sistemski display ne postoji, ali workspace-only Xvfb iz službenih Debian paketa omogućuje stvarni Tk runtime test bez sistemske instalacije.

- Dokaz: **CONFIRMED** — Tk root i MidiEnhancerApp 1360x900 s 16 kartica pokrenuti su na :102; paketni i patched-binary hashovi zapisani su u runtime manifestu i audit izvještaju.
- Implementacija: **PASS** — Lokalni virtual-display runtime postoji u ignoriranom loaded-data području; sistemski paketi nisu mijenjani.
- Validacija: **PASS** — TEST-049 prolazi pod DISPLAY=:102.
- Certifikacija: **PARTIAL** — Automatizirani GUI runtime blocker je zatvoren; native korisnički desktop test ostaje release zadatak.

### ISSUE-002 — K01 produkcijski modul i test — resolved

Raniji nedostatak K01 generatora, kanonskog JSON-a, lookup modula i testa potpunosti zatvoren je reproducibilnim artefaktima.

- Dokaz: **CONFIRMED** — MOD-009, MOD-017, DATA-009 i TEST-050 postoje u aktualnom snapshotu.
- Implementacija: **PASS** — K01 read-only implementacija i generator su prisutni.
- Validacija: **PASS** — Dedicated K01 suite prolazi i generator --check potvrđuje kanonski JSON.
- Certifikacija: **PASS** — Zatvoren je konkretni missing-artifact issue; certifikacija ostaje ograničena K01 scopeom.

### ISSUE-003 — Fox Shuffle Break konflikt broja taktova

Fox Shuffle 1_Break.mid sadrži konfliktne oznake 1 Bar i 5 Bars te je blokiran za vremensku analizu.

- Dokaz: **CONFIRMED** — Konflikt je reproducibilno detektiran u Factory arhivu.
- Implementacija: **PASS** — M06 ga čuva i blokira umjesto nagađanja.
- Validacija: **PASS** — Corpus provjera potvrđuje sigurno ponašanje.
- Certifikacija: **PASS** — Certificirano je blokiranje, ne izbor jedne konfliktne vrijednosti.

### ISSUE-004 — Valja RAR5 sadržaj nije analiziran

Arhiv je identificiran, ali njegov MIDI sadržaj nije dokazano raspakiran ili analiziran.

- Dokaz: **CONFIRMED** — Postoji samo dokaz arhiva i hasha.
- Implementacija: **BLOCKED** — Nema podržanog RAR5 loadera.
- Validacija: **BLOCKED** — Nema corpus testova.
- Certifikacija: **NONE** — Tvrdnje o sadržaju nisu dopuštene.

### ISSUE-005 — M01 Format 2 test gap — resolved

Raniji nedostatak zasebnog SMF Format 2 testa zatvoren je neovisnim sequence-timeline, display, optional-analyzer i dual-parser strukturnim testovima.

- Dokaz: **CONFIRMED** — tests/test_midi_format2.py sadrži četiri izravna testa i registriran je kao TEST-047.
- Implementacija: **PASS** — Format 2 više se ne prikazuje kao Format 1 niti spaja u lažnu globalnu tempo/trajanje vremensku liniju.
- Validacija: **PASS** — Namjenski Format 2 suite prolazi.
- Certifikacija: **PARTIAL** — Zatvoren je konkretni Format 2 gap; opći cross-parser parity ostaje zaseban ISSUE-006.

### ISSUE-006 — Dvostruka SMF parser logika — parity guard implemented

Parser putanje ostaju odvojene, ali sada imaju valid/malformed sintetički parity i izravni core-fingerprint test nad svih 3.211 Factory MIDI datoteka.

- Dokaz: **CONFIRMED** — TEST-048 uspoređuje strukturu, događaje, note, tempo/metar/key, programe, kontrolere, pitch bend, hash i završne tickove.
- Implementacija: **PASS** — Implementiran je dopušteni alternativni parity pristup te jednake header/division/EOT strukturne kapije u oba parsera.
- Validacija: **PASS** — 5 parity testova i 3.223 subtesta prolaze; 3.211/3.211 Factory datoteka ima isti core fingerprint.
- Certifikacija: **PARTIAL** — Certificiran je core parity na registriranom Factory korpusu i sintetičkim rubovima; parseri još nisu fizički objedinjeni.

### ISSUE-007 — M07 score nije kalibrirana pouzdanost

Brojčani rezultati M07 su heuristički bodovi pravila, a ne empirijski kalibrirane vjerojatnosti.

- Dokaz: **CONFIRMED** — Classifier koristi fiksne pragove i bodove bez označenog calibration skupa.
- Implementacija: **PASS** — Heuristički score postoji i prikazuje se kao dio read-only rezultata.
- Validacija: **PARTIAL** — Grananja su testirana, ali score nije kalibriran prema labeliranom golden skupu.
- Certifikacija: **NONE** — Score se ne smije predstavljati kao statistička vjerojatnost.

### ISSUE-008 — DNA Factory container duplikat — resolved

Unutarnji Split Factory Styles.zip u DATA-004 ima isti SHA-256 kao DATA-003 i mora se isključiti iz Gold/DNA trening i evaluacijskih brojki.

- Dokaz: **CONFIRMED** — Unutarnji hash ffb95c...d8f5e jednak je registriranom DATA-003 hashu.
- Implementacija: **PASS** — G02 automatski prepoznaje exact Factory container hash i isključuje ga iz Gold evaluacije.
- Validacija: **PASS** — TEST-061 potvrđuje jednu exclusion stavku i nula cross-source individual MIDI hashova.
- Certifikacija: **PASS** — Konkretni container contamination issue je zatvoren.

### ISSUE-009 — M07 statistical calibration lacks human ground truth

Deduplicirani Gold MIDI nema neovisne per-part role labele, pa M07 heuristic confidence ne smije biti prikazan kao statistička vjerojatnost.

- Dokaz: **CONFIRMED** — G02 potvrđuje strukturalno neovisan evaluation source, ali u arhivu nema human-verified role annotation datoteke.
- Implementacija: **BLOCKED** — Calibration model/metrics su blokirani dok se ne doda zaseban ručno označen label manifest.
- Validacija: **BLOCKED** — Accuracy, precision, recall i probability calibration se ne mogu izračunati bez ground trutha.
- Certifikacija: **NONE** — M07 confidence ostaje heuristic score.

## MODULE

| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |
|---|---|---|---|---|---|---|---|
| `MOD-001` | Standard MIDI parser | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `TEST-001`, `TEST-047`, `ISSUE-005`, `ISSUE-006`, `TEST-048` |
| `MOD-002` | Mapiranje 16 slotova | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `TEST-001`, `MOD-001`, `TEST-047` |
| `MOD-003` | Instrument i uloga | `ACTIVE` | `PARTIAL` | `PASS` | `PASS` | `NONE` | `TEST-002` |
| `MOD-004` | Guitar uloge | `ACTIVE` | `PARTIAL` | `PASS` | `PASS` | `NONE` | `TEST-002`, `MOD-003` |
| `MOD-005` | Desktop GUI | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `TEST-003`, `TEST-049`, `ISSUE-001`, `MOD-026`, `TEST-058` |
| `MOD-006` | Style Works Loader | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-001`, `DATA-003`, `TEST-004`, `TEST-005`, `TEST-006`, `TEST-007`, `TEST-008`, `EVID-001`, `TEST-048` |
| `MOD-007` | Context Classifier | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-001`, `DATA-003`, `TEST-009`, `TEST-010`, `TEST-011`, `TEST-012`, `TEST-013`, `TEST-014`, `TEST-015`, `TEST-016`, `TEST-017`, `TEST-018`, `TEST-019`, `TEST-020`, `TEST-021`, `TEST-022`, `TEST-024`, `EVID-002`, `ISSUE-007` |
| `MOD-008` | Measure/Phrase Analyzer | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-006`, `MOD-007`, `TEST-026`, `TEST-027`, `TEST-028`, `TEST-029`, `TEST-030`, `TEST-044`, `RUN-007`, `DEC-001` |
| `MOD-009` | Pa800 K01 Factory Registry | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-001`, `DATA-009`, `MOD-017`, `TEST-050`, `ISSUE-002` |
| `MOD-010` | Evidence Registry Foundation | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `TEST-023`, `TEST-025`, `DEC-004` |
| `MOD-011` | Instrument Identity Resolver | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-009`, `MOD-014`, `TEST-044`, `TEST-051`, `DATA-003`, `DEC-003` |
| `MOD-012` | K03 verified Factory Sound Replacement backend | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-009`, `MOD-011`, `MOD-018`, `MOD-019`, `MOD-020`, `MOD-023`, `MOD-024`, `MOD-025`, `TEST-057`, `DEC-003`, `MOD-026`, `TEST-058`, `TEST-049` |
| `MOD-013` | Instrument Measurement Engine | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-006`, `MOD-007`, `MOD-008`, `TEST-031`, `TEST-032`, `TEST-033`, `TEST-034`, `TEST-035`, `TEST-036`, `TEST-044`, `RUN-007`, `DEC-001` |
| `MOD-014` | Instrument Segmenter | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-006`, `MOD-007`, `MOD-009`, `TEST-037`, `TEST-038`, `TEST-039`, `TEST-040`, `TEST-041`, `TEST-042`, `TEST-043`, `TEST-044`, `RUN-007`, `DEC-001` |
| `MOD-015` | Workspace Persistence Probe | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `TEST-046`, `RUN-009` |
| `MOD-016` | Repository Inventory Auditor | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-010`, `TEST-045`, `MOD-015`, `RUN-009` |
| `MOD-017` | K01 reproducible generator | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-001`, `DATA-009`, `DATA-010`, `MOD-009`, `TEST-050` |
| `MOD-018` | Immutable Change Plan Foundation | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `TEST-052`, `MOD-019`, `DEC-003`, `MOD-028`, `TEST-060` |
| `MOD-019` | Suggest Policy Engine | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-018`, `TEST-053`, `DEC-003`, `MOD-028`, `TEST-060` |
| `MOD-020` | K03 user-selected Factory replacement Proposal Builder | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-009`, `MOD-011`, `MOD-018`, `MOD-019`, `MOD-012`, `TEST-054`, `DEC-003` |
| `MOD-021` | Windows local installer | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `DATA-010`, `TEST-055`, `MOD-022` |
| `MOD-022` | Windows GUI launcher | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-021`, `TEST-055`, `MOD-005` |
| `MOD-023` | In-memory byte-preserving Change Engine | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-018`, `MOD-019`, `MOD-020`, `MOD-024`, `TEST-056`, `MOD-030`, `TEST-062` |
| `MOD-024` | Independent Change Verifier | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-018`, `MOD-023`, `TEST-056`, `MOD-030`, `TEST-062` |
| `MOD-025` | Atomic Verified MIDI Writer | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-012`, `MOD-023`, `MOD-024`, `TEST-057`, `MOD-030`, `TEST-062` |
| `MOD-026` | Bounded GUI Change Workflow Controller | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-005`, `MOD-012`, `MOD-020`, `MOD-023`, `MOD-024`, `MOD-025`, `TEST-058` |
| `MOD-027` | Factory Contextual Profile Builder | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-003`, `MOD-007`, `MOD-009`, `MOD-011`, `MOD-013`, `MOD-014`, `TEST-059`, `DEC-001`, `MOD-028`, `TEST-060` |
| `MOD-028` | Exact Contextual Profile Velocity Suggestor | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-007`, `MOD-018`, `MOD-019`, `MOD-023`, `MOD-027`, `TEST-060`, `DEC-001`, `MOD-030`, `TEST-062` |
| `MOD-029` | Gold Dataset Contamination Guard | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-003`, `DATA-004`, `ISSUE-008`, `ISSUE-009`, `TEST-061` |
| `MOD-030` | Specialized S01 Note On Velocity Apply Scope | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-023`, `MOD-024`, `MOD-025`, `MOD-028`, `TEST-062` |

### MOD-001 — Standard MIDI parser

Read-only SMF parser za formate 0/1/2; Format 2 čuva neovisne sekvence i ne izmišlja globalni tempo ili trajanje.

- Dokaz: **CONFIRMED** — Kod eksplicitno razlikuje Format 2 independent-sequence semantiku i zadržava globalni rezultat PARTIAL/read-only.
- Implementacija: **PASS** — Formati 0/1/2, trackovi, događaji, note i zasebne Format 2 vremenske linije implementirani su u ugrađenom parseru.
- Validacija: **PASS** — Format 0/1 regresije, četiri Format 2 testa i pet parser-parity testova prolaze; Factory parity pokriva svih 3.211 datoteka.
- Certifikacija: **PARTIAL** — Certificiran je ograničeni read-only SMF 0/1/2 i Factory core-parity scope; puni SMF standard, sve SMPTE glazbene operacije i writer nisu certificirani.
- Putanja: `midi_enhancer.py`

### MOD-002 — Mapiranje 16 slotova

Mapira Format 0 kanale, Format 1 fizičke trackove i Format 2 neovisne sekvence na 16 prikaznih slotova bez međusobnog spajanja.

- Dokaz: **CONFIRMED** — Opći MIDI model i implementacija su pregledljivi u kodu.
- Implementacija: **PASS** — build_display_tracks je implementiran.
- Validacija: **PASS** — Pokriveno testom formata 0 i 1.
- Certifikacija: **NONE** — Nije Pa800-specifično certificirano.
- Putanja: `midi_instruments.py`

### MOD-003 — Instrument i uloga

GM program, percussion, raspon i polifonija daju heurističku procjenu instrumenta i uloge.

- Dokaz: **PARTIAL** — Heuristika je eksplicitna, ali nije činjenica o stvarnom zvuku.
- Implementacija: **PASS** — infer_instrument i infer_role su implementirani.
- Validacija: **PASS** — Relevantna guitar grananja imaju automatski test.
- Certifikacija: **NONE** — Heuristička klasifikacija nije certificirani identitet instrumenta.
- Putanja: `midi_instruments.py`

### MOD-004 — Guitar uloge

Razlikuje rhythm, solo i power-chord guitar heuristike.

- Dokaz: **PARTIAL** — Pravila su heuristike i nisu Guitar Mode dekoder.
- Implementacija: **PASS** — Guitar role grane su implementirane.
- Validacija: **PASS** — test_guitar_roles prolazi.
- Certifikacija: **NONE** — Nema Pa800 Guitar Mode certifikacije.
- Putanja: `midi_instruments.py`

### MOD-005 — Desktop GUI

Tk desktop GUI za Analyze i bounded user-selected Factory replacement preview/approve/verify/save/rollback workflow.

- Dokaz: **CONFIRMED** — Tk 8.6 i puni MidiEnhancerApp prozor pokrenuti su na workspace-only Xvfb runtimeu iz službenih Debian paketa.
- Implementacija: **PASS** — GUI import, 16 kartica, Format 0/1/2, Factory dialog, exact diff/risk, USER approval, V01 status, W01 save i rollback su implementirani.
- Validacija: **PASS** — TEST-049 stvarno renderira Tk i prolazi Analyze, Format 2 te puni Factory preview→verify→save→rollback tok; TEST-058 provjerava backend bez Tk.
- Certifikacija: **PARTIAL** — Certificiran je automatizirani virtual-display bounded GUI scope; native Windows UX/accessibility još čeka korisnika.
- Putanja: `midi_gui.py`

### MOD-006 — Style Works Loader

Read-only ZIP/MIDI model, Style/Element/CV/role, vremenski prozor i CC00.CC32.PC praćenje.

- Dokaz: **CONFIRMED** — Pa800 stranice 114–116 i 134–135 te Factory corpus podupiru ograničeni scope.
- Implementacija: **PASS** — Loader i nepromjenjivi modeli su implementirani.
- Validacija: **PASS** — Pet loader testova i puni corpus test prolaze.
- Certifikacija: **PASS** — Certificiran samo read-only M06 scope na registriranom Factory arhivu.
- Putanja: `style_loader.py`

### MOD-007 — Context Classifier

Generički feature model i Style adapter za strukturalnu ulogu, funkciju, encoding kandidat i sigurnosnu politiku.

- Dokaz: **CONFIRMED** — Pa800 stranice 112, 116, 118–120 i 134–135 te corpus smoke test podupiru read-only scope.
- Implementacija: **PASS** — Classifier i Style adapter su implementirani.
- Validacija: **PASS** — Četrnaest unit testova i reproducibilni puni corpus test prolaze.
- Certifikacija: **PASS** — Certificiran samo read-only M07 scope; ne autorizira Enhance.
- Putanja: `context_classifier.py`

### MOD-008 — Measure/Phrase Analyzer

Analyze-only tempo/metar timeline, položaj događaja u taktu, egzaktna ponavljanja mjera i konzervativni kandidati granica fraza.

- Dokaz: **CONFIRMED** — Timeline činjenice izvode se iz potvrđenih SMF meta događaja; frazne granice ostaju jasno označeni heuristički kandidati.
- Implementacija: **PASS** — Generička jezgra i Style adapter implementirani su nad nepromjenjivim M06 modelom bez writer funkcija.
- Validacija: **PASS** — Devet M08 testova pokriva tempo/metar, fazu prozora, potpuni note potpis ponavljanja, konflikte unutar/izvan prozora i Style adapter; puni Factory corpus test također prolazi.
- Certifikacija: **PASS** — Certificiran je samo read-only M08 scope; timing, Humanize i strumming izmjene nisu autorizirane.
- Putanja: `measure_phrase_analyzer.py`

### MOD-009 — Pa800 K01 Factory Registry

Read-only puni Factory Sound/Drum Kit lookup po točnoj CC00.CC32.PC adresi.

- Dokaz: **CONFIRMED** — Generator prihvaća samo službeni manual hash; Sound tablice su tiskane 275–283/PDF 279–287, Drum Kit tablica tiskana 295/PDF 299.
- Implementacija: **PASS** — Kanonski JSON, immutable lookup, remap evidence i User-range lokacijska provjera su implementirani bez MIDI izmjene.
- Validacija: **PASS** — Generator reproducira 1.006 Sound + 65 Drum Kit = 1.071 jedinstvenu adresu; sedam namjenskih testova prolazi.
- Certifikacija: **PASS** — Certificiran je samo K01 read-only Factory identity scope za točnu punu adresu i potvrđeni manual; K02 rezolucija nije uključena.
- Putanja: `pa800_registry.py`

### MOD-010 — Evidence Registry Foundation

Strojno provjerljiv master registry s determinističkim Markdown prikazom.

- Dokaz: **CONFIRMED** — Scope i četiri neovisne statusne osi potvrđeni su projektnom odlukom.
- Implementacija: **PASS** — JSON registry, schema, validator i generator su implementirani standardnom bibliotekom.
- Validacija: **PASS** — Suite provjerava ID namespace, IDEA izolaciju, lokalne putanje, hashove, test prisutnost, reference i aktualnost generiranog prikaza.
- Certifikacija: **PASS** — Certificiran je samo G00 format i referencijalni integritet, ne istinitost svake buduće domenske tvrdnje.
- Putanja: `registry/build_registry.py`

### MOD-011 — Instrument Identity Resolver

Read-only K02 resolver koji povezuje stvarne M10 segmente s K01 exact/remap/User dokazima bez izmjene segmenta ili MIDI-ja.

- Dokaz: **CONFIRMED** — Svaki rezultat navodi M10 adresu, K01 entry/remap dokaz, stabilni rule ID, traženu i ciljnu adresu kada postoji.
- Implementacija: **PASS** — Implementirani su svi ugovoreni statusi: FACTORY_CONFIRMED, USER_SLOT_CONFIRMED, UNKNOWN, CONFLICT, INCOMPLETE_ADDRESS i NO_PROGRAM.
- Validacija: **PASS** — Šest dedicated testova i puni Factory corpus od 82.917 stvarnih M10 segmenata prolaze s fiksnim raspodjelama i digestom.
- Certifikacija: **PASS** — Certificiran je ograničeni read-only K02 identity scope; K03 replacement i MIDI izmjene nisu autorizirani.
- Putanja: `instrument_identity_resolver.py`

### MOD-012 — K03 verified Factory Sound Replacement backend

Bounded user-selected exact-event K03 pipeline dostupan kroz programatski backend i automatizirani Tk GUI workflow.

- Dokaz: **CONFIRMED** — Backend zahtijeva K01/K02 identitet, USER selection/approval/request, exact event diff, Verifier PASS i no-overwrite writer gate.
- Implementacija: **PASS** — Proposal, in-memory change, rollback, independent verification, atomic new-file MIDI/JSON save i filesystem rollback su implementirani.
- Validacija: **PASS** — TEST-057 filesystem backend, TEST-058 workflow i prošireni TEST-049 stvarni Tk end-to-end tok prolaze.
- Certifikacija: **PASS** — Certificiran je bounded user-selected existing-event K03 backend/virtual-GUI scope; automatski Enhance i native Windows UX nisu uključeni.
- Putanja: `verified_writer.py`

### MOD-013 — Instrument Measurement Engine

Read-only zajedničke statistike nota, velocityja, trajanja, gustoće, polifonije, kontrolera te profila mjera i fraza.

- Dokaz: **CONFIRMED** — Brojčane metrike deterministički se izvode iz M06 događaja; M07 kontekst i M08 fraze zadržavaju vlastite statuse i zaštite.
- Implementacija: **PASS** — Generički engine i Style adapter implementirani su bez Suggest, Change ili writer putanje.
- Validacija: **PASS** — Devet M09 testova pokriva metrike, aftertouch, timeline provenance, višetrack zaštitu, potvrđeni density prozor i Style adapter; puni Factory corpus test također prolazi.
- Certifikacija: **PASS** — Certificiran je samo read-only M09 mjerni scope; statistike nisu preporuka niti dopuštenje za izmjenu.
- Putanja: `instrument_measurement_engine.py`

### MOD-014 — Instrument Segmenter

Read-only segmentacija po MIDI kanalu i Program Change granicama uz CC00/CC32 snapshot, M09 profil i zaštitu nota preko granice.

- Dokaz: **CONFIRMED** — Granice i adrese deterministički se izvode iz redoslijeda Bank Select i Program Change događaja; identity ostaje UNRESOLVED.
- Implementacija: **PASS** — Generički segmenter i Style adapter implementirani su bez Factory/User klasifikacije i bez writer putanje.
- Validacija: **PASS** — Devet M10 testova pokriva adrese, staged bank promjene, zatvorene i otvorene note preko granice, globalne ordinale, cross-track neodređenost i Style adapter; puni Factory corpus test također prolazi.
- Certifikacija: **PASS** — Certificiran je samo read-only M10 segmentacijski scope; identitet instrumenta i zamjena nisu autorizirani.
- Putanja: `instrument_segmenter.py`

### MOD-015 — Workspace Persistence Probe

Provjerava da checkpointirani lokalni Git commit te nova Python i testna datoteka ostaju prisutni i bajtovno jednaki u kasnijem workspace turnu.

- Dokaz: **CONFIRMED** — Checkpoint commit 70bc744 i četiri zabilježena artefakta ponovno su provjereni nakon sljedeće korisničke poruke; Git ancestry i svi SHA-256 zbrojevi odgovaraju.
- Implementacija: **PASS** — Probe, checkpoint i integracijski test trajno su prisutni u Git snapshotu.
- Validacija: **PASS** — Cross-turn izvršenje 2026-08-14 potvrđuje commit, Python datoteke i testove bez razlike.
- Certifikacija: **PASS** — Certificiran je samo workspace/Git persistence scope za checkpoint 16ebf358-7bbd-4810-9215-d8e2928ba6c7.
- Putanja: `tools/workspace_persistence_probe.py`

### MOD-016 — Repository Inventory Auditor

Uspoređuje implementirane MODULE/TEST zapise i MODULE_LOG ID-jeve s radnim stablom i git ls-tree popisom odabranog commita.

- Dokaz: **CONFIRMED** — Nalazi se izvode deterministički iz master registra, MODULE_LOG tablice, worktreea i Git treea.
- Implementacija: **PASS** — CLI, JSON/Markdown izvještaj i testovi trajno su prisutni nakon A01 cross-turn provjere.
- Validacija: **PASS** — Namjenski testovi prolaze, a aktualni inventar ima 0 errora i 0 warninga za dokumentirane produkcijske/testne/generatorske artefakte.
- Certifikacija: **PASS** — Certificirana je samo prisutnost dokumentiranih artefakata u odabranom Git treeu/worktreeu; ne glazbena ispravnost.
- Putanja: `tools/repository_inventory.py`

### MOD-017 — K01 reproducible generator

Iz potvrđenog Pa800 manuala generira kanonski Factory registry i odbija drugi hash, page count, extractor ili broj zapisa.

- Dokaz: **CONFIRMED** — Izvorne stranice, manual hash, pypdf wheel hash i očekivani brojevi ugrađene su kao hard gate.
- Implementacija: **PASS** — Generator, --check način, parser Sound/Drum/remap/User redaka i deterministički renderer su implementirani.
- Validacija: **PASS** — TEST-050 reproducira kanonski JSON bajt-po-bajt i odbija izmijenjeni manual.
- Certifikacija: **PASS** — Certificiran je reproducibilni K01 generator za točno registrirani manual/extractor.
- Putanja: `registry/generate_pa800_factory.py`

### MOD-018 — Immutable Change Plan Foundation

Deterministički Suggest-phase plan s exact event-field mutacijama, dokazima, mjerenjima, rizikom i eksplicitnim USER odlukama; nema Apply ni writer.

- Dokaz: **CONFIRMED** — Plan model izravno provodi projektne kapije za stabilne ID-jeve, exact diff, evidence status, confidence i odluke.
- Implementacija: **PASS** — Immutable proposal/plan/decision modeli, deterministic JSON i strogi validator su implementirani.
- Validacija: **PASS** — Šest dedicated testova pokriva determinističnost, odluke, confidence, duplikate, no-op i apply zabranu.
- Certifikacija: **PASS** — Certificiran je samo P01 data/validation scope; nema MIDI primjene.
- Putanja: `change_plan.py`

### MOD-019 — Suggest Policy Engine

Provjerava named/versioned pravilo, rizik, evidence i exact source event snapshot prije uključivanja prijedloga u Suggest plan.

- Dokaz: **CONFIRMED** — Policy rezultat navodi verdict, razloge i provjerene mutation ID-jeve; apply_authorized je uvijek false.
- Implementacija: **PASS** — Rule registry, source-event verification, blocking evidence/risk kapije i plan builder su implementirani.
- Validacija: **PASS** — Šest dedicated testova pokriva allowed/blocked, tampered/missing event, inferred opt-in, version/risk i duplicate rule.
- Certifikacija: **PASS** — Certificiran je samo Suggest policy scope; user confirmation i budući Change Engine ostaju odvojeni.
- Putanja: `policy_engine.py`

### MOD-020 — K03 user-selected Factory replacement Proposal Builder

Gradi Suggest-only plan za user-selected exact K01 target preko postojećih ekskluzivnih CC00/CC32/PC događaja; nema writer.

- Dokaz: **CONFIRMED** — Prijedlog povezuje stvarni M10/K02 segment, K01 cilj, USER_SELECTION i exact source-event snapshot.
- Implementacija: **PASS** — Builder, compatibility/shared-bank/insertion kapije i K03 named policy pravilo su implementirani.
- Validacija: **PASS** — Sedam dedicated testova pokriva exact/same-bank, exclusive bank change, shared bank block, User Drum, status/type/target block i approval bez Apply.
- Certifikacija: **PASS** — Certificiran je samo K03-P Suggest proposal scope; MIDI replacement backend nije autoriziran.
- Putanja: `k03_sound_replacement.py`

### MOD-021 — Windows local installer

install.bat provjerava Python/Tk, kreira lokalni .venv, instalira pinned lokalni K01 wheel, nudi optional biblioteke i izvršava registry smoke checks.

- Dokaz: **CONFIRMED** — Skripta i statički provjerljive sigurnosne naredbe prisutne su u Git snapshotu.
- Implementacija: **PASS** — Windows batch installer s minimal načinom, error gateovima i bez sistemske package instalacije je implementiran.
- Validacija: **PASS** — TEST-055 potvrđuje CRLF, venv izolaciju, local/hash-pinned K01 instalaciju i smoke naredbe.
- Certifikacija: **PARTIAL** — Statički scope je potvrđen; stvarno Windows izvršavanje čeka korisnički računar.
- Putanja: `install.bat`

### MOD-022 — Windows GUI launcher

run.bat pokreće GUI samo iz lokalnog .venv i pruža console/check dijagnostičke načine.

- Dokaz: **CONFIRMED** — Launcher putanje, failure poruke i načini rada prisutni su u Git snapshotu.
- Implementacija: **PASS** — Default pythonw GUI, console i check načini su implementirani bez MIDI output naredbi.
- Validacija: **PASS** — TEST-055 potvrđuje venv-only launch i odsustvo destruktivnih/Enhance naredbi.
- Certifikacija: **PARTIAL** — Statički scope je potvrđen; stvarno Windows/Tk pokretanje čeka korisnički računar.
- Putanja: `run.bat`

### MOD-023 — In-memory byte-preserving Change Engine

Byte-preserving working-copy engine za CC/PC i specialized S01 Note On velocity uz explicit rule authorization i switch/RX risk acknowledgement.

- Dokaz: **CONFIRMED** — Svaka primjena veže plan/request/source SHA, exact raw event snapshot i apsolutni byte offset.
- Implementacija: **PASS** — In-memory byte patch, source reparse, applied log, PENDING_VERIFICATION i exact rollback su implementirani; nema filesystem write.
- Validacija: **PASS** — TEST-056 pokriva approved/request gate, CC/PC patch, running status, tampered source i rollback.
- Certifikacija: **PASS** — Certificiran je samo C01 in-memory working-copy/rollback scope; save nije autoriziran.
- Putanja: `change_engine.py`

### MOD-024 — Independent Change Verifier

Independent verifier za exact byte/event diff, uključujući neovisnu V02 specialized authorization i 8-unit/1..127 kapiju.

- Dokaz: **CONFIRMED** — Verifier samostalno locira event data bajtove i ne koristi Change Engine offset helper.
- Implementacija: **PASS** — Struktura, event set, immutable polja, exact data diff, applied log, hash, reparse i unauthorized-byte kapije su implementirani.
- Validacija: **PASS** — TEST-056 potvrđuje PASS put i blokira extra byte, forged applied offset i truncated output.
- Certifikacija: **PASS** — Certificiran je V01 in-memory verification scope; filesystem writer nije uključen.
- Putanja: `change_verifier.py`

### MOD-025 — Atomic Verified MIDI Writer

Prihvaća samo V01 PASS verified bytes, ponovno provjerava source file, objavljuje novi _enhanced MIDI i JSON bez overwrite-a te podržava hash-guarded filesystem rollback.

- Dokaz: **CONFIRMED** — Writer veže source/plan/request/execution/verification hashove i statusne kapije u JSON report.
- Implementacija: **PASS** — Same-directory temp+fsync, atomic hard-link create-if-absent, two-file cleanup, source recheck i guarded rollback su implementirani.
- Validacija: **PASS** — TEST-057 pokriva save/report, no-overwrite, bad source/name/verifier, second-publish failure cleanup i rollback/tamper.
- Certifikacija: **PASS** — Certificiran je W01 lokalni filesystem scope na testiranom filesystemu; GUI/release packaging nije uključeno.
- Putanja: `verified_writer.py`

### MOD-026 — Bounded GUI Change Workflow Controller

Testabilni non-Tk servis koji orkestrira M10/K02 eligible segmente, K01 ciljeve, K03-P preview, USER approval, C01/V01, W01 save i rollback.

- Dokaz: **CONFIRMED** — Controller izlaže samo explicit eligible segment/target opcije i provodi strogi redoslijed faza bez automatskog prijedloga.
- Implementacija: **PASS** — Load/options/preview/approve/verify/save/rollback state machine je implementiran izvan Tk koda.
- Validacija: **PASS** — TEST-058 pokriva full backend tok, stage/USER gates, Unknown exclusion i shared-bank blokiranje.
- Certifikacija: **PASS** — Certificiran je bounded G01 backend controller scope; automatski Suggest/Enhance nije uključen.
- Putanja: `gui_change_workflow.py`

### MOD-027 — Factory Contextual Profile Builder

Streamingom agregira empirijske Factory profile bez miješanja source kind, K01 adrese, M07 funkcije, Elementa, CV-a, strukturne uloge, encodinga ili fixed kandidata.

- Dokaz: **CONFIRMED** — Ulaz je registrirani Factory corpus; svaki profil čuva K01 identitet, source members i derived empirical status.
- Implementacija: **PASS** — Observation/provenance modeli, strogi contextual key, distribucije, deterministic renderer/digest i Factory archive builder su implementirani.
- Validacija: **PASS** — TEST-059 potvrđuje izolaciju i puni corpus: 29.603 observacije, 13.821 profil, digest 33a9b426… i nepromijenjen ZIP.
- Certifikacija: **PASS** — Certificiran je R01 read-only Factory empirical reference scope; profil ne autorizira Suggest ili Change.
- Putanja: `contextual_profile_builder.py`

### MOD-028 — Exact Contextual Profile Velocity Suggestor

Exact R01 key matcher i Suggest-only bounded Note On velocity outlier pravilo bez fallbacka i bez C01 Apply podrške.

- Dokaz: **CONFIRMED** — Prijedlog zahtijeva exact source/address/function/element/CV/role/encoding/fixed key i minimalnu empirical potporu.
- Implementacija: **PASS** — Matcher statusi, named config, context/user gates, p10-p90 bounded-step outlier plan i P02 integracija su implementirani.
- Validacija: **PASS** — TEST-060 pokriva exact suggestion, sve key mismatch grane, support/context/user gate, no-outlier/too-many i invalid config.
- Certifikacija: **PASS** — Certificiran je S01 Suggest-only scope; Note On Apply je namjerno unsupported i automatic Enhance nije autoriziran.
- Putanja: `profile_suggest_engine.py`

### MOD-029 — Gold Dataset Contamination Guard

Validira Factory/DNA hashove i ZIP putanje, isključuje exact Factory container, deduplicira Gold po sadržaju i stvara source-disjoint train/evaluation manifest.

- Dokaz: **CONFIRMED** — Guard koristi pune archive/member SHA-256 hashove i byte-preserving SMF validaciju bez ekstrakcije.
- Implementacija: **PASS** — Safe ZIP path, outer container classification, Gold validation/dedup, Factory overlap guard, manifest i calibration blocker su implementirani.
- Validacija: **PASS** — TEST-061 reproducira 3211/3187 Factory, 182/181 Gold, 1 excluded container, 0 cross overlap i digest 62a0ac2c….
- Certifikacija: **PASS** — Certificiran je G02 structural contamination/split scope; M07 accuracy calibration nije uključena.
- Putanja: `gold_dataset_guard.py`

### MOD-030 — Specialized S01 Note On Velocity Apply Scope

Stvara specialized USER execution request za odobreni S01 plan samo uz zaseban unknown velocity-switch/RX risk acknowledgement; C01/V01 neovisno provode 1..127, max 8 i max 32 kapije.

- Dokaz: **CONFIRMED** — Request bilježi authorized S01 rule ID i eksplicitni UNKNOWN_VELOCITY_SWITCH_RX_THRESHOLDS acknowledgement u execution/report lancu.
- Implementacija: **PASS** — Specialized request validator i C01/V01 Note On safety grane su implementirane; generic request ostaje blokiran.
- Validacija: **PASS** — TEST-062 pokriva full apply/verify/save/rollback, missing ack/generic block, zero/large block i forged-ack verifier FAIL.
- Certifikacija: **PASS** — Certificiran je samo explicit USER-acknowledged bounded S01 velocity scope; automatic Apply/Enhance nije autoriziran.
- Putanja: `velocity_change_scope.py`

## RESOURCE

| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |
|---|---|---|---|---|---|---|---|
| `DATA-001` | Korg Pa800 2.0 User's Manual (E12) | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `NOT_APPLICABLE` | — |
| `DATA-002` | Korg Pa800 2.0 Advanced Edit Manual (E5) | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `NOT_APPLICABLE` | — |
| `DATA-003` | Split Factory Styles corpus | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `NONE` | `TEST-006`, `EVID-001` |
| `DATA-004` | DNA premium MIDI corpus | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `DEC-001`, `ISSUE-008`, `TEST-025`, `MOD-029`, `TEST-061`, `ISSUE-009` |
| `DATA-005` | Valja MIDI corpus | `BLOCKED` | `CONFIRMED` | `BLOCKED` | `BLOCKED` | `NONE` | `ISSUE-004` |
| `DATA-006` | Oscilatori drum-kit bilješke | `ACTIVE` | `CONFIRMED` | `NONE` | `NONE` | `NONE` | `DEC-002` |
| `DATA-007` | Napredni spisak mogućnosti | `IDEA_CATALOG` | `CONFIRMED` | `NONE` | `NONE` | `NONE` | `DEC-004` |
| `DATA-008` | Napredni registar pravila | `IDEA_CATALOG` | `CONFIRMED` | `NONE` | `NONE` | `NONE` | `DEC-004` |
| `DATA-009` | K01 canonical Pa800 Factory registry | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PASS` | `DATA-001`, `DATA-010`, `MOD-009`, `MOD-017`, `TEST-050` |
| `DATA-010` | Pinned pypdf 6.16.0 wheel | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-017`, `TEST-050` |

### DATA-001 — Korg Pa800 2.0 User's Manual (E12)

Normativni izvor za Pa800 korisničke funkcije te popise tvorničkih Soundova i Drum Kitova.

- Dokaz: **CONFIRMED** — Lokalni službeni PDF postoji i SHA-256 je ponovno izračunljiv.
- Implementacija: **NOT_APPLICABLE** — Dokument nije programski modul.
- Validacija: **PASS** — Datoteka postoji; hash je registriran.
- Certifikacija: **NOT_APPLICABLE** — Izvor podupire certifikaciju drugih zapisa, ali sam nije funkcija.
- Putanja: `prism-uploads/Pa800-201UM-ENG.pdf`
- SHA-256: `b7df16fb0113d998a6411ea1c28971707021da8bc0b728aff98eafcceb57c71b`

### DATA-002 — Korg Pa800 2.0 Advanced Edit Manual (E5)

Normativni izvor za detalje uređivanja i ponašanja Pa800 zvuka.

- Dokaz: **CONFIRMED** — Lokalni službeni PDF postoji i SHA-256 je ponovno izračunljiv.
- Implementacija: **NOT_APPLICABLE** — Dokument nije programski modul.
- Validacija: **PASS** — Datoteka postoji; hash je registriran.
- Certifikacija: **NOT_APPLICABLE** — Izvor podupire certifikaciju drugih zapisa, ali sam nije funkcija.
- Putanja: `prism-uploads/Pa800_AE_E.pdf`
- SHA-256: `6bcda56658a89eda31e9fe62a2b744df5cecaaf478e050d3256ad6440c0d413e`

### DATA-003 — Split Factory Styles corpus

Read-only Factory Style Works ZIP korišten za M06 i M07 corpus provjere.

- Dokaz: **CONFIRMED** — Arhiv je lokalno dostupan i loader ga obrađuje samo za čitanje.
- Implementacija: **NOT_APPLICABLE** — Corpus je podatkovni izvor.
- Validacija: **PASS** — M06 corpus test potvrđuje strukturu i očuvanje izvornog hasha.
- Certifikacija: **NONE** — Corpus nije certifikat za ponašanje fizičkog Pa800 uređaja.
- Putanja: `prism-uploads/Split Factory Styles.zip`
- SHA-256: `ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`
- Opažanja: `3211` MIDI datoteka

### DATA-004 — DNA premium MIDI corpus

DNA paket s Gold evaluacijskim arhivom i exact Factory container kopijom koja se deterministički isključuje kroz G02.

- Dokaz: **CONFIRMED** — Arhiv i njegov identitet postoje; glazbene generalizacije zahtijevaju zasebne reproducibilne metrike.
- Implementacija: **NOT_APPLICABLE** — DNA je podatkovni resurs; G02 guard je zaseban modul.
- Validacija: **PASS** — G02/TEST-061 validira 182 Gold MIDI-ja, deduplicira na 181 i potvrđuje nultu cross-source MIDI kontaminaciju.
- Certifikacija: **PARTIAL** — Certificirana je strukturalna evaluacijska neovisnost; premium kvaliteta i M07 accuracy nisu ground-truth certificirani.
- Putanja: `prism-uploads/DNA.zip`
- SHA-256: `125f4486625db44f7cdd49bd670aff252a961c88ea14741ec970ec3ae5eec85a`

### DATA-005 — Valja MIDI corpus

Dodatni korisnički corpus dostavljen u RAR5 arhivu.

- Dokaz: **CONFIRMED** — Arhiv i hash postoje.
- Implementacija: **BLOCKED** — Workspace nema potvrđen RAR5 dekoder; sadržaj nije dio aktivnog pipelinea.
- Validacija: **BLOCKED** — MIDI sadržaj nije raspakiran ni parsiran.
- Certifikacija: **NONE** — Nema certifikacije neanaliziranog sadržaja.
- Putanja: `prism-uploads/Valja.rar`
- SHA-256: `57b54dc69fa6aee21cf71e4324a2d1588c97a6016f2ae01514df29e9c1b63e32`

### DATA-006 — Oscilatori drum-kit bilješke

Korisnički izvor prijedloga za balkanski Drum Kit; nije službeni Pa800 dokaz.

- Dokaz: **CONFIRMED** — Tekstualni resurs postoji; tvrdnje iz njega ostaju prijedlozi dok ih ne potvrdi normativni ili empirijski dokaz.
- Implementacija: **NONE** — Drum Kit profil i GUI izbor nisu implementirani.
- Validacija: **NONE** — Nema automatskog testa za preporuku kita.
- Certifikacija: **NONE** — Nije certificiran kao univerzalni default.
- Putanja: `prism-uploads/Oscilatori.txt`
- SHA-256: `ee0aaf065231283fea55b69fca65c43ddab13e552389466c0c6848ea1c17434e`

### DATA-007 — Napredni spisak mogućnosti

Katalog kandidata za buduće mogućnosti; nijedna stavka samim unosom ne postaje aktivna funkcija ili pravilo.

- Dokaz: **CONFIRMED** — Dokument postoji samo kao provenance za ideje.
- Implementacija: **NONE** — Katalog nije specifikacija implementiranog stanja.
- Validacija: **NONE** — Stavke nisu pojedinačno testirane.
- Certifikacija: **NONE** — Nijedna stavka nije certificirana samim prisustvom u katalogu.
- Putanja: `prism-uploads/NAPREDNI SPISAK MOGUĆNOSTI — KORG PA800 FACTORY STYLE - MIDI - DNA ENGINE.md`
- SHA-256: `b4a91f65510bb2a3314c72d878c17ca38bddb4f2401b048189ea312049338e55`

### DATA-008 — Napredni registar pravila

Katalog kandidata za buduća pravila; nije aktivni rule set.

- Dokaz: **CONFIRMED** — Dokument postoji samo kao provenance za ideje.
- Implementacija: **NONE** — Katalog nije aktivni strojno izvršivi rule set.
- Validacija: **NONE** — Pravila nisu pojedinačno povezana s testovima.
- Certifikacija: **NONE** — Nijedno pravilo nije certificirano samim prisustvom u katalogu.
- Putanja: `prism-uploads/NAPREDNI REGISTAR PRAVILA — KORG PA800 FACTORY STYLE - MIDI INTELLIGENCE ENGINE.md`
- SHA-256: `01d03043b5285075e8152798443591d0ba30427498f2eef4907f45058b3a3432`

### DATA-009 — K01 canonical Pa800 Factory registry

Deterministički generirani JSON s Factory Sound/Drum Kit adresama, izvorima, remap dokazima i sigurnosnom politikom.

- Dokaz: **CONFIRMED** — Svaki zapis nastaje iz DATA-001 na unaprijed definiranim stranicama i s točnom adresom.
- Implementacija: **NOT_APPLICABLE** — Kanonski JSON je generirani podatkovni artefakt.
- Validacija: **PASS** — Generator --check i TEST-050 potvrđuju determinističnost, broj, jedinstvenost i izvore.
- Certifikacija: **PASS** — Certificiran je read-only K01 Factory adresni skup, ne K02 identitet nepotpunih adresa.
- Putanja: `registry/pa800_factory_registry.json`
- SHA-256: `9176dd41720b72111bd17263b376a07bfb188c0390404614275ade0b11cb5a16`
- Opažanja: `1071` jedinstvena puna Factory adresa

### DATA-010 — Pinned pypdf 6.16.0 wheel

Vendored pure-Python extractor wheel s licencom, korišten isključivo za reproducibilnu K01 PDF ekstrakciju.

- Dokaz: **CONFIRMED** — Wheel je preuzet iz službenog Python package indeksa pomoću pip-a i hashiran prije korištenja.
- Implementacija: **NOT_APPLICABLE** — Treća strana je pinned alatni resurs, ne domenska implementacija.
- Validacija: **PASS** — Generator provjerava wheel SHA-256 i točnu verziju prije uvoza.
- Certifikacija: **PARTIAL** — Pin potvrđuje identitet korištenog ekstraktora, ne neovisnu sigurnosnu reviziju cijele biblioteke.
- Putanja: `vendor/pypdf-6.16.0-py3-none-any.whl`
- SHA-256: `8c47581faa1cba7006ac269da30075c929c251cc4ffbafb2bcbe260306631118`

## TEST

| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |
|---|---|---|---|---|---|---|---|
| `TEST-001` | test_format_zero_and_one | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-001`, `MOD-002`, `RUN-001` |
| `TEST-002` | test_guitar_roles | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-003`, `MOD-004`, `RUN-001` |
| `TEST-003` | test_gui_module_imports | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-005`, `ISSUE-001`, `RUN-001` |
| `TEST-004` | test_rejects_truncated_track_without_mutating_source | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-006`, `RUN-001` |
| `TEST-005` | test_preserves_running_status_and_raw_events | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-006`, `RUN-001` |
| `TEST-006` | test_full_archive_structure_and_preservation | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-006`, `DATA-003`, `RUN-001` |
| `TEST-007` | test_pilot_style_and_declared_window | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-006`, `DATA-003`, `RUN-001` |
| `TEST-008` | test_style_window_excludes_trailing_content | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-006`, `RUN-001` |
| `TEST-009` | test_structural_roles_are_style_context_not_core_channel_rules | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-010` | test_same_guitar_sound_has_chordal_and_solo_contexts | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-011` | test_low_guitar_riff_is_not_guitar_mode_without_source_evidence | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-012` | test_source_guitar_mode_evidence_does_not_force_rhythm_function | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-013` | test_high_rx_notes_do_not_create_guitar_mode_false_positive | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-014` | test_fixed_intro_flag_is_orthogonal_and_scoped | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-015` | test_fixed_flag_excludes_rhythm_bass_and_empty_tracks | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-016` | test_blocked_element_is_not_editable | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-017` | test_drum_perc_and_bass_precede_texture_heuristics | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-018` | test_repeated_ostinato_is_riff_but_varied_line_is_solo | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-019` | test_ppq_scaled_strum_cluster_is_not_slow_arpeggio | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-020` | test_rx_policy_cannot_relax_fixed_intro_protection | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-021` | test_rx_policy_cannot_relax_guitar_mode_protection | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-022` | test_multiple_musical_channels_block_classification | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-007`, `RUN-002` |
| `TEST-023` | Master registry invariant suite | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-010`, `RUN-003` |
| `TEST-024` | test_full_factory_archive_reproduces_registered_m07_counts | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-007`, `DATA-003`, `RUN-002`, `CLAIM-002` |
| `TEST-025` | test_dna_bundle_factory_member_is_exact_registered_duplicate | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `DATA-003`, `DATA-004`, `ISSUE-008`, `RUN-003` |
| `TEST-026` | test_builds_tempo_meter_map_and_event_positions | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-008`, `RUN-004` |
| `TEST-027` | test_detects_exact_repeated_measures | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-008`, `RUN-004` |
| `TEST-028` | test_marks_long_gap_as_phrase_candidate_not_fact | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-008`, `RUN-004` |
| `TEST-029` | test_conflicting_meter_blocks_timeline | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-008`, `RUN-004` |
| `TEST-030` | test_style_adapter_respects_valid_window_and_preserves_source_hash | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-006`, `MOD-008`, `RUN-004` |
| `TEST-031` | test_derives_velocity_duration_polyphony_and_controllers | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-013`, `RUN-005` |
| `TEST-032` | test_creates_measure_profiles_from_m08_timeline | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-008`, `MOD-013`, `RUN-005` |
| `TEST-033` | test_creates_phrase_profiles_from_inferred_boundaries | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-008`, `MOD-013`, `RUN-005` |
| `TEST-034` | test_unmatched_notes_make_profile_partial | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-013`, `RUN-005` |
| `TEST-035` | test_blocked_timeline_preserves_global_metrics_but_blocks_use | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-008`, `MOD-013`, `RUN-005` |
| `TEST-036` | test_style_adapter_inherits_context_protections_and_valid_window | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-006`, `MOD-007`, `MOD-008`, `MOD-013`, `RUN-005` |
| `TEST-037` | test_splits_complete_addresses_and_profiles_each_segment | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-013`, `MOD-014`, `RUN-006` |
| `TEST-038` | test_bank_change_applies_only_at_next_program_change | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-014`, `RUN-006` |
| `TEST-039` | test_incomplete_address_is_partial_not_guessed | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-014`, `RUN-006` |
| `TEST-040` | test_note_crossing_program_boundary_is_flagged | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-014`, `RUN-006` |
| `TEST-041` | test_same_tick_event_order_defines_boundary | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `NONE` | `MOD-006`, `MOD-014`, `RUN-006` |
| `TEST-042` | test_multiple_channels_are_partitioned_but_result_is_partial | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-007`, `MOD-014`, `RUN-006` |
| `TEST-043` | test_style_adapter_respects_valid_window_and_source_hash | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-006`, `MOD-014`, `RUN-006` |
| `TEST-044` | test_m08_m09_m10_full_factory_corpus_is_deterministic_and_read_only | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `DATA-003`, `MOD-008`, `MOD-013`, `MOD-014`, `RUN-007`, `MOD-011`, `TEST-051` |
| `TEST-045` | RepositoryInventoryTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-016` |
| `TEST-046` | WorkspacePersistenceTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-015` |
| `TEST-047` | MidiFormatTwoTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-001`, `MOD-002`, `ISSUE-005` |
| `TEST-048` | ParserParityTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-001`, `MOD-006`, `ISSUE-006`, `DATA-003` |
| `TEST-049` | GuiRuntimeTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-005`, `ISSUE-001`, `TEST-003` |
| `TEST-050` | Pa800FactoryRegistryTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `DATA-001`, `DATA-009`, `DATA-010`, `MOD-009`, `MOD-017`, `ISSUE-002` |
| `TEST-051` | InstrumentIdentityResolverTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-009`, `MOD-011`, `MOD-014`, `TEST-044` |
| `TEST-052` | ChangePlanTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-018` |
| `TEST-053` | PolicyEngineTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-019`, `MOD-018` |
| `TEST-054` | K03SoundReplacementTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-020`, `MOD-012`, `MOD-011`, `MOD-018`, `MOD-019` |
| `TEST-055` | WindowsBatchScriptTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PARTIAL` | `MOD-021`, `MOD-022` |
| `TEST-056` | ChangeEngineVerifierTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-023`, `MOD-024`, `MOD-020`, `MOD-018` |
| `TEST-057` | VerifiedWriterTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-012`, `MOD-025`, `MOD-023`, `MOD-024` |
| `TEST-058` | GuiChangeWorkflowTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-026`, `MOD-005`, `MOD-012` |
| `TEST-059` | ContextualProfileBuilderTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-027`, `DATA-003`, `DEC-001` |
| `TEST-060` | ProfileSuggestEngineTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-028`, `MOD-027`, `MOD-019` |
| `TEST-061` | GoldDatasetGuardTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-029`, `DATA-003`, `DATA-004`, `ISSUE-008`, `ISSUE-009` |
| `TEST-062` | VelocityChangeScopeTests | `ACTIVE` | `CONFIRMED` | `PASS` | `PASS` | `PASS` | `MOD-030`, `MOD-028`, `MOD-023`, `MOD-024`, `MOD-025` |

### TEST-001 — test_format_zero_and_one

Provjerava parsing i prikazno mapiranje MIDI formata 0 i 1.

- Dokaz: **CONFIRMED** — Test metoda postoji u repozitoriju.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Registrirani test run je prošao.
- Certifikacija: **NONE** — Ne pokriva Format 2 ni puni SMF standard.
- Putanja: `tests/test_midi_modules.py`

### TEST-002 — test_guitar_roles

Provjerava rhythm, solo i power-chord guitar heuristike.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Registrirani test run je prošao.
- Certifikacija: **NONE** — Ne certificira Pa800 Guitar Mode.
- Putanja: `tests/test_midi_modules.py`

### TEST-003 — test_gui_module_imports

Provjerava import desktop GUI modula kada je tkinter dostupan.

- Dokaz: **CONFIRMED** — Test i uvjet preskakanja postoje.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — test_gui_module_imports prolazi s dostupnim tkinterom 8.6.
- Certifikacija: **PARTIAL** — Test potvrđuje samo import i prisutnost MidiEnhancerApp, ne otvaranje prozora ni korisnički workflow.
- Putanja: `tests/test_midi_modules.py`

### TEST-004 — test_rejects_truncated_track_without_mutating_source

Odbija skraćeni track i čuva ulaz.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test ograničenog slučaja.
- Putanja: `tests/test_style_loader.py`

### TEST-005 — test_preserves_running_status_and_raw_events

Provjerava running status i očuvanje sirovih događaja.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test ograničenog slučaja.
- Putanja: `tests/test_style_loader.py`

### TEST-006 — test_full_archive_structure_and_preservation

Provjerava puni Factory arhiv, strukturu i SHA-256 očuvanje.

- Dokaz: **CONFIRMED** — Corpus test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi na registriranom arhivu.
- Certifikacija: **PARTIAL** — Podupire samo M06 read-only corpus scope.
- Putanja: `tests/test_style_loader.py`

### TEST-007 — test_pilot_style_and_declared_window

Provjerava pilot Style i deklarirani vremenski prozor.

- Dokaz: **CONFIRMED** — Corpus test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Pokriva pilot slučaj.
- Putanja: `tests/test_style_loader.py`

### TEST-008 — test_style_window_excludes_trailing_content

Provjerava odvajanje događaja izvan deklariranog Style prozora.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test ograničenog slučaja.
- Putanja: `tests/test_style_loader.py`

### TEST-009 — test_structural_roles_are_style_context_not_core_channel_rules

Strukturne uloge ostaju u Style adapteru, ne u generičkoj jezgri.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test klasifikatora.
- Putanja: `tests/test_context_classifier.py`

### TEST-010 — test_same_guitar_sound_has_chordal_and_solo_contexts

Isti guitar sound može imati chordal i solo kontekst.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test klasifikatora.
- Putanja: `tests/test_context_classifier.py`

### TEST-011 — test_low_guitar_riff_is_not_guitar_mode_without_source_evidence

Nizak guitar riff ne postaje Guitar Mode bez izvornog dokaza.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Negativna sigurnosna provjera.
- Putanja: `tests/test_context_classifier.py`

### TEST-012 — test_source_guitar_mode_evidence_does_not_force_rhythm_function

Izvorni Guitar Mode dokaz ne prisiljava rhythm funkciju.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test klasifikatora.
- Putanja: `tests/test_context_classifier.py`

### TEST-013 — test_high_rx_notes_do_not_create_guitar_mode_false_positive

RX visoke note ne stvaraju lažni Guitar Mode zaključak.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Negativna sigurnosna provjera.
- Putanja: `tests/test_context_classifier.py`

### TEST-014 — test_fixed_intro_flag_is_orthogonal_and_scoped

Fixed Intro/Ending kandidat je ortogonalan i ograničen kontekstom.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test klasifikatora.
- Putanja: `tests/test_context_classifier.py`

### TEST-015 — test_fixed_flag_excludes_rhythm_bass_and_empty_tracks

Fixed kandidat isključuje rhythm, bass i prazne trackove.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test klasifikatora.
- Putanja: `tests/test_context_classifier.py`

### TEST-016 — test_blocked_element_is_not_editable

Blokirani element nije kandidat za editiranje.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Sigurnosni unit test.
- Putanja: `tests/test_context_classifier.py`

### TEST-017 — test_drum_perc_and_bass_precede_texture_heuristics

Drum, Perc i Bass imaju prioritet pred texture heuristikama.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test prioriteta.
- Putanja: `tests/test_context_classifier.py`

### TEST-018 — test_repeated_ostinato_is_riff_but_varied_line_is_solo

Razlikuje ponovljeni ostinato/riff od raznolike solo linije.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Heuristički unit test.
- Putanja: `tests/test_context_classifier.py`

### TEST-019 — test_ppq_scaled_strum_cluster_is_not_slow_arpeggio

PPQ-proporcionalni strum cluster nije spor arpeggio.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Heuristički unit test.
- Putanja: `tests/test_context_classifier.py`

### TEST-020 — test_rx_policy_cannot_relax_fixed_intro_protection

RX politika ne može ublažiti zaštitu fixed Intro konteksta.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Sigurnosni unit test.
- Putanja: `tests/test_context_classifier.py`

### TEST-021 — test_rx_policy_cannot_relax_guitar_mode_protection

RX politika ne može ublažiti Guitar Mode zaštitu.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Sigurnosni unit test.
- Putanja: `tests/test_context_classifier.py`

### TEST-022 — test_multiple_musical_channels_block_classification

Više glazbenih MIDI kanala u fizičkom partu blokira klasifikaciju.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Sigurnosni unit test.
- Putanja: `tests/test_context_classifier.py`

### TEST-023 — Master registry invariant suite

Provjerava ID namespace, reference, četiri osi, IDEA_CATALOG izolaciju, putanje, hashove, test-prisutnost i deterministički Markdown.

- Dokaz: **CONFIRMED** — Test suite je dio G00 implementacije.
- Implementacija: **PASS** — Test suite je implementiran standardnom bibliotekom.
- Validacija: **PASS** — Suite prolazi u registriranom G00 runu.
- Certifikacija: **PARTIAL** — Certificira format, lokalni integritet i veze registra, ne domensku istinitost svih tvrdnji.
- Putanja: `tests/test_master_registry.py`

### TEST-024 — test_full_factory_archive_reproduces_registered_m07_counts

Ponovno računa M07 puni Factory corpus rezultat i provjerava hash, 3.211 datoteka, 65.021 sliceova i statusne brojeve.

- Dokaz: **CONFIRMED** — Corpus test metoda postoji i koristi registrirani DATA-003 hash.
- Implementacija: **PASS** — Test je implementiran postojećim loader/classifier modulima.
- Validacija: **PASS** — Test reproducibilno prolazi na DATA-003.
- Certifikacija: **PARTIAL** — Podupire samo registrirani read-only M07 corpus rezultat.
- Putanja: `tests/test_context_classifier_corpus.py`

### TEST-025 — test_dna_bundle_factory_member_is_exact_registered_duplicate

Provjerava da unutarnji Factory ZIP u DNA paketu ima isti SHA-256 kao DATA-003.

- Dokaz: **CONFIRMED** — Test čita unutarnji ZIP bez ekstrakcije i ponovno računa hash.
- Implementacija: **PASS** — Contamination guard test je implementiran.
- Validacija: **PASS** — Test prolazi na registriranim DATA-003 i DATA-004 resursima.
- Certifikacija: **PARTIAL** — Dokazuje ovaj duplikat, ne cjelovitu čistoću budućeg golden skupa.
- Putanja: `tests/test_master_registry.py`

### TEST-026 — test_builds_tempo_meter_map_and_event_positions

Provjerava promjene tempa i metra te položaj Note On događaja po mjeri i beat-u.

- Dokaz: **CONFIRMED** — Test metoda postoji i koristi sintetički SMF s dvije timeline promjene.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test ograničenog općeg MIDI slučaja.
- Putanja: `tests/test_measure_phrase_analyzer.py`

### TEST-027 — test_detects_exact_repeated_measures

Provjerava grupiranje dviju mjera s jednakim normaliziranim Note On potpisom.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Certificira samo egzaktno ponavljanje, ne perceptivnu sličnost motiva.
- Putanja: `tests/test_measure_phrase_analyzer.py`

### TEST-028 — test_marks_long_gap_as_phrase_candidate_not_fact

Provjerava da duga stanka proizvodi kandidat granice fraze s eksplicitnom pouzdanošću, a ne potvrđenu činjenicu.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Heuristička granica nije certificirana kao glazbena fraza.
- Putanja: `tests/test_measure_phrase_analyzer.py`

### TEST-029 — test_conflicting_meter_blocks_timeline

Provjerava blokiranje vremenskog tumačenja kada izvori na istom ticku daju različit metar.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Certificira sigurnosno blokiranje testiranog konflikta.
- Putanja: `tests/test_measure_phrase_analyzer.py`

### TEST-030 — test_style_adapter_respects_valid_window_and_preserves_source_hash

Provjerava da M08 Style adapter isključuje trailing događaj, prenosi izvorni hash i ostaje Analyze-only.

- Dokaz: **CONFIRMED** — Test metoda postoji nad M06 Style modelom.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Podupire ograničeni M08 Style adapter scope.
- Putanja: `tests/test_measure_phrase_analyzer.py`

### TEST-031 — test_derives_velocity_duration_polyphony_and_controllers

Provjerava zajedničke velocity, duration, polifonija, CC i pitch-bend metrike.

- Dokaz: **CONFIRMED** — Test metoda postoji nad sintetičkim SMF događajima.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test ograničenog općeg MIDI slučaja.
- Putanja: `tests/test_instrument_measurement_engine.py`

### TEST-032 — test_creates_measure_profiles_from_m08_timeline

Provjerava M09 statistike po mjeri dobivene iz M08 timelinea.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Pokriva dvije sintetičke mjere.
- Putanja: `tests/test_instrument_measurement_engine.py`

### TEST-033 — test_creates_phrase_profiles_from_inferred_boundaries

Provjerava profile fraza i očuvanje razloga/pouzdanosti M08 granice.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Frazna granica ostaje heuristički kandidat.
- Putanja: `tests/test_instrument_measurement_engine.py`

### TEST-034 — test_unmatched_notes_make_profile_partial

Provjerava PARTIAL status za nezatvoreni Note On i orphan Note Off.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Certificira sigurnosno označavanje testiranih strukturnih problema.
- Putanja: `tests/test_instrument_measurement_engine.py`

### TEST-035 — test_blocked_timeline_preserves_global_metrics_but_blocks_use

Provjerava da globalne činjenice ostaju vidljive, ali konfliktni M08 timeline daje BLOCKED status.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Certificira zaštitu testiranog konfliktnog slučaja.
- Putanja: `tests/test_instrument_measurement_engine.py`

### TEST-036 — test_style_adapter_inherits_context_protections_and_valid_window

Provjerava M06 prozor te nasljeđivanje M07 fixed/DO_NOT_TOUCH i M08 Analyze-only zaštita.

- Dokaz: **CONFIRMED** — Test metoda postoji nad Style adapterom.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Podupire ograničeni M09 Style adapter scope.
- Putanja: `tests/test_instrument_measurement_engine.py`

### TEST-037 — test_splits_complete_addresses_and_profiles_each_segment

Provjerava dva potpuna CC00.CC32.PC segmenta i zaseban M09 profil svakoga.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Ne dokazuje Factory/User identitet adrese.
- Putanja: `tests/test_instrument_segmenter.py`

### TEST-038 — test_bank_change_applies_only_at_next_program_change

Provjerava da Bank Select promjena mijenja snapshot tek na sljedećem Program Changeu.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test MIDI state pravila.
- Putanja: `tests/test_instrument_segmenter.py`

### TEST-039 — test_incomplete_address_is_partial_not_guessed

Provjerava da Program Change bez oba bank kontrolera ostaje INCOMPLETE i PARTIAL.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Certificira nenagađanje testirane nepotpune adrese.
- Putanja: `tests/test_instrument_segmenter.py`

### TEST-040 — test_note_crossing_program_boundary_is_flagged

Provjerava detekciju note čiji Note On i Note Off leže s različitih strana Program Change granice.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Certificira zaštitu testiranog boundary slučaja.
- Putanja: `tests/test_instrument_segmenter.py`

### TEST-041 — test_same_tick_event_order_defines_boundary

Provjerava da izvorni event order razdvaja događaje kada Note i Program Change dijele tick.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **NONE** — Unit test očuvanja izvornog redoslijeda.
- Putanja: `tests/test_instrument_segmenter.py`

### TEST-042 — test_multiple_channels_are_partitioned_but_result_is_partial

Provjerava odvajanje segmenata po kanalu uz PARTIAL status višekanalnog fizičkog parta.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Certificira konzervativno ponašanje testiranog višekanalnog slučaja.
- Putanja: `tests/test_instrument_segmenter.py`

### TEST-043 — test_style_adapter_respects_valid_window_and_source_hash

Provjerava M10 Style adapter, M06 prozor, izvorni SHA-256 i puni adresni snapshot.

- Dokaz: **CONFIRMED** — Test metoda postoji.
- Implementacija: **PASS** — Test je implementiran.
- Validacija: **PASS** — Test prolazi.
- Certifikacija: **PARTIAL** — Podupire ograničeni M10 Style adapter scope.
- Putanja: `tests/test_instrument_segmenter.py`

### TEST-044 — test_m08_m09_m10_full_factory_corpus_is_deterministic_and_read_only

Obrađuje 3.211 Factory MIDI datoteka i 65.021 track-slice kroz M08–M10 i K02; provjerava 82.917 identiteta, statuse, digest i nepromijenjen ZIP hash.

- Dokaz: **CONFIRMED** — Izvršni corpus test i fiksna očekivanja postoje u repozitoriju.
- Implementacija: **PASS** — Test je implementiran nad DATA-003.
- Validacija: **PASS** — Puni test reproducira 82.917 M10/K02 segmenata, K02 raspodjelu i digest 5245ec7a… bez promjene izvornog arhiva; dio je RUN-014.
- Certifikacija: **PARTIAL** — Certificira samo read-only M08-M10 ponašanje za točno identificirani Factory corpus.
- Putanja: `tests/test_analysis_pipeline_corpus.py`

### TEST-045 — RepositoryInventoryTests

Testira uspješan Git inventar i detekciju dokumentirane datoteke izvan Git treea te MODULE_LOG ID-ja bez registry MODULE zapisa.

- Dokaz: **CONFIRMED** — Testni slučajevi grade izolirane privremene Git repozitorije.
- Implementacija: **PASS** — Tri namjenska unit testa su prisutna.
- Validacija: **PASS** — Testovi su izravno izvršivi standardnom bibliotekom i Gitom.
- Certifikacija: **PARTIAL** — Pokrivene su ključne inventory grane, ali ne glazbeni ili Pa800 scope.
- Putanja: `tests/test_repository_inventory.py`

### TEST-046 — WorkspacePersistenceTests

Provjerava checkpointirani commit i SHA-256 Python probea i vlastite testne datoteke.

- Dokaz: **CONFIRMED** — Test poziva stvarni Git checkpoint verifier nad aktualnim repozitorijem.
- Implementacija: **PASS** — Integracijski test je prisutan.
- Validacija: **PASS** — Isti checkpoint test prošao je lokalno i ponovno nakon sljedeće korisničke poruke.
- Certifikacija: **PASS** — Test certificira samo zabilježeni cross-turn commit/file persistence ugovor.
- Putanja: `tests/test_workspace_persistence.py`

### TEST-047 — MidiFormatTwoTests

Provjerava zasebne Format 2 vremenske linije, izostanak lažnog globalnog trajanja/tempa, 16-slot sequence prikaz, zabranu globalnih optional analizatora i strukturno slaganje oba parsera.

- Dokaz: **CONFIRMED** — Četiri deterministička testa grade mali SMF Format 2 s dvije neovisne sekvence različitog tempa.
- Implementacija: **PASS** — Dedicated test datoteka je prisutna.
- Validacija: **PASS** — 4/4 namjenska testa i puni suite od 69 testova + 6 subtestova prolaze bez failurea ili skippa.
- Certifikacija: **PARTIAL** — Test certificira ograničenu Format 2 read-only semantiku, ne puni SMF standard.
- Putanja: `tests/test_midi_format2.py`

### TEST-048 — ParserParityTests

Uspoređuje oba SMF parsera na event-rich, malformed, missing-EOT i SMPTE primjerima te core fingerprintu svih 3.211 Factory MIDI datoteka.

- Dokaz: **CONFIRMED** — Test gradi determinističke sintetičke ulaze i ponovno čita registrirani DATA-003 bez izmjene.
- Implementacija: **PASS** — Pet test metoda i corpus subtestovi su prisutni.
- Validacija: **PASS** — 5 parity testova, 3.223 parity subtesta i puni suite od 74 testa + 3.229 subtestova prolaze; Factory ZIP hash ostaje nepromijenjen.
- Certifikacija: **PARTIAL** — Pokriva core parser parity i odabrane strukturne rubove, ne puni SMF standard ili writer.
- Putanja: `tests/test_parser_parity.py`

### TEST-049 — GuiRuntimeTests

Na stvarnom Tk/Xvfb displayu testira Analyze/Format2 te Factory dialog preview, USER approve, V01 PASS, W01 save i rollback.

- Dokaz: **CONFIRMED** — Test koristi stvarni tkinter.Tk i MidiEnhancerApp; nije samo import ili mock cijelog GUI-a.
- Implementacija: **PASS** — Dvije GUI runtime test metode su prisutne.
- Validacija: **PASS** — 3/3 stvarna Tk GUI testa i puni DISPLAY=:109 suite od 128 testova + 3.242 subtesta prolaze.
- Certifikacija: **PARTIAL** — Pokriva automatizirani render/data/export scope, ne ljudski UX ili native packaging.
- Putanja: `tests/test_gui_runtime.py`

### TEST-050 — Pa800FactoryRegistryTests

Testira generator, potpunost, lookup, source pages, duplicate name, 57–58 konflikt, User range i odbijanje krivog manual hasha.

- Dokaz: **CONFIRMED** — Sedam namjenskih testova koristi stvarni DATA-001 i kanonski DATA-009.
- Implementacija: **PASS** — Dedicated K01 test datoteka je prisutna.
- Validacija: **PASS** — 7/7 K01 testova i puni DISPLAY=:103 suite od 83 testa + 3.229 subtestova prolaze bez failurea ili skippa.
- Certifikacija: **PASS** — Pokriven je ograničeni read-only K01 Factory registry/generator scope.
- Putanja: `tests/test_pa800_factory_registry.py`

### TEST-051 — InstrumentIdentityResolverTests

Na stvarnim sintetički generiranim M10 segmentima testira exact Factory Sound/Kit, User slot, Unknown, incomplete, no-program, remap i 57–58 konflikt te očuvanje ulaza.

- Dokaz: **CONFIRMED** — Šest testova prolazi kroz StandardMidiLoader i InstrumentSegmenter prije K02 rezolucije.
- Implementacija: **PASS** — Dedicated K02 test datoteka je prisutna.
- Validacija: **PASS** — 6/6 dedicated K02 testova i puni DISPLAY=:104 suite od 89 testova + 3.233 subtesta prolaze.
- Certifikacija: **PASS** — Pokriva ograničeni read-only K02 statusni i immutability ugovor.
- Putanja: `tests/test_instrument_identity_resolver.py`

### TEST-052 — ChangePlanTests

Testira deterministic plan/proposal ID, JSON, USER decision history, timezone, confidence, duplicate target, no-op/range i trajnu Apply zabranu.

- Dokaz: **CONFIRMED** — Šest testova koristi stvarni byte-preserving MidiEvent snapshot.
- Implementacija: **PASS** — Dedicated P01 test datoteka je prisutna.
- Validacija: **PASS** — 6/6 P01 testova i puni DISPLAY=:105 suite od 101 testa + 3.236 subtestova prolaze.
- Certifikacija: **PASS** — Pokriva P01 immutable data/decision scope, ne writer.
- Putanja: `tests/test_change_plan.py`

### TEST-053 — PolicyEngineTests

Testira Suggest allowed/blocked verdict, exact source snapshot, evidence/risk/version/rule kapije i plan creation bez Apply.

- Dokaz: **CONFIRMED** — Šest testova koristi stvarne parsirane MIDI kontrolerske događaje.
- Implementacija: **PASS** — Dedicated P02 test datoteka je prisutna.
- Validacija: **PASS** — 6/6 P02 testova, 3 subtesta i puni DISPLAY=:105 suite od 101 testa + 3.236 subtestova prolaze.
- Certifikacija: **PASS** — Pokriva P02 Suggest policy scope, ne Change/Writer.
- Putanja: `tests/test_policy_engine.py`

### TEST-054 — K03SoundReplacementTests

Testira user-selected K01 target plan, exact PC/bank mutations, shared/inherited bank zaštitu, kind/status/target blokiranje i trajnu Apply zabranu.

- Dokaz: **CONFIRMED** — Sedam testova koristi stvarni StandardMidiLoader, M10, K02, K01, P01 i P02 lanac.
- Implementacija: **PASS** — Dedicated K03-P test datoteka je prisutna.
- Validacija: **PASS** — 7/7 K03-P testova, 4 subtesta i puni DISPLAY=:105 suite od 108 testova + 3.240 subtestova prolaze.
- Certifikacija: **PASS** — Pokriva Suggest-only K03-P scope, ne writer ili Verifier.
- Putanja: `tests/test_k03_sound_replacement.py`

### TEST-055 — WindowsBatchScriptTests

Statički provjerava CRLF, Python/Tk/venv kapije, pinned local wheel, registry checks, launch načine i zabranu destruktivnih naredbi.

- Dokaz: **CONFIRMED** — Tri testa čitaju stvarne install.bat/run.bat bajtove.
- Implementacija: **PASS** — Dedicated Windows batch static test je prisutan.
- Validacija: **PASS** — 3/3 testa prolaze.
- Certifikacija: **PARTIAL** — Certificira statički script ugovor, ne izvršavanje pod Windows cmd.exe.
- Putanja: `tests/test_windows_batch_scripts.py`

### TEST-056 — ChangeEngineVerifierTests

Testira approved USER execution, working-copy CC/PC patch, running status, rollback, tampered source i Verifier blokiranje extra/forged/truncated outputa.

- Dokaz: **CONFIRMED** — Šest testova koristi stvarni K01/K02/K03-P/P01/P02/M10 lanac i byte-preserving parser.
- Implementacija: **PASS** — Dedicated C01/V01 test datoteka je prisutna.
- Validacija: **PASS** — 6/6 C01/V01 testova i puni DISPLAY=:107 suite od 117 testova + 3.240 subtestova prolaze.
- Certifikacija: **PASS** — Pokriva in-memory Change/rollback/verifier scope, ne disk writer.
- Putanja: `tests/test_change_engine_verifier.py`

### TEST-057 — VerifiedWriterTests

End-to-end testira verified new-file MIDI/JSON save, source očuvanje, no-overwrite, bad verifier/source/name, atomic failure cleanup i guarded rollback.

- Dokaz: **CONFIRMED** — Pet testova koristi stvarni M10/K01/K02/K03-P/P01/P02/C01/V01 lanac i privremeni filesystem.
- Implementacija: **PASS** — Dedicated W01 test datoteka je prisutna.
- Validacija: **PASS** — 5/5 W01 testova, 2 subtesta i puni DISPLAY=:108 suite od 122 testa + 3.242 subtesta prolaze.
- Certifikacija: **PASS** — Pokriva bounded atomic writer/rollback scope na aktualnom filesystemu.
- Putanja: `tests/test_verified_writer.py`

### TEST-058 — GuiChangeWorkflowTests

Testira eligible segmente/targets, preview→approve→verify→save→rollback, stage/USER gate, Unknown exclusion i shared-bank zaštitu.

- Dokaz: **CONFIRMED** — Pet testova koristi stvarne privremene MIDI fajlove i cijeli backend lanac.
- Implementacija: **PASS** — Dedicated G01 backend test je prisutan.
- Validacija: **PASS** — 5/5 G01 backend testova i puni DISPLAY=:109 suite od 128 testova + 3.242 subtesta prolaze.
- Certifikacija: **PASS** — Pokriva bounded GUI workflow backend, ne native human UX.
- Putanja: `tests/test_gui_change_workflow.py`

### TEST-059 — ContextualProfileBuilderTests

Testira agregaciju distribucija/provenance, isolation po function/element/CV/source, rejection konflikta, deterministic render i puni Factory katalog.

- Dokaz: **CONFIRMED** — Pet testova uključuje stvarni DATA-003 build i fixed expected digest.
- Implementacija: **PASS** — Dedicated R01 test datoteka je prisutna.
- Validacija: **PASS** — 5/5 R01 testova i puni DISPLAY=:110 suite od 133 testa + 3.242 subtesta prolaze.
- Certifikacija: **PASS** — Pokriva read-only Factory contextual profile scope, ne Suggest.
- Putanja: `tests/test_contextual_profile_builder.py`

### TEST-060 — ProfileSuggestEngineTests

Testira exact profile plan, bounded velocity step, no fallback za function/element/CV/role/encoding/source, support/context/user gate i C01 Apply block.

- Dokaz: **CONFIRMED** — Šest testova i deset subtestova koriste stvarne parsirane Note On događaje i R01 profile.
- Implementacija: **PASS** — Dedicated S01 test datoteka je prisutna.
- Validacija: **PASS** — 6/6 S01 testova, 10 subtestova i puni DISPLAY=:111 suite od 139 testova + 3.252 subtesta prolaze.
- Certifikacija: **PASS** — Pokriva Suggest-only S01 matching/proposal scope, ne Apply.
- Putanja: `tests/test_profile_suggest_engine.py`

### TEST-061 — GoldDatasetGuardTests

Testira stvarni Factory/DNA split/dedup/hash/digest/read-only rezultat, determinističnost i unsafe ZIP path rejection.

- Dokaz: **CONFIRMED** — Tri testa i tri subtesta koriste stvarne DATA-003/DATA-004 arhive i sintetičke unsafe ZIP putanje.
- Implementacija: **PASS** — Dedicated G02 test datoteka je prisutna.
- Validacija: **PASS** — 3/3 G02 testova, 3 subtesta i puni DISPLAY=:112 suite od 142 testa + 3.255 subtestova prolaze.
- Certifikacija: **PASS** — Pokriva structural contamination/dedup/source split scope.
- Putanja: `tests/test_gold_dataset_guard.py`

### TEST-062 — VelocityChangeScopeTests

End-to-end testira S01 USER ack, Note On running-status patch, V01/W01/rollback, generic/missing ack block, zero/large delta block i forged ack detection.

- Dokaz: **CONFIRMED** — Četiri testa i dva subtesta koriste stvarne parsirane Note On događaje, R01/S01 plan i C01/V01/W01.
- Implementacija: **PASS** — Dedicated V02 test datoteka je prisutna.
- Validacija: **PASS** — 4/4 V02 testova, 2 subtesta i puni DISPLAY=:113 suite od 146 testova + 3.257 subtestova prolaze.
- Certifikacija: **PASS** — Pokriva explicit acknowledged bounded velocity Apply scope.
- Putanja: `tests/test_velocity_change_scope.py`

## TEST_RUN

| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |
|---|---|---|---|---|---|---|---|
| `RUN-001` | M06 i osnovni MIDI test run — 2026-08-13 | `HISTORICAL` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `TEST-001`, `TEST-002`, `TEST-003`, `TEST-004`, `TEST-005`, `TEST-006`, `TEST-007`, `TEST-008` |
| `RUN-002` | M07 kombinirani test run — 2026-08-13 | `HISTORICAL` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-007`, `DATA-003`, `TEST-024` |
| `RUN-003` | G00 registry test run — 2026-08-13 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `TEST-023`, `TEST-025`, `MOD-010` |
| `RUN-004` | M08 kombinirani test run — 2026-08-13 | `SUPERSEDED` | `CONFIRMED` | `NOT_APPLICABLE` | `PARTIAL` | `NONE` | `MOD-008`, `TEST-026`, `TEST-027`, `TEST-028`, `TEST-029`, `TEST-030` |
| `RUN-005` | M09 kombinirani test run — 2026-08-13 | `SUPERSEDED` | `CONFIRMED` | `NOT_APPLICABLE` | `PARTIAL` | `NONE` | `MOD-013`, `TEST-031`, `TEST-032`, `TEST-033`, `TEST-034`, `TEST-035`, `TEST-036` |
| `RUN-006` | M10 kombinirani test run — 2026-08-13 | `SUPERSEDED` | `CONFIRMED` | `NOT_APPLICABLE` | `PARTIAL` | `NONE` | `MOD-014`, `TEST-037`, `TEST-038`, `TEST-039`, `TEST-040`, `TEST-041`, `TEST-042`, `TEST-043` |
| `RUN-007` | M08-M10 hard-gate i Factory corpus run — 2026-08-13 (historical) | `HISTORICAL` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `DATA-003`, `MOD-008`, `MOD-013`, `MOD-014`, `TEST-044` |
| `RUN-008` | Full imported-snapshot suite — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `DATA-003`, `MOD-010`, `MOD-015`, `MOD-016`, `TEST-044`, `TEST-045`, `TEST-046` |
| `RUN-009` | A01 cross-turn persistence i A02 inventory — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-015`, `MOD-016`, `TEST-045`, `TEST-046` |
| `RUN-010` | M01/M02 Format 2 full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-001`, `MOD-002`, `TEST-047`, `DATA-003`, `ISSUE-006` |
| `RUN-011` | Dual-parser core parity full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-001`, `MOD-006`, `TEST-048`, `DATA-003`, `ISSUE-006` |
| `RUN-012` | M05 virtual-display GUI full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-005`, `TEST-003`, `TEST-049`, `ISSUE-001` |
| `RUN-013` | K01 Factory Registry full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-009`, `MOD-017`, `DATA-009`, `DATA-010`, `TEST-050`, `RUN-012` |
| `RUN-014` | K02 M10 identity integration full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-009`, `MOD-011`, `MOD-014`, `TEST-044`, `TEST-051`, `RUN-013` |
| `RUN-015` | P01/P02 Change Plan and Policy full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-018`, `MOD-019`, `TEST-052`, `TEST-053`, `RUN-014` |
| `RUN-016` | K03-P user-selected proposal full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-020`, `MOD-012`, `TEST-054`, `RUN-015` |
| `RUN-017` | C01/V01 Change Engine and Verifier full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-023`, `MOD-024`, `TEST-056`, `RUN-016` |
| `RUN-018` | W01 Atomic Verified Writer full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-012`, `MOD-025`, `TEST-057`, `RUN-017` |
| `RUN-019` | G01 bounded GUI Change workflow full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-005`, `MOD-012`, `MOD-026`, `TEST-049`, `TEST-058`, `RUN-018` |
| `RUN-020` | R01 Contextual Profile full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-027`, `TEST-059`, `DATA-003`, `RUN-019` |
| `RUN-021` | S01 Exact Profile Suggest full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-028`, `TEST-060`, `MOD-027`, `RUN-020` |
| `RUN-022` | G02 Gold Dataset Guard full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-029`, `TEST-061`, `DATA-003`, `DATA-004`, `ISSUE-009`, `RUN-021` |
| `RUN-023` | V02 Specialized Velocity Apply full regression — 2026-08-14 | `ACTIVE` | `CONFIRMED` | `NOT_APPLICABLE` | `PASS` | `PARTIAL` | `MOD-030`, `TEST-062`, `MOD-028`, `RUN-022` |

### RUN-001 — M06 i osnovni MIDI test run — 2026-08-13

Osam testova: sedam uspješnih i jedan opravdano preskočen GUI test.

- Dokaz: **CONFIRMED** — Naredba i rezultat zapisani su u MODULE_LOG.md.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 7 PASS, 1 skipped zbog tkinter preduvjeta.
- Certifikacija: **PARTIAL** — Podupire M01–M06 samo u pokrivenom scopeu.
- Naredba: `python3 -m unittest -v tests/test_style_loader.py tests/test_midi_modules.py`

### RUN-002 — M07 kombinirani test run — 2026-08-13

Dvadeset tri testa: 22 uspješna i jedan opravdano preskočen GUI test, uključujući reproducibilni M07 corpus test.

- Dokaz: **CONFIRMED** — Naredba i rezultat zapisani su u MODULE_LOG.md.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 22 PASS, 1 skipped; corpus brojke i izvorni hash ponovno su izračunati.
- Certifikacija: **PARTIAL** — Podupire read-only M07 scope na registriranom korpusu.
- Naredba: `python3 -m unittest -v tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py`

### RUN-003 — G00 registry test run — 2026-08-13

Validacija namespacea, IDEA izolacije, putanja, hashova, test-prisutnosti, referenci i generiranog Markdown prikaza.

- Dokaz: **CONFIRMED** — Naredba je reproducibilna u workspaceu.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — G00 suite prolazi s deset testova.
- Certifikacija: **PARTIAL** — Podupire samo G00 registry invariantne uvjete.
- Naredba: `python3 -m unittest -v tests/test_master_registry.py`

### RUN-004 — M08 kombinirani test run — 2026-08-13

Povijesni M08 run prije proširenog rubnog i corpus pokrića.

- Dokaz: **CONFIRMED** — Naredba i rezultat zapisani su u MODULE_LOG.md.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PARTIAL** — Run je zamijenjen strožim RUN-007 nakon pronalaska nepokrivenih rubnih slučajeva.
- Certifikacija: **NONE** — Ne koristi se kao aktualni hard-gate dokaz.
- Naredba: `python3 -m unittest -v tests/test_measure_phrase_analyzer.py tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py`

### RUN-005 — M09 kombinirani test run — 2026-08-13

Povijesni M09 run prije timeline provenance, višetrack i corpus zaštita.

- Dokaz: **CONFIRMED** — Naredba i rezultat zapisani su u MODULE_LOG.md.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PARTIAL** — Run je zamijenjen strožim RUN-007 nakon pronalaska nepokrivenih rubnih slučajeva.
- Certifikacija: **NONE** — Ne koristi se kao aktualni hard-gate dokaz.
- Naredba: `python3 -m unittest -v tests/test_instrument_measurement_engine.py tests/test_measure_phrase_analyzer.py tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py`

### RUN-006 — M10 kombinirani test run — 2026-08-13

Povijesni M10 run prije open-note, ordinal, cross-track i corpus zaštita.

- Dokaz: **CONFIRMED** — Naredba i rezultat zapisani su u MODULE_LOG.md.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PARTIAL** — Run je zamijenjen strožim RUN-007 nakon pronalaska nepokrivenih rubnih slučajeva.
- Certifikacija: **NONE** — Ne koristi se kao aktualni hard-gate dokaz.
- Naredba: `python3 -m unittest -v tests/test_instrument_segmenter.py tests/test_instrument_measurement_engine.py tests/test_measure_phrase_analyzer.py tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py`

### RUN-007 — M08-M10 hard-gate i Factory corpus run — 2026-08-13 (historical)

Aktualni dedicated, puni regresijski i Factory corpus dokaz nakon neovisnog testnog audita.

- Dokaz: **CONFIRMED** — Naredba je izravno izvršna; TEST-044 veže rezultat uz fiksni corpus hash, raspodjele i deterministički digest.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — Aktualni hard-gate suite: 61 test, 60 PASS, 1 GUI skip/BLOCKED zbog nedostupnog tkintera i 0 failurea.
- Certifikacija: **PARTIAL** — Podupire samo read-only M08-M10 scope i postojeće regresije; ne autorizira writer, identity ili hardware tvrdnje.
- Naredba: `python3 -m unittest -v tests/test_analysis_pipeline_corpus.py tests/test_instrument_segmenter.py tests/test_instrument_measurement_engine.py tests/test_measure_phrase_analyzer.py tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py`

### RUN-008 — Full imported-snapshot suite — 2026-08-14

Aktualni puni pytest run nakon popravka ZIP filename kodiranja, regeneracije G00 prikaza te dodavanja A01/A02 governance alata.

- Dokaz: **CONFIRMED** — Naredba je izvršena u aktualnom Git workspaceu nakon stvaranja persistence checkpointa.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 65 testova i 6 subtestova prošlo je za 195,99 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Run podupire postojeći softverski i read-only corpus scope; ne certificira K01/K02, writer, Enhance, hardware, zvuk ni interaktivni GUI.
- Naredba: `python -m pytest -q`

### RUN-009 — A01 cross-turn persistence i A02 inventory — 2026-08-14

Ponovno izvršenje persistence checkpointa nakon nove korisničke poruke te aktualni Git inventory bez dokumentiranih nedostajućih artefakata.

- Dokaz: **CONFIRMED** — Izvršeno u novom korisničkom turnu nad commitom c1244c2; checkpoint commit i četiri SHA-256 artefakta odgovaraju.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — Persistence test 1/1 PASS; A02 inventory PASS s 0 errora i 0 warninga.
- Certifikacija: **PARTIAL** — Podupire samo A01/A02 governance scope; ne certificira MIDI ponašanje, K01/K02 ni Enhance.
- Naredba: `python tools/workspace_persistence_probe.py && python -m pytest -q tests/test_workspace_persistence.py && python tools/repository_inventory.py`

### RUN-010 — M01/M02 Format 2 full regression — 2026-08-14

Puni regression i Factory corpus run nakon uvođenja neovisnih Format 2 sequence timelineova i konzervativnog GUI/optional-library ponašanja.

- Dokaz: **CONFIRMED** — Namjenski Format 2 testovi i puna naredba izvršeni su u aktualnom workspaceu.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 69 testova i 6 subtestova PASS za 196,33 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire ograničeni read-only SMF Format 2 i postojeći regression/corpus scope; ne certificira puni SMF standard, writer ili Enhance.
- Naredba: `python -m pytest -q`

### RUN-011 — Dual-parser core parity full regression — 2026-08-14

Puni regression i corpus run nakon ujednačavanja SMF track-count, PPQ/SMPTE i End-of-Track kapija te Factory core-parity guarda.

- Dokaz: **CONFIRMED** — Dedicated parity i puna naredba izvršeni su nad aktualnim kodom i registriranim Factory corpusom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 74 testa i 3.229 subtestova PASS za 235,43 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire testirani core parser parity i postojeći read-only scope; ne certificira writer, puni SMF standard ili Enhance.
- Naredba: `python -m pytest -q`

### RUN-012 — M05 virtual-display GUI full regression — 2026-08-14

Puni regression/corpus run s aktivnim lokalnim Xvfb displayem, tako da stvarni Tk GUI runtime testovi nisu preskočeni.

- Dokaz: **CONFIRMED** — Tk/Xvfb runtime, dedicated GUI testovi i puna naredba izvršeni su u aktualnom workspaceu.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 76 testova i 3.229 subtestova PASS za 234,64 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire automatizirani virtual-display GUI i postojeći read-only scope; ne certificira native packaging, human UX, K01/K02 ili Enhance.
- Naredba: `DISPLAY=:102 python -m pytest -q`

### RUN-013 — K01 Factory Registry full regression — 2026-08-14

Puni regression/corpus/GUI run nakon reproducibilnog K01 generatora, kanonskog registra i immutable lookup modula.

- Dokaz: **CONFIRMED** — Generator --check, dedicated K01 suite i puna naredba izvršeni su nad potvrđenim manualom i pinned extractorom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 83 testa i 3.229 subtestova PASS za 237,61 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire K01 read-only Factory identity/generator i postojeći scope; ne certificira K02/K03, writer ili Enhance.
- Naredba: `DISPLAY=:103 python -m pytest -q`

### RUN-014 — K02 M10 identity integration full regression — 2026-08-14

Puni regression/corpus/GUI run nakon produkcijskog K02 resolvera i integracije svih 82.917 Factory M10 segmenata.

- Dokaz: **CONFIRMED** — Dedicated K02 testovi, M08–M10/K02 Factory corpus i puna naredba izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 89 testova i 3.233 subtesta PASS za 243,18 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire K02 read-only identity i postojeći scope; ne autorizira K03, Change, Writer ili Enhance.
- Naredba: `DISPLAY=:104 python -m pytest -q`

### RUN-015 — P01/P02 Change Plan and Policy full regression — 2026-08-14

Puni regression/corpus/GUI run nakon immutable Change Plan temelja i Suggest Policy Enginea bez Apply/writer putanje.

- Dokaz: **CONFIRMED** — Dedicated P01/P02 testovi i puna naredba izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 101 test i 3.236 subtestova PASS za 238,08 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire P01/P02 Suggest/data scope; K03, Change, Writer i Verifier ostaju necertificirani.
- Naredba: `DISPLAY=:105 python -m pytest -q`

### RUN-016 — K03-P user-selected proposal full regression — 2026-08-14

Puni regression/corpus/GUI run nakon Suggest-only K03-P buildera s exclusive existing CC/PC event kapijama.

- Dokaz: **CONFIRMED** — Dedicated K03-P testovi i puna naredba izvršeni su nad aktualnim K01/K02/P01/P02 lancem.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 108 testova i 3.240 subtestova PASS za 239,67 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire K03-P Suggest proposal scope; Change backend, writer i Verifier ostaju necertificirani.
- Naredba: `DISPLAY=:105 python -m pytest -q`

### RUN-017 — C01/V01 Change Engine and Verifier full regression — 2026-08-14

Puni regression/corpus/GUI run nakon in-memory byte-preserving Change Enginea, rollbacka i independent Verifiera.

- Dokaz: **CONFIRMED** — Dedicated C01/V01 sigurnosni testovi i puna naredba izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 117 testova i 3.240 subtestova PASS za 241,59 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire in-memory Change/rollback/verifier scope; disk writer/save gate ostaje necertificiran.
- Naredba: `DISPLAY=:107 python -m pytest -q`

### RUN-018 — W01 Atomic Verified Writer full regression — 2026-08-14

Puni regression/corpus/GUI run nakon atomic no-overwrite verified MIDI/JSON writera i hash-guarded filesystem rollbacka.

- Dokaz: **CONFIRMED** — Dedicated W01 filesystem testovi i puna naredba izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 122 testa i 3.242 subtesta PASS za 234,51 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire bounded W01/K03 programatski backend; GUI save workflow i automatski Enhance nisu certificirani.
- Naredba: `DISPLAY=:108 python -m pytest -q`

### RUN-019 — G01 bounded GUI Change workflow full regression — 2026-08-14

Puni regression/corpus/GUI run nakon segment/target preview, USER approval, V01, W01 save i rollback Tk integracije.

- Dokaz: **CONFIRMED** — G01 backend, stvarni Tk end-to-end test i puna naredba izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 128 testova i 3.242 subtesta PASS za 236,29 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire bounded virtual-display GUI Change workflow; native Windows human UX i automatic Enhance nisu certificirani.
- Naredba: `DISPLAY=:109 python -m pytest -q`

### RUN-020 — R01 Contextual Profile full regression — 2026-08-14

Puni regression/corpus/GUI run uključujući streaming build 29.603 Factory observacije i 13.821 izoliranog profila.

- Dokaz: **CONFIRMED** — R01 unit/full-corpus test i cijeli suite izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 133 testa i 3.242 subtesta PASS za 308,25 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire R01 reference-only Factory profile scope; Suggest i automatic Enhance nisu certificirani.
- Naredba: `DISPLAY=:110 python -m pytest -q`

### RUN-021 — S01 Exact Profile Suggest full regression — 2026-08-14

Puni regression/corpus/GUI run nakon exact contextual matcher i bounded Suggest-only Note On velocity outlier pravila.

- Dokaz: **CONFIRMED** — S01 testovi, R01 full build i cijeli suite izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 139 testova i 3.252 subtesta PASS za 302,44 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire S01 Suggest-only scope; Note On Apply i automatic Enhance ostaju necertificirani.
- Naredba: `DISPLAY=:111 python -m pytest -q`

### RUN-022 — G02 Gold Dataset Guard full regression — 2026-08-14

Puni regression/corpus/GUI run uključujući R01 Factory build i G02 real/deterministic Gold contamination manifest testove.

- Dokaz: **CONFIRMED** — G02 stvarni/deterministički/unsafe testovi i cijeli suite izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 142 testa i 3.255 subtestova PASS za 421,49 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire G02 structural contamination/split scope; M07 statistical calibration ostaje BLOCKED.
- Naredba: `DISPLAY=:112 python -m pytest -q`

### RUN-023 — V02 Specialized Velocity Apply full regression — 2026-08-14

Puni regression/corpus/GUI run nakon explicit USER-acknowledged S01 Note On velocity C01/V01/W01 scopea.

- Dokaz: **CONFIRMED** — V02 dedicated testovi i cijeli R01/G02/regression suite izvršeni su nad aktualnim snapshotom.
- Implementacija: **NOT_APPLICABLE** — Test run nije produkcijska implementacija.
- Validacija: **PASS** — 146 testova i 3.257 subtestova PASS za 391,22 s; 0 failurea i 0 skipova.
- Certifikacija: **PARTIAL** — Podupire bounded explicit V02 scope; automatic velocity Apply/Enhance i GUI risk-ack workflow nisu certificirani.
- Naredba: `DISPLAY=:113 python -m pytest -q`
