# Dnevnik modula

Svaki modul prolazi redoslijed:

1. definiranje jedne ograničene funkcije;
2. navođenje relevantnih stranica Pa800 priručnika;
3. implementacija;
4. automatski test;
5. zapis rezultata i konkretno primijenjenih promjena;
6. status `PASS`, `FAIL` ili `BLOCKED`.

Moduli čine dependency DAG, a ne jedan linearni lanac. Novi modul počinje tek
kada su svi njegovi deklarirani preduvjeti `PASS`; nepovezani `BLOCKED` ili
`FAIL` modul ne zaustavlja neovisnu granu. Pa800-specifičan modul ne može biti
`PASS` bez lokalnog službenog PDF-a i navedenih stranica.

## Trenutno stanje

| ID | Modul | Implementirano | Test | Pa800 dokaz | Status |
|---|---|---|---|---|---|
| M01 | Standard MIDI parser | Read-only formati 0/1/2; Format 2 neovisne sekvence; dual-parser parity guard | M01, Format 2 i `tests/test_parser_parity.py` | Nije Pa800-specifično | PASS za ograničeni read-only/core-parity scope |
| M02 | Mapiranje 16 slotova | Format 0 kanali; Format 1 trackovi; Format 2 zasebne sekvence | M01 i Format 2 testovi | Opći MIDI model | PASS (opći MIDI prikaz) |
| M03 | Instrument i uloga | GM programi, percussion, raspon i polifonija | `test_guitar_roles` | Heuristika, nije Pa800 činjenica | PASS (heuristika) |
| M04 | Guitar uloge | Rhythm, solo i power-chord pravila | `test_guitar_roles` | Heuristika, nije Guitar Mode dekoder | PASS (heuristika) |
| M05 | Desktop GUI | Analyze + bounded Factory preview/approve/verify/save/rollback | `tests/test_gui_runtime.py` na lokalnom Xvfb | Automatizirani virtual-display scope | PASS; native Windows UX ostaje PARTIAL |
| K01 | Pa800 Factory registar | Generator, kanonski JSON i immutable lookup za 1.071 adresu | `tests/test_pa800_factory_registry.py` | User's Manual, tiskane 275--283 i 295 | PASS (read-only Factory identity) |
| M06 | Style Works Loader | Read-only ZIP/MIDI model, Style/Element/CV/role, valjani prozor taktova i CC00.CC32.PC | `tests/test_style_loader.py` | User's Manual, tiskane stranice 114--116, 134--135 | PASS |
| M07 | Context Classifier | Generički feature model, Style adapter, Drum/Perc/Bass, chordal, riff, rhythm guitar, solo/fixed i Guitar Mode kandidat | unit suite + `tests/test_context_classifier_corpus.py` | User's Manual, tiskane stranice 112, 116, 118--120 i 134--135 | PASS (read-only) |
| M08 | Measure/Phrase Analyzer | Tempo/metar timeline, položaj u taktu, egzaktna ponavljanja i kandidati granica fraza | `tests/test_measure_phrase_analyzer.py` | Opći MIDI; Style adapter koristi potvrđeni M06 kontekst | PASS (read-only) |
| M09 | Instrument Measurement Engine | Velocity, trajanje, gustoća, polifonija, kontroleri te profili mjera i fraza | `tests/test_instrument_measurement_engine.py` | Opći MIDI; nasljeđuje M07/M08 statuse i zaštite | PASS (read-only) |
| M10 | Instrument Segmenter | Segmenti po kanalu i Program Changeu, CC00/CC32 snapshot i M09 profil | `tests/test_instrument_segmenter.py` | Opći MIDI; ne određuje Factory/User identitet | PASS (read-only) |
| G00 | Evidence Registry Foundation | Kanonski JSON registry, validator, lokalni integrity check i deterministički Markdown | `tests/test_master_registry.py` | Governance modul; veže službene i empirijske izvore | PASS |
| A01 | Workspace Persistence Probe | Git checkpoint, ancestry i SHA-256 provjera nove Python/test datoteke | `tests/test_workspace_persistence.py` | Nije Pa800-specifično | PASS: ponovno potvrđen u sljedećem korisničkom turnu |
| A02 | Repository Inventory Auditor | Usporedba registry/MODULE_LOG artefakata s worktreeom i `git ls-tree` | `tests/test_repository_inventory.py` | Governance modul | PASS: 0 errora i 0 warninga |
| D01 | Windows local installer | Lokalni `.venv`, pinned K01 wheel, optional libs i smoke checks | `tests/test_windows_batch_scripts.py` | Nije Pa800-specifično | PARTIAL: statički PASS, čeka stvarni Windows |
| D02 | Windows GUI launcher | venv-only GUI, console i check načini | `tests/test_windows_batch_scripts.py` | Nije Pa800-specifično | PARTIAL: statički PASS, čeka stvarni Windows |
| K02 | Instrument Identity Resolver | Exact/remap/User identitet po stvarnom M10 segmentu, bez izmjene | dedicated + puni Factory corpus | K01 i M10 | PASS (read-only identity) |
| P01 | Immutable Change Plan | Exact event-field diff, dokazi, rizik i USER odluke; nema Apply | `tests/test_change_plan.py` | Governance/safety | PASS |
| P02 | Suggest Policy Engine | Named/versioned pravila i source snapshot kapije; nema Apply | `tests/test_policy_engine.py` | Governance/safety | PASS |
| K03-P | User-selected Factory replacement Proposal | Exact ekskluzivni CC00/CC32/PC Suggest plan; nema Apply | `tests/test_k03_sound_replacement.py` | K01/K02/P01/P02 | PASS (proposal-only) |
| C01 | In-memory Change Engine | USER request, exact CC/PC working-copy patch i rollback; nema disk write | `tests/test_change_engine_verifier.py` | P01/P02/K03-P | PASS (in-memory) |
| V01 | Independent Verifier | Reparse, exact byte/event diff i unauthorized-change gate | `tests/test_change_engine_verifier.py` | C01 + original | PASS (in-memory) |
| W01 | Atomic Verified Writer | Novi `_enhanced` MIDI + JSON, no-overwrite i guarded rollback | `tests/test_verified_writer.py` | V01 PASS | PASS (testirani filesystem scope) |
| G01 | GUI Change Workflow Controller | Eligible segment/target, preview, USER approval, V01, W01 i rollback | backend + Tk runtime testovi | K03-P/C01/V01/W01 | PASS (bounded) |
| R01 | Factory Contextual Profile Builder | K01 × M07 function × Element × CV × role × encoding izolirani profili | unit + puni Factory build | M06--M10/K01/K02 | PASS (reference-only) |
| S01 | Exact Profile Velocity Suggestor | Exact-key p10–p90 bounded Note On outlier plan | `tests/test_profile_suggest_engine.py` | R01/P01/P02 | PASS (Suggest-only) |
| V02 | Specialized Velocity Apply | S01 Note On max 8/max 32 uz explicit switch/RX USER ack | `tests/test_velocity_change_scope.py` | S01/C01/V01/W01 | PASS (bounded explicit scope) |
| G02 | Gold Dataset Guard | Factory container exclusion, Gold hash dedup i source-disjoint split | `tests/test_gold_dataset_guard.py` | Factory/DNA hashovi | PASS; M07 calibration BLOCKED bez labels |
| K03 | Verified Factory Sound Replacement backend | K03-P → C01 → V01 → W01 + G01 bounded pipeline | end-to-end backend/Tk testovi | USER selection/approval/request | PASS (bounded; bez auto Enhance) |

## Pravilo zapisa novog modula

Za svaki novi modul dodati zapis:

```text
ID:
Naziv:
Cilj:
Izvor: Korg Pa800 Owner's Manual, stranice ...
Implementirane datoteke:
Primijenjene funkcije:
Testna naredba:
Rezultat testa:
Poznata ograničenja:
Status: PASS / FAIL / BLOCKED
Sljedeći preporučeni modul:
Razlog prioriteta:
Način primjene:
Koristi:
Rizici i zaštite:
Alternativni pristupi:
Odluka: GO / NO-GO / ČEKA KORISNIKA
```

Svaki završeni modul mora imati završni plan. Taj plan izrađuje tim nakon
pregleda stvarnog koda i MIDI modela; korisnik ne mora sam pogađati sljedeći
tehnički korak.

## Test run — 2026-08-13

Testna naredba:

```bash
python3 -m unittest -v tests/test_style_loader.py tests/test_midi_modules.py
```

Rezultat:

- pet Style Loader testova: PASS;
- `test_format_zero_and_one`: PASS;
- `test_guitar_roles`: PASS;
- `test_gui_module_imports`: BLOCKED / skipped jer `tkinter` nije dostupan;
- ukupno: 8 testova, 7 izvršeno uspješno, 1 opravdano preskočen.

Primijenjeno ovim test-runom:

