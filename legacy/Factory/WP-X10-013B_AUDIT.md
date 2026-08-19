# WP-X10-013B — Independent Architecture Audit

Datum: 12. august 2026.  
Predmet: `WP-X10-013B_ARCHITECT.md` naspram QA-prihvaćenih WP-012A/B/C/D i WP-013A granica  
Capability: `ANALYZE_ONLY / mutation NONE`

## Sažetak

Architect ispravno razdvaja `USER_INPUT_RAW` od Factory/Gold/Human autoriteta, zabranjuje training/evidence promociju, provjerava šest song SHA vrijednosti prije parsiranja i ne uvodi anomaly, target, simulation-change, MIDI writer ili output. Međutim, paket još nije spreman za Lead/Implementer lock. Otvorene su obavezne Human Owner odluke, a tenant namespace, privacy digest, purge concurrency, exclusion receipt i platform upload/storage primitive nisu dovoljno zaključani da bi implementacija bila jednoznačna i dokaziva.

## Potvrđene jake granice

- `USER_INPUT_RAW` je objekt analize, nikad model/evidence/training autoritet.
- Byte-identičan Factory/Gold sadržaj ne dobija corpus authority.
- Tačnih šest SHA vrijednosti se provjerava nad originalnim bajtovima prije MIDI parsera; rename/ekstenzija nisu relevantni.
- Excluded šest-song input ne dobija generalni X10 graf niti automatski Delay/Terca handoff.
- Originalni stream se copy/hashuje, artifact nezavisno rehashuje, a accepted parser čita samo verificirani artifact.
- V1/V2 prihvaćeni corpus slojevi ostaju read-only i ne mijenjaju se.
- Schema/API izričito zabranjuju calibration, anomaly, candidate, target, delta, change simulation, mutation i MIDI output.

## Blockeri

### B1 — Human Owner storage/privacy odluke nisu donesene

Sekcija 18 izričito zahtijeva odluke prije Lead locka, ali trenutno nisu zaključani: retention period, čuvanje raw artifacta poslije parsea, display filename politika, cross-session dedup, purge receipt sadržaj/retention, atomic publish/purge garancija, upload limit/kvota, raw access policy i trajna zabrana evidence/training promocije.

Ove vrijednosti utiču na schema, lifecycle i acceptance testove. Implementer ih ne smije izabrati sam niti zamijeniti proizvoljnim defaultima.

### B2 — Owner/session/upload vrijednosti nisu authorization dokaz

Architect opisuje opaque `owner_scope_id`, `session_locator_id` i `upload_locator_id`, ali ne zaključava da dolaze iz trusted platform auth konteksta, a ne iz caller payload-a. Caller-provided owner ID bi omogućio cross-tenant lookup, purge ili existence disclosure.

Create/read/verify/purge moraju dobiti server-side authenticated principal/capability. Svaki storage, cache, lease i API lookup mora biti vezan najmanje za `(owner_scope_id, session_locator_id, snapshot_id)`. API koji traži samo globalni `snapshot_id` ili `subject_id` nije prihvatljiv.

### B3 — Subject ID nije snapshot/tenant izolovan

`X10_USER_INPUT_SUBJECT_V1` i `authority_domain=USER_INPUT` odvajaju USER_INPUT od WP-012 Factory/Gold subject ID-a, ali dva ownera sa istim bajtovima dobijaju iste event/note subject ID-jeve jer natural key ne sadrži snapshot/upload namespace. To je prihvatljivo samo ako je svaki lookup, cache, FK handoff i budući join obavezno composite-scoped; Architect to ne zaključava.

Zabraniti globalni subject index i lookup po samom `subject_id`. Lead mora ili:

1. uvesti snapshot-local namespace seed u USER_INPUT stable-ID ugovor, ili
2. dokazati da je `subject_id` uvijek privatni lokalni ključ unutar jednog snapshot paketa i da nijedan API/cache/log ne koristi niti otkriva cross-snapshot equality.

