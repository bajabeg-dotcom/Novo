# Python MIDI Enhancer

Prva faza projekta sigurno učitava i analizira Standard MIDI datoteke. Original
se otvara samo za čitanje, provjerava SHA-256 kontrolnim zbrojem i nikada se ne
prepisuje.

## Windows instalacija i pokretanje

1. Raspakiraj cijeli projekt u novu mapu. Nemoj pokretati skripte izravno iz
   ZIP pregleda.
2. Instaliraj službeni **Python 3.11 ili noviji** sa `python.org` i uključi
   opciju **Add Python to PATH**.
3. Dvaput klikni `install.bat`. Skripta kreira isključivo lokalni `.venv`,
   instalira hash-pinned K01 extractor iz `vendor/`, opcionalno instalira MIDI
   biblioteke te provjerava K01 i Evidence Registry.
4. Nakon poruke `INSTALACIJA JE USPJESNO ZAVRSENA`, pokreni `run.bat`.

Dodatni načini:

```bat
install.bat minimal
run.bat console
run.bat check
```

`minimal` preskače opcionalne biblioteke. `console` ostavlja terminal otvoren
radi prikaza greške. `check` ponovno provjerava instalaciju i K01 registry.
Skripte ne instaliraju sistemski Python paket i ne mijenjaju MIDI datoteke.

Windows izvršavanje još ima status `PARTIAL` dok se skripte ne potvrde na
stvarnom korisničkom Windows računaru.

## Ručno pokretanje / razvoj

```bash
python3 midi_gui.py
python3 midi_enhancer.py pjesma.mid
python3 midi_enhancer.py pjesma.mid --json
python3 midi_enhancer.py pjesma.mid --json-output pjesma_analysis.json
python3 midi_enhancer.py pjesma.mid --advanced --json
python3 style_loader.py "prism-uploads/Split Factory Styles.zip"
python3 style_loader.py "prism-uploads/Split Factory Styles.zip" --json-output style_collection.json
python3 registry/build_registry.py --check
python3 tools/repository_inventory.py --markdown-output audit/generated/REPOSITORY_INVENTORY.md
python3 tools/workspace_persistence_probe.py
python3 -m unittest -v tests/test_measure_phrase_analyzer.py
```

`midi_gui.py` pokreće desktop sučelje s importom, pregledom 16 track-slotova,
ikonama instrumenata, procjenom pouzdanosti i objašnjenjem korištenih dokaza.
Format 0 mapira MIDI kanale 1–16, Format 1 fizičke trackove 1–16, a Format 2
prikazuje svaki fizički track kao neovisnu sekvencu. Format 2 nema izmišljeno
globalno trajanje ili tempo i ostaje `PARTIAL / READ-ONLY`; vrijednosti se
prikazuju zasebno po sekvenci.
Analiza glazbene uloge razlikuje bass, lead, akordsku pratnju, pad, arpeggio,
percussion te rhythm guitar, solo guitar i power-chord guitar. JSON izvještaj
sadrži korištene pragove, izračunate metrike i dokaze za svaki zaključak.

Analiza obuhvaća strukturu datoteke, trackove, tempo, takt, tonalitet zapisan u
datoteci, note, velocity, kanale, programe, percussion, polifoniju, kontrolne
poruke, sustain, pitch bend i upozorenja.

Dvije postojeće parser putanje imaju izravni parity guard. Sintetički
valid/malformed/SMPTE testovi i svih 3.211 Factory MIDI datoteka moraju dati
isti core fingerprint: strukturu, događaje, note, tempo/metar/key, programe,
kontrolere, pitch bend, hash i završne tickove. To smanjuje rizik razilaženja,
ali nije certifikat cijelog SMF standarda niti writer parityja.

## Biblioteke

Ugrađeni parser uvijek radi bez vanjskih MIDI paketa. Ako su dostupni, program
automatski povezuje:

- `numpy` za detaljniju statistiku;
- `mido` za neovisnu validaciju strukture;
- `pretty_midi` za analizu instrumenata, beatova i procjenu tempa;
- `music21` za opcionalnu analizu tonaliteta uz zastavicu `--advanced`.

Popis poželjnih paketa nalazi se u `requirements-optional.txt`. U ovom Prism
workspaceu nisu instalirani novi paketi; trenutno dostupni paketi koriste se
izravno.

Formalna pravila projekta i granice budućih poboljšanja nalaze se u
`main.tex`.

## Style Works Loader

