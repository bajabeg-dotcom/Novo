# WP-X10-013A — Independent Codex QA

Datum: 12. august 2026.  
Pass: 1  
Capability: `ANALYZE_ONLY / mutation NONE`

## Verdict

```text
RETURN
```

## Scope pregledan

- `WP-X10-013A_ARCHITECT_ADDENDUM.md`
- `WP-X10-013A_REAUDIT.md`, posebno lockovi L1–L6
- `WP-X10-013A_LEAD_PLAN.md`
- `rxoptimizer/rhythm_proposal_readiness.py`
- `tests/test_rhythm_proposal_readiness.py`

Prihvaćeni WP-012A/B/C/D moduli nisu mijenjani u pregledanom diffu.

## Nalazi

### HIGH — Trusted lineage se ne rekonstruiše i ne verifikuje

`_source_manifest_digest()` samo:

1. parsira `source_semantic_json`;
2. poredi eventualni ugniježđeni `lineage_sha256` sa `source_context_v2.lineage_sha256`;
3. hashira dostavljeni manifest.

Ovo potvrđuje internu jednakost dvije stored vrijednosti, ali ne rekonstruiše trusted-lineage recorde, root record/class, ancestor closure, zabranjene SHA/class skupove ili authority matrix. Schema-v2 trenutno u ovom putu ne daje 013A validatoru canonical lineage DAG iz kojeg bi se `lineage_sha256` mogao nezavisno ponovo izračunati.

Adversarial provjere su pokazale da build i dalje vraća `013A_WITHHELD_FOUNDATION_ACCEPTED` kada se schema-v2 semantic digest legitimno ponovo izračuna nakon:

- konzistentne zamjene stored i manifest lineage digesta proizvoljnom vrijednošću;
- postavljanja manifest `source_class` na `OPTIMIZER_OUTPUT`;
- dodavanja cross-authority `GOLD_REFERENCE_RAW` ancestor zapisa Factory izvoru.

Time nisu ispunjeni Architect source/authority ugovor, re-audit L4, Lead korak 2 i acceptance kriterij 10. Forbidden six-song/optimizer/repaired/cross-authority lineage guard nije stvarno ponovo izvršen za svaki snapshot.

### Potrebna korekcija

013A input mora sadržati ili dobiti zaseban frozen canonical trusted-lineage snapshot dovoljan za nezavisnu rekonstrukciju. Validator mora ponovo izračunati record ID-jeve i DAG digest, provjeriti root SHA/class, puni ancestor closure, zabranjene SHA i klase, authority matrix i jednakost sa source manifestom. Samo poređenje stored hash vrijednosti nije dovoljno.

Obavezni adversarial testovi moraju dokazati odbijanje sva tri gore navedena slučaja.

## Provjere koje prolaze

- assessment universe je tačno `analysis_authorization` i NOTE/source/event-slot anchor se provjerava;
- svih 21 authorization statusa imaju totalni withheld-only mapping;
- composite authorization locator uključuje recomputed row digest;
- schema-v2 semantic/file, RAW i stable subject/edge digesti se ponovo računaju radi identity parity;
- recursive forbidden-key guard pokriva nested config i schema semantic JSON;
- schema/status domene, immutable no-change lifecycle i FK lanac su implementirani;
- schema-v2 se otvara read-only; runtime nema MIDI writer/encoder/export put;
- permutation determinism, no-output guard i atomic rollback testovi prolaze;
- targeted pytest: `13 passed` sa warning-as-error;
- puni pytest: `369 passed` sa warning-as-error;
- `py_compile` i `git diff --check` prolaze.

## Zavšni QA status

Paket ostaje striktno withheld-only i nije pronađen repair/mutation put. Ipak, otvoreni HIGH lineage nalaz onemogućava tehnički ACCEPT dok trusted source provenance nije nezavisno dokaziva.

```text
RETURN
```