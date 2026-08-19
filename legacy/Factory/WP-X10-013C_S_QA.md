# WP-X10-013C-S — Independent Codex QA

Datum: 12. august 2026.  
Scope: samo phase-independent structural slot registry  
Pregledano: Architect, Addendum, Audit, Re-audit, Lead plan, `rxoptimizer/rhythm_structural_slots.py` i ciljani testovi  
Verdict: `RETURN`

## Izvršene provjere

- Ciljani pytest: `18 passed` sa `-W error`.
- Puni pytest: `448 passed` sa `-W error`.
- Python compile: prolazi.
- `git diff --check`: prolazi.
- Potvrđeni su atomic replace/rollback, deterministička permutacija, FK/integrity, full-bar token alignment i odsustvo model/envelope/target/output tabela.

## Nalazi koji blokiraju ACCEPT

### 1. Identity-kritični Factory context nije rekonstruisan iz frozen provenancea

`CalibrationContextPrimitives` je caller-supplied. `_validate_bar_provenance()` potvrđuje samo role i section token, ali ne potvrđuje Bank MSB/LSB, Program, canonical instrument identity, style name, section number, CV, meter, tempo regime, track-channel structural role ni voice policy prema prihvaćenom schema-v2/RAW zapisu.

Adversarial proba je uz nepromijenjen trusted snapshot zamijenila te vrijednosti sa Bank `99/88`, Program `77`, `FORGED_IDENTITY`, drugim style/CV/metrom/tempom i `DRUM_TRACK`. Build je ipak dao `STRUCTURAL_SLOT_RESOLVED`, a lažne vrijednosti su ušle u `calibration_context_key`.

To krši primitive-only reconstruction, exact provenance i Factory role/program/section trust. Nedokaziva dimenzija mora dati `STRUCTURAL_CONTEXT_UNPROVEN`, ne resolved membership.

### 2. Production Factory authority i NORMAL quality su samopotvrđeni

Builder nema obavezni accepted schema-v2/corpus manifest anchor. Caller može napraviti novi self-consistent `SourceLineageRecord(..., "FACTORY_RAW")`, source manifest, stable registry i snapshot za proizvoljne/sintetičke bajtove. `FactoryStructuralSource.quality_status` je takođe običan caller string `NORMAL`; nije vezan za frozen `rhythm_validation`/schema-v2 quality zapis.

Pozitivni test fixture upravo sintetički gradi ovakav `FACTORY_RAW` i production builder ga prihvata. Time `SYNTHETIC_GUARD_FIXTURE`, nepoznat ili drugi izvor može biti preimenovan u Factory i dobiti production membership/sufficiency. Re-audit izričito zahtijeva da synthetic fixture nikad ne dobije production Factory status.

Potrebna je obavezna recomputation veza prema accepted immutable corpus/schema-v2 source manifestu i quality registru, uključujući semantic/config digest parity; self-declared lineage class nije autoritet.

### 3. Duplicate/unison tie-break koristi neprovjeren caller token

`StructuralVoicePrimitive.voice_token` je proizvoljan caller string. Validator samo radi regex i substring zabranu. Token nije rekonstruisan iz allowlisted stable NOTE prirodnog ključa niti vezan za frozen provenance.

Zato npr. tokeni `V000123` i `V000124`, koji mogu kodirati onset tick ili parser order bez zabranjene riječi, razrješavaju unison i build daje dvije resolved membership stavke. Isti kanal omogućava source-local/cross-source collision i voice-crossing odluke na osnovu nedokazanog podatka.

Duplicate/unison smije biti resolved samo iz eksplicitne, frozen i provenance-provjerene timing-free projekcije. U suprotnom cijeli subset mora ostati `STRUCTURAL_DUPLICATE_AMBIGUOUS`.

## Dodatni hardening potreban uz povrat

- Dodati verifier koji ponovo provjerava stored semantic root, FK/integrity, closed status domene i canonical identity/provenance prije downstream upotrebe.
- Dodati adversarial testove za forged Bank/Program/style/CV/meter/tempo/track role/voice policy, self-labeled synthetic Factory, forged `NORMAL` quality i timing zakodiran u duplicate tokenu.
- Topology-preserving timing test mora ostati pozitivan samo dok simultanost, redoslijed i puna cluster sekvenca ostaju isti; postojeći split/merge/arpeggio testovi treba da ostanu fail-closed.

## Konačni verdict

```text
RETURN
```

Implementacija je konzervativna u više strukturalnih slučajeva i regresija je čista, ali trenutno može proizvesti production structural identitete iz nedokazanog contexta, samoproglašenog Factory/NORMAL autoriteta i caller-supplied unison tie-breaka. 013C-E ne smije početi prije korekcije i novog nezavisnog QA prolaza.