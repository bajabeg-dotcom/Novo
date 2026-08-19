# Puna forenzika — DNA korpus i baza

Datum: 19.08.2026.
Predmet: `DNA.zip` (3.393 MIDI) i `data/pa800-enhancer.db` (37 MB, schema 5)

Alati (u ovom repou): `tools/forensics/smf_probe.py`, `corpus_forensics.py`, `db_forensics.py`
Sirovi izlazi: `forensics/corpus-forensics.json`, `forensics/database-forensics.json`

---

## Metoda

Forenzika **ne koristi kod projekta**. Napisan je nezavisan SMF čitač (`smf_probe.py`) od nule — vlastiti VLQ dekoder, running status, chunk walker. Razlog: alat koji provjerava ne smije dijeliti pretpostavke sa sistemom koji se provjerava. Kad se oba slože, nalaz je jak; kad se ne slože, to je samo po sebi nalaz.

Svi brojevi ispod dobijeni su iz stvarnih bajtova, ne iz dokumentacije.

---

## 1. Forenzika korpusa

### 1.1 Integritet — bez ijednog oštećenja

| Metrika | Rezultat |
|---|---|
| Skenirano | **3.393** |
| Parsirano bez greške | **3.393 (100 %)** |
| Greške parsiranja | **0** |
| Fajlova sa strukturnim upozorenjem | **0** |
| Jedinstvenih SHA-256 | 3.368 |
| Grupa duplikata | 25 (50 fajlova) |
| Nota (Note On, vel>0) | **3.705.678** |

Nijedan fajl nema: prazan sadržaj, nedostajući End-of-Track, bajtove iza zadnjeg chunka, SMPTE vremensku bazu, Format 2, kanal van 1–16, niti velocity zaglavljen na 127.

**Ocjena: korpus je čist.** Ovo je neuobičajeno dobar rezultat za 3.393 fajla iz različitih izvora.

### 1.2 Dva korpusa su mjerljivo različita

| | Gold DNA | Factory (Workspace_Styles) |
|---|---|---|
| Fajlova | 182 (181 jedinstven) | 3.211 (3.187 jedinstvenih) |
| Nota | 2.272.811 | 1.432.867 |
| Format | 180× SMF 0, 2× SMF 1 | 3.211× SMF 1 |
| PPQ | 384 (178), 120 (2), 192 (1), 480 (1) | **192 (svi)** |
| Trackova prosječno | 1,06 | 20,25 |
| **Velocity prosjek** | **101,48** | **86,09** |
| Velocity p10–p90 | 85,2 – 115,3 | 68,6 – 102,6 |
| SysEx | 180 fajlova | **0** |
| Pitch bend | 171 fajlova | 661 fajlova |
| Kanali | svih 1–16 | 2, 9–16 |

Ovo **potvrđuje ključnu projektnu premisu**: Gold je izražajniji (velocity +15,4), Factory je strukturiran (20 trackova, jedinstven PPQ). Podjela „Factory za strukturu, Gold za izvedbu" ima mjerljivu osnovu.

Zapažanje: Factory ne koristi kanale 1–8 osim kanala 2. Kanali 9–16 su Pa800 style konvencija (Drum, Perc, Bass, Acc1–5).

### 1.3 Muzički profil

- **Tempo:** 46–215 BPM, prosjek 112,7 (3.682 tempo događaja)
- **Metri:** 4/4 (3.256), 2/4 (326), 3/4 (251), 6/8 (84), 6/4 (31), 7/8 (12), 9/8 (2), 9/4 (6), 8/8 (8), 1/4 (1)
- **Programi:** 113 različitih GM programa od 128
- **Kontroleri:** CC11 expression (73.341), CC1 modulation (68.640), CC0 bank (37.141), CC32 (37.030), CC7 volume (35.232), CC22 (23.431)

**Bank pokrivenost — vrijedan nalaz:**

