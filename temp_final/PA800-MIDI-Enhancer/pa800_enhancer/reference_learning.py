from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from .analysis.notes import pair_notes
from .corpus import CorpusRunner
from .optimize.velocity import detect_trill_note_ids
from .smf.reader import SmfReader


REFERENCE_CATALOG_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class LearnedInstrumentProfile:
    address: str
    bank_msb: int
    bank_lsb: int
    program: int
    channel: int
    factory_note_count: int
    factory_key_range: tuple[int, int] | None
    factory_velocity_range: tuple[int, int] | None
    factory_velocity_p10_p90: tuple[int, int] | None
    gold_note_count: int
    gold_short_note_ratio: float
    gold_trill_note_ratio: float
    factory_sources: int
    gold_sources: int
    gold_velocity_p10_p90: tuple[int,int] | None = None
    gold_velocity_mean: float | None = None
    gold_duration_beats_p10_p90: tuple[float,float] | None = None
    gold_microtiming_beats_p10_p90: tuple[float,float] | None = None


@dataclass(frozen=True, slots=True)
class ReferenceCatalog:
    schema_version: int
    gold_match: str
    factory_match: str
    source_sha256: dict[str, str]
    profiles: tuple[LearnedInstrumentProfile, ...]

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"

    def find(self, address: str) -> LearnedInstrumentProfile:
        try:
            return next(item for item in self.profiles if item.address == address)
        except StopIteration as error:
            raise ValueError(f"reference catalog has no address {address}") from error


@dataclass(slots=True)
class _Stats:
    notes: list[int]
    velocities: list[int]
    note_ids: set[str]
    short_ids: set[str]
    trill_ids: set[str]
    sources: set[str]
    durations: list[float]
    timing_residuals: list[float]

    @classmethod
    def empty(cls) -> "_Stats":
        return cls([], [], set(), set(), set(), set(), [], [])


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def _address(msb: int, lsb: int, program: int, channel: int) -> str:
    return f"{msb}:{lsb}:{program}:ch{channel}"


