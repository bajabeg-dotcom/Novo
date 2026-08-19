"""
Engines Package Initialization

This package contains all the processing engines for the X10 Think system:
- Parser Engine: MIDI file parsing and export
- Track Intelligence Engine: Track classification
- RX Engine: Articulation rules
- Humanization Engine: Performance humanization
- Harmony Engine: Harmonic analysis
- Expression Engine: Controller automation
- Velocity Engine: Velocity shaping
- Musical Rules Engine: Rule validation
"""

from .parser import MIDIParserEngine
from .track_intelligence import TrackIntelligenceEngine
from .rx import RXEngine
from .humanization import HumanizationEngine
from .harmony import HarmonyEngine
from .expression import ExpressionEngine
from .velocity import VelocityEngine
from .musical_rules import MusicalRulesEngine

__all__ = [
    "MIDIParserEngine",
    "TrackIntelligenceEngine",
    "RXEngine",
    "HumanizationEngine",
    "HarmonyEngine",
    "ExpressionEngine",
    "VelocityEngine",
    "MusicalRulesEngine"
]
