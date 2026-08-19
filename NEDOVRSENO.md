# Nedovršene stavke — radni spisak

Izvor: korisnički pregled od 19.08.2026.
Ovaj fajl je **živa radna lista**. Uz svaku stavku stoji da li je tvrdnja
provjerena mjerenjem u ovom repou i gdje je zaključana testom.

Legenda statusa:

| Oznaka | Značenje |
|---|---|
| 🔒 | zaključano testom — regresija je nemoguća |
| 📋 | potvrđeno mjerenjem, test još nije napisan |
| ⏳ | nije još provjereno |
| 🔧 | traži fizički Pa800 |

---

## Šta je urađeno od objave spiska

| Stavka | Radnja | Test |
|---|---|---|
| **11.1** regression za očuvanje | **gotovo** | `tests/regression/test_preservation_contract.py` — 20 testova |
| **10** guitar RX zona `iznad 96` | **ispravljeno**: tačno je **od 96 (C7) uključivo** | `test_rx_trigger_zones.py::test_boundary_is_inclusive_not_exclusive` |
| **10** CLI ispisuje traceback | **popravljeno**: kratka poruka + exit 2 | `test_cli_contract.py::TestErrorHandling` |
| **10** nema unit testa za mapper | **gotovo**: 20 testova | `test_preservation_contract.py` |
| **11.2** RX profile schema | **gotovo**: 12 profila + guard spojen na velocity | `test_rx_profiles.py` (35), `test_rx_trigger_zones.py` (19) |

### Incident „Nevera moja" je sada trajno zaključan

```
16 trackova / 8.340 nota  →  7 trackova / 4.492 note
```

`test_nevera_moja_incident_cannot_recur` gradi pjesmu sa 16 trackova, lyricsom,
pitch bendom i sustainom, pa provjerava da konzervativni `Optimize`:

- ne mijenja broj trackova ni njihove indekse,
- čuva **svaku** notu bit-identično (tick, kanal, visina, velocity),
- čuva lyrics, nazive trackova, tempo, metar, pitch bend i sustain,
- ne ispušta nijedan kanal,
- je idempotentan — drugi prolaz ništa ne mijenja.

Eksplicitno se provjeravaju i tačni brojevi iz incidenta (`!= 7`, `!= 4492`).

---

## Nalazi otkriveni pisanjem testova

### N1 — drum adresa se dodjeljuje bez ijednog dokaza 🔒

`optimize/conservative.py:45`:

```python
if role=="drums": candidates=[((120,0,4),1)]
```

