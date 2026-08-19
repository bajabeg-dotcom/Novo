# Plan pune revizije — PA800-MIDI-Enhancer

Datum: 19.08.2026.
Baseline: `PA800-MIDI-Enhancer` v0.27.0 (iz `Final.zip`)
Cilj: **v0.28.0 „Consolidation"** — konsolidovan, testiran i dokazima potkrijepljen projekat, bez ijednog izgubljenog fajla.

Analiza na kojoj plan počiva: `ANALIZA_I_REVIZIJA.md`.

---

## 0. Nalaz koji mijenja pristup

Prije pisanja plana provjerio sam ključnu pretpostavku iz prethodne analize — da se stari testovi mogu „vratiti". **Ta pretpostavka je netačna** i plan je zbog toga prepravljen.

Uporedio sam module koje stari testovi importuju sa modulima koji postoje u v0.27.0:

| Izvor | Testova | LOC | Cilja module | Postoji u v0.27.0 |
|---|---|---|---|---|
| `Jap` | 28 | 4.344 | `style_loader`, `change_plan`, `change_engine`, `verified_writer`, `context_classifier`, … (21) | **0 od 21** |
| `Factory` | 27+ | 2.605 | `rxoptimizer.*` (28 modula) | **0 od 28** |

v0.27.0 ima potpuno drugačiju arhitekturu (`pa800_enhancer/{smf,domain,optimize,analysis,profiles,hardware,…}`). **Nijedan stari test ne može se pokrenuti kao takav** — ni uz preimenovanje importa, jer ne postoje ni ekvivalentne funkcije.

**Posljedica:** korak „vrati 66 testova" iz prve skice ne postoji. Testovi se pišu **iznova** za v0.27.0 API. Stari testovi ostaju u `legacy/` kao **specifikacija ponašanja** — vrijedni su jer opisuju *šta* treba provjeriti (parser parity, atomic rollback, identity lock), ne *kako*.

To povećava posao na testovima, ali čini plan izvodljivim umjesto da propadne na prvom koraku.

---

## 1. Ciljna struktura

```
Novo/
├── src/pa800_enhancer/          # v0.27.0 kod, nepromijenjen
├── tests/                       # NOVO, pisano za v0.27.0
│   ├── unit/                    #   po podpaketu
│   ├── integration/             #   CLI end-to-end
│   ├── golden/                  #   fiksni MIDI + očekivani izlaz
│   └── fixtures/
├── data/                        # artefakti + manifest (nepromijenjeno)
├── evidence/                    # VRAĆENO iz Jap/Factory
│   ├── pa800-manual/            #   Pa800-201UM-ENG.pdf (23 MB) — vidi §6 o veličini
│   ├── registry/                #   K01: 1.071 adresa
│   └── oscilatori/              #   Oscilatori.txt, 49 RX zona
├── corpus/                      # DNA.zip + Valja.rar (vidi §6)
├── profiles/                    # pa800-documented.json (generisan iz K01)
├── legacy/                      # ARHIVA, read-only
│   ├── jap-python-midi-enhancer/
│   ├── factory-gm-rx-studio/
│   ├── beg-korg-optimizer/
│   ├── a-midi-optimizer/
│   └── dna-song-optimizer/
├── docs/
├── tools/                       # migracijske skripte (k01_to_profile.py …)
└── .github/workflows/ci.yml
```

---

## 2. Faze

### Faza A — Temelj (bez rizika, ništa se ne mijenja u kodu)

| # | Zadatak | Rezultat provjere |
|---|---|---|
| A1 | Uvezi v0.27.0 u `src/`, `pyproject.toml` na `src`-layout | `pip install -e .` prolazi; 105/105 modula import OK |
| A2 | Arhiviraj svih 5 repoa u `legacy/` (bez `.git`, bez blobova >50 MB) | `legacy/MANIFEST.md` sa SHA-256 i izvornim commitom svakog repoa |
| A3 | `.gitignore`, `LICENSE`, `CONTRIBUTING.md`, `docs/` skelet | — |
| A4 | CI: Python 3.11/3.12/3.13 × Ubuntu/Windows | zeleno na praznom test setu |

**Izlaz A:** ništa nije izgubljeno, sve staro je dostupno, CI radi.

### Faza B — Testovi (rješava P0 #1)

Piše se iznova. Redoslijed po riziku — prvo ono što može tiho pokvariti MIDI.

| # | Sloj | Šta se pokriva | Cilj |
|---|---|---|---|
| B1 | `smf/` | reader/writer/vlq round-trip, malformed, SMPTE, Format 0/1/2 | **byte-identičan round-trip** |
| B2 | `domain/` + `optimize/history` | ChangeTransaction, preconditions, undo/redo, checkpoint rollback | svaka transakcija reverzibilna |
| B3 | `export/` | `preserve` = identični bajtovi; `segment-preserve`; `canonical`; reparse+validate | export nikad ne kvari fajl |
| B4 | `optimize/policy` + `simulation` | 4 moda, lock-ovi, fingerprint match, rollback na blocker | policy gate se ne može zaobići |
| B5 | `analysis/` | 15 analizatora na golden fixture-ima | determinizam |
| B6 | `profiles/` + `hardware/` | loader odbija nevalidno; 2-ciklusna promocija | evidence gate drži |
| B7 | `cli.py` | svih 43 komandi: `--help`, preview-bez-izmjene, `--apply` traži izlaz | nijedna komanda ne mijenja ulaz bez `--apply` |
| B8 | golden regresija | 20–30 MIDI iz korpusa, fiksni hash izlaza | detekcija tihe promjene ponašanja |

