# NAPREDNI SPISAK MOGUĆNOSTI
## KORG PA800 Factory Style / MIDI / Factory DNA / RX-DNC / Intelligence Project

**Namjena ovog spiska:**  
Svaku stavku možeš pojedinačno poslati agentu kao zaseban istraživački zadatak.

**Princip rada s agentima:**  
Ne tražiti samo „da li je moguće“, nego za svaku stavku utvrditi:

**MOGUĆNOST → IZVOR PODATAKA → DOKAZ → ALGORITAM → PRIMJENA → TEST → OGRANIČENJA**

Agent ne smije izmišljati Korg ponašanje. Sve što je moguće dokazati iz MIDI/STY/OC31/FActory podataka, manuala, postojećeg koda ili kontrolisanog testa treba označiti kao **DOKAZANO**, dok sve ostalo mora ostati **HIPOTEZA / NEPOTVRĐENO**.

---

# A. FORENZIČKO ČITANJE I REKONSTRUKCIJA FACTORY STYLEOVA

### A01 — Automatska detekcija kompletnog MIDI formata
Prepoznati format 0/1, PPQN, broj trackova, event tipove, SysEx, Meta događaje i strukturu fajla.

### A02 — Rekonstrukcija originalne strukture Factory MIDI-ja
Utvrditi kako su originalni Factory fajlovi organizovani bez oslanjanja na pretpostavke.

### A03 — Prepoznavanje Korg specifičnih Meta događaja
Detektovati i klasifikovati događaje koji nisu standardni GM/MIDI.

### A04 — Prepoznavanje Korg SysEx struktura
Automatski pronaći, parsirati i grupisati Korg-specifične SysEx poruke.

### A05 — OC31 forenzička analiza
Napraviti kompletan parser/validator svih pronađenih OC31 struktura.

### A06 — Rekonstrukcija Style ID-a
Utvrditi kako se identitet konkretnog Style-a može razlikovati od samog MIDI sadržaja.

### A07 — Rekonstrukcija track-role odnosa
Automatski dokazivati koji track pripada Bass/Drum/Percussion/Chord/Pad/Acc1–5 itd.

### A08 — Detekcija skrivenih ili pomoćnih trackova
Pronaći trackove koji nisu očigledni iz običnog MIDI prikaza.

### A09 — Detekcija dummy/placeholder događaja
Utvrditi postoje li događaji koji postoje zbog internog engine-a, ali nisu muzički relevantni.

### A10 — Rekonstrukcija granica Style sekcija
Automatski pronaći Intro/Variation/Fill/Break/Ending/Count In/Count Out gdje je moguće.

---

# B. MUZIČKA STRUKTURA I SEMANTIKA

### B01 — Automatska segmentacija na taktove
Pretvoriti MIDI u muzički vremenski model sa tačnim granicama taktova.

### B02 — Segmentacija na muzičke fraze
Detektovati fraze duže od jednog takta.

### B03 — Detekcija 1-taktnih ćelija
Napraviti preciznu Factory Pattern bazu.

### B04 — Detekcija 2-, 4-, 8- i 16-taktnih obrazaca
Pronaći višetalne repeticije i razvojne strukture.

### B05 — Pattern cloning detection
Detektovati kada je jedan Pattern izveden iz drugog sa malim izmjenama.

### B06 — Motif extraction
Izvući ponavljajuće melodijske, ritmičke i harmonske motive.

### B07 — Groove extraction
Izvući mikro-timing obrazac karakterističan za Factory Style.

### B08 — Humanization fingerprint
Izračunati koliko konkretan Factory Style odstupa od stroge grid pozicije.

### B09 — Velocity fingerprint
Izvući tipičnu distribuciju velocity vrijednosti po ulozi.

### B10 — Accent fingerprint
Pronaći gdje Factory sistem prirodno stavlja naglaske.

---

# C. FACTORY DNA

### C01 — Complete Style DNA fingerprint
Napraviti jedinstveni potpis svakog Style-a.

### C02 — Track DNA
DNA za svaki pojedinačni track.

### C03 — Lane DNA
DNA za Bass, Drum, Percussion, Chord, Pad, ACC itd.

### C04 — Phrase DNA
DNA pojedinačne muzičke fraze.

### C05 — Rhythm DNA
Matematički opis ritmičkog karaktera.

### C06 — Harmony DNA
Opis intervala, akorda, voicinga i harmonijskog ponašanja.

### C07 — Velocity DNA
Opis dinamike i akcenta.

### C08 — Timing DNA
Opis mikro-pomjeranja nota.

### C09 — Density DNA
Prosječna i maksimalna gustina nota.

### C10 — Polyphony DNA
Broj simultanih tonova i način korištenja polifonije.

### C11 — Register DNA
Tipični tonski raspon i centar svake uloge.

### C12 — Articulation DNA
Prepoznati legato, staccato, repeated-note, grace-note i druge obrasce.

### C13 — Arrangement DNA
Opis kako se energija i gustoća mijenjaju kroz Style.

### C14 — Genre DNA
Odvojiti karakteristike koje pripadaju žanru od onih koje pripadaju konkretnom Style-u.