- potvrđeno mapiranje MIDI formata 0 i 1 na 16 prikaznih slotova;
- potvrđeno razlikovanje rhythm, solo i power-chord guitar uloga;
- potvrđeno read-only učitavanje 3.211 Style Works MIDI datoteka;
- potvrđeno 252 Style skupa, od kojih je 230 potpuno i 22 nepotpuno;
- potvrđeno očuvanje izvornog ZIP SHA-256 zbroja;
- potvrđeno odvajanje događaja iza deklariranog broja taktova;
- konflikt `Fox Shuffle 1_Break.mid` (`1 Bar` / `5 Bars`) sigurno je blokiran
  za vremensku analizu;
- otkriven i zapisan nedostajući GUI preduvjet;
- utvrđeno da dokumentirani Pa800 registar nema produkcijski modul ni zaseban
  test u trenutnom workspaceu i zato ne može imati status `PASS`.

## M06 — Style Works Loader

ID: M06

Naziv: Style Works Loader i nepromjenjivi MIDI model

Cilj: Sigurno učitati ZIP/MIDI, razdvojiti Style/Element/CV/ulogu, izračunati
valjani vremenski prozor i sačuvati sve izvorne događaje bez optimizacije.

Izvor: Korg Pa800 User's Manual, tiskane stranice 114--116 i 134--135
(PDF stranice 118--120 i 138--139).

Implementirane datoteke:

- `style_loader.py`;
- `tests/test_style_loader.py`;
- `README.md`;
- `.gitignore`.

Primijenjene funkcije:

- byte-preserving Standard MIDI parser;
- nepromjenjivi modeli događaja, tracka, datoteke, elementa i kolekcije;
- Style Works grupiranje 13 elemenata;
- CV i kanalno mapiranje Bass 9, Drum 10, Perc 11, Acc1--Acc5 12--16;
- praćenje `CC00.CC32.PC` po kanalu i vremenu;
- deklarirani prozor `broj taktova × metar × PPQ`;
- odvajanje i očuvanje događaja izvan prozora;
- JSON-ready zbirni izvještaj i CLI.

Testna naredba:

```bash
python3 -m unittest -v tests/test_style_loader.py tests/test_midi_modules.py
```

Rezultat testa: 8 testova, 7 PASS, 1 GUI test opravdano preskočen.

Puni korpus:

- 3.211/3.211 valjanih MIDI datoteka;
- 252 Style skupa;
- 230 potpunih i 22 nepotpuna skupa;
- svi MIDI izvori Format 1, division 192 PPQ;
- 29.652 aktivna track-slice zapisa unutar potvrđenog prozora;
- 1.320.691 Note On događaj unutar potvrđenog prozora;
- 29.621 potpuna i 6 nepotpunih instrument-adresa pri Program Changeu;
- 250.242 događaja očuvana izvan deklariranog prozora;
- izvorni ZIP SHA-256 ostao
  `ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`.

Poznata ograničenja:

- ne klasificira solo, podlogu ili Guitar Mode;
- ne mijenja MIDI i nije optimizer;
- jedan element ima konflikt deklariranog broja taktova i ostaje blokiran;
- nepopunjeni Style elementi ne rekonstruiraju se.

Status: PASS

## M07 — Context Classifier

ID: M07

Naziv: Generički Context Classifier i Style adapter

Cilj: Iz potvrđenih MIDI događaja odvojeno odrediti strukturnu ulogu,
glazbenu funkciju, mogući poseban encoding i sigurnosnu politiku, bez izmjene
izvornog MIDI sadržaja.

Izvor: Korg Pa800 User's Manual, tiskane stranice 112, 116, 118--120 i
134--135 (PDF stranice 116, 120, 122--124 i 138--139).

Implementirane datoteke:

- `context_classifier.py`;
- `tests/test_context_classifier.py`;
- `.gitignore`;
- `MODULE_LOG.md`;
- `README.md`;
- `main.tex`.

Primijenjene funkcije:

- generički nepromjenjivi `ClassificationInput` i `FeatureExtractor`;
- lokalno sklapanje Note On/Off parova bez promjene izvora;
- PPQ-proporcionalno grupiranje bliskih onseta za strummane akorde;
- prioritetne strukturne funkcije `RHYTHM_DRUM`, `RHYTHM_PERC` i
  `BASS_ACCOMP`;
- funkcije `ACCOMP_CHORDAL`, `ACCOMP_LINE_RIFF`, `RHYTHM_GUITAR`,
  `SOLO_CANDIDATE` i `UNKNOWN`;
- zaseban `GUITAR_MODE_CANDIDATE` koji se ne zaključuje iz raspona nota;
- ortogonalni `fixed_intro_ending_candidate` samo za neprazan melodijski
  Intro 1/Ending 1 kontekst;
- RX high-note ambiguity zaštita;
- politike `SAFE_BOUNDED`, `SUGGEST_ONLY` i `DO_NOT_TOUCH` s monotono
  najstrožim pravilom;
- blokiranje fizičkog parta s više glazbenih MIDI kanala;
- Style adapter koji prenosi potvrđeni Element, CV, ulogu i valjani prozor bez
  hard-code Style kanala u generičkoj jezgri.

Testna naredba:

```bash
python3 -m unittest -v tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py
```

Rezultat testa: 23 testa, 22 PASS, 1 GUI test opravdano preskočen. Corpus
brojke sada ponovno računa zaseban test, a nisu samo ručno zapisan rezultat.

Puni corpus smoke test:

- 3.211/3.211 MIDI datoteka klasificirano bez iznimke;
- 65.021 track-slice rezultata;
- 27.121 `CLASSIFIED`, 37.850 `UNCERTAIN` i 50 sigurno `BLOCKED`;
- izvorni ZIP SHA-256 ostao
  `ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`.

Poznata ograničenja:

- Program Change segmenti unutar istog slicea još se ne klasificiraju zasebno;
- repetition mjera još ne uključuje inter-onset ritam;
- evidence još koristi opisni tekst bez stabilnih rule ID/status polja;
- Guitar Mode ostaje kandidat bez eksplicitnog `Track Type=Gtr` izvora;
- RX high-note zaštita je namjerno konzervativna i može blokirati sigurnu
  automatizaciju, ali ne dopušta opasnu izmjenu;
- modul je read-only i ne autorizira `Enhance`.

Status: PASS

Sljedeći preporučeni modul: M08 Measure/Phrase Analyzer.

Razlog prioriteta: poboljšanje generičkog MIDI-ja zahtijeva točnu poziciju
svakog događaja u taktu, detekciju ponavljanja i granice fraza prije bilo kakve
korekcije timing-a ili strumminga.

Način primjene: tempo i time-signature mapa pretvaraju tick u
`takt.beat.subdivision`; zatim se po tracku određuju ponovljeni motivi, akcenti,
fraze i odnosi kick--bass ili akord--strum. Prva verzija ostaje Analyze-only.

Koristi: omogućava kontekstualnu korekciju umjesto globalne kvantizacije i
stvara zajedničku osnovu za Drum, Bass, Rhythm Guitar i ostale Instrument
Engine module.

Rizici i zaštite: promjena metra/tempa, pickup takt, triplet/swing i nedovršena
fraza mogu dati pogrešnu segmentaciju; takvi dijelovi ostaju `SUGGEST_ONLY` ili
`DO_NOT_TOUCH` dok model nema dovoljno dokaza.

Alternativni pristupi: odmah graditi Drum Engine ili Groove Template, ali oba
bi bez mjera i fraza ponovila timing logiku i povećala rizik pogrešne primjene.

Odluka: GO za G00 Evidence Registry Foundation prije M08; automatska timing
izmjena ostaje NO-GO dok M08 i kasniji transformation/verifier moduli ne prođu.

## G00 — Evidence Registry Foundation

ID: G00

Naziv: Kanonski Evidence Registry v0 i generirani pregled

Cilj: Uvesti jedan strojno provjerljiv izvor za registry zapise bez pretvaranja
idejnih dokumenata u aktivna pravila i bez lažne certifikacije.

Implementirane datoteke:

- `registry/schema.json`;
- `registry/master_registry.json`;
- `registry/build_registry.py`;
- `registry/MASTER_REGISTRY.md`;
- `tests/test_master_registry.py`;
- `tests/test_context_classifier_corpus.py`.

Primijenjene funkcije:

- stabilni ID namespace po vrsti zapisa;
- četiri neovisne osi: evidence, implementation, validation i certification;
- provjera referenci, lokalnih putanja, SHA-256 zbrojeva i prisutnosti testova;
- obavezna izolacija `IDEA_CATALOG` zapisa;
- determinističko generiranje Markdown pregleda iz JSON-a;
- reproducibilni M07 corpus test za 3.211 datoteka i 65.021 slice rezultat;
- registrirani problemi: parser duplikacija, nekalibrirani M07 score i Factory
  duplikat unutar DNA paketa.

Testne naredbe:

```bash
python3 registry/build_registry.py --check
python3 -m unittest -v tests/test_master_registry.py
python3 -m unittest -v tests/test_context_classifier_corpus.py
python3 -m unittest -v tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py
```

Rezultat testa: registry sadrži 65 zapisa; G00 suite ima 10/10 PASS. Puni suite
ima 33 testa, 32 PASS i jedan opravdani `tkinter` skip.