`style_loader.py` je read-only ulazni modul za split Style Works kolekcije.
Provjerava MIDI strukturu i SHA-256 arhiva, grupira 13 Style Elemenata, mapira
CV i Pa800 uloge kanala, čita `CC00.CC32.PC` te odvaja valjani broj taktova od
zaostalih događaja. Ne klasificira solo/podlogu i ne mijenja MIDI sadržaj.

Puni test nad učitanim arhivom potvrđuje 3.211 valjanih MIDI datoteka, 252
Style skupa, 230 potpunih i 22 nepotpuna skupa. Element
`Fox Shuffle 1_Break.mid` sadrži konflikt `1 Bar` / `5 Bars`; Loader ga čuva,
ali blokira njegovu vremensku statistiku bez nagađanja.

## Context Classifier

`context_classifier.py` je generička read-only jezgra za klasifikaciju MIDI
parta. Odvojeno prikazuje strukturnu ulogu, glazbenu funkciju, mogući poseban
encoding, dokaze i sigurnosnu politiku. Style adapter prenosi potvrđene
Drum/Perc/Bass/Acc, Element i CV podatke, ali generička jezgra ne ovisi o
Pa800 kanalima.

Klasifikator razlikuje Drum, Perc, Bass, chordal accompaniment, line/riff,
običnu rhythm gitaru i solo kandidata. Guitar Mode ostaje zaseban kandidat bez
eksplicitnog `Track Type=Gtr` dokaza. RX nejasnoća, fixed Intro/Ending i
višekanalni konflikt automatski pooštravaju ili blokiraju buduću izmjenu.

## Evidence Registry

`registry/master_registry.json` je kanonski izvor za G00 registry zapise.
`registry/MASTER_REGISTRY.md` generira se deterministički i ne uređuje se
ručno. Validator provjerava ID namespace, reference, četiri odvojena statusa,
izolaciju idejnih kataloga, lokalne putanje, SHA-256 i prisutnost registriranih
testova. To ne znači da validator sam dokazuje glazbenu istinitost; svaka
domenska tvrdnja i dalje treba vlastiti test i dokaz.

Provjera i ponovno generiranje:

```bash
python3 registry/build_registry.py --check
python3 registry/build_registry.py
python3 -m unittest -v tests/test_master_registry.py
```

Napredni spisak mogućnosti i napredni registar pravila vode se kao
`IDEA_CATALOG`: služe izboru budućih koraka, ali nisu aktivni rule set.

## K01 Pa800 Factory Registry

`registry/generate_pa800_factory.py` iz potvrđenog User's Manuala deterministički
stvara `registry/pa800_factory_registry.json`. Generator prihvaća samo
registrirani PDF SHA-256, 344 stranice i pinned `pypdf 6.16.0` wheel. Kanonski
registar sadrži 1.006 Factory Sound i 65 imenovanih Drum Kit adresa, ukupno
1.071 jedinstvenu `CC00.CC32.PC` adresu.

`pa800_registry.py` je immutable read-only lookup. Ne pretpostavlja banku,
ne identificira sadržaj User slota i ne primjenjuje remap. Preklop Drum Kit
remapa 57–63 s imenovanim adresama 57 i 58 ostaje eksplicitni `CONFLICT`.

```bash
python3 registry/generate_pa800_factory.py --check
python3 -m pytest -q tests/test_pa800_factory_registry.py
```

## K02 Instrument Identity Resolver

`instrument_identity_resolver.py` povezuje stvarni immutable M10 segment s K01
registracijom. Vraća `FACTORY_CONFIRMED`, `USER_SLOT_CONFIRMED`, `UNKNOWN`,
`CONFLICT`, `INCOMPLETE_ADDRESS` ili `NO_PROGRAM`. Potvrđeni remap čuva traženu
i ciljnu adresu; konflikt 57–58 ne razrješava automatski. Izvorni M10 segment i
MIDI događaji ostaju nepromijenjeni, a K02 ne autorizira K03 ili Enhance.

Puni Factory corpus reproducira 82.917 K02 rezultata i deterministički digest.

```bash
python3 -m pytest -q tests/test_instrument_identity_resolver.py
python3 -m pytest -q tests/test_analysis_pipeline_corpus.py
```

## Immutable Change Plan i Policy Engine

`change_plan.py` opisuje samo Suggest-phase prijedloge s točnim event/field
diffom, source-event SHA-256, dokazima, mjerenjima, rizikom i stabilnim ID-jem.
Korisničke odluke zapisuju se zasebno i immutable. Čak i odobren plan uvijek
ima `apply_authorized=false`.

`policy_engine.py` dopušta prijedlog u plan samo kada named/versioned pravilo,
evidence, rizik i stvarni izvorni event prođu sve kapije. Moduli nemaju MIDI
writer i ne mogu izvršiti promjenu.

