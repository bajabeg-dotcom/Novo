from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from .notes import Note, pair_notes
from ..domain.song import Song


@dataclass(frozen=True, slots=True)
class BarFeature:
    bar: int; start_tick: int; end_tick: int; note_density: float; drum_density: float
    velocity_mean: float; pitch_mean: float; onset_vector: tuple[float,...]; fill_score: float

    def vector(self): return (self.note_density/32,self.drum_density/16,self.velocity_mean/127,self.pitch_mean/127,*self.onset_vector)

@dataclass(frozen=True, slots=True)
class SectionBoundary:
    tick: int; bar: int; novelty: float; fill_score: float; silence_score: float; confidence: float

@dataclass(frozen=True, slots=True)
class SectionSegment:
    start_tick: int; end_tick: int; start_bar: int; end_bar: int; label: str; confidence: float; density: float

@dataclass(frozen=True, slots=True)
class TrackRoleSegment:
    track_index: int; channel: int; start_tick: int; end_tick: int; bank_msb: int; bank_lsb: int
    program: int; role: str; confidence: float; note_count: int; key_range: tuple[int,int]|None

@dataclass(frozen=True, slots=True)
class StructureAnalysis:
    bars: tuple[BarFeature,...]; boundaries: tuple[SectionBoundary,...]
    sections: tuple[SectionSegment,...]; track_roles: tuple[TrackRoleSegment,...]


def _meter(song):
    for track in song.tracks:
        for event in track.events:
            if event.meta_type==0x58 and len(event.data)>=2: return event.data[0],2**event.data[1]
    return 4,4

def _distance(left,right):
    a,b=left.vector(),right.vector(); return math.sqrt(sum((x-y)**2 for x,y in zip(a,b))/len(a))

def _bar_features(song: Song, notes: list[Note]):
    ppq=song.header.ppq or 96; numerator,denominator=_meter(song); bar_ticks=max(1,round(ppq*numerator*4/denominator)); count=max(1,math.ceil(song.end_tick/bar_ticks)); result=[]
    for bar in range(count):
        start=bar*bar_ticks; end=min(song.end_tick,max(start+1,start+bar_ticks)); selected=[n for n in notes if start<=n.start_tick<end]
        drums=[n for n in selected if n.channel==10]; melodic=[n for n in selected if n.channel!=10]; grid=[0]*16
        for note in selected: grid[min(15,int((note.start_tick-start)/max(1,end-start)*16))]+=1
        total=max(1,len(selected)); onset=tuple(round(value/total,6) for value in grid)
        fill_notes=[n for n in drums if n.start_tick>=end-max(1,ppq) and n.note in {38,40,41,43,45,47,48,50,49,51,57}]
        result.append(BarFeature(bar,start,end,len(melodic),len(drums),sum(n.velocity for n in selected)/total,sum(n.note for n in melodic)/max(1,len(melodic)),onset,min(1.0,len(fill_notes)/4)))
    return result

def _role(program,channel,notes,onset_counts,highest_score):
    if channel==10: return "drums",1.0
    if 32<=program<=39: return "bass",.98
    if 24<=program<=31: return "guitar",.95
    mean=sum(n.note for n in notes)/max(1,len(notes)); mono=sum(v==1 for v in onset_counts.values())/max(1,len(onset_counts))
    score=mean+18*mono
    if 64<=program<=87 and mono>.45: return "solo",min(.95,.72+.22*mono)
    if score>=highest_score-.01 and mono>.72: return "solo",min(.95,.60+.35*mono)
    if 40<=program<=55 or 88<=program<=103: return "pad",.82
    return "accompaniment",.68

def _track_roles(song,notes):
    event_track={event.event_id:track.index for track in song.tracks for event in track.events}; grouped=defaultdict(list)
    for note in notes: grouped[(event_track.get(note.on_event_id,0),note.channel)].append(note)
    scores=[]
    for key,items in grouped.items():
        if key[1]==10: continue
        counts=Counter(n.start_tick for n in items); scores.append((sum(n.note for n in items)/len(items)+18*sum(v==1 for v in counts.values())/len(counts),key))
    highest=max((score for score,_ in scores),default=0); output=[]
    for (track_index,channel),items in sorted(grouped.items()):
        state=[0,0,0]; changes=[(0,0,0,0)]
        for event in sorted(song.tracks[track_index].events,key=lambda e:(e.absolute_tick,e.order)):
            if event.channel!=channel: continue
            if event.message_type==0xB0 and len(event.data)==2 and event.data[0] in (0,32): state[0 if event.data[0]==0 else 1]=event.data[1]
            elif event.message_type==0xC0 and event.data: state[2]=event.data[0]; changes.append((event.absolute_tick,*state))
        boundaries=sorted({tick for tick,*_ in changes}|{song.end_tick}); current=(0,0,0)
        for index,start in enumerate(boundaries[:-1]):
            for change in changes:
                if change[0]<=start: current=change[1:]
            end=boundaries[index+1]; selected=[n for n in items if start<=n.start_tick<end]
            if not selected: continue
            counts=Counter(n.start_tick for n in selected); role,confidence=_role(current[2],channel,selected,counts,highest)
            output.append(TrackRoleSegment(track_index,channel,start,end,*current,role,round(confidence,6),len(selected),(min(n.note for n in selected),max(n.note for n in selected))))
    return output

