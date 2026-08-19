# W01 Atomic Verified Writer audit — 2026-08-14

## Decision

**PASS** for the bounded programmatic local-filesystem scope.

GUI save workflow and automatic Enhance are not included. The writer accepts
only a fully verified K03-P/C01/V01 chain.

## Mandatory gates

Before creating any temporary file, W01 requires:

- fully USER-approved Change Plan;
- matching USER execution request;
- C01 `PENDING_VERIFICATION` result that did not self-authorize save;
- V01 `PASS`, `save_authorized=true` and non-null verified bytes;
- matching plan/source/output identities and mutation count;
- verified-byte SHA-256 match;
- successful final MIDI reparse;
- current source file hash and bytes equal to the Change Engine original.

## Path policy

- Source must be an existing `.mid` or `.midi` file.
- Output must be a different new `.mid`/`.midi` file.
- Output stem must end with `_enhanced`.
- Report must be a distinct new `.json` file.
- MIDI and report must use the same existing output directory.
- Existing MIDI or report path blocks the entire operation.

## Atomic publication

Both MIDI and JSON are first written to same-directory temporary files, flushed
and `fsync`-ed. Publication uses `os.link(temp, destination)`, an atomic
create-if-absent operation on the tested local filesystem. It cannot overwrite
an existing destination.

If the second link, post-publication hash check or source recheck fails, W01
removes only artifacts created by that call and removes all temporary files.
There is no fallback to unsafe overwrite-style rename.

## JSON report

The report contains:

- schema/writer/status and timestamp;
- source/output/report paths and hashes;
- plan/proposal/request IDs;
- USER actor and request time;
- verification status and exact changed byte offsets;
- mutation IDs, event refs, fields, old/new values and absolute byte offsets;
- explicit no-overwrite/no-automatic-Enhance safety flags.

Its own SHA-256 is returned in `VerifiedWriteResult`.

## Filesystem rollback

Rollback removes report and MIDI only when both still exist and exactly match
the hashes recorded by W01. A modified output or report is not deleted. The
original source remains untouched in every path.

## Tests

```bash
python -m pytest -q tests/test_verified_writer.py
```

Dedicated result: **5 passed, 2 subtests passed**.

Full command:

```bash
DISPLAY=:108 python -m pytest -q
```

Full result: **122 passed, 3,242 subtests passed, 0 failed, 0 skipped** in
234.51 seconds.

Covered cases:

- end-to-end new MIDI and JSON save through M10/K01/K02/K03-P/P01/P02/C01/V01;
- output reparse and hash/report validation;
- original byte preservation;
- existing MIDI/report no-overwrite;
- source change, invalid output name and Verifier FAIL;
- simulated failure of the second atomic publication with full cleanup;
- successful filesystem rollback;
- rollback refusal after output tampering.

## Next gate

The next module may expose this bounded backend through a GUI workflow showing
the selected segment, original/target address, exact diff, risk, USER approval,
Verifier result, save paths and rollback. No automatic suggestion or Enhance
is authorized by W01.
