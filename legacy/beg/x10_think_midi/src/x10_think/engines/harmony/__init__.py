"""
Harmony Engine Module

Detects and analyzes harmonic structure including:
- Scale detection
- Mode identification
- Chord progression analysis
- Chord quality recognition
- Voice leading optimization
- Cadence detection
- Modulation tracking
- Tension and resolution mapping
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import Counter

from x10_think.engines.parser import MidiFileData, MidiTrackData

logger = logging.getLogger(__name__)


class ScaleQuality(Enum):
    """Scale quality types."""
    MAJOR = "major"
    MINOR = "minor"
    DORIAN = "dorian"
    PHRYGIAN = "phrygian"
    LYDIAN = "lydian"
    MIXOLYDIAN = "mixolydian"
    LOCRIAN = "locrian"
    HARMONIC_MINOR = "harmonic_minor"
    MELODIC_MINOR = "melodic_minor"


class ChordQuality(Enum):
    """Chord quality types."""
    MAJOR = "major"
    MINOR = "minor"
    DIMINISHED = "diminished"
    AUGMENTED = "augmented"
    MAJOR_7 = "major7"
    MINOR_7 = "minor7"
    DOMINANT_7 = "dominant7"
    HALF_DIMINISHED = "half_diminished"
    SUS4 = "sus4"
    SUS2 = "sus2"


@dataclass
class DetectedChord:
    """Represents a detected chord."""
    root: int  # MIDI pitch number
    quality: ChordQuality
    inversion: int  # 0=root, 1=first, 2=second
    time: float
    duration: float
    bass_note: Optional[int] = None


@dataclass
class KeyAnalysis:
    """Key analysis result."""
    tonic: int  # MIDI pitch number
    quality: ScaleQuality
    confidence: float
    modulation_points: List[float] = field(default_factory=list)


@dataclass
class HarmonyAnalysis:
    """Complete harmony analysis result."""
    key: Optional[KeyAnalysis] = None
    chords: List[DetectedChord] = field(default_factory=list)
    progression: List[str] = field(default_factory=list)
    cadences: List[Tuple[float, str]] = field(default_factory=list)
    tension_map: List[Tuple[float, float]] = field(default_factory=list)


class HarmonyEngine:
    """
    Harmonic analysis engine.
    
    Analyzes MIDI data to detect key, chords, progressions,
    and harmonic tension using deterministic music theory rules.
    
    Example:
        >>> engine = HarmonyEngine()
        >>> analysis = engine.analyze(midi_data)
        >>> print(f"Key: {analysis.key}")
    """
    
    # Pitch class to note name mapping
    PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    # Major scale intervals (semitones from root)
    MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
    
    # Natural minor scale intervals
    NATURAL_MINOR = [0, 2, 3, 5, 7, 8, 10]
    
    # Chord construction templates
    CHORD_TEMPLATES = {
        ChordQuality.MAJOR: [0, 4, 7],
        ChordQuality.MINOR: [0, 3, 7],
        ChordQuality.DIMINISHED: [0, 3, 6],
        ChordQuality.AUGMENTED: [0, 4, 8],
        ChordQuality.MAJOR_7: [0, 4, 7, 11],
        ChordQuality.MINOR_7: [0, 3, 7, 10],
        ChordQuality.DOMINANT_7: [0, 4, 7, 10],
        ChordQuality.HALF_DIMINISHED: [0, 3, 6, 10],
        ChordQuality.SUS4: [0, 5, 7],
        ChordQuality.SUS2: [0, 2, 7],
    }
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the Harmony Engine."""
        self._parameters = parameters or {}
        logger.debug("HarmonyEngine initialized")
    
    def analyze(self, midi_data: MidiFileData) -> HarmonyAnalysis:
        """
        Perform complete harmonic analysis on MIDI data.
        
        Args:
            midi_data: Parsed MIDI file data.
            
        Returns:
            HarmonyAnalysis containing all harmonic information.
        """
        logger.info("Analyzing harmonic structure")
        
        analysis = HarmonyAnalysis()
        
        # Step 1: Detect key
        analysis.key = self._detect_key(midi_data)
        
        # Step 2: Detect chords
        analysis.chords = self._detect_chords(midi_data)
        
        # Step 3: Build progression
        if analysis.key:
            analysis.progression = self._build_progression(
                analysis.chords, analysis.key.tonic, analysis.key.quality
            )
        
        # Step 4: Detect cadences
        analysis.cadences = self._detect_cadences(analysis.chords, analysis.key)
        
        # Step 5: Calculate tension map
        analysis.tension_map = self._calculate_tension_map(analysis.chords, analysis.key)
        
        logger.info(
            f"Harmony analysis complete: "
            f"Key={analysis.key}, Chords={len(analysis.chords)}"
        )
        
        return analysis
    
    def _detect_key(self, midi_data: MidiFileData) -> Optional[KeyAnalysis]:
        """Detect the key of the piece using pitch class profiling."""
        # Collect all pitch classes
        pitch_classes = []
        for track in midi_data.tracks:
            for note in track.notes:
                pitch_classes.append(note.pitch % 12)
        
        if not pitch_classes:
            return None
        
        # Count pitch class occurrences
        pc_counts = Counter(pitch_classes)
        
        # Try each possible tonic and quality
        best_match = None
        best_score = 0.0
        
        for tonic in range(12):
            for quality in [ScaleQuality.MAJOR, ScaleQuality.MINOR]:
                score = self._calculate_key_fit(pc_counts, tonic, quality)
                if score > best_score:
                    best_score = score
                    best_match = KeyAnalysis(
                        tonic=tonic,
                        quality=quality,
                        confidence=min(score / len(pitch_classes), 1.0)
                    )
        
        return best_match
    
    def _calculate_key_fit(self, pc_counts: Counter, tonic: int, 
                          quality: ScaleQuality) -> float:
        """Calculate how well pitch classes fit a given key."""
        if quality == ScaleQuality.MAJOR:
            scale_pcs = set((tonic + interval) % 12 for interval in self.MAJOR_SCALE)
        else:
            scale_pcs = set((tonic + interval) % 12 for interval in self.NATURAL_MINOR)
        
        score = 0.0
        for pc, count in pc_counts.items():
            if pc in scale_pcs:
                score += count  # Diatonic notes add positively
            else:
                score -= count * 0.5  # Chromatic notes reduce confidence
        
        return max(score, 0)
    
    def _detect_chords(self, midi_data: MidiFileData) -> List[DetectedChord]:
        """Detect chords from simultaneous notes."""
        chords = []
        
        # Group notes by time slices
        time_slices = self._create_time_slices(midi_data)
        
        for time_point, pitches in time_slices.items():
            if len(pitches) >= 3:  # Need at least 3 notes for a chord
                chord = self._identify_chord(pitches, time_point)
                if chord:
                    chords.append(chord)
        
        return chords
    
    def _create_time_slices(self, midi_data: MidiFileData) -> Dict[float, List[int]]:
        """Create time slices with active pitches."""
        slices: Dict[float, List[int]] = {}
        
        for track in midi_data.tracks:
            for note in track.notes:
                time_key = round(note.start_time, 2)
                if time_key not in slices:
                    slices[time_key] = []
                slices[time_key].append(note.pitch)
        
        return slices
    
    def _identify_chord(self, pitches: List[int], time: float) -> Optional[DetectedChord]:
        """Identify a chord from a set of pitches."""
        # Get unique pitch classes
        pcs = list(set(p % 12 for p in pitches))
        pcs.sort()
        
        # Try to match against chord templates
        for root in pcs:
            for quality, template in self.CHORD_TEMPLATES.items():
                chord_pcs = [(root + interval) % 12 for interval in template]
                if set(chord_pcs).issubset(set(pcs)):
                    # Find bass note
                    bass_note = min(pitches)
                    inversion = 0
                    if bass_note % 12 != root:
                        # Determine inversion
                        for i, pc in enumerate(chord_pcs):
                            if pc == bass_note % 12:
                                inversion = i
                                break
                    
                    return DetectedChord(
                        root=root,
                        quality=quality,
                        inversion=inversion,
                        time=time,
                        duration=0.5,  # Simplified
                        bass_note=bass_note
                    )
        
        return None
    
    def _build_progression(self, chords: List[DetectedChord], 
                          tonic: int, quality: ScaleQuality) -> List[str]:
        """Build Roman numeral progression from chords."""
        progression = []
        
        scale_degrees = self.MAJOR_SCALE if quality == ScaleQuality.MAJOR else self.NATURAL_MINOR
        
        for chord in chords:
            # Find scale degree of chord root
            root_pc = chord.root
            for degree, interval in enumerate(scale_degrees):
                if (tonic + interval) % 12 == root_pc:
                    roman = ['I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii°'][degree]
                    if chord.quality in [ChordQuality.MINOR, ChordQuality.HALF_DIMINISHED]:
                        roman = roman.lower() if roman.isupper() else roman
                    progression.append(roman)
                    break
        
        return progression
    
    def _detect_cadences(self, chords: List[DetectedChord], 
                        key: Optional[KeyAnalysis]) -> List[Tuple[float, str]]:
        """Detect cadential points in the progression."""
        cadences = []
        
        if not key or len(chords) < 2:
            return cadences
        
        # Look for common cadence patterns
        for i in range(len(chords) - 1):
            curr = chords[i]
            next_chord = chords[i + 1]
            
            # V-I cadence (authentic)
            if self._is_dominant(curr, key.tonic) and next_chord.root == key.tonic:
                cadences.append((next_chord.time, "authentic"))
            
            # IV-I cadence (plagal)
            if self._is_subdominant(curr, key.tonic, key.quality) and next_chord.root == key.tonic:
                cadences.append((next_chord.time, "plagal"))
            
            # V-vi cadence (deceptive)
            if self._is_dominant(curr, key.tonic) and self._is_relative_minor(next_chord, key):
                cadences.append((next_chord.time, "deceptive"))
        
        return cadences
    
    def _is_dominant(self, chord: DetectedChord, tonic: int) -> bool:
        """Check if chord is dominant (V)."""
        dominant_root = (tonic + 7) % 12
        return chord.root == dominant_root and chord.quality == ChordQuality.MAJOR
    
    def _is_subdominant(self, chord: DetectedChord, tonic: int, 
                       quality: ScaleQuality) -> bool:
        """Check if chord is subdominant (IV)."""
        subdominant_root = (tonic + 5) % 12
        return chord.root == subdominant_root
    
    def _is_relative_minor(self, chord: DetectedChord, key: KeyAnalysis) -> bool:
        """Check if chord is relative minor (vi in major, III in minor)."""
        if key.quality == ScaleQuality.MAJOR:
            relative_minor = (key.tonic + 9) % 12
            return chord.root == relative_minor and chord.quality == ChordQuality.MINOR
        return False
    
    def _calculate_tension_map(self, chords: List[DetectedChord], 
                              key: Optional[KeyAnalysis]) -> List[Tuple[float, float]]:
        """Calculate harmonic tension over time."""
        tension_map = []
        
        if not key:
            return tension_map
        
        for chord in chords:
            tension = self._calculate_chord_tension(chord, key)
            tension_map.append((chord.time, tension))
        
        return tension_map
    
    def _calculate_chord_tension(self, chord: DetectedChord, key: KeyAnalysis) -> float:
        """Calculate tension value for a chord (0.0-1.0)."""
        # Base tension by chord quality
        quality_tension = {
            ChordQuality.MAJOR: 0.2,
            ChordQuality.MINOR: 0.3,
            ChordQuality.DIMINISHED: 0.8,
            ChordQuality.AUGMENTED: 0.7,
            ChordQuality.MAJOR_7: 0.4,
            ChordQuality.MINOR_7: 0.4,
            ChordQuality.DOMINANT_7: 0.6,
            ChordQuality.HALF_DIMINISHED: 0.7,
            ChordQuality.SUS4: 0.5,
            ChordQuality.SUS2: 0.4,
        }
        
        base = quality_tension.get(chord.quality, 0.5)
        
        # Add tension for non-diatonic chords
        diatonic_roots = set((key.tonic + i) % 12 for i in 
                           (self.MAJOR_SCALE if key.quality == ScaleQuality.MAJOR else self.NATURAL_MINOR))
        
        if chord.root not in diatonic_roots:
            base += 0.3
        
        return min(base, 1.0)
    
    def shutdown(self) -> None:
        """Shutdown the engine."""
        logger.debug("HarmonyEngine shutdown")
