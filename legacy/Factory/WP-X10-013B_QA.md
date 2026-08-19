# WP-X10-013B — Independent Codex QA

Datum: 12. august 2026.  
Predmet: immutable `USER_INPUT` snapshot, private store i lifecycle  
Capability: `ANALYZE_ONLY`  
Mutation capability: `NONE`

## Verdict

```text
RETURN
```

Paket ostaje izolovan od `app.py`, writer/output i Factory/Gold authority putanja, a postojeći testovi prolaze. Ipak, nezavisne adversarial provjere nalaze contract-critical propuste u trusted policy/parser granici, retry/atomic recoveryju, full verificationu i purge crash recoveryju. `013B_USER_INPUT_SNAPSHOT_ACCEPTED` se još ne smije dodijeliti.

## Obavezni nalazi

### QA-013B-1 — Guard policy, parser identity i limits su caller-controlled

`create_user_input_snapshot()` javno prima proizvoljni `policy` i proizvoljni `parser` callback. `_freeze_policy()` samo sintaktički kopira caller-provided six-song/forbidden skup, parser digest/version i limite. Nijedan trusted injected port ne potvrđuje canonical guard registry, parser implementation/config niti gornje resource granice.

Posljedice:

- caller može izostaviti stvarni šest-song SHA iz lokalno konstruisanog skupa;
- caller može proširiti limite mimo `X10_USER_INPUT_LIMITS_V1`;
- caller može deklarisati proizvoljni parser digest, a predati drugi callback;
- validni MIDI sa notama može biti prihvaćen kao prazni graf ako callback vrati `MidiFile(..., [[]])`.

Adversarial reprodukcija je vratila `SNAPSHOT_ACCEPTED_USER_INPUT`, `event_count=0` i `FULL_RAW_AND_GRAPH_VERIFIED` za MIDI koji stvarno sadrži note.

Potrebno: frozen source-guard/parser/limits moraju doći kroz neforgeable platform port/capability; public core ne smije prihvatati slobodni parser callback ili caller-built policy. Parser implementation/config digest mora biti provjerljivo vezan za stvarno pozvani parser.

### QA-013B-2 — Public same-locator retry nije idempotentan

`ReservationIdentity` uključuje `seal_generation`. Synthetic sealed-upload port za svaki novi sealed handle generiše novu vrijednost, dok je stari handle one-read-only. Zato nakon uspješnog createa jedini praktični retry — novi sealed handle sa istim locatorom i identičnim bajtovima — završava kao `LOCATOR_CONTENT_CONFLICT`.

Adversarial reprodukcija:

```text
create #1, isti locator/bajti -> SNAPSHOT_ACCEPTED_USER_INPUT
create #2, novi sealed handle, isti locator/bajti/policy/parser -> LOCATOR_CONTENT_CONFLICT
```

Ovo nije same-locator/same-byte/policy/parser idempotency iz Addenduma. Dodatno, publish se izvršava prije `registry.finish_create()`. Pad nakon publisha ostavlja aktivni paket uz `BUILD_FAILED`; retry generiše novi random payload key/key slot, pa se postojeća generacija više ne može byte-identično prihvatiti i collision recovery može ostati trajno zaglavljen.

Potrebno: zaključati request-generation/retry identitet koji je ponovljiv bez recikliranja locatora; definisati recoverable publish transaction. Random snapshot key mora biti rezervisan/reuseovan za istu create generaciju ili orphan published generation mora biti deterministički reconciled/quarantined prije retrya.

### QA-013B-3 — `FULL_RAW_AND_GRAPH_VERIFIED` ne verificira cijeli immutable paket

Verification računa trenutni inventory, ali ga ne poredi sa accepted `inventory_digest` iz registryja. Takođe ne rekonstruiše graph iz raw bajtova niti provjerava payload HMAC key protiv privatnih event identiteta. Manifest polja izvan `run` semantic digesta nisu potpuno reconciled sa SQLite sadržajem.

Dvije nezavisne korupcije i dalje vraćaju `FULL_RAW_AND_GRAPH_VERIFIED`:

