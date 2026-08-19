from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from ..domain.events import EventKind, MidiEvent
from ..domain.song import SmfHeader, Song, Track
from .transform import ArrangedPattern


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    song: Song; note_count: int; trimmed_overlaps: int; channel_addresses: tuple[tuple[int,int,int,int],...]
    mixer_levels: tuple[tuple[int,str,int,int],...]


def _event(event_id,track,order,tick,status,data=b"",meta_type=None):
    return MidiEvent(event_id,EventKind.META if meta_type is not None else EventKind.CHANNEL,tick,track,order,status,data,meta_type)


def _mixer_levels(notes, end_tick: int, ppq: int):
    """Build conservative role-aware CC7/CC11 levels without touching velocity."""
    role_priority={"bass":5,"drums":4,"percussion":3,"guitar":2,"accompaniment":1}
    roles={}
    counts=defaultdict(int)
    for note in notes:
        counts[note.channel]+=1
        if role_priority.get(note.role,0)>role_priority.get(roles.get(note.channel,""),0): roles[note.channel]=note.role
    beats=max(1.0,end_tick/ppq); densest=max((count/beats for count in counts.values()),default=0.0)
    result={}
    for channel,role in roles.items():
        density=counts[channel]/beats
        velocities=[note.velocity for note in notes if note.channel==channel]
        velocity_compensation=round((96-median(velocities))*.18)
        if role=="bass":
            # Sparse bass needs more mixer headroom; dense bass is kept safer.
            volume=120 if densest and density<densest*.35 else 114
            volume=max(114,min(122,volume+velocity_compensation))
            expression=127
        elif role=="drums": volume,expression=104+velocity_compensation,118
        elif role=="percussion": volume,expression=98+velocity_compensation,114
        elif role=="guitar": volume,expression=101+velocity_compensation,116
        else: volume,expression=100+velocity_compensation,116
        volume=max(88,min(122,volume))
        result[channel]=(role,volume,expression)
    return result


def _expression_automation(patterns, channels, mixer, ppq):
    """Reinforce song-form dynamics from local Factory density, per channel."""
    result={channel:[] for channel in channels}
    for channel in channels:
        densities=[]
        for pattern in patterns:
            beats=max(0.25,(pattern.end_tick-pattern.start_tick)/ppq)
            count=sum(1 for note in pattern.notes if note.channel==channel)
            densities.append((pattern.start_tick,count/beats))
        active=[value for _,value in densities if value>0]
        if not active: continue
        low,high=min(active),max(active); role,_,ceiling=mixer[channel]
        floor=max(96,ceiling-(8 if role=="bass" else 12))
        previous=None
        for tick,value in densities:
            if value<=0: continue
            normalized=1.0 if high==low else (value-low)/(high-low)
            expression=round(floor+(ceiling-floor)*normalized)
            if expression!=previous: result[channel].append((tick,expression)); previous=expression
    return result


def materialize_arrangement(patterns: tuple[ArrangedPattern,...],target: Song) -> MaterializationResult:
    if not target.header.ppq: raise ValueError("materialization requires PPQ target")
    notes=[note for pattern in patterns for note in pattern.notes]; end_tick=max((pattern.end_tick for pattern in patterns),default=0)
    if not notes or end_tick<=0: raise ValueError("cannot materialize empty arrangement")
    addresses=defaultdict(set)
    for note in notes: addresses[note.channel].add((note.bank_msb,note.bank_lsb,note.program))
    mixer=_mixer_levels(notes,end_tick,target.header.ppq)
    expression_automation=_expression_automation(patterns,addresses.keys(),mixer,target.header.ppq)
    meta=[]; order=0
    for track in target.tracks:
        for event in track.events:
            if event.meta_type in (0x51,0x58,0x59) and event.absolute_tick<=end_tick:
                meta.append(_event(f"preview:meta:{order}",0,order,event.absolute_tick,0xFF,event.data,event.meta_type)); order+=1
    meta.append(_event("preview:meta:eot",0,order,end_tick,0xFF,b"",0x2F)); tracks=[Track(0,meta)]; trimmed=0; note_count=0
    for track_index,channel in enumerate(sorted(addresses),1):
        selected=sorted((note for note in notes if note.channel==channel),key=lambda item:(item.start_tick,item.pitch,item.duration_ticks)); normalized=[]; last={}
        for note in selected:
            previous=last.get(note.pitch)
            if previous is not None and normalized[previous][1]>note.start_tick:
                start,finish,old=normalized[previous]; normalized[previous]=(start,max(start+1,note.start_tick),old); trimmed+=1
                if start==note.start_tick:
                    normalized[previous]=(start,max(finish,note.start_tick+note.duration_ticks),old if old.velocity>=note.velocity else note); continue
            normalized.append((note.start_tick,min(end_tick,note.start_tick+note.duration_ticks),note)); last[note.pitch]=len(normalized)-1
        events=[]; sequence=0
        label=f"Factory channel {channel}".encode("ascii")
        events.append(_event(f"preview:t{track_index}:name",track_index,sequence,0,0xFF,label,0x03)); sequence+=1
        staged=[]; by_tick=defaultdict(set)
        role,volume,expression=mixer[channel]
        staged.append((0,1,7,_event(f"preview:t{track_index}:volume",track_index,0,0,0xB0+(channel-1),bytes((7,volume)))))
        automation=expression_automation[channel] or [(0,expression)]
        for tick,value in automation:
            staged.append((tick,1,11,_event(f"preview:t{track_index}:expression:{tick}",track_index,0,tick,0xB0+(channel-1),bytes((11,value)))))
        for start,_,note in normalized: by_tick[start].add((note.bank_msb,note.bank_lsb,note.program))
        if any(len(value)>1 for value in by_tick.values()): raise ValueError("Factory plan has simultaneous bank/program conflict within a MIDI channel")
        current=None
        for tick in sorted(by_tick):
            address=next(iter(by_tick[tick]))
            if address==current: continue
            bank_msb,bank_lsb,program=address
            staged.append((tick,1,0,_event(f"preview:t{track_index}:bank-msb:{tick}",track_index,0,tick,0xB0+(channel-1),bytes((0,bank_msb)))))
            staged.append((tick,1,32,_event(f"preview:t{track_index}:bank-lsb:{tick}",track_index,0,tick,0xB0+(channel-1),bytes((32,bank_lsb)))))
            staged.append((tick,2,0,_event(f"preview:t{track_index}:program:{tick}",track_index,0,tick,0xC0+(channel-1),bytes((program,))))); current=address
        for start,finish,note in normalized:
            staged.append((start,3,note.pitch,_event(f"preview:t{track_index}:n{note_count}:on",track_index,0,start,0x90+(channel-1),bytes((note.pitch,note.velocity)))))
            staged.append((finish,0,note.pitch,_event(f"preview:t{track_index}:n{note_count}:off",track_index,0,finish,0x80+(channel-1),bytes((note.pitch,0))))); note_count+=1
        for _,_,_,event in sorted(staged,key=lambda item:(item[0],item[1],item[2])):
            events.append(MidiEvent(event.event_id,event.kind,event.absolute_tick,event.track_index,sequence,event.status,event.data)); sequence+=1
        events.append(_event(f"preview:t{track_index}:eot",track_index,sequence,end_tick,0xFF,b"",0x2F)); tracks.append(Track(track_index,events))
    levels=tuple((channel,*mixer[channel]) for channel in sorted(mixer))
    return MaterializationResult(Song(SmfHeader(1,len(tracks),target.header.division),tracks),note_count,trimmed,tuple((channel,*address) for channel in sorted(addresses) for address in sorted(addresses[channel])),levels)
