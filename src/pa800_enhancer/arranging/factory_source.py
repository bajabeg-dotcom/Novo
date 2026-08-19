from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..analysis.notes import pair_notes
from ..retrieval.factory_corpus import FactoryElementPattern
from ..smf.reader import SmfReader


@dataclass(frozen=True, slots=True)
class FactoryPatternNote:
    role: str; channel: int; bank_msb: int; bank_lsb: int; program: int
    start_tick: int; duration_ticks: int; pitch: int; velocity: int
    chord_interval: int|None; absolute_trigger: bool; source_track: int


@dataclass(frozen=True, slots=True)
class FactoryPatternSkeleton:
    locator: str; sha256: str; ppq: int; length_ticks: int
    notes: tuple[FactoryPatternNote,...]; ignored_non_cv1_tracks: int; unmatched_events: int


def _role(channel: int,program: int) -> str:
    if channel==9: return "bass"
    if channel==10: return "drums"
    if channel==11: return "percussion"
    if 24<=program<=31: return "guitar"
    return "accompaniment"


def _cv1_tracks(song) -> set[int]:
    result=set()
    for track in song.tracks:
        for event in track.events:
            if event.meta_type==3:
                text=event.data.decode("latin1",errors="ignore").strip().upper()
                if text.endswith("CV1"): result.add(track.index)
    return result


def _addresses(song):
    addresses={}
    for track in song.tracks:
        state={channel:[0,0,0] for channel in range(1,17)}
        for event in sorted(track.events,key=lambda item:(item.absolute_tick,item.order)):
            channel=event.channel
            if channel is None: continue
            if event.message_type==0xB0 and len(event.data)==2 and event.data[0] in (0,32): state[channel][0 if event.data[0]==0 else 1]=event.data[1]
            elif event.message_type==0xC0 and event.data: state[channel][2]=event.data[0]
            elif event.is_note_on: addresses.setdefault((track.index,channel),tuple(state[channel]))
    return addresses


def extract_factory_skeleton(element: FactoryElementPattern,data: bytes) -> FactoryPatternSkeleton:
    digest=hashlib.sha256(data).hexdigest()
    if digest!=element.sha256: raise ValueError(f"Factory source hash mismatch for {element.locator}")
    song=SmfReader().parse(data)
    if not song.header.ppq: raise ValueError("Factory skeleton requires PPQ time division")
    cv1=_cv1_tracks(song); addresses=_addresses(song); notes,unmatched=pair_notes(song); event_track={event.event_id:track.index for track in song.tracks for event in track.events}; output=[]
    for note in notes:
        track=event_track.get(note.on_event_id,0)
        if track not in cv1: continue
        bank_msb,bank_lsb,program=addresses.get((track,note.channel),(0,0,0)); role=_role(note.channel,program)
        # RX guitar keys C7..G9 are hardware noise/fret/slide triggers, not harmony.
        trigger=role in {"drums","percussion"} or (role=="guitar" and (note.note<24 or note.note>=96))
        interval=None if trigger else note.note%12
        output.append(FactoryPatternNote(role,note.channel,bank_msb,bank_lsb,program,note.start_tick,max(1,note.end_tick-note.start_tick),note.note,note.velocity,interval,trigger,track))
    ignored=sum(1 for track in song.tracks if track.index not in cv1 and any(event.is_note_on for event in track.events))
    return FactoryPatternSkeleton(element.locator,digest,song.header.ppq,song.end_tick,tuple(sorted(output,key=lambda item:(item.start_tick,item.source_track,item.pitch))),ignored,len(unmatched))


class FactorySourceRepository:
    def __init__(self,source: Path,factory_member: str="Split Factory Styles.zip"):
        self.source=source; self.factory_member=factory_member

    def read(self,element: FactoryElementPattern) -> bytes:
        source_data=self.source.read_bytes()
        with zipfile.ZipFile(io.BytesIO(source_data)) as outer:
            direct={item.filename.casefold():item for item in outer.infolist() if not item.is_dir()}
            if element.locator.casefold() in direct: data=outer.read(direct[element.locator.casefold()])
            else:
                member=next((item for item in outer.infolist() if Path(item.filename).name.casefold()==self.factory_member.casefold()),None)
                if member is None: raise ValueError(f"Factory member not found: {self.factory_member}")
                with zipfile.ZipFile(io.BytesIO(outer.read(member))) as inner:
                    index={item.filename.casefold():item for item in inner.infolist() if not item.is_dir()}
                    target=index.get(element.locator.casefold())
                    if target is None: raise FileNotFoundError(f"Factory element not found: {element.locator}")
                    data=inner.read(target)
        if hashlib.sha256(data).hexdigest()!=element.sha256: raise ValueError(f"Factory source hash mismatch for {element.locator}")
        return data

    def skeleton(self,element: FactoryElementPattern) -> FactoryPatternSkeleton:
        return extract_factory_skeleton(element,self.read(element))
