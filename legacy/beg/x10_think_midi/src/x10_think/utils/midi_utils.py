"""
MIDI Utilities Module

Common MIDI utility functions used throughout the application.
"""

from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class MidiUtils:
    """
    Utility class for common MIDI operations.
    
    Provides static helper methods for MIDI-related calculations
    and conversions.
    """
    
    @staticmethod
    def ticks_to_seconds(ticks: int, ticks_per_beat: int, tempo_bpm: float) -> float:
        """
        Convert MIDI ticks to seconds.
        
        Args:
            ticks: Number of ticks.
            ticks_per_beat: Ticks per quarter note.
            tempo_bpm: Tempo in beats per minute.
            
        Returns:
            Time in seconds.
        """
        beats = ticks / ticks_per_beat
        seconds_per_beat = 60.0 / tempo_bpm
        return beats * seconds_per_beat
    
    @staticmethod
    def seconds_to_ticks(seconds: float, ticks_per_beat: int, 
                        tempo_bpm: float) -> int:
        """
        Convert seconds to MIDI ticks.
        
        Args:
            seconds: Time in seconds.
            ticks_per_beat: Ticks per quarter note.
            tempo_bpm: Tempo in beats per minute.
            
        Returns:
            Number of ticks.
        """
        seconds_per_beat = 60.0 / tempo_bpm
        beats = seconds / seconds_per_beat
        return int(beats * ticks_per_beat)
    
    @staticmethod
    def midi_pitch_to_frequency(pitch: int) -> float:
        """
        Convert MIDI pitch number to frequency in Hz.
        
        Args:
            pitch: MIDI pitch number (0-127).
            
        Returns:
            Frequency in Hz.
        """
        return 440.0 * (2 ** ((pitch - 69) / 12))
    
    @staticmethod
    def frequency_to_midi_pitch(frequency: float) -> int:
        """
        Convert frequency in Hz to nearest MIDI pitch number.
        
        Args:
            frequency: Frequency in Hz.
            
        Returns:
            MIDI pitch number.
        """
        if frequency <= 0:
            return 0
        return round(69 + 12 * (log2(frequency / 440.0)))
    
    @staticmethod
    def midi_pitch_to_note_name(pitch: int) -> str:
        """
        Convert MIDI pitch number to note name with octave.
        
        Args:
            pitch: MIDI pitch number.
            
        Returns:
            Note name (e.g., "C4", "A#3").
        """
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        note = pitch % 12
        octave = (pitch // 12) - 1
        return f"{note_names[note]}{octave}"
    
    @staticmethod
    def note_name_to_midi_pitch(note_name: str) -> Optional[int]:
        """
        Convert note name to MIDI pitch number.
        
        Args:
            note_name: Note name (e.g., "C4", "A#3", "Bb3").
            
        Returns:
            MIDI pitch number or None if invalid.
        """
        import re
        match = re.match(r'^([A-Ga-g])([#b]?)(-?\d+)$', note_name)
        if not match:
            return None
        
        note_letter = match.group(1).upper()
        accidental = match.group(2)
        octave = int(match.group(3))
        
        note_offsets = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        pitch = note_offsets[note_letter] + (octave + 1) * 12
        
        if accidental == '#':
            pitch += 1
        elif accidental == 'b':
            pitch -= 1
        
        return max(0, min(127, pitch))
    
    @staticmethod
    def calculate_note_duration(start_tick: int, end_tick: int, 
                               ticks_per_beat: int) -> float:
        """
        Calculate note duration in beats.
        
        Args:
            start_tick: Start position in ticks.
            end_tick: End position in ticks.
            ticks_per_beat: Ticks per quarter note.
            
        Returns:
            Duration in beats.
        """
        return (end_tick - start_tick) / ticks_per_beat
    
    @staticmethod
    def is_valid_midi_pitch(pitch: int) -> bool:
        """Check if a pitch value is within valid MIDI range."""
        return 0 <= pitch <= 127
    
    @staticmethod
    def is_valid_midi_velocity(velocity: int) -> bool:
        """Check if a velocity value is within valid MIDI range."""
        return 0 <= velocity <= 127
    
    @staticmethod
    def clamp_midi_value(value: int, min_val: int = 0, 
                        max_val: int = 127) -> int:
        """Clamp a value to valid MIDI range."""
        return max(min_val, min(max_val, value))
    
    @staticmethod
    def get_chord_pitches(root: int, quality: str) -> List[int]:
        """
        Get MIDI pitches for a chord.
        
        Args:
            root: Root pitch number.
            quality: Chord quality ('major', 'minor', 'dim', 'aug', etc.).
            
        Returns:
            List of pitch numbers in the chord.
        """
        intervals = {
            'major': [0, 4, 7],
            'minor': [0, 3, 7],
            'dim': [0, 3, 6],
            'aug': [0, 4, 8],
            'sus4': [0, 5, 7],
            'sus2': [0, 2, 7],
            'major7': [0, 4, 7, 11],
            'minor7': [0, 3, 7, 10],
            'dominant7': [0, 4, 7, 10],
        }
        
        chord_intervals = intervals.get(quality.lower(), [0, 4, 7])
        return [root + interval for interval in chord_intervals]


# Import log2 for frequency conversion
from math import log2
