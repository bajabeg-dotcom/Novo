# Korg Pa800 MIDI Enhancer

Konsolidovani projekat za sigurnu analizu, optimizaciju i izvoz Standard MIDI
datoteka u Korg Pa800 radnom toku.

**Verzija:** 0.28.0.dev0 (konsolidacija u toku — vidi `PLAN_REVIZIJE.md`)
**Status:** svi artefakti su `candidate`; nema hardverske potvrde na fizičkom Pa800.

---

## Brzi start

```bash
pip install -e ".[dev]"
python -m pa800_enhancer --help
pytest
```

Aplikacijska dokumentacija sa svih 43 komande: `README_APP.md`.

---

## Struktura

| Putanja | Sadržaj |
|---|---|
| `src/pa800_enhancer/` | izvorni kod, 105 modula, 15.583 LOC |
| `tests/` | 120 testova (unit, integration, forenzičke invarijante) |
| `tools/forensics/` | nezavisni SMF parser i forenzički alati |
| `tools/archive_legacy.py` | arhivator starih repozitorija |
| `evidence/` | K01 Pa800 registar (1.071 adresa), Oscilatori.txt |
| `legacy/` | **arhiva 5 prethodnih repozitorija — nepromjenjiva** |
| `forensics/` | sirovi forenzički izvještaji (JSON) |
| `config/`, `profiles/` | konfiguracija i profil uređaja |
| `ci/ci.yml` | CI workflow (treba ručno premjestiti — vidi niže) |

---

## Dokumenti

| Fajl | Sadržaj |
|---|---|
| `ANALIZA_I_REVIZIJA.md` | analiza zatečenog stanja, nedostaci, DNA.zip |
| `PLAN_REVIZIJE.md` | plan u 6 faza (A–F) do verzije 1.0.0 |
| `FORENZIKA.md` | puna forenzika korpusa i baze |
| `CHANGELOG.md` | istorija verzija |
| `legacy/MANIFEST.md` | šta je arhivirano i šta je izuzeto (sa SHA-256) |

---

## Vanjski podaci

Veliki artefakti se **ne drže u gitu**. Provjeravaju se preko manifesta:

```bash
python -m pa800_enhancer artifacts audit data/artifact-manifest.json --root .
```

| Artefakt | Veličina | SHA-256 (skraćeno) |
|---|---|---|
| `data/pa800-enhancer.db` | 37,4 MB | `da1e4acd…` |
| `data/factory-pattern-catalog.json` | 18,9 MB | `24421cb6…` |
| `data/performance-reference-catalog-v2.json` | 1,5 MB | `8df0350a…` |
| `data/performance-reference-catalog.json` | 1,3 MB | `a0f32f88…` |
| `data/models/midi-gru.pt` | 5,7 MB | `0e71c13c…` |

Izvorni paket: `Final.zip`, SHA-256
`a49efbe760aeef23eaddb7cabbc21855f15be89bd85cb850caa9f5ee8739f138`.

DNA korpus (`DNA.zip`, 21 MB, SHA-256 `125f4486…`) dostupan je u repozitoriju
`bajabeg-dotcom/Factory` pod `prism-uploads/`.

---

## Testovi

```bash
pytest                                    # bez vanjskih podataka
PA800_TEST_DATABASE=data/pa800-enhancer.db \
PA800_TEST_CORPUS=/put/do/korpusa pytest  # sa punim podacima
```

Testovi koji traže korpus ili bazu **preskaču se** kad podaci nisu dostupni,
pa suite radi i u čistom checkoutu.

---

## CI

Bot token nema `workflows` dozvolu, pa je workflow pripremljen u `ci/ci.yml`.
Aktivacija:

```bash
mkdir -p .github/workflows
git mv ci/ci.yml .github/workflows/ci.yml
git commit -m "Enable CI" && git push
```

---

## Načelo očuvanja

Konsolidacija **samo dodaje**. Ništa iz ranijeg rada nije obrisano:

- `legacy/` sadrži svih 5 prethodnih repozitorija (4.685 fajlova)
- veliki fajlovi koji nisu ušli u git zapisani su u `legacy/MANIFEST.md` sa SHA-256
- git istorija ostaje na GitHubu: `a`, `beg`, `DNA`, `Factory`, `Jap`, `Beg123`
- duplikati se označavaju, ne brišu
- `candidate` ostaje `candidate` dok ga hardver ne promoviše
