# WP-X10-013C-S — Independent Codex QA Pass 2

Datum: 12. august 2026.  
Standard: `prism-uploads/MASTER PROMPT — COMPLETE PROOF - NO UNPROVEN CLAIMS AUDIT.md`  
Scope: samo phase-independent structural slot registry; bez envelope implementacije  
Verdict: `RETURN`

## Executive verdict

Tri originalna napada su sada zatvorena na direktnom builder putu:

- svih 14 caller-forged context dimenzija ne daju resolved membership;
- source koji nije član predatog accepted corpusa se odbija;
- duplicate/unison se ne razrješava proizvoljnim `V...`, `ORDER...` ili drugim caller tokenom.

Ovo još nije dovoljan proof za `ACCEPT`. Pronađena su dva preostala trust propusta:

1. caller može sam napraviti proizvoljan schema-v2 corpus, sam izračunati njegov root i tako mintovati `AcceptedFactoryCorpus`; production izvor pouzdanog root-a nije implementiran niti dosegljiv;
2. downstream `verify_structural_registry()` prihvata više identity/provenance mutacija nakon što napadač ponovo izračuna semantic root.

Zato tvrdnja da accepted Factory authority i finalni structural registry ostaju dokazivi nakon persistiranja ima status `FAILED/UNPROVEN`, a 013C-E ostaje blokiran.

## Execution evidence

Stvarni ciljani put:

```text
FactoryStructuralSource
→ load_accepted_factory_corpus(path, caller_expected_digest)
→ build_structural_registry
→ _validate_source
→ _accepted_source_anchor
→ _reconstruct_bar_context
→ _validate_bar_provenance
→ _bar_tokens
→ calibration_context_identity / structural_slot_identity
→ SQLite
→ verify_structural_registry
```

Repo pretraga nije pronašla production poziv `build_structural_registry`, `load_accepted_factory_corpus` ili `verify_structural_registry` iz CLI-ja, GUI-ja ili `build-dna` toka. Trenutna execution reachability je test/library-only.

```text
CLI/GUI/production integration = UNPROVEN / DEAD PRODUCTION INTEGRATION
```

## Claim-by-claim rezultat

### CLAIM — Context se rekonstruiše, ne vjeruje calleru

**EVIDENCE:** `_reconstruct_bar_context()` pravi context iz accepted NOTE redova i zahtijeva punu jednakost sa caller contextom. Parametrizovani test zasebno mijenja role, Bank MSB/LSB, Program, instrument identity, style, section, section number, CV, meter numerator/denominator, tempo, track-channel role i voice policy.

**TEST:** `test_every_identity_context_dimension_is_reconstructed_not_caller_claimed` ima stvarne assertione: nula membershipa, jedan ambiguous bar, `STRUCTURAL_CONTEXT_UNPROVEN` i nula context redova.

**MUTATION:** monkeypatch koji je zamijenio rekonstrukciju sa `return source.context` oborio je svih 14 parametara (`14 failed`).

**STATUS:** `PROVEN` za direktni builder put uz već učitan accepted anchor.

### CLAIM — Source absent iz predatog accepted corpusa se odbija

**EVIDENCE:** `_accepted_source_anchor()` zahtijeva membership source SHA-a, `NORMAL`, lineage digest, snapshot commitment i subject/edge parity.

**TEST:** `test_self_declared_factory_absent_from_accepted_corpus_is_rejected` odbija masquerade prije target baze. Mutation koja je zaobišla membership lookup oborila je test (`1 failed`). `test_normal_quality_must_come_from_accepted_quality_registry` dodatno pokriva caller `NORMAL` nasuprot accepted `RARE`.

**STATUS:** `PROVEN` samo relativno prema predatom `AcceptedFactoryCorpus` objektu.

### CLAIM — Predati accepted corpus je sam po sebi pouzdan production Factory autoritet

**EVIDENCE:** `load_accepted_factory_corpus()` prima običan `expected_semantic_digest` string. Nema signed/generation pointera, platform trust porta, allowlisted accepted generationa niti production adaptera koji određuje očekivani root. Test helper sam gradi schema-v2 bazu iz arbitrary fixturea, sam računa `semantic_digest_v2()` i zatim je loader prihvata.

**ADVERSARIAL TEST:** proizvoljan `source_fixture("arbitrary-self-declared")` je upisan u lokalno mintovan schema-v2 corpus; njegov samostalno izračunat root predat je loaderu. `build_structural_registry()` je zatim proizveo `resolved_memberships=1`.

Schema-v2 baza takođe ne sadrži canonical lineage DAG redove; čuva samo `lineage_sha256`. Loader zato ne može nezavisno ponovo izračunati ancestor closure iz accepted baze. `build_config_sha256` se provjerava samo kao SHA-format, ne prema eksterno prihvaćenom build contractu.

**STATUS:** `UNPROVEN` za production authority; self-minted anchor attack i dalje postoji jedan nivo iznad prethodnog membership testa.

### CLAIM — Unison ne može koristiti timing/parser token

**EVIDENCE:** `_cluster_token()` sada svaki duplicate pitch bez izuzetka vraća kao `STRUCTURAL_DUPLICATE_AMBIGUOUS`; `voice_token` ne ulazi u ordering.

**TEST:** `None`, `VOICE_A/B`, `V000123/V000124` i `ORDER_0001/0002` svi daju nula membershipa i ambiguity status.

**MUTATION:** monkeypatch koji je duplicate sortirao po pitch/note ID-u oborio je sva četiri relevantna test slučaja (`4 failed`).

**STATUS:** `PROVEN` za v1 fail-closed ponašanje. Pozitivno verified unison razrješenje nije implementirano i nije claim.

### CLAIM — Persistirani registry verifier otkriva rehashed tampering

