from __future__ import annotations

from dataclasses import dataclass

from ..analysis.structure import StructureAnalysis


LABEL_PRIOR={"intro":.12,"verse":.38,"chorus":.82,"bridge":.58,"ending":.30,"unknown":.45}


@dataclass(frozen=True, slots=True)
class SectionEnergy:
    section_index: int; start_tick: int; end_tick: int; label: str
    energy: float; variation_level: int|None; element_type: str
    transition_after: str|None; confidence: float; evidence: tuple[tuple[str,float],...]


@dataclass(frozen=True, slots=True)
class EnergyPlan:
    sections: tuple[SectionEnergy,...]; minimum_energy: float; maximum_energy: float


def _normalize(value: float,low: float,high: float) -> float:
    if high<=low: return .5
    return max(0.0,min(1.0,(value-low)/(high-low)))


def map_section_energy(analysis: StructureAnalysis) -> EnergyPlan:
    if not analysis.sections: return EnergyPlan((),0.0,0.0)
    densities=[section.density for section in analysis.sections]; low=min(densities); high=max(densities); raw=[]
    for section in analysis.sections:
        bars=analysis.bars[section.start_bar:section.end_bar]
        drum=sum(bar.drum_density for bar in bars)/max(1,len(bars)); velocity=sum(bar.velocity_mean for bar in bars)/max(1,len(bars))
        density_norm=_normalize(section.density,low,high); drum_norm=min(1.0,drum/12); velocity_norm=max(0.0,min(1.0,(velocity-45)/65)); prior=LABEL_PRIOR.get(section.label,.45)
        energy=.46*density_norm+.22*drum_norm+.12*velocity_norm+.20*prior
        raw.append((max(0.0,min(1.0,energy)),density_norm,drum_norm,velocity_norm,prior))
    output=[]
    for index,(section,values) in enumerate(zip(analysis.sections,raw)):
        energy,density_norm,drum_norm,velocity_norm,prior=values
        if section.label=="intro" and index==0: element,variation="intro",None
        elif section.label=="ending" and index==len(analysis.sections)-1: element,variation="ending",None
        else:
            element="variation"; variation=1+min(3,int(energy*4))
            if section.label=="chorus": variation=max(3,variation)
            elif section.label=="verse": variation=min(3,variation)
        transition=None
        if index<len(analysis.sections)-1:
            next_section=analysis.sections[index+1]; next_energy=raw[index+1][0]; delta=next_energy-energy
            if next_section.label=="ending": transition=None  # Ending is the next primary element, never duplicated.
            elif next_section.label=="bridge" or delta<-.24: transition="break"
            elif next_section.label=="chorus" or delta>.12: transition="fill"
        confidence=min(1.0,.45+.30*section.confidence+.15*abs(energy-.5)*2+.10*(high>low))
        evidence=(("relative_density",density_norm),("drum_intensity",drum_norm),("velocity_context",velocity_norm),("section_prior",prior))
        output.append(SectionEnergy(index,section.start_tick,section.end_tick,section.label,round(energy,6),variation,element,transition,round(confidence,6),tuple((name,round(value,6)) for name,value in evidence)))
    energies=[item.energy for item in output]
    return EnergyPlan(tuple(output),min(energies),max(energies))