**Prihvatni kriterij:** ≥70 % pokrivenosti na `smf/`, `domain/`, `optimize/`, `export/`; 100 % komandi ima bar smoke test; CI zelen na 6 kombinacija.

**Preneseno iz `legacy/` kao spisak provjera** (ne kao kod): dual-parser parity, atomic writer + rollback, identity lock, Gold contamination guard, Format 2 read-only.

### Faza C — Dokazi (rješava P0 #2)

Ovdje se otključavaju mrtve komande.

| # | Zadatak | Detalj |
|---|---|---|
| C1 | Uvezi K01 registar | 1.071 adresa (1.006 sounds + 65 drum kits), svaka `CONFIRMED` sa `printed_page`/`pdf_page`/`extracted_line` |
| C2 | Napiši `tools/k01_to_profile.py` | K01 zapis → `SoundProfile`/`DrumKitProfile`; evidence status **`documented`** |
| C3 | Generiši `profiles/pa800-documented.json` | prolazi `profile validate` |
| C4 | Uvezi `Oscilatori.txt` + 15 drum remap pravila + 1 user kit range | kao zasebne evidence izvore |
| C5 | Test: profil se učitava, adrese razrješavaju | `programs song.mid --profile …` daje imena umjesto `unknown` |

**Kritična napomena o statusu.** K01 kaže `CONFIRMED`, ali to znači *„potvrđeno u priručniku"*. v0.27.0 ima četiri statusa:

```
hypothesis < documented < software_verified < hardware_confirmed
```

`sound-map` i `drum-map` po defaultu traže **`hardware_confirmed`** (`sound_mapping.py:59`). Priručnik daje **`documented`** — to je nivo 2 od 4.

Zato:
- **`programs`, `initialization`, `inspect`** (read-only) rade odmah — to je već velik dobitak
- **`sound-map`/`drum-map`** rade tek uz eksplicitni `--minimum-identity-status documented`, uz jasno upozorenje u izlazu
- automatski `hardware_confirmed` **ostaje zaključan** do Faze F

Ovo je namjerno. Priručnik nije isto što i izmjereni odziv instrumenta.

### Faza D — Korpus i reprodukcija (rješava P1 #5, #6, #7)

| # | Zadatak | Detalj |
|---|---|---|
| D1 | `corpus/DNA.zip` (jedna kopija, iz `Factory`) | SHA `125f4486…`; upiši u manifest |
| D2 | Dokumentuj reprodukciju baze | `dna-learn corpus/DNA.zip` → provjeri 3.393/3.368/25 |
| D3 | Reproducibilnost test u CI (nightly) | rebuild → uporedi agregate sa isporučenom bazom |
| D4 | `corpus/Valja.rar` kao **odvojena grupa** | 163 song MIDI; popuni `dataset_groups`/`dataset_members` |
| D5 | Materijalizuj prazne schema-5 tabele | `music_songs`, `music_sections`, `music_chords`, `music_tracks`, `style_elements`, `style_families` |
| D6 | Označi 25 duplikata | ne briši — obilježi u manifestu |

**Pravilo za Valja.rar** (iz `Factory/SESSION_CHECKPOINT.md`): novi korpus ulazi kao izolovana, imenovana grupa. Prvo evaluacija na **source-disjoint** skupu, tek onda promocija u Gold model. Bez ovoga se kontaminira postojeći model i gubi mogućnost poštene evaluacije.

### Faza E — Higijena (P1 #4, P2 #8–11)

| # | Zadatak |
|---|---|
| E1 | Rekonstruiši CHANGELOG 0.15.0–0.25.0; ujednači format na Keep-a-Changelog |
| E2 | Objedini launchere: `install.bat` (ispravi tipfeler `instal.bat`) + `run.bat`; ostavi `POKRENI APLIKACIJU.bat` kao alias |
| E3 | Ukloni `dist/*.whl` iz gita → CI release artefakt |
| E4 | Odluči v1 vs v2 performance katalog; označi drugi `deprecated` (ne briši) |
| E5 | Zamijeni 7 širokih `except Exception` konkretnim tipovima |
| E6 | Verzija → `0.28.0`, CHANGELOG unos |

### Faza F — Hardver (jedini put ka 1.0.0)

| # | Zadatak |
|---|---|
| F1 | Generiši probe set: `hardware generate sound/drum` za prioritetne adrese |
| F2 | Na Pa800: import → export → 2 ciklusa po slučaju |
| F3 | `hardware record-cycle` za svaki ciklus |
| F4 | `profile promote-hardware` → `documented` prelazi u `hardware_confirmed` |
| F5 | Kad kritični skup prođe: artefakti `candidate` → `verified`, verzija **1.0.0** |