Poznata ograničenja:

- `MODULE_LOG.md` i `main.tex` ostaju narativni dokumenti, nisu potpuno
  generirani iz registra;
- validator dokazuje lokalni integritet i veze, ali ne može sam dokazati
  glazbenu ispravnost tvrdnje;
- M07 score je heuristički bod, ne kalibrirana vjerojatnost;
- K01, GUI i automatski Enhance ostaju necertificirani.

Status: PASS

Sljedeći preporučeni modul: M08 Measure/Phrase Analyzer, Analyze-only.

Način primjene: izgraditi tempo/metar mapu, položaj događaja u taktu, pickup,
swing/triplet kandidate, ponavljanja i granice fraza. Izlaz M08 ulazi u buduće
Drum, Bass, Rhythm Guitar i Humanize Engine module, ali još ništa ne mijenja.

Koristi: Humanize i strumming kasnije dobivaju stvarnu mjeru, frazu i ulogu
umjesto slučajnog pomicanja tickova.

Rizici i zaštite: promjene metra, pickup, rubovi fraze i nejasan swing ostaju
`SUGGEST_ONLY` ili `DO_NOT_TOUCH`; DNA Factory duplikat ne smije ući u Gold
evaluation skup.

Odluka: GO za M08 Analyze-only; NO-GO za writer i automatski Humanize.

## M08 — Measure/Phrase Analyzer

ID: M08

Naziv: Analyze-only Measure/Phrase Analyzer

Cilj: Izgraditi provjerljiv tempo/metar timeline, položaj događaja u taktu,
egzaktna ponavljanja mjera i konzervativne kandidate granica fraza bez izmjene
MIDI sadržaja.

Izvor: Opći Standard MIDI meta događaji `Set Tempo` i `Time Signature`.
Pa800-specifična tvrdnja nije uvedena; Style adapter koristi samo kontekst i
vremenski prozor koje je prethodno potvrdio M06.

Implementirane datoteke:

- `measure_phrase_analyzer.py`;
- `tests/test_measure_phrase_analyzer.py`;
- `README.md`;
- `registry/master_registry.json`;
- `registry/MASTER_REGISTRY.md`;
- `MODULE_LOG.md`;
- `main.tex`.

Primijenjene funkcije:

- nepromjenjivi modeli tempo i metar točaka;
- pozicija događaja kao mjera, beat i tick unutar beata;
- podrška za promjene metra na timelineu i eksplicitno upozorenje kada promjena
  ili kraj prozora prekine mjeru;
- blokiranje konfliktnih tempo/metar vrijednosti na istom ticku;
- egzaktni potpis Note On sadržaja normaliziran na početak mjere;
- grupiranje egzaktno ponovljenih nepraznih mjera;
- `FIRST_ONSET` i `LONG_GAP_CANDIDATE` granice s razlogom i pouzdanošću;
- Style adapter koji koristi samo `valid_event_indexes` i `valid_end_tick` iz
  M06 te prenosi SHA-256 izvora;
- obavezna Analyze-only zaštita bez writera, kvantizacije ili Humanizea.

Testna naredba:

```bash
python3 -m unittest -v tests/test_measure_phrase_analyzer.py tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py
```

Ovaj izvorni testni run zamijenjen je strožim hard-gate runom opisanim u
odjeljku "M08--M10 neovisni audit i corpus certifikacija".

Poznata ograničenja:

- frazna granica nakon duge stanke heuristički je kandidat, ne potvrđena
  glazbena fraza;
- ponavljanje trenutno zahtijeva egzaktno jednake note i relativne tickove;
- nema transpozicijski, ritmički-sličan ni perceptivni motif matcher;
- nema swing/triplet klasifikacije ni pickup rekonstrukcije;
- bez eksplicitnog tempa ne izvodi vrijeme u sekundama;
- SMPTE division i konfliktni timeline ostaju blokirani;
- modul ne autorizira nikakvu MIDI izmjenu.

Status: PASS (read-only M08 scope)

Sljedeći preporučeni modul: zajednički read-only Instrument Measurement Engine
koji koristi M07 ulogu i M08 mjeru/frazu za velocity, trajanje, gustoću i
artikulatorne statistike po potvrđenom kontekstu.

Razlog prioriteta: M07 sada daje funkciju parta, a M08 njegov vremenski
kontekst. Sljedeći siguran korak jest izmjeriti instrument po tim granicama,
prije Policy, Suggest ili Change Enginea.

Način primjene: samo analiza i izvještaj; svi nepoznati, konfliktni, Guitar
Mode/RX i fixed slučajevi zadržavaju strožu postojeću zaštitu.

Koristi: zajednička mjerna osnova za buduće Drum, Bass, Guitar i ostale Family
Engine module bez dupliciranja timeline logike.

Rizici i zaštite: heuristička fraza ne smije postati dopuštenje za editiranje;
izlaz mora zadržati status, razlog i confidence te izvorne bajtove.

Alternativni pristupi: K01 Pa800 registry može se razvijati kao neovisna grana,
ali K02/K03 ostaju blokirani dok K01 nema produkcijski registar i test.

Odluka: GO za read-only Instrument Measurement Engine; NO-GO za timing writer,
automatski Humanize, strumming korekciju i bilo koji Enhance bez Policy i
Verifier modula.

## M09 — Instrument Measurement Engine

ID: M09

Naziv: Zajednički read-only Instrument Measurement Engine

Cilj: Deterministički izmjeriti note, velocity, trajanje, gustoću, polifoniju,
kontrolere i statistike po mjeri/frazi, uz potpuno očuvanje statusa i zaštita
iz M07 i M08.

Izvor: Opći Standard MIDI Note On/Off, Control Change, pitch bend i aftertouch
događaji. M09 ne uvodi Pa800-specifičnu tvrdnju; Style adapter koristi samo
potvrđene M06 događaje, M07 kontekst i M08 timeline.

Implementirane datoteke:

- `instrument_measurement_engine.py`;
- `tests/test_instrument_measurement_engine.py`;
- `.gitignore`;
- `README.md`;
- `registry/master_registry.json`;
- `registry/MASTER_REGISTRY.md`;
- `MODULE_LOG.md`;
- `main.tex`.

Primijenjene funkcije:

- FIFO sparivanje Note On/Off događaja po kanalu i visini;
- zasebno brojanje zatvorenih, nezatvorenih i orphan Note Off događaja;
- distribucije minimuma, maksimuma, sredine, medijana i populacijske standardne
  devijacije za velocity i trajanje;
- trajanje u tickovima i beatovima te gustoća nota po beatu;
- najveća stvarna sounding polifonija i najveća egzaktna onset polifonija;
- grupiranje Control Change vrijednosti po broju kontrolera;
- brojanje pitch bend, poly-aftertouch i channel-aftertouch događaja;
- statistike po M08 mjeri i kandidatu fraze;
- nasljeđivanje M07 funkcije, encodinga i najstrože edit politike;
- statusi `READY`, `PARTIAL` i `BLOCKED` bez skrivanja dostupnih činjenica;
- obavezna Analyze-only zaštita bez Suggest, Change, Humanize ili Enhance
  putanje.

Testna naredba:

```bash
python3 -m unittest -v tests/test_instrument_measurement_engine.py tests/test_measure_phrase_analyzer.py tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py
```

Ovaj izvorni testni run zamijenjen je strožim hard-gate runom opisanim u
odjeljku "M08--M10 neovisni audit i corpus certifikacija".

Poznata ograničenja:

- kontroleri se mjere brojčano, ali se još ne tumače kao instrument-specifična
  artikulacija;
- phrase profil nasljeđuje heurističku M08 granicu i ne proglašava je činjenicom;
- nema segmentacije po promjenama `CC00.CC32.PC` unutar istog tracka;
- nema Family Engine pravila, Factory usporedbe ni preporučenih raspona;
- otvorene ili orphan note daju `PARTIAL`, a blokirani M07/M08 kontekst daje
  `BLOCKED`;
- modul ne autorizira MIDI izmjenu.

Status: PASS (read-only M09 scope)

Sljedeći preporučeni modul: Instrument Segmenter koji razdvaja jedan logički
part na vremenske segmente prema Bank Select i Program Change događajima, ali
još bez tvrdnje je li adresa Factory, User ili Unknown.

Razlog prioriteta: M09 sada pouzdano mjeri part, ali različiti instrumenti
unutar istog tracka još bi bili pomiješani u isti profil. Segmentacija se može
izvesti općim MIDI pravilima bez čekanja blokiranog K01 registra.

Način primjene: read-only segmenti s početnim/završnim tickom, punom ili
nepotpunom adresom, pripadajućim događajima i zasebnim M09 mjerenjem.

Koristi: sprječava miješanje statistika dvaju instrumenata i priprema siguran
ulaz za budući K02 identity resolver kada K01 bude završen.

Rizici i zaštite: nepotpuna Bank Select adresa, Program Change na granici note,
aktivna nota preko granice i višekanalni track moraju ostati jasno označeni i
ne smiju proizvesti pretpostavljeni Factory identitet.