### C15 — Factory-vs-user DNA
Napraviti razliku između „tipičnog Factory ponašanja“ i individualnog izuzetka.

---

# D. FACTORY PATTERN DATABASE

### D01 — Pattern fingerprint baza
Čuvati svaki prepoznati Pattern kao jedinstveni fingerprint.

### D02 — Near-duplicate Pattern detection
Pronaći skoro identične Pattern-e.

### D03 — Pattern clustering
Grupisati Pattern-e prema muzičkoj sličnosti.

### D04 — Pattern genealogy
Utvrditi koji Pattern liči na koji i iz kojeg bi mogao biti izveden.

### D05 — Rare Pattern detector
Pronaći rijetke i neobične Factory obrasce.

### D06 — Signature Pattern detector
Pronaći obrasce karakteristične za određenog Style/žanr.

### D07 — Negative Pattern database
Čuvati obrasce koji se ne smiju automatski mijenjati.

### D08 — Safe Pattern database
Čuvati obrasce koji su dokazano sigurni za određeni tip obrade.

### D09 — Context-aware Pattern matching
Isti Pattern tretirati drugačije zavisno od konteksta.

### D10 — Pattern mutation engine
Testirati kako se Factory Pattern može minimalno modificirati a da zadrži DNA.

---

# E. AUTOMATSKA KLASIFIKACIJA TRACKOVA

### E01 — Track role classifier
Automatski odrediti funkciju tracka.

### E02 — Bass detector
Prepoznati Bass bez oslanjanja samo na MIDI kanal/program.

### E03 — Drum detector
Prepoznati Drum track po ponašanju.

### E04 — Percussion detector
Odvojiti percussion od klasičnog Drum tracka.

### E05 — Chord detector
Prepoznati harmonske/comping trackove.

### E06 — Pad detector
Prepoznati pad teksture.

### E07 — Melody detector
Prepoznati melodijske linije.

### E08 — Guitar detector
Prepoznati gitarističke obrasce.

### E09 — Solo guitar protection
Automatski zaštititi solo gitaru od agresivnog optimizovanja.

### E10 — Riff guitar detector
Razlikovati riff gitaru od prateće gitare.

### E11 — Arpeggio detector
Detektovati arpeggio i ostaviti njegovo prirodno ponašanje.

### E12 — Percussion-role detector
Prepoznati kick/snare/hat/tom/cymbal/perc funkcije.

---

# F. RX / DNC / ARTIKULACIJE

### F01 — RX articulation detection
Automatski pronaći gdje bi RX ponašanje moglo biti relevantno.

### F02 — DNC articulation detection
Detektovati potencijalne DNC kontekste.

### F03 — Noise articulation detection
Prepoznati note/event obrasce koji predstavljaju noise artikulaciju.

### F04 — Guitar strum detection
Prepoznati downstroke/upstroke ponašanje.

### F05 — Hammer-on/pull-off candidates
Pronaći moguće legato-guitar obrasce.

### F06 — Slide candidates
Detektovati obrasce koji mogu odgovarati slide artikulaciji.

### F07 — Mute candidate detection
Pronaći mutirane ili kratke note.

### F08 — Pick/noise candidate detection
Prepoznati tipične noise događaje.

### F09 — RX context engine
Ne određivati artikulaciju samo po jednoj noti već prema susjednim događajima.

### F10 — Articulation conflict detection
Pronaći slučajeve gdje bi dva RX/DNC pravila bila međusobno konfliktna.

### F11 — Articulation confidence score
Svakoj predloženoj artikulaciji dodijeliti confidence.

### F12 — Safe articulation application
Primijeniti samo artikulacije koje zadovoljavaju određeni prag dokaza.

---

# G. MIDI OPTIMIZATION ENGINE

### G01 — Deterministic optimizer
Ista ulazna datoteka uvijek daje isti rezultat.

### G02 — Track-specific optimization
Svaki track obrađivati posebnim pravilima.

### G03 — Role-aware optimization
Optimizacija zavisna od muzičke funkcije.

### G04 — Factory-aware quantization
Ne quantizovati sve jednako.

### G05 — Microtiming preservation
Zaštititi namjerne mikro-pomake.

### G06 — Velocity normalization
Ispraviti ekstremne velocity vrijednosti bez uništavanja dinamike.

### G07 — Velocity contour preservation
Sačuvati oblik dinamike.

### G08 — Accent preservation
Zaštititi Factory akcentne udare.

### G09 — Note-length optimization
Optimizovati trajanja samo kada je dokazano potrebno.

### G10 — Overlap correction
Pronaći neželjene note overlap-e.

### G11 — Ghost-note protection
Zaštititi namjerne ghost note obrasce.

### G12 — Duplicate note detection
Pronaći identične duple note.

### G13 — Impossible-note detector
Detektovati muzički ili tehnički sumnjive događaje.

### G14 — Range correction
Detektovati tonove van očekivanog registra.

### G15 — Polyphony protection
Zaštititi prirodnu polifoniju.