class ReferenceLearner:
    def __init__(self, corpus: CorpusRunner | None = None) -> None:
        self.corpus = corpus or CorpusRunner()
        self.reader: SmfReader = self.corpus.reader

    def learn(
        self,
        sources: tuple[Path, ...],
        *,
        gold_match: str = "Gold DNA.zip",
        factory_match: str = "Split Factory Styles.zip",
    ) -> ReferenceCatalog:
        gold: dict[str, _Stats] = defaultdict(_Stats.empty)
        factory: dict[str, _Stats] = defaultdict(_Stats.empty)
        source_hashes: dict[str, str] = {}
        gold_token = gold_match.casefold()
        factory_token = factory_match.casefold()
        for locator, data in self.corpus.iter_midi(sources):
            folded = locator.casefold()
            target = gold if gold_token in folded else factory if factory_token in folded else None
            if target is None:
                continue
            source_hashes[locator] = hashlib.sha256(data).hexdigest()
            song = self.reader.parse(data)
            notes, _ = pair_notes(song)
            note_by_id = {note.on_event_id: note for note in notes}
            trill_ids = detect_trill_note_ids(notes, song.header.ppq or 96)
            state: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0, 0])
            for track in song.tracks:
                for event in sorted(track.events, key=lambda item: (item.absolute_tick, item.order)):
                    if event.channel is None:
                        continue
                    key = (track.index, event.channel)
                    if event.message_type == 0xB0 and len(event.data) == 2:
                        if event.data[0] == 0:
                            state[key][0] = event.data[1]
                        elif event.data[0] == 32:
                            state[key][1] = event.data[1]
                    elif event.message_type == 0xC0 and event.data:
                        state[key][2] = event.data[0]
                    elif event.is_note_on:
                        msb, lsb, program = state[key]
                        address = _address(msb, lsb, program, event.channel)
                        stats = target[address]
                        observation_id = f"{locator}::{event.event_id}"
                        stats.notes.append(event.data[0])
                        stats.velocities.append(event.data[1])
                        stats.note_ids.add(observation_id)
                        stats.sources.add(locator)
                        note = note_by_id.get(event.event_id)
                        ppq=song.header.ppq or 96
                        if note and note.end_tick - note.start_tick <= max(1, (song.header.ppq or 96) // 4):
                            stats.short_ids.add(observation_id)
                        if note:
                            stats.durations.append((note.end_tick-note.start_tick)/ppq)
                            grid=max(1,ppq//4); residual=((note.start_tick+grid//2)%grid)-grid//2; stats.timing_residuals.append(residual/ppq)
                        if event.event_id in trill_ids:
                            stats.trill_ids.add(observation_id)
        profiles = []
        for address in sorted(set(gold) | set(factory)):
            g = gold.get(address, _Stats.empty())
            f = factory.get(address, _Stats.empty())
            prefix, channel_text = address.rsplit(":ch", 1)
            msb, lsb, program = (int(item) for item in prefix.split(":"))
            profiles.append(
                LearnedInstrumentProfile(
                    address, msb, lsb, program, int(channel_text),
                    len(f.notes),
                    (min(f.notes), max(f.notes)) if f.notes else None,
                    (min(f.velocities), max(f.velocities)) if f.velocities else None,
                    (_percentile(f.velocities, 0.10), _percentile(f.velocities, 0.90)) if f.velocities else None,
                    len(g.notes),
                    round(len(g.short_ids) / len(g.note_ids), 6) if g.note_ids else 0.0,
                    round(len(g.trill_ids) / len(g.note_ids), 6) if g.note_ids else 0.0,
                    len(f.sources), len(g.sources),
                    (_percentile(g.velocities,.10),_percentile(g.velocities,.90)) if g.velocities else None,
                    round(sum(g.velocities)/len(g.velocities),6) if g.velocities else None,
                    (round(sorted(g.durations)[round((len(g.durations)-1)*.10)],6),round(sorted(g.durations)[round((len(g.durations)-1)*.90)],6)) if g.durations else None,
                    (round(sorted(g.timing_residuals)[round((len(g.timing_residuals)-1)*.10)],6),round(sorted(g.timing_residuals)[round((len(g.timing_residuals)-1)*.90)],6)) if g.timing_residuals else None,
                )
            )
        return ReferenceCatalog(
            REFERENCE_CATALOG_SCHEMA_VERSION,
            gold_match,
            factory_match,
            dict(sorted(source_hashes.items())),
            tuple(profiles),
        )


def write_reference_catalog(catalog: ReferenceCatalog, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        temporary.write_text(catalog.dumps(), encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def load_reference_catalog(path: Path) -> ReferenceCatalog:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") not in (1,REFERENCE_CATALOG_SCHEMA_VERSION):
        raise ValueError("unsupported reference catalog schema")
    profiles = tuple(
        LearnedInstrumentProfile(
            **{
                **item,
                "factory_key_range": tuple(item["factory_key_range"]) if item.get("factory_key_range") else None,
                "factory_velocity_range": tuple(item["factory_velocity_range"]) if item.get("factory_velocity_range") else None,
                "factory_velocity_p10_p90": tuple(item["factory_velocity_p10_p90"]) if item.get("factory_velocity_p10_p90") else None,
                "gold_velocity_p10_p90": tuple(item["gold_velocity_p10_p90"]) if item.get("gold_velocity_p10_p90") else None,
                "gold_duration_beats_p10_p90": tuple(item["gold_duration_beats_p10_p90"]) if item.get("gold_duration_beats_p10_p90") else None,
                "gold_microtiming_beats_p10_p90": tuple(item["gold_microtiming_beats_p10_p90"]) if item.get("gold_microtiming_beats_p10_p90") else None,
            }
        )
        for item in raw.get("profiles", [])
    )
    return ReferenceCatalog(
        raw["schema_version"], raw.get("gold_match", ""), raw.get("factory_match", ""),
        dict(raw.get("source_sha256", {})), profiles,
    )
