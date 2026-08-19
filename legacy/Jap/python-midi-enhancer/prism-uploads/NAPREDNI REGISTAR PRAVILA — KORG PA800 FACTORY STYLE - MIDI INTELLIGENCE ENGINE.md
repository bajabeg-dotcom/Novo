# NAPREDNI REGISTAR PRAVILA
## KORG PA800 Factory Style / MIDI / Factory DNA / RX-DNC / Intelligence System

### Svrha

Ovaj registar predstavlja centralnu bazu mogućih **pravila sistema**.

Svako pravilo može se pojedinačno dati agentu da:

**pronađe → provjeri → dokaže → implementira → testira → dokumentuje**

Nijedno pravilo ne treba automatski smatrati tačnim samo zato što zvuči muzički logično.

Svako pravilo mora dobiti status:

- `PROVEN`
- `PARTIALLY_PROVEN`
- `FACTORY_OBSERVED`
- `INFERRED`
- `EXPERIMENTAL`
- `UNVERIFIED`
- `REJECTED`

---

# A. TEMELJNA PRAVILA SISTEMA

### A01 — Originalni MIDI nikad se ne mijenja
Original mora ostati byte-for-byte sačuvan.

### A02 — Svaka obrada radi nad kopijom
Optimizer nikada ne smije direktno uništavati ulazni fajl.

### A03 — Nema promjene bez razloga
Svaka izmjena mora imati konkretan razlog.

### A04 — Nema promjene bez evidence
Svaka izmjena mora imati dokaz ili jasno označenu eksperimentalnu prirodu.

### A05 — Nepoznat element se ne dira
Ako sistem ne razumije događaj, podrazumijevano ga čuva.

### A06 — Preserve before optimize
Prvo zaštititi originalno ponašanje, pa tek onda optimizovati.

### A07 — Minimal-change principle
Napraviti najmanju moguću promjenu koja rješava problem.

### A08 — Deterministic processing
Isti input + ista konfiguracija = isti output.

### A09 — No hidden mutation
Nijedna funkcija ne smije krišom mijenjati MIDI.

### A10 — Every write is traceable
Svaki zapis/izmjena MIDI eventa mora biti sljediva.

---

# B. MIDI PARSER PRAVILA

### B01 — Parser mora validirati MIDI header
Format i division moraju biti provjereni.

### B02 — Track count mora odgovarati stvarnom broju trackova.

### B03 — PPQN se ne smije pretpostavljati.

### B04 — SMPTE division se ne smije tretirati kao PPQN.

### B05 — Delta-time mora biti pravilno akumuliran.

### B06 — Running status mora biti pravilno obrađen.

### B07 — Meta eventi se ne smiju odbacivati bez razloga.

### B08 — SysEx se ne smije odbacivati bez eksplicitnog pravila.

### B09 — Unknown event mora biti sačuvan ili eksplicitno prijavljen.

### B10 — Event order mora biti stabilan.

### B11 — Note-on velocity 0 mora biti tretiran prema MIDI pravilima.

### B12 — End-of-track mora biti validiran.

### B13 — Malformed MIDI ne smije tiho proći kao validan.

### B14 — Parser mora evidentirati svaku recovery akciju.

### B15 — Parse → export → parse mora biti konzistentan.

---

# C. TEMPO PRAVILA

### C01 — Originalni tempo se nikada ne mijenja bez eksplicitnog zahtjeva.

### C02 — Tempo mapa mora biti sačuvana.

### C03 — Sve promjene tempa moraju biti identificirane.

### C04 — Event koji zavisi od apsolutnog vremena mora koristiti tačnu tempo mapu.

### C05 — Ne pretvarati tickove u sekunde preko jednog BPM-a ako postoji tempo mapa.

### C06 — Tempo normalizacija je posebna operacija, nikad implicitna.

### C07 — Tempo change event mora biti auditiran nakon exporta.

---

# D. TIME SIGNATURE PRAVILA

### D01 — Originalni takt mora biti sačuvan.

### D02 — Time-signature event se ne smije izgubiti.

### D03 — Granice taktova računaju se prema stvarnom meteru.

### D04 — Pattern segmentation ne smije pretpostaviti 4/4.

### D05 — Promjena takta mora kreirati novi muzički kontekst.

### D06 — Quantization grid mora zavisiti od takta kada je relevantno.

---

# E. NOTE PRAVILA

### E01 — Note-on i Note-off moraju ostati pravilno upareni.

