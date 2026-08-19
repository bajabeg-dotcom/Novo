"""RX oscillator profili -- stavka 2.2 iz spiska nedovrsenog.

Jedan izvor istine o tome sta velocity i visina ZNACE na konkretnom Pa800 RX
zvuku. Do sada je ta informacija postojala samo kao proza u
`evidence/oscilatori/Oscilatori.txt` i djelimicno u
`config/performance-defaults.json`, a nijedan optimizer je nije citao.

Dvije stvari koje ovaj modul cini mogucim:

1. **Velocity nije samo glasnoca.** Na RX zvuku velocity bira oscilator, tj.
   artikulaciju. Pomjeranje velocityja sa 90 na 80 na `Finger Bass RX` ne
   znaci "tise" nego mijenja Harm u Radni. Optimizer koji to ne zna tiho
   mijenja artikulaciju.

2. **Neke note nisu muzika.** Zona C7-G9 su fret/slide/noise okidaci. Ne
   smiju se transponovati, harmonizovati niti im se smije dirati velocity.

Svaki profil nosi `evidence_status`. Nista iznad `documented` se ne tvrdi bez
hardverske potvrde; `hypothesis` se nikad ne koristi za automatsku odluku.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Zona apsolutnih okidaca zajednicka svim RX gitarama i bass zvukovima.
# C7 = MIDI 96. Granica je UKLJUCIVA -- vidi tests/regression/test_rx_trigger_zones.py.
TRIGGER_ZONE_LOW = 96
TRIGGER_ZONE_HIGH = 127

# Redoslijed pouzdanosti; automatska izmjena trazi barem `documented`.
EVIDENCE_ORDER = ("hypothesis", "documented", "software_verified", "hardware_confirmed")
MINIMUM_AUTOMATIC_STATUS = "documented"


class RxProfileError(ValueError):
    """Neispravan ili nedosljedan RX profil."""


@dataclass(frozen=True, slots=True)
class OscillatorZone:
    """Jedan oscilator: velocity opseg + opseg tipki na kojem se javlja."""

    index: int
    name: str
    velocity_min: int
    velocity_max: int
    key_min: int = 0
    key_max: int = 127
    switch: int | None = None
    absolute_trigger: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.velocity_min <= self.velocity_max <= 127:
            raise RxProfileError(
                f"{self.name}: neispravan velocity opseg "
                f"{self.velocity_min}-{self.velocity_max}"
            )
        if not 0 <= self.key_min <= self.key_max <= 127:
            raise RxProfileError(
                f"{self.name}: neispravan key opseg {self.key_min}-{self.key_max}"
            )

    def covers(self, note: int, velocity: int) -> bool:
        return (
            self.key_min <= note <= self.key_max
            and self.velocity_min <= velocity <= self.velocity_max
        )


@dataclass(frozen=True, slots=True)
class RxSoundProfile:
    """RX zvuk sa svojim oscilatorskim slojevima."""

    profile_id: str
    display_name: str
    family: str
    zones: tuple[OscillatorZone, ...]
    evidence_status: str = "documented"
    evidence: tuple[str, ...] = ()
    bank_msb: int | None = None
    bank_lsb: int | None = None
    program: int | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.evidence_status not in EVIDENCE_ORDER:
            raise RxProfileError(
                f"{self.profile_id}: nepoznat evidence_status "
                f"{self.evidence_status!r}"
            )
        if not self.zones:
            raise RxProfileError(f"{self.profile_id}: profil bez oscilatora")

    @property
    def address(self) -> tuple[int, int, int] | None:
        if None in (self.bank_msb, self.bank_lsb, self.program):
            return None
        return (self.bank_msb, self.bank_lsb, self.program)  # type: ignore[return-value]

    @property
    def is_automatic_eligible(self) -> bool:
        """Smije li se koristiti za automatsku izmjenu bez pitanja."""
        return EVIDENCE_ORDER.index(self.evidence_status) >= EVIDENCE_ORDER.index(
            MINIMUM_AUTOMATIC_STATUS
        )

    # -- upiti koje optimizeri koriste ------------------------------------

    def is_trigger_note(self, note: int) -> bool:
        """Je li nota apsolutni okidac (fret/slide/noise), a ne muzika."""
        return any(
            zone.absolute_trigger and zone.key_min <= note <= zone.key_max
            for zone in self.zones
        )

    def musical_zones(self) -> tuple[OscillatorZone, ...]:
        return tuple(zone for zone in self.zones if not zone.absolute_trigger)

    def zone_for(self, note: int, velocity: int) -> OscillatorZone | None:
        for zone in self.zones:
            if zone.covers(note, velocity):
                return zone
        return None

    def articulation_changes(
        self, note: int, old_velocity: int, new_velocity: int
    ) -> bool:
        """Bi li promjena velocityja presla u drugi oscilator.

        Ovo je kljucni upit: `True` znaci da izmjena nije samo dinamicka
        nego mijenja artikulaciju i mora se blokirati ili eksplicitno
        odobriti.
        """
        if old_velocity == new_velocity:
            return False
        before = self.zone_for(note, old_velocity)
        after = self.zone_for(note, new_velocity)
        if before is None or after is None:
            return before is not after
        return before.index != after.index

    def safe_velocity_span(self, note: int, velocity: int) -> tuple[int, int]:
        """Opseg u kojem se velocity smije mijenjati bez promjene artikulacije."""
        zone = self.zone_for(note, velocity)
        if zone is None:
            return (velocity, velocity)
        return (zone.velocity_min, zone.velocity_max)

    def clamp_velocity(self, note: int, velocity: int, target: int) -> int:
        """Priblizi se `target` koliko dopusta trenutna zona."""
        low, high = self.safe_velocity_span(note, velocity)
        return max(low, min(high, target))


@dataclass(frozen=True, slots=True)
class RxProfileSet:
    schema_version: int
    profiles: tuple[RxSoundProfile, ...]

    def by_id(self, profile_id: str) -> RxSoundProfile | None:
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        return None

    def by_address(self, bank_msb: int, bank_lsb: int, program: int) -> RxSoundProfile | None:
        for profile in self.profiles:
            if profile.address == (bank_msb, bank_lsb, program):
                return profile
        return None

    def by_family(self, family: str) -> tuple[RxSoundProfile, ...]:
        return tuple(p for p in self.profiles if p.family == family)

    def __len__(self) -> int:
        return len(self.profiles)

    def __iter__(self):
        return iter(self.profiles)


# ----------------------------------------------------------------------
# Ugradjeni profili iz evidence/oscilatori/Oscilatori.txt
# ----------------------------------------------------------------------
_OSC_SOURCE = "evidence/oscilatori/Oscilatori.txt"

_NOISE_ZONE = OscillatorZone(
    index=5,
    name="Noise",
    velocity_min=1,
    velocity_max=127,
    key_min=TRIGGER_ZONE_LOW,
    key_max=TRIGGER_ZONE_HIGH,
    switch=1,
    absolute_trigger=True,
)

# Bass: C-1..B6 je muzicki opseg (MIDI 0..95), C7+ su okidaci.
_BASS_MUSICAL_HIGH = TRIGGER_ZONE_LOW - 1


def _finger_picked_bass(profile_id: str, name: str) -> RxSoundProfile:
    return RxSoundProfile(
        profile_id=profile_id,
        display_name=name,
        family="bass",
        zones=(
            OscillatorZone(1, "Harm", 114, 127, 0, _BASS_MUSICAL_HIGH, switch=1),
            OscillatorZone(2, "Radni", 53, 113, 0, _BASS_MUSICAL_HIGH, switch=94),
            OscillatorZone(3, "Stop", 23, 52, 0, _BASS_MUSICAL_HIGH, switch=39),
            OscillatorZone(4, "Gliss", 1, 22, 0, _BASS_MUSICAL_HIGH, switch=1),
            _NOISE_ZONE,
        ),
        evidence_status="documented",
        evidence=(_OSC_SOURCE,),
    )


def _slap_bass(profile_id: str, name: str, low_sample: str) -> RxSoundProfile:
    return RxSoundProfile(
        profile_id=profile_id,
        display_name=name,
        family="bass",
        zones=(
            OscillatorZone(1, "Slap", 114, 127, 0, _BASS_MUSICAL_HIGH, switch=1),
            # Prag 87 je ispravka ranijeg 94; podrzan bimodalnom Factory
            # raspodjelom ali jos ceka PCG/Sound Edit potvrdu na uredjaju.
            OscillatorZone(2, f"Radni ({low_sample})", 53, 113, 0, _BASS_MUSICAL_HIGH, switch=87),
            OscillatorZone(3, "Stop", 23, 52, 0, _BASS_MUSICAL_HIGH, switch=39),
            OscillatorZone(4, "Gliss", 1, 22, 0, _BASS_MUSICAL_HIGH, switch=1),
            _NOISE_ZONE,
        ),
        evidence_status="documented",
        evidence=(_OSC_SOURCE,),
        notes="Switch 87 ceka direktnu PCG/Sound Edit potvrdu na Pa800.",
    )


def _clean_guitar(profile_id: str, name: str) -> RxSoundProfile:
    return RxSoundProfile(
        profile_id=profile_id,
        display_name=name,
        family="guitar",
        zones=(
            OscillatorZone(1, "Clean Slap / Slide", 94, 127, 0, _BASS_MUSICAL_HIGH, switch=114),
            OscillatorZone(2, "Radni", 53, 93, 0, _BASS_MUSICAL_HIGH, switch=74),
            OscillatorZone(3, "Clean Dead / Mute", 23, 52, 0, _BASS_MUSICAL_HIGH, switch=39),
            OscillatorZone(4, "Clean Harm / Ghost", 1, 22, 0, _BASS_MUSICAL_HIGH, switch=1),
            _NOISE_ZONE,
        ),
        evidence_status="documented",
        evidence=(_OSC_SOURCE,),
    )


def _dist_guitar() -> RxSoundProfile:
    return RxSoundProfile(
        profile_id="dist-guitar-rx",
        display_name="Dist Guitar RX1/RX2",
        family="guitar",
        zones=(
            OscillatorZone(1, "Dist / Harmonic", 88, 127, 0, _BASS_MUSICAL_HIGH, switch=114),
            OscillatorZone(2, "Dist Mute", 1, 87, 0, _BASS_MUSICAL_HIGH, switch=49),
            OscillatorZone(3, "Noise", 1, 127, TRIGGER_ZONE_LOW, TRIGGER_ZONE_HIGH, switch=1, absolute_trigger=True),
        ),
        evidence_status="documented",
        evidence=("config/performance-defaults.json", _OSC_SOURCE),
    )


def _power_chord() -> RxSoundProfile:
    return RxSoundProfile(
        profile_id="power-chords",
        display_name="Power Chords",
        family="guitar",
        zones=(
            # Oba sloja zvuce 1-127: velocity je ISKLJUCIVO dinamika.
            OscillatorZone(1, "Layer 1", 1, 127, 0, 127),
        ),
        evidence_status="documented",
        evidence=("config/performance-defaults.json",),
        bank_msb=121,
        bank_lsb=4,
        program=30,
        notes=(
            "Oba oscilatorska sloja pokrivaju 1-127; velocity ne bira "
            "artikulaciju. Root-fifth-octave bez terce."
        ),
    )


@lru_cache(maxsize=1)
def builtin_rx_profiles() -> RxProfileSet:
    """Profili izvedeni iz lokalnih dokaza. Nijedan nije hardware_confirmed."""
    return RxProfileSet(
        schema_version=1,
        profiles=(
            _finger_picked_bass("finger-bass-rx", "Finger Bass RX"),
            _finger_picked_bass("picked-bass-rx", "Picked Bass RX"),
            _slap_bass("slapfing-bass-rx", "SlapFing Bass RX", "E.Bass3"),
            _slap_bass("slappick-bass-rx", "SlapPick Bass RX", "E.Bass4 Pick"),
            *(
                _clean_guitar(f"clean-guitar-rx{n}", f"Clean Guitar RX{n}")
                for n in range(1, 7)
            ),
            _dist_guitar(),
            _power_chord(),
        ),
    )


def load_rx_profiles(path: Path | None = None) -> RxProfileSet:
    """Ucitaj RX profile iz JSON-a, ili vrati ugradjene ako put nije dat."""
    if path is None:
        return builtin_rx_profiles()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise RxProfileError("nepodrzana RX profile schema")
    profiles = []
    for item in raw.get("profiles", []):
        zones = tuple(
            OscillatorZone(
                index=int(z["index"]),
                name=str(z["name"]),
                velocity_min=int(z["velocity_min"]),
                velocity_max=int(z["velocity_max"]),
                key_min=int(z.get("key_min", 0)),
                key_max=int(z.get("key_max", 127)),
                switch=z.get("switch"),
                absolute_trigger=bool(z.get("absolute_trigger", False)),
            )
            for z in item["zones"]
        )
        profiles.append(
            RxSoundProfile(
                profile_id=str(item["profile_id"]),
                display_name=str(item.get("display_name", item["profile_id"])),
                family=str(item.get("family", "unknown")),
                zones=zones,
                evidence_status=str(item.get("evidence_status", "documented")),
                evidence=tuple(item.get("evidence", ())),
                bank_msb=item.get("bank_msb"),
                bank_lsb=item.get("bank_lsb"),
                program=item.get("program"),
                notes=str(item.get("notes", "")),
            )
        )
    return RxProfileSet(schema_version=1, profiles=tuple(profiles))


# ----------------------------------------------------------------------
# Pomoc za optimizere koji nemaju konkretan RX profil
# ----------------------------------------------------------------------
def is_absolute_trigger_note(note: int, role: str) -> bool:
    """Konzervativna provjera bez poznatog profila.

    Koristi se kada adresa jos nije razrijesena: gitara i bass iznad C7 su
    okidaci, kao i vrlo niske gitarske note (fret sampleovi).
    """
    if role in {"drums", "percussion"}:
        return True
    if role in {"guitar", "bass"}:
        return note >= TRIGGER_ZONE_LOW or (role == "guitar" and note < 24)
    return False