| CC0 | Fajlova | Značenje |
|---|---|---|
| **120** | 3.366 | Pa800 Drum Kit banka |
| **121** | 3.100 | Pa800 Factory Sound banka |
| 127 | 45 | — |
| 0 | 8 | GM default |

CC32 ima **46 različitih vrijednosti** (0–34, 49–51, 64–66, 68–69, 71, 77, 80, 83). Korpus dakle sadrži stvarne Pa800 bank adrese — nisu izmišljene. Ovo je direktno upotrebljivo za popunjavanje profila (Faza C plana revizije).

### 1.4 Anomalija: 523 fajla sa neuparenim Note On

523 fajla (513 Factory, 10 Gold) imaju više Note On nego Note Off — ukupno **10.367 viška**, tj. 0,28 % svih nota.

To su „viseće" note bez pripadajućeg Note Off. U pattern-baziranom Factory materijalu očekivano je da nota traje preko granice segmenta, ali ostaje činjenica da fajl nije samodostatan.

### 1.5 Duplikati: 25 grupa

Svi su unutar Factory korpusa i gotovo svi su **završni segmenti** (`End1/2/3`) koje dijele srodni stilovi:

```
Half Beat_End2      == Modern Beat_End2
Fast Big Band 2_End1 == Serenade Band_End1
Jazz Funk_End3      == Motown Shuffle 1_End3
Oberkr_ Waltz 1_End3 == Oberkr_ Waltz 2_End3
```

Nije greška — Korg je dijelio isti ending među varijantama stila. Ali statistički blago pretežu te obrasce, pa ih treba označiti.

---

## 2. Forenzika baze

### 2.1 Integritet — besprijekoran

| Provjera | Rezultat |
|---|---|
| `PRAGMA integrity_check` | **ok** |
| `PRAGMA foreign_key_check` | **0 povreda** |
| Siročad u `midi_fingerprint_roles` | **0** |
| Siročad u `midi_fingerprint_sources` | **0** |
| Otisci bez ijedne uloge | **0** |
| Uloge sa `note_count <= 0` | **0** |
| Nevažeće oznake uloga | **0** |
| Kodiranje | UTF-8 |

Shema: 16 tabela, 11 indeksa, FK ograničenja i CHECK-ovi na svim enum poljima (`role`, `corpus_kind`, `split`, `evidence_status`, `confidence BETWEEN 0 AND 1`). **Shema je projektovana ozbiljno** — ne kao ad-hoc dump.

### 2.2 Nalaz: 36 % baze je mrtav prostor

```
page_count     = 9.121
freelist_count = 3.277   (35,9 %)
page_size      = 4.096
```

Baza od 37,4 MB nosi ~13,4 MB oslobođenih stranica. `VACUUM` bi je smanjio na ~24 MB bez gubitka podataka. Uzrok je vjerovatno ponovljeni `dna-learn` preko iste datoteke.

Ovo nije kvar, ali `artifact-manifest.json` fiksira SHA-256 baš tog fajla — **`VACUUM` mijenja hash** i zahtijeva ažuriranje manifesta. Treba uraditi jednom, kontrolisano.

### 2.3 Kvalitet feature vektora — odličan

Uzorak 4.000 od 14.369 uloga:

| Provjera | Rezultat |
|---|---|
| Dimenzija vektora | **48 kod svih** (konzistentno) |
| NaN vrijednosti | **0** |
| Inf vrijednosti | **0** |
| Neispravan JSON | **0** |
| Konstantne dimenzije (beskorisne) | **0** |
| `note_count` neslaganje vektor↔kolona | **0** |

19 feature ključeva: `density_per_quarter`, `pitch_mean/std/min/max`, `velocity_mean/std`, `duration_mean/std_quarters`, `short_ratio`, `chord_ratio`, `syncopation_ratio`, `repetition_ratio`, `trill_ratio`, `onset_grid`, `pitch_classes`, `drum_classes`, `note_count`, `role`.

Nijedna dimenzija nije konstantna — znači svih 48 nosi informaciju. Za ML sloj je ovo zdrava osnova.