### E02 — Note duration mora biti izračunat iz stvarnih eventova.

### E03 — Duplikat note ne smije automatski značiti grešku.

### E04 — Overlap ne smije automatski značiti grešku.

### E05 — Voice-leading kontekst mora se uzeti u obzir.

### E06 — Kratka nota nije automatski ghost note.

### E07 — Duga nota nije automatski pad.

### E08 — Jedna nota nije dovoljna za klasifikaciju funkcije.

### E09 — Note koje pripadaju artikulaciji ne smiju se automatski brisati.

### E10 — Note izvan očekivanog registra označiti, a ne automatski brisati.

---

# F. VELOCITY PRAVILA

### F01 — Velocity 1–127 je validni MIDI opseg.

### F02 — Velocity 0 note-on mora biti pravilno tretiran.

### F03 — Velocity se ne normalizuje globalno bez analize tracka.

### F04 — Velocity contour mora biti sačuvan.

### F05 — Akcenti moraju biti zaštićeni.

### F06 — Ghost note obrasci moraju biti zaštićeni.

### F07 — Drum velocity se ne smije tretirati kao melody velocity.

### F08 — Bass velocity ne smije koristiti isti model kao hi-hat.

### F09 — Velocity humanization mora biti role-aware.

### F10 — Nema random velocity promjena bez ograničenja.

### F11 — Factory-derived velocity model ima prednost nad generičkim randomizationom.

### F12 — Svaka velocity write operacija mora biti logovana.

### F13 — Ako velocity promjena prelazi definisani prag, mora postojati dodatni dokaz.

### F14 — Velocity original-vs-output diff mora biti dostupan.

---

# G. TIMING / GROOVE PRAVILA

### G01 — Ne quantizovati sve note na isti način.

### G02 — Grid nije nužno stvarna izvedbena pozicija.

### G03 — Namjerni mikro-offset mora biti zaštićen.

### G04 — Humanization ne smije uništiti groove.

### G05 — Timing model zavisi od muzičke uloge.

### G06 — Bass i kick imaju različitu timing toleranciju.

### G07 — Guitar strumming ima specifičnu toleranciju.

### G08 — Percussion može imati veći mikro-timing prostor.

### G09 — Groove extraction mora koristiti Factory podatke kada su dostupni.

### G10 — Quantization mora imati audit trail.

### G11 — Microtiming promjene moraju imati prije/poslije metriku.

### G12 — Ne dozvoliti cumulative timing drift.

---

# H. TRACK ROLE PRAVILA

### H01 — MIDI kanal sam po sebi nije dovoljan za određivanje uloge.

### H02 — Program Change sam po sebi nije dovoljan.

### H03 — Uloga se određuje kombinacijom više feature-a.

### H04 — Drum channel mora imati poseban tretman.

### H05 — Bass mora imati poseban model.

### H06 — Chord/comping mora imati poseban model.

### H07 — Solo melodija mora biti zaštićena.

### H08 — Solo guitar mora biti zaštićena od generičkog humanizationa.

### H09 — Riff guitar mora imati drugačije pravilo od solo gitare.

### H10 — Track role classifier mora imati confidence.

### H11 — Low-confidence track ne smije biti agresivno obrađen.

---

# I. BASS PRAVILA

### I01 — Bass mora ostati u svom funkcionalnom registru.

### I02 — Bass ne smije nepotrebno duplirati chord register.

### I03 — Root movement mora biti očuvan.

### I04 — Passing tone ne smije automatski biti uklonjen.

### I05 — Bass groove mora biti sačuvan.

### I06 — Bass velocity ne smije biti globalno normalizovan.

### I07 — Bass note length mora pratiti muzičku funkciju.

### I08 — Kick/Bass timing konflikt treba prijaviti.

### I09 — Bass collision s drugim niskim trackovima mora biti analiziran.

### I10 — Bass optimization mora biti harmonic-aware.

---

# J. DRUM PRAVILA

### J01 — Drum kanal mora biti tretiran kao zaseban sistem.

### J02 — Kick, snare, hat i cymbal imaju različita pravila.

### J03 — Ghost note se ne smije automatski izbrisati.

### J04 — Identical note repetition ne znači automatski bug.

### J05 — Drum fill mora biti prepoznat prije promjene.

### J06 — Variation groove mora biti zaštićen.

### J07 — Fill može imati drugačiju velocity grammar.

