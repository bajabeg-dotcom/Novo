from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ..analysis.notes import pair_notes


FAMILY_TOKENS = {
    "ballad": ("ballad", "balad", "slow", "love"),
    "pop": ("pop", "8 beat", "16 beat", "8beat", "16beat"),
    "rock": ("rock", "metal", "twist"),
    "dance": ("dance", "disco", "house", "techno", "club"),
    "jazz": ("jazz", "swing", "bossa", "latin", "fox"),
    "folk": ("folk", "polka", "waltz", "kolo", "country"),
}


def _family(name: str) -> str:
    folded=name.casefold().replace("_"," ")
    for family,tokens in FAMILY_TOKENS.items():
        if any(token in folded for token in tokens): return family
    return "other"


@dataclass(frozen=True, slots=True)
class FactoryVariation:
    level: int; density: float; channels: int; drum_density: float; drum_pitches: int
    velocity_mean: float; accent_delta: float; off16_ratio: float; simultaneity: float
    beats: float; meter: tuple[int,int]


@dataclass(frozen=True, slots=True)
class FactoryStyle:
    name: str; family: str; locator: str; variations: tuple[FactoryVariation,...]


@dataclass(frozen=True, slots=True)
class FactoryQuery:
    family: str|None=None; variation_level: int=2; meter: tuple[int,int]=(4,4)
    density: float|None=None; drum_density: float|None=None; off16_ratio: float|None=None
    minimum_channels: int=1
    style: str|None=None


@dataclass(frozen=True, slots=True)
class FactoryCandidate:
    style: str; family: str; locator: str; variation: FactoryVariation
    score: float; evidence: tuple[tuple[str,float],...]; limitations: tuple[str,...]


def derive_factory_query(song, *, style: str|None=None, family: str|None=None) -> FactoryQuery:
    """Measure input MIDI in the same note-per-beat space as Factory variations."""
    if not song.header.ppq: raise ValueError("automatic Factory selection requires PPQ MIDI")
    notes,_=pair_notes(song); end=max((note.start_tick for note in notes),default=0)
    if family is None and song.source_path:
        inferred=_family(Path(song.source_path).stem)
        if inferred!="other": family=inferred
    beats=max(1.0,end/song.header.ppq); melodic=[note for note in notes if note.channel!=10]; drums=[note for note in notes if note.channel==10]
    step=max(1,song.header.ppq//4); half=max(1,song.header.ppq//2)
    off=sum(1 for note in notes if abs((note.start_tick%half)-step)<=max(1,step//5))
    meter=(4,4); meter_event=next((event for track in song.tracks for event in track.events if event.meta_type==0x58 and len(event.data)>=2),None)
    if meter_event is not None: meter=(meter_event.data[0],2**meter_event.data[1])
    return FactoryQuery(family,2,meter,len(melodic)/beats,len(drums)/beats,off/max(1,len(notes)),max(1,len({note.channel for note in notes})),style)


class FactoryIndex:
    def __init__(self, styles: tuple[FactoryStyle,...], *, source: str=""):
        self.styles=styles; self.source=source

    @classmethod
    def load(cls,path: Path) -> "FactoryIndex":
        raw=json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema_version")!=1 or not isinstance(raw.get("styles"),list):
            raise ValueError("unsupported Factory groove analysis schema")
        styles=[]
        for item in raw["styles"]:
            variations=[]
            for key,value in sorted(item.get("variations",{}).items()):
                if not key.startswith("var"): continue
                meter=value.get("meter",[4,4])
                variations.append(FactoryVariation(int(key[3:]),float(value.get("density",0)),int(value.get("channels",0)),float(value.get("drum_density",0)),int(value.get("drum_pitches",0)),float(value.get("velocity_mean",0)),float(value.get("accent_delta",0)),float(value.get("off16_ratio",0)),float(value.get("simultaneity",0)),float(value.get("beats",0)),(int(meter[0]),int(meter[1]))))
            if variations: styles.append(FactoryStyle(item["style"],_family(item["style"]),item.get("path",item["style"]),tuple(variations)))
        return cls(tuple(styles),source=str(path))

    def retrieve(self,query: FactoryQuery, *, limit: int=5) -> tuple[FactoryCandidate,...]:
        if not 1<=query.variation_level<=4: raise ValueError("variation_level must be 1..4")
        if limit<1: raise ValueError("limit must be positive")
        candidates=[]
        for style in self.styles:
            if query.style is not None and style.name.casefold()!=query.style.casefold(): continue
            variation=next((item for item in style.variations if item.level==query.variation_level),None)
            if variation is None: continue
            family=1.0 if query.family is None or style.family==query.family.casefold() else 0.0
            meter=1.0 if variation.meter==query.meter else 0.0
            density=1.0 if query.density is None else math.exp(-abs(variation.density-query.density)/max(4,query.density*.45))
            drums=1.0 if query.drum_density is None else math.exp(-abs(variation.drum_density-query.drum_density)/max(2,query.drum_density*.5))
            groove=1.0 if query.off16_ratio is None else max(0.0,1-abs(variation.off16_ratio-query.off16_ratio))
            coverage=min(1.0,variation.channels/max(1,query.minimum_channels))
            evidence=(("family",family),("meter",meter),("density",density),("drums",drums),("groove",groove),("role_coverage_proxy",coverage))
            score=.25*family+.25*meter+.18*density+.14*drums+.12*groove+.06*coverage
            limitations=("channel count is only a role-coverage proxy; note-level role evidence is not indexed yet",)
            candidates.append(FactoryCandidate(style.name,style.family,style.locator,variation,round(score,6),tuple((name,round(value,6)) for name,value in evidence),limitations))
        return tuple(sorted(candidates,key=lambda item:(-item.score,item.style.casefold()))[:limit])
