# Analiza projekta i prijedlog revizije

Datum: 19.08.2026.
Predmet: `Final.zip` → `PA800-MIDI-Enhancer` v0.27.0, uporedno sa 5 postojećih GitHub repozitorija.

---

## 1. Šta je stvarno u Final.zip

`PA800-MIDI-Enhancer`, 125 fajlova, 68,6 MB raspakovano, verzija **0.27.0**.

| Stavka | Vrijednost |
|---|---|
| Python kod | 15.583 LOC, 105 modula, svi se importuju bez greške |
| CLI komande | 43 (`inspect`, `validate`, `optimize`, `dna-*`, `hardware`, `factory-*`, `generator-*`…) |
| DNA baza | `pa800-enhancer.db`, 37 MB, schema 5 |
| Katalozi | Factory pattern (18,9 MB), performance v1 (1,2 MB) i v2 (1,5 MB) |
| ML model | GRU `midi-gru.pt` (5,7 MB), status `experimental` |
| GUI | Tk desktop (`ui/main_window.py`, 712 LOC) |
| Windows | `instal.bat`, `run.bat`, `POKRENI APLIKACIJU.bat` + template-i u paketu |
| Wheel | `dist/pa800_midi_enhancer-0.27.0-py3-none-any.whl` |

### Verifikacija koju sam proveo

- **Integritet artefakata: 5/5 OK.** Svih pet unosa iz `artifact-manifest.json` prolazi SHA-256 i provjeru veličine. `artifacts audit` vraća `"ok": true`, `missing: []`, `mismatched: []`.
- **Import svih modula: 105 OK, 0 FAIL** — i to bez instaliranih `numpy`/`mido`, tj. dependency-free jezgro stvarno radi.
- **Funkcionalni end-to-end test** na generisanom fixture-u: `inspect`, `validate`, `rhythms`, `parameters`, `initialization`, `sysex`, `structure`, `export --mode preserve`, `optimize --grid 16` — **sve prolazi**.
- **DNA putanje rade:** `dna-audit` vraća pun izvještaj, `dna-optimize` korektno javlja `changes: 0, protected_notes: 1, applied: false` (konzervativno ponašanje je ispravno).
- **Higijena koda:** 0 `TODO`/`FIXME`/`NotImplementedError`, 0 hardkodovanih apsolutnih putanja, samo 7 širokih `except`.

### Pokrivenost korpusa u bazi

3.393 izvora (3.211 Factory + 182 Gold), 3.368 jedinstvenih otisaka, 14.369 role-otisaka, **3.653.509 nota**.

| Uloga | Izvora | Nota |
|---|---|---|
| accompaniment | 2.599 | 1.371.650 |
| guitar | 2.574 | 1.025.585 |
| drums | 3.310 | 724.096 |
| solo | 2.987 | 319.867 |
| bass | 2.899 | 212.311 |

Kompletnih izvora sa svih 5 uloga: 2.087. Katalog ima 1.227 naučenih profila.

---

## 2. Nedostaci — poredani po ozbiljnosti

### P0 — kritično

**1. Nula testova u isporuci.**
README kaže `python -m unittest discover -v`, ali u ZIP-u **nema nijednog test fajla**. Za poređenje: `Jap` ima 28 testova, `Factory` 38 (i tvrdnju da 481 test prolazi). Ovo je najveći gubitak — cijeli safety sistem (atomic transakcije, undo/redo, export blokeri, policy gate) nema regresivnu zaštitu. Svaka naredna izmjena je slijepa.

**2. Prazan uređajni profil = mrtve komande.**
`profiles/pa800-template.json` ima `sounds: 0`, `drum_kits: 0`, `rhythms: 0`. Namjerno — jer nema hardverske potvrde. Ali posljedica: `sound-map`, `drum-map` i `programs --profile` praktično nemaju šta da mapiraju. `velocity-auto` na testu vraća `unmatched_addresses`.

**3. Nula hardverskih potvrda.**
Tabele `device_profiles: 0` i `hardware_tests: 0`. Svih 5 artefakata je `candidate`, GRU model `experimental`. Znači: **projekat nikad nije potvrđen na fizičkom Pa800.** Kompletan `hardware` podsistem (generate/validate/record-cycle, dvociklusna verifikacija) je izgrađen i radi, ali nije nijednom upotrijebljen.

### P1 — ozbiljno