```bash
python3 -m pytest -q tests/test_change_plan.py tests/test_policy_engine.py
```

## K03-P Factory replacement Proposal Builder

`k03_sound_replacement.py` gradi samo Suggest plan za eksplicitno korisnički
odabranu K01 Factory adresu. Dopušteni su samo postojeći, točno identificirani
i ekskluzivni CC00/CC32/Program Change događaji odabranog M10 segmenta.
Shared/inherited Bank Select, insertion, Unknown/Conflict/Incomplete, kind
mismatch i ne-Factory cilj se blokiraju. Čak i odobren plan nema Apply.

```bash
python3 -m pytest -q tests/test_k03_sound_replacement.py
```

## In-memory Change Engine i Verifier

`change_engine.py` prihvaća samo potpuno USER-odobren plan i zaseban USER
execution request. Mijenja isključivo točne CC/Program data bajtove u radnoj
memorijskoj kopiji, čuva running status i omogućuje exact rollback. Ne piše
MIDI datoteku i vlastiti rezultat ostavlja `PENDING_VERIFICATION`.

`change_verifier.py` neovisno reparsira original i kopiju te zahtijeva da su sve
i jedine bajtovne razlike točno odobrene mutacije. Dodatni bajt, forged log ili
neparsabilan izlaz daje `FAIL`. Disk writer još nije implementiran.

```bash
python3 -m pytest -q tests/test_change_engine_verifier.py
```

## Atomic Verified Writer

`verified_writer.py` prima samo `Verifier PASS` bajtove. Ponovno provjerava
original na disku, zapisuje same-directory temp fajlove te atomic/no-overwrite
objavljuje novi `_enhanced.mid` i JSON izvještaj. Postojeći izlaz nikada se ne
prepisuje. Kvar druge publikacije uklanja sve artefakte tog pokušaja.
Filesystem rollback briše samo writer izlaze čiji hash još odgovara.

```bash
python3 -m pytest -q tests/test_verified_writer.py
```

Ovo certificira bounded programatski K03 backend. Automatski Enhance nije
uključen.

## GUI Factory replacement workflow

Nakon importa eligible MIDI-ja gumb `Factory Sound…` otvara zaseban bounded
dijalog. Korisnik bira M10/K02 segment i kompatibilni K01 cilj, pregledava exact
event-field diff i rizik, zasebno potvrđuje C01/V01, a Save se omogućuje samo
nakon `Verifier PASS`. W01 sprema novi `_enhanced.mid` i JSON; rollback briše
samo netaknute writer izlaze. Import nikada automatski ne pokreće promjenu.

```bash
python3 -m pytest -q tests/test_gui_change_workflow.py
```

## Factory contextual profiles

`contextual_profile_builder.py` gradi reference-only Factory profile po punoj
K01 adresi, M07 funkciji, Elementu, CV-u, strukturnoj ulozi, encodingu i fixed
kandidatu. Chordal, riff, solo, Drum/Perc/Bass i različiti CV/Elementi nikada se
ne spajaju. Factory i Gold source kind ostaju odvojeni. Puni corpus daje 29.603
observacije i 13.821 izolirani profil; profil sam ne autorizira Suggest.

```bash
python3 -m pytest -q tests/test_contextual_profile_builder.py
```

## S01 exact profile velocity Suggest

`profile_suggest_engine.py` koristi isključivo exact R01 key. Nema fallbacka
između instrumenata, funkcija, Elemenata, CV-ova, uloga, encodinga ili
Factory/Gold izvora. Uz minimalnu referentnu potporu može napraviti Suggest-only
plan za mali broj Note On velocity outliera, s maksimalnim korakom 8.

V02 može primijeniti takav plan samo nakon dodatnog USER acknowledgementa da su
velocity-switch/RX pragovi nepoznati. Generic request ostaje blokiran; C01/V01
provode max 8, max 32 i velocity 1–127. W01 report bilježi acknowledgement.

```bash
python3 -m pytest -q tests/test_profile_suggest_engine.py
python3 -m pytest -q tests/test_velocity_change_scope.py
```

## Gold evaluation contamination guard

`gold_dataset_guard.py` isključuje exact Factory arhiv ugrađen u DNA paket,
deduplicira 182 Gold MIDI-ja na 181 sadržajno jedinstven fajl i potvrđuje nula
Factory–Gold MIDI hash preklapanja. Manifest definira Factory kao reference
source, a deduplicirani Gold kao evaluation-only source. M07 statistička
kalibracija ostaje blokirana jer Gold nema ručno potvrđene per-part role labele.

