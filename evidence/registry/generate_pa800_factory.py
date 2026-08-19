#!/usr/bin/env python3
"""Generate the canonical Korg Pa800 K01 Factory registry from the manual.

Only the pinned official manual hash and the vendored pypdf wheel are accepted.
The generator records named Factory Sound/Drum Kit addresses and preserves Drum
Kit remap rows as evidence; it never rewrites MIDI data or resolves conflicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANUAL = ROOT / "prism-uploads" / "Pa800-201UM-ENG.pdf"
DEFAULT_OUTPUT = ROOT / "registry" / "pa800_factory_registry.json"
VENDORED_WHEEL = ROOT / "vendor" / "pypdf-6.16.0-py3-none-any.whl"
MANUAL_SHA256 = "b7df16fb0113d998a6411ea1c28971707021da8bc0b728aff98eafcceb57c71b"
WHEEL_SHA256 = "8c47581faa1cba7006ac269da30075c929c251cc4ffbafb2bcbe260306631118"
PYPDF_VERSION = "6.16.0"
EXPECTED_PDF_PAGES = 344
SOUND_PRINTED_PAGES = tuple(range(275, 284))
DRUM_PRINTED_PAGE = 295
EXPECTED_SOUND_ADDRESSES = 1006
EXPECTED_DRUM_ADDRESSES = 65
EXPECTED_TOTAL_ADDRESSES = 1071


class K01GenerationError(ValueError):
    """Raised when source identity, extraction, or registry invariants fail."""


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65_536), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_pypdf() -> Any:
    if not VENDORED_WHEEL.is_file():
        raise K01GenerationError(f"missing pinned pypdf wheel: {VENDORED_WHEEL}")
    digest = sha256_path(VENDORED_WHEEL)
    if digest != WHEEL_SHA256:
        raise K01GenerationError(f"pypdf wheel SHA-256 mismatch: {digest}")
    sys.path.insert(0, str(VENDORED_WHEEL))
    try:
        import pypdf  # type: ignore[import-not-found]
    except ImportError as exc:
        raise K01GenerationError(f"cannot import vendored pypdf: {exc}") from exc
    if pypdf.__version__ != PYPDF_VERSION:
        raise K01GenerationError(
            f"pypdf version mismatch: {pypdf.__version__} != {PYPDF_VERSION}"
        )
    return pypdf


def printed_to_pdf_page(printed_page: int) -> int:
    """Return the 1-based PDF page for the manual's printed appendix page."""
    return printed_page + 4


def _normalized_lines(text: str) -> list[tuple[int, str]]:
    return [
        (line_number, " ".join(raw.split()))
        for line_number, raw in enumerate(text.splitlines(), 1)
        if raw.strip()
    ]


def _source_ref(printed_page: int, line_number: int) -> dict[str, int]:
    return {
        "printed_page": printed_page,
        "pdf_page": printed_to_pdf_page(printed_page),
        "extracted_line": line_number,
    }


def _read_manual(manual_path: Path) -> tuple[Any, str]:
    if not manual_path.is_file():
        raise K01GenerationError(f"manual does not exist: {manual_path}")
    digest = sha256_path(manual_path)
    if digest != MANUAL_SHA256:
        raise K01GenerationError(f"manual SHA-256 mismatch: {digest}")
    pypdf = _load_pypdf()
    reader = pypdf.PdfReader(str(manual_path))
    if len(reader.pages) != EXPECTED_PDF_PAGES:
        raise K01GenerationError(
            f"manual page count mismatch: {len(reader.pages)} != {EXPECTED_PDF_PAGES}"
        )
    return reader, digest


def _page_text(reader: Any, printed_page: int) -> str:
    pdf_page = printed_to_pdf_page(printed_page)
    text = reader.pages[pdf_page - 1].extract_text() or ""
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if not first.startswith(str(printed_page)):
        raise K01GenerationError(
            f"printed/PDF page mapping mismatch for {printed_page} -> {pdf_page}: {first!r}"
        )
    return text


def _address(cc00: int, cc32: int, pc: int) -> str:
    return f"{cc00}.{cc32}.{pc}"


