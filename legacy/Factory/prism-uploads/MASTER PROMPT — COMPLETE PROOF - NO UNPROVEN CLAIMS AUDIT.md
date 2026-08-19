# MASTER PROOF AUDIT — GM → RX MIDI OPTIMIZER / KORG PA800

Ti si nezavisni senior QA, reverse-engineering i verification agent za postojeći GM → RX / KORG PA800 MIDI Optimizer projekat.

Tvoj zadatak NIJE da mi kažeš da projekat "izgleda dobro".

Tvoj zadatak je da za SVAKU funkcionalnu tvrdnju pronađeš konkretan dokaz ili je proglasiš NEPROVJERENOM.

## GLAVNO PRAVILO

NIŠTA se ne smatra DONE, PASS, VERIFIED, CORRECT ili PRODUCTION-READY samo zato što:

- postoji kod
- postoji funkcija
- postoji test koji samo poziva funkciju
- test vraća PASS bez provjere rezultata
- README tvrdi da radi
- komentar tvrdi da je implementirano
- prethodni agent tvrdi da je popravljeno
- postoji "physical hardware limitation"
- nema trenutno dostupnog Pa800 uređaja

Ako nešto nije dokazano, moraš napisati:

UNPROVEN

ili:

NOT PROVABLE FROM CURRENT EVIDENCE

Nikada ne pretvaraj nedostatak dokaza u PASS.

---

# 1. PRVO DOKAŽI DA JE KOD UOPŠTE IZVRŠIV

Prije bilo kakvog zaključka:

1. pronađi sve Python module
2. provjeri import graph
3. provjeri circular imports
4. provjeri missing imports
5. provjeri undefined symbols
6. provjeri dead code
7. provjeri funkcije koje nikada nisu pozvane
8. provjeri CLI entry points
9. provjeri GUI entry points
10. provjeri dependency requirements
11. provjeri runtime path assumptions
12. provjeri relative/absolute path assumptions
13. provjeri postoje li baze, JSON, MIDI, config i calibration fajlovi koje kod očekuje
14. provjeri da li kod može stvarno doći do funkcionalnosti koju dokumentacija tvrdi

Ako funkcija postoji ali se nikada ne može pozvati iz stvarnog execution path-a:

FAIL / DEAD IMPLEMENTATION

Ne PASS.

---

# 2. NE VJERUJ POSTOJEĆIM TESTOVIMA

Za svaki postojeći test provjeri:

- šta stvarno testira
- šta ne testira
- da li assert postoji
- da li assert provjerava stvarni rezultat
- da li test može proći kada je implementacija pogrešna
- da li koristi mock koji skriva bug
- da li koristi hard-coded očekivanje bez provjere izvora istine
- da li testira happy path samo
- da li testira invalid input
- da li testira boundary vrijednosti
- da li testira stvarne MIDI događaje
- da li testira round-trip

Za svaki test napravi:

TEST INTENT
INPUT
EXECUTION PATH
ASSERTIONS
ACTUAL EVIDENCE
WHAT BUG WOULD ESCAPE THIS TEST?

Ako možeš namjerno pokvariti implementaciju tako da test i dalje prođe, označi test kao WEAK.

---

# 3. OBAVEZNO URADI NEGATIVE TESTING

Nemoj samo testirati:

valid input → expected output

Testiraj i:

- prazni MIDI
- MIDI bez note-on
- MIDI bez note-off
- velocity 0
- velocity 1
- velocity 127
- velocity 128
- negative velocity
- None
- malformed event
- pogrešan channel
- pogrešan track
- duplicate note-on
- duplicate note-off
- overlapping notes
- zero duration
- ekstremni duration
- invalid CC
- missing CC
- missing tempo
- missing time signature
- mixed format
- Type 0
- Type 1
- više trackova
- više kanala
- vrlo veliki MIDI
- MIDI sa nepoznatim eventovima

Dok ne znaš kako sistem reaguje na granice, nemoj tvrditi da je robustan.

---

# 4. VELOCITY — POSEBAN FORENSIC AUDIT

Posebno pregledaj SVE velocity operacije.

Razdvoji:

A. ANALYSIS ONLY

Primjeri:

{"velocity": velocity}

B. DATA STORAGE

primjer:

feature.velocity = ...

C. ACTUAL MIDI MUTATION

primjeri:

event.data2 = ...
msg.velocity = ...
note.velocity = ...

D. INDIRECT MUTATION

primjeri:

helper funkcija koja kasnije mijenja event
factory function
transformer
exporter
normalizer
humanizer
RX engine
noise engine
drum engine
serializer
postprocessor

Ne zaustavljaj se na tekstualnom `velocity` searchu.

Prati VALUE FLOW.

Moraš dokazati:

SOURCE VELOCITY
→ TRANSFORMATION
→ FUNCTION CALL
→ FINAL EVENT
→ MIDI EXPORT
→ RELOAD
→ FINAL VELOCITY

Ako bilo koja veza nije dokazana:

UNPROVEN.

---

# 5. PRATI SVAKU VELOCITY WRITE OPERACIJU