### G16 — Channel safety
Spriječiti neželjeno miješanje MIDI kanala.

### G17 — Program-change safety
Zaštititi program/bank select podatke.

### G18 — CC protection
Napraviti sistem koji zna koji CC se smije, a koji ne smije mijenjati.

### G19 — CC7 lock verification
Automatski dokazivati da CC7 nije nehotice promijenjen.

### G20 — Event ordering verification
Provjeriti tačan redoslijed kritičnih MIDI događaja.

---

# H. NOISE / DRUM / PERCUSSION INTELLIGENCE

### H01 — Noise-after-song analysis
Analizirati Noise tek nakon kompletne obrade pjesme.

### H02 — Original-track overwrite mode
Noise događaje dodavati ili prepisivati kontrolisano preko originalnog tracka.

### H03 — Noise placement engine
Odrediti gdje noise ima muzički smisao.

### H04 — Drum velocity grammar
Naučiti prirodnu Factory distribuciju drum velocity-ja.

### H05 — Drum ghost detection
Odvojiti ghost od glavnih udaraca.

### H06 — Snare grammar
Naučiti Factory logiku snarea.

### H07 — Kick grammar
Naučiti Factory logiku kicka.

### H08 — Hi-hat grammar
Naučiti otvoreni/zatvoreni hi-hat odnos.

### H09 — Cymbal transition logic
Detektovati transition cymbal ponašanje.

### H10 — Percussion groove model
Naučiti mikro-groove percussion kanala.

### H11 — Drum fill detector
Prepoznati fill obrasce.

### H12 — Fill-to-variation relationship
Analizirati kako se fill razlikuje od glavne Variation strukture.

---

# I. HARMONIJA I CHORD INTELLIGENCE

### I01 — Chord-role inference
Procijeniti koji track zavisi od harmonije.

### I02 — Chord-tone detector
Prepoznati root/third/fifth/seventh funkcije.

### I03 — Passing-tone detector
Odvojiti chord tones od prolaznih tonova.

### I04 — Voice-leading analysis
Analizirati kretanje glasova između uzastopnih akorda.

### I05 — Chord-density model
Odrediti optimalnu gustinu compinga.

### I06 — Harmonic tension model
Izračunati napetost po frazi.

### I07 — Register-aware harmony
Provjeriti da li je voicing u realnom korisnom registru.

### I08 — Factory chord grammar
Napraviti model tipičnog Factory ponašanja po akordima.

### I09 — Chord compatibility test
Provjeriti koliko Pattern dobro radi kroz različite akorde.

### I10 — Harmonic anomaly detector
Pronaći neuobičajene obrasce koji mogu biti greška.

---

# J. GROOVE I HUMANIZATION

### J01 — Factory groove extraction
Izvući groove direktno iz Factory podataka.

### J02 — Genre-specific groove models
Napraviti različite groove modele za Balkan/Folk/Turbo Folk/Sevdah/Kafana itd.

### J03 — Instrument-specific timing
Različito pomjeranje za Bass/Drums/Guitar/Keys.

### J04 — Velocity humanization from Factory DNA
Humanizovati prema stvarnim Factory obrascima.

### J05 — Controlled randomization
Randomizacija samo unutar naučenih granica.

### J06 — Deterministic humanization seed
Omogućiti reproducibilnu humanizaciju.

### J07 — Anti-humanization detector
Pronaći kada obrada zvuči „previše savršeno“.

### J08 — Naturalness score
Izračunati koliko MIDI liči na Factory izvedbu.

### J09 — Groove deviation score
Koliko se obrađeni fajl udaljio od Factory groove-a.

### J10 — Before/after groove proof
Automatski generisati dokaz promjene.

---

# K. FACTORY SIMILARITY ENGINE

### K01 — Style similarity
Naći najbliži Factory Style.

### K02 — Track similarity
Naći najsličniji Factory track.

### K03 — Phrase similarity
Naći najsličniju Factory frazu.

### K04 — Rhythm similarity
Uporediti samo ritam.

### K05 — Harmony similarity
Uporediti samo harmoniju.

### K06 — Velocity similarity
Uporediti dinamiku.

### K07 — Articulation similarity
Uporediti način sviranja.

### K08 — Complete multidimensional similarity
Objediniti sve metrike.

### K09 — Nearest Factory ancestor
Pronaći Factory Style koji je „najbliži predak“ novog MIDI-ja.

### K10 — Similarity confidence
Ne prikazivati sličnost kao apsolutnu istinu nego sa confidence vrijednošću.

---

# L. STYLE GENERATION

### L01 — Generate from Factory DNA
Generisati novi Style iz naučenih obrazaca.

### L02 — Style mutation
Napraviti novu varijantu postojećeg Style-a.

### L03 — Genre transfer
Prenijeti muzičku strukturu jednog žanra u drugi.

### L04 — Groove transfer
Prenijeti groove bez potpunog mijenjanja nota.

### L05 — Bass transfer
Prenijeti Factory Bass ponašanje na drugi Pattern.

### L06 — Drum transfer
Prenijeti drum grammar.