```bash
python3 -m pytest -q tests/test_gold_dataset_guard.py
```

## Measure/Phrase Analyzer

`measure_phrase_analyzer.py` je read-only M08 modul. Iz eksplicitnih Set Tempo
i Time Signature događaja gradi timeline, mapira događaje na mjeru, beat i
tick, pronalazi egzaktno ponovljene mjere te označava konzervativne kandidate
granica fraza nakon duge stanke. Konfliktne oznake metra ili tempa blokiraju
vremensko tumačenje. Style adapter koristi samo potvrđeni M06 vremenski prozor.

M08 ne kvantizira, ne pomiče i ne briše MIDI događaje. Kandidat granice fraze
nije potvrđena glazbena činjenica i uvijek sadrži razlog i razinu pouzdanosti.

## Instrument Measurement Engine

`instrument_measurement_engine.py` je read-only M09 modul. Mjeri velocity,
raspon, trajanje, gustoću, sounding/onset polifoniju, kontrolere, pitch bend i
aftertouch. Kada su dostupni M07 i M08 rezultati, izrađuje zasebne profile po
mjeri i kandidatu fraze te zadržava njihovu sigurnosnu politiku.

Nezatvorene ili orphan note daju `PARTIAL`, a blokirani M07/M08 kontekst daje
`BLOCKED`. M09 nema Suggest, Change, Humanize ni writer funkciju.

## Instrument Segmenter

`instrument_segmenter.py` je read-only M10 modul. Po MIDI kanalu prati CC00,
CC32 i Program Change te stvara zaseban segment i M09 profil za svaki odabir
instrumenta. Nepotpuna adresa ostaje `INCOMPLETE`, događaji prije prvog
programa ostaju `NO_PROGRAM`, a note preko granice posebno se upozoravaju.

M10 ne određuje Factory/User identitet: svaki segment ostaje `UNRESOLVED` dok
produkcijski K01 registry i K02 resolver ne budu završeni.

M08--M10 prošli su dodatni neovisni audit. Svaki modul sada ima devet
dedicated testova, a `tests/test_analysis_pipeline_corpus.py` izvršava cijeli
read-only lanac nad svih 3.211 Factory MIDI datoteka i 65.021 track-slice.
Corpus test provjerava fiksne statusne raspodjele, 82.917 segmenata,
deterministički digest i nepromijenjen SHA-256 izvornog ZIP-a. PASS vrijedi
samo za taj izravno testirani read-only scope.

## Pa800 izvor i razvoj modula

Normativni Pa800 izvori su učitani službeni priručnici:

`prism-uploads/Pa800-201UM-ENG.pdf`

`prism-uploads/Pa800_AE_E.pdf`

PDF-ovi su provjereni naslovom, brojem stranica i SHA-256 kontrolnim zbrojem.

Nakon svakog modula pokreće se:

```bash
python3 -m unittest -v tests/test_midi_modules.py
python3 -m unittest -v tests/test_style_loader.py
python3 -m unittest -v tests/test_context_classifier.py
python3 -m unittest -v tests/test_context_classifier_corpus.py
python3 -m unittest -v tests/test_master_registry.py
python3 -m unittest -v tests/test_measure_phrase_analyzer.py
python3 -m unittest -v tests/test_instrument_measurement_engine.py
python3 -m unittest -v tests/test_instrument_segmenter.py
python3 -m unittest -v tests/test_analysis_pipeline_corpus.py
```

Rezultat, primijenjene funkcije i status odmah se zapisuju u `MODULE_LOG.md`.
`tkinter` 8.6 je dostupan. Workspace-only Xvfb runtime iz službenih Debian
paketa omogućio je stvarni automatizirani Tk test: prozor, 16 kartica, Format 0
analiza/JSON izvoz i Format 2 read-only prikaz prolaze. Native desktop
pakiranje i ljudski UX još nisu certificirani.

## Repository audit i persistence gate

`tools/repository_inventory.py` uspoređuje implementirane MODULE/TEST zapise i
MODULE_LOG ID-jeve sa stvarnim worktreeom i `git ls-tree` popisom. Njegov
`PASS` dokazuje prisutnost artefakta, ne ispravnost glazbene logike.

`tools/workspace_persistence_probe.py` provjerava checkpointirani Git commit i
SHA-256 nove Python i testne datoteke. Checkpoint je ponovno uspješno provjeren
nakon sljedeće korisničke poruke, pa A01 i A02 imaju ograničeni governance
`PASS`. To ne certificira glazbenu ispravnost, K01/K02 ni Enhance.