Alternativni pristupi: razvijati Family Engine odmah, ali bez segmentacije bi
profil mogao spojiti dvije zvučne boje i dati pogrešan referentni kontekst.

Odluka: GO za read-only Instrument Segmenter; NO-GO za Factory/User identitet,
preporuke, Policy ili Change Engine dok njihovi preduvjeti ne prođu.

## M10 — Instrument Segmenter

ID: M10

Naziv: Read-only Instrument Segmenter

Cilj: Razdvojiti jedan događajni tok po MIDI kanalu i Program Change
granicama, sačuvati aktivni CC00/CC32 snapshot te izračunati zaseban M09 profil
bez proglašavanja Factory, User ili Unknown identiteta.

Izvor: Opći Standard MIDI redoslijed Bank Select `CC00`, Bank Select `CC32` i
Program Change događaja. Modul nije Pa800 registry i ne koristi K01 tvrdnje.

Implementirane datoteke:

- `instrument_segmenter.py`;
- `tests/test_instrument_segmenter.py`;
- `.gitignore`;
- `README.md`;
- `registry/master_registry.json`;
- `registry/MASTER_REGISTRY.md`;
- `MODULE_LOG.md`;
- `main.tex`.

Primijenjene funkcije:

- nepromjenjivi segmenti po MIDI kanalu;
- granica na svakom Program Change događaju;
- Bank Select stanje primjenjuje se tek pri sljedećem Program Changeu;
- statusi adrese `COMPLETE`, `INCOMPLETE` i `NO_PROGRAM`;
- puni prikaz `CC00.CC32.PC` samo kada su sva tri dijela prisutna;
- čisti CC00/CC32 setup prije prvog Program Changea ne stvara lažni segment;
- stvarni glazbeni događaji prije prvog Program Changea ostaju zaseban
  nepotvrđen segment;
- redoslijed događaja, a ne samo tick, određuje granicu kada događaji dijele
  isti tick;
- detekcija nota koje prelaze Program Change granicu;
- zaseban M07 kontekst i M09 profil za svaki segment;
- višekanalni ulaz razdvaja se, ali cijeli rezultat ostaje `PARTIAL`;
- `identity_status` je obavezno `UNRESOLVED`;
- nema writer, replacement ili identity-resolver funkcije.

Testna naredba:

```bash
python3 -m unittest -v tests/test_instrument_segmenter.py tests/test_instrument_measurement_engine.py tests/test_measure_phrase_analyzer.py tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py
```

Ovaj izvorni testni run zamijenjen je strožim hard-gate runom opisanim u
odjeljku "M08--M10 neovisni audit i corpus certifikacija".

Poznata ograničenja:

- ne određuje je li adresa Factory, User ili nepoznata;
- nepotpuna adresa ostaje `INCOMPLETE` bez GM zamjene ili zadane banke;
- nota preko Program Change granice ostaje prijavljena, a ne prebačena u drugi
  segment;
- segmentni M09 profil zasad ne uključuje zaseban izrez M08 timelinea;
- višekanalni fizički part ostaje `PARTIAL` iako su kanali prikazani odvojeno;
- nema promjene izvornog MIDI sadržaja.

Status: PASS (read-only M10 scope)

## M08--M10 neovisni audit i corpus certifikacija

Neovisni testni audit pronašao je rubne slučajeve koje početni testovi nisu
pokrivali. Razvoj sljedećeg modula zaustavljen je dok nedostaci nisu dobili
izravne izvršne testove i popravke.

Popravljeno i izravno testirano:

- M08 egzaktni potpis uključuje onset, kanal, pitch, attack velocity, trajanje,
  release velocity i vrstu zatvaranja note;
- M08 čuva fazu mjere za prozor koji ne počinje na ticku nula te razlikuje
  konflikt unutar aktivnog prozora od konflikta nakon njegova kraja;
- M09 prihvaća M08 timeline samo kada SHA-256, PPQ i granice prozora odgovaraju
  istom izvoru;
- M09 blokira zajednički višetrack note profil, mjeri oba tipa aftertoucha i ne
  izračunava gustoću bez potvrđenog završetka prozora;
- M10 prijavljuje i nezatvorenu notu preko Program Change granice, dodjeljuje
  globalno jedinstvene ordinale te cross-track redoslijed na istom kanalu i
  ticku konzervativno označava kao `PARTIAL`;
- `.gitignore` izričito uključuje implementacije, njihove testove i corpus test;
- generirani Evidence Registry mora biti aktualan i završiti uspješnim
  `--check` rezultatom.

Dedicated testovi: M08 9/9 PASS, M09 9/9 PASS i M10 9/9 PASS.

Corpus test `tests/test_analysis_pipeline_corpus.py` ponovno obrađuje svih
3.211 MIDI datoteka i 65.021 track-slice iz arhiva SHA-256
`ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`.
Provjerava 82.917 segmenata, fiksne raspodjele statusa, deterministički digest
`a0a3d7a9b03aa53cf23bd3819e4168c04c11bf5a9dbd8f408f2978cd51a0b821`
i nepromijenjen SHA-256 izvornog ZIP-a.

Aktualna hard-gate naredba:

```bash
python3 -m unittest -v tests/test_analysis_pipeline_corpus.py tests/test_instrument_segmenter.py tests/test_instrument_measurement_engine.py tests/test_measure_phrase_analyzer.py tests/test_master_registry.py tests/test_context_classifier_corpus.py tests/test_context_classifier.py tests/test_style_loader.py tests/test_midi_modules.py
```

Rezultat aktualnog hard-gate runa: 61 test ukupno, 60 PASS, jedan GUI test
`BLOCKED`/preskočen zbog nedostupnog `tkintera` i nula failurea.

Status ostaje ograničen na read-only M08--M10 funkcionalnost. GUI je i dalje
`BLOCKED` bez `tkintera`, a identity, writer, Enhance i hardware ponašanje nisu
certificirani ovim testovima.

Sljedeći preporučeni modul: K01 produkcijski Pa800 Sound/Drum Kit Registry,
jer M10 sada proizvodi potpune i nepotpune adrese koje se mogu sigurno
usporediti s kanonskim službenim popisom.

Razlog prioriteta: K02 identity resolver više ne treba rješavati segmentaciju,
ali je i dalje blokiran dok K01 nema strojno provjerljiv potpuni registar i
test pokrivenosti službenih tablica.

Način primjene: transkribirati samo službene User's Manual tablice u podatkovni
modul, navesti stranice svakog skupa, zapisati remap iznimke i testirati
jedinstvenost/potpunost adresa.

Koristi: omogućava budućem K02 da razlikuje `FACTORY_CONFIRMED`,
`USER_SLOT_CONFIRMED`, `UNKNOWN`, `CONFLICT` i `INCOMPLETE_ADDRESS` bez
nagađanja po nazivu ili General MIDI programu.

Rizici i zaštite: OCR ili ručni prijepis može zamijeniti banku/program; svaki
zapis treba izvorne stranice, reproducibilan generator i test graničnih/remap
slučajeva.

Alternativni pristupi: nastaviti s generičkim Family Engineom, ali K01 je sada
izravni blocker za postojeće K02/K03 grane i donosi veću strukturnu korist.

Odluka: GO za K01 produkcijski registry; NO-GO za automatsko mapiranje ili
zamjenu Sounda dok K01 i K02 ne prođu.
## Import, A01 i A02 audit — 2026-08-14

Izvorni Google Drive ZIP nije sadržavao `.git` metapodatke. Sigurno je
raspakiran nakon provjere 39 putanja; izvorni ZIP imao je SHA-256
`80e05a0c2ecedf70bd5785fcabf68d7c5ec687fa008c274969fa29f89431de20`.
Detaljni nalaz nalazi se u `audit/IMPORT_AUDIT_2026-08-14.md`.

Prvo izvršenje `python -m pytest -q` završilo je s 59 PASS i 2 FAIL. Oba FAIL-a
bila su G00 packaging problema: dva UTF-8 naziva iz ZIP-a bila su CP437
mojibake, a generirani `MASTER_REGISTRY.md` nije imao završni newline. Nazivi su
lossless vraćeni i Markdown je ponovno generiran; `tests/test_master_registry.py`
zatim ima 10/10 PASS.

Stvarni snapshot sadrži `instrument_segmenter.py` i njegove testove, ali ne
sadrži produkcijski K01 Factory registry, K02 resolver ni njihove namjenske
testove. K01 zato ostaje `FAIL`, K02 `BLOCKED`, a K03/Change/Writer/Verifier i
automatski Enhance ostaju `NO-GO`.

A01 implementira Git checkpoint probe, ali status ostaje `PARTIAL` dok se isti
commit, Python artefakt i test ne potvrde u sljedećem korisničkom turnu. A02
implementira deterministički repository inventory nad registryjem, MODULE_LOG
ID-jevima, worktreeom i `git ls-tree`; njegov konačni status također čeka A01.

### RUN-008 — puni aktualni testni skup

Testna naredba:

```bash
python -m pytest -q
```