### L07 — Guitar pattern transfer
Prenijeti gitaristički pattern.

### L08 — Chord pattern transfer
Prenijeti comping ponašanje.

### L09 — Energy-controlled generation
Generisati Style prema target energiji.

### L10 — Complexity-controlled generation
Generisati jednostavniju ili složeniju varijantu.

### L11 — Humanization-controlled generation
Kontrolisati koliko će rezultat biti „Factory“ ili „human“.

### L12 — Factory-safe generation
Generacija samo unutar dokazano validnog prostora.

---

# M. INTELLIGENCE / ML / AI

### M01 — Supervised track-role classifier
Trenirati klasifikator na ručno potvrđenim Factory primjerima.

### M02 — Unsupervised Style clustering
Automatsko grupisanje Factory Styleova.

### M03 — Embedding model za MIDI
Pretvoriti Pattern u vektorski embedding.

### M04 — 32D/64D/128D Musical DNA embedding
Eksperimentisati sa dimenzionalnošću.

### M05 — Similarity search preko embeddings
Brzo pronalaženje sličnih Pattern-a.

### M06 — Anomaly detection model
Pronalaženje neuobičajenih Pattern-a.

### M07 — Autoencoder za Style strukturu
Provjeriti može li model naučiti osnovnu reprezentaciju Factory podataka.

### M08 — Transformer MIDI model
Predviđanje sljedećih događaja.

### M09 — Conditional MIDI generation
Generisanje prema Style/tempo/genre/role uslovima.

### M10 — Rule + ML hybrid engine
Kombinovati deterministička pravila sa ML modelom.

### M11 — Confidence-aware AI
AI smije izvršiti promjenu samo kada je confidence dovoljno visok.

### M12 — Explainable AI
Za svaku automatsku odluku prikazati razlog.

---

# N. AUDIO / PCM VALIDACIJA

### N01 — MIDI-to-audio comparison
Uporediti MIDI rezultat sa renderovanim zvukom.

### N02 — Spectral analysis
Analizirati frekvencijski sadržaj.

### N03 — Dynamic range analysis
Provjeriti dinamiku.

### N04 — RMS/LUFS analysis
Izvući objektivne audio metrike.

### N05 — Transient analysis
Analizirati udarce drum/percussion događaja.

### N06 — Bass energy analysis
Provjeriti ponašanje Bass tracka nakon promjena.

### N07 — Drum punch analysis
Provjeriti posljedice velocity/promjena na drumovima.

### N08 — Perceptual difference engine
Procijeniti koliko se audio razlikuje prije/poslije.

### N09 — Blind A/B framework
Automatski pripremiti slijepe A/B testove.

### N10 — MIDI-to-audio forensic correlation
Povezati MIDI promjene sa audio posljedicama.

---

# O. AUTOMATSKO TESTIRANJE

### O01 — Every transformation has a test
Nijedna transformacija bez testa.

### O02 — Golden MIDI regression tests
Golden fajlovi kao referentni standard.

### O03 — Byte-level regression
Provjeravati strukturalne promjene na nivou fajla.

### O04 — Event-level regression
Provjeravati MIDI događaje.

### O05 — Musical regression
Provjeravati muzičke metrike.

### O06 — Factory regression
Provjeravati udaljavanje od Factory DNA.

### O07 — Property-based MIDI testing
Automatski generisati mnogo ulaznih slučajeva.

### O08 — Fuzz testing
Testirati parser na neobičnim MIDI fajlovima.

### O09 — Corruption recovery tests
Provjeriti ponašanje na oštećenim fajlovima.

### O10 — Round-trip tests
Import → process → export → import.

### O11 — Determinism tests
Isti ulaz mora uvijek dati isti rezultat.

### O12 — Cross-module integration tests
Dokazati veze između svih .py modula.

### O13 — Database consistency tests
Provjeriti da kod i DB koriste ista pravila.

### O14 — Protocol-order tests
Provjeravati redoslijed događaja.

### O15 — Physical-evidence gate
Build ne označiti „certified“ bez odgovarajućeg eksternog dokaza.

---

# P. DATABASE INTELLIGENCE

### P01 — Factory Style relational graph
Povezati Style → Track → Pattern → DNA → Instrument → Articulation.

### P02 — Pattern provenance
Čuvati iz kojeg fajla i tačno kojeg mjesta dolazi svaki Pattern.

### P03 — Evidence database
Za svaku tvrdnju čuvati izvor i dokaz.

### P04 — Rule provenance
Znati iz kojeg Factory podatka je nastalo pravilo.

### P05 — Confidence database
Čuvati confidence svakog zaključka.

### P06 — Negative knowledge database
Čuvati i ono što je dokazano da NE treba raditi.

### P07 — Cross-style behavior database
Naći pravila koja se ponavljaju kroz mnogo Styleova.

### P08 — Outlier database
Posebno čuvati izuzetke.

### P09 — Versioned Factory knowledge
Svaka izmjena pravila dobija verziju.

### P10 — Reproducible dataset builds
Baza se uvijek može ponovno izgraditi iz sirovog korpusa.

---