### B4 — SHA-256 privatnog MIDI teksta nije dovoljna zaštita

Text, lyric, copyright, marker, cue i kratki SysEx payloadovi imaju mali/predvidiv prostor vrijednosti. Javni `canonical_data_digest`, subject ID izveden iz njega ili edge payload mogu omogućiti dictionary attack čak i bez plaintexta.

Potrebna je odvojena privatna canonical identity reprezentacija: npr. snapshot-local keyed digest/HMAC ili drugi Human-approved secret-salted ugovor, uz versioned key lifecycle. Javni manifest/subject API mora redigovati payload digest i svaki identifikator iz kojeg se privatni sadržaj praktično može brute-forceovati. Obični nesoljeni SHA nije anonimizacija.

### B5 — Purge nije atomski ni race-safe definisan

"Provjeri da nema leasea pa obriši paket i cache" ima TOCTOU trku: novi analyze lease može nastati poslije provjere, ili purge može pasti nakon brisanja raw fajla a prije SQLite/cache kopija. Fizičko brisanje više fajlova nije jedna filesystem atomska operacija.

Potreban je zaključan lifecycle state machine i linearizable lease/purge protokol, npr. `ACTIVE -> PURGE_REQUESTED -> ACCESS_REVOKED/TOMBSTONED -> PHYSICAL_PURGE_PENDING -> PURGED`, sa atomskim zabranjivanjem novih leaseova. Directory/package se prvo atomски renameuje iz aktivnog namespacea; kasnije idempotentni sweeper briše sadržaj i sve registrovane cache/spool kopije. Crash recovery i minimalni receipt moraju biti testirani. "Whole package" znači atomsko uklanjanje iz dostupnog namespacea, ne nedokazivu atomsku secure-delete operaciju.

### B6 — Platform upload/content-store primitive nije specificiran

`sealed_upload_handle` je naziv, ne provjerljiv contract. Nije definisano ko seal potvrđuje, može li backing file biti zamijenjen, može li handle biti seekovan/reopenovan, kako se sprečavaju symlink/hardlink/path swap i da li staged i final direktorij dijele filesystem potreban za atomic rename.

Lead mora vezati paket za trusted platform capability ili descriptor-based primitive. Builder ne smije resolveovati caller path. Temp/final fajlovi moraju koristiti private directory, restrictive permissions, exclusive create, no-follow semantics gdje su relevantne, fsync/close prije publisha i same-filesystem staged rename. Relativna string-validacija sama ne zatvara symlink/TOCTOU rizik.

### B7 — Exclusion receipt ne dokazuje dovoljno `parse_count=0` i `subject_graph=NOT_CREATED`

Minimalni receipt nema zaseban natural key/digest/API ugovor, niti dokaz da parser callback nije pozvan i da nije ostao raw/temp/graph artifact. Stored broj `parse_count=0` sam po sebi može biti falsifikovan.

Potrebni su zatvoreni `exclusion_receipt_id`, canonical receipt digest, mandatory guard-policy digest, raw SHA/count, terminal reason, parser invocation audit counter iz builder orchestrationa i package inventory commitment koji dokazuje odsustvo graph/parse tabela ili njihovih redova. Excluded put mora uništiti temp raw kopiju prema retention odluci i ne smije koristiti accepted snapshot API/status.

### B8 — Duplicate/retry i locator collision semantika nedostaje

Nije definisano ponašanje za:

- isti owner/session/upload locator i iste bajtove nakon retryja;
- isti locator i različite bajtove;
- različite upload locatore sa istim bajtovima u istoj ili drugoj sesiji;
- paralelna dva create poziva za isti locator;
- cache/content-store key collision.

Preporučeni gate: same-locator/same-bytes je idempotentni povrat istog accepted snapshot/receipta; same-locator/different-bytes je hard conflict; različiti upload locator uvijek daje odvojenu privatnu instance bez cross-session existence signala ili shared purge fatea. Lock/unique constraints moraju biti owner/session scoped.