### J08 — Hi-hat open/closed relationship mora biti očuvan.

### J09 — Cymbal transition mora biti očuvan.

### J10 — Drum humanization mora biti instrument-specific.

---

# K. PERCUSSION PRAVILA

### K01 — Percussion se ne smije tretirati kao kick/snare.

### K02 — Percussion groove mora biti analiziran zasebno.

### K03 — High-density percussion mora imati poseban threshold.

### K04 — Kratke percussion note nisu automatski noise.

### K05 — Percussion velocity ima zaseban model.

### K06 — Repeated percussion pattern mora biti prepoznat prije humanizacije.

---

# L. HARMONIJSKA PRAVILA

### L01 — Chord context ima prednost nad pojedinačnom notom.

### L02 — Chord tone se ne smije brisati samo zato što izgleda redundantno.

### L03 — Passing tone mora biti analiziran u kontekstu.

### L04 — Neighbor tone mora biti sačuvan kada ima muzičku funkciju.

### L05 — Voice-leading mora biti zaštićen.

### L06 — Chord voicing ne smije biti automatski normalizovan.

### L07 — Register mora biti uzet u obzir.

### L08 — Harmonic anomaly nije automatski MIDI bug.

### L09 — Chord-dependent Pattern ne smije se tretirati kao obična melodija.

### L10 — Harmonic transformation mora proći multi-note validation.

---

# M. POLIFONIJA PRAVILA

### M01 — Maksimalna polifonija mora biti izmjerena prije izmjene.

### M02 — Polyphony limit ne smije se automatski pretpostavljati.

### M03 — Overlap se procjenjuje u kontekstu.

### M04 — Akordne note se ne smiju automatski smanjivati radi „čistoće“.

### M05 — Polifonija Drums tracka tretira se drugačije od harmonic tracka.

### M06 — Polyphony reduction mora imati minimal-change pravilo.

---

# N. REGISTER PRAVILA

### N01 — Svaki instrument ima expected register.

### N02 — Out-of-range nota je prvo anomaly, tek onda potencijalna greška.

### N03 — Register mora zavisiti od instrumenta.

### N04 — Register mora zavisiti od funkcije.

### N05 — Register ne smije automatski biti transponovan na C.

### N06 — Ne mijenjati oktavu bez jasnog razloga.

### N07 — Extreme register events moraju biti evidentirani.

---

# O. TRANSPOSE PRAVILA

### O01 — Globalni transpose nije dozvoljen bez eksplicitne naredbe.

### O02 — Ne transponovati MIDI automatski u C.

### O03 — Key context mora biti očuvan.

### O04 — Relative interval relationships moraju ostati stabilne.

### O05 — Drum note numbers se ne transponuju.

### O06 — Percussion mapping se ne transponuje kao melodija.

---

# P. PROGRAM / BANK SELECT PRAVILA

### P01 — Program Change se ne smije brisati bez razloga.

### P02 — Bank Select MSB mora biti očuvan.

### P03 — Bank Select LSB mora biti očuvan.

### P04 — Program Change order mora biti sačuvan.

### P05 — Instrument mapping mora biti role-aware.

### P06 — Ne mapirati GM → Korg samo na osnovu naziva instrumenta.

### P07 — Factory sound mapping ima prednost nad generičkim GM mappingom kada postoji dokaz.

### P08 — Ne mijenjati program bez audit zapisa.

---

# Q. CC PRAVILA

### Q01 — CC7 mora biti zaštićen ako je zaključan pravilima projekta.

### Q02 — CC11 se ne smije globalno mijenjati bez analize.

### Q03 — CC64 mora biti tretiran posebno.

### Q04 — CC1/Modulation mora biti sačuvan kada ima funkciju.

### Q05 — Unknown CC ne brisati automatski.

### Q06 — CC write operation mora biti auditirana.

### Q07 — CC vrijednosti se ne smiju normalizovati bez konteksta.

### Q08 — CC događaji moraju biti analizirani po tracku i kanalu.

---

# R. SYSEX PRAVILA

### R01 — SysEx se nikada ne briše „jer nije standardni MIDI“.

### R02 — Unknown SysEx se čuva.

### R03 — Korg SysEx se označava i parsira kada postoji dokaz.

### R04 — SysEx promjena mora biti posebno logovana.

### R05 — Ne generisati Korg SysEx iz pretpostavke.

### R06 — SysEx integrity test obavezan je nakon exporta.

---