# Q. FORENSIC PROVENANCE

### Q01 — Every result has source
Svaki rezultat mora imati izvor.

### Q02 — Every rule has evidence level
DOKAZANO / VISOKO VJEROVATNO / HIPOTEZA.

### Q03 — Immutable original archive
Originalni Factory fajlovi nikada se ne mijenjaju.

### Q04 — Processing manifest
Za svaki output čuvati kompletan manifest obrade.

### Q05 — Hash-based provenance
SHA256 ili sličan hash za ulaze/izlaze.

### Q06 — Pipeline event log
Svaka transformacija dobija zapis.

### Q07 — Decision trace
Prikazati zašto je optimizer donio određenu odluku.

### Q08 — Reproducible execution
Svaki rezultat mora biti ponovljiv.

---

# R. AUTOMATSKI FACTORY STYLE EDITOR

### R01 — Visual MIDI editor
GUI za direktan pregled Pattern-a.

### R02 — Track role editor
Ručno potvrđivanje Bass/Drum/Chord itd.

### R03 — DNA inspector
Prikaz kompletnog DNA potpisa.

### R04 — Pattern inspector
Prikaz 1/2/4/8-taktnih Pattern-a.

### R05 — Factory comparison view
Original naspram novog Pattern-a.

### R06 — Similar Style browser
Pronaći najbliže Factory Styleove.

### R07 — Articulation map editor
Vizualno uređivanje RX/DNC logike.

### R08 — Velocity map
Vizualizacija velocity ponašanja.

### R09 — Groove map
Vizualizacija mikro-timinga.

### R10 — Event forensic editor
Pregled svih MIDI događaja.

### R11 — Before/after diff
Tačno pokazati šta se promijenilo.

### R12 — Safe edit mode
Omogućiti samo izmjene koje zadovoljavaju pravila.

---

# S. AUTOMATSKI STYLE REPAIR

### S01 — Broken Style detection
Pronaći potencijalno oštećene Styleove.

### S02 — Missing event detection
Naći nedostajuće događaje.

### S03 — Broken timing detection
Naći neprirodne timing vrijednosti.

### S04 — Broken velocity detection
Naći anomalije velocity-ja.

### S05 — Broken articulation detection
Naći sumnjive articulation evente.

### S06 — Broken channel detection
Pronaći pogrešne kanale.

### S07 — Broken program mapping
Provjeriti instrument mapping.

### S08 — Structural repair
Automatski popraviti dokazive strukturalne greške.

### S09 — Musical repair
Popraviti samo ono za šta postoji dovoljno dokaza.

### S10 — Repair confidence
Svaka popravka dobija score.

---

# T. GM → KORG INTELLIGENCE

### T01 — GM instrument detection
Prepoznati početni GM instrument.

### T02 — Korg bank-select mapping
Mapirati MSB/LSB/Program.

### T03 — RX Sound mapping
Predložiti RX sound.

### T04 — DNC Sound mapping
Predložiti DNC sound.

### T05 — Role-aware instrument mapping
Instrument zavisi od muzičke funkcije.

### T06 — Factory-native mapping
Pronaći koji Korg sound najviše odgovara Factory primjerima.

### T07 — Multi-candidate sound ranking
Dati više mogućih soundova sa scoreom.

### T08 — Sound confidence
Procijeniti sigurnost mapiranja.

### T09 — Forbidden mapping detector
Spriječiti pogrešna mapiranja.

### T10 — Instrument profile database
Napraviti bazu ponašanja svakog instrumenta.

---

# U. INSTRUMENT PROFILE ENGINE

### U01 — Bass profile
### U02 — Electric guitar profile
### U03 — Acoustic guitar profile
### U04 — Piano profile
### U05 — Organ profile
### U06 — Brass profile
### U07 — Strings profile
### U08 — Pad profile
### U09 — Synth profile
### U10 — Drum profile
### U11 — Percussion profile
### U12 — Lead profile
### U13 — Instrument articulation profile
### U14 — Instrument register profile
### U15 — Instrument velocity profile

Za svaki profil utvrditi:

**range + density + velocity + timing + articulation + polyphony + typical role + Factory examples**

---

# V. AUTOMATSKA ANALIZA PJESME

### V01 — Song-level musical DNA
### V02 — Tempo map
### V03 — Time-signature map
### V04 — Energy curve
### V05 — Density curve
### V06 — Velocity curve
### V07 — Register curve
### V08 — Harmony map
### V09 — Instrument-role map
### V10 — Arrangement map
### V11 — Tension/release map
### V12 — Intro/Verse/Chorus/Bridge candidate detection
### V13 — Repetition map
### V14 — Change-point detection

---

# W. INTELIGENTNO PREPOZNAVANJE ŽANRA

### W01 — Serbian Folk classifier
### W02 — Turbo Folk classifier
### W03 — Sevdah classifier
### W04 — Kafana classifier
### W05 — Balkan generic classifier
### W06 — Pop/Folk crossover detector
### W07 — Rock/Folk hybrid detector
### W08 — Rap/Folk hybrid detector
### W09 — Genre confidence
### W10 — Multi-genre mixture model