def _mean_vector(bars):
    vectors=[bar.vector() for bar in bars]
    return tuple(sum(vector[index] for vector in vectors)/len(vectors) for index in range(len(vectors[0])))

def _vector_distance(left,right):
    return math.sqrt(sum((x-y)**2 for x,y in zip(left,right))/len(left))

def analyze_structure(song: Song, *, minimum_section_bars: int=8, maximum_section_bars: int=32, boundary_threshold: float=.12) -> StructureAnalysis:
    if not song.header.ppq: raise ValueError("structure analysis requires PPQ time division")
    if maximum_section_bars<minimum_section_bars: raise ValueError("maximum_section_bars must be at least minimum_section_bars")
    notes,_=pair_notes(song); bars=_bar_features(song,notes)
    phrase=max(4,minimum_section_bars); ranges=[]
    for start in range(0,len(bars),phrase): ranges.append([start,min(len(bars),start+phrase)])
    if len(ranges)>1 and ranges[-1][1]-ranges[-1][0]<max(4,phrase//2): ranges[-2][1]=ranges[-1][1]; ranges.pop()
    fingerprints=[_mean_vector(bars[start:end]) for start,end in ranges]

    # Online clustering preserves recurrence evidence without requiring a trained model.
    centroids=[]; members=[]; cluster_ids=[]
    cluster_threshold=max(.055,boundary_threshold*.72)
    for vector in fingerprints:
        distances=[_vector_distance(vector,centroid) for centroid in centroids]
        cluster=min(range(len(distances)),key=distances.__getitem__) if distances else -1
        if cluster<0 or distances[cluster]>cluster_threshold:
            centroids.append(vector); members.append([vector]); cluster_ids.append(len(centroids)-1)
        else:
            members[cluster].append(vector); cluster_ids.append(cluster)
            centroids[cluster]=tuple(sum(item[i] for item in members[cluster])/len(members[cluster]) for i in range(len(vector)))

    counts=Counter(cluster_ids); block_density=[sum(bar.note_density+bar.drum_density for bar in bars[start:end])/max(1,end-start) for start,end in ranges]
    recurrent={cluster for cluster,count in counts.items() if count>=2}
    recurrent_density={cluster:sum(block_density[i] for i,c in enumerate(cluster_ids) if c==cluster)/counts[cluster] for cluster in recurrent}
    chorus_cluster=max(recurrent_density,key=recurrent_density.get) if recurrent_density else None
    verse_cluster=max((c for c in recurrent if c!=chorus_cluster),key=lambda c:counts[c],default=None)
    labels=[]
    for index,cluster in enumerate(cluster_ids):
        if index==0 and len(ranges)>1 and block_density[index]<sorted(block_density)[len(block_density)//2]*.9: label="intro"
        elif index==len(ranges)-1 and len(ranges)>1: label="ending"
        elif cluster==chorus_cluster: label="chorus"
        elif cluster==verse_cluster or cluster in recurrent: label="verse"
        else: label="bridge" if 0<index<len(ranges)-1 else "unknown"
        labels.append(label)

    # Merge adjacent phrase blocks only when both their musical fingerprint and label agree.
    groups=[]
    for index,(start,end) in enumerate(ranges):
        if groups and labels[index]==groups[-1][2] and cluster_ids[index]==groups[-1][3] and end-groups[-1][0]<=maximum_section_bars: groups[-1][1]=end
        else: groups.append([start,end,labels[index],cluster_ids[index]])
    candidates=[]; sections=[]
    for index,(start,end,label,cluster) in enumerate(groups):
        density=sum(bar.note_density+bar.drum_density for bar in bars[start:end])/max(1,end-start)
        recurrence=min(1.0,counts[cluster]/3); confidence=.48+.28*recurrence if label not in {"intro","ending"} else .62
        sections.append(SectionSegment(bars[start].start_tick,bars[end-1].end_tick,start,end,label,round(confidence,6),round(density,6)))
        if index:
            previous=groups[index-1]; novelty=_vector_distance(_mean_vector(bars[previous[0]:previous[1]]),_mean_vector(bars[start:end]))
            fill=bars[start-1].fill_score; silence=max(0.0,1-bars[start].note_density/max(1,bars[start-1].note_density)); confidence=min(1.0,novelty*3.5+fill*.2+silence*.2)
            candidates.append(SectionBoundary(bars[start].start_tick,start,round(novelty,6),round(fill,6),round(silence,6),round(confidence,6)))
    return StructureAnalysis(tuple(bars),tuple(candidates),tuple(sections),tuple(_track_roles(song,notes)))
