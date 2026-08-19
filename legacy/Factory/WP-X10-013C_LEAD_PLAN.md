# WP-X10-013C — Codex Lead Plan

Datum: 12. august 2026.  
Status: `LEAD_READY`  
Capability: `ANALYZE_ONLY / mutation NONE`

## Redoslijed

WP-013C se implementira kroz dva strogo odvojena gatea:

```text
013C-S phase-independent structural registry
→ independent QA ACCEPT
→ 013C-E Factory calibration envelope
→ independent final QA ACCEPT
```

Envelope kod ne počinje prije 013C-S QA acceptancea.

## 013C-S vlasništvo

- `rxoptimizer/rhythm_structural_slots.py`
- `tests/test_rhythm_structural_slots.py`
- zasebni QA agent bez prava izmjene

Prihvaćeni schema-v2/012C/012D moduli ostaju read-only.

## 013C-S interfejs

Typed primitive API mora:

- graditi canonical `calibration_context_key` iz closed role/instrument/style/section/CV/meter/tempo-regime/track-role/bar-structure primitive;
- graditi `structural_event_slot_key` tek nakon exact token-sequence alignmenta cijelog bara;
- rekonstruisati identity iz primitive allowliste, bez generic mappinga i caller digesta;
- odvojiti identity JSON od provenance/stable-FK zapisa;
- dati resolved, unproven ili ambiguity status; nikad target/anomaly vrijednost.

Timing-bearing primitive/digest (`tick`, phase, IOI, duration, velocity, accent, legacy exact context/topology/event-slot) ne smije biti ancestor identity digesta. Topology-preserving timing promjena daje isti ključ; timing promjena koja mijenja simultanost/red/cluster strukturu daje ambiguity.

Transposition equivalence je dozvoljena, inversion nije. Duplicate/unison bez unique allowlisted voice mappinga je ambiguous. Jedna resolved observation po source/bar/slot.

## 013C-S storage

Structural registry materializer je odvojena atomska SQLite baza sa:

- build contract/config;
- structural context registry;
- structural slot registry;
- source-local memberships i provenance;
- ambiguity/unproven rows;
- canonical semantic digest.

Ulaz je read-only schema-v2 snapshot uz mandatory trusted Factory lineage/source manifest i registry digest revalidation. Sam hash collision nije membership dokaz.

Schema/API zabranjuju Factory model, envelope, delta, reference overlay, USER_INPUT, anomaly, target, proposal, simulation i output semantiku u 013C-S.

## 013C-S testovi

- topology-preserving onset/phase/IOI varijante isti key;
- split/merge/order/simultaneity promjena nije isti resolved key;
- primitive dependency tracing i nested digest smuggling rejection;
- transposition positive; inversion/arpeggio/crossing negative;
- duplicate/unison ambiguity bez timing/event-ID tie-breaka;
- full-bar token sequence obavezna prije ordinal alignmenta;
- source lineage, authority i stable FK recomputation;
- cross-authority/synthetic/cross-source hash collision odbijanje;
- one observation per source/bar/slot;
- deterministic input permutation, atomic rollback, integrity/FK/digest;
- static/schema scan: nema model/envelope/delta/USER_INPUT/target/output surfacea;
- targeted i puni pytest sa warning-as-error.

## Budući 013C-E

Poslije 013C-S `ACCEPT`, zasebni Implementer može posjedovati:

- `rxoptimizer/rhythm_calibration_envelope.py`
- `tests/test_rhythm_calibration_envelope.py`

013C-E mora koristiti accepted structural registry kao jedini slot autoritet i implementirati novi structural refit, exact source-balanced stats, circular support, LOSO, NULL delta redove i odvojeni reference overlay.
