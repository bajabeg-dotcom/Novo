from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace

from ..domain.events import EventKind, MidiEvent
from ..domain.song import Song, Track


def _role(channel: int, program: int) -> str:
    if channel == 10: return "drums"
    if 32 <= program <= 39: return "bass"
    if 24 <= program <= 31: return "guitar"
    return "accompaniment"


@dataclass(frozen=True, slots=True)
class ConservativeSoundMapping:
    channel: int; role: str; source_program: int
    bank_msb: int; bank_lsb: int; program: int; evidence_notes: int


@dataclass(frozen=True, slots=True)
class ConservativeOptimizationResult:
    song: Song; mappings: tuple[ConservativeSoundMapping,...]
    preserved_tracks: int; preserved_notes: int; skipped_channels: tuple[int,...]


def optimize_conservatively(song: Song, catalog) -> ConservativeOptimizationResult:
    """Map sounds and normalize initialization without changing musical notes."""
    channel_program={}
    note_count=0
    for track in song.tracks:
        for event in sorted(track.events,key=lambda item:(item.absolute_tick,item.order)):
            if event.is_note_on: note_count+=1
            if event.channel and event.message_type==0xC0 and event.data:
                channel_program.setdefault(event.channel,event.data[0])
    evidence=defaultdict(Counter)
    for element in catalog.elements:
        for item in element.roles:
            evidence[(item.role,item.program)][(item.bank_msb,item.bank_lsb,item.program)]+=item.note_count
    usage=defaultdict(int); mappings={}; skipped=[]
    for channel,program in sorted(channel_program.items()):
        role=_role(channel,program)
        if role=="drums": candidates=[((120,0,4),1)]
        else: candidates=evidence[(role,program)].most_common()
        if not candidates: skipped.append(channel); continue
        address,count=candidates[usage[(role,program)]%len(candidates)]; usage[(role,program)]+=1
        mappings[channel]=ConservativeSoundMapping(channel,role,program,*address,count)
    tracks=[]
    for track in song.tracks:
        events=[]
        for event in track.events:
            mapping=mappings.get(event.channel or -1); updated=event
            if mapping:
                if event.message_type==0xB0 and len(event.data)==2 and event.data[0]==0:
                    updated=replace(event,absolute_tick=0,order=-300,data=bytes((0,mapping.bank_msb)))
                elif event.message_type==0xB0 and len(event.data)==2 and event.data[0]==32:
                    updated=replace(event,absolute_tick=0,order=-299,data=bytes((32,mapping.bank_lsb)))
                elif event.message_type==0xC0 and event.data:
                    updated=replace(event,absolute_tick=0,order=-298,data=bytes((mapping.program,)))
            events.append(updated)
        tracks.append(Track(track.index,events))
    projected=Song(song.header,tracks,song.source_path,song.source_sha256,song.raw_document)
    return ConservativeOptimizationResult(projected,tuple(mappings[key] for key in sorted(mappings)),len(song.tracks),note_count,tuple(skipped))
