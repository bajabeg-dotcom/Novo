from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from ..analysis.notes import pair_notes
from ..smf.reader import SmfReader


_ELEMENT = re.compile(r"_(Var([1-4])|Fill([1-9])|Break|Intro([1-9])|End([1-9]))\.mid$",re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FactoryRolePattern:
    role: str; channel: int; bank_msb: int; bank_lsb: int; program: int
    note_count: int; key_range: tuple[int,int]; velocity_range: tuple[int,int]
    velocity_p10_p90: tuple[int,int]; onset_grid: tuple[float,...]; drum_notes: tuple[tuple[int,int],...]


@dataclass(frozen=True, slots=True)
class FactoryElementPattern:
    locator: str; sha256: str; style: str; family: str; element_type: str
    variation_level: int|None; ppq: int; end_tick: int; roles: tuple[FactoryRolePattern,...]
    boundary_truncated_events: int; evidence_status: str


@dataclass(frozen=True, slots=True)
class FactoryPatternCatalog:
    schema_version: int; source_sha256: str; source_locator: str
    elements: tuple[FactoryElementPattern,...]; failures: tuple[tuple[str,str],...]


def _family(name: str) -> str:
    from .factory import _family as classify
    return classify(name)


def _role(channel: int,program: int) -> str:
    if channel==9: return "bass"
    if channel==10: return "drums"
    if channel==11: return "percussion"
    if 24<=program<=31: return "guitar"
    return "accompaniment"


def _percentile(values: list[int],fraction: float) -> int:
    ordered=sorted(values); return ordered[round((len(ordered)-1)*fraction)]


def _addresses(song) -> dict[tuple[int,int],tuple[int,int,int]]:
    result={}
    for track in song.tracks:
        state=defaultdict(lambda:[0,0,0])
        for event in sorted(track.events,key=lambda item:(item.absolute_tick,item.order)):
            channel=event.channel
            if channel is None: continue
            if event.message_type==0xB0 and len(event.data)==2 and event.data[0] in (0,32): state[channel][0 if event.data[0]==0 else 1]=event.data[1]
            elif event.message_type==0xC0 and event.data: state[channel][2]=event.data[0]
            elif event.is_note_on: result.setdefault((track.index,channel),tuple(state[channel]))
    return result


def _element(locator: str,data: bytes) -> FactoryElementPattern:
    match=_ELEMENT.search(locator.replace("\\","/"))
    if not match: raise ValueError("unrecognized Factory element filename")
    parts=locator.replace("\\","/").split("/"); style=parts[-2] if len(parts)>1 else parts[-1].rsplit("_",1)[0]
    token=match.group(1).casefold(); element_type="variation" if token.startswith("var") else "fill" if token.startswith("fill") else "ending" if token.startswith("end") else "intro" if token.startswith("intro") else "break"
    variation=int(match.group(2)) if match.group(2) else None
    song=SmfReader().parse(data); notes,unmatched=pair_notes(song)
    event_track={event.event_id:track.index for track in song.tracks for event in track.events}; addresses=_addresses(song); grouped=defaultdict(list)
    for note in notes:
        track=event_track.get(note.on_event_id,0); address=addresses.get((track,note.channel),(0,0,0)); grouped[(note.channel,*address)].append(note)
    patterns=[]
    for (channel,bank_msb,bank_lsb,program),items in sorted(grouped.items()):
        grid=[0]*16
        for note in items: grid[min(15,int(note.start_tick/max(1,song.end_tick)*16))]+=1
        total=len(items); velocities=[note.velocity for note in items]; drums=Counter(note.note for note in items) if channel in (10,11) else Counter()
        patterns.append(FactoryRolePattern(_role(channel,program),channel,bank_msb,bank_lsb,program,total,(min(n.note for n in items),max(n.note for n in items)),(min(velocities),max(velocities)),(_percentile(velocities,.1),_percentile(velocities,.9)),tuple(round(value/total,6) for value in grid),tuple(sorted(drums.items()))))
    status="boundary_truncated" if unmatched else "complete"
    return FactoryElementPattern(locator,hashlib.sha256(data).hexdigest(),style,_family(style),element_type,variation,song.header.ppq or 0,song.end_tick,tuple(patterns),len(unmatched),status)


def _element_job(item):
    name,data=item
    try: return _element(name,data),None
    except (ValueError,EOFError) as error: return None,(name,str(error))


class FactoryCorpusIndexer:
    def build(self,source: Path, *, factory_member: str="Split Factory Styles.zip", limit: int|None=None, workers: int=1) -> FactoryPatternCatalog:
        if workers<1: raise ValueError("workers must be positive")
        source_data=source.read_bytes(); source_hash=hashlib.sha256(source_data).hexdigest()
        with zipfile.ZipFile(io.BytesIO(source_data)) as outer:
            midi_names=[item.filename for item in outer.infolist() if not item.is_dir() and item.filename.casefold().endswith((".mid",".midi"))]
            if midi_names: archive_data=source_data
            else:
                member=next((item for item in outer.infolist() if Path(item.filename).name.casefold()==factory_member.casefold()),None)
                if member is None: raise ValueError(f"Factory member not found: {factory_member}")
                archive_data=outer.read(member)
        elements=[]; failures=[]
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            names=[item.filename for item in archive.infolist() if not item.is_dir() and item.filename.casefold().endswith((".mid",".midi"))]
            jobs=[(name,archive.read(name)) for name in names[:limit]]
        if workers==1: results=map(_element_job,jobs)
        else:
            executor=ProcessPoolExecutor(max_workers=workers); results=executor.map(_element_job,jobs,chunksize=16)
        try:
            for element,failure in results:
                if element: elements.append(element)
                if failure: failures.append(failure)
        finally:
            if workers!=1: executor.shutdown()
        return FactoryPatternCatalog(1,source_hash,str(source),tuple(elements),tuple(failures))


def load_factory_catalog(path: Path) -> FactoryPatternCatalog:
    raw=json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version")!=1 or not isinstance(raw.get("elements"),list): raise ValueError("unsupported Factory pattern catalog schema")
    elements=[]
    for item in raw["elements"]:
        roles=tuple(FactoryRolePattern(role["role"],int(role["channel"]),int(role["bank_msb"]),int(role["bank_lsb"]),int(role["program"]),int(role["note_count"]),tuple(role["key_range"]),tuple(role["velocity_range"]),tuple(role["velocity_p10_p90"]),tuple(role["onset_grid"]),tuple(tuple(pair) for pair in role["drum_notes"])) for role in item["roles"])
        elements.append(FactoryElementPattern(item["locator"],item["sha256"],item["style"],item["family"],item["element_type"],item.get("variation_level"),int(item["ppq"]),int(item["end_tick"]),roles,int(item.get("boundary_truncated_events",0)),item.get("evidence_status","complete")))
    return FactoryPatternCatalog(1,raw.get("source_sha256",""),raw.get("source_locator",str(path)),tuple(elements),tuple(tuple(item) for item in raw.get("failures",())))


def write_factory_catalog(catalog: FactoryPatternCatalog,path: Path) -> None:
    path.parent.mkdir(parents=True,exist_ok=True); temporary=path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(asdict(catalog),indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); temporary.replace(path)
    finally:
        if temporary.exists(): temporary.unlink()
