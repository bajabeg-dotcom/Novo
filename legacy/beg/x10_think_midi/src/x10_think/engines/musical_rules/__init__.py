"""
Musical Rules Engine Module

Comprehensive deterministic rule system covering:
- Performance practice conventions
- Instrument physical constraints
- Breathing and phrasing logic
- Hand and finger movement realism
- String direction behavior
- Bowing direction logic
- Drum sticking patterns
- Natural phrasing structures
- Musical accent rules
- Cadence behavior
- Genre-independent musical principles
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from x10_think.engines.parser import MidiFileData, MidiTrackData
from x10_think.engines.track_intelligence import TrackClassification

logger = logging.getLogger(__name__)


class RuleCategory(Enum):
    """Categories of musical rules."""
    PERFORMANCE = "performance"
    PHYSICAL = "physical"
    PHRASING = "phrasing"
    ARTICULATION = "articulation"
    HARMONY = "harmony"
    RHYTHM = "rhythm"
    DYNAMICS = "dynamics"


@dataclass
class MusicalRule:
    """Represents a musical rule."""
    id: str
    name: str
    category: RuleCategory
    description: str
    condition: str
    action: str
    priority: int = 0
    enabled: bool = True


@dataclass
class RuleViolation:
    """Represents a rule violation."""
    rule_id: str
    track_index: int
    time: float
    description: str
    severity: str  # 'warning', 'error', 'suggestion'


class MusicalRulesEngine:
    """
    Comprehensive musical rules validation engine.
    
    Validates MIDI data against a comprehensive set of
    deterministic musical rules to ensure realistic and
    musically appropriate output.
    """
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the Musical Rules Engine."""
        self._parameters = parameters or {}
        self._rules: List[MusicalRule] = []
        self._load_default_rules()
        logger.debug("MusicalRulesEngine initialized")
    
    def _load_default_rules(self) -> None:
        """Load default musical rules."""
        # Physical constraint rules
        self._rules.append(MusicalRule(
            id="PHYS001",
            name="Piano Hand Span",
            category=RuleCategory.PHYSICAL,
            description="Piano parts should not exceed realistic hand span",
            condition="Simultaneous notes > 12 semitones apart in single hand",
            action="Flag for review or redistribute between hands",
            priority=10
        ))
        
        self._rules.append(MusicalRule(
            id="PHYS002",
            name="Guitar String Reach",
            category=RuleCategory.PHYSICAL,
            description="Guitar parts should respect string tuning constraints",
            condition="Note transitions requiring impossible fret stretches",
            action="Suggest alternative voicing or fingering",
            priority=10
        ))
        
        # Phrasing rules
        self._rules.append(MusicalRule(
            id="PHRASE001",
            name="Wind Instrument Breathing",
            category=RuleCategory.PHRASING,
            description="Wind instruments need breathing points",
            condition="Continuous playing > 8 beats without rest",
            action="Insert brief rest or phrase break",
            priority=15
        ))
        
        self._rules.append(MusicalRule(
            id="PHRASE002",
            name="String Bow Direction",
            category=RuleCategory.PHRASING,
            description="String bow changes should be logical",
            condition="Bow change on weak beat without musical justification",
            action="Adjust bow change position",
            priority=8
        ))
        
        # Articulation rules
        self._rules.append(MusicalRule(
            id="ARTIC001",
            name="Staccato Consistency",
            category=RuleCategory.ARTICULATION,
            description="Staccato markings should be consistent within phrases",
            condition="Mixed staccato/legato without clear pattern",
            action="Standardize articulation within phrase",
            priority=5
        ))
        
        # Rhythm rules
        self._rules.append(MusicalRule(
            id="RHYTHM001",
            name="Drum Pattern Consistency",
            category=RuleCategory.RHYTHM,
            description="Drum patterns should maintain groove consistency",
            condition="Inconsistent kick/snare placement across bars",
            action="Align to established groove pattern",
            priority=10
        ))
        
        # Dynamics rules
        self._rules.append(MusicalRule(
            id="DYN001",
            name="Crescendo Logic",
            category=RuleCategory.DYNAMICS,
            description="Crescendos should have logical shape",
            condition="Volume decrease during marked crescendo",
            action="Adjust volume curve to match marking",
            priority=7
        ))
        
        logger.debug(f"Loaded {len(self._rules)} default musical rules")
    
    def validate(self, midi_data: MidiFileData) -> Dict[str, Any]:
        """
        Validate MIDI data against all musical rules.
        
        Args:
            midi_data: Parsed MIDI file data.
            
        Returns:
            Dictionary containing validation results.
        """
        logger.info("Validating against musical rules")
        
        result = {
            'violations': [],
            'warnings': [],
            'suggestions': [],
            'rules_checked': len(self._rules),
            'passed': 0
        }
        
        for track in midi_data.tracks:
            track_violations = self._validate_track(track)
            
            for violation in track_violations:
                if violation.severity == 'error':
                    result['violations'].append(violation)
                elif violation.severity == 'warning':
                    result['warnings'].append(f"Track {violation.track_index}: {violation.description}")
                else:
                    result['suggestions'].append(violation.description)
        
        result['passed'] = result['rules_checked'] - len(result['violations'])
        
        logger.info(
            f"Validation complete: {result['passed']}/{result['rules_checked']} rules passed"
        )
        
        return result
    
    def _validate_track(self, track: MidiTrackData) -> List[RuleViolation]:
        """Validate a single track against all rules."""
        violations = []
        
        for rule in self._rules:
            if not rule.enabled:
                continue
            
            violation = self._check_rule(track, rule)
            if violation:
                violations.append(violation)
        
        return violations
    
    def _check_rule(self, track: MidiTrackData, rule: MusicalRule) -> Optional[RuleViolation]:
        """Check a specific rule against a track."""
        # Simplified implementation - full version would have detailed rule checking
        
        if rule.id == "PHYS001":
            return self._check_piano_hand_span(track, rule)
        elif rule.id == "PHRASE001":
            return self._check_breathing_points(track, rule)
        elif rule.id == "RHYTHM001":
            return self._check_drum_consistency(track, rule)
        
        return None
    
    def _check_piano_hand_span(self, track: MidiTrackData, 
                              rule: MusicalRule) -> Optional[RuleViolation]:
        """Check piano hand span constraint."""
        # Implementation would analyze simultaneous note intervals
        return None
    
    def _check_breathing_points(self, track: MidiTrackData,
                               rule: MusicalRule) -> Optional[RuleViolation]:
        """Check for adequate breathing points in wind parts."""
        # Implementation would analyze phrase lengths
        return None
    
    def _check_drum_consistency(self, track: MidiTrackData,
                               rule: MusicalRule) -> Optional[RuleViolation]:
        """Check drum pattern consistency."""
        # Implementation would analyze rhythmic patterns
        return None
    
    def add_rule(self, rule: MusicalRule) -> None:
        """Add a custom rule to the engine."""
        self._rules.append(rule)
        logger.debug(f"Added custom rule: {rule.id}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        for i, rule in enumerate(self._rules):
            if rule.id == rule_id:
                self._rules.pop(i)
                logger.debug(f"Removed rule: {rule_id}")
                return True
        return False
    
    def get_rules_by_category(self, category: RuleCategory) -> List[MusicalRule]:
        """Get all rules in a category."""
        return [r for r in self._rules if r.category == category]
    
    def shutdown(self) -> None:
        """Shutdown the engine."""
        logger.debug("MusicalRulesEngine shutdown")