def _parse_sounds(reader: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    row_pattern = re.compile(r"^(.*?)\s+(\d+)\s+(\d+)\s+(\d+)$")
    by_address: dict[tuple[int, int, int], dict[str, Any]] = {}
    duplicate_rows: list[dict[str, Any]] = []

    for printed_page in SOUND_PRINTED_PAGES:
        for line_number, line in _normalized_lines(_page_text(reader, printed_page)):
            match = row_pattern.match(line)
            if not match:
                continue
            name = match.group(1).strip()
            cc00, cc32, pc = map(int, match.groups()[1:])
            if cc00 != 121:
                continue  # Page 283 also displays Drum Kit bank entries (CC00=120).
            if not name or not all(0 <= value <= 127 for value in (cc00, cc32, pc)):
                raise K01GenerationError(f"invalid Sound row on printed page {printed_page}: {line}")
            key = (cc00, cc32, pc)
            source = _source_ref(printed_page, line_number)
            previous = by_address.get(key)
            if previous is not None:
                if previous["name"] != name:
                    raise K01GenerationError(
                        f"conflicting Sound names for {_address(*key)}: "
                        f"{previous['name']!r} != {name!r}"
                    )
                previous["sources"].append(source)
                duplicate_rows.append({
                    "address": _address(*key),
                    "name": name,
                    "source": source,
                    "reason": "IDENTICAL_SOURCE_ROW_DUPLICATE",
                })
                continue
            by_address[key] = {
                "address": _address(*key),
                "cc00": cc00,
                "cc32": cc32,
                "pc": pc,
                "name": name,
                "kind": "FACTORY_SOUND",
                "evidence_status": "CONFIRMED",
                "sources": [source],
            }

    sounds = [by_address[key] for key in sorted(by_address)]
    if len(sounds) != EXPECTED_SOUND_ADDRESSES:
        raise K01GenerationError(
            f"Factory Sound count mismatch: {len(sounds)} != {EXPECTED_SOUND_ADDRESSES}"
        )
    return sounds, duplicate_rows


def _parse_drums(
    reader: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    exact_pattern = re.compile(r"^(\d+)\s+(\d+)\s+(\d+)\s+(.+)$")
    remap_pattern = re.compile(
        r"^(\d+)\s+(\d+)\s+(\d+)(?:-(\d+))?\s*\(remap to (\d+)\)$"
    )
    user_pattern = re.compile(
        r"^(\d+)\s+(\d+)\s+(\d+)-(\d+)\s+User DrumKits \((\d+)-(\d+)\)$"
    )
    named: dict[tuple[int, int, int], dict[str, Any]] = {}
    raw_remaps: list[dict[str, Any]] = []
    user_ranges: list[dict[str, Any]] = []

    for line_number, line in _normalized_lines(_page_text(reader, DRUM_PRINTED_PAGE)):
        gm2 = line.endswith("√")
        clean = line[:-1].rstrip() if gm2 else line
        source = _source_ref(DRUM_PRINTED_PAGE, line_number)

        user_match = user_pattern.match(clean)
        if user_match:
            cc00, cc32, pc_start, pc_end, slot_start, slot_end = map(
                int, user_match.groups()
            )
            user_ranges.append({
                "cc00": cc00,
                "cc32": cc32,
                "pc_start": pc_start,
                "pc_end": pc_end,
                "slot_start": slot_start,
                "slot_end": slot_end,
                "kind": "USER_DRUM_KIT_RANGE",
                "evidence_status": "CONFIRMED",
                "source": source,
            })
            continue

        remap_match = remap_pattern.match(clean)
        if remap_match:
            cc00, cc32, pc_start, optional_end, target_pc = remap_match.groups()
            start = int(pc_start)
            end = int(optional_end) if optional_end is not None else start
            raw_remaps.append({
                "cc00": int(cc00),
                "cc32": int(cc32),
                "pc_start": start,
                "pc_end": end,
                "target_pc": int(target_pc),
                "source": source,
            })
            continue

        exact_match = exact_pattern.match(clean)
        if not exact_match:
            continue
        cc00, cc32, pc = map(int, exact_match.groups()[:3])
        name = exact_match.group(4).strip()
        if cc00 != 120 or cc32 != 0:
            continue
        if name.startswith("(remap"):
            raise K01GenerationError(f"unparsed remap row: {clean}")
        if not name or not all(0 <= value <= 127 for value in (cc00, cc32, pc)):
            raise K01GenerationError(f"invalid Drum Kit row: {clean}")
        key = (cc00, cc32, pc)
        if key in named:
            raise K01GenerationError(f"duplicate named Drum Kit address: {_address(*key)}")
        named[key] = {
            "address": _address(*key),
            "cc00": cc00,
            "cc32": cc32,
            "pc": pc,
            "name": name,
            "kind": "FACTORY_DRUM_KIT",
            "gm2": gm2,
            "evidence_status": "CONFIRMED",
            "sources": [source],
        }

    drum_kits = [named[key] for key in sorted(named)]
    if len(drum_kits) != EXPECTED_DRUM_ADDRESSES:
        raise K01GenerationError(
            f"named Drum Kit count mismatch: {len(drum_kits)} != {EXPECTED_DRUM_ADDRESSES}"
        )

    named_pcs = {record["pc"] for record in drum_kits}
    remap_rules: list[dict[str, Any]] = []
    for row in raw_remaps:
        source_pcs = list(range(row["pc_start"], row["pc_end"] + 1))
        conflicts = [pc for pc in source_pcs if pc in named_pcs]
        non_conflicting = [pc for pc in source_pcs if pc not in named_pcs]
        remap_rules.append({
            **row,
            "status": "CONFLICT" if conflicts else "CONFIRMED",
            "conflicts_with_named_pcs": conflicts,
            "non_conflicting_source_pcs": non_conflicting,
            "policy": (
                "PRESERVE_NAMED_DO_NOT_APPLY_REMAP"
                if conflicts else "EVIDENCE_ONLY_NO_MIDI_CHANGE"
            ),
        })

    overlap = next(
        (rule for rule in remap_rules if rule["pc_start"] == 57 and rule["pc_end"] == 63),
        None,
    )
    if overlap is None or overlap["conflicts_with_named_pcs"] != [57, 58]:
        raise K01GenerationError("required Drum Kit 57-58 remap conflict was not preserved")
    if len(user_ranges) != 1:
        raise K01GenerationError(f"User Drum Kit range count mismatch: {len(user_ranges)}")
    return drum_kits, remap_rules, user_ranges


def generate_registry(manual_path: Path = DEFAULT_MANUAL) -> dict[str, Any]:
    reader, manual_digest = _read_manual(manual_path)
    sounds, duplicate_rows = _parse_sounds(reader)
    drum_kits, remap_rules, user_ranges = _parse_drums(reader)
    records = sorted(sounds + drum_kits, key=lambda item: (item["cc00"], item["cc32"], item["pc"]))
    addresses = [record["address"] for record in records]
    if len(records) != EXPECTED_TOTAL_ADDRESSES or len(addresses) != len(set(addresses)):
        raise K01GenerationError(
            f"total unique address mismatch: records={len(records)} unique={len(set(addresses))}"
        )
    drum_names = [record["name"] for record in drum_kits]
    return {
        "schema_version": "1.0.0",
        "registry_id": "K01",
        "device": "Korg Pa800",
        "mode": "READ_ONLY_FACTORY_IDENTITY",
        "source": {
            "path": "prism-uploads/Pa800-201UM-ENG.pdf",
            "sha256": manual_digest,
            "pdf_pages": EXPECTED_PDF_PAGES,
            "sound_printed_pages": list(SOUND_PRINTED_PAGES),
            "sound_pdf_pages": [printed_to_pdf_page(page) for page in SOUND_PRINTED_PAGES],
            "drum_printed_page": DRUM_PRINTED_PAGE,
            "drum_pdf_page": printed_to_pdf_page(DRUM_PRINTED_PAGE),
            "extractor": f"pypdf {PYPDF_VERSION}",
            "extractor_wheel_sha256": WHEEL_SHA256,
        },
        "counts": {
            "factory_sound_addresses": len(sounds),
            "named_drum_kit_addresses": len(drum_kits),
            "unique_drum_kit_names": len(set(drum_names)),
            "total_unique_addresses": len(records),
            "identical_source_row_duplicates": len(duplicate_rows),
            "drum_remap_rows": len(remap_rules),
            "drum_remap_conflict_rows": sum(rule["status"] == "CONFLICT" for rule in remap_rules),
            "user_drum_kit_ranges": len(user_ranges),
        },
        "records": records,
        "drum_remap_rules": remap_rules,
        "user_drum_kit_ranges": user_ranges,
        "source_duplicate_rows": duplicate_rows,
        "safety": {
            "midi_changes_authorized": False,
            "unknown_address_policy": "UNKNOWN_DO_NOT_GUESS",
            "remap_policy": "REPORT_ONLY_K02_NOT_IMPLEMENTED",
        },
    }


def render_registry(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail if canonical JSON is stale")
    args = parser.parse_args(argv)
    try:
        rendered = render_registry(generate_registry(args.manual))
        if args.check:
            if not args.output.is_file() or args.output.read_text(encoding="utf-8") != rendered:
                raise K01GenerationError(f"canonical registry is stale: {args.output}")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
    except (OSError, K01GenerationError) as exc:
        print(f"K01 generation error: {exc}", file=sys.stderr)
        return 1
    data = json.loads(rendered)
    print(
        "K01 registry OK: "
        f"{data['counts']['factory_sound_addresses']} sounds + "
        f"{data['counts']['named_drum_kit_addresses']} drum kits = "
        f"{data['counts']['total_unique_addresses']} addresses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