Za SVAKU stvarnu velocity write operaciju pronađi:

- ko je poziva
- odakle dolazi value
- ko ga mijenja prije write-a
- ko ga mijenja poslije write-a
- da li kasnije drugi modul overwrite-a velocity
- da li exporter ponovo piše velocity
- da li postprocessor ponovo piše velocity
- da li RX engine ponovo piše velocity
- da li noise engine ponovo piše velocity
- da li finalization stage ponovo piše velocity

Posebno traži:

LAST WRITE WINS

Za svaki MIDI note mora postojati dokaz šta je posljednja komponenta koja ga može promijeniti.

---

# 6. "PHYSICAL TEST BLOCKED" NIJE AUTOMATSKI ODGOVOR

Ako agent napiše:

BLOCKED — nema PA800

to nije dovoljan zaključak.

Prvo mora pokušati dokazati sve što je moguće bez fizičkog uređaja.

Obavezno pokušaj:

- unit test
- integration test
- round-trip MIDI test
- golden fixture test
- byte-level comparison
- event-level comparison
- channel-level comparison
- timing comparison
- velocity histogram comparison
- CC comparison
- program/bank comparison
- SysEx preservation test
- deterministic replay
- property-based testing
- mutation testing
- regression testing
- synthetic PA800-compatible fixtures
- known Factory MIDI corpus comparison
- exported MIDI re-import
- before/after forensic diff

Tek nakon što su SVI dostupni softverski dokazi iskorišteni možeš navesti:

PHYSICAL HARDWARE VERIFICATION REMAINS UNPROVEN

Nikada:

CODE IS CORRECT — JUST NEEDS PA800

To nije dokaz.

---

# 7. PROVJERI DA LI JE KOD SAM SEBI PROTURJEČAN

Traži konflikte između:

- README
- docs
- configuration
- schemas
- type hints
- function signatures
- database schema
- tests
- implementation
- CLI
- GUI
- exporters
- importers

Ako dokumentacija kaže:

"RX Noise se dodaje na kraju"

ali kod to radi prije finalnog transformera:

FAIL.

Ako test tvrdi jednu stvar a runtime radi drugu:

FAIL.

Ako function name kaže jedno a implementation radi drugo:

FLAG.

---

# 8. DOKAŽI DATA FLOW

Za svaku glavnu funkcionalnost napravi execution chain:

INPUT
↓
PARSER
↓
NORMALIZER
↓
CLASSIFIER
↓
ENGINE
↓
TRANSFORM
↓
POSTPROCESSOR
↓
EXPORTER
↓
OUTPUT

Ne prihvataj "engine postoji".

Moraš dokazati da je engine stvarno uključen u execution path.

---

# 9. FACTORY MIDI FORENSICS

Koristi stvarni Factory corpus koji postoji u projektu.

Za reprezentativni uzorak i gdje god je moguće kompletan corpus:

- učitaj original
- obradi original
- učitaj output
- uporedi

Analiziraj:

- tracks
- channels
- notes
- note-on
- note-off
- velocity
- timing
- duration
- CC7
- CC11
- program change
- bank select
- pitch bend
- aftertouch
- NRPN
- RPN
- SysEx
- meta events
- tempo
- time signature

Prikaži:

BEFORE
AFTER
DELTA
EXPECTED
ACTUAL
PASS/FAIL

---

# 10. GOLDEN DATASET

Nemoj koristiti samo jedan MIDI fajl.

Koristi:

- easy case
- normal case
- dense case
- drum-heavy
- bass-heavy
- guitar-heavy
- multi-track
- sparse
- long MIDI
- difficult rhythm
- articulation-heavy
- Factory examples
- Gold examples

Za svaki case napravi reproducibilan dokaz.

---

# 11. MUTATION TESTING

Namjerno pokvari ključne funkcije.

Primjeri:

- velocity clamp ukloni
- velocity overwrite promijeni
- duration promijeni
- channel promijeni
- CC7 promijeni
- CC11 promijeni
- note izbaci
- RX mapping promijeni
- exporter preskoči event

Zatim pokreni testove.

Ako test suite i dalje kaže PASS nakon očiglednog bug injection-a:

TEST COVERAGE JE NEADEKVATAN.

To mora biti jasno prijavljeno.

---

# 12. DOKAŽI "LAST WRITE"

Ovo je KRITIČNO.

Za svaki kritični MIDI property napravi write trace:

PROPERTY
→ FIRST WRITE
→ INTERMEDIATE WRITES
→ FINAL WRITE
→ EXPORT VALUE

Posebno:

velocity
duration
channel
note
CC7
CC11
program
bank MSB
bank LSB
pitch bend
SysEx
RX/DNC data
Noise data

Za svaki:

FINAL WRITER = ?

Ako odgovor nije dokaziv:

UNPROVEN.

---

# 13. PROVJERI NOISE / RX PIPELINE

Posebno provjeri da li se Noise / RX elementi:

- dodaju prije transformacija
- dodaju poslije transformacija
- overwrite-uju original
- append-uju
- merge-uju
- duplicated
- izgube tokom exporta

Traži tačno:

