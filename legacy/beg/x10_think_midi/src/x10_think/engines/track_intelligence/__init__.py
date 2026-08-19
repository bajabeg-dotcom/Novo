"""
Track Intelligence Engine Module

Automatically classifies tracks into musical roles based on:
- Instrument program numbers
- Note range analysis
- Rhythmic patterns
- MIDI channel usage
- Track names
- Control change patterns
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from x10_think.engines.parser import MidiFileData, MidiTrackData

logger = logging.getLogger(__name__)


class TrackRole(Enum):
    """Enumeration of possible track roles."""
    MELODY = "melody"
    SOLO = "solo"
    BASS = "bass"
    DRUM = "drum"
    PAD = "pad"
    STRINGS = "strings"
    BRASS = "brass"
    PIANO = "piano"
    GUITAR = "guitar"
    ORGAN = "organ"
    ACCORDION = "accordion"
    CHOIR = "choir"
    SYNTH = "synth"
    FX = "fx"
    PERCUSSION = "percussion"
    COUNTER_MELODY = "counter_melody"
    RHYTHM_GUITAR = "rhythm_guitar"
    FINGERPICKING = "fingerpicking"
    ARPEGGIO = "arpeggio"
    UNKNOWN = "unknown"


@dataclass
class TrackClassification:
    """Classification result for a track."""
    track_index: int
    role: TrackRole
    confidence: float  # 0.0 to 1.0
    reasoning: List[str] = field(default_factory=list)
    instrument_name: str = ""
    pitch_range: tuple = (0, 127)
    average_velocity: float = 0.0
    note_density: float = 0.0  # notes per beat


class TrackIntelligenceEngine:
    """
    Intelligent track classification engine.
    
    Analyzes MIDI tracks using deterministic rules to classify them
    into musical roles. Uses multiple heuristics including:
    - GM program number mapping
    - Pitch range analysis
    - Rhythmic pattern detection
    - Note density calculation
    - Track name keyword matching
    
    Example:
        >>> engine = TrackIntelligenceEngine()
        >>> classifications = engine.classify(midi_data)
        >>> for c in classifications:
        ...     print(f"Track {c.track_index}: {c.role}")
    """
    
    # GM Program number to instrument category mapping
    GM_PROGRAM_CATEGORIES = {
        # Piano family (0-7)
        0: TrackRole.PIANO, 1: TrackRole.PIANO, 2: TrackRole.PIANO, 3: TrackRole.PIANO,
        4: TrackRole.PIANO, 5: TrackRole.PIANO, 6: TrackRole.PIANO, 7: TrackRole.PIANO,
        
        # Chromatic percussion (8-15)
        8: TrackRole.FX, 9: TrackRole.FX, 10: TrackRole.FX, 11: TrackRole.FX,
        
        # Organ (16-23)
        16: TrackRole.ORGAN, 17: TrackRole.ORGAN, 18: TrackRole.ORGAN, 19: TrackRole.ORGAN,
        20: TrackRole.ORGAN, 21: TrackRole.ORGAN, 22: TrackRole.ORGAN, 23: TrackRole.ORGAN,
        
        # Guitar (24-31)
        24: TrackRole.GUITAR, 25: TrackRole.GUITAR, 26: TrackRole.GUITAR, 27: TrackRole.GUITAR,
        28: TrackRole.GUITAR, 29: TrackRole.GUITAR, 30: TrackRole.GUITAR, 31: TrackRole.GUITAR,
        
        # Bass (32-39)
        32: TrackRole.BASS, 33: TrackRole.BASS, 34: TrackRole.BASS, 35: TrackRole.BASS,
        36: TrackRole.BASS, 37: TrackRole.BASS, 38: TrackRole.BASS, 39: TrackRole.BASS,
        
        # Strings (40-47)
        40: TrackRole.STRINGS, 41: TrackRole.STRINGS, 42: TrackRole.STRINGS, 43: TrackRole.STRINGS,
        44: TrackRole.STRINGS, 45: TrackRole.STRINGS, 46: TrackRole.STRINGS, 47: TrackRole.STRINGS,
        
        # Ensemble (48-55)
        48: TrackRole.STRINGS, 49: TrackRole.STRINGS, 50: TrackRole.BRASS, 51: TrackRole.BRASS,
        52: TrackRole.BRASS, 53: TrackRole.BRASS, 54: TrackRole.CHOIR, 55: TrackRole.CHOIR,
        
        # Brass (56-63)
        56: TrackRole.BRASS, 57: TrackRole.BRASS, 58: TrackRole.BRASS, 59: TrackRole.BRASS,
        60: TrackRole.BRASS, 61: TrackRole.BRASS, 62: TrackRole.BRASS, 63: TrackRole.BRASS,
        
        # Reed (64-71)
        64: TrackRole.FX, 65: TrackRole.FX, 66: TrackRole.FX, 67: TrackRole.FX,
        68: TrackRole.FX, 69: TrackRole.FX, 70: TrackRole.FX, 71: TrackRole.FX,
        
        # Pipe (72-79)
        72: TrackRole.FX, 73: TrackRole.FX, 74: TrackRole.FX, 75: TrackRole.FX,
        76: TrackRole.FX, 77: TrackRole.FX, 78: TrackRole.FX, 79: TrackRole.FX,
        
        # Synth lead (80-87)
        80: TrackRole.SYNTH, 81: TrackRole.SYNTH, 82: TrackRole.SYNTH, 83: TrackRole.SYNTH,
        84: TrackRole.SYNTH, 85: TrackRole.SYNTH, 86: TrackRole.SYNTH, 87: TrackRole.SYNTH,
        
        # Synth pad (88-95)
        88: TrackRole.PAD, 89: TrackRole.PAD, 90: TrackRole.PAD, 91: TrackRole.PAD,
        92: TrackRole.PAD, 93: TrackRole.PAD, 94: TrackRole.PAD, 95: TrackRole.PAD,
        
        # Synth effects (96-103)
        96: TrackRole.FX, 97: TrackRole.FX, 98: TrackRole.FX, 99: TrackRole.FX,
        100: TrackRole.FX, 101: TrackRole.FX, 102: TrackRole.FX, 103: TrackRole.FX,
        
        # Ethnic (104-111)
        104: TrackRole.FX, 105: TrackRole.FX, 106: TrackRole.ACCORDION, 107: TrackRole.FX,
        108: TrackRole.FX, 109: TrackRole.FX, 110: TrackRole.FX, 111: TrackRole.FX,
        
        # Percussive (112-119)
        112: TrackRole.FX, 113: TrackRole.FX, 114: TrackRole.FX, 115: TrackRole.FX,
        116: TrackRole.FX, 117: TrackRole.FX, 118: TrackRole.FX, 119: TrackRole.FX,
        
        # Sound effects (120-127)
        120: TrackRole.FX, 121: TrackRole.FX, 122: TrackRole.FX, 123: TrackRole.FX,
        124: TrackRole.FX, 125: TrackRole.FX, 126: TrackRole.FX, 127: TrackRole.FX,
    }
    
    # Track name keywords for role detection
    ROLE_KEYWORDS = {
        TrackRole.MELODY: ['melody', 'lead', 'main', 'theme'],
        TrackRole.SOLO: ['solo', 'sol'],
        TrackRole.BASS: ['bass', 'bs'],
        TrackRole.DRUM: ['drum', 'drums', 'kit', 'perc'],
        TrackRole.PAD: ['pad', 'background', 'bg'],
        TrackRole.STRINGS: ['string', 'strings', 'viol', 'cello', 'viola'],
        TrackRole.BRASS: ['brass', 'trumpet', 'trombone', 'horn', 'french horn'],
        TrackRole.PIANO: ['piano', 'pno', 'keys', 'electric piano'],
        TrackRole.GUITAR: ['guitar', 'gtr', 'acoustic guitar', 'electric guitar'],
        TrackRole.ORGAN: ['organ', 'hammond', 'church organ'],
        TrackRole.ACCORDION: ['accordion', 'accord'],
        TrackRole.CHOIR: ['choir', 'voice', 'vocal', 'ahh', 'ooh'],
        TrackRole.SYNTH: ['synth', 'synthesizer'],
        TrackRole.FX: ['fx', 'effect', 'sfx', 'sound effect'],
        TrackRole.PERCUSSION: ['percussion', 'perc', 'shaker', 'tambourine'],
        TrackRole.ARPEGGIO: ['arp', 'arpeggio', 'arpeggiator'],
    }
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the Track Intelligence Engine.
        
        Args:
            parameters: Optional configuration parameters.
        """
        self._parameters = parameters or {}
        logger.debug("TrackIntelligenceEngine initialized")
    
    def classify(self, midi_data: MidiFileData) -> List[TrackClassification]:
        """
        Classify all tracks in a MIDI file.
        
        Args:
            midi_data: Parsed MIDI file data.
            
        Returns:
            List of TrackClassification objects for each track.
        """
        logger.info(f"Classifying {len(midi_data.tracks)} tracks")
        
        classifications = []
        
        for track in midi_data.tracks:
            classification = self._classify_track(track, midi_data)
            classifications.append(classification)
            logger.debug(
                f"Track {track.track_index} '{track.name}' -> "
                f"{classification.role.value} (confidence: {classification.confidence:.2f})"
            )
        
        return classifications
    
    def _classify_track(self, track: MidiTrackData, 
                       midi_data: MidiFileData) -> TrackClassification:
        """Classify a single track using multiple heuristics."""
        reasons = []
        scores: Dict[TrackRole, float] = {}
        
        # Heuristic 1: Program number-based classification
        program_role = self._classify_by_program(track.program)
        if program_role != TrackRole.UNKNOWN:
            scores[program_role] = scores.get(program_role, 0) + 0.4
            reasons.append(f"Program {track.program} suggests {program_role.value}")
        
        # Heuristic 2: Track name keyword matching
        name_role, name_confidence = self._classify_by_name(track.name)
        if name_role != TrackRole.UNKNOWN:
            scores[name_role] = scores.get(name_role, 0) + name_confidence
            reasons.append(f"Track name contains '{name_role.value}' keyword")
        
        # Heuristic 3: Pitch range analysis
        pitch_role = self._classify_by_pitch_range(track)
        if pitch_role != TrackRole.UNKNOWN:
            scores[pitch_role] = scores.get(pitch_role, 0) + 0.2
            reasons.append(f"Pitch range suggests {pitch_role.value}")
        
        # Heuristic 4: Channel-based detection (channel 10 is drums)
        if track.channel == 9:  # MIDI channels are 0-indexed
            scores[TrackRole.DRUM] = scores.get(TrackRole.DRUM, 0) + 0.8
            reasons.append("Channel 10 (drum channel)")
        
        # Determine final classification
        if scores:
            best_role = max(scores.keys(), key=lambda k: scores[k])
            confidence = min(scores[best_role], 1.0)
        else:
            best_role = TrackRole.UNKNOWN
            confidence = 0.0
        
        # Calculate additional metrics
        pitch_range = self._calculate_pitch_range(track)
        avg_velocity = self._calculate_average_velocity(track)
        note_density = self._calculate_note_density(track, midi_data.ticks_per_beat)
        
        return TrackClassification(
            track_index=track.track_index,
            role=best_role,
            confidence=confidence,
            reasoning=reasons,
            instrument_name=self._get_instrument_name(track.program),
            pitch_range=pitch_range,
            average_velocity=avg_velocity,
            note_density=note_density
        )
    
    def _classify_by_program(self, program: int) -> TrackRole:
        """Classify track by GM program number."""
        return self.GM_PROGRAM_CATEGORIES.get(program, TrackRole.UNKNOWN)
    
    def _classify_by_name(self, name: str) -> tuple:
        """Classify track by name keywords."""
        name_lower = name.lower()
        
        for role, keywords in self.ROLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return role, 0.6
        
        return TrackRole.UNKNOWN, 0.0
    
    def _classify_by_pitch_range(self, track: MidiTrackData) -> TrackRole:
        """Classify track by pitch range analysis."""
        pitches = [note.pitch for note in track.notes]
        
        if not pitches:
            return TrackRole.UNKNOWN
        
        avg_pitch = sum(pitches) / len(pitches)
        
        # Bass range (typically below E3 = 52)
        if avg_pitch < 50:
            return TrackRole.BASS
        
        # High range could be melody or solo
        if avg_pitch > 80:
            return TrackRole.MELODY
        
        return TrackRole.UNKNOWN
    
    def _calculate_pitch_range(self, track: MidiTrackData) -> tuple:
        """Calculate the pitch range of a track."""
        if not track.notes:
            return (0, 0)
        
        pitches = [note.pitch for note in track.notes]
        return (min(pitches), max(pitches))
    
    def _calculate_average_velocity(self, track: MidiTrackData) -> float:
        """Calculate average velocity of notes in a track."""
        if not track.notes:
            return 0.0
        
        velocities = [note.velocity for note in track.notes]
        return sum(velocities) / len(velocities)
    
    def _calculate_note_density(self, track: MidiTrackData, 
                               ticks_per_beat: int) -> float:
        """Calculate note density (notes per beat)."""
        if not track.notes or track.notes[0].end_time == 0:
            return 0.0
        
        duration_beats = max(note.end_time for note in track.notes)
        if duration_beats == 0:
            return 0.0
        
        return len(track.notes) / duration_beats
    
    def _get_instrument_name(self, program: int) -> str:
        """Get instrument name from GM program number."""
        gm_instruments = [
            "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano",
            "Honky-tonk Piano", "Electric Piano 1", "Electric Piano 2", "Harpsichord",
            "Clavinet", "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba",
            "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ", "Percussive Organ",
            "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica",
            "Tango Accordion", "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)",
            "Electric Guitar (jazz)", "Electric Guitar (clean)", "Electric Guitar (muted)",
            "Overdriven Guitar", "Distortion Guitar", "Guitar harmonics", "Acoustic Bass",
            "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
            "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2", "Violin",
            "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings",
            "Orchestral Harp", "Timpani", "String Ensembles 1", "String Ensembles 2",
            "SynthStrings 1", "SynthStrings 2", "Choir Aahs", "Voice Oohs", "Synth Voice",
            "Orchestra Hit", "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
            "French Horn", "Brass Section", "SynthBrass 1", "SynthBrass 2", "Soprano Sax",
            "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon",
            "Clarinet", "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle",
            "Shakuhachi", "Whistle", "Ocarina", "Lead 1 (square)", "Lead 2 (sawtooth)",
            "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)",
            "Lead 7 (fifths)", "Lead 8 (bass + lead)", "Pad 1 (new age)", "Pad 2 (warm)",
            "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)",
            "Pad 7 (halo)", "Pad 8 (sweep)", "FX 1 (rain)", "FX 2 (soundtrack)",
            "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)", "FX 6 (goblins)",
            "FX 7 (echoes)", "FX 8 (sci-fi)", "Sitar", "Banjo", "Shamisen", "Koto",
            "Kalimba", "Bag pipe", "Fiddle", "Shanai", "Tinkle Bell", "Agogo",
            "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom", "Synth Drum",
            "Reverse Cymbal", "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
            "Telephone Ring", "Helicopter", "Applause", "Gunshot"
        ]
        
        if 0 <= program < len(gm_instruments):
            return gm_instruments[program]
        return "Unknown"
    
    def shutdown(self) -> None:
        """Shutdown the engine."""
        logger.debug("TrackIntelligenceEngine shutdown")