### B9 — Malformed/resource-exhaustion MIDI ugovor zavisi od neriješenih limita

Architect navodi invalid/truncated/SMPTE testove, ali nema zaključane granice za byte size, track/event/note count, declared track length, VLQ/tick, text/SysEx length, parser CPU/time i disk/session kvotu. Zlonamjerni validno strukturiran MIDI može iscrpiti disk/memoriju prije parser failurea.

Human Owner mora potvrditi maksimalni upload i kvotu, a Lead zaključati parser/storage budgets. Prekoračenje mora imati zaseban zatvoren terminal status ili jasno mapiranje u `INVALID_OR_UNSUPPORTED_MIDI`, bez djelimičnog grafa i bez logovanja privatnog sadržaja.

## Dodatni rizici i kontradikcije

### R1 — `verify` može postati existence oracle

`snapshot_id` uključuje owner/session/upload i nije čist content hash, što je dobro, ali raw SHA/content ID i subject ID ostaju osjetljivi. Unauthorized i nonexistent odgovor moraju biti indistinguishable; rate limiting i audit su platform concern, ali contract mora zabraniti različite poruke/timing gdje je razumno.

### R2 — Parse determinism nije samo parser version string

Parser/config digest mora zaključati pairing contract, same-tick ordering, running-status obradu, zero-velocity note-off, SMPTE policy, text decoding policy, integer limits i canonical serialization. Runtime/library verzija ili druga semantika koja mijenja graf mora promijeniti digest. Binary64/locale/default text decode ne smiju uticati na semantic rezultat.

### R3 — Snapshot ID definicija je operativno nestabilna bez locator uniquenessa

Snapshot ID uključuje opaque locatore, ali contract ne definiše njihovu canonical encoding/normalization niti zabranu ponovne upotrebe. IDs moraju biti byte/string canonical, length-bounded i immutable; Unicode/confusable normalization ne smije biti implicitna.

### R4 — Atomic package publish traži durability i inventory proof

Directory rename daje visibility atomicity samo pod određenim filesystem uslovima. Acceptance treba razlikovati atomic visibility od crash durability i zahtijevati package inventory/digest: raw artifact, SQLite i manifest moraju pripadati istoj commit generaciji. Nema parcijalnog čitanja ni stale current-pointera.

### R5 — "Known forbidden lineage if available" je previše opcionalno

Šest-song skup je mandatory i jasan. Za poznate optimizer/repaired hashove, prihvaćeni guard registry snapshot mora biti versioned i frozen za build; u suprotnom implementacija može preskočiti raspoloživu listu. Nepoznat direktni upload smije ostati `UNVERIFIED_USER_ORIGIN`, ali poznata registry membership provjera ne smije biti caller-optional.

### R6 — Raw retention i snapshot verification su međuzavisni

Architect traži rehash raw bajtova na svakom `verify`, ali Human Owner možda odluči da se raw artifact ne čuva nakon parsea. Tada full byte verification više nije moguća. Contract mora imati dva odvojena statusa/API nivoa: `FULL_RAW_AND_GRAPH_VERIFIED` dok raw postoji i `GRAPH_ONLY_VERIFIED_RAW_PURGED` nakon dozvoljenog raw purgea, ili mora zahtijevati zajednički retention raw+DB paketa.

### R7 — Display filename kao ne-semantički metadata ipak je privacy/lifecycle podatak

Ako se omogući, mora pripadati istom owner scopeu, purge fateu i access logici. Basename sanitization nije dovoljna ako vrijednost završi u exceptionu, metrics labelu ili OS temp imenu.

### R8 — Zabrana writer/output putanje mora biti izvršno testirana

Pored schema forbidden-key skena, test treba monkeypatchovati/guardovati postojeće MIDI writer/export entrypointe i dokazati nula poziva; output/staged/package inventory mora odbiti `.mid`/`.midi` artefakte. Parser modul koji sadrži writer funkcije nije sam po sebi mutacija, ali nijedan writer/encoder callback ne smije biti dosegljiv kroz 013B API.

