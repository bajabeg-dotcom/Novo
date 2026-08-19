# WP-X10-013A — Codex Lead Plan

Datum: 12. august 2026.  
Status: `LEAD_READY`  
Capability: `ANALYZE_ONLY / mutation NONE`

## TECHNICAL_PLAN

Implementirati samo withheld-only readiness materijalizer iz Architect addenduma. Ulaz je QA-prihvaćena schema-v2 SQLite baza plus frozen RAW bytes mapa za sve izvore. Izlaz je nova atomski građena SQLite baza koja ima samo immutable run, snapshot, assessment, no-change simulation i identity validation zapise.

Ne implementirati exact target, anomaly-positive odluku, change overlay, MIDI writer/export, cost, score, budget ili repair API.

## FILE_OWNERSHIP

- Implementer: `rxoptimizer/rhythm_proposal_readiness.py`
- Implementer: `tests/test_rhythm_proposal_readiness.py`
- Lead: ovaj plan i integracijski pregled
- QA: read-only pregled svih promjena; ne popravlja implementaciju
- Prihvaćeni WP-012A/B/C/D moduli i testovi: read-only

## INTERFACES

Javni API:

```text
build_withheld_readiness_database(
    schema_v2_path,
    output_path,
    source_bytes_by_sha256,
    config=None,
) -> build report
```

Ulazna schema-v2 baza otvara se read-only. Za svaki `source_context_v2` izvor mora postojati frozen byte payload čiji SHA-256 odgovara source ključu. Assessment universe je tačno skup svih `analysis_authorization` redova i svaki mora pokazivati na `NOTE` subject istog sourcea.

Authorization locator je canonical digest od composite ključa `(source_sha256, note_subject_id, event_slot_key)` i recomputeovanog row semantic digesta. Ne upisuje se ID u schema-v2.

Totalni authorization mapping mora pokriti svih 21 zatvorenih 012D statusa. `ANALYZE_ALLOWED` postaje samo `READINESS_INPUT_ANALYZE_ALLOWED`; svaki red ostaje withheld i dobija najmanje osnovne razloge `SOURCE_NOT_USER_INPUT`, `ANOMALY_PROOF_CONTRACT_UNAVAILABLE`, `EXACT_TARGET_CONTRACT_UNAVAILABLE` i `CHANGE_SIMULATION_CONTRACT_UNAVAILABLE` plus status-specifične razloge.

No-change simulation i identity validation moraju ponovo izračunati:

- RAW source SHA-256;
- schema-v2 whole-file SHA-256;
- schema-v2 semantic digest preko prihvaćene v2 canonical funkcije;
- stable subject+edge universe digest;
- source manifest/lineage digest;
- output-directory no-artifact guard za `.mid`/`.midi`.

## STORAGE

Nova schema ima zatvorene enum CHECK ugovore i FK lanac:

```text
assessment_runs
→ input_snapshots
→ candidate_assessments
→ no_change_simulations
→ identity_validations
```

Nema UPDATE/DELETE javnog API-ja. Build ide u temp fajl, zatim integrity/FK/digest provjera i atomic replace. Greška briše temp i čuva prethodni accepted output byte-identično.

## MIGRATION_ORDER

1. Verifikovati schema-v2 capability, mutation status, semantic digest i read-only pristup.
2. Frozen source byte i source/lineage manifest verifikacija.
3. Recompute stable subject/edge universe digesta.
4. Učitati i totalno mapirati authorization universe.
5. Materijalizovati immutable lifecycle redove.
6. Recompute before/after identity vrijednosti i no-output guard.
7. Canonical semantic digest, SQLite integrity/FK i atomic replace.

## TEST_ASSIGNMENTS

Obavezni testovi:

- svih 21 authorization statusa mapirano i withheld;
- missing/extra authorization assessment nije moguć;
- non-NOTE ili cross-source authorization hard-fail;
- authorization locator koristi composite key + row digest;
- RAW/schema semantic/subject digesti se stvarno recomputeuju;
- forged stored digest, mutated RAW bytes i schema-v2 mutation se odbijaju;
- recursive forbidden-key injection u config/nested payload se odbija;
- nema zabranjenih schema kolona/ključeva niti MIDI writer/export importa;
- changed counts su nula, before/after digesti jednaki, output `NOT_CREATED`;
- determinism pod permutacijom input mape;
- atomic rollback čuva prethodni output byte-identično;
- output folder ne dobija `.mid`/`.midi` artefakt;
- targeted i puni pytest sa warning-as-error.

## INTEGRATION_CHECKLIST

- [ ] Architect addendum ima precedencu nad v1 exact-target scopeom.
- [ ] Audit lockovi L1–L6 implementirani.
- [ ] WP-012A/B/C/D fajlovi nisu mijenjani.
- [ ] Capability svuda `ANALYZE_ONLY`, mutation `NONE`.
- [ ] Jedina acceptance oznaka je `013A_WITHHELD_FOUNDATION_ACCEPTED`.
- [ ] Exact target i change simulation ostaju za kasnije pakete.