# S. RX / DNC PRAVILA

### S01 — RX/DNC ne pretpostavljati bez dokaza.

### S02 — Artikulacija mora zavisiti od konteksta.

### S03 — Jedan event nije dovoljan za sigurnu klasifikaciju.

### S04 — Guitar articulation mora imati guitar-aware pravila.

### S05 — Noise articulation mora biti odvojena od obične note.

### S06 — Strum obrasci moraju biti analizirani kao grupa.

### S07 — Articulation candidates dobijaju confidence.

### S08 — Low-confidence articulation se samo predlaže.

### S09 — High-confidence articulation može biti automatski primijenjena samo ako postoji dokazano pravilo.

### S10 — Articulation transformacija mora biti reverzibilna.

### S11 — Originalni articulation context mora biti sačuvan.

### S12 — Konflikt RX/DNC pravila mora rezultirati `REVIEW`, a ne nasumičnim izborom.

---

# T. NOISE PRAVILA

### T01 — Noise se ne dodaje prije završetka osnovne MIDI obrade ako pipeline to zahtijeva.

### T02 — Noise analiza se radi tek nakon finalizacije glavnog musical layera.

### T03 — Noise ne smije duplicirati postojeći event bez razloga.

### T04 — Noise placement mora biti context-aware.

### T05 — Originalni track se mora sačuvati prije overwrite operacije.

### T06 — Noise append/overwrite mora biti eksplicitno definisan.

### T07 — Noise velocity mora imati vlastita pravila.

### T08 — Noise mora imati vlastiti provenance zapis.

### T09 — Noise write operation mora biti posebno testirana.

---

# U. FACTORY DNA PRAVILA

### U01 — Factory DNA je referentni model, ne apsolutna naredba.

### U02 — Izuzeci iz Factory corpus-a moraju ostati vidljivi.

### U03 — Jedan Factory primjer nije dovoljan za globalno pravilo.

### U04 — Pravilo postaje jače što je više nezavisnih primjera potvrđeno.

### U05 — Cross-style potvrda ima veću težinu od single-style dokaza.

### U06 — Rare Pattern ne smije automatski biti označen kao greška.

### U07 — Outlier mora biti posebno sačuvan.

### U08 — DNA promjena mora biti mjerljiva.

### U09 — Before/after DNA score obavezan je za veće izmjene.

### U10 — Optimizer ne smije nepotrebno udaljiti rezultat od Factory DNA.

---

# V. FACTORY PATTERN PRAVILA

### V01 — Pattern granice moraju biti muzički validne.

### V02 — 1-taktni Pattern nije uvijek dovoljan za klasifikaciju.

### V03 — 2/4/8/16 taktova koristiti kada kontekst zahtijeva.

### V04 — Pattern repetition mora biti analiziran.

### V05 — Near-duplicate Pattern-i ne smiju se nepotrebno tretirati kao različiti.

### V06 — Signature Pattern mora biti zaštićen.

### V07 — Pattern mutation mora biti ograničena.

### V08 — Pattern transplant mora provjeriti kompatibilnost.

### V09 — Pattern crossover nije dozvoljen bez compatibility check-a.

### V10 — Pattern sa konfliktom harmonije ne smije biti automatski primijenjen.

---

# W. GROOVE / HUMANIZATION PRAVILA

### W01 — Humanization nije randomization.

### W02 — Randomness nije dozvoljena bez eksplicitne dozvole.

### W03 — Humanization mora biti deterministic kada je u produkcijskom optimizeru.

### W04 — Timing i velocity se ne smiju mijenjati potpuno nezavisno.

### W05 — Humanization mora pratiti instrument.

### W06 — Humanization mora pratiti žanr kada postoji model.

### W07 — Factory-derived limits imaju prednost.

### W08 — Prekomjerna humanizacija mora biti detektovana.

### W09 — Groove deviation mora imati limit.

### W10 — Humanization ne smije promijeniti identitet Pattern-a.

---

# X. OPTIMIZATION PRAVILA

### X01 — Optimizer ne smije biti destructive by default.

### X02 — Svaka transformacija ima precondition.

### X03 — Svaka transformacija ima postcondition.

### X04 — Svaka transformacija ima confidence.

### X05 — Svaka transformacija mora biti testirana.

### X06 — Jedna transformacija ne smije poništiti raniju bez upozorenja.

### X07 — Pravila se izvršavaju u determinističkom redoslijedu.

