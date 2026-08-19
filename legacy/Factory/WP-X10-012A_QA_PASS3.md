# WP-X10-012A — Independent QA Pass 3

Datum: 12. august 2026.  
Verdict: `RETURN`

Preostala četiri nalaza:

1. `protected_count`/`ambiguous_count` nisu reconciled sa stvarnim grupama i membershipima, pa declared non-clear run može lažno clearovati sve subjekte.
2. Partition result digesti nisu dokazivo povezani sa parent run result digestom.
3. Structural subject membership SHA vrijednosti nisu provjerene protiv istog-source/same-version registry subjekata i tipova.
4. Canonical config još ne zaključava weight/density/Decimal/init/M-step/posterior/collapse/BIC/LOSO/support/groove contract verzije.

Targeted 66 i full 209 testova prolaze, ali paket nije prihvaćen.

## Verdict

`RETURN`