Rezultat: 65 testova i 6 subtestova `PASS`, 0 `FAIL`, 0 `SKIP`, vrijeme
195,99 s. Ovaj run uključuje puni Factory corpus, G00, A01 lokalni checkpoint
i A02 unit testove. Ne certificira K01/K02, writer, Enhance, hardver, zvuk ni
interaktivni GUI.

## RUN-009 i read-only učitavanje baza — 2026-08-14

A01 checkpoint ponovno je izvršen nakon nove korisničke poruke. Commit
`70bc744d28fabccfea306416c331c7c915fa7290` ostao je ancestor aktualnog HEAD-a,
a Python probe, inventory alat i oba testa imaju iste SHA-256 vrijednosti.
`tests/test_workspace_persistence.py` ima 1/1 PASS. A01 i A02 zato prelaze u
ograničeni governance `PASS`.

Factory Styles arhiv učitan je read-only u 21,069 s: 3.211 MIDI datoteka, 252
Style skupa, 230 potpunih, 22 nepotpuna, 29.652 aktivna track-slice zapisa i
1.320.691 Note On događaj unutar deklariranih prozora. Izvorni SHA-256 ostao je
nepromijenjen.

Gold DNA nested arhiv sadrži 182/182 valjana MIDI-ja: 180 Format 0 i 2 Format
1, ukupno 5.047.285 događaja i 2.272.811 Note On događaja. Nema SHA-256
duplikata između Gold DNA MIDI-ja i 3.211 Factory MIDI-ja. Cijela kopija
`Split Factory Styles.zip` unutar DNA paketa potvrđena je kao točan duplikat i
isključena iz runtime indeksa.

Lokalni `loaded-data/corpus_catalog.sqlite3` indeksira 3.393 jedinstveno
odabrana zapisa izvora (3.211 Factory + 182 Gold DNA). SQLite
`PRAGMA integrity_check` vraća `ok`; izvorni Factory i DNA hashovi ostali su
nepromijenjeni. To je runtime read-only katalog, nije K01/K02 produkcijski
registar i ne autorizira Enhance.

`Valja.rar` je potvrđen kao RAR5, ali ostaje `BLOCKED`: nema instaliranog i
provjerenog RAR5 dekodera. Arhiv nije raspakiran niti izmijenjen.

## M01/M02 — SMF Format 2 zatvaranje — 2026-08-14

ID: M01/M02 Format 2 scope

Cilj: Strukturno učitati SMF Format 2 bez spajanja njegovih neovisnih sekvenci
u lažnu globalnu pjesmu, tempo mapu ili trajanje.

Izvor: Opći SMF model; modul nije Pa800-specifičan.

Implementirane datoteke:

- `midi_enhancer.py`;
- `midi_instruments.py`;
- `midi_gui.py`;
- `tests/test_midi_format2.py`.

Primijenjene funkcije i zaštite:

- svaki Format 2 fizički track prikazuje se kao zasebna `Sequence`;
- tempo i trajanje računaju se zasebno po sekvenci;
- globalni `duration_ticks`, `duration_seconds`, `initial_bpm` i
  `tempo_changes` ostaju `null` umjesto izmišljene vrijednosti;
- ukupni rezultat dobiva `PARTIAL` i `INDEPENDENT_SEQUENCES` oznaku;
- `pretty_midi` globalni beat/tempo i `music21` globalna harmonijska analiza
  blokiraju se za Format 2 čak i ako su biblioteke dostupne;
- GUI model prikazuje `PER SEQUENCE` i `PARTIAL / READ-ONLY`;
- originalni SHA-256 i bajtovi ostaju nepromijenjeni;
- oba ugrađena parsera moraju se složiti o formatu, broju trackova, divisionu,
  hashu i završnom ticku svake testne sekvence.

Testna naredba:

```bash
python -m pytest -q tests/test_midi_format2.py tests/test_midi_modules.py
```

Namjenski/regression rezultat: 7/7 PASS. Format 2 testovi: 4/4 PASS. Puni
`python -m pytest -q` rezultat: 69 testova i 6 subtestova PASS, 0 FAIL, 0 SKIP,
196,33 s.

Status: `PASS` za ograničeni read-only SMF Format 2 scope. To nije puna SMF
certifikacija; ISSUE-006 cross-parser event parity i širi SMPTE/rubni testovi
ostaju sljedeći M01 zadatak.

Odluka: GO za puni regression run; Enhance ostaje NO-GO.

## M01/M06 — ISSUE-006 parser parity guard — 2026-08-14

Cilj: Zadržati postojeće dvije parser putanje samo ako izravni test dokazuje da
isti MIDI tumače jednako u core read-only scopeu.

Implementirane datoteke:

- `midi_enhancer.py`;
- `style_loader.py`;
- `tests/test_parser_parity.py`.

Ujednačene strukturne kapije:

- SMF mora imati najmanje jedan track;
- Format 0 mora imati točno jedan track;
- PPQ division nula se odbija;
- SMPTE prihvaća samo frame codeove -24, -25, -29 i -30;
- SMPTE ticks-per-frame nula se odbija;
- nedostajući End-of-Track prijavljuju oba parsera;
- izvorni bajtovi i SHA-256 ostaju nepromijenjeni.

Parity fingerprint uspoređuje format, track count, division, hash, završne
tickove, vrste događaja, zatvorene i izvedene nezatvorene note, tempo, metar,
tonalitet, nazive trackova, programe, kontrolere i pitch bend.

Prvi corpus run pronašao je 410 prividnih razlika. Audit je dokazao da su to
bile dokumentirane izvedene `unterminated_notes`: glavni analizator ih
materijalizira do kraja tracka, a byte-preserving model ih čuva kao otvorene
Note On događaje. Oracle je ispravljen da iz istih potvrđenih događaja izvede
istu semantiku, bez izmjene produkcijskog MIDI sadržaja.

Testna naredba:

```bash
python -m pytest -q tests/test_parser_parity.py
```

Rezultat: 5 testova i 3.223 subtesta PASS. Svih 3.211 Factory MIDI datoteka ima
isti core fingerprint u oba parsera, a Factory ZIP SHA-256 ostaje
`ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e`.
Puni `python -m pytest -q` rezultat: 74 testa i 3.229 subtestova PASS, 0 FAIL,
0 SKIP, 235,43 s.

Status: `PASS` za izravno testirani core-parity scope. Parseri još nisu fizički
objedinjeni i puni SMF/writer parity nije certificiran.

## M05 — automatizirani GUI runtime — 2026-08-14

Cilj: Stvarno stvoriti Tk root i `MidiEnhancerApp`, a ne samo importirati modul.

Okruženje nije imalo sistemski X server. U `loaded-data/xvfb-runtime` su zato
bez root instalacije raspakirani službeni Debian 13 paketi `xvfb`,
`xserver-common`, `xkb-data`, `x11-xkb-utils`, `libxfont2`, `libfontenc1` i
`libunwind8`. SHA-256 svakog `.deb` paketa i lokalnog Xvfb binaryja nalazi se u
`loaded-data/xvfb-runtime/MANIFEST.json`. Sistemski paketi nisu mijenjani.

Xvfb je pokrenut na displayu `:102`. Stvoreni su Tk 8.6 root, prozor
`Prism MIDI Enhancer` geometrije 1360x900 i svih 16 track kartica.

Implementirane datoteke:

- `tests/test_gui_runtime.py`;
- ažurirani G00 zapisi i dokumentacija.

Test pokriva:

- stvarni Tk render i 16 kartica;
- sinkroni prikaz analiziranog Format 0 MIDI-ja;
- sažetak, note i channel-slot mapiranje;
- JSON izvoz u novu datoteku i očuvanje originala;
- Format 2 `PER SEQUENCE` i `PARTIAL / READ-ONLY` zaštitu.

Testna naredba u aktivnom virtualnom displayu:

```bash
DISPLAY=:102 python -m pytest -q tests/test_gui_runtime.py tests/test_midi_modules.py
```

Namjenski rezultat: 5/5 PASS, uključujući 2/2 stvarna GUI runtime testa. Puni
`DISPLAY=:102 python -m pytest -q` rezultat: 76 testova i 3.229 subtestova PASS,
0 FAIL, 0 SKIP, 234,64 s.

Status: `PASS` za automatizirani virtual-display scope. Native desktop
pakiranje, ljudski UX, accessibility i fizički korisnički workflow ostaju
`PARTIAL` certifikacija i budući release zadatak.

## K01 — Pa800 Factory Registry — 2026-08-14

Cilj: Reproducibilno izgraditi read-only Factory identitet samo iz potvrđenog
Pa800 User's Manuala i pune `CC00.CC32.PC` adrese.

Normativni izvor:

- `prism-uploads/Pa800-201UM-ENG.pdf`;
- SHA-256 `b7df16fb0113d998a6411ea1c28971707021da8bc0b728aff98eafcceb57c71b`;
- 344 PDF stranice;
- Sound tablice: tiskane 275--283 / PDF 279--287;
- Drum Kit tablica: tiskana 295 / PDF 299.