### X08 — Critical transformations imaju priority.

### X09 — Conflicting transformations moraju biti detektovane.

### X10 — Unsupported transformations se preskaču.

### X11 — Skip mora biti evidentiran.

### X12 — Fail-safe je bolji od neprovjerene izmjene.

---

# Y. PIPELINE REDOSLIJED PRAVILA

### Y01 — Parse prije Analyze.

### Y02 — Analyze prije Classify.

### Y03 — Classify prije Optimize.

### Y04 — Optimize prije Finalize.

### Y05 — Finalize prije Noise insertion ako pipeline tako zahtijeva.

### Y06 — Export tek nakon validationa.

### Y07 — Validation prije certificationa.

### Y08 — Physical test dolazi nakon software validationa.

### Y09 — Nijedna faza ne smije preskakati obavezne gates.

### Y10 — Svaka faza mora imati jasno definisan input/output contract.

---

# Z. DATABASE PRAVILA

### Z01 — Database schema mora imati verziju.

### Z02 — Rule ID mora biti stabilan.

### Z03 — Svako pravilo mora imati status.

### Z04 — Svako pravilo mora imati provenance.

### Z05 — Pravilo mora imati datum/versiju nastanka.

### Z06 — Promjena pravila ne smije retroaktivno falsifikovati stare rezultate.

### Z07 — Golden dataset mora biti versioned.

### Z08 — Corpus build mora biti reproducibilan.

### Z09 — Duplicate data mora biti detektovan.

### Z10 — Conflicting rules moraju biti prijavljene.

### Z11 — Deprecated rule mora ostati istorijski zapisan.

### Z12 — Rule dependency graph mora biti dostupan.

---

# AA. CONFIDENCE PRAVILA

### AA01 — Confidence nije isto što i certainty.

### AA02 — Confidence mora imati definiciju.

### AA03 — Confidence mora imati izvor.

### AA04 — Jedan primjer ne daje maksimalni confidence.

### AA05 — Veći corpus povećava pouzdanost samo kada je evidence nezavisna.

### AA06 — Conflicting evidence smanjuje confidence.

### AA07 — Outlier ne smije automatski oboriti globalno pravilo.

### AA08 — Low-confidence rezultat se ne primjenjuje automatski.

### AA09 — Confidence mora biti sačuvan u output provenance.

### AA10 — Confidence threshold mora biti konfigurabilan.

---

# AB. RULE PRIORITY PRAVILA

Kada više pravila djeluje istovremeno:

### AB01 — Safety pravilo ima prednost nad optimization pravilom.

### AB02 — Original-preservation pravilo ima prednost nad enhancement pravilom.

### AB03 — Proven rule ima prednost nad experimental rule.

### AB04 — Track-specific rule ima prednost nad globalnim pravilom.

### AB05 — Instrument-specific rule ima prednost nad generic MIDI pravilom.

### AB06 — Factory-observed rule ima prednost nad proizvoljnim random behaviorom.

### AB07 — Explicit user rule ima prednost nad automatskim suggestionom.

### AB08 — Conflict mora biti prijavljen.

### AB09 — Silent override nije dozvoljen.

### AB10 — Final rule resolution mora biti logovana.

---

# AC. CONFLICT RULES

### AC01 — Dva konflikta se ne rješavaju proizvoljno.

### AC02 — Konflikt mora imati identitet.

### AC03 — Svako pravilo u konfliktu mora biti navedeno.

### AC04 — Priority engine odlučuje samo ako je priority dokazan.

### AC05 — U suprotnom rezultat je `REVIEW_REQUIRED`.

### AC06 — Agent ne smije „pretpostaviti“ pobjedničko pravilo.

### AC07 — Konflikti se čuvaju za kasniju analizu.

---

# AD. BEFORE / AFTER PRAVILA

### AD01 — Svaki output mora biti moguće uporediti sa inputom.

### AD02 — Broj nota mora biti uporediv.

### AD03 — Velocity distribution mora biti uporediva.

### AD04 — Timing distribution mora biti uporediva.

### AD05 — Polyphony mora biti uporediva.

### AD06 — Register mora biti uporediv.

### AD07 — DNA mora biti uporediv.

### AD08 — Event count mora biti uporediv.

### AD09 — Program/CC/SysEx promjene moraju biti uporedive.

### AD10 — Nijedna „quality improvement“ tvrdnja bez mjerljivog before/after dokaza.

---

# AE. VALIDATION PRAVILA

