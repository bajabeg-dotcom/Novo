from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from .factory import FactoryIndex, FactoryQuery
from .factory_corpus import FactoryElementPattern, FactoryPatternCatalog


DEFAULT_ROLES=("bass","drums","percussion","guitar","accompaniment")


@dataclass(frozen=True, slots=True)
class FactoryPackageQuery:
    groove: FactoryQuery; required_roles: tuple[str,...]=DEFAULT_ROLES
    include_types: tuple[str,...]=("variation","fill","break","intro","ending")


@dataclass(frozen=True, slots=True)
class FactoryPackageCandidate:
    style: str; family: str; score: float; groove_score: float
    variation_level: int; role_coverage: tuple[str,...]; missing_roles: tuple[str,...]
    elements: tuple[FactoryElementPattern,...]; evidence: tuple[tuple[str,float],...]
    limitations: tuple[str,...]


class FactoryPackageIndex:
    def __init__(self,grooves: FactoryIndex,patterns: FactoryPatternCatalog):
        self.grooves=grooves; self.patterns=patterns; grouped=defaultdict(list)
        for element in patterns.elements: grouped[element.style.casefold()].append(element)
        self._by_style={key:tuple(value) for key,value in grouped.items()}

    def retrieve(self,query: FactoryPackageQuery, *, limit: int=5) -> tuple[FactoryPackageCandidate,...]:
        if limit<1: raise ValueError("limit must be positive")
        groove_candidates=self.grooves.retrieve(query.groove,limit=len(self.grooves.styles)); output=[]
        for groove in groove_candidates:
            available=self._by_style.get(groove.style.casefold(),())
            variation=[item for item in available if item.element_type=="variation" and item.variation_level==query.groove.variation_level]
            if not variation: continue
            selected=list(variation)
            for element_type in query.include_types:
                if element_type=="variation": continue
                selected.extend(item for item in available if item.element_type==element_type)
            selected=sorted(selected,key=lambda item:(item.element_type,item.locator.casefold()))
            variation_roles=Counter(role.role for item in variation for role in item.roles)
            covered=tuple(role for role in query.required_roles if variation_roles[role]>0); missing=tuple(role for role in query.required_roles if variation_roles[role]==0)
            coverage=len(covered)/max(1,len(query.required_roles)); transitions=len({item.element_type for item in selected if item.element_type!="variation"})/max(1,len(set(query.include_types)-{"variation"}))
            completeness=1.0 if variation else 0.0; truncation=sum(item.boundary_truncated_events for item in selected)/max(1,sum(sum(role.note_count for role in item.roles) for item in selected))
            boundary_quality=max(0.0,1-min(1.0,truncation)); score=.72*groove.score+.18*coverage+.07*transitions+.03*boundary_quality
            evidence=(("groove",groove.score),("role_coverage",coverage),("transition_coverage",transitions),("variation_present",completeness),("boundary_quality",boundary_quality))
            limitations=[]
            if missing: limitations.append("missing requested roles in selected variation: "+", ".join(missing))
            if truncation: limitations.append("some source notes cross Factory element boundaries; only complete note pairs are indexed")
            output.append(FactoryPackageCandidate(groove.style,groove.family,round(score,6),groove.score,query.groove.variation_level,covered,missing,tuple(selected),tuple((name,round(value,6)) for name,value in evidence),tuple(limitations)))
        return tuple(sorted(output,key=lambda item:(-item.score,item.style.casefold()))[:limit])
