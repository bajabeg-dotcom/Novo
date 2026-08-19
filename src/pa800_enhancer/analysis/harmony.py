from __future__ import annotations

import math
from dataclasses import dataclass

from .notes import Note, pair_notes
from ..domain.song import Song


PITCH_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
CHORD_QUALITIES = {
    "major": (0, 4, 7), "minor": (0, 3, 7), "diminished": (0, 3, 6),
    "sus2": (0, 2, 7), "sus4": (0, 5, 7),
}


@dataclass(frozen=True, slots=True)
class KeyCandidate:
    root: int
    mode: str
    score: float
    probability: float

    @property
    def label(self) -> str:
        return f"{PITCH_NAMES[self.root]} {self.mode}"


@dataclass(frozen=True, slots=True)
class KeyWindow:
    start_tick: int
    end_tick: int
    candidates: tuple[KeyCandidate, ...]


@dataclass(frozen=True, slots=True)
class ChordSegment:
    start_tick: int
    end_tick: int
    root: int | None
    quality: str | None
    bass: int | None
    confidence: float
    evidence_notes: int
    inferred: bool = False

    @property
    def label(self) -> str:
        if self.root is None or self.quality is None:
            return "unknown"
        suffix = {"major": "", "minor": "m", "diminished": "dim", "sus2": "sus2", "sus4": "sus4"}[self.quality]
        inversion = f"/{PITCH_NAMES[self.bass]}" if self.bass is not None and self.bass != self.root else ""
        return f"{PITCH_NAMES[self.root]}{suffix}{inversion}"


@dataclass(frozen=True, slots=True)
class HarmonyAnalysis:
    key_windows: tuple[KeyWindow, ...]
    chords: tuple[ChordSegment, ...]

    @property
    def primary_key(self) -> KeyCandidate | None:
        totals: dict[tuple[int,str], list[float]] = {}
        duration_sum=0.0
        for window in self.key_windows:
            duration=max(1,window.end_tick-window.start_tick); duration_sum+=duration
            for candidate in window.candidates:
                values=totals.setdefault((candidate.root,candidate.mode),[0.0,0.0])
                values[0]+=candidate.score*duration; values[1]+=candidate.probability*duration
        if not totals or not duration_sum: return None
        root,mode=max(totals,key=lambda key:totals[key][1])
        score,probability=totals[(root,mode)]
        return KeyCandidate(root,mode,round(score/duration_sum,6),round(probability/duration_sum,6))


def _correlation(values: list[float], profile: tuple[float, ...]) -> float:
    left=sum(values)/12; right=sum(profile)/12
    numerator=sum((a-left)*(b-right) for a,b in zip(values,profile))
    denominator=math.sqrt(sum((a-left)**2 for a in values)*sum((b-right)**2 for b in profile))
    return numerator/denominator if denominator else 0.0


def _key_candidates(histogram: list[float], limit: int=5) -> tuple[KeyCandidate, ...]:
    scored=[]
    for root in range(12):
        for mode,profile in (("major",MAJOR_PROFILE),("minor",MINOR_PROFILE)):
            rotated=profile[-root:]+profile[:-root] if root else profile
            scored.append((root,mode,_correlation(histogram,rotated)))
    maximum=max(score for _,_,score in scored); weights=[math.exp((score-maximum)*5) for _,_,score in scored]; total=sum(weights)
    candidates=[KeyCandidate(root,mode,round(score,6),round(weight/total,6)) for (root,mode,score),weight in zip(scored,weights)]
    return tuple(sorted(candidates,key=lambda item:item.probability,reverse=True)[:limit])


def _histogram(notes: list[Note], start: int, end: int) -> list[float]:
    values=[0.0]*12
    for note in notes:
        overlap=max(0,min(note.audible_end_tick,end)-max(note.start_tick,start))
        if overlap: values[note.note%12]+=overlap*max(1,note.velocity)/127
    return values


def _score_chords(notes: list[Note],start: int,end: int):
    active=[note for note in notes if note.start_tick < end and note.audible_end_tick > start]
    if not active: return [],None,0.0,0
    histogram=_histogram(active,start,end); bass=min(active,key=lambda item:item.note).note%12; scored=[]
    for root in range(12):
        for quality,intervals in CHORD_QUALITIES.items():
            tones={(root+interval)%12 for interval in intervals}; support=sum(histogram[pitch] for pitch in tones); outside=sum(histogram)-support
            scored.append((support-outside*.22+histogram[root]*.35+(.30 if bass in tones else -.20),root,quality))
    return sorted(scored,reverse=True),bass,sum(histogram),len(active)


def _infer_chord(notes: list[Note], start: int, end: int, minimum_confidence: float) -> ChordSegment:
    scored,bass,total,evidence_notes=_score_chords(notes,start,end)
    if not scored: return ChordSegment(start,end,None,None,None,0.0,0)
    best=scored[0]
    competing_root=next((item for item in scored[1:] if item[1]!=best[1]),scored[1])
    root_margin=max(0.0,best[0]-competing_root[0])
    same_root=next((item for item in scored[1:] if item[1]==best[1]),None)
    quality_margin=max(0.0,best[0]-same_root[0]) if same_root else root_margin
    root_confidence=1-math.exp(-root_margin/max(0.5,total*0.18))
    quality_confidence=1-math.exp(-quality_margin/max(0.5,total*0.18))
    confidence=.82*root_confidence+.18*quality_confidence
    if confidence < minimum_confidence:
        return ChordSegment(start,end,None,None,bass,round(confidence,6),evidence_notes)
    return ChordSegment(start,end,best[1],best[2],bass,round(confidence,6),evidence_notes)