### AE01 — Structural validation
MIDI mora ostati validan.

### AE02 — Semantic validation
MIDI mora zadržati očekivanu muzičku strukturu.

### AE03 — Factory validation
Rezultat se poredi s Factory DNA.

### AE04 — Regression validation
Ni postojeće funkcije ne smiju biti pokvarene.

### AE05 — Protocol validation
Korg-specifične stvari moraju proći protocol check.

### AE06 — Output validation
Exportovani MIDI se ponovo parsira.

### AE07 — Numerical validation
Metrike se provjeravaju.

### AE08 — Determinism validation
Rezultat se ponavlja.

### AE09 — Evidence validation
Svaka važna tvrdnja mora imati dokaz.

### AE10 — Certification validation
Nema certificationa bez svih obaveznih gateova.

---

# AF. AGENTSKA PRAVILA

### AF01 — Agent prvo mora pročitati postojeću arhitekturu.

### AF02 — Agent ne smije odmah prepravljati kod.

### AF03 — Agent prvo mora pronaći postojeće pravilo.

### AF04 — Agent mora tražiti povezana pravila u drugim modulima.

### AF05 — Agent mora pratiti data flow.

### AF06 — Agent mora pratiti call graph.

### AF07 — Agent mora pratiti sve write operacije.

### AF08 — Agent mora pronaći postojeće testove.

### AF09 — Ako test ne postoji, agent mora ga predložiti ili implementirati.

### AF10 — Agent ne smije tvrdnju označiti kao dokazanu bez izvršenog dokaza.

### AF11 — Agent mora prijaviti nepoznato.

### AF12 — Agent ne smije „popuniti rupe“ pretpostavkom.

### AF13 — Agent mora dokumentovati posljedice izmjene.

### AF14 — Agent mora navesti koje module može pogoditi promjena.

### AF15 — Agent mora pokrenuti regression test nakon izmjene.

---

# AG. FORENZIČKA PRAVILA ZA .PY MODULe

### AG01 — Svaka funkcija koja piše MIDI mora biti pronađena.

### AG02 — Svaka funkcija koja mijenja velocity mora biti pronađena.

### AG03 — Svaka funkcija koja mijenja timing mora biti pronađena.

### AG04 — Svaka funkcija koja mijenja duration mora biti pronađena.

### AG05 — Svaka funkcija koja mijenja channel mora biti pronađena.

### AG06 — Svaka funkcija koja mijenja Program Change mora biti pronađena.

### AG07 — Svaka funkcija koja mijenja CC mora biti pronađena.

### AG08 — Svaka funkcija koja piše SysEx mora biti pronađena.

### AG09 — Svaki output writer mora biti auditiran.

### AG10 — Svaki hidden transformation path mora biti pronađen.

### AG11 — Dead code mora biti označen.

### AG12 — Duplicated rules mora biti označen.

### AG13 — Contradictory implementations mora biti označene.

---

# AH. RULE ENGINE PRAVILA

### AH01 — Pravilo mora imati jedinstveni ID.

### AH02 — Pravilo mora imati trigger.

### AH03 — Pravilo mora imati condition.

### AH04 — Pravilo mora imati action.

### AH05 — Pravilo mora imati priority.

### AH06 — Pravilo mora imati confidence.

### AH07 — Pravilo mora imati evidence level.

### AH08 — Pravilo mora imati test.

### AH09 — Pravilo mora imati owner/module.

### AH10 — Pravilo mora imati dependency.

Minimalni koncept:

`RULE → CONDITION → DECISION → ACTION → VALIDATION`

---

# AI. „MORA“, „SMIJE“, „NE SMIJE“ PRAVILA

Svako pravilo treba klasifikovati prema tipu.

### AI01 — MUST
Sistem obavezno mora nešto uraditi.

### AI02 — MUST NOT
Sistem nešto nikada ne smije uraditi.

### AI03 — SHOULD
Sistem to treba uraditi kada su uslovi ispunjeni.

### AI04 — SHOULD NOT
Sistem to uglavnom ne treba raditi.

### AI05 — MAY
Sistem može to uraditi.

### AI06 — PROPOSAL ONLY
Sistem smije samo predložiti.

### AI07 — HUMAN APPROVAL
Za izvršenje treba potvrda korisnika.

### AI08 — PHYSICAL VERIFICATION
Može se prihvatiti tek nakon PA800 testa.

---

