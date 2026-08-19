# WP-X10-013B — Independent Architecture Re-audit

Datum: 12. august 2026.  
Predmet: `WP-X10-013B_ARCHITECT.md`, `WP-X10-013B_AUDIT.md` i `WP-X10-013B_ARCHITECT_ADDENDUM.md`  
Capability: `ANALYZE_ONLY`  
Mutation capability: `NONE`

## Sažetak

Architect addendum dovoljno zatvara prethodne B1–B9 blokere i R1–R8 rizike da Codex Lead može napraviti tehnički plan. Human Owner odluka je zaključana na čuvanje originalnog `USER_INPUT` MIDI-ja i cijelog immutable paketa do eksplicitnog ručnog purgea. Addendum dalje bira konzervativne privacy, authority, quota, retry, verification i purge vrijednosti koje ne proširuju muzičku ili release vlast.

Workspace trenutno nema gotov produkcijski trusted-auth, sealed-upload, tenant-key/KMS, lease registry ili purge sweeper primitive. Postojeći `app.py` upload prima filename/payload i nije prihvatljiva 013B trust granica. To nije razlog da se ugovor ponovo otvori, ali jeste obavezni implementation lock: 013B mora prvo definisati zatvorene adapter interfejse i fail-closed referentnu implementaciju/test doubles; ne smije postojeći GUI/API upload proglasiti trusted primitiveom niti javno spojiti paket dok platform adapter nije dokaziv.

## Ponovna provjera blokera

### B1 — Human Owner storage/privacy odluke: zatvoreno

Zaključani su manual purge retention, zajednički raw/snapshot lifetime, zabrana display filenamea i cross-session dedupa, 30-dnevni minimalni purge receipt poslije completiona, zabrana automatskog šest-song routinga, zabrana standardnog raw pristupa i trajna zabrana evidence/training promocije u 013B. Resource i session kvote su versioned u `X10_USER_INPUT_LIMITS_V1`. Secure erase se korektno ne obećava.

### B2/B3 — Trusted authorization i tenant namespace: zatvoreno uz adapter lock

Owner/session/upload više nisu caller payload. Sve operacije zahtijevaju server-side capability i composite scope. Snapshot namespace i subject ID-jevi koriste tenant-keyed HMAC; globalni hash/subject lookup, cache i existence signal su zabranjeni. Unauthorized i nonexistent daju isti javni `NOT_AVAILABLE` odgovor.

Implementacija mora verificirati capability kriptografski ili preko neforgeable platform objecta prije bilo kakvog lookup-a. Plain dataclass koji caller može konstruisati nije trusted capability.

### B4 — Privatni MIDI payload identitet: zatvoreno uz key-lifecycle lock

Text/SysEx identitet koristi random snapshot-local 256-bitni HMAC ključ. Standardni API ne vraća raw payload, keyed digest, key ni oracle-identifikator. Key slot dijeli package purge sudbinu.

Lead mora zaključati `key_id`, algorithm/KDF version i provider provenance u privatnom manifestu. Tenant identity/audit key ne smije doći iz caller inputa, environment defaulta ili determinističke izvedenice privatnog MIDI sadržaja. Stari provider key mora ostati provjerljiv do purgea pripadajućih paketa ili se paket mora fail-closed označiti nedostupnim; tiha re-identifikacija drugim ključem je zabranjena.

### B5 — Linearizable lease/purge: zatvoreno

CAS/transaction state machine linearizuje lease i purge, revocation epoch zatvara nove leaseove, active package se uklanja atomic renameom tek nakon nula leaseova, a idempotentni sweeper i inventory reconciliation završavaju fizički purge. Crash poslije revocationa ne vraća paket u `ACTIVE`.

### B6 — Sealed upload/content-store: ugovor zatvoren, primitive mora biti implementiran

Addendum zahtijeva platform-issued one-read descriptor capability, no caller path/URL, descriptor revalidation, private root, restrictive permissions, no-follow, regular-file i hardlink/path-swap zaštitu, exclusive create, same-filesystem staging, fsync i atomic rename.

Pošto takav primitive nije pronađen u workspaceu, Lead ne smije koristiti postojeći `app.py` filename/path upload kao zamjenu. Production adapter bez dokazive seal generacije ili hardlink/private-root garancije mora vratiti `UPLOAD_CAPABILITY_REJECTED`. Test-only in-memory capability mora biti jasno označen `SYNTHETIC_TEST` i nedostupan production factoryju.

### B7 — Pre-parse exclusion dokaz: zatvoreno

