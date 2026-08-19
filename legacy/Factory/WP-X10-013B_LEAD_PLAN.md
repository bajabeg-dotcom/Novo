# WP-X10-013B — Codex Lead Plan

Datum: 12. august 2026.  
Status: `LEAD_READY`  
Capability: `ANALYZE_ONLY / mutation NONE`

## TECHNICAL_PLAN

Implementirati izolovan USER_INPUT core bez povezivanja na `app.py`, GUI ili postojeći path/base64 upload. Svi trust elementi dolaze kroz eksplicitne injected portove; nedostajući port hard-failuje.

Paket je podijeljen na dva paralelna vlasništva:

1. private store/auth/key/reservation/lease/purge contract i referentni synthetic adapteri;
2. streaming ingest, pre-parse guard, canonical USER_INPUT subject graph, SQLite snapshot i verification orchestrator.

Exact target, calibration, anomaly, candidate, change simulation, repair i MIDI output ostaju zabranjeni.

## FILE_OWNERSHIP

### Implementer Store

- `rxoptimizer/user_input_store.py`
- `tests/test_user_input_store.py`

### Implementer Snapshot

- `rxoptimizer/user_input_snapshot.py`
- `tests/test_user_input_snapshot.py`

### Lead

- integracija interfejsa, acceptance pregled i dokumenti

### QA

- read-only nezavisni pregled; ne popravlja isti kod

Prihvaćeni WP-012/013A moduli ostaju read-only.

## PORT INTERFACES

`user_input_store.py` mora izložiti zatvorene protocol/ABC portove:

```text
AuthorizationVerifierPort.verify(auth_handle, operation)
  -> VerifiedAuthorizationScope

SealedUploadPort.stream_once(upload_handle, verified_scope)
  -> iterator[bytes] + seal_generation

TenantKeyProviderPort
  -> namespace_hmac / new_snapshot_payload_key / payload_hmac / audit_hmac

OperationalRegistryPort
  -> reserve / finish_create / acquire_lease / release_lease / request_purge /
     move_to_quarantine / finish_purge / recover

PrivatePackageStorePort
  -> create_stage / write_private_member / fsync_stage / publish_generation /
     open_active_read_only / quarantine / delete_quarantine / inventory
```

Production factory bez svih portova vraća fail-closed `PLATFORM_CAPABILITY_UNAVAILABLE`. Caller ne može konstruisati verified scope, birati authority klasu, key, digest, parse count ili lifecycle stanje.

Referentni adapteri u ovom paketu moraju biti jasno označeni `SYNTHETIC_TEST_ONLY`; ne smiju biti automatski dostupni production factoryju.

## SNAPSHOT INTERFACE

`user_input_snapshot.py` izlaže samo core orchestration API:

```text
create_user_input_snapshot(ports, auth_handle, upload_handle, policy)
verify_user_input_snapshot(ports, auth_handle, snapshot_handle)
request_user_input_snapshot_purge(ports, auth_handle, snapshot_handle)
run_user_input_purge_sweeper(ports)
```

Create radi streaming copy i SHA/count, rehash, frozen mandatory source guard, exactly-one parse samo poslije guarda, USER_INPUT-local HMAC subject graph, private SQLite/manifest/key slot i whole-package atomic publish.

Excluded šest-song/forbidden upload proizvodi odvojeni tenant-keyed receipt sa orchestration parse countom `0`, `NOT_CREATED` grafom i bez raw/package/handoff artefakta.

## IDENTITY I PRIVACY

- owner/session/upload dolaze samo iz verified server capabilityja;
- svi registry/cache/lease/store ključevi su composite tenant/session/upload/instance ključevi;
- namespace, snapshot, subject i private payload identitet su provider-versioned HMAC vrijednosti;
- text/SysEx raw i digest nikad nisu javni DB/API payload;
- display filename, absolute/temp path, URL i host metadata se ne čuvaju;
- identični bajtovi kod različitih ownera ili upload lokatora ne dijele namespace, package, key ni purge fate;
- standardni unauthorized/nonexistent odgovor je isti `NOT_AVAILABLE` oblik.

## GRAPH CONTRACT

USER_INPUT koristi `X10_USER_INPUT_SUBJECT_V1`, ne globalni Factory/Gold subject ID.

Minimalni subjecti:

```text
EVENT
NOTE
TRACK_CHANNEL
```

Minimalni edgeovi:

```text
TRACK_CHANNEL_CONTAINS_EVENT
TRACK_CHANNEL_CONTAINS_NOTE
NOTE_HAS_ON_EVENT
NOTE_HAS_OFF_EVENT  # samo dokaziv par
```

Event ID koristi authority domain, track indeks, stvarni event ordinal, tick, event kind/channel/type i private canonical data digest. Note pairing je deterministički; unmatched/ambiguous se evidentira, ne popravlja.

## RESOURCE I SECURITY LOCKOVI

- obavezni `X10_USER_INPUT_LIMITS_V1` iz Architect addenduma;
- streaming raw/session limit prije parsea;
- MIDI header/track declared-length i track-count preflight prije parsera;
- post-parse event/note/payload/tick/graph limiti prije publisha;
- parser invocation counter posjeduje orchestrator;
- recursive forbidden semantic scan;
- sanitized zatvoreni public error enum;
- no writer/encoder/export import ili poziv;
- package inventory dopušta samo original raw member, SQLite, private manifest/key slot;
- injected failure na svakoj publish/purge fazi čuva prethodnu generaciju i zatvara pristup nakon purge requesta.

## LIFECYCLE

Registry state machine je tačno:

```text
CREATING -> ACTIVE -> PURGE_REQUESTED -> ACCESS_REVOKED
         -> PHYSICAL_PURGE_PENDING -> PURGED
CREATING -> BUILD_FAILED
```

Purge request linearizuje revocation epoch i zabranjuje nove leaseove. Kada lease count postane nula, paket se uklanja iz active namespacea u quarantine. Sweeper je idempotentan; partial delete ostaje nedostupan i recovery nastavlja purge. Locator se ne reciklira.

## TEST ASSIGNMENTS

### Store testovi

- forged/caller-built auth odbijen;
- cross-owner lookup i existence oracle zatvoreni;
- same-locator idempotency/conflict i concurrent reservation;
- lease/purge race, no-new-lease poslije requesta, revocation epoch;
- quarantine/recovery/idempotent purge;
- package inventory, same-generation atomicity i injected failures;
- locator validation, no path/symlink/URL fallback;
- key provider/version/purge lifecycle.

### Snapshot testovi

- exactly-one parse accepted, zero parse excluded;
- svih šest SHA-eva pre-parse excluded i bez automatic route;
- malformed/oversized/declared-length/VLQ/resource napadi;
- ordinal/HMAC subject determinism i cross-owner unlinkability;
- private text/SysEx dictionary oracle nije izložen;
- unmatched notes bez popravke;
- no authority/training/evidence contamination;
- no writer/output i sanitized errors;
- byte/graph/package verification i corruption fail-closed;
- input-order determinism i atomic rollback.

## INTEGRATION CHECKLIST

- [ ] Retention je `UNTIL_EXPLICIT_MANUAL_PURGE`.
- [ ] Nema production `app.py`/path fallbacka.
- [ ] Portovi su obavezni i fail-closed.
- [ ] Snapshot i excluded receipt su različiti tipovi/API rezultati.
- [ ] USER_INPUT authority je `NONE/NEVER` za evidence/model/training.
- [ ] QA prolazi targeted/full pytest sa warning-as-error.
- [ ] Acceptance oznaka je samo `013B_USER_INPUT_SNAPSHOT_ACCEPTED`.