# AJ. PRAVILA ZA „NE ZNAM“

Ovo je izuzetno važno.

### AJ01 — Unknown nije False.

### AJ02 — Unknown nije True.

### AJ03 — Unknown znači „nema dovoljno dokaza“.

### AJ04 — Unknown event se čuva.

### AJ05 — Unknown rule se ne primjenjuje automatski.

### AJ06 — Unknown result mora biti vidljiv u reportu.

### AJ07 — Agent mora imati pravo reći:
`INSUFFICIENT EVIDENCE`

---

# AK. PRAVILA ZA FACTORY EXCEPTIONS

### AK01 — Factory izuzetak se ne briše zato što je rijedak.

### AK02 — Rijetko ponašanje se registruje.

### AK03 — Izuzetak može postati posebno pravilo.

### AK04 — Exception rule ima uži scope.

### AK05 — Globalno pravilo ne smije uništiti lokalni exception.

### AK06 — Exception mora imati provenance.

---

# AL. PRAVILA ZA GOLDEN DATASET

### AL01 — Golden dataset je referentni dokazni skup.

### AL02 — Golden fajl ne mijenja se tokom normalnog rada.

### AL03 — Novi kandidat ulazi u golden dataset tek nakon validacije.

### AL04 — Golden dataset mora biti versioned.

### AL05 — Svaki golden entry ima provenance.

### AL06 — Golden rules ne smiju zavisiti od slučajnog outputa.

### AL07 — Regression mora koristiti golden dataset.

### AL08 — Dataset drift mora biti detektovan.

---

# AM. PRAVILA ZA STYLE SIMILARITY

### AM01 — Similarity nije identity.

### AM02 — Visoka sličnost ne znači isti Style.

### AM03 — Similarity mora imati metrike.

### AM04 — Rhythm similarity i harmonic similarity moraju biti odvojene.

### AM05 — Full similarity mora biti composite rezultat.

### AM06 — Similarity score mora imati confidence.

### AM07 — Najbliži Style nije automatski najbolji donor.

### AM08 — Donor Pattern mora proći compatibility test.

---

# AN. PRAVILA ZA STYLE TRANSFER

### AN01 — Ne prenositi Pattern bez role compatibility.

### AN02 — Ne prenositi guitar Pattern na Bass bez posebne transformacije.

### AN03 — Ne prenositi drum velocity grammar na melodic track.

### AN04 — Register mora biti provjeren.

### AN05 — Harmony mora biti provjerena.

### AN06 — Timing mora biti kompatibilan.

### AN07 — Density mora biti kompatibilna.

### AN08 — Articulation mora biti kompatibilna.

### AN09 — Transfer mora imati similarity evidence.

### AN10 — Transfer mora imati rollback.

---

# AO. PRAVILA ZA GENERISANJE

### AO01 — Generator ne smije generisati van definisanog prostora.

### AO02 — Factory grammar ima prednost.

### AO03 — Random generation mora biti kontrolisana.

### AO04 — Generator mora imati seed.

### AO05 — Generated Pattern dobija provenance.

### AO06 — Generated Pattern se ne smije predstaviti kao originalni Factory Pattern.

### AO07 — Synthetic data mora biti označena.

### AO08 — Generated Style mora imati authenticity score.

### AO09 — Generated articulation zahtijeva confidence.

### AO10 — Generated output mora proći isti validation pipeline kao ručno obrađen MIDI.

---

# AP. PRAVILA ZA QUALITY SCORE

### AP01 — Quality score mora imati definisane komponente.

### AP02 — Komponente moraju imati težine.

### AP03 — Težine moraju biti dokumentovane.

### AP04 — Score ne smije sakriti ozbiljan pojedinačni problem.

### AP05 — Technical PASS i Musical PASS nisu isto.

### AP06 — Factory similarity PASS nije isto što i audio quality PASS.

### AP07 — Jedan zbirni score ne smije zamijeniti detaljni report.

### AP08 — Score mora biti reproducibilan.

---

# AQ. PRAVILA ZA CERTIFICATION

### AQ01 — „Tests passed“ nije isto što i „physically validated“.

### AQ02 — Software PASS mora biti odvojen od Hardware PASS.

### AQ03 — Audio PASS mora biti odvojen od MIDI PASS.

### AQ04 — Human evaluation mora biti odvojena od automated score-a.

### AQ05 — Missing evidence mora ostati `NOT VERIFIED`.