---

# X. AUTOMATSKA PROCJENA KVALITETA

### X01 — Musical Quality Score
### X02 — Factory Similarity Score
### X03 — Groove Score
### X04 — Dynamics Score
### X05 — Articulation Score
### X06 — Arrangement Score
### X07 — Harmony Score
### X08 — Humanization Score
### X09 — Technical MIDI Score
### X10 — Overall Confidence Score

Važno: jedan „Quality 85%“ ne smije biti samo proizvoljna formula. Svaka komponenta mora imati dokazivu definiciju.

---

# Y. MULTI-OBJECTIVE OPTIMIZATION

### Y01 — Maximize Factory similarity
### Y02 — Maximize naturalness
### Y03 — Minimize technical errors
### Y04 — Preserve original musical identity
### Y05 — Preserve articulation
### Y06 — Preserve arrangement
### Y07 — Preserve groove
### Y08 — Preserve dynamics
### Y09 — Optimize instrument mapping
### Y10 — Balance all objectives

Napraviti Pareto pristup gdje korisnik može birati:

**Originality ←→ Factory Match ←→ Humanization ←→ Technical Cleanliness**

---

# Z. AI AGENT FORENSIC ORCHESTRATION

### Z01 — Agent koji samo analizira
Bez mijenjanja koda.

### Z02 — Agent koji samo dokazuje
Traži testove i dokaze.

### Z03 — Agent koji prati veze između .py fajlova
Dependency/data-flow audit.

### Z04 — Agent koji prati MIDI write operacije
Svaka izmjena MIDI događaja mora biti pronađena.

### Z05 — Agent koji prati velocity write operacije
Dokazati svaku promjenu velocity-ja.

### Z06 — Agent koji prati CC write operacije
Dokazati sve CC izmjene.

### Z07 — Agent za SysEx audit
Pronaći svaku SysEx transformaciju.

### Z08 — Agent za database/code consistency
Uporediti DB pravila i implementaciju.

### Z09 — Agent za protocol validation
Provjeriti Korg-protokolne pretpostavke.

### Z10 — Agent za regression hunting
Pronaći šta je nova verzija pokvarila.

### Z11 — Agent za unused-code detection
Pronaći mrtav kod.

### Z12 — Agent za unreachable logic
Pronaći logiku koja se nikada ne izvršava.

### Z13 — Agent za duplicated logic
Pronaći ista pravila implementirana na više mjesta.

### Z14 — Agent za hidden assumptions
Pronaći neprovjerene pretpostavke.

### Z15 — Agent za contradiction detection
Pronaći konflikt između modula.

---

# AA. SELF-AUDITING ENGINE

### AA01 — Self-test prije obrade
Program provjeri vlastito stanje.

### AA02 — Self-test poslije obrade
Program provjeri rezultat.

### AA03 — Rule integrity
Provjeri da su sva pravila učitana.

### AA04 — Database integrity
Provjeri DB prije izvršenja.

### AA05 — Configuration integrity
Provjeri konfiguraciju.

### AA06 — Dependency integrity
Provjeri verzije i dostupnost biblioteka.

### AA07 — Model integrity
Provjeri AI model.

### AA08 — Output integrity
Provjeri finalni MIDI.

### AA09 — Automatic rollback
Ako rezultat ne prođe validaciju, vrati original.

### AA10 — Safe failure
Nikada ne proizvesti „validan“ output kada validacija nije prošla.

---

# AB. FACTORY KNOWLEDGE GRAPH

### AB01 — Style graph
### AB02 — Track graph
### AB03 — Pattern graph
### AB04 — Instrument graph
### AB05 — Articulation graph
### AB06 — Genre graph
### AB07 — Similarity graph
### AB08 — Provenance graph
### AB09 — Rule graph
### AB10 — Evidence graph

Cilj: napraviti mrežu u kojoj se može pitati:

**„Zašto je ovaj Pattern klasifikovan kao Bass?“**

i dobiti lanac:

**Pattern → features → Factory examples → rule → confidence → evidence**

---

# AC. AUTOMATSKO UČENJE IZ NOVIH FACTORY PODATAKA

### AC01 — Incremental learning
Dodavanje novih Styleova bez potpunog rebuilda modela.

### AC02 — New-pattern discovery
Automatsko otkrivanje novih obrazaca.

### AC03 — Rule mining
Automatsko pronalaženje pravila.

### AC04 — Cross-style rule mining
Pronalaženje pravila koja se ponavljaju kroz različite Styleove.

### AC05 — Exception mining
Automatsko pronalaženje izuzetaka.

### AC06 — Confidence evolution
Confidence se povećava kada se pravilo potvrdi na više primjera.

### AC07 — Dataset contamination detection
Pronaći duplikate ili pogrešno klasifikovane podatke.

### AC08 — Golden dataset drift detection
Detektovati kada novi podaci mijenjaju definiciju „Factory ponašanja“.

---

# AD. ADVANCED SEARCH ENGINE