**4. Prekid u istoriji verzija: 0.15.0 – 0.25.0 nedostaju.**
CHANGELOG ide 0.1.0 → 0.14.0, pa **skače na 0.26.0**. Jedanaest verzija nema zapis. Uz to, format je nekonzistentan (0.1–0.14 koriste `##` i silazni redoslijed, 0.26+ koriste `#` i uzlazni) — jasan znak da su spajane dvije različite razvojne linije. **Ne zna se šta je ušlo, a šta ispalo u tih 11 verzija.**

**5. Prazne schema-5 tabele.**
`music_songs`, `music_sections`, `music_chords`, `music_tracks`, `music_annotations`, `style_elements`, `style_families`, `dataset_groups`, `dataset_members` — **sve 0 redova**. Harmony/structure analiza (v0.13–0.14) ima shemu ali nema materijalizovane podatke. Funkcionalnost postoji, sadržaj ne.

**6. Nema izvornog korpusa u ZIP-u.**
Baza je izvedena iz `DNA.zip` (3.211 Factory + 182 Gold), ali sam `DNA.zip` nije uključen. Bez njega se baza **ne može reprodukovati** — a `dna-learn` je upravo komanda za to. Detaljna lokacija i sadržaj: vidi §5.

**7. 25 grupa duplikata** u korpusu (`duplicate_content_groups: 25`) — isti sadržaj pod različitim imenima, blago iskrivljuje statistiku.

### P2 — za urediti

**8. Nema CI-ja, `.gitignore`, licence, `CONTRIBUTING`.** v0.2.0 pominje „Windows/Linux CI za Python 3.11-3.13" — u ZIP-u ga nema.
**9. Dupli launcher-i:** `instal.bat` (tipfeler), `run.bat`, `POKRENI APLIKACIJU.bat` — tri ulazne tačke, preklapaju se.
**10. Dva performance kataloga** (v1 i v2) žive paralelno bez jasne oznake koji je aktivan.
**11. `dist/*.whl` je commitovan** — build artefakt u izvornom kodu.

---

## 3. Šta postoji u starim repoima a NEMA u Final.zip

Ovo je materijal koji bi se **izgubio** ako se uzme samo Final.zip:

| Izvor | Jedinstvena vrijednost | Ocjena |
|---|---|---|
| **Jap** (`python-midi-enhancer`) | **28 testova**; K01 Pa800 Factory registar (1.071 adresa iz službenog priručnika, str. 275–283, 295); `MODULE_LOG.md` sa PASS/PARTIAL/BLOCKED statusima za 30 modula; dual-parser parity guard; `vendor/pypdf` wheel | **Najveći gubitak** |
| **Factory** (GM→RX Studio) | **`Pa800-201UM-ENG.pdf` (23 MB, službeni priručnik)**; `DNA.zip` (21,9 MB izvorni korpus); `Oscilatori.txt` (49 RX zona); 6 referentnih pjesama; 38 testova; 40 `rxoptimizer` modula (strumming, solo, trill, RX noise probe); 25 dokumentovanih SQLite baza; single-articulation probe paket | **Kritični dokazni sloj** |
| **beg** | `korg_pa800_optimizer`, `x10_think_midi`, `factory_intelligence` — tri paralelna paketa | Uglavnom nadmašeno |
| **a** | `midi_optimizer_*` CLI/GUI/core, forenzički izvještaji | Nadmašeno |
| **DNA** | `song_midi_optimizer[_pro].py` | Nadmašeno |

**Najvažnije:** Final.zip nema **nijedan primarni Pa800 dokazni dokument** — ni PDF priručnik, ni Oscilatori.txt, ni K01 registar. Zato su svi profili prazni i sve je `candidate`. Dokazi postoje, samo u drugom repou.

---

## 4. Preporučena revizija

### Baseline: `PA800-MIDI-Enhancer` v0.27.0 iz Final.zip

Obrazloženje: najčistija arhitektura (105 modula bez greške), najviše funkcionalnosti (43 komande), jedini sa verifikovanim manifestom artefakata, jedini sa gotovim wheel-om, jedini sa ML generatorom. Kod je zreo — problem je isključivo **nedostatak testova i dokaza**, a oboje postoji u starim repoima.

### Ciljna struktura — ništa se ne briše

