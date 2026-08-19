# WP-X10-013B — Architect Addendum

Datum: 12. august 2026.  
Verzija: 1  
Nadopunjuje: `WP-X10-013B_ARCHITECT.md`  
Capability: `ANALYZE_ONLY`  
Mutation capability: `NONE`  
Status: `ARCHITECT_READY`

## 1. Zaključane Human Owner odluke

Human Owner je izabrao da se privatni originalni `USER_INPUT` MIDI i njegov immutable snapshot čuvaju do eksplicitnog ručnog purge zahtjeva. Nema automatskog isteka sadržaja.

Ostale odluke se zaključavaju konzervativno:

```text
RETENTION = UNTIL_EXPLICIT_MANUAL_PURGE
RAW_LIFETIME = SAME_AS_SNAPSHOT
DISPLAY_FILENAME = NOT_STORED
CROSS_SESSION_DEDUP = FORBIDDEN
AUTOMATIC_SIX_SONG_ROUTING = FORBIDDEN
STANDARD_RAW_ACCESS = FORBIDDEN
TRAINING_OR_EVIDENCE_PROMOTION = PERMANENTLY_FORBIDDEN_IN_013B
PURGE_RECEIPT_RETENTION = 30_DAYS
```

Raw artifact, semantic SQLite, manifest, private identity key, cache i spool pripadaju istoj purge sudbini. Standardni X10 API ostaje manifest/subject-only. Novi Human-approved work-package bio bi obavezan za bilo kakvu buduću promjenu authority politike.

## 2. Trusted owner/session authorization capability

`owner_scope_id`, `session_locator_id` i `upload_locator_id` ne dolaze iz caller payload-a. Platforma prije ulaska u 013B izdaje neforgeable server-side capability:

```text
UserInputAuthorizationCapabilityV1 {
  authenticated_principal_id
  owner_scope_id
  session_locator_id
  upload_locator_id
  allowed_operations
  issued_at
  expiry_or_session_epoch
  nonce
  capability_mac_or_platform_signature
}
```

Builder prima verificiranu capability instancu, ne slobodne ID stringove. Create, get, list, verify, lease i purge zahtijevaju odgovarajuću operaciju u capabilityju. Caller nikada ne može birati owner scope. Authorization se ponovo provjerava prije svakog filesystem/DB lookup-a i prije vraćanja SHA, snapshot ili subject identiteta.

Svaki storage, lock, cache, lease i API ključ je najmanje:

```text
(owner_scope_id, session_locator_id, upload_locator_id, snapshot_instance_id)
```

Unauthorized i nonexistent rezultat imaju isti sanitizovani javni odgovor `NOT_AVAILABLE`; nema globalnog lookup-a po content hash-u, snapshot ID-u ili subject ID-u. Raw SHA i interne identifikatore API vraća samo istoj verificiranoj owner/session capability instanci.

## 3. Authority-namespaced snapshot i subject identitet

Globalno poređenje USER_INPUT subject ID-jeva je zabranjeno. Svaki accepted upload dobija privatni namespace:

```text
snapshot_namespace_id = HMAC-SHA256(
  tenant_identity_key,
  canonical("X10_USER_INPUT_NAMESPACE_V1",
            owner_scope_id,
            session_locator_id,
            upload_locator_id,
            raw_byte_sha256,
            parser_config_sha256)
)
```

EVENT, NOTE, TRACK_CHANNEL i svi izvedeni subject ID-jevi su HMAC identiteti nad `snapshot_namespace_id`, subject tipom i kanonskim natural keyjem. Nijedan plain SHA natural-key ID nije javni ili cross-snapshot ključ. FK i edgeovi ostaju unutar istog namespacea; cross-namespace i cross-authority edge je hard fail.

DB, cache i API uvijek koriste composite `(snapshot_namespace_id, subject_id)`. Zabranjeni su globalni subject index, globalni subject cache i logovanje subject ID-a bez owner-scoped audit tokena. Dva ownera sa identičnim bajtovima dobijaju nepovezive namespace, snapshot i subject identitete.

Opaque ID inputi imaju ASCII base64url canonical form, 16–128 znakova, bez Unicode normalizacije, path separatora, whitespacea ili ponovne upotrebe unutar istog owner/session scopea.

