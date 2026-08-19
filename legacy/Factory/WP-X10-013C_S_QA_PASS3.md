# WP-X10-013C-S — Independent Codex QA Pass 3

Datum: 12. august 2026.  
Scope: samo `013C-S` phase-independent structural registry  
Standard: `MASTER PROMPT — COMPLETE PROOF - NO UNPROVEN CLAIMS AUDIT`  
QA nije mijenjao implementaciju ni testove.

## Izvršene provjere

```text
python3 -m pytest -q -W error tests/test_rhythm_structural_slots.py
50 passed

python3 -m pytest -q -W error
480 passed

python3 -m pytest -q -W error tests/test_rhythm_structural_slots.py \
  -k 'every_identity_context_dimension or unison or external_authority_rejects_rehashed \
      or authority_port_recomputes_full_lineage or missing_production_authority_port \
      or self_minted_test_authority'
29 passed, 21 deselected

python3 -m py_compile rxoptimizer/rhythm_structural_slots.py \
  tests/test_rhythm_structural_slots.py
git diff --check
```

Sve navedene komande prolaze bez warninga ili compile/diff greške. Prolazni testovi nisu sami po sebi dokaz produkcijskog autoriteta.

## Claim-by-claim status

### 1. Production caller nema raw path/digest loader

**STATUS: PROVEN — ograničeno na trenutni javni call graph.**

Repo pretraga ne nalazi production CLI/GUI/build poziv za `build_structural_registry()` ili `verify_structural_registry()`. Raw path/digest loader je nazvan `_TestOnlyAcceptedFactoryCorpusAuthorityVerifier` i koristi se samo u testovima. Ne postoji implementiran production authority adapter niti stvarni production execution path.

Ovo dokazuje odsustvo production integracije, ne sigurnost budućeg adaptera.

### 2. Missing authority port fail-closed blokira build

**STATUS: PROVEN.**

`None`, pogrešan tip ili verifier koji ne vrati očekivani capability tip bivaju odbijeni. Ciljani test `test_missing_production_authority_port_fails_closed` je mutation-sensitive.

### 3. TEST_ONLY authority se ne može koristiti kao PRODUCTION

**STATUS: FAILED.**

Literalni test-only capability se bez `allow_test_only_authority=True` ispravno odbija. Međutim, zaštita se oslanja na modul-global Python objekat:

```text
_ACCEPTED_CORPUS_SEAL
```

Taj objekat nije neforgeable boundary. Caller može importovati modul, pročitati seal, izračunati `_digest`, konstruisati `VerifiedAcceptedFactoryCorpusAuthority(authority_scope="PRODUCTION", ...)` i vratiti ga iz vlastitog `AcceptedFactoryCorpusAuthorityVerifierPort` adaptera.

Nezavisni adversarial test je uradio upravo to. Rezultat:

```text
FORGED_BUILD_ACCEPTED
authority_scope = PRODUCTION
resolved_memberships = 1

FORGED_VERIFY_ACCEPTED
authority_scope = PRODUCTION
memberships = 1
```

Dakle, test-only synthetic corpus može biti promovisan u production autoritet bez vanjskog platformskog trust roota.

### 4. Arbitrary synthetic schema-v2/root ne može self-authorize

**STATUS: FAILED.**

Self-consistent synthetic schema-v2 baza, njen lokalno izračunat semantic root, lokalni lineage/manifest i caller-mintovan `PRODUCTION` capability prošli su i build i završni verifier. Postojeći test pokriva samo direktnu upotrebu `TEST_ONLY` scopea; ne pokriva custom port koji koristi dostupan seal.

Potrebna je authority vrijednost koju ovaj proces/modul ne može sam mintovati: platform-provided adapter sa vanjskim accepted-generation commitmentom ili eksplicitno trajno ograničenje cijelog paketa na `TEST_ONLY` bez production scopea.

### 5. Context se rekonstruiše iz accepted NOTE/source podataka