def _transition_penalty(left,right):
    if left==right: return 0.0
    if left[0]==right[0]: return .08
    distance=min((left[0]-right[0])%12,(right[0]-left[0])%12)
    return .035*distance+(.04 if left[1]!=right[1] else 0)


def _decode_temporal_path(raw,candidate_rows,minimum_confidence):
    output=list(raw); index=0
    while index<len(raw):
        if not candidate_rows[index]: index+=1; continue
        end=index
        while end<len(raw) and candidate_rows[end]: end+=1
        rows=[]
        for candidates,total in candidate_rows[index:end]:
            best_by_state={}
            for score,root,quality in candidates:
                best_by_state.setdefault((root,quality),score)
            maximum=max(best_by_state.values()); scale=max(.5,total*.22)
            rows.append({state:(score-maximum)/scale for state,score in best_by_state.items()})
        scores=rows[0]; back=[]
        for row in rows[1:]:
            current={}; links={}
            for state,emission in row.items():
                previous=max(scores,key=lambda prior:scores[prior]-_transition_penalty(prior,state)); current[state]=scores[previous]-_transition_penalty(previous,state)+emission; links[state]=previous
            scores=current; back.append(links)
        state=max(scores,key=scores.get); path=[state]
        for links in reversed(back): state=links[state]; path.append(state)
        path.reverse()
        for offset,state in enumerate(path):
            position=index+offset; chord=raw[position]
            if chord.root is None and chord.evidence_notes>=2:
                output[position]=ChordSegment(chord.start_tick,chord.end_tick,state[0],state[1],chord.bass,round(max(.08,chord.confidence),6),chord.evidence_notes,True)
        index=end
    return output


def _smooth_chords(raw: list[ChordSegment],notes: list[Note],ppq: int,minimum_confidence: float) -> list[ChordSegment]:
    contextual=[]
    for chord in raw:
        if chord.root is not None or chord.evidence_notes<2 or chord.end_tick-chord.start_tick>ppq*4:
            contextual.append(chord); continue
        expanded=_infer_chord(notes,max(0,chord.start_tick-ppq),chord.end_tick+ppq,max(.08,minimum_confidence*.55))
        if expanded.root is None: contextual.append(chord)
        else: contextual.append(ChordSegment(chord.start_tick,chord.end_tick,expanded.root,expanded.quality,expanded.bass,round(expanded.confidence*.75,6),chord.evidence_notes,True))
    bridged=list(contextual)
    for index,chord in enumerate(contextual):
        if chord.root is not None or chord.end_tick-chord.start_tick>ppq*2 or index==0 or index==len(contextual)-1: continue
        left,right=contextual[index-1],contextual[index+1]
        if left.root is not None and (left.root,left.quality)==(right.root,right.quality):
            bridged[index]=ChordSegment(chord.start_tick,chord.end_tick,left.root,left.quality,left.bass,round(min(left.confidence,right.confidence)*.65,6),chord.evidence_notes,True)
    return bridged


def analyze_harmony(song: Song, *, key_window_bars: int=8, chord_subdivision: int=1,
                    minimum_chord_confidence: float=0.18, smooth: bool=True,
                    chord_context_beats: float=.5, temporal_decode: bool=True) -> HarmonyAnalysis:
    if not song.header.ppq: raise ValueError("harmony analysis requires PPQ time division")
    if key_window_bars < 1 or chord_subdivision < 1 or chord_context_beats<0: raise ValueError("analysis window values must be positive")
    ppq=song.header.ppq; notes,_=pair_notes(song)
    harmonic=[note for note in notes if note.channel != 10]
    key_ticks=ppq*4*key_window_bars; windows=[]
    for start in range(0,max(1,song.end_tick),key_ticks):
        end=min(song.end_tick,max(start+1,start+key_ticks)); histogram=_histogram(harmonic,start,end)
        windows.append(KeyWindow(start,end,_key_candidates(histogram) if sum(histogram)>0 else ()))
    cell=max(1,ppq//chord_subdivision); raw=[]
    padding=round(ppq*chord_context_beats); candidate_rows=[]
    for start in range(0,max(1,song.end_tick),cell):
        end=min(song.end_tick,max(start+1,start+cell)); window_start=max(0,start-padding); window_end=min(song.end_tick,end+padding); inferred=_infer_chord(harmonic,window_start,window_end,minimum_chord_confidence)
        raw.append(ChordSegment(start,end,inferred.root,inferred.quality,inferred.bass,inferred.confidence,inferred.evidence_notes))
        scored,_,total,_=_score_chords(harmonic,window_start,window_end); candidate_rows.append((scored,total) if scored else None)
    if temporal_decode: raw=_decode_temporal_path(raw,candidate_rows,minimum_chord_confidence)
    if smooth: raw=_smooth_chords(raw,harmonic,ppq,minimum_chord_confidence)
    merged=[]
    for chord in raw:
        if merged and (merged[-1].root,merged[-1].quality,merged[-1].bass,merged[-1].inferred)==(chord.root,chord.quality,chord.bass,chord.inferred):
            previous=merged.pop(); total=previous.evidence_notes+chord.evidence_notes
            confidence=(previous.confidence*previous.evidence_notes+chord.confidence*chord.evidence_notes)/max(1,total)
            merged.append(ChordSegment(previous.start_tick,chord.end_tick,chord.root,chord.quality,chord.bass,round(confidence,6),total,chord.inferred))
        else: merged.append(chord)
    return HarmonyAnalysis(tuple(windows),tuple(merged))