1. zamjena `payload_key.slot` key materiala drugim random 32-byte ključem uz isti key ID;
2. promjena `private_manifest.json.subject_count` na proizvoljnu netačnu vrijednost.

Potrebno: verificirati accepted generation commitment iz registryja; canonicalno reconciliirati cijeli privatni manifest, key-slot provider/key metadata, stvarne subject/edge countove i SQLite redove. Payload key mora dokazivo odgovarati private payload HMAC identitetima, idealno kontrolisanim single reparse/rebuild verify ugovorom ili ekvivalentnim committed proofom.

### QA-013B-4 — Purge recovery se trajno zaglavi nakon crasha poslije fizičkog deletea

Sweeper briše quarantine directory prije `registry.finish_purge()`, bez prethodnog durable `PHYSICAL_PURGE_PENDING`/inventory reconciliation koraka. Ako proces padne poslije `delete_quarantine()` a prije `finish_purge()`, registry ostaje `ACCESS_REVOKED`. Sljedeći sweeper pokušava ponovo `package.quarantine()`, ali active i quarantine paket više ne postoje, pa vraća `INTERNAL_OPERATION_FAILED`; record ostaje u `recover()` zauvijek.

Adversarial reprodukcija:

```text
purge request -> paket u quarantine
simulirani crash: delete_quarantine završen, finish_purge nije pozvan
sweeper retry -> INTERNAL_OPERATION_FAILED, purged=0
registry.recover() -> isti record i dalje prisutan
```

Potrebno: durable state transition prije deletea, tolerantna provjera da odsustvo active/quarantine paketa nakon revocationa predstavlja reconciled physical deletion, te idempotentni nastavak do `PURGED`. Dodati injected-failure test za svaku granicu quarantine/mark-pending/delete/reconcile/finish.

### QA-013B-5 — Versioned resource ugovor nije kompletno izvršan

Definisani, ali neprimijenjeni su najmanje:

- `max_session_retained_bytes`;
- `max_parser_wall_seconds`;
- `max_builder_wall_seconds`;
- `max_peak_event_batch`.

Pošto je cijeli raw poslije spoola učitan u jedan `bytes`, a svi subjecti/edgeovi se drže u listama do finalnog SQLite builda, `max_peak_event_batch` nije stvarno mjeren ni enforced. Caller-controlled `limits` dodatno omogućava zaobilaženje nominalnih granica.

Potrebno: trusted immutable limits config, session quota port, provjerljivi timeout/cancellation ugovor i stvarno batch/disk-backed graph materijalizovanje ili korektno sužavanje Architect acceptance ugovora prije implementacije.

## Pozitivne provjere

- Synthetic auth attestation i composite owner/session/upload scoping odbijaju jednostavno forged scope korištenje.
- Identical-byte uploadi u različitim owner scopeovima dobijaju različit namespace i instance ID.
- Text/SysEx plaintext i obični SHA dictionary locator nisu izloženi kroz testirani result/manifest/SQLite payload.
- Šest-song/forbidden test fixtures prolaze guard prije poziva parser callbacka kada je odgovarajući skup prisutan u predatom policy objektu.
- Unmatched note-on/off se evidentiraju bez repaira.
- Nema `app.py`, GUI, target, calibration, proposal, writer ili MIDI output integracije u pregledanom API-ju.
- Public failure oblik ne vraća privatne exception detalje.

## Izvršena verifikacija

```text
Targeted pytest -W error: 33 passed
Full pytest -W error:     409 passed
Python compile:           passed
git diff --check:         passed
```

Adversarial reprodukcije izvan postojećeg suitea:

```text
forged parser graph       -> accepted + FULL verification
payload key corruption    -> FULL verification
manifest count corruption -> FULL verification
same-locator retry        -> LOCATOR_CONTENT_CONFLICT
post-delete purge retry   -> INTERNAL_OPERATION_FAILED, record unreconciled
```

## Return kriterij

Implementer treba zatvoriti QA-013B-1 do QA-013B-5 i dodati regresione testove. Nakon toga je potreban novi nezavisni QA prolaz; trenutni prolaz ne daje tehnički acceptance, platform-production niti release autoritet.