**STATUS: PROVEN — za izolovani test-only library model.**

Svaka context dimenzija ima mutation-sensitive test. Caller promjena rolea, Bank/Programa, instrument identiteta, style/section/CV-a, metra, tempa, track rolea ili voice policyja daje `STRUCTURAL_CONTEXT_UNPROVEN` i ne materijalizuje structural identity.

### 6. Duplicate/unison ne koristi timing/parser token

**STATUS: PROVEN — za v1 library ponašanje.**

Svaki duplicate pitch ostaje `STRUCTURAL_DUPLICATE_AMBIGUOUS`. Proizvoljni `VOICE_*`, `V000123` i `ORDER_*` tokeni ne razrješavaju unison. Caller voice token ne utiče na unique-pitch identity. Pozitivno verified unison razrješenje nije implementirano i nije dokazano.

### 7. Cross-authority/forbidden lineage se odbija

**STATUS: PROVEN unutar predatog authority capabilityja; UNPROVEN kao production trust claim.**

Lineage DAG se rekonstruiše, provjeravaju se root/class, ancestor closure, šest zabranjenih SHA vrijednosti, forbidden klase i allowed-parent matrix. Cross-authority fixture se odbija.

Ipak, pošto caller može mintovati sam production capability, ove provjere dokazuju internu konzistentnost predatog DAG-a, ali ne dokazivo eksterno porijeklo produkcijskog autoriteta.

### 8. Rehashed persisted tampering se otkriva

**STATUS: PROVEN — za authority-pinned library verifier.**

Nakon izmjene i urednog ponovnog računanja lokalnog semantic roota odbijeni su:

- source manifest;
- lineage digest;
- accepted schema root;
- source semantic record;
- lineage record;
- stable NOTE subject semantic record;
- stable NOTE edge semantic record;
- membership provenance.

Verifier nezavisno rekonstruiše canonical `StableSubject`, `StableSubjectEdge`, lineage DAG/closure i poredi ih sa authority anchorom.

### 9. Determinizam, atomicity i capability lock

**STATUS: PROVEN — za pokrivene library fixture slučajeve.**

Permutovan input daje isti semantic digest i byte-identičnu bazu. Failed rebuild čuva prethodni target. Schema ostaje `ANALYZE_ONLY/NONE` i nema envelope, target, proposal, repair ili MIDI-output površinu.

### 10. Production corpus materialization i stvarni platform adapter

**STATUS: NOT PROVABLE FROM CURRENT EVIDENCE.**

Nema stvarnog production authority adaptera, CLI/GUI/build integracije ni izvršenog production corpus builda. Synthetic test fixtures ne mogu dokazati Factory production authority. Zbog forgeable in-process seala trenutna biblioteka nije spremna ni za tvrdnju da bi proizvoljan production adapter bio sigurno razgraničen.

## Obavezne korekcije

1. Ukloniti mogućnost da caller/modul sam konstruiše `PRODUCTION` capability. Modul-global object seal i underscore nisu trust boundary.
2. Production authority mora dolaziti iz vanjskog platformskog adaptera/accepted-generation registra sa commitmentom koji structural library ne može mintovati ili prepisati.
3. Ako takav adapter nije dostupan, ukloniti `PRODUCTION` scope iz ovog paketa i formalno ga ograničiti na test-only library.
4. Dodati adversarial test sa custom verifier portom koji pokušava vratiti caller-mintovan production capability i mora biti odbijen prije builda.
5. Tek poslije toga ponoviti QA; 013C envelope ostaje blokiran.

## Konačni QA verdict

```text
RETURN
```

Izolovano structural ponašanje, context rekonstrukcija, unison fail-closed, persisted-tamper detekcija, determinism i atomicity imaju stvarne dokaze u test-only biblioteci. Production authority separation i production corpus integracija nisu dokazani; caller-mintovan production capability je praktično reprodukovan. Zato `013C-S ACCEPT` i početak envelope implementacije nisu dozvoljeni.