## Obavezni Lead gateovi

### Gate A — Human Owner decision record

Prije plana/koda napraviti versioned odluku za svih deset stavki Architect sekcije 18, posebno retention, raw lifetime, dedup, upload/kvotu, purge receipt i platform atomic primitive.

### Gate B — Trusted platform boundary

Zaključati tip i verifikaciju sealed upload capabilityja, authenticated owner/session kontekst, private content-store root, no-follow/exclusive-create pravila, same-filesystem publish i permission model. Caller ne smije predati owner identitet ili filesystem path kao authority.

### Gate C — Tenant/snapshot namespace

Izabrati snapshot-local subject namespace ili obavezni composite scoping za svaki DB/API/cache/lease ključ. Dodati adversarial testove za dva ownera sa identičnim bajtovima, isti subject ID, cross-session read/verify/purge i timing/existence disclosure.

### Gate D — Privacy-safe event identity

Zaključati keyed/salted privatni payload identity i public redaction. Testirati dictionary-friendly lyric/marker/SysEx vrijednosti, exception/log capture, subject API i digeste. Nijedan javni payload ne smije omogućiti jednostavnu provjeru pretpostavljenog plaintexta.

### Gate E — Exclusion proof

Definisati zaseban canonical exclusion receipt/schema/API. Test za svih šest SHA mora dokazati guard prije parser invocationa, `parse_count=0`, nema graph/package publish artefakta, nema automatic Delay/Terca handoffa i nema general X10 snapshot ID-a.

### Gate F — Lifecycle, retry i purge state machine

Definisati idempotency/collision pravila, linearizable lease/purge, tombstone/rename, crash recovery, cache registry i raw-purged verification semantiku. Injected failure treba pokriti svaku fazu publisha i purgea.

### Gate G — Parser/resource contract

Zaključati parser semantic/config digest i hard resource limite. Testirati malformed header/length/VLQ, huge declared length, oversized text/SysEx, excessive tracks/events, same-tick/running-status i timeout/quota rollback.

### Gate H — Contamination i mutation proof

Prije/poslije hash/digest svih Factory/Gold/evidence/training/calibration/consensus/proposal baza; read-only/open-mode ili filesystem guard; monkeypatched write APIs; package inventory bez MIDI outputa; recursive schema/payload forbidden-key scan.

## Acceptance dopuna

Nezavisni QA ne smije dati `ACCEPT` bez testova koji dokazuju:

1. authority i namespace izolaciju za identične bajtove između najmanje dva owner/session scopea;
2. svih šest pre-parse exclusions sa auditable zero parser invocationom i bez subject grafa;
3. privacy-safe text/SysEx identity bez plaintexta i dictionary oraclea u API-ju;
4. same-locator retry/collision i paralelni create rezultat;
5. symlink/path swap i staged/final publish adversarial slučajeve;
6. atomic access revocation i idempotentni purge poslije crasha;
7. malformed/resource-exhaustion fail-closed ponašanje;
8. byte-identičan Factory/Gold upload ostaje `USER_INPUT_RAW` i ne kontaminira nijedan autoritativni store;
9. raw-retained i eventualni raw-purged verify status nisu predstavljeni kao ista garancija;
10. capability ostaje `ANALYZE_ONLY`, mutation/model/evidence/training authority `NONE/NEVER`, uz nula writer/export poziva.

## Audit verdict

Smjer je ispravan i 013B treba biti sljedeći paket, ali implementacija sada zahtijeva nagađanje o obaveznim Human Owner odlukama i kritičnim platform/tenant/privacy/lifecycle pravilima. To bi moglo proizvesti cross-tenant disclosure, dictionary leakage privatnog MIDI teksta, neauditable exclusion ili djelimični purge.

Prije produkcijskog koda potrebni su Human Owner decision record i Architect addendum koji zatvaraju B1–B9, zatim Lead plan i novi nezavisni QA.

```text
BLOCKED
```