Sav alat za ovo **već postoji i radi** — samo nikad nije upotrijebljen (`hardware_tests: 0`).

---

## 3. Redoslijed i zavisnosti

```
A1 → A2 → A3 → A4          (temelj)
      ↓
     B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8     (testovi)
      ↓
     C1 → C2 → C3 → C4 → C5                     (dokazi; C5 traži B6)
      ↓
     D1 → D2 → D3 ; D4 → D5 → D6                (korpus)
      ↓
     E1..E6                                      (higijena)
      ↓
     F1 → F2 → F3 → F4 → F5                      (hardver, traži fizički Pa800)
```

Faze B i C mogu ići paralelno poslije A. F je jedina blokirana na vanjski resurs.

---

## 4. Prioritet — ako se radi samo dio

| Prioritet | Faze | Dobit |
|---|---|---|
| **Minimum** | A + B1–B4 | ništa nije izgubljeno; MIDI-safety putanje pod testom |
| **Preporučeno** | A + B + C + E | testiran projekat, profili popunjeni, mrtve komande žive |
| **Puno** | A–E | + reproducibilan korpus i +163 song MIDI |
| **Release** | A–F | 1.0.0 sa hardverskom potvrdom |

---

## 5. Rizici

| Rizik | Vjerovatnoća | Mjera |
|---|---|---|
| Pisanje testova iznova je veći posao od procjene | visoka | Faza B je inkrementalna; B1–B4 same po sebi daju vrijednost |
| K01 `CONFIRMED` se pogrešno shvati kao hardverski potvrđen | **visoka** | mapira se strogo u `documented`; `hardware_confirmed` samo kroz F4 |
| Valja.rar kontaminira Gold model | srednja | D4: izolovana grupa, source-disjoint evaluacija |
| Rebuild baze ne reprodukuje isporučenu | srednja | D3 poredi agregate, ne bajtove; odstupanje = blocker |
| Git repo prenatrpan (PDF 23 MB, korpus 21 MB) | **visoka** | vidi §6 |
| Nema fizičkog Pa800 | — | A–E su potpuno upotrebljivi bez njega |

---

## 6. Upravljanje veličinom repozitorija

Ukupno ako se sve commit-uje sirovo: **~250 MB**. Previše za udoban `git clone`.

| Artefakt | Veličina | Prijedlog |
|---|---|---|
| `Final.zip` | 19,6 MB | ukloniti iz gita nakon A1 (sadržaj je u `src/`) |
| `data/` (baza + katalozi + model) | 68 MB | zadržati — jezgro proizvoda |
| `Pa800-201UM-ENG.pdf` | 23 MB | **ne u git** — vanjski, provjeren SHA-256 iz manifesta |
| `DNA.zip` | 21 MB | granično — može u git ili vanjski |
| `Valja.rar` | 1 MB | u git |
| `legacy/` (5 repoa) | ~60 MB bez blobova | zadržati (bez `.git`, bez velikih arhiva) |

**Preporuka:** PDF i DNA.zip ostaju **vanjski**, ali se registruju u `data/artifact-manifest.json` sa SHA-256 i uputom za nabavku. Postojeći `artifacts audit` mehanizam upravo to podržava — provjerava prisustvo i hash. Izvedeni K01 JSON (mali) ide u git, izvorni PDF ne.

Alternativa ako se želi sve u repou: Git LFS.

---

## 7. Definicija „ništa se ne gubi"

1. **`legacy/` je nepromjenjiv** — svih 5 repoa, uključujući 66 starih testova i 40 `rxoptimizer` modula.
2. **Git istorija ostaje** na GitHubu: `a`, `beg`, `DNA`, `Factory`, `Jap`, `Beg123`.
3. **Konsolidacija samo dodaje** — nijedan postojeći fajl se ne prepisuje.
4. **Svaki artefakt ima SHA-256** u manifestu, uključujući vanjske.
5. **Duplikati se označavaju, ne brišu.**
6. **`candidate` ostaje `candidate`** dok ga hardver ne promoviše.
7. **Stari testovi = specifikacija** — njihove tvrdnje se prenose u nove testove, i kad se kod ne prenosi.

---

## 8. Sažetak

Kod v0.27.0 je zdrav: 105/105 modula, 5/5 artefakata verifikovano, 43 komande rade. Slabost nije u kodu — nego u tome što je isporuka **odsječena od testova i dokaza**.

Plan to zatvara u pet izvodljivih faza (A–E), uz šestu (F) koja zavisi od fizičkog instrumenta. Najveća izmjena u odnosu na prvu skicu: **testovi se pišu iznova, ne prenose** — jer arhitekture se ne poklapaju ni u jednom modulu. Stari testovi ostaju kao specifikacija.

Poslije A+B+C imaš testiran projekat sa popunjenim profilima i živim `programs`/`sound-map` komandama. Put do 1.0.0 vodi kroz Fazu F — alat za nju je već napisan i čeka.
