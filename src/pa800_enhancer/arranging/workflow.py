from __future__ import annotations

from dataclasses import dataclass

from ..analysis.harmony import HarmonyAnalysis
from ..planning.energy import EnergyPlan
from ..planning.factory_song import FactorySongPlan
from .factory_source import FactorySourceRepository
from .transform import ArrangedPattern, arrange_skeleton


@dataclass(frozen=True, slots=True)
class ArrangementPlacement:
    section_index: int; kind: str; start_tick: int; end_tick: int; source_locator: str


@dataclass(frozen=True, slots=True)
class FactoryArrangementPreview:
    patterns: tuple[ArrangedPattern,...]; placements: tuple[ArrangementPlacement,...]


def arrange_song_plan(plan: FactorySongPlan,energy: EnergyPlan,harmony: HarmonyAnalysis,repository: FactorySourceRepository, *, target_ppq: int) -> FactoryArrangementPreview:
    patterns=[]; placements=[]
    for assignment in plan.assignments:
        section=energy.sections[assignment.section_index]; primary_end=section.end_tick; transition_skeleton=None
        if assignment.transition:
            transition_skeleton=repository.skeleton(assignment.transition); duration=max(1,round(transition_skeleton.length_ticks*target_ppq/transition_skeleton.ppq)); primary_end=max(section.start_tick,section.end_tick-min(duration,section.end_tick-section.start_tick))
        if primary_end>section.start_tick:
            skeleton=repository.skeleton(assignment.primary); patterns.append(arrange_skeleton(skeleton,harmony.chords,start_tick=section.start_tick,end_tick=primary_end,target_ppq=target_ppq)); placements.append(ArrangementPlacement(assignment.section_index,"primary",section.start_tick,primary_end,assignment.primary.locator))
        if transition_skeleton and primary_end<section.end_tick:
            patterns.append(arrange_skeleton(transition_skeleton,harmony.chords,start_tick=primary_end,end_tick=section.end_tick,target_ppq=target_ppq)); placements.append(ArrangementPlacement(assignment.section_index,"transition",primary_end,section.end_tick,assignment.transition.locator))
    return FactoryArrangementPreview(tuple(patterns),tuple(placements))