### AQ06 — Certification ne smije pretpostaviti fizički rezultat.

### AQ07 — Certifikacija mora imati datum/verziju.

### AQ08 — Certifikacija mora imati evidence manifest.

---

# AR. GOLDEN MASTER PRAVILO

Nijedan novi modul, algoritam ili agent ne smije zaobići postojeća temeljna pravila samo zato što daje „bolji rezultat“.

Centralno pravilo sistema:

**PRESERVE → UNDERSTAND → PROVE → CHANGE → VALIDATE → CERTIFY**

---

# AS. NAJVIŠI NIVO PRAVILA

### AS01
**Ne mijenjaj ono što ne razumiješ.**

### AS02
**Ne tvrdi ono što nije dokazano.**

### AS03
**Ne koristi generičko MIDI pravilo tamo gdje Factory dokaz pokazuje drugačije ponašanje.**

### AS04
**Ne koristi Factory pretpostavku tamo gdje postoji samo jedan primjer.**

### AS05
**Ne žrtvuj originalno muzičko ponašanje zbog tehničke „čistoće“.**

### AS06
**Ne žrtvuj tehničku validnost zbog subjektivnog muzičkog dojma.**

### AS07
**Ne primjenjuj globalno pravilo kada postoji track/instrument/context specifično pravilo.**

### AS08
**Ne dozvoli tihe transformacije.**

### AS09
**Ne dozvoli neobjašnjive transformacije.**

### AS10
**Svaka automatska odluka mora biti objašnjiva.**

### AS11
**Svaki kritični write mora biti dokaziv.**

### AS12
**Nepoznat slučaj mora završiti u REVIEW, a ne u pretpostavci.**

---

# AT. STANDARD ZA AGENTA KOJEM SE DAJE JEDNO PRAVILO

Kada agentu pošalješ, na primjer:

**„Istraži pravilo F13 — velocity write audit.“**

agent treba utvrditi:

**1. Gdje se velocity piše?**  
**2. Koji moduli mogu promijeniti velocity?**  
**3. Koji pozivi vode do tih write operacija?**  
**4. Koja pravila određuju novu vrijednost?**  
**5. Da li postoji test?**  
**6. Da li test pokriva svaki write path?**  
**7. Da li postoji hidden write path?**  
**8. Da li output zaista mijenja samo očekivane evente?**  
**9. Da li je rezultat deterministic?**  
**10. Da li se originalni velocity contour očuvao?**  
**11. Koji je evidence level?**  
**12. Koji je finalni status pravila?**

---

# AU. PREPORUČENI FORMAT ZA SVAKO IMPLEMENTIRANO PRAVILO

```text
RULE_ID:
TITLE:

TYPE:
MUST / MUST_NOT / SHOULD / SHOULD_NOT / MAY / PROPOSAL / HUMAN_APPROVAL

STATUS:
PROVEN / PARTIALLY_PROVEN / FACTORY_OBSERVED / INFERRED /
EXPERIMENTAL / UNVERIFIED / REJECTED

SCOPE:
GLOBAL / TRACK / CHANNEL / INSTRUMENT / PATTERN / EVENT

TRIGGER:

PRECONDITION:

RULE:

ACTION:

PRIORITY:

CONFIDENCE:

EVIDENCE:

SOURCE:

IMPLEMENTATION:

TESTS:

REGRESSION:

BEFORE_METRICS:

AFTER_METRICS:

CONFLICTS:

DEPENDENCIES:

LIMITATIONS:

ROLLBACK:

FINAL_DECISION:
```

---

# AV. KLJUČNA IDEJA

Ovaj projekat ne bi trebao imati samo:

**CODE**

nego:

**CODE + RULES + EVIDENCE + DATA + TESTS + PROVENANCE**

A zatim:

**FACTORY OBSERVATION → RULE → IMPLEMENTATION → TEST → RESULT → EVIDENCE**

Tako agent više ne dobija zadatak:

> „Napravi bolji velocity.“

nego:

> **„Istraži pravilo F13, pronađi svaki velocity write path, dokaži trenutno ponašanje, uporedi ga sa Factory evidence bazom, implementiraj samo dokazive korekcije, pokreni regression i vrati status pravila.“**

To je puno jača arhitektura za ovaj projekat, jer ćeš moći uzimati **jedno pravilo po jedno**, a vremenom napraviti stvarni **KORG PA800 Rule Intelligence System**, umjesto hrpe nepovezanih heuristika.