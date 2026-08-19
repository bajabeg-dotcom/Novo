from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..retrieval.factory import FactoryIndex, FactoryQuery
from ..retrieval.factory_corpus import FactoryElementPattern, FactoryPatternCatalog
from .energy import EnergyPlan, SectionEnergy


DEFAULT_ROLES=("bass","drums","percussion","guitar","accompaniment")


@dataclass(frozen=True, slots=True)
class FactorySectionAssignment:
    section_index: int; label: str; energy: float; variation_level: int|None
    primary: FactoryElementPattern; transition: FactoryElementPattern|None
    confidence: float; evidence: tuple[tuple[str,float],...]


@dataclass(frozen=True, slots=True)
class FactorySongPlan:
    style: str; family: str; score: float; assignments: tuple[FactorySectionAssignment,...]
    role_coverage: tuple[str,...]; missing_roles: tuple[str,...]; evidence: tuple[tuple[str,float],...]


def _roles(elements): return {role.role for element in elements for role in element.roles}


def _complexity(element: FactoryElementPattern) -> float:
    notes=sum(role.note_count for role in element.roles); role_factor=min(1.0,len({role.role for role in element.roles})/5)
    density=min(1.0,notes/max(16,element.end_tick/max(1,element.ppq)*10))
    return .7*density+.3*role_factor


def _choose(elements: list[FactoryElementPattern], target: float, required_roles: tuple[str,...]) -> tuple[FactoryElementPattern,float]:
    if not elements: raise ValueError("no Factory element candidates")
    ranked=[]
    for element in elements:
        coverage=len(_roles((element,))&set(required_roles))/max(1,len(required_roles)); closeness=max(0.0,1-abs(_complexity(element)-target)); quality=1.0 if element.evidence_status=="complete" else .82
        ranked.append((.50*closeness+.35*coverage+.15*quality,element))
    score,element=max(ranked,key=lambda item:(item[0],item[1].locator.casefold()))
    return element,score


class FactorySongPlanner:
    def __init__(self,grooves: FactoryIndex,patterns: FactoryPatternCatalog):
        self.grooves=grooves; grouped=defaultdict(list)
        for element in patterns.elements: grouped[element.style.casefold()].append(element)
        self._patterns={key:tuple(value) for key,value in grouped.items()}

    def plan(self,energy: EnergyPlan,query: FactoryQuery, *, required_roles: tuple[str,...]=DEFAULT_ROLES) -> FactorySongPlan:
        if not energy.sections: raise ValueError("energy plan has no sections")
        levels=sorted({item.variation_level for item in energy.sections if item.variation_level is not None})
        by_level={level:{item.style.casefold():item for item in self.grooves.retrieve(FactoryQuery(query.family,level,query.meter,query.density,query.drum_density,query.off16_ratio,query.minimum_channels,query.style),limit=len(self.grooves.styles))} for level in levels}
        required_types={item.element_type for item in energy.sections}|{item.transition_after for item in energy.sections if item.transition_after}
        style_scores=[]
        for style in self.grooves.styles:
            key=style.name.casefold(); elements=self._patterns.get(key,())
            if not elements or any(key not in by_level[level] for level in levels): continue
            relevant=[item for item in elements if (item.element_type=="variation" and item.variation_level in levels) or item.element_type in required_types]
            covered=_roles(item for item in relevant if item.element_type=="variation"); role_score=len(covered&set(required_roles))/max(1,len(required_roles))
            present={item.element_type for item in relevant}; form_score=len(present&required_types)/max(1,len(required_types)); groove_score=sum(by_level[level][key].score for level in levels)/max(1,len(levels))
            score=.70*groove_score+.20*role_score+.10*form_score
            style_scores.append((score,style,relevant,covered,groove_score,role_score,form_score))
        if not style_scores: raise ValueError("no single Factory style covers the requested song plan")
        score,style,elements,covered,groove_score,role_score,form_score=max(style_scores,key=lambda item:(item[0],item[1].name.casefold()))
        assignments=[]
        for index,section in enumerate(energy.sections):
            primary_candidates=[item for item in elements if item.element_type==section.element_type and (section.variation_level is None or item.variation_level==section.variation_level)]
            primary,primary_score=_choose(primary_candidates,section.energy,required_roles)
            transition=None; transition_score=1.0
            if section.transition_after:
                candidates=[item for item in elements if item.element_type==section.transition_after]
                target=energy.sections[min(index+1,len(energy.sections)-1)].energy
                transition,transition_score=_choose(candidates,target,required_roles)
            confidence=min(1.0,.45*section.confidence+.35*primary_score+.20*transition_score)
            assignments.append(FactorySectionAssignment(section.section_index,section.label,section.energy,section.variation_level,primary,transition,round(confidence,6),(("section",section.confidence),("primary",round(primary_score,6)),("transition",round(transition_score,6)))))
        missing=tuple(role for role in required_roles if role not in covered); coverage=tuple(role for role in required_roles if role in covered)
        return FactorySongPlan(style.name,style.family,round(score,6),tuple(assignments),coverage,missing,(("groove",round(groove_score,6)),("role_coverage",round(role_score,6)),("form_coverage",round(form_score,6))))