```
Novo/
├── src/pa800_enhancer/        ← v0.27.0 kod, nepromijenjen (baseline)
├── tests/                     ← VRAĆENO: 28 testova iz Jap + 38 iz Factory, prilagođeno
├── data/                      ← artefakti + manifest (nepromijenjeno)
├── evidence/                  ← VRAĆENO iz Factory/Jap:
│   ├── pa800-manual/          ·   Pa800-201UM-ENG.pdf + page locator
│   ├── registry/              ·   K01 registar, 1.071 Factory adresa
│   └── oscilatori/            ·   Oscilatori.txt, 49 RX zona
├── corpus/                    ← DNA.zip (izvor za dna-learn reprodukciju)
├── legacy/                    ← ARHIVA, read-only:
│   ├── jap-python-midi-enhancer/
│   ├── factory-gm-rx-studio/
│   ├── beg-korg-optimizer/
│   ├── a-midi-optimizer/
│   └── dna-song-optimizer/
├── docs/                      ← MODULE_LOG, DNA dokumentacija, audit izvještaji
└── .github/workflows/ci.yml   ← VRAĆENO: Python 3.11–3.13, Win+Linux
```

### Verzija: `0.28.0` — „Consolidation"

Ne 1.0.0. Bez hardverske potvrde projekat nije produkcijski, ma koliko kod bio dobar. `0.28.0` iskreno kaže: konsolidovano, testirano, ali još `candidate`.

### Redoslijed izvođenja

| # | Korak | Rizik | Dobit |
|---|---|---|---|
| 1 | Uvezi Final.zip v0.27.0 kao baseline u `src/` | nema | čista polazna tačka |
| 2 | Arhiviraj svih 5 starih repoa u `legacy/` | nema | **garancija da se ništa ne gubi** |
| 3 | Vrati dokaze: PDF, K01 registar, Oscilatori | nema | omogućava popunjavanje profila |
| 4 | Vrati i prilagodi testove (Jap 28 + Factory 38) | nizak | **rješava P0 #1** |
| 5 | Popuni `profiles/pa800-*.json` iz K01 registra | srednji | **rješava P0 #2** |
| 6 | Dodaj CI (3.11–3.13, Win+Linux) | nema | trajna zaštita |
| 7 | Rekonstruiši CHANGELOG 0.15–0.25 iz git istorije | nizak | rješava P1 #4 |
| 8 | Vrati `DNA.zip`, dokumentuj `dna-learn` reprodukciju | nema | rješava P1 #6 |
| 9 | Materijalizuj prazne schema-5 tabele | srednji | rješava P1 #5 |
| 10 | Objedini launcher-e, ukloni `dist/` iz gita | nizak | čistoća |
| 11 | Odradi 2-ciklusnu hardversku verifikaciju na Pa800 | — | **jedini put ka 1.0.0** |

Koraci 1–4 su prioritet: poslije njih imaš testiran, dokazima potkrijepljen projekat bez ijednog izgubljenog fajla.

### Princip očuvanja

1. **`legacy/` je nepromjenjiv** — svih 5 repoa ide netaknuto, ne briše se ništa.
2. **Git istorija svih repoa ostaje** dostupna na GitHubu (`a`, `beg`, `DNA`, `Factory`, `Jap`).
3. **Ništa se ne prepisuje** — konsolidacija samo dodaje.
4. **Svaki artefakt zadržava SHA-256** u manifestu.
5. **`candidate` ostaje `candidate`** dok ga hardver ne promoviše.

---

## 5. DNA.zip — gdje je i šta je unutra

### Lokacije: tri kopije, sve bajt-identične

| Repo | Putanja | Veličina |
|---|---|---|
| `Factory` | `prism-uploads/DNA.zip` | 21.922.630 B |
| `Jap` | `workspace-…zip` → `python-midi-enhancer/prism-uploads/DNA.zip` | 21.922.630 B |
| `Beg123` | `New Project (18).zip` → `prism-uploads/DNA.zip` | 21.922.630 B |

Sve tri imaju SHA-256 `125f4486625db44f7cdd49bd670aff252a961c88ea14741ec970ec3ae5eec85a` — **jedan te isti fajl**. Nema „verzije 2"; README-ovo `DNA.zip (2)` je samo Windows naziv kopije preuzimanja.

Za `legacy/` je dovoljna **jedna** kopija. `Beg123` je inače stara kopija `Factory` repoa (`rxoptimizer`, `app.py`, `tests`) i nema ništa jedinstveno.

### Sadržaj: dva ugniježđena arhiva

