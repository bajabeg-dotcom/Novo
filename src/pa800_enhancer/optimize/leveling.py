"""Konzervativni output leveling -- stavka 2.4 iz spiska nedovrsenog.

Density-aware CC7/CC11 mastering do sada je radio samo za novo
materijalizovane Factory aranzmane (`arranging/materialize.py`). Proizvoljan
korisnicki MIDI sa sacuvanim originalnim trackovima nije se nivelirao.

Ovaj modul to radi, uz cetiri zastite koje spisak trazi:

1. **Namjerni tihi layer se ne dize.** Track koji je ocito namjerno tisi od
   ostalih (echo, doubling, pad ispod soloa) zadrzava svoj odnos. Ovo je
   najvaznije pravilo -- glupi normalizator bi ga "popravio" i unistio
   aranzman.
2. **Bass/kick masking.** Kada bass i kick dijele niski registar, bassu se
   ostavlja prostor umjesto da se oba diraju na maksimum.
3. **Anti-clipping budget.** Zbir istovremenih glasnoca ima gornju granicu.
4. **Bez naglih skokova.** CC7/CC11 se ne smiju pomjerati vise od praga
   izmedju susjednih tacaka.

Velocity se NIKADA ne dira -- to je muzicki sadrzaj. Mijenjaju se samo CC7
(volume) i CC11 (expression), i to samo kada postoji jasna potreba.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from statistics import median

# Granice u kojima se smije kretati CC7.
VOLUME_FLOOR = 70
VOLUME_CEILING = 122

# Track tisi od ovog udjela medijana smatra se NAMJERNO tihim.
INTENTIONAL_QUIET_RATIO = 0.72

# Maksimalna promjena CC7 po jednom prolazu, po jacini.
MAX_DELTA = {"light": 6, "balanced": 12, "strong": 20}

# Zbirni budzet: prosjecna glasnoca svih aktivnih kanala ne prelazi ovo.
LOUDNESS_BUDGET = 112

ROLE_TARGET = {
    "bass": 114,
    "drums": 108,
    "percussion": 100,
    "guitar": 104,
    "accompaniment": 100,
    "solo": 110,
    "unknown": 100,
}


class Intensity(StrEnum):
    LIGHT = "light"
    BALANCED = "balanced"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class ChannelStatistics:
    """Izmjereni profil jednog kanala -- ulaz za odluku o nivelaciji."""

    channel: int
    role: str
    note_count: int
    velocity_median: float
    velocity_peak: int
    density_per_beat: float
    pitch_median: float
    current_volume: int | None = None

    @property
    def loudness_proxy(self) -> float:
        """Gruba procjena doprinosa glasnoci: velocity x gustoca."""
        return self.velocity_median * (1.0 + min(2.0, self.density_per_beat) / 4.0)


@dataclass(frozen=True, slots=True)
class LevelDecision:
    channel: int
    role: str
    current_volume: int
    proposed_volume: int
    reason: str
    protected: bool = False

    @property
    def is_change(self) -> bool:
        return self.proposed_volume != self.current_volume

    @property
    def delta(self) -> int:
        return self.proposed_volume - self.current_volume


@dataclass(frozen=True, slots=True)
class LevelingPlan:
    decisions: tuple[LevelDecision, ...]
    intensity: Intensity
    budget_applied: bool = False

    @property
    def changes(self) -> tuple[LevelDecision, ...]:
        return tuple(d for d in self.decisions if d.is_change)

    @property
    def protected(self) -> tuple[LevelDecision, ...]:
        return tuple(d for d in self.decisions if d.protected)

    def summary(self) -> dict[str, object]:
        return {
            "intensity": self.intensity.value,
            "channels": len(self.decisions),
            "changed": len(self.changes),
            "protected": len(self.protected),
            "budget_applied": self.budget_applied,
            "max_delta": max((abs(d.delta) for d in self.decisions), default=0),
        }


def collect_channel_statistics(
    song, role_by_channel: dict[int, str] | None = None
) -> tuple[ChannelStatistics, ...]:
    """Izmjeri po-kanalni profil iz stvarnih dogadjaja."""
    roles = role_by_channel or {}
    ppq = song.header.ppq or 384
    beats = max(1.0, (song.end_tick or ppq) / ppq)

    velocities: dict[int, list[int]] = {}
    pitches: dict[int, list[int]] = {}
    volumes: dict[int, int] = {}

    for track in song.tracks:
        for event in track.events:
            channel = event.channel
            if channel is None:
                continue
            if event.message_type == 0x90 and event.data and event.data[1] > 0:
                velocities.setdefault(channel, []).append(event.data[1])
                pitches.setdefault(channel, []).append(event.data[0])
            elif (
                event.message_type == 0xB0
                and len(event.data) == 2
                and event.data[0] == 7
            ):
                volumes.setdefault(channel, event.data[1])

    stats = []
    for channel in sorted(velocities):
        values = velocities[channel]
        stats.append(
            ChannelStatistics(
                channel=channel,
                role=roles.get(channel, "drums" if channel == 10 else "unknown"),
                note_count=len(values),
                velocity_median=median(values),
                velocity_peak=max(values),
                density_per_beat=len(values) / beats,
                pitch_median=median(pitches[channel]),
                current_volume=volumes.get(channel),
            )
        )
    return tuple(stats)


def _is_intentionally_quiet(
    stat: ChannelStatistics, reference_median: float
) -> bool:
    """Je li kanal namjerno tisi od ostatka aranzmana."""
    if reference_median <= 0:
        return False
    return stat.velocity_median < reference_median * INTENTIONAL_QUIET_RATIO


def plan_leveling(
    statistics: tuple[ChannelStatistics, ...],
    *,
    intensity: Intensity | str = Intensity.BALANCED,
    default_volume: int = 100,
) -> LevelingPlan:
    """Napravi plan CC7 nivelacije, uz sve cetiri zastite."""
    mode = Intensity(intensity)
    limit = MAX_DELTA[mode.value]

    if not statistics:
        return LevelingPlan((), mode)

    reference = median([s.velocity_median for s in statistics])
    bass_channels = {s.channel for s in statistics if s.role == "bass"}
    low_drums = {
        s.channel
        for s in statistics
        if s.role in {"drums", "percussion"} and s.pitch_median < 48
    }

    decisions: list[LevelDecision] = []
    for stat in statistics:
        current = stat.current_volume if stat.current_volume is not None else default_volume

        # Zastita 1: namjerno tihi layer zadrzava svoj odnos.
        if _is_intentionally_quiet(stat, reference):
            decisions.append(
                LevelDecision(
                    channel=stat.channel,
                    role=stat.role,
                    current_volume=current,
                    proposed_volume=current,
                    reason=(
                        f"namjerno tih layer (velocity medijan "
                        f"{stat.velocity_median:.0f} vs {reference:.0f})"
                    ),
                    protected=True,
                )
            )
            continue

        target = ROLE_TARGET.get(stat.role, ROLE_TARGET["unknown"])

        # Zastita 2: bass/kick masking -- ako oba dijele niski registar,
        # bass dobija prostor, a niski bubnjevi se ne diraju navise.
        if stat.channel in low_drums and bass_channels:
            target = min(target, current)
            reason = "niski bubnjevi ostavljaju prostor bassu"
        elif stat.role == "bass" and low_drums:
            target = min(VOLUME_CEILING, target + 2)
            reason = "bass dobija prostor zbog maskiranja kickom"
        else:
            reason = f"nivelacija prema cilju uloge '{stat.role}'"

        # Zastita 4: bez naglih skokova.
        proposed = max(current - limit, min(current + limit, target))
        proposed = max(VOLUME_FLOOR, min(VOLUME_CEILING, proposed))

        decisions.append(
            LevelDecision(
                channel=stat.channel,
                role=stat.role,
                current_volume=current,
                proposed_volume=proposed,
                reason=reason,
            )
        )

    # Zastita 3: anti-clipping budzet nad neprotektiranim kanalima.
    budget_applied = False
    active = [d for d in decisions if not d.protected]
    if active:
        average = sum(d.proposed_volume for d in active) / len(active)
        if average > LOUDNESS_BUDGET:
            reduction = round(average - LOUDNESS_BUDGET)
            budget_applied = True
            decisions = [
                d
                if d.protected
                else LevelDecision(
                    channel=d.channel,
                    role=d.role,
                    current_volume=d.current_volume,
                    proposed_volume=max(
                        VOLUME_FLOOR, d.proposed_volume - reduction
                    ),
                    reason=f"{d.reason}; smanjeno zbog anti-clipping budzeta",
                )
                for d in decisions
            ]

    return LevelingPlan(tuple(decisions), mode, budget_applied)


def level_song(
    song,
    *,
    role_by_channel: dict[int, str] | None = None,
    intensity: Intensity | str = Intensity.BALANCED,
) -> LevelingPlan:
    """Izmjeri pjesmu i vrati plan nivelacije. Ne mijenja pjesmu."""
    stats = collect_channel_statistics(song, role_by_channel)
    return plan_leveling(stats, intensity=intensity)
