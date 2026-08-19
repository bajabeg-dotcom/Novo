"""Konzervativno mapiranje zvukova bez diranja muzickog sadrzaja.

Garancija: trackovi, note, lyrics, pitch bend i tempo ostaju bit-identicni.
Mijenjaju se samo Bank Select i Program Change dogadjaji. Zakljucano u
`tests/regression/test_preservation_contract.py`.

Rupa N1 (zatvorena): drum adresa 120.0.4 bila je hardkodirana i dodjeljivala
se cak i kada katalog nema nijedan dokaz. Sada svaka adresa -- ukljucujuci
drum kit -- dolazi iz izvora sa navedenim `evidence_status`, a odluka ispod
praga se odbija umjesto da se nagadja.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from ..domain.song import Song, Track
from ..profiles.rx import EVIDENCE_ORDER

# Ispod ovog praga se adresa ne dodjeljuje automatski.
MINIMUM_EVIDENCE = "documented"

# Mapiranje statusa iz config fajla u zajednicku ljestvicu iz profiles.rx.
_CONFIG_STATUS_MAP = {
    "hypothesis": "hypothesis",
    "factory_reference": "documented",
    "user_hardware_reference": "documented",
    "documented": "documented",
    "software_verified": "software_verified",
    "hardware_confirmed": "hardware_confirmed",
}

_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "performance-defaults.json"
)


def _role(channel: int, program: int) -> str:
    if channel == 10:
        return "drums"
    if 32 <= program <= 39:
        return "bass"
    if 24 <= program <= 31:
        return "guitar"
    return "accompaniment"


def _meets_threshold(status: str) -> bool:
    if status not in EVIDENCE_ORDER:
        return False
    return EVIDENCE_ORDER.index(status) >= EVIDENCE_ORDER.index(MINIMUM_EVIDENCE)


@dataclass(frozen=True, slots=True)
class DrumKitReference:
    """Podrazumijevani drum kit iz konfiguracije, sa svojim dokazom."""

    name: str
    bank_msb: int
    bank_lsb: int
    program: int
    evidence_status: str
    evidence: tuple[str, ...]

    @property
    def address(self) -> tuple[int, int, int]:
        return (self.bank_msb, self.bank_lsb, self.program)

    @property
    def is_eligible(self) -> bool:
        return _meets_threshold(self.evidence_status) and bool(self.evidence)


@lru_cache(maxsize=1)
def load_default_drum_kit(path: str | None = None) -> DrumKitReference | None:
    """Ucitaj podrazumijevani drum kit iz config fajla.

    Vraca `None` ako config ne postoji ili nema potreban zapis -- u tom
    slucaju drum kanal se preskace, ne nagadja.
    """
    target = Path(path) if path else _CONFIG_PATH
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = raw.get("default_drum_kit")
    if not isinstance(entry, dict):
        return None
    try:
        return DrumKitReference(
            name=str(entry["name"]),
            bank_msb=int(entry["bank_msb"]),
            bank_lsb=int(entry["bank_lsb"]),
            program=int(entry["program"]),
            evidence_status=_CONFIG_STATUS_MAP.get(
                str(entry.get("status", "hypothesis")), "hypothesis"
            ),
            evidence=tuple(entry.get("evidence", ())),
        )
    except (KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class ConservativeSoundMapping:
    channel: int
    role: str
    source_program: int
    bank_msb: int
    bank_lsb: int
    program: int
    evidence_notes: int
    evidence_status: str = "documented"
    evidence_source: str = "factory_catalog"


@dataclass(frozen=True, slots=True)
class SkippedChannel:
    """Kanal koji je namjerno ostavljen nepromijenjen, sa razlogom."""

    channel: int
    role: str
    program: int
    reason: str


@dataclass(frozen=True, slots=True)
class ConservativeOptimizationResult:
    song: Song
    mappings: tuple[ConservativeSoundMapping, ...]
    preserved_tracks: int
    preserved_notes: int
    skipped_channels: tuple[int, ...]
    skipped_details: tuple[SkippedChannel, ...] = ()

    def summary(self) -> dict[str, object]:
        return {
            "preserved_tracks": self.preserved_tracks,
            "preserved_notes": self.preserved_notes,
            "mapped_channels": len(self.mappings),
            "skipped_channels": len(self.skipped_channels),
            "skip_reasons": {s.channel: s.reason for s in self.skipped_details},
        }


def optimize_conservatively(
    song: Song,
    catalog,
    *,
    drum_kit: DrumKitReference | str | None = "auto",
) -> ConservativeOptimizationResult:
    """Mapiraj zvukove i normalizuj inicijalizaciju bez diranja nota.

    `drum_kit` prima:
      - `"auto"` (podrazumijevano): ucitaj iz config fajla,
      - `DrumKitReference`: eksplicitan izvor,
      - `None`: bez podrazumijevanog kita, drum kanal se preskace.
    """
    resolved_kit = (
        load_default_drum_kit() if drum_kit == "auto" else drum_kit
    )
    if isinstance(resolved_kit, str):  # zastita od pogresnog poziva
        resolved_kit = None

    channel_program: dict[int, int] = {}
    note_count = 0
    for track in song.tracks:
        for event in sorted(
            track.events, key=lambda item: (item.absolute_tick, item.order)
        ):
            if event.is_note_on:
                note_count += 1
            if event.channel and event.message_type == 0xC0 and event.data:
                channel_program.setdefault(event.channel, event.data[0])

    evidence: defaultdict[tuple[str, int], Counter] = defaultdict(Counter)
    for element in catalog.elements:
        for item in element.roles:
            evidence[(item.role, item.program)][
                (item.bank_msb, item.bank_lsb, item.program)
            ] += item.note_count

    usage: defaultdict[tuple[str, int], int] = defaultdict(int)
    mappings: dict[int, ConservativeSoundMapping] = {}
    skipped: list[SkippedChannel] = []

    for channel, program in sorted(channel_program.items()):
        role = _role(channel, program)

        if role == "drums":
            if resolved_kit is None:
                skipped.append(
                    SkippedChannel(
                        channel, role, program,
                        "nema podrazumijevanog drum kita u konfiguraciji",
                    )
                )
                continue
            if not resolved_kit.is_eligible:
                skipped.append(
                    SkippedChannel(
                        channel, role, program,
                        f"drum kit '{resolved_kit.name}' je "
                        f"{resolved_kit.evidence_status}, ispod praga "
                        f"{MINIMUM_EVIDENCE}",
                    )
                )
                continue
            mappings[channel] = ConservativeSoundMapping(
                channel=channel,
                role=role,
                source_program=program,
                bank_msb=resolved_kit.bank_msb,
                bank_lsb=resolved_kit.bank_lsb,
                program=resolved_kit.program,
                evidence_notes=0,
                evidence_status=resolved_kit.evidence_status,
                evidence_source=f"config:{resolved_kit.name}",
            )
            continue

        candidates = evidence[(role, program)].most_common()
        if not candidates:
            skipped.append(
                SkippedChannel(
                    channel, role, program,
                    f"nema Factory dokaza za ulogu '{role}' i program {program}",
                )
            )
            continue

        address, count = candidates[usage[(role, program)] % len(candidates)]
        usage[(role, program)] += 1
        mappings[channel] = ConservativeSoundMapping(
            channel=channel,
            role=role,
            source_program=program,
            bank_msb=address[0],
            bank_lsb=address[1],
            program=address[2],
            evidence_notes=count,
            evidence_status="documented",
            evidence_source="factory_catalog",
        )

    tracks = []
    for track in song.tracks:
        events = []
        for event in track.events:
            mapping = mappings.get(event.channel or -1)
            updated = event
            if mapping:
                if (
                    event.message_type == 0xB0
                    and len(event.data) == 2
                    and event.data[0] == 0
                ):
                    updated = replace(
                        event,
                        absolute_tick=0,
                        order=-300,
                        data=bytes((0, mapping.bank_msb)),
                    )
                elif (
                    event.message_type == 0xB0
                    and len(event.data) == 2
                    and event.data[0] == 32
                ):
                    updated = replace(
                        event,
                        absolute_tick=0,
                        order=-299,
                        data=bytes((32, mapping.bank_lsb)),
                    )
                elif event.message_type == 0xC0 and event.data:
                    updated = replace(
                        event,
                        absolute_tick=0,
                        order=-298,
                        data=bytes((mapping.program,)),
                    )
            events.append(updated)
        tracks.append(Track(track.index, events))

    projected = Song(
        song.header, tracks, song.source_path, song.source_sha256, song.raw_document
    )
    return ConservativeOptimizationResult(
        song=projected,
        mappings=tuple(mappings[key] for key in sorted(mappings)),
        preserved_tracks=len(song.tracks),
        preserved_notes=note_count,
        skipped_channels=tuple(s.channel for s in skipped),
        skipped_details=tuple(skipped),
    )