## 4. Privacy-safe text i SysEx identitet

Nesoljeni javni SHA privatnog MIDI texta, lyric-a, copyrighta, markera, cue-a ili SysEx payload-a je zabranjen. Pri prihvatu se generiše random 256-bitni `snapshot_payload_key`, čuvan samo u privatnom package key slotu. Payload identity je:

```text
private_payload_digest = HMAC-SHA256(
  snapshot_payload_key,
  canonical("X10_PRIVATE_MIDI_PAYLOAD_V1", event_kind, payload_bytes)
)
```

Subject/event identitet koristi ovaj keyed digest, ali standardni API ne vraća digest, key, raw payload niti identifikator iz kojeg se može testirati pretpostavljeni plaintext. Public manifest navodi samo redigovan event kind i length bucket/count. Purge cijelog paketa uništava i key slot; poslije purgea nema graph-only zadržavanja.

Key verzija i KDF/algorithm ID ulaze u privatni semantic manifest. Key material, HMAC i raw payload nikad ne ulaze u log, exception, telemetry, filename, SQLite error ili javni receipt. Testovi moraju koristiti dictionary-friendly vrijednosti i dokazati da javni izlaz ne daje plaintext oracle.

## 5. Sealed upload i private content-store capability

013B prihvata samo platformom izdan `SealedUploadCapabilityV1`, vezan za authorization capability. Ona sadrži neforgeable descriptor/reference, expected seal generation i dozvolu za jednokratni read. Caller path, URL i archive path nisu dozvoljeni.

Platform adapter mora dokazati:

1. backing object je sealed prije builder poziva i ne može se zamijeniti tokom read-a;
2. read koristi descriptor/object handle, ne naknadni path resolution;
3. lokalni file adapter koristi private root, restrictive permissions, `O_NOFOLLOW`/ekvivalent, regular-file provjeru, exclusive create i otvoreni descriptor revalidation;
4. symlink, hardlink izvan private root-a, device, FIFO i path swap se odbijaju;
5. staged i final package direktorij su na istom filesystemu/atomic-store domenu;
6. svi fileovi su close/fsyncovani, zatim staged directory i parent directory durability-syncovani prije/poslije atomic renamea;
7. package inventory i generation digest obuhvataju raw artifact, SQLite, private manifest i key slot.

Builder nikada ne reopen-uje caller path. Temp imena su random, privatna i bez originalnog filenamea. Atomic publish garantuje visibility jedne generacije; secure erase izvan platformskih garancija se ne obećava.

## 6. Pre-parse exclusion receipt

Guard registry/policy snapshot je mandatory, frozen i versioned za svaki build. Šest-song SHA skup i poznati optimizer/repaired hashovi nisu caller-optional.

Pre-parse excluded put proizvodi zaseban canonical receipt, nikad accepted snapshot:

```text
ExclusionReceiptV1 {
  owner_private_receipt_id
  owner_scope_id
  session_locator_id
  upload_locator_id
  raw_byte_sha256
  raw_byte_count
  guard_policy_digest
  terminal_reason
  orchestration_parse_invocation_count = 0
  subject_graph_status = NOT_CREATED
  automatic_route_status = NOT_INVOKED
  package_inventory_digest
  retention_state
}
```

`owner_private_receipt_id` i receipt digest su HMAC-ovani tenant audit keyjem. Orchestrator posjeduje append-only parse invocation counter; parser callback se registruje tek poslije successful guard gatea. Receipt inventory mora kanonski dokazati odsustvo raw retained artifacta, parse manifest/rows, subject DB/graph, MIDI outputa i Delay/Terca handoffa. Staged raw kopija se briše prije terminalnog receipta; receipt zadržava samo navedeni minimalni metadata skup do ručnog purgea ili 30 dana nakon purge completiona.

Stored `parse_count=0` bez orchestration counter commitmenta nije dovoljan dokaz. Exclusion receipt nije dostupan accepted snapshot API-jem i nema general X10 snapshot ID.

## 7. Retry, duplicate i locator collision semantika

Owner/session/upload locator ima unique reservation u trusted operational registryju:

