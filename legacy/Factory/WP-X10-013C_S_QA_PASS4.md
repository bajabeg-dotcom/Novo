# WP-X10-013C-S — Independent Codex QA Pass 4

Datum: 12. august 2026.  
Scope: samo `013C-S` phase-independent structural registry  
Standard: `MASTER PROMPT — COMPLETE PROOF - NO UNPROVEN CLAIMS AUDIT`  
QA nije mijenjao implementaciju ni testove.

## Izvršene provjere

```text
python3 -m pytest -q -W error tests/test_rhythm_structural_slots.py
51 passed

python3 -m pytest -q -W error
481 passed

python3 -m pytest -q -W error <30 authority/context/unison/tamper slučajeva>
30 passed

python3 -m py_compile rxoptimizer/rhythm_structural_slots.py \
  tests/test_rhythm_structural_slots.py
git diff --check
```

Sve komande prolaze bez warninga, compile ili diff greške. Prolazni testovi se ovdje koriste samo kao dokaz ograničenog test-only ponašanja; nisu dokaz produkcijskog Factory autoriteta.

## Authority i execution-path audit

### Pass-3 self-mint napad

Ponovljen je napad koji koristi `object.__new__`, custom `AcceptedFactoryCorpusAuthorityVerifierPort` i pokušava promijeniti `authority_scope` u `PRODUCTION`.

Rezultat:

```text
build: REJECTED — production authority is NOT_PROVABLE
verify: REJECTED — production authority is NOT_PROVABLE
output database after failed build: NOT CREATED
```

`_resolve_factory_authority()` prihvata isključivo `TestOnlyFactoryCorpusAuthorityEvidence`, zatim zahtijeva literalni `TEST_ONLY` scope i eksplicitni `allow_test_only_authority=True`. Dataclass konstruktor takođe odbija svaki scope različit od `TEST_ONLY`; `object.__new__` zaobilaženje konstruktora ne zaobilazi build/verify gate.

### Arbitrary `PRODUCTION`, missing flag i synthetic corpus

- Ne postoji prihvaćen `PRODUCTION` tip, scope ili builder grana.
- Nedostajući verifier port hard-failuje prije target baze.
- Validni test verifier bez `allow_test_only_authority=True` hard-failuje.
- Self-built synthetic corpus može proći samo kroz eksplicitni test-only helper/flag. Njegov report, schema i verifier rezultat ostaju:

```text
authority_scope = TEST_ONLY
production_authority_status = NOT_PROVABLE
calibration_envelope_allowed = false
capability = ANALYZE_ONLY
mutation_capability = NONE
```

Caller može napraviti vlastiti self-consistent `TEST_ONLY` capability kada eksplicitno uključi test-only flag. To je namjerno dozvoljena testna površina i nije production claim. Takav rezultat se ne može promovisati kroz ovaj modul jer schema `CHECK`, build contract, authority proof, report i završni verifier zaključavaju gore navedene vrijednosti.

### Envelope execution surface

Repo i schema/API pregled ne nalaze envelope builder, fit, target, proposal, repair, MIDI writer ili output put u `rhythm_structural_slots.py`. Jedina pojava riječi `envelope` u dozvoljenoj površini je negativni lock `calibration_envelope_allowed=false`; static surface validator odbija druge envelope/target/proposal/repair/output identifikatore.

Zato je production envelope i dalje blokiran. Ovaj ACCEPT ne odobrava početak envelopea na osnovu production corpusa koji nije dokaziv.

## Regresija prethodnih nalaza

### Context provenance — PROVEN za test-only library

Svih 14 identity-kritičnih dimenzija imaju parametrizovane mutation-sensitive testove: role, Bank MSB/LSB, Program, instrument identity, style, section, section number, CV, meter numerator/denominator, tempo, track-channel role i voice policy. Caller-validna, ali anchor-netočna vrijednost daje `STRUCTURAL_CONTEXT_UNPROVEN`, nula context/slot redova i nula resolved memberships.

### Factory anchor i quality — PROVEN za test-only library

Source odsutan iz accepted schema-v2 anchor universea se odbija. Caller `NORMAL` ne može nadjačati accepted `RARE`. Accepted database je byte-pinned, semantic root se nezavisno recomputeuje, a source snapshot, manifest, lineage, stable subjects, edges i NOTE context moraju odgovarati anchoru.

Ovo ne dokazuje stvarni production accepted corpus, jer production adapter/generation commitment nije implementiran.

### Duplicate/unison — PROVEN fail-closed za v1

Duplicate pitch uvijek daje `STRUCTURAL_DUPLICATE_AMBIGUOUS`. Caller tokeni `VOICE_A/B`, `V000123/V000124` i `ORDER_0001/0002` ne mogu sakriti tick, parser ili event redoslijed. Unique-pitch identitet ne koristi caller voice token. Pozitivno razrješenje unisona nije implementirano niti se tvrdi.

### Lineage, subject, edge i mutation sensitivity — PROVEN za authority-pinned test-only verifier

Verifier rekonstruiše lineage closure i allowed-parent matrix, canonical stable subjecte/edgeove, njihove FK veze i membership provenance. Rehashovanje lokalnog semantic roota ne spašava izmjene manifest-a, lineage digest/recorda, accepted schema root-a, source semantic zapisa, NOTE subjecta, NOTE edgea ili membership provenancea.

Testovi imaju konkretne negativne ishode i provjeravaju da target nije kreiran ili da verifier baca grešku; nisu samo smoke/import testovi. Permutacija daje isti digest i byte-identičan output, a failed rebuild čuva prethodnu bazu.

## Complete-proof status

```text
TEST_ONLY structural library: PROVEN
Production authority integration: NOT PROVABLE FROM CURRENT EVIDENCE
Production corpus materialization: NOT PROVABLE FROM CURRENT EVIDENCE
Calibration envelope execution: BLOCKED
Repair / MIDI output / release: NOT IMPLEMENTED
```

`PROVEN` je strogo ograničen na reproducirane test-only ugovore i pregledani call graph. Ne prenosi se na production podatke, calibration envelope, anomaly proof, target, simulation, repair, Pa800 dokaz ili release.

## Konačni QA verdict

```text
ACCEPT
```

ACCEPT znači samo da je trenutni 013C-S paket ispravno i dokazivo ograničen na safe `TEST_ONLY` structural biblioteku, uz eksplicitno označen `NOT_PROVABLE` production autoritet i `calibration_envelope_allowed=false`. Production 013C-S integration i calibration envelope ostaju blokirani dok zaseban vanjski accepted-generation authority adapter i njegovi dokazi ne postoje.