Adresa `120.0.4` („Pop Std. Kit RX") je **hardkodirana** i dodjeljuje se čak i
kada je Factory katalog potpuno prazan. U `config/performance-defaults.json`
označena je kao `factory_reference`, **ne** `hardware_confirmed`.

Ovo krši pravilo iz §2.3 spiska: *„mapper ne mijenja sound bez objašnjivog
role, range, Factory i hardware dokaza; nepoznati slučaj ostaje nepromijenjen."*

Zaključano kao `xfail(strict)` u
`test_preservation_contract.py::test_drum_kit_requires_evidence` — test će sam
postati zelen kad adresa počne dolaziti iz dokaza.

### N2 — optimizer ne čita RX oscillator konfiguraciju ✅ ZATVORENO

Bilo: `absolute_trigger` logika postojala je **samo** u
`arranging/factory_source.py:69`, a optimizeri je nisu čitali.

Sada: `profiles/rx.py` nosi 12 RX profila izvedenih iz `Oscilatori.txt`, a
`optimize/rx_guard.py` provjerava svaki velocity prijedlog protiv
oscilatorskih zona. `VelocityRangeModule` prima `rx_profile` i poštuje ga.

Zaključano testovima ponašanja (ne grep-om izvora) u
`test_rx_trigger_zones.py::TestOptimizerIsOscillatorAware`.

### N3 — 0,99 % nota tiho otpada pri uparivanju 🔒

Iz `FORENZIKA.md`: 36.525 nota u 405 Factory fajlova. Uzrok su viseći Note On
bez Note Off. Reprodukovano 405/405 tačno.

Zaključano u `test_forensic_invariants.py::TestUnpairedNoteBehaviour`.

---

## P0 — prije ozbiljne upotrebe

### 2.1 Hardware potvrda Factory sound adresa 🔧

Alat za ovo **već postoji i radi** (`hardware generate` / `record-cycle` /
`profile promote-hardware`), ali nikad nije upotrijebljen: `hardware_tests` ima
**0 redova**, svih 5 artefakata je `candidate`.

Nedostaje: probe MIDI po adresi, dva ciklusa na uređaju, zapis OS/resource
verzije, blokiranje izvoza za nepotvrđenu adresu.

### 2.2 Potpuna RX/oscillator baza 🔒 djelimično

**Urađeno:** `profiles/rx.py` — verzionirana schema sa 12 profila iz
`evidence/oscilatori/Oscilatori.txt`:

| Porodica | Profili | Zona |
|---|---|---|
| bass | Finger, Picked, SlapFing, SlapPick RX | 5 (Gliss/Stop/Radni/Harm + Noise) |
| guitar | Clean RX1–RX6 | 5 (Harm-Ghost/Dead-Mute/Radni/Slap-Slide + Noise) |
| guitar | Dist Guitar RX1/RX2 | 3 (Mute 1–87 / Dist 88–127 + Noise) |
| guitar | Power Chords | 1 (oba sloja 1–127, čista dinamika) |

Svaki nosi `evidence_status` (svi `documented`), izvor i validaciju opsega.
SlapFing/SlapPick prag je **87** — ispravka ranije zapisanog 94 — uz bilješku
da čeka PCG/Sound Edit potvrdu.

**Spojeno na velocity** kroz `RxVelocityGuard`: izmjena koja bi prešla u drugi
oscilator se skrati na granicu zone ili odbaci; note u C7–G9 se ne diraju.

**Nedostaje:** bank/program veza za većinu naziva (samo Power Chords ima
adresu), potpuna lista svih RX soundova i kitova, spajanje na articulation i
validator, Pop Std. Kit RX per-nota velocity slojevi.

### 2.3 Sigurno automatsko sound mapiranje 📋

Trenutni mapper klasificira ulogu iz **samo** kanala i GM programa
(`conservative.py:10-14`) — bez registra, polifonije, ritma i naziva tracka.

Nedostaje sve iz spiska; dodatno vidi **N1**.

### 2.4 Automatski balans za sačuvane trackove ⏳
### 2.5 Listening i regresijski skup 📋

Softverski dio (100 % očuvanje) je **gotov i zaključan**. Ostaje ljudski dio:
curated korpus, slijepi A/B, snimke sa stvarnog Pa800.

---

## P1 / P2

Stavke 3.1–3.5, 4, 5, 6, 7, 8, 9 stoje nepromijenjene u odnosu na spisak.
Prioritet ostaje redoslijed iz §11.

---

## Stanje testova

```
194 testa ukupno
  182 prolaze
   11 preskočeno (traže vanjsku bazu/korpus)
    1 xfail(strict) — dokumentovana rupa N1
```

Pokretanje:

```bash
pytest                                     # bez vanjskih podataka
pytest tests/regression/                   # samo ugovor o očuvanju
PA800_TEST_DATABASE=... PA800_TEST_CORPUS=... pytest   # sve
```

---

## Sljedeći korak po §11

1. ~~Regression test za očuvanje~~ **gotovo**
2. ~~RX profile schema → velocity~~ **gotovo** (N2 zatvoren). Ostaje spojiti
   na articulation i validator, te dodati bank/program adrese.
3. Hardware probe paket za sve korištene Factory adrese (zatvara N1 i 2.1) 🔧
4. Konzervativni output leveling uz zaštitu tihih layera (2.4)
5. Gold mikro-dinamika samo na potvrđene adrese (3.1)
6. GUI evidence/mixer + zasebno `Re-arrange` dugme (4, 7)
7. Pa800 A/B listening korpus i release pragovi (2.5) 🔧
8. Tek onda ML generator (6)
