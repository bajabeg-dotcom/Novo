# K01 Pa800 Factory Registry audit — 2026-08-14

## Decision

**PASS** for the bounded read-only K01 Factory identity and reproducible
generator scope.

K01 does not resolve incomplete addresses, determine User slot contents, apply
remaps, connect M10 segments, replace Sounds or authorize MIDI changes. Those
belong to K02/K03 and remain unimplemented.

## Normative source

- File: `prism-uploads/Pa800-201UM-ENG.pdf`
- SHA-256:
  `b7df16fb0113d998a6411ea1c28971707021da8bc0b728aff98eafcceb57c71b`
- PDF pages: 344
- Sound tables: printed pages 275–283, PDF pages 279–287
- Drum Kit table: printed page 295, PDF page 299

The generator refuses a different manual hash or page count.

## Pinned extractor

The source PDF is parsed with the vendored pure-Python
`pypdf 6.16.0` wheel:

- Path: `vendor/pypdf-6.16.0-py3-none-any.whl`
- SHA-256:
  `8c47581faa1cba7006ac269da30075c929c251cc4ffbafb2bcbe260306631118`
- License: included inside the wheel

The generator verifies the wheel hash and exact version before extraction.

## Generated artifacts

- Generator: `registry/generate_pa800_factory.py`
- Canonical data: `registry/pa800_factory_registry.json`
- Read-only lookup: `pa800_registry.py`
- Tests: `tests/test_pa800_factory_registry.py`
- Pinned requirement: `requirements-k01.txt`

Canonical JSON SHA-256:
`9176dd41720b72111bd17263b376a07bfb188c0390404614275ade0b11cb5a16`.

## Reproduced counts

- Factory Sound addresses (`CC00=121`): **1,006**
- Named Factory Drum Kit addresses (`CC00=120`): **65**
- Unique Drum Kit names: **64**
- Total unique full addresses: **1,071**
- Drum remap rows: **15**
- User Drum Kit ranges: **1**

The Sound table extraction contains 1,007 matching source rows but exactly
1,006 addresses because printed page 280 lists `121.0.71 Clarinet GM` twice
with identical name and address. The duplicate source occurrence is preserved
as provenance and not emitted as a second registry address.

## Confirmed examples

- `121.0.33 — Finger Bass GM` (printed page 282 / PDF page 286)
- `120.0.5 — Standard Kit RX1` (printed page 295 / PDF page 299)
- `120.0.48 — Orchestra Kit GM`
- `120.0.49 — Orchestra Kit GM`
- `120.0.57 — SFX Kit 2`
- `120.0.58 — Synth Kit`

Addresses 48 and 49 remain separate even though their official names are the
same.

## Drum remap conflict

Printed page 295 contains both named 57/58 entries and
`57–63 (remap to 56)`. K01 emits one remap evidence row with:

- status: `CONFLICT`;
- named conflicts: 57 and 58;
- non-overlapping source PCs: 59–63;
- policy: `PRESERVE_NAMED_DO_NOT_APPLY_REMAP`.

No remap is applied to MIDI, and K01 does not choose a winning interpretation.

## Lookup safety

`Pa800FactoryRegistry`:

- requires all address components in 0–127;
- performs exact full-address lookup only;
- returns immutable `FactoryEntry` values;
- returns no Factory entry for User range `120.64.0–63`;
- confirms that range only as a User slot location;
- exposes remap rows as evidence without resolving them.

## Dedicated tests

```bash
python registry/generate_pa800_factory.py --check
python -m pytest -q tests/test_pa800_factory_registry.py
```

Dedicated result: **7 passed**.

Full command with the GUI display active:

```bash
DISPLAY=:103 python -m pytest -q
```

Full result: **83 passed, 3,229 subtests passed, 0 failed, 0 skipped** in
237.61 seconds.

Tests cover deterministic byte-equal regeneration, counts, unique addresses,
source pages, exact lookup, immutable entries, duplicate official names,
57–58 conflict preservation, User range behavior and rejection of a modified
manual hash.

## Next dependency

K01 and M10 now satisfy the prerequisites for a separate K02 read-only
Instrument Identity Resolver. K02 must be implemented and tested before any
K03 replacement or Change/Writer/Enhance work.
