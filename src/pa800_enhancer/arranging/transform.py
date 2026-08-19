from __future__ import annotations

from dataclasses import dataclass

from ..analysis.harmony import ChordSegment
from .factory_source import FactoryPatternSkeleton

ROLE_RANGES={"bass":(28,60),"guitar":(35,96),"accompaniment":(36,100)}


@dataclass(frozen=True, slots=True)
class ArrangedPatternNote:
    role: str; channel: int; bank_msb: int; bank_lsb: int; program: int
    start_tick: int; duration_ticks: int; pitch: int; velocity: int
    source_pitch: int; absolute_trigger: bool; chord_label: str|None


@dataclass(frozen=True, slots=True)
class ArrangedPattern:
    source_locator: str; start_tick: int; end_tick: int
    notes: tuple[ArrangedPatternNote,...]; harmonized_notes: int; inferred_chord_notes: int
    preserved_triggers: int; unknown_chord_notes: int


def _quality_interval(interval: int,quality: str|None) -> int:
    if quality=="minor" and interval==4: return 3
    if quality=="diminished":
        if interval==4: return 3
        if interval==7: return 6
    if quality=="sus2" and interval in (3,4): return 2
    if quality=="sus4" and interval in (3,4): return 5
    return interval


def _nearest_pitch(source: int,target_pc: int,bounds=None) -> int:
    low,high=bounds or (0,127); candidates=[pitch for pitch in range(max(low,source-24),min(high,source+24)+1) if pitch%12==target_pc]
    return min(candidates,key=lambda pitch:(abs(pitch-source),pitch)) if candidates else source


def _chord_at(chords,tick,max_hold_ticks):
    direct=next((item for item in chords if item.start_tick<=tick<item.end_tick and item.root is not None),None)
    if direct: return direct,direct.inferred
    previous=[item for item in chords if item.root is not None and item.end_tick<=tick and tick-item.end_tick<=max_hold_ticks]
    if previous: return max(previous,key=lambda item:item.end_tick),True
    following=[item for item in chords if item.root is not None and item.start_tick>tick and item.start_tick-tick<=max_hold_ticks]
    return (min(following,key=lambda item:item.start_tick),True) if following else (None,False)


def arrange_skeleton(skeleton: FactoryPatternSkeleton,chords: tuple[ChordSegment,...], *, start_tick: int,end_tick: int,target_ppq: int) -> ArrangedPattern:
    if end_tick<=start_tick: raise ValueError("arrangement end_tick must exceed start_tick")
    if target_ppq<=0: raise ValueError("target_ppq must be positive")
    if skeleton.length_ticks<=0: raise ValueError("Factory skeleton is empty")
    scale=target_ppq/skeleton.ppq; cycle=max(1,round(skeleton.length_ticks*scale)); output=[]; harmonized=inferred=triggers=unknown=0
    offset=0
    while start_tick+offset<end_tick:
        for note in skeleton.notes:
            tick=start_tick+offset+round(note.start_tick*scale)
            if tick>=end_tick: continue
            duration=min(max(1,round(note.duration_ticks*scale)),end_tick-tick); pitch=note.pitch; chord_label=None
            if note.absolute_trigger: triggers+=1
            else:
                chord,was_inferred=_chord_at(chords,tick,target_ppq*4)
                if chord is None: unknown+=1
                else:
                    interval=_quality_interval(note.chord_interval or 0,chord.quality); pitch=_nearest_pitch(note.pitch,(chord.root+interval)%12,ROLE_RANGES.get(note.role)); chord_label=chord.label; harmonized+=1
                    if was_inferred: inferred+=1
            output.append(ArrangedPatternNote(note.role,note.channel,note.bank_msb,note.bank_lsb,note.program,tick,duration,pitch,note.velocity,note.pitch,note.absolute_trigger,chord_label))
        offset+=cycle
    return ArrangedPattern(skeleton.locator,start_tick,end_tick,tuple(sorted(output,key=lambda item:(item.start_tick,item.channel,item.pitch))),harmonized,inferred,triggers,unknown)