Reproducibilni extractor je pinned `pypdf 6.16.0` wheel SHA-256
`8c47581faa1cba7006ac269da30075c929c251cc4ffbafb2bcbe260306631118`.
Wheel s licencom nalazi se u `vendor/`; generator odbija drugi hash ili verziju.

Implementirane datoteke:

- `registry/generate_pa800_factory.py`;
- `registry/pa800_factory_registry.json`;
- `pa800_registry.py`;
- `tests/test_pa800_factory_registry.py`;
- `requirements-k01.txt`;
- `vendor/pypdf-6.16.0-py3-none-any.whl`.

Generator reproducira:

- 1.006 jedinstvenih Factory Sound adresa (`CC00=121`);
- 65 imenovanih Drum Kit adresa (`CC00=120`, 64 jedinstvena naziva);
- ukupno 1.071 jedinstvenu punu adresu;
- 15 službenih Drum Kit remap redaka i jedan User Drum Kit range;
- jednu identičnu dvostruku izvornu Sound pojavu: `121.0.71 Clarinet GM`;
- `120.0.48` i `120.0.49` kao dvije adrese naziva `Orchestra Kit GM`;
- imenovane `120.0.57 SFX Kit 2` i `120.0.58 Synth Kit`;
- remap `57--63 -> 56` kao `CONFLICT` za 57--58, uz nepreklopljeni dokaz
  59--63. K01 remap ne primjenjuje na MIDI.

Lookup je immutable i potvrđuje samo točnu punu Factory adresu. Nepotpuna ili
nepoznata adresa ostaje bez rezultata; User range potvrđuje lokaciju, ne sadržaj.

Testne naredbe:

```bash
python registry/generate_pa800_factory.py --check
python -m pytest -q tests/test_pa800_factory_registry.py
```

Namjenski rezultat: 7/7 PASS. Puni `DISPLAY=:103 python -m pytest -q`
rezultat: 83 testa i 3.229 subtestova PASS, 0 FAIL, 0 SKIP, 237,61 s.

Status: `PASS` za ograničeni K01 read-only Factory identity/generator scope.
K02 resolver, remap odluka, Sound replacement i bilo kakva MIDI izmjena nisu
dio K01 i ostaju neimplementirani.

## K02 — Instrument Identity Resolver — 2026-08-14

Cilj: Povezati stvarni immutable M10 `InstrumentSegment` s K01 dokazom bez
izmjene segmenta, događaja ili MIDI datoteke.

Implementirane datoteke:

- `instrument_identity_resolver.py`;
- `tests/test_instrument_identity_resolver.py`;
- prošireni `tests/test_analysis_pipeline_corpus.py`.

K02 vraća isključivo eksplicitne statuse:

- `FACTORY_CONFIRMED` za exact K01 adresu ili jednoznačni službeni remap;
- `USER_SLOT_CONFIRMED` samo za potvrđenu User Drum Kit lokaciju, bez naziva
  ili sadržaja;
- `UNKNOWN` za potpunu adresu bez K01/User/remap dokaza;
- `CONFLICT` za imenovanu adresu koja se preklapa s remap pravilom;
- `INCOMPLETE_ADDRESS` kada nedostaje CC00 ili CC32;
- `NO_PROGRAM` prije prvog Program Changea.

Službeni remap čuva i traženu i ciljnu adresu, ali ne prepisuje MIDI. Za
`120.0.57` i `120.0.58` rezultat je `CONFLICT`; za nepreklopljeni `120.0.59`
rezultat je remap-potvrđen `120.0.56 SFX Kit GM`. Svaki rezultat nosi rule ID,
evidence status, upozorenja, zaštite i izvorni M10 segment čiji
`identity_status` ostaje `UNRESOLVED`.

Dedicated testna naredba:

```bash
python -m pytest -q tests/test_instrument_identity_resolver.py
```

Rezultat: 6/6 PASS.

Puni Factory corpus proširuje postojeći M08--M10 test i reproducira 82.917 K02
rezultata:

- 29.604 `FACTORY_CONFIRMED`;
- 15 `CONFLICT`;
- 6 `INCOMPLETE_ADDRESS`;
- 53.292 `NO_PROGRAM`;
- 0 automatski primijenjenih remapa u ovom korpusu;
- digest `5245ec7ac6c66e7642c5748accdaa5a5188b807b11a2057b3651f0e4ef450227`.

Originalni Factory ZIP SHA-256 ostaje nepromijenjen. Puni
`DISPLAY=:104 python -m pytest -q` rezultat: 89 testova i 3.233 subtesta PASS,
0 FAIL, 0 SKIP, 243,18 s. Status: `PASS` za ograničeni K02 read-only identity
scope. K03, Change Plan, writer i Verifier ostaju `NO-GO`.

## P01/P02 — Immutable Change Plan i Suggest Policy Engine — 2026-08-14

Cilj: Uvesti strojno provjerljiv prijedlog prije K03/Change Enginea bez ikakve
MIDI primjene.

Implementirane datoteke:

- `change_plan.py`;
- `policy_engine.py`;
- `tests/test_change_plan.py`;
- `tests/test_policy_engine.py`.

Svaki `EventMutation` zaključava:

- fizički track/event indeks;
- apsolutni tick, vrstu i kanal;
- točno polje `data[0]` ili `data[1]`;
- staru i novu 7-bitnu vrijednost;
- SHA-256 sirovog izvornog eventa;
- deterministički mutation ID.

Svaki prijedlog nosi stabilni proposal ID, rule ID/verziju, ulazna mjerenja,
evidence reference/status, confidence samo za `INFERRED`, rizik, expected diff
i zaštite. `CONFLICT`, `UNKNOWN`, `UNSUPPORTED`, `BLOCKING`, nepoznato pravilo,
pogrešna verzija, nedostajući ili promijenjeni source event blokiraju Suggest.

Plan postoji samo u fazi `SUGGEST`. Odluku može zapisati samo actor `USER` uz
ISO-8601 vrijeme s vremenskom zonom. Povijest odluka je immutable; najnovija
odluka određuje status. Čak i potpuno `APPROVED` plan uvijek ima
`apply_authorized=false` jer Change Engine i Verifier ne postoje.

Testna naredba:

```bash
python -m pytest -q tests/test_change_plan.py tests/test_policy_engine.py
```

Namjenski rezultat: 12 testova i 3 subtesta PASS. Puni
`DISPLAY=:105 python -m pytest -q` rezultat: 101 test i 3.236 subtestova PASS,
0 FAIL, 0 SKIP, 238,08 s.

Status: P01 i P02 `PASS` za ograničeni immutable data/Suggest policy scope.
K03 proposal builder, Change Engine, writer i Verifier ostaju `NO-GO`.

## K03-P — User-selected Factory replacement Proposal Builder — 2026-08-14

Cilj: Iz stvarnog M10/K02 segmenta i eksplicitno korisnički odabrane K01
Factory adrese napraviti samo immutable Suggest plan.

Implementirane datoteke:

- `k03_sound_replacement.py`;
- `tests/test_k03_sound_replacement.py`.

Prvi K03-P scope dopušta samo postojeće događaje. Program Change mora točno
odgovarati granici segmenta. CC00/CC32 se smiju predložiti samo kada postoje na
istoj granici i njihov event ref nije dijeljen s drugim M10 segmentom.
Nedostajući Bank Select zahtijevao bi insertion i zato se blokira. Naslijeđeni
ili shared Bank Select također se blokira.

Builder zahtijeva:

- `user_selected=true`;
- complete M10 adresu;
- K02 `FACTORY_CONFIRMED` ili `USER_SLOT_CONFIRMED`;
- exact K01 Factory target;
- kompatibilnu vrstu Sound/Drum Kit;
- target različit od tražene izvorne adrese;
- exact source event snapshot koji prolazi P02 Policy Engine.

`CONFLICT`, `UNKNOWN`, `INCOMPLETE_ADDRESS`, `NO_PROGRAM`, non-Factory target,
kind mismatch, event insertion, shared/inherited bank i no-op su blokirani.
User Drum Kit lokacija smije predložiti samo Factory Drum Kit cilj i dobiva
`HIGH` rizik; potvrđeni Factory-to-Factory prijedlog dobiva `MEDIUM`.

Čak i nakon naknadne USER `APPROVE` odluke plan zadržava
`apply_authorized=false` i MIDI bajtovi ostaju isti.

Testna naredba:

```bash
python -m pytest -q tests/test_k03_sound_replacement.py
```

Namjenski rezultat: 7/7 PASS i 4 subtesta. Puni
`DISPLAY=:105 python -m pytest -q` rezultat: 108 testova i 3.240 subtestova
PASS, 0 FAIL, 0 SKIP, 239,67 s.

Status: K03-P `PASS` za Suggest proposal-only scope. K03 Change backend,
Change Engine, writer, rollback i Verifier ostaju `NO-GO`.

## D01/D02 — Windows install.bat i run.bat — 2026-08-14

Cilj: Omogućiti korisniku lokalnu Windows instalaciju i pokretanje bez
sistemskog Python package scopea i bez MIDI izmjena.

Implementirane datoteke:

