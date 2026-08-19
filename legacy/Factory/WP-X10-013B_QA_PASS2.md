# WP-X10-013B — Independent Codex QA Pass 2

Datum: 12. august 2026.  
Prethodni verdict: `RETURN`  
Capability: `ANALYZE_ONLY`  
Mutation capability: `NONE`

## Verdict

```text
RETURN
```

Pass-1 nalazi o caller-controlled policy/parser/limits, idempotentnom retryju, package verificationu, purge crash recoveryju i batch/session quota ugovoru su uglavnom zatvoreni. Dva preostala contract-critical nalaza sprečavaju `ACCEPT`.

## Potvrđene pass-1 popravke

- Public create više nema caller `policy`, `parser` ni `limits` argument.
- Guard registry, parser i canonical limits dolaze kroz attested trusted-ingest port.
- Fake caller parser/empty-graph put više nije dio public API-ja.
- Novi sealed handle sa istim locatorom i identičnim bajtovima vraća isti snapshot i byte-identičnu package generaciju.
- Injected pad nakon publish-a, prije registry finish-a, može se ponoviti i završava accepted snapshotom.
- Registry accepted inventory digest se poredi sa trenutnim package inventoryjem.
- Payload-key i manifest-count korupcija daju `NOT_AVAILABLE`, čak i kada test nasilno osvježi registry inventory commitment.
- Raw/package korupcija, cross-owner lookup i nonexistent snapshot imaju isti javni `NOT_AVAILABLE` oblik.
- Post-delete/pre-finish purge crash se idempotentno dovršava do `PURGED`.
- Session retained quota i disk-backed graph spool sa peak-batch granicom postoje i testirani su.
- Šest-song/forbidden guard ostaje pre-parse sa stvarnim `parse_count=0`, bez graph/handoff/outputa.
- Nema `app.py`, target, calibration, proposal, writer ili MIDI output integracije.

## Preostali obavezni nalazi

### QA-013B-P2-1 — Parser wall timeout ne prekida zaglavljeni parser

`_trusted_parse()` poziva parser sinhrono u istom threadu, a watchdog provjerava deadline tek nakon što se `parser(raw)` vrati. `TrustedWatchdogPort` dobija samo `start/checkpoint/finish`; nije vlasnik parser izvršenja i ugovor mu ne daje pouzdan način da prekine callback koji se nikada ne vraća.

Adversarial reprodukcija koristi parser koji čeka na event:

```text
parser je ušao i blokirao
trusted clock je pomjeren daleko preko max_parser_wall_seconds
create poziv je i dalje živ — timeout nije vratio fail-closed rezultat
tek nakon ručnog oslobađanja parsera rezultat postaje RESOURCE_LIMIT_EXCEEDED
```

Znači da `max_parser_wall_seconds` trenutno mjeri zakašnjeli povrat, a ne ograničava wall time/resource exhaustion. Parser koji beskonačno visi može beskonačno zadržati worker, quota reservation i staged ingest operaciju.

Potrebno: izvršiti parser kroz interruptible/killable trusted executor sa hard deadlineom i bounded cleanupom, ili proširiti trusted parser port tako da on sam garantuje i dokazuje timeout. Test mora imati parser koji se ne vraća i dokazati da create završi unutar ograničenog vremena bez ručnog releasea.

### QA-013B-P2-2 — Whole-package purge ne uništava snapshot-local key niti rediguje raw identity

Purge briše filesystem package i quota zapis, ali interface nema key-destruction/revocation operaciju. `SyntheticTenantKeyProvider._payload_generations` poslije uspješnog purgea i dalje čuva puni snapshot-local 256-bitni payload key. Operational registry takođe zadržava cijeli `ReservationIdentity`, uključujući raw SHA-256, byte count i seal generation, iako je stanje `PURGED`.

Adversarial reprodukcija poslije `run_user_input_purge_sweeper(...)=OK` potvrđuje:

```text
snapshot payload key       -> i dalje prisutan u key provideru
raw_byte_sha256            -> i dalje prisutan u PURGED registry recordu
seal_generation            -> i dalje prisutan u PURGED registry recordu
```

To krši ugovor da private identity key dijeli package purge sudbinu i da minimalni post-purge receipt/tombstone ne zadržava raw/content hash ili MIDI identity metadata.

Potrebno:

- dodati idempotentni `destroy_snapshot_payload_key(scope/generation)` ili ekvivalentan KMS revocation port;
- key destruction uključiti u durable purge state machine prije `finish_purge`;
- `finish_purge` redigovati/odvojiti `ReservationIdentity`, zadržavajući samo minimalni tenant-keyed no-reuse tombstone/receipt;
- dodati crash testove prije/poslije key destructiona i registry redactiona;
- dokazati da ponovljeni sweeper ne vraća key niti raw identity.

## Izvršena verifikacija

```text
Targeted pytest -W error: 48 passed
Full pytest -W error:     424 passed
Python compile:           passed
git diff --check:         passed
```

Nezavisne reprodukcije:

```text
same-locator new-handle retry       -> PASS
post-publish failure recovery       -> PASS
accepted inventory corruption      -> rejected
payload-key corruption              -> rejected
manifest corruption                 -> rejected
post-delete purge recovery          -> PASS
hard parser timeout                 -> FAIL: call remains blocked
payload-key destruction on purge    -> FAIL: key retained
raw identity redaction on purge     -> FAIL: SHA/seal retained
```

## Return kriterij

Implementer treba zatvoriti QA-013B-P2-1 i QA-013B-P2-2 ciljanim adversarial testovima. Nakon toga je potreban QA pass 3. Ovaj verdict ne daje production-platform, calibration, anomaly, proposal, mutation, Pa800 niti release autoritet.