### AD01 — Search by Style
### AD02 — Search by Pattern
### AD03 — Search by Rhythm
### AD04 — Search by Groove
### AD05 — Search by Instrument
### AD06 — Search by Articulation
### AD07 — Search by Velocity
### AD08 — Search by Harmony
### AD09 — Search by DNA similarity
### AD10 — Search by natural-language description

Primjer:

**„Nađi sve Factory gitarističke Pattern-e slične balkanskom 16-beat groove-u, sa velocityjem 70–105 i syncopated endingom.“**

---

# AE. AUTOMATSKA GENERACIJA IZVJEŠTAJA

### AE01 — MIDI forensic report
### AE02 — Factory similarity report
### AE03 — DNA report
### AE04 — Optimization report
### AE05 — Before/after report
### AE06 — Test evidence report
### AE07 — Database audit report
### AE08 — Protocol audit report
### AE09 — Agent work report
### AE10 — Certification report

---

# AF. CERTIFICATION SISTEM

### AF01 — CODE PASS
### AF02 — UNIT PASS
### AF03 — INTEGRATION PASS
### AF04 — REGRESSION PASS
### AF05 — MIDI STRUCTURAL PASS
### AF06 — FACTORY DNA PASS
### AF07 — AUDIO PASS
### AF08 — BLIND A/B PASS
### AF09 — HUMAN EVALUATION PASS
### AF10 — PHYSICAL KORG PASS

Konačni status ne bi smio biti samo:

**„TESTOVI PROŠLI“**

nego npr.:

**CODE PASS  
MIDI PASS  
DNA PASS  
FACTORY PASS  
AUDIO PASS  
PHYSICAL KORG = NOT VERIFIED**

---

# AG. PHYSICAL KORG VALIDATION

### AG01 — PA800 real-hardware test harness
### AG02 — Automated test MIDI suite
### AG03 — Instrument-by-instrument verification
### AG04 — RX verification
### AG05 — DNC verification
### AG06 — Drum verification
### AG07 — Bass verification
### AG08 — Chord verification
### AG09 — Fill verification
### AG10 — Variation verification
### AG11 — Ending verification
### AG12 — Song Play verification

---

# AH. PERFORMANCE / SCALE

### AH01 — 1,000 MIDI benchmark
### AH02 — 10,000 MIDI benchmark
### AH03 — 100,000 MIDI benchmark
### AH04 — Memory profiling
### AH05 — CPU profiling
### AH06 — Database query profiling
### AH07 — Parallel processing
### AH08 — Batch processing
### AH09 — Cache system
### AH10 — Incremental rebuild
### AH11 — GPU acceleration feasibility
### AH12 — Streaming analysis

---

# AI. ADVANCED SAFETY

### AI01 — Original file immutable mode
### AI02 — Output-only mode
### AI03 — Dry-run mode
### AI04 — Diff-only mode
### AI05 — Rule whitelist
### AI06 — Rule blacklist
### AI07 — Maximum-change threshold
### AI08 — Track protection
### AI09 — Event protection
### AI10 — Automatic rollback
### AI11 — Full audit trail
### AI12 — User approval gate

---

# AJ. FUTURE HIGH-END POSSIBILITIES

### AJ01 — Factory Style reconstruction from audio
Iz audio snimka pokušati rekonstruisati MIDI/Style strukturu.

### AJ02 — Audio → MIDI → Factory DNA
Kompletan pipeline.

### AJ03 — MIDI → Style
Od običnog MIDI-ja napraviti Style-like strukturu.

### AJ04 — Song → Style extraction
Iz pjesme izvući ritam, bass, guitar i chord Pattern-e.

### AJ05 — Style → Song generation
Od Factory Style DNA generisati kompletnu MIDI pjesmu.

### AJ06 — Singer-aware arrangement
Prilagoditi aranžman vokalnoj liniji.

### AJ07 — Vocal-aware accompaniment
Pratnju prilagoditi melodiji pjevača.

### AJ08 — Emotion-controlled arrangement
Kontrola preko emocije/energije.

### AJ09 — Live-performance mode
MIDI mijenjati tokom sviranja.

### AJ10 — Intelligent arranger assistant
Sistem predlaže šta treba promijeniti, ali ništa ne izvršava bez odobrenja.

---

# AK. EKSPERIMENTALNE IDEJE

### AK01 — Factory Style „DNA inheritance“
Style može nasljeđivati osobine drugog Style-a.

### AK02 — Musical mutation engine
Kontrolisane mutacije Pattern-a.

### AK03 — Pattern crossover
Kombinovati dijelove dva kompatibilna Pattern-a.

### AK04 — Style evolution simulator
Simulirati generacije Style varijacija.

### AK05 — Factory similarity landscape
Vizualizovati cijeli Factory corpus kao mapu.

### AK06 — Musical fingerprint search
Jedinstveni „prst otisak“ Pattern-a.

### AK07 — Outlier Style discovery
Pronaći najneobičnije Factory Styleove.

### AK08 — Hidden Factory families
Pronaći grupe koje nisu očigledne po nazivu Style-a.

### AK09 — Historical reconstruction
Pokušati rekonstruisati razvoj Pattern-a kroz dataset.