- `install.bat`;
- `run.bat`;
- `tests/test_windows_batch_scripts.py`.

`install.bat`:

- zahtijeva Python 3.11+ i tkinter;
- kreira lokalni `.venv` u projektu;
- koristi samo `.venv\\Scripts\\python.exe` nakon kreiranja;
- instalira `pypdf 6.16.0` iz lokalnog `vendor/` foldera s
  `--no-index --require-hashes`;
- opcionalno instalira numpy, mido, pretty_midi i music21;
- ima `minimal` način bez opcionalnih biblioteka;
- izvršava K01 generator `--check`, G00 registry `--check` i GUI/K01 smoke test;
- ne sadrži writer, Enhance ni MIDI output naredbu.

`run.bat`:

- default pokreće `midi_gui.py` preko lokalnog `pythonw.exe`;
- `run.bat console` prikazuje runtime greške;
- `run.bat check` ponavlja installation/registry smoke provjeru;
- odbija rad kada `.venv` ne postoji.

Obje datoteke koriste Windows CRLF. Statički test potvrđuje venv izolaciju,
pinned local wheel, check/console putanje i odsustvo destruktivnih naredbi.

Testna naredba:

```bash
python -m pytest -q tests/test_windows_batch_scripts.py
```

Rezultat: 3/3 PASS. Status D01/D02 ostaje `PARTIAL`: implementacija i statički
ugovor su PASS, ali stvarno `cmd.exe`/Windows/Tk izvršavanje mora potvrditi
korisnik u sljedećem koraku.

## C01/V01 — In-memory Change Engine, rollback i independent Verifier — 2026-08-14

Cilj: Sigurno izvršiti potpuno odobren exact plan na radnoj kopiji, ali još ne
pisati datoteku.

Implementirane datoteke:

- `change_engine.py`;
- `change_verifier.py`;
- `tests/test_change_engine_verifier.py`.

C01 zahtijeva potpuno USER-odobren plan i zaseban `ChangeExecutionRequest` čiji
actor mora biti `USER`, vrijeme mora imati timezone, a plan/source/approval
skup mora odgovarati. Source SHA-256 se provjerava prije radne kopije.

Engine ne reserializira MIDI. Neovisno locira postojeći channel-event data bajt
u originalnom track bodyju, provjerava raw snapshot i mijenja samo `bytearray`
kopiju. Prvi scope dopušta samo control-change `data[1]` i Program Change
`data[0]`. Running status, delta, status bajt, redoslijed i duljina ostaju isti.
Rezultat je uvijek `PENDING_VERIFICATION`, `verified=false` i
`save_authorized=false`. Rollback vraća točne originalne bajtove i hash.

V01 zasebno reparsira original i izlaz, vlastitim kodom locira očekivane byte
offsete te uspoređuje cijeli byte diff, strukturu, track/event set, tickove,
status/running status, data vrijednosti i applied log. PASS je moguć samo kada
su sve i jedine razlike odobrene. FAIL vraća `verified_bytes=None` i
`save_authorized=false`.

Testovi pokrivaju:

- exact CC32/PC working-copy promjenu;
- verifier PASS i očuvanje Note događaja;
- running status;
- exact rollback;
- neodobren plan i non-USER request;
- tampered source SHA;
- dodatni neodobreni note velocity bajt;
- forged applied offset;
- truncated/neparsabilan output.

Testna naredba:

```bash
python -m pytest -q tests/test_change_engine_verifier.py
```

Namjenski rezultat: 6/6 PASS. Puni `DISPLAY=:107 python -m pytest -q`
rezultat: 117 testova i 3.240 subtestova PASS, 0 FAIL, 0 SKIP, 241,59 s.

Status: C01 i V01 `PASS` za in-memory scope. Disk writer, atomic new-file save,
filesystem rollback i završni release gate ostaju `NO-GO`.

## W01/K03 — Atomic Verified Writer i bounded disk backend — 2026-08-14

Cilj: Spremiti samo `Verifier PASS` bajtove kao novi MIDI i JSON, bez
prepisivanja izvora ili postojećeg izlaza.

Implementirane datoteke:

- `verified_writer.py`;
- `tests/test_verified_writer.py`.

W01 ponovno provjerava cijeli lanac: USER-approved plan, C01 execution/request,
V01 PASS, source/output hash i mutation count. Original na disku čita samo za
provjeru te ga hashira prije i nakon spremanja.

Output MIDI mora završavati sufiksom `_enhanced.mid` ili `_enhanced.midi`.
MIDI i JSON moraju biti novi, različiti od originala i u istoj postojećoj mapi.
Writer prvo stvara i `fsync`-a privremene fajlove, zatim ih objavljuje atomic
hard-link create-if-absent operacijom koja ne može prepisati postojeći path.
Ako druga publikacija ili naknadna hash/source kapija padne, writer uklanja samo
artefakte koje je sam stvorio i čisti temp fajlove.

JSON izvještaj sadrži source/output hash, plan/proposal/request ID, USER actor i
vrijeme, Verifier status, mutation/byte diff, applied promjene i sigurnosne
zastavice. Report SHA-256 ulazi u `VerifiedWriteResult`.

Filesystem rollback briše report i MIDI samo kada oba još imaju writerom
zabilježene hashove. Ako je korisnik ili drugi proces izmijenio izlaz, rollback
odbija brisanje.

Testovi pokrivaju:

- puni K03-P/C01/V01/W01 save i ponovno parsiranje;
- original ostaje bajtovno jednak;
- MIDI + JSON hash i sadržaj;
- postojeći MIDI ili report nikad se ne prepisuje;
- source promjenu, loš naziv i Verifier FAIL;
- simulirani kvar druge atomic publikacije i potpuno čišćenje;
- uspješan rollback;
- rollback odbijanje izmijenjenog izlaza.

Testna naredba:

```bash
python -m pytest -q tests/test_verified_writer.py
```

Namjenski rezultat: 5/5 PASS i 2 subtesta. Puni
`DISPLAY=:108 python -m pytest -q` rezultat: 122 testa i 3.242 subtesta PASS,
0 FAIL, 0 SKIP, 234,51 s.

Status: W01 i bounded K03 backend `PASS` na testiranom lokalnom filesystemu.
GUI confirmation/save workflow i automatski Enhance nisu dio ovog statusa.

## G01/M05 — Bounded GUI Factory Change Workflow — 2026-08-14

Cilj: Povezati testirani K03 backend s GUI-em bez skrivanja pravila u Tk kodu
i bez automatskog prijedloga ili Apply koraka.

Implementirane datoteke:

- `gui_change_workflow.py`;
- prošireni `midi_gui.py`;
- `tests/test_gui_change_workflow.py`;
- prošireni `tests/test_gui_runtime.py`.

G01 pri importu iz stvarnog MIDI-ja gradi immutable M10/K02 model i GUI-u
izlaže samo eligible `FACTORY_CONFIRMED` ili `USER_SLOT_CONFIRMED` segmente.
Target lista sadrži samo kompatibilne K01 Factory Soundove ili Drum Kitove.
Unknown/Conflict/Incomplete/No Program nije ponuđen.

GUI ima zaseban `Factory Sound…` dijalog i obavezni redoslijed:

1. korisnik bira segment i K01 cilj;
2. `Preview exact diff` prikazuje source/target, segment/channel/tick, rizik,
   plan ID, svaku event/field staru i novu vrijednost te zaštite;
3. `USER Approve + Verify` traži zaseban yes/no i pokreće C01/V01;
4. Save se omogućuje samo nakon `Verifier PASS`;
5. file dialog predlaže novi `_enhanced.mid`, a W01 stvara i JSON;
6. rollback traži novu USER potvrdu i koristi hash-guarded W01 rollback.

Import nikada ne pokreće preview, approval, execution ili save. Promjena izbora
poništava prethodni preview/verification state.

Backend testovi pokrivaju full tok, stage/USER kapije, Unknown exclusion i
shared-bank block. Stvarni Tk/Xvfb test otvara dijalog, bira target, prikazuje
diff, odobrava, verificira, sprema MIDI/JSON i rollbacka, uz nepromijenjen
original.

Namjenske naredbe:

```bash
python -m pytest -q tests/test_gui_change_workflow.py
DISPLAY=:109 python -m pytest -q tests/test_gui_runtime.py
```

Namjenski rezultat: 8/8 PASS. Puni `DISPLAY=:109 python -m pytest -q`
rezultat: 128 testova i 3.242 subtesta PASS, 0 FAIL, 0 SKIP, 236,29 s.

Status: G01/M05 `PASS` za bounded automatizirani virtual-display scope. Native
Windows korisnički test i automatski Enhance ostaju izvan certifikacije.

## R01 — Factory Contextual Profile Builder — 2026-08-14

Cilj: Izgraditi empirijske referentne profile bez statističkog miješanja
različitih uloga ili izvora i bez stvaranja Suggest odluke.

Implementirane datoteke:

- `contextual_profile_builder.py`;
- `tests/test_contextual_profile_builder.py`.

Context key obavezno sadrži:

