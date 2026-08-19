"""
Music Theory Utilities Module

Common music theory calculations and helpers.
"""

from typing import List, Dict, Optional, Set
import logging

logger = logging.getLogger(__name__)


class MusicTheory:
    """
    Utility class for music theory calculations.
    
    Provides static helper methods for scale, chord, and
    harmonic analysis operations.
    """
    
    # Note names
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    FLAT_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    
    # Scale interval patterns (in semitones)
    SCALE_PATTERNS = {
        'major': [0, 2, 4, 5, 7, 9, 11],
        'natural_minor': [0, 2, 3, 5, 7, 8, 10],
        'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
        'melodic_minor': [0, 2, 3, 5, 7, 9, 11],
        'dorian': [0, 2, 3, 5, 7, 9, 10],
        'phrygian': [0, 1, 3, 5, 7, 8, 10],
        'lydian': [0, 2, 4, 6, 7, 9, 11],
        'mixolydian': [0, 2, 4, 5, 7, 9, 10],
        'locrian': [0, 1, 3, 5, 6, 8, 10],
        'whole_tone': [0, 2, 4, 6, 8, 10],
        'diminished': [0, 1, 3, 4, 6, 7, 9, 10],
        'chromatic': list(range(12)),
    }
    
    # Chord construction patterns
    CHORD_PATTERNS = {
        'major': [0, 4, 7],
        'minor': [0, 3, 7],
        'diminished': [0, 3, 6],
        'augmented': [0, 4, 8],
        'sus2': [0, 2, 7],
        'sus4': [0, 5, 7],
        'major6': [0, 4, 7, 9],
        'minor6': [0, 3, 7, 9],
        'major7': [0, 4, 7, 11],
        'minor7': [0, 3, 7, 10],
        'dominant7': [0, 4, 7, 10],
        'half_diminished7': [0, 3, 6, 10],
        'fully_diminished7': [0, 3, 6, 9],
        'augmented7': [0, 4, 8, 10],
        'major9': [0, 4, 7, 11, 14],
        'minor9': [0, 3, 7, 10, 14],
        'dominant9': [0, 4, 7, 10, 14],
        'add9': [0, 4, 7, 14],
        'power': [0, 7],
    }
    
    @staticmethod
    def get_scale_notes(root: int, scale_type: str = 'major') -> List[int]:
        """
        Get the pitch classes in a scale.
        
        Args:
            root: Root pitch class (0-11).
            scale_type: Type of scale.
            
        Returns:
            List of pitch classes in the scale.
        """
        pattern = MusicTheory.SCALE_PATTERNS.get(scale_type, 
                        MusicTheory.SCALE_PATTERNS['major'])
        return [(root + interval) % 12 for interval in pattern]
    
    @staticmethod
    def get_chord_notes(root: int, chord_type: str = 'major') -> List[int]:
        """
        Get the pitch classes in a chord.
        
        Args:
            root: Root pitch class (0-11).
            chord_type: Type of chord.
            
        Returns:
            List of pitch classes in the chord.
        """
        pattern = MusicTheory.CHORD_PATTERNS.get(chord_type,
                        MusicTheory.CHORD_PATTERNS['major'])
        return [(root + interval) % 12 for interval in pattern]
    
    @staticmethod
    def is_diatonic(pitch_class: int, key_root: int, 
                   key_type: str = 'major') -> bool:
        """
        Check if a pitch class is diatonic to a key.
        
        Args:
            pitch_class: Pitch class to check (0-11).
            key_root: Root of the key.
            key_type: Type of key (major/minor).
            
        Returns:
            True if the pitch is diatonic to the key.
        """
        scale_type = 'major' if key_type == 'major' else 'natural_minor'
        scale_notes = MusicTheory.get_scale_notes(key_root, scale_type)
        return pitch_class in scale_notes
    
    @staticmethod
    def get_scale_degree(pitch_class: int, key_root: int,
                        key_type: str = 'major') -> Optional[int]:
        """
        Get the scale degree of a pitch class in a key.
        
        Args:
            pitch_class: Pitch class to analyze.
            key_root: Root of the key.
            key_type: Type of key.
            
        Returns:
            Scale degree (1-7) or None if not in key.
        """
        scale_type = 'major' if key_type == 'major' else 'natural_minor'
        scale_notes = MusicTheory.get_scale_notes(key_root, scale_type)
        
        try:
            return scale_notes.index(pitch_class) + 1
        except ValueError:
            return None
    
    @staticmethod
    def get_interval(semitones: int) -> str:
        """
        Get the name of an interval.
        
        Args:
            semitones: Number of semitones.
            
        Returns:
            Interval name.
        """
        intervals = {
            0: 'Perfect Unison',
            1: 'Minor Second',
            2: 'Major Second',
            3: 'Minor Third',
            4: 'Major Third',
            5: 'Perfect Fourth',
            6: 'Tritone',
            7: 'Perfect Fifth',
            8: 'Minor Sixth',
            9: 'Major Sixth',
            10: 'Minor Seventh',
            11: 'Major Seventh',
            12: 'Perfect Octave',
        }
        return intervals.get(semitones % 12, 'Unknown')
    
    @staticmethod
    def get_relative_major(minor_root: int) -> int:
        """Get the relative major key root from a minor key."""
        return (minor_root + 3) % 12
    
    @staticmethod
    def get_relative_minor(major_root: int) -> int:
        """Get the relative minor key root from a major key."""
        return (major_root - 3) % 12
    
    @staticmethod
    def get_circle_of_fifths_position(root: int) -> int:
        """
        Get the position of a key on the circle of fifths.
        
        Args:
            root: Root pitch class.
            
        Returns:
            Position on circle of fifths (-7 to 7).
        """
        fifth_positions = {
            0: 0,   # C
            7: 1,   # G
            2: 2,   # D
            9: 3,   # A
            4: 4,   # E
            11: 5,  # B
            6: 6,   # F#
            1: 7,   # C#
            5: -1,  # F
            10: -2, # Bb
            3: -3,  # Eb
            8: -4,  # Ab
            1: -5,  # Db
            6: -6,  # Gb
            11: -7, # Cb
        }
        return fifth_positions.get(root, 0)
    
    @staticmethod
    def analyze_pitch_class_set(pcs: Set[int]) -> Dict[str, any]:
        """
        Analyze a set of pitch classes.
        
        Args:
            pcs: Set of pitch classes.
            
        Returns:
            Analysis results including possible scales/chords.
        """
        result = {
            'pitch_classes': sorted(pcs),
            'cardinality': len(pcs),
            'possible_scales': [],
            'possible_chords': [],
            'interval_vector': MusicTheory._calculate_interval_vector(pcs)
        }
        
        # Find matching scales
        for scale_name in MusicTheory.SCALE_PATTERNS:
            for root in range(12):
                scale_pcs = set(MusicTheory.get_scale_notes(root, scale_name))
                if pcs.issubset(scale_pcs):
                    result['possible_scales'].append({
                        'root': root,
                        'type': scale_name
                    })
        
        # Find matching chords
        for chord_name in MusicTheory.CHORD_PATTERNS:
            for root in range(12):
                chord_pcs = set(MusicTheory.get_chord_notes(root, chord_name))
                if pcs == chord_pcs:
                    result['possible_chords'].append({
                        'root': root,
                        'type': chord_name
                    })
        
        return result
    
    @staticmethod
    def _calculate_interval_vector(pcs: Set[int]) -> List[int]:
        """
        Calculate the interval vector for a pitch class set.
        
        The interval vector shows how many of each interval class
        (1 through 6) are present in the set.
        """
        vector = [0] * 6
        pcs_list = sorted(pcs)
        
        for i in range(len(pcs_list)):
            for j in range(i + 1, len(pcs_list)):
                interval = min(
                    pcs_list[j] - pcs_list[i],
                    12 - (pcs_list[j] - pcs_list[i])
                )
                if 1 <= interval <= 6:
                    vector[interval - 1] += 1
        
        return vector
    
    @staticmethod
    def pitch_class_to_note_name(pc: int, use_flats: bool = False) -> str:
        """Convert pitch class to note name."""
        names = MusicTheory.FLAT_NAMES if use_flats else MusicTheory.NOTE_NAMES
        return names[pc]
    
    @staticmethod
    def note_name_to_pitch_class(note_name: str) -> int:
        """Convert note name to pitch class."""
        name = note_name.upper()
        if name in MusicTheory.NOTE_NAMES:
            return MusicTheory.NOTE_NAMES.index(name)
        if name in MusicTheory.FLAT_NAMES:
            return MusicTheory.FLAT_NAMES.index(name)
        return 0
