# WP-X10-013B — Independent Codex QA Pass 3

Datum: 12. august 2026.  
Prethodni verdict: `RETURN`  
Capability: `ANALYZE_ONLY`  
Mutation capability: `NONE`

## Verdict

```text
ACCEPT
```

Pass-2 nalazi su zatvoreni. Hard parser timeout sada koristi killable child-process executor, a whole-package purge uništava snapshot-local payload key, rediguje raw reservation identity i zadržava samo minimalni no-reuse tombstone/receipt.

## Hard timeout provjera

Nezavisna reprodukcija koristila je parser sa beskonačnom petljom, bez ikakvog manual release mehanizma.

Rezultat:

```text
status                    = RESOURCE_LIMIT_EXCEEDED
bounded return            = približno 0,16 s uz test timeout cap 0,05 s
novi active child procesi = 0
pending quota reservation = 0
active packages           = 0
staging packages          = 0
```

Executor nakon deadlinea radi terminate/join i kill fallback, zatvara IPC i ne dopušta parser rezultatu da nastavi snapshot build.

## Purge/key lifecycle provjera

Provjerene su tri nezavisne crash granice:

1. poslije fizičkog deletea, prije key destructiona;
2. poslije key destructiona, prije durable registry marka;
3. poslije durable key-destroyed marka, prije `finish_purge`.

Svaki slučaj je idempotentno nastavljen do:

```text
state                    = PURGED
registry.identity        = null
registry.generation      = null
payload key live         = false
active/quarantine package= absent
drugi sweeper prolaz     = OK, purged=0
```

Isti owner/session/upload locator se nakon purgea ne reciklira; novi sealed upload daje `LOCATOR_CONTENT_CONFLICT`. Destroyed-generation marker sprečava ponovno kreiranje prethodnog snapshot-local ključa, ali ne zadržava raw SHA, byte count, seal generation niti key material.

## Regresija prethodnih nalaza

- trusted ingest contract zaključava guard registry, parser/config i canonical limits;
- public create nema caller policy/parser/limits surface;
- svih šest zabranjenih song SHA vrijednosti ostaju pre-parse exclusion sa `parse_count=0`, bez grafa i handoffa;
- identical-byte cross-owner snapshoti ostaju privatno unlinkable;
- same-locator/new-seal retry je idempotentan i byte-identičan;
- post-publish/pre-registry-finish pad se oporavlja istom generacijom i payload keyjem;
- accepted inventory mismatch, raw corruption, payload-key corruption i manifest corruption daju `NOT_AVAILABLE`;
- session quota, builder watchdog i disk-backed peak-batch limit su izvršni;
- unmatched note događaji ostaju evidentirani bez repaira;
- lease revocation, quarantine, physical purge i repeated sweeper su fail-closed/idempotentni;
- USER_INPUT ostaje `NONE/NEVER` za evidence/model/training;
- nema `app.py`, calibration, anomaly, target, proposal, writer ili MIDI output semantike.

## Izvršena verifikacija

```text
Targeted pytest -W error: 54 passed
Full pytest -W error:     430 passed
Python compile:           passed
git diff --check:         passed
```

## Acceptance granica

Tehnički acceptance je isključivo:

```text
013B_USER_INPUT_SNAPSHOT_ACCEPTED
```

Ovaj QA ne daje production platform adapter, calibration, anomaly proof, exact target, proposal, simulation-change, MIDI mutation/output, Pa800 dokaz ili release autoritet.