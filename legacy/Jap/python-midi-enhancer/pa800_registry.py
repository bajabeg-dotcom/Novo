#!/usr/bin/env python3
"""Read-only lookup for the generated Korg Pa800 K01 Factory registry.

K01 confirms only exact Factory addresses. It does not infer missing bank
components, resolve Drum Kit remaps, identify User slot contents, or authorize
MIDI changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
DEFAULT_REGISTRY = ROOT / "registry" / "pa800_factory_registry.json"
EXPECTED_MANUAL_SHA256 = "b7df16fb0113d998a6411ea1c28971707021da8bc0b728aff98eafcceb57c71b"
EXPECTED_SOUND_ADDRESSES = 1006
EXPECTED_DRUM_ADDRESSES = 65
EXPECTED_TOTAL_ADDRESSES = 1071


class Pa800RegistryError(ValueError):
    """Raised when the canonical K01 registry violates read-only invariants."""


@dataclass(frozen=True, slots=True)
class FactoryEntry:
    address: str
    cc00: int
    cc32: int
    pc: int
    name: str
    kind: str
    evidence_status: str
    printed_pages: tuple[int, ...]
    pdf_pages: tuple[int, ...]
    gm2: bool | None = None


@dataclass(frozen=True, slots=True)
class DrumRemapEvidence:
    cc00: int
    cc32: int
    pc_start: int
    pc_end: int
    target_pc: int
    status: str
    conflicts_with_named_pcs: tuple[int, ...]
    non_conflicting_source_pcs: tuple[int, ...]
    policy: str
    printed_page: int
    pdf_page: int


def _validate_address_parts(cc00: int, cc32: int, pc: int) -> None:
    for name, value in (("cc00", cc00), ("cc32", cc32), ("pc", pc)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 127:
            raise Pa800RegistryError(f"{name} must be an integer in 0..127: {value!r}")


def canonical_address(cc00: int, cc32: int, pc: int) -> str:
    _validate_address_parts(cc00, cc32, pc)
    return f"{cc00}.{cc32}.{pc}"


class Pa800FactoryRegistry:
    """Immutable K01 address and remap-evidence view."""

    def __init__(self, data: dict[str, Any]):
        if data.get("schema_version") != "1.0.0" or data.get("registry_id") != "K01":
            raise Pa800RegistryError("unsupported K01 registry schema or ID")
        registry_source = data.get("source", {})
        if registry_source.get("sha256") != EXPECTED_MANUAL_SHA256:
            raise Pa800RegistryError("K01 manual SHA-256 mismatch")
        counts = data.get("counts", {})
        expected_counts = {
            "factory_sound_addresses": EXPECTED_SOUND_ADDRESSES,
            "named_drum_kit_addresses": EXPECTED_DRUM_ADDRESSES,
            "total_unique_addresses": EXPECTED_TOTAL_ADDRESSES,
        }
        for key, expected in expected_counts.items():
            if counts.get(key) != expected:
                raise Pa800RegistryError(f"K01 count mismatch for {key}")

        entries: dict[str, FactoryEntry] = {}
        for raw in data.get("records", []):
            cc00, cc32, pc = raw.get("cc00"), raw.get("cc32"), raw.get("pc")
            _validate_address_parts(cc00, cc32, pc)
            address = canonical_address(cc00, cc32, pc)
            if raw.get("address") != address:
                raise Pa800RegistryError(f"non-canonical address: {raw.get('address')!r}")
            if address in entries:
                raise Pa800RegistryError(f"duplicate K01 address: {address}")
            kind = raw.get("kind")
            if kind not in {"FACTORY_SOUND", "FACTORY_DRUM_KIT"}:
                raise Pa800RegistryError(f"unsupported K01 entry kind: {kind!r}")
            if raw.get("evidence_status") != "CONFIRMED":
                raise Pa800RegistryError(f"unconfirmed K01 record: {address}")
            sources = raw.get("sources")
            if not isinstance(sources, list) or not sources:
                raise Pa800RegistryError(f"missing source pages for {address}")
            entries[address] = FactoryEntry(
                address=address,
                cc00=cc00,
                cc32=cc32,
                pc=pc,
                name=str(raw.get("name", "")),
                kind=kind,
                evidence_status="CONFIRMED",
                printed_pages=tuple(sorted({int(item["printed_page"]) for item in sources})),
                pdf_pages=tuple(sorted({int(item["pdf_page"]) for item in sources})),
                gm2=(bool(raw.get("gm2")) if kind == "FACTORY_DRUM_KIT" else None),
            )
        if len(entries) != EXPECTED_TOTAL_ADDRESSES:
            raise Pa800RegistryError("K01 records length does not match total count")

        remaps: list[DrumRemapEvidence] = []
        for raw in data.get("drum_remap_rules", []):
            remap_source = raw.get("source", {})
            remaps.append(DrumRemapEvidence(
                cc00=int(raw["cc00"]),
                cc32=int(raw["cc32"]),
                pc_start=int(raw["pc_start"]),
                pc_end=int(raw["pc_end"]),
                target_pc=int(raw["target_pc"]),
                status=str(raw["status"]),
                conflicts_with_named_pcs=tuple(int(value) for value in raw["conflicts_with_named_pcs"]),
                non_conflicting_source_pcs=tuple(
                    int(value) for value in raw["non_conflicting_source_pcs"]
                ),
                policy=str(raw["policy"]),
                printed_page=int(remap_source["printed_page"]),
                pdf_page=int(remap_source["pdf_page"]),
            ))
        self._entries: Mapping[str, FactoryEntry] = MappingProxyType(entries)
        self._remaps = tuple(remaps)
        self._user_ranges = tuple(dict(item) for item in data.get("user_drum_kit_ranges", []))
        self._source: Mapping[str, Any] = MappingProxyType(dict(registry_source))

    @property
    def source(self) -> Mapping[str, Any]:
        return self._source

    @property
    def entries(self) -> tuple[FactoryEntry, ...]:
        return tuple(self._entries[address] for address in sorted(
            self._entries,
            key=lambda value: tuple(map(int, value.split("."))),
        ))

    def lookup(self, cc00: int, cc32: int, pc: int) -> FactoryEntry | None:
        return self._entries.get(canonical_address(cc00, cc32, pc))

    def lookup_address(self, address: str) -> FactoryEntry | None:
        parts = address.split(".")
        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            raise Pa800RegistryError(f"invalid address syntax: {address!r}")
        return self.lookup(*(int(part) for part in parts))

    def remap_evidence_for_pc(self, pc: int) -> tuple[DrumRemapEvidence, ...]:
        _validate_address_parts(120, 0, pc)
        return tuple(rule for rule in self._remaps if rule.pc_start <= pc <= rule.pc_end)

    def is_user_drum_slot(self, cc00: int, cc32: int, pc: int) -> bool:
        _validate_address_parts(cc00, cc32, pc)
        return any(
            cc00 == int(item["cc00"])
            and cc32 == int(item["cc32"])
            and int(item["pc_start"]) <= pc <= int(item["pc_end"])
            for item in self._user_ranges
        )


@lru_cache(maxsize=4)
def load_factory_registry(path: str | Path = DEFAULT_REGISTRY) -> Pa800FactoryRegistry:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Pa800RegistryError(f"cannot load K01 registry {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise Pa800RegistryError("K01 registry root must be an object")
    return Pa800FactoryRegistry(data)
