from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from ..analysis.harmony import CHORD_QUALITIES, ChordSegment
from ..arranging.transform import ArrangedPattern


ROLE_RANGES={"bass":(28,60),"guitar":(35,96),"accompaniment":(36,100)}


@dataclass(frozen=True, slots=True)
class EvaluationMetric:
    name: str; value: float; warning_threshold: float|None; blocker_threshold: float|None; passed: bool


@dataclass(frozen=True, slots=True)
class MusicalIssue:
    severity: str; code: str; message: str; count: int


@dataclass(frozen=True, slots=True)
class MusicalEvaluation:
    status: str; score: float; metrics: tuple[EvaluationMetric,...]; issues: tuple[MusicalIssue,...]


def _ratio(numerator,denominator): return numerator/max(1,denominator)


def evaluate_arrangement(patterns: tuple[ArrangedPattern,...],chords: tuple[ChordSegment,...], *, ppq: int) -> MusicalEvaluation:
    if ppq<=0: raise ValueError("ppq must be positive")
    notes=[note for pattern in patterns for note in pattern.notes]; musical=[note for note in notes if not note.absolute_trigger]; total_musical=len(musical)
    unknown=sum(pattern.unknown_chord_notes for pattern in patterns); inferred=sum(pattern.inferred_chord_notes for pattern in patterns); harmonized=sum(pattern.harmonized_notes for pattern in patterns)
    unknown_ratio=_ratio(unknown,total_musical); inferred_ratio=_ratio(inferred,harmonized)
    out_of_range=[]
    for note in musical:
        bounds=ROLE_RANGES.get(note.role)
        if bounds and not bounds[0]<=note.pitch<=bounds[1]: out_of_range.append(note)
    range_ratio=_ratio(len(out_of_range),total_musical)
    strong=[]; dissonant=[]
    tolerance=max(1,ppq//24)
    for note in musical:
        if min(note.start_tick%ppq,ppq-note.start_tick%ppq)>tolerance: continue
        chord=next((item for item in chords if item.start_tick<=note.start_tick<item.end_tick and item.root is not None and item.quality in CHORD_QUALITIES),None)
        if not chord: continue
        strong.append(note); tones={(chord.root+interval)%12 for interval in CHORD_QUALITIES[chord.quality]}
        if note.pitch%12 not in tones: dissonant.append(note)
    dissonance_ratio=_ratio(len(dissonant),len(strong))
    onset=defaultdict(list)
    for note in musical: onset[note.start_tick].append(note)
    collisions=0
    for items in onset.values():
        by_pitch=defaultdict(list)
        for note in items: by_pitch[note.pitch].append(note)
        for same_pitch in by_pitch.values():
            if len({item.role for item in same_pitch})>1: collisions+=len(same_pitch)-1
    collision_ratio=_ratio(collisions,total_musical)
    drums=[note for note in notes if note.role in {"drums","percussion"}]; drum_duplicates=sum(count-1 for count in Counter((note.start_tick,note.channel,note.pitch) for note in drums).values() if count>1); drum_duplicate_ratio=_ratio(drum_duplicates,len(drums))
    metrics=(
        EvaluationMetric("unknown_chord_ratio",round(unknown_ratio,6),.05,.15,unknown_ratio<=.15),
        EvaluationMetric("inferred_chord_ratio",round(inferred_ratio,6),.20,.40,inferred_ratio<=.40),
        EvaluationMetric("role_range_violation_ratio",round(range_ratio,6),.005,.02,range_ratio<=.02),
        EvaluationMetric("strong_beat_dissonance_ratio",round(dissonance_ratio,6),.30,.50,dissonance_ratio<=.50),
        EvaluationMetric("cross_role_collision_ratio",round(collision_ratio,6),.08,.18,collision_ratio<=.18),
        EvaluationMetric("drum_duplicate_ratio",round(drum_duplicate_ratio,6),.03,.10,drum_duplicate_ratio<=.10),
    )
    issues=[]
    definitions=((unknown_ratio,.05,.15,"HARMONY_UNKNOWN",unknown,"notes lack a confident chord"),(inferred_ratio,.20,.40,"HARMONY_INFERRED",inferred,"notes use held/anticipated chord evidence"),(range_ratio,.005,.02,"ROLE_RANGE",len(out_of_range),"notes are outside conservative role range"),(dissonance_ratio,.30,.50,"STRONG_BEAT_DISSONANCE",len(dissonant),"strong-beat notes are outside the detected triad"),(collision_ratio,.08,.18,"ROLE_COLLISION",collisions,"cross-role notes collide on the same pitch"),(drum_duplicate_ratio,.03,.10,"DRUM_DUPLICATE",drum_duplicates,"duplicate drum hits share tick/channel/pitch"))
    for value,warning,blocker,code,count,message in definitions:
        if value>blocker: issues.append(MusicalIssue("blocker",code,message,count))
        elif value>warning: issues.append(MusicalIssue("warning",code,message,count))
    if not notes: issues.append(MusicalIssue("blocker","EMPTY_ARRANGEMENT","arrangement contains no notes",0))
    status="blocked" if any(item.severity=="blocker" for item in issues) else "review" if issues else "ready"
    penalties=(unknown_ratio*.28+inferred_ratio*.16+range_ratio*.18+dissonance_ratio*.18+collision_ratio*.10+drum_duplicate_ratio*.10)
    return MusicalEvaluation(status,round(max(0.0,100*(1-min(1.0,penalties))),3),metrics,tuple(issues))
