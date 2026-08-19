from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from ..reference_learning import LearnedInstrumentProfile, ReferenceCatalog
from .transform import ArrangedPattern


def _role(channel,program):
    if channel==9 or 32<=program<=39: return "bass"
    if channel==10: return "drums"
    if channel==11: return "percussion"
    if 24<=program<=31: return "guitar"
    return "accompaniment"


@dataclass(frozen=True, slots=True)
class GoldTransferEvidence:
    address: str; match_level: str; gold_notes: int; source_profiles: int
    velocity_p10_p90: tuple[int,int]; duration_beats_p10_p90: tuple[float,float]|None


@dataclass(frozen=True, slots=True)
class GoldPerformanceTransfer:
    patterns: tuple[ArrangedPattern,...]; evidence: tuple[GoldTransferEvidence,...]
    changed_velocities: int; changed_durations: int; unmatched_addresses: tuple[str,...]
    factory_timing_locked: bool


def _weighted(candidates,field,index):
    values=[(getattr(item,field),item.gold_note_count) for item in candidates if getattr(item,field) is not None]
    if not values: return None
    return sum(value[index]*weight for value,weight in values)/sum(weight for _,weight in values)


def _resolve(catalog: ReferenceCatalog,address: str,role: str,program: int):
    strong=[item for item in catalog.profiles if item.gold_note_count>=50 and item.factory_note_count>=20 and item.gold_velocity_p10_p90]
    exact=[item for item in strong if item.address==address]
    candidates=exact or [item for item in strong if item.program==program and _role(item.channel,item.program)==role]
    if not candidates: return None
    level="exact" if exact else "same_program"
    low=round(_weighted(candidates,"gold_velocity_p10_p90",0)); high=round(_weighted(candidates,"gold_velocity_p10_p90",1))
    # A saturated Gold track still supplies intensity evidence, but its literal
    # 127/127 envelope must not erase all metrical and phrase dynamics.
    if high-low<8: low=max(1,high-8)
    duration=None
    if any(item.gold_duration_beats_p10_p90 for item in candidates): duration=(round(_weighted(candidates,"gold_duration_beats_p10_p90",0),6),round(_weighted(candidates,"gold_duration_beats_p10_p90",1),6))
    return GoldTransferEvidence(address,level,sum(item.gold_note_count for item in candidates),len(candidates),(low,high),duration)


def transfer_gold_performance(patterns: tuple[ArrangedPattern,...],catalog: ReferenceCatalog, *, ppq: int, seed: int=0) -> GoldPerformanceTransfer:
    if ppq<=0: raise ValueError("ppq must be positive")
    addresses={(note.channel,note.bank_msb,note.bank_lsb,note.program,note.role) for pattern in patterns for note in pattern.notes if not note.absolute_trigger}; resolved={}; unmatched=[]
    for channel,msb,lsb,program,role in sorted(addresses):
        address=f"{msb}:{lsb}:{program}:ch{channel}"; evidence=_resolve(catalog,address,role,program)
        if evidence: resolved[(channel,msb,lsb,program,role)]=evidence
        else: unmatched.append(address)
    changed_v=changed_d=0; output=[]
    for pattern in patterns:
        transformed=[]
        for note in pattern.notes:
            evidence=resolved.get((note.channel,note.bank_msb,note.bank_lsb,note.program,note.role))
            if note.absolute_trigger or evidence is None: transformed.append(note); continue
            low,high=evidence.velocity_p10_p90; center=(low+high)/2; beat=(note.start_tick//ppq)%4; accent=6 if beat==0 else 2 if beat==2 else -2
            token=f"{seed}:{note.role}:{note.channel}:{note.start_tick}:{note.pitch}".encode(); residual=(hashlib.sha256(token).digest()[0]%7)-3
            velocity=max(low,min(high,round(center+accent+residual)))
            duration=note.duration_ticks
            if note.role not in {"drums","percussion"} and evidence.match_level=="exact" and evidence.duration_beats_p10_p90:
                minimum=max(1,round(evidence.duration_beats_p10_p90[0]*ppq)); maximum=max(minimum,round(evidence.duration_beats_p10_p90[1]*ppq)); duration=max(minimum,min(maximum,duration))
            changed_v+=velocity!=note.velocity; changed_d+=duration!=note.duration_ticks; transformed.append(replace(note,velocity=velocity,duration_ticks=duration))
        output.append(replace(pattern,notes=tuple(transformed)))
    return GoldPerformanceTransfer(tuple(output),tuple(resolved[key] for key in sorted(resolved)),changed_v,changed_d,tuple(unmatched),True)