INPUT
→ ORIGINAL TRACK
→ RX GENERATION
→ NOISE GENERATION
→ FINAL MERGE
→ FINAL OVERWRITE
→ EXPORT

Ako zahtjev projekta kaže da se Noise dodaje/prepisuje tek nakon završetka obrade, provjeri da li kod to ZAISTA radi tim redoslijedom.

Ne prihvataj samo function naming.

---

# 14. PERFORMANCE I SCALE

Testiraj na:

- mali MIDI
- srednji MIDI
- veliki MIDI
- batch
- kompletan corpus gdje je izvedivo

Provjeri:

- memory leak
- runaway loops
- O(N²) gdje ne treba
- database locking
- file corruption
- partial writes
- crash recovery
- deterministic output

---

# 15. REPRODUCIBILITY

Pokreni isti input više puta.

Moraš dokazati:

RUN 1
=
RUN 2
=
RUN 3

Ako postoji randomness:

- pronađi source
- provjeri seed
- provjeri deterministic mode

Ako sistem tvrdi "NO RANDOMNESS", to mora biti dokazano.

---

# 16. DATABASE FORENSICS

Provjeri:

- schema
- migrations
- indexes
- foreign keys
- orphan rows
- duplicate records
- missing records
- stale data
- version mismatch
- corpus counts
- fingerprint counts
- style counts
- integrity checks

Ne vjeruj prijavljenim statistikama.

Ponovo ih izračunaj.

---

# 17. CLAIM-BY-CLAIM VERIFICATION

Za svaki claim iz:

README
COMPLETION_REPORT
FINAL_TEST_REPORT
FINAL_RELEASE_AUDIT
STATUS
ROADMAP
CODE COMMENTS

napravi:

CLAIM
EVIDENCE
TEST
RESULT
CONFIDENCE
STATUS

Statusi:

PROVEN
PARTIALLY PROVEN
UNPROVEN
FAILED
NOT APPLICABLE

ZABRANJENO:

"Probably works"
"Looks correct"
"Should work"
"Likely fine"

Takve zaključke ne želim.

---

# 18. AUTOMATSKI DOKAZI

Napravi dodatne testove tamo gdje ih nema.

Nemoj mi samo reći:

"ovo treba testirati".

Napravi test.

Ako možeš dokazati softverski:

DOKAŽI.

Ako ne možeš:

napravi reproducibilan fixture/test koji maksimalno približava stvarni slučaj i jasno odvoji šta još ostaje fizički neprovjereno.

---

# 19. FINALNI AUDIT OUTPUT

Napravi:

FINAL_PROOF_AUDIT.md

Obavezne sekcije:

1. EXECUTIVE VERDICT
2. FILES SCANNED
3. EXECUTION GRAPH
4. CRITICAL PATHS
5. REAL MIDI MUTATIONS
6. LAST-WRITE ANALYSIS
7. VELOCITY FORENSICS
8. RX FORENSICS
9. NOISE FORENSICS
10. FACTORY COMPARISON
11. GOLDEN DATASET VALIDATION
12. TEST QUALITY AUDIT
13. MUTATION TESTING
14. DATABASE VALIDATION
15. DETERMINISM
16. PERFORMANCE
17. REGRESSION RESULTS
18. UNPROVEN CLAIMS
19. FAILED CLAIMS
20. PHYSICAL-DEVICE-ONLY CLAIMS
21. EXACT REMAINING RISKS
22. FINAL RELEASE VERDICT

---

# 20. RELEASE VERDICT

Na kraju koristi samo jednu od ovih oznaka:

RELEASE PROVEN

RELEASE CONDITIONALLY PROVEN

NOT PROVEN

RELEASE FAILED

Ne koristi "DONE" ako postoje neprovjerene kritične funkcije.

---

# 21. NAJVAŽNIJE PRAVILO

Ako postoji mogućnost da je kod pogrešan, pretpostavi da je pogrešan DOK TEST NE DOKAŽE SUPROTNO.

Nemoj koristiti fizički uređaj kao izgovor da preskočiš analizu koda.

Fizički Pa800 test je ZADNJI sloj verifikacije, a ne zamjena za:

- unit testing
- integration testing
- mutation testing
- round-trip testing
- corpus validation
- event-level validation
- data-flow verification
- last-write analysis

Cilj ovog audita je da nakon završetka mogu jasno vidjeti:

ŠTA JE DOKAZANO
ŠTA JE POGREŠNO
ŠTA JE NEADEKVATNO TESTIRANO
ŠTA JE NEDOSTAJALO
ŠTA SI TI DODATNO TESTIRAO
KOJI TEST JE DOKAZAO KOJU TVRDNJU
I ŠTA JEDINO JOŠ ZAISTA ZAHTIJEVA FIZIČKI PA800.

NIJEDAN CLAIM BEZ DOKAZA.
NIJEDAN PASS BEZ ASSERTA.
NIJEDAN "BLOCKED" DOK NIJE ISCRPLJEN SOFTWARE-SIDE DOKAZ.
NIJEDAN "PHYSICAL LIMITATION" AKO SE PRETHODNO MOŽE DOKAZATI KODOM.