Canonical tenant-keyed receipt obavezuje frozen guard policy, raw SHA/count, terminalni razlog, orchestration parse invocation counter `0`, `NOT_CREATED` graph, `NOT_INVOKED` route i inventory odsustva raw/parse/graph/output artefakata. Parser callback se registruje tek poslije guard gatea. Receipt nema accepted/general-X10 snapshot ID.

### B8 — Retry/collision: zatvoreno

Same-locator/same-identity retry je idempotentan; same-locator/different bytes, policy ili parser identity je hard conflict; različiti locator uvijek daje privatno odvojenu instancu. Paralelni create koristi owner/session-scoped reservation/CAS, a locator se poslije purgea ne reciklira.

### B9 — Resource exhaustion: zatvoreno

Versioned limit set pokriva raw/session/staged bytes, tracks, events, notes, declared lengths, text/SysEx, VLQ, ticks, graph size, batch, parser i builder wall time. Bound check mora prethoditi allocationu. Prekoračenje daje zatvoreni `RESOURCE_LIMIT_EXCEEDED` bez djelimičnog grafa/publisha.

## Ponovna provjera dodatnih rizika

- R1: owner-scoped capability i indistinguishable `NOT_AVAILABLE` zatvaraju standardni existence oracle; testovi moraju porediti i response shape, ne obećavati savršenu konstantnu mrežnu latenciju.
- R2: parser digest sada obuhvata ordering, running status, zero-velocity note-off, pairing, PPQ/SMPTE, integer/VLQ, payload i serialization pravila.
- R3: opaque ID canonical form, dužina i no-reuse pravilo su zaključani.
- R4: package inventory/generation digest, fsync granice i same-domain atomic rename razdvajaju visibility od eventualnog physical purgea.
- R5: frozen guard registry je mandatory i nije caller-optional.
- R6: raw i graph imaju zajednički lifecycle; jedini dozvoljeni verify status je `FULL_RAW_AND_GRAPH_VERIFIED`.
- R7: display filename se ne čuva.
- R8: writer/export API mora biti nedosegljiv, invocation count `0`, a inventory odbija MIDI output osim interno označenog originalnog upload artefakta.

## Obavezni implementation lockovi

Codex Lead mora prenijeti sljedeće kao nepromjenjive acceptance uslove:

1. Novi 013B modul ostaje izolovan od javnog GUI/API upload puta dok trusted platform adapter nije stvarno dostupan i testiran.
2. Auth, sealed-upload, tenant-key provider, operational registry/CAS i content-store su eksplicitni injected portovi; nedostajući production port daje fail-closed rezultat, nikad lokalni implicitni fallback.
3. Caller ne predaje authority ID, filesystem path, key, digest, source class, terminal status, parse count ili inventory truth.
4. Jedan accepted build radi exactly one MIDI parse iz rehashovanog immutable artifacta; excluded build ima stvarni orchestration counter `0`.
5. Svaki DB/cache/lease/lock lookup je composite-scoped; nema globalnog lookup-a po raw SHA, snapshot ID-u ili subject ID-u.
6. Snapshot-local privacy key i tenant keys imaju versioned provider/key ID i isti purge/verification ugovor; key material nikad nije semantic/public payload.
7. Public errori ostaju isključivo zatvoreni sanitizovani enum; privatni audit sadrži samo tenant-keyed operation ID i bounded phase/reason.
8. Reservation, package publish, lifecycle registry i quarantine registry imaju eksplicitne crash-recovery testove; filesystem rename nije predstavljen kao secure erase.
9. Exclusion receipt i accepted snapshot su različiti schema/API tipovi bez zajedničkog success ID-a.
10. Resource checks se rade streaming/before-allocation; timeout nije muzički ili semantički signal.
11. Package publish je whole-generation atomic: raw, SQLite, private manifest, key slot i inventory pripadaju istoj generaciji.
12. Factory/Gold/evidence/training/calibration/consensus/proposal storeovi ostaju read-only i byte-identični; šest pjesama nemaju automatic Delay/Terca handoff.
13. Recursive schema/API/payload scan zabranjuje calibration, anomaly, candidate, target, delta, change simulation, repair, mutation i MIDI output semantiku.
14. QA mora izvršiti sve injected-failure, cross-owner, dictionary-payload, malicious MIDI, retry/race, lease/purge, no-writer i contamination testove iz addenduma prije `ACCEPT`.

## Preostala granica

Re-audit ne tvrdi da workspace već ima production platform capability niti da je 013B implementiran. Odobrava samo prelazak na Lead plan i ciljanu implementaciju pod gore navedenim lockovima. Tehnički QA acceptance neće dati evidence/training, calibration, anomaly, target, simulation-change, MIDI mutation/output, Pa800 ili release autoritet.

## Verdict

```text
AUDIT_REVIEWED
```