- source kind (`FACTORY_STYLE`);
- punu efektivnu K01 adresu i item kind;
- M07 funkciju;
- Style Element;
- CV;
- strukturnu ulogu Drum/Perc/Bass/AccN;
- encoding;
- fixed Intro/Ending kandidat.

Promjena bilo kojeg ključa stvara drugi profil. Factory i Gold source kind
nikada ne dijele profile ni profile ID. Profile ulaze samo K02
`FACTORY_CONFIRMED` segmenti s notama i bez BLOCKED segment/measurement statusa.
Conflict, Incomplete, No Program i neupotrebljivi segmenti ostaju u excluded
brojačima.

Profil sadrži exact empirijske percentile velocityja, pitcha, zatvorenog
trajanja u beatovima i gustoće, maksimalnu sounding/onset polifoniju,
kontrolerske brojeve, quality status counts, member/style provenance i stabilni
profile ID. Safety policy je uvijek
`REFERENCE_ONLY_NO_SUGGEST_AUTHORIZATION`.

Puni Factory rezultat:

- 29.603 validne segment-observacije;
- 13.821 izolirani profil;
- 3.754 chordal, 1.759 line/riff, 1.305 solo, 2.383 rhythm-guitar profila;
- 945 bass, 806 drum, 765 perc i 2.104 unknown profila;
- excluded: 15 conflict, 6 incomplete, 53.292 no-program i 1 unusable confirmed;
- digest `33a9b42601bd7612f51312e4c2985bd483f49281edfaa2710d65bcf84998f4b5`;
- Factory ZIP SHA-256 ostaje nepromijenjen.

Testna naredba:

```bash
python -m pytest -q tests/test_contextual_profile_builder.py
```

Rezultat: 5/5 PASS, uključujući puni build. Puni
`DISPLAY=:110 python -m pytest -q` rezultat: 133 testa i 3.242 subtesta PASS,
0 FAIL, 0 SKIP, 308,25 s. Status: R01 `PASS` za read-only Factory empirical
reference scope. Nijedan profil sam ne autorizira Suggest, Change ili Enhance.

## S01 — Exact Contextual Profile Velocity Suggestor — 2026-08-14

Cilj: Napraviti prvi konzervativni profil-based Suggest bez fallbacka i bez
mogućnosti primjene Note On velocity promjene.

Implementirane datoteke:

- `profile_suggest_engine.py`;
- `tests/test_profile_suggest_engine.py`.

Exact matcher zahtijeva jednak source kind, punu K01 adresu, item kind, M07
funkciju, Style Element, CV, strukturnu ulogu, encoding i fixed flag. Bilo koja
razlika daje `NO_PROFILE`; Factory i Gold nikada se ne miješaju.

Konzervativna zadana konfiguracija zahtijeva najmanje 3 observacije, 2 Stylea i
32 note. Prag tolerancije je 4 velocity jedinice, maksimalni pojedinačni korak
8, a maksimalno 32 mutacije u jednom prijedlogu. Konfiguracija je named i
validirana; nevažeće vrijednosti se odbijaju.

Kontekst mora biti K02 `FACTORY_CONFIRMED`, M07 `CLASSIFIED`, encoding
`ORDINARY_MIDI`, funkcija različita od UNKNOWN, bez fixed kandidata i bez
`DO_NOT_TOUCH`. Korisnik mora eksplicitno uključiti S01 pravilo.

Samo Note On izvan profile p10--p90 intervala za više od tolerancije dobiva
bounded korak prema intervalu. Pitch, timing, duration i sve druge velocity
vrijednosti ostaju izvan plana. Prijedlog je `INFERRED`, koristi M07 confidence,
ima `MEDIUM` rizik i upozorenje da velocity-switch/RX pragovi nisu poznati.

Od 13.821 R01 Factory profila, 1.687 prolazi reference/context prefilter:
293 chordal, 18 line/riff, 372 bass, 419 drum, 325 rhythm-guitar, 255 perc i
samo 5 solo profila. Ovo nije broj automatskih prijedloga; stvarni ulaz i
outlieri moraju dodatno proći sve kapije.

C01 namjerno odbija Note On `data[1]`, pa čak ni USER-approved S01 plan ne može
biti primijenjen. Automatic Enhance ostaje zabranjen.

Testna naredba:

```bash
python -m pytest -q tests/test_profile_suggest_engine.py
```

Rezultat: 6/6 PASS i 10 subtestova. Puni
`DISPLAY=:111 python -m pytest -q` rezultat: 139 testova i 3.252 subtesta PASS,
0 FAIL, 0 SKIP, 302,44 s. Status: S01 `PASS` za Suggest-only scope.

## G02 — Gold Dataset Contamination Guard — 2026-08-14

Cilj: Definirati source-disjoint Factory reference i Gold evaluaciju bez
poznatog DNA Factory containera ili sadržajnih MIDI duplikata.

Implementirane datoteke:

- `gold_dataset_guard.py`;
- `tests/test_gold_dataset_guard.py`.

Guard zahtijeva registrirane Factory/DNA/Gold nested hashove, provjerava unsafe
ZIP putanje i ništa ne raspakirava na source lokaciju. `Split Factory
Styles.zip` unutar DNA paketa ima exact Factory SHA-256 i dobiva
`EXACT_FACTORY_ARCHIVE_CONTAMINATION_EXCLUDED`.

Factory skup sadrži 3.211 fajlova i 3.187 jedinstvenih sadržajnih hashova, uz 24
interne duplicate grupe. Gold sadrži 182 valjana MIDI-ja i 181 jedinstven hash;
jedina interna duplicate grupa su dvije `JOZA TUZNI-KNINDZA UZIVO` kopije.
Canonical evaluation uzima lexicografski prvi member po hashu i čuva duplicate
provenance.

Nema nijednog zajedničkog sadržajnog MIDI SHA-256 između 181 Gold canonical
fajla i Factory skupa. Gold evaluation sadrži 5.028.387 događaja i 2.263.727
Note On događaja. Manifest digest je
`62a0ac2ceb1ccf301c99e5a0c65a4d3febd3d6b46f14543b8b9e9898c60bb2e1`.
Oba source arhiva ostaju nepromijenjena.

Train/evaluation provenance je `FACTORY_STYLE_REFERENCE_ONLY` naspram
`GOLD_DNA_DEDUPLICATED_ONLY`. Gold nema ručno potvrđene per-part role labele,
pa M07 probability calibration ostaje `BLOCKED`; heuristic confidence se ne
smije nazvati statističkom vjerojatnošću.

Testna naredba:

```bash
python -m pytest -q tests/test_gold_dataset_guard.py
```

Rezultat: 3/3 PASS i 3 subtesta. Puni
`DISPLAY=:112 python -m pytest -q` rezultat: 142 testa i 3.255 subtestova PASS,
0 FAIL, 0 SKIP, 421,49 s. Status: G02 `PASS` za structural
contamination/dedup/split scope; M07 calibration ostaje zaseban BLOCKED issue.

## V02 — Specialized S01 Note On Velocity Apply Scope — 2026-08-14

Cilj: Dopustiti primjenu samo odobrenog S01 plana uz drugu, eksplicitnu USER
potvrdu da su velocity-switch i RX pragovi nepoznati.

Implementirane/promijenjene datoteke:

- `velocity_change_scope.py`;
- prošireni `change_engine.py`;
- prošireni `change_verifier.py`;
- prošireni `verified_writer.py` report;
- `tests/test_velocity_change_scope.py`.

Generic execution request i dalje blokira Note On. V02 prihvaća samo potpuno
USER-approved plan u kojem su svi proposal rule ID-jevi
`S01.PROFILE_VELOCITY_OUTLIER`. Potrebno je zasebno
`user_acknowledged_unknown_switch_risk=true`; request tada bilježi authorized
rule ID i `UNKNOWN_VELOCITY_SWITCH_RX_THRESHOLDS` acknowledgement.

C01 i V01 neovisno provode:

- samo Note On `data[1]`;
- velocity ostaje 1--127;
- Note On velocity nula/off semantika je zabranjena;
- maksimalna razlika po noti 8;
- maksimalno 32 mutacije;
- running status, pitch, timing, duration i note count ostaju isti.

V01 odbija rezultat ako su specialized rule authorization ili acknowledgement
uklonjeni nakon executiona. W01 JSON report zapisuje oba polja. Apply nikada
nije automatski: potrebni su USER enable S01, USER approval plana, zaseban USER
risk acknowledgement i USER execution request.

Testovi pokrivaju full S01→V02→C01→V01→W01→rollback, running Note On status,
missing ack, generic request, velocity zero, korak veći od 8 i forged ack.

Testna naredba:

```bash
python -m pytest -q tests/test_velocity_change_scope.py
```

Rezultat: 4/4 PASS i 2 subtesta. Puni
`DISPLAY=:113 python -m pytest -q` rezultat: 146 testova i 3.257 subtestova
PASS, 0 FAIL, 0 SKIP, 391,22 s. Status: V02 `PASS` za bounded explicit
USER-acknowledged scope. Automatic velocity Apply i Enhance ostaju zabranjeni.