### AK10 — Style authenticity score
Procijeniti koliko novi Style „zvuči kao da je došao iz Factory corpus-a“.

---

# AL. IDEJE ZA „ONE-CLICK“ SISTEM

### AL01 — Analyze
Kompletna analiza MIDI-ja.

### AL02 — Diagnose
Pronaći probleme.

### AL03 — Compare
Uporediti sa Factory bazom.

### AL04 — Recommend
Predložiti izmjene.

### AL05 — Optimize
Primijeniti samo odobrene izmjene.

### AL06 — Humanize
Dodati Factory-aware humanization.

### AL07 — Map
Mapirati GM → Korg.

### AL08 — Articulate
Dodati RX/DNC gdje postoji dokaz.

### AL09 — Validate
Pokrenuti kompletan test.

### AL10 — Certify
Generisati certification report.

---

# AM. NAJVAŽNIJI META-SISTEM

### AM01 — „DO NOT CHANGE“
Sistem prvo pronalazi šta se **ne smije** mijenjati.

### AM02 — „SAFE TO CHANGE“
Pronalazi šta je dokazano sigurno.

### AM03 — „MAY CHANGE“
Pronalazi stvari koje se mogu mijenjati uz određeni confidence.

### AM04 — „MUST CHANGE“
Pronalazi dokazive greške.

### AM05 — „UNKNOWN“
Sve što nije dovoljno dokazano ostaje netaknuto.

Ovo može postati centralna filozofija cijelog Optimizer-a:

**PRESERVE → PROVE → CHANGE → VERIFY**

---

# AN. IDEJE ZA AGENTSKI RADNI TOK

Za svaku pojedinačnu stavku agent treba izvršiti:

**1. DISCOVER**  
Pronađi gdje se mogućnost već pojavljuje u kodu, DB-u ili datasetu.

**2. TRACE**  
Prati sve module, funkcije i podatke koji učestvuju.

**3. PROVE**  
Nađi test ili napravi test koji potvrđuje ponašanje.

**4. IMPLEMENT**  
Implementiraj samo ono što je dokazivo.

**5. REGRESSION**  
Provjeri da nije pokvareno postojeće ponašanje.

**6. MEASURE**  
Izmjeri rezultat prije/poslije.

**7. DOCUMENT**  
Upiši izvor, dokaz, ograničenja i confidence.

**8. CERTIFY**  
Označi:
- `PROVEN`
- `PARTIALLY_PROVEN`
- `EXPERIMENTAL`
- `UNVERIFIED`
- `REJECTED`

---

# AO. VRHUNSKI CILJ PROJEKTA

Krajnji cilj nije samo:

**„MIDI Optimizer koji mijenja MIDI.“**

Nego sistem koji može odgovoriti:

> **Šta je ovaj MIDI?**  
> **Zašto je napravljen ovako?**  
> **Na koji Factory Style najviše liči?**  
> **Koji track šta radi?**  
> **Koje artikulacije koristi?**  
> **Šta je tehnički pogrešno?**  
> **Šta je muzički dobro?**  
> **Šta je sigurno promijeniti?**  
> **Zašto je sigurno?**  
> **Šta će se promijeniti nakon obrade?**  
> **Da li rezultat i dalje liči na Factory?**  
> **Da li je rezultat reproducibilan?**  
> **Da li je fizički potvrđen na PA800?**

---

# AP. PRIORITETNI „GOLDEN“ PODSKUP ZA PRVE AGENTE

Ako treba krenuti od najvrjednijih mogućnosti, prioritet bih dao:

**AP01 — Complete Factory DNA**

**AP02 — Pattern DNA**

**AP03 — Track-role intelligence**

**AP04 — Factory similarity engine**

**AP05 — RX/DNC articulation inference**

**AP06 — Factory-aware humanization**

**AP07 — Noise intelligence**

**AP08 — GM → Korg/RX/DNC mapping**

**AP09 — Forensic provenance**

**AP10 — Evidence-based optimizer**

**AP11 — Before/after forensic diff**

**AP12 — Complete regression framework**

**AP13 — Factory knowledge graph**

**AP14 — Confidence engine**

**AP15 — Physical Korg validation framework**

**AP16 — Automatic Style editor**

**AP17 — Style generation from Factory DNA**

**AP18 — Song → Style extraction**

**AP19 — MIDI → Audio → MIDI validation loop**

**AP20 — Fully self-auditing X10 Musical Intelligence Engine**

---

## CENTRALNI PRINCIP

**Svaku mogućnost tretirati kao zaseban eksperiment.**

**Ne pitati samo „može li?“**

Nego:

**MOŽE LI → GDJE JE EVIDENCIJA → KAKO TO DOKAZATI → KAKO PRIMIJENITI → KAKO TESTIRATI → KAKO DOKAZATI DA NIJE POGORŠANO**

Na taj način možeš agentima slati jednu po jednu stavku iz ovog registra, a njihov posao je da pronađu **konkretnu tehničku primjenu u postojećem projektu**, umjesto da samo generišu nove ideje.