- isti locator + isti raw SHA/count + ista policy/parser generacija: idempotentno vraća isti accepted snapshot ili receipt;
- isti locator + različiti bajtovi, policy identity ili parser identity: `LOCATOR_CONTENT_CONFLICT`, bez overwritea;
- različiti upload locator + isti bajtovi: uvijek zaseban private snapshot, key, namespace i purge fate;
- drugi owner/session sa istim bajtovima: nema dedup-a niti existence signala;
- paralelni create za isti locator: jedan osvaja compare-and-set reservation; drugi čeka terminalno stanje i dobija isti rezultat ili sanitizovani conflict;
- content-store/cache collision: identity i full committed inventory se provjeravaju; mismatch je hard fail, nikad reuse.

Failed build reservation može se retryati samo sa istom request generation i istim byte/policy identityjem; nova generacija zahtijeva novi upload locator. Originalni locator se ne reciklira poslije purgea.

## 8. Linearizable lease i purge state machine

Operational lifecycle je zatvoren:

```text
CREATING
  -> ACTIVE
  -> PURGE_REQUESTED
  -> ACCESS_REVOKED
  -> PHYSICAL_PURGE_PENDING
  -> PURGED

CREATING -> BUILD_FAILED
```

Jedan transactional registry lock/CAS linearizuje lease acquisition i purge request:

1. lease se izdaje samo iz `ACTIVE` i povećava generation-bound lease count;
2. purge request atomски mijenja `ACTIVE -> PURGE_REQUESTED`, incrementuje revocation epoch i od tog trenutka zabranjuje nove leaseove;
3. svi postojeći čitači moraju validirati revocation epoch prije svakog package open/DB transactiona i završiti/cancelovati lease; nema publish rezultata nakon revocationa;
4. kada lease count dođe na nulu, paket se atomic renameom uklanja iz active namespacea u private purge quarantine i stanje postaje `ACCESS_REVOKED`;
5. cache/spool registry se zamrzava; sweeper idempotentno briše cijeli package, key slot i sve registrovane kopije;
6. tek kompletan inventory reconciliation daje `PURGED`.

Ako crash nastane poslije revocationa/renamea, recovery nastavlja iz quarantine inventoryja. Paket se nikad ne vraća u `ACTIVE`. Djelimični physical delete ostaje `PHYSICAL_PURGE_PENDING`, ali je već nedostupan svim standardnim API-jima. Purge iste instance je idempotentan. Purge ne obećava atomsku fizičku secure-delete operaciju; garantuje atomsku zabranu pristupa i eventualno cijelo-package brisanje.

Minimalni receipt nakon completiona sadrži samo tenant-keyed purge receipt ID, lifecycle/config version, request/completion vrijeme, final state i inventory-reconciled boolean. Ne sadrži raw/content/subject hash, filename, path ili MIDI metadata i briše se automatski nakon 30 dana.

## 9. Resource i parser granice

Production acceptance koristi zatvoreni `X10_USER_INPUT_LIMITS_V1`:

```text
max_raw_bytes                  = 33_554_432   # 32 MiB
max_session_retained_bytes     = 536_870_912  # 512 MiB
max_tracks                     = 256
max_events_total               = 2_000_000
max_notes_total                = 1_000_000
max_events_per_track           = 1_000_000
max_declared_track_bytes       = 33_554_432
max_text_payload_bytes_event   = 1_048_576
max_sysex_payload_bytes_event  = 4_194_304
max_cumulative_private_payload = 16_777_216
max_vlq_bytes                  = 4
max_absolute_tick              = 9_007_199_254_740_991
max_graph_subjects             = 4_000_000
max_graph_edges                = 8_000_000
max_staged_package_bytes       = 1_073_741_824
max_parser_wall_seconds        = 60
max_builder_wall_seconds       = 180
max_peak_event_batch           = 65_536
```

Declared chunk/track length mora stati u stvarno preostale raw bajtove. Overflow, allocation-before-bound-check, noncanonical/oversized VLQ, event/note/edge limit, timeout ili quota prekoračenje daje `RESOURCE_LIMIT_EXCEEDED`, bez parcijalnog grafa ili publisha. CPU/wall watchdog je server-side i fail-closed; semantic rezultat ne zavisi od tačnog elapsed vremena osim terminalnog resource statusa.