**EVIDENCE:** postojeći test mijenja samo `provenance_json.note_subject_id`, ponovo računa root i potvrđuje rejection.

**ADVERSARIAL TEST:** na pet zasebnih kopija validne baze promijenjeno je po jedno polje, zatim je semantic root uredno ponovo izračunat. `verify_structural_registry()` je prihvatio svih pet:

```text
source_registry.manifest_json = {}
source_registry.lineage_sha256 = forged SHA
source_registry.accepted_schema_v2_sha256 = forged SHA
stable_subjects NOTE semantic_json = {}
stable_edges NOTE_HAS_ON_EVENT semantic_json = {}
```

Verifier provjerava FK, root, context/slot hash, subject type kolone, edge kolone i membership provenance, ali ne rekonstruiše source manifest/lineage/snapshot/accepted-root commitments niti canonical subject/edge semantic zapise.

**STATUS:** `FAILED`.

## Test quality audit

| Test / grupa | Test intent i stvarni assertion | Status / bug koji može pobjeći |
|---|---|---|
| topology-preserving timing | isti context/slot count i forbidden-string scan | `PARTIALLY PROVEN`; scan ne dokazuje cjelokupan dependency graph |
| typed identity API | generic mapping/type smuggling se odbija | `PROVEN` za public signature |
| transposition/inversion | transposition resolved, inversion ambiguous | `PROVEN` za fixture oblik |
| split/merge/insert/delete/arpeggio | nula memberships i oba bara ambiguous | `PROVEN` |
| duplicate/unison grupa | nula memberships i exact ambiguity status | `PROVEN`; mutation-sensitive |
| caller token on unique pitches | token permutacija ne mijenja resolved count | `PARTIALLY PROVEN`; ne poredi semantic digest/slot keys |
| exact drum lane | transposed lanes ne alignuju | `PROVEN` za fixture |
| untrusted literal authority | literal `SYNTHETIC_TEST` odbijen | `WEAK` samostalno; ne pokriva self-minted accepted corpus |
| absent accepted source | očekuje exact membership rejection | `PROVEN` relativno prema već trusted anchoru; ne dokazuje trust origin |
| accepted quality | accepted `RARE` pobjeđuje caller `NORMAL` | `PROVEN` za source-level fixture; track/context quality granularity nije široko testirana |
| byte pin after load | post-load DB mutacija se odbija | `PROVEN` za TOCTOU byte pin; ne pokriva forged pre-load DB + novi root |
| external expected root mismatch | pogrešan digest se odbija | `WEAK` za authority: caller može predati vlastiti recomputeovan digest |
| 14 context dimensions | svaki forged field daje unproven/nula redova | `PROVEN`; mutation-sensitive |
| source-local edge recomputation | forged NOTE_ON ID se odbija | `PARTIALLY PROVEN`; samo jedna edge attack forma |
| observation/FK/integrity | count, FK, integrity i verifier membership | `PROVEN` za fixture |
| rehashed membership provenance | jedan provenance-field tamper se odbija | `WEAK/INCOMPLETE`; pet drugih semantic/source tampera prolaze |
| deterministic permutation | semantic digest i puni SQLite bytes jednaki | `PROVEN` za dva sourcea |
| atomic failure | duplicate source čuva prethodne bytes | `PROVEN` za pre-build failure; late-stage failure nije zasebno injected |
| static surface separation | capability i legacy token identity/provenance split | `PARTIALLY PROVEN`; substring scan nije data-flow proof |
| closed context domains | unknown role daje unproven | `PROVEN` za role; ostali closed domains nisu svi adversarialno enumerisani |
| style/tempo canonicalization | ekvivalentan style daje isti identity | `PROVEN` za navedeni normalization case |

Ukupno: novi testovi imaju stvarne assertione i tri originalna guard testa jesu mutation-sensitive. Slaba tačka nije odsustvo assertiona, nego preuzak verifier-tamper universe i self-generated authority fixture koji ne može dokazati production trust.

## Test i build rezultati

```text
targeted pytest -W error: 40 passed
full pytest -W error:     470 passed
Python compile:           PASS
git diff --check:         PASS
```

Broj prolaznih testova ne mijenja dva gore reprodukovana trust nalaza.

## Obavezne korekcije prije pass 3

1. Production accepted root mora dolaziti iz zasebnog neforgeable/read-only generation authority ugovora (ili paket mora eksplicitno ostati synthetic/library-only bez production Factory claimova). Običan caller digest nije dokaz porijekla.
2. Accepted schema-v2 authority mora omogućiti nezavisnu rekonstrukciju source classa, build/config identityja, punog lineage DAG-a/closurea, registry digesta i canonical subject/edge ID-jeva; digest-only lineage nije dovoljna za ovaj proof claim.
3. `verify_structural_registry()` mora zahtijevati i provjeriti accepted authority commitment te ponovo izračunati/usporediti najmanje source manifest, lineage, snapshot, subject registry, accepted schema/build digeste, subject semantic recorde i edge semantic recorde.
4. Dodati parametrizovane rehashed-tamper testove za svako prethodno navedeno polje. Svaka mutacija mora pasti čak i kada je lokalni `semantic_root` napadački ažuriran.
5. Dodati test koji dokazuje da self-minted schema-v2 DB + self-computed root ne može dobiti production Factory authority.
6. Dokumentovati stvarni CLI/GUI/build execution adapter ili zadržati tačnu oznaku `UNPROVEN / isolated library`.

## Final verdict

```text
RETURN
```

013C-S je popravio tri originalna direktna napada, ali complete-proof acceptance nije dozvoljen dok production trust-root origin i downstream rehashed-tamper verifikacija ostaju nedokazani. 013C-E ne smije početi.