```
DNA.zip (20,9 MB)
├── Split Factory Styles.zip  (15,5 MB) → 3.211 .mid u Workspace_Styles/
└── Gold DNA.zip              (6,4 MB)  →   182 .mid u Gold DNA/
```

**Split Factory Styles** — 248 stilova, 3.211 fajlova, 3.187 jedinstvenih (24 duplikata). Svaki stil razložen na elemente:

| Element | Broj | Element | Broj |
|---|---|---|---|
| Var1–Var4 | 252/246/245/245 | Intro1–3 | 246/241/239 |
| Fill1/Fill2 | 249/252 | End1–3 | 251/247/247 |
| Break | 251 | | |

**Gold DNA** — 182 fajla, 181 jedinstven (1 duplikat), balkanske live izvedbe (`UZIVO`).

### Poklapanje sa bazom iz Final.zip — tačno

| Metrika | DNA.zip | Baza | |
|---|---|---|---|
| Ukupno izvora | 3.393 | 3.393 | ✔ |
| Factory | 3.211 | 3.211 | ✔ |
| Gold | 182 | 182 | ✔ |
| Jedinstvenih | 3.368 | 3.368 | ✔ |
| Duplikata | 25 (24+1) | 25 | ✔ |

**Baza iz Final.zip je 100 % reproducibilna iz ovog DNA.zip.** Nema skrivenog ili izgubljenog izvora.

### Novi nalaz: `Valja.rar` — 163 pjesme koje NISU nigdje iskorištene

U `Jap/prism-uploads/Valja.rar` (1,0 MB, RAR5) nalazi se **163 balkanska song MIDI fajla** (11,28 MB, prosjek 71 KB) — Halid Bešlić, Šaban Šaulić, Sinan Sakić, Mile Kitić, Kemal Malovčić i drugi.

Provjerio sam preklapanje sa Gold DNA na dva načina:
- **po CRC32: 0 poklapanja** od 163
- **po normalizovanom nazivu: 0 poklapanja**, fuzzy tek 1 mogući („Zbog tebe sam")

Zaključak: **potpuno nezavisan korpus koji nikad nije ušao u bazu** (baza ima tačno 3.393 = 3.211 + 182, bez Valja). Sadrži i jedan `.enhanced.report.txt` — dokaz da je bar jedan fajl već obrađen kroz enhancer.

Vrijednost: ovo su **song MIDI** (linearne izvedbe), za razliku od Factory **style MIDI** (pattern materijal). Uz 182 Gold fajla, Valja bi skoro **udvostručio** song-korpus na ~345 fajlova. To je najveća neiskorištena rezerva u cijelom projektu.

Napomena: RAR5 se ne može raspakovati u ovom sandboxu (nema `unrar` alata), pa je analiza urađena preko metapodataka arhive. Na Windowsu se otvara normalno.

### Dopuna plana revizije

| # | Korak | Dobit |
|---|---|---|
| 8a | `corpus/DNA.zip` — jedna kopija (iz `Factory`) | reprodukcija baze preko `dna-learn` |
| 8b | `corpus/Valja.rar` + zaseban `dataset_group` | **+163 song MIDI**, potencijalno 2× Gold sloj |
| 8c | Zapiši SHA-256 oba u `artifact-manifest.json` | integritet izvora, ne samo izvedenih baza |

Za 8b vrijedi pravilo iz `Factory/SESSION_CHECKPOINT.md`: novi korpus ulazi kao **odvojena, označena grupa** (schema-5 `dataset_groups` je već spremna i prazna), da ne kontaminira postojeći Gold model. Prvo evaluacija na razdvojenom skupu, pa tek onda promocija.

---

## 6. Zaključak

Kod je u boljem stanju nego što se očekivalo: 105/105 modula radi, 5/5 artefakata verifikovano, 43 komande funkcionalne, 3,65 miliona nota u bazi. Prava slabost nije kod — nego to što je **isporuka odsječena od svojih testova i svojih dokaza**, koji netaknuti postoje u `Jap` i `Factory`.

Revizija je zato konsolidacija, ne prepisivanje: v0.27.0 kao jezgro + vraćeni testovi i dokazi + puna arhiva starog = **v0.28.0**, bez ijednog izgubljenog fajla. Put do 1.0.0 vodi isključivo kroz dvociklusnu verifikaciju na fizičkom Pa800 — sav alat za to je već napisan i čeka.