### 2.4 Pokrivenost uloga

| Uloga | Izvora | Nota |
|---|---|---|
| drums | 3.310 | 724.096 |
| solo | 2.987 | 319.867 |
| bass | 2.899 | 212.311 |
| accompaniment | 2.599 | 1.371.650 |
| guitar | 2.574 | 1.025.585 |

Raspodjela po broju uloga: 5 uloga → 2.087 izvora; 4 → 712; 3 → 195; 2 → 127; **1 uloga → 247 izvora**.

Onih 247 sa jednom ulogom su gotovo sigurno Factory drum-only segmenti. Nije greška, ali su slabi za višeulogno učenje.

### 2.5 Unakrsna provjera baza ↔ korpus

| Provjera | Rezultat |
|---|---|
| Jedinstvenih u korpusu | 3.368 |
| Otisaka u bazi | 3.368 |
| U korpusu a ne u bazi | **0** |
| U bazi a ne u korpusu | **0** |
| Neslaganje PPQ | **0 / 3.368** |
| Neslaganje `end_tick` | **0 / 3.368** |

**Svaki fajl je zastupljen, nijedan izmišljen, sve vremenske baze tačne.** Provenijencija je potpuna: 3.393 `source_locator` zapisa pokriva svih 25 duplikatnih grupa (isti otisak, više lokatora).

---

## 3. Glavni nalaz: 36.525 nota ne stiže u bazu

Nezavisni parser broji **3.690.034** nota u jedinstvenim fajlovima. Baza sadrži **3.653.509**.

**Razlika: 36.525 nota (0,99 %) u 405 Factory fajlova. Gold korpus nije pogođen.**

### Uzrok — dokazan, ne pretpostavljen

`pa800_enhancer/dna.py:classify_note_roles()` radi nad `pair_notes()`. Taj uparivač (`analysis/notes.py:72`) grupiše aktivne note po ključu **`(channel, note)` globalno preko svih trackova**, FIFO strategijom. Note On koji nikad ne dobije Note Off ostaje u redu i **nikad ne postane `Note`** — pa ne uđe ni u jednu ulogu.

Dokaz u tri koraka:

1. **Direktna reprodukcija.** Za `Pop Shuffle 3_Var1.mid`: `pair_notes()` vraća 21.461 notu i 8.475 neuparenih događaja. Baza za taj fajl ima **tačno 21.461**.

2. **Nezavisna reimplementacija.** Napisao sam vlastiti FIFO uparivač po `(channel, note)`. Na svih 405 pogođenih fajlova reprodukuje broj iz baze **405/405 tačno**.

3. **Brojevi se zatvaraju.** Zbir visećih nota u ta 404 fajla = **36.525** — identičan ukupnom manjku. Bez ostatka.

```
Note On u korpusu          3.690.034
− viseće note (bez Note Off)   36.525
= note u bazi               3.653.509   ✔
```

### Zašto baš Factory

Factory su pattern segmenti gdje nota često „prelazi" granicu takta/segmenta i Note Off pada izvan izrezanog dijela. Gold su cjelovite izvedbe pa su note zatvorene — otud 0 gubitka.

### Ozbiljnost: niska, ali sistematska

0,99 % je malo i ne remeti statistiku. Ali:

- gubitak je **tih** — nigdje se ne prijavljuje
- **neravnomjeran** je: pogađa samo Factory, i to nejednako (najgori fajl gubi 5.034 od 26.495 nota = **19 %**)
- taj fajl doprinosi profilima sa petinom manje materijala nego što stvarno ima

**Preporuka:** ne mijenjati `pair_notes` (uparivanje je ispravno po SMF semantici), nego:
1. `dna-learn` treba **prijaviti** broj neuparenih po fajlu,
2. `dna-audit` treba prikazati ukupan `unpaired_note_on`,
3. razmotriti opciju da viseća nota dobije sintetički kraj na `end_tick` — **iza eksplicitne zastavice**, nikad podrazumijevano.

---

## 4. Verifikacija artefakata

Svih 5 iz `artifact-manifest.json` prolazi SHA-256 i provjeru veličine: **5/5 OK**.

| Status | Broj |
|---|---|
| `candidate` | 4 |
| `experimental` | 1 (GRU model) |

Nijedan nije `verified` — dosljedno sa činjenicom da hardverske potvrde nema (`hardware_tests: 0`).

---

## 5. Zbirna ocjena

| Oblast | Ocjena | Obrazloženje |
|---|---|---|
| Integritet korpusa | **odličan** | 3.393/3.393 parsira, 0 upozorenja |
| Integritet baze | **odličan** | integrity ok, 0 FK povreda, 0 siročadi |
| Provenijencija | **odlična** | 3.368/3.368 hash poklapanje, 0 izmišljenih |
| Kvalitet vektora | **odličan** | 48 dim, 0 NaN, 0 konstanti |
| Dizajn sheme | **vrlo dobar** | FK, CHECK, indeksi, dedup preko `source_sha256` |
| Potpunost nota | **dobar uz manu** | 0,99 % tiho otpada u 405 fajlova |
| Efikasnost skladišta | **slab** | 36 % freelist, treba `VACUUM` |
| Iskorištenost sheme | **slaba** | 9 od 16 tabela prazno |

### Nalazi po prioritetu

| # | Nalaz | Prioritet | Radnja |
|---|---|---|---|
| 1 | 36.525 nota (0,99 %) tiho se gubi u 405 fajlova | **P1** | prijaviti u `dna-learn`/`dna-audit`; opcioni sintetički Note Off iza zastavice |
| 2 | 36 % baze je freelist (~13 MB) | **P2** | kontrolisan `VACUUM` + ažurirati manifest |
| 3 | 9 praznih schema-5 tabela | **P1** | materijalizovati (Faza D plana) |
| 4 | 523 fajla sa 10.367 visećih nota | P2 | označiti u manifestu kao poznatu osobinu korpusa |
| 5 | 25 duplikatnih grupa (Korg dijeli ending-e) | P2 | označiti, ne brisati |
| 6 | 247 izvora sa samo 1 ulogom | P3 | isključiti iz višeulognog treninga |
| 7 | CC0 120/121 + 46 CC32 vrijednosti u korpusu | **prilika** | direktan izvor za popunjavanje profila (Faza C) |

### Šta forenzika mijenja u planu revizije

- **Faza C dobija drugi izvor.** Uz K01 registar (1.071 adresa iz priručnika), sam korpus nosi stvarne CC0/CC32 adrese. Ukrštanje ta dva daje jaču evidenciju nego bilo koji pojedinačno.
- **Faza D dobija konkretan test.** Reproducibilnost se sad može provjeriti egzaktno: rebuild mora dati 3.368 otisaka, 14.369 uloga, 3.653.509 nota. Svako odstupanje je blocker.
- **Faza B dobija golden slučajeve.** 405 fajlova sa gubitkom i 25 duplikatnih grupa su idealni regresijski fiksni slučajevi.

---

## 6. Zaključak

Korpus i baza su u **znatno boljem stanju nego što je dokumentacija tvrdila**. Nema oštećenih fajlova, nema izmišljenih zapisa, nema povreda integriteta, nema NaN-ova. Provenijencija je potpuna i provjerljiva do bajta.

Jedina stvarna mana je **tihi gubitak 0,99 % nota** pri uparivanju — sistematski, ograničen na Factory, i sada u potpunosti objašnjen i mjerljiv. Nije greška u uparivanju nego u tome što se gubitak nigdje ne prijavljuje.

Sve tvrdnje u ovom dokumentu su reproducibilne:

```bash
python3 tools/forensics/corpus_forensics.py <korpus> --json forensics/corpus-forensics.json
python3 tools/forensics/db_forensics.py <baza> \
    --corpus-records <records.json> --project-root <projekat> \
    --json forensics/database-forensics.json
```