Parser config digest zaključava header/format policy, PPQ/SMPTE policy, chunk handling, running status, same-tick order, zero-velocity note-off, note pairing, text byte policy, integer/VLQ limite, canonical serialization, library/runtime compatibility i sve gore navedene limite. Locale, implicit text decoding i binary float ne smiju mijenjati graf.

## 10. Sanitizovani error contract

Javni create/read/verify/purge errori pripadaju zatvorenom skupu:

```text
NOT_AVAILABLE
INVALID_OR_UNSUPPORTED_MIDI
RESOURCE_LIMIT_EXCEEDED
UPLOAD_CAPABILITY_REJECTED
LOCATOR_CONTENT_CONFLICT
POLICY_REJECTED
OPERATION_IN_PROGRESS
INTERNAL_OPERATION_FAILED
```

Javni error nema raw bajtove, SHA, subject ID, filename, text/SysEx, host/temp path, SQL, parser offset, stack trace, owner ID druge instance niti razliku unauthorized/nonexistent. Privatni audit zapis koristi tenant-keyed opaque operation ID i redigovan phase/reason enum; exception chain se sanitizuje prije logovanja. Metrics labels su bounded enumi, nikad locator ili sadržaj.

## 11. Verification i package semantics

Pošto Human Owner čuva raw i snapshot zajedno do ručnog purgea, prihvaćen je samo:

```text
FULL_RAW_AND_GRAPH_VERIFIED
```

`GRAPH_ONLY_VERIFIED_RAW_PURGED` nije dozvoljen u 013B. Nedostajući raw, key slot ili inventory član znači package corruption i fail-closed `NOT_AVAILABLE`; nema djelimičnog snapshot korištenja.

Verify ponovo provjerava authorization, lifecycle `ACTIVE`, full package inventory/generation digest, raw SHA/count, SQLite integrity/FK, semantic digest, keyed subject graph i authority policy. Writer/export entrypointi su nedostupni; package inventory odbija `.mid`/`.midi` output osim immutable originalnog raw artifacta čiji je internal content-store tip eksplicitno `ORIGINAL_UPLOAD_BYTES`, ne MIDI export.

## 12. Revidirani acceptance gateovi

Lead i QA moraju dokazati najmanje:

1. server-side auth capability; caller-spoofed owner/session/upload je odbijen;
2. identični bajtovi kod dva ownera daju nepovezive namespace/subject ID-jeve i bez existence oraclea;
3. text/SysEx koristi keyed private identity, bez javnog digest/plaintext oraclea;
4. sealed upload descriptor sprečava symlink, hardlink/path swap i TOCTOU;
5. svih šest song SHA vrijednosti i forbidden registry membership daju canonical pre-parse receipt, stvarni parser invocation count `0`, bez graph/package/handoffa;
6. retry, parallel create, same-locator conflict i različiti locator semantics su deterministični;
7. purge request linearizovano zatvara nove leaseove, atomic revoke/rename uklanja paket iz aktivnog namespacea, a crash recovery završava whole-package deletion;
8. svaki resource limit i malicious declared length fail-closed vraća sanitizovani status;
9. raw i graph imaju zajednički manual-purge lifecycle i samo full verification status;
10. authority contamination digesti ostaju byte-identični, writer/export invocation count je `0`;
11. capability ostaje `ANALYZE_ONLY`, mutation/model/evidence/training authority `NONE/NEVER`;
12. nema calibration, anomaly, candidate, target, delta, simulation change, repair ili MIDI output polja/API-ja.

QA mora uključiti injected failure testove za reservation, upload copy, rehash, guard, parse, SQLite commit, fsync, publish rename, lease revocation, quarantine rename, cache deletion i final inventory reconciliation.

## 13. Granica narednog rada

Ovaj addendum zatvara Audit B1–B9 i R1–R8 samo za immutable USER_INPUT snapshot. Ne autorizuje calibration envelope, leave-one-target-out comparison, anomaly proof, target, proposal, simulation promjene, repair, preview ili output.

```text
CAPABILITY = ANALYZE_ONLY
MUTATION = NONE
MODEL_AUTHORITY = NONE
EVIDENCE_AUTHORITY = NONE
TRAINING_ELIGIBILITY = NEVER
MIDI_OUTPUT = NONE
```

## 14. Architect verdict

```text
ARCHITECT_READY
```