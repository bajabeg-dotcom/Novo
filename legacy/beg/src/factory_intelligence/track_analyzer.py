"""
KORG PA800 Factory Intelligence - Track Analyzer

Analyzes track roles and characteristics in Factory Styles.
"""

from __future__ import annotations

import logging
from typing import Any

from .config import (
    DRUM_CHANNEL,
    BASS_NOTE_THRESHOLD,
    LOW_NOTE_THRESHOLD,
    HIGH_NOTE_THRESHOLD
)
from .models import TrackRole, NoteEvent, VelocityStats


logger = logging.getLogger(__name__)


def detect_track_role(
    channels: set[int],
    notes: list[NoteEvent],
    program_changes: list[tuple[int, int]],
    track_name: str | None = None
) -> tuple[TrackRole, float, list[str]]:
    """
    Detect the role of a track based on heuristic evidence.
    
    IMPORTANT: This is HEURISTIC analysis, not definitive classification.
    Results should be marked as HEURISTIC confidence level.
    
    Args:
        channels: Set of MIDI channels used by the track
        notes: List of note events
        program_changes: List of (tick, program) tuples
        track_name: Optional track name from MIDI meta event
    
    Returns:
        Tuple of (role, confidence, evidence_list)
    """
    evidence: list[str] = []
    confidence = 0.0
    role = TrackRole.UNKNOWN
    
    # Check for drum channel (MIDI channel 10, index 9)
    if DRUM_CHANNEL in channels:
        evidence.append(f"Uses MIDI channel {DRUM_CHANNEL + 1} (standard drum channel)")
        role = TrackRole.DRUM
        confidence = 0.95
        
        # Additional drum evidence
        if track_name and any(word in track_name.lower() for word in ["drum", "perc", "kit"]):
            evidence.append(f"Track name suggests drums: '{track_name}'")
            confidence = min(confidence + 0.04, 0.99)
        
        return role, confidence, evidence
    
    # Check track name hints
    if track_name:
        name_lower = track_name.lower()
        
        if any(word in name_lower for word in ["bass", "bs"]):
            evidence.append(f"Track name suggests bass: '{track_name}'")
            role = TrackRole.BASS
            confidence = 0.75
        
        elif any(word in name_lower for word in ["guitar", "gt", "gtr"]):
            evidence.append(f"Track name suggests guitar: '{track_name}'")
            role = TrackRole.GUITAR
            confidence = 0.70
        
        elif any(word in name_lower for word in ["piano", "keys", "kbd", "ep"]):
            evidence.append(f"Track name suggests keyboard: '{track_name}'")
            role = TrackRole.KEYBOARD
            confidence = 0.70
        
        elif any(word in name_lower for word in ["string", "str"]):
            evidence.append(f"Track name suggests strings: '{track_name}'")
            role = TrackRole.STRING
            confidence = 0.70
        
        elif any(word in name_lower for word in ["brass", "br"]):
            evidence.append(f"Track name suggests brass: '{track_name}'")
            role = TrackRole.BRASS
            confidence = 0.70
        
        elif any(word in name_lower for word in ["pad", "synth"]):
            evidence.append(f"Track name suggests pad: '{track_name}'")
            role = TrackRole.PAD
            confidence = 0.65
        
        elif any(word in name_lower for word in ["wind", "flute", "sax", "trumpet"]):
            evidence.append(f"Track name suggests wind instrument: '{track_name}'")
            role = TrackRole.WIND
            confidence = 0.70
        
        elif any(word in name_lower for word in ["melody", "lead"]):
            evidence.append(f"Track name suggests melodic role: '{track_name}'")
            role = TrackRole.MELODIC
            confidence = 0.60
    
    # Analyze pitch range if we have notes
    if notes:
        pitches = [n.note for n in notes]
        min_pitch = min(pitches)
        max_pitch = max(pitches)
        mean_pitch = sum(pitches) / len(pitches)
        
        # Bass detection by pitch range
        if max_pitch <= BASS_NOTE_THRESHOLD:
            if role == TrackRole.UNKNOWN:
                role = TrackRole.BASS
                confidence = 0.60
            evidence.append(f"Low pitch range (max: {max_pitch}, MIDI note)")
        
        # Very low notes strongly suggest bass
        if min_pitch < LOW_NOTE_THRESHOLD:
            if role == TrackRole.UNKNOWN:
                role = TrackRole.BASS
                confidence = 0.55
            evidence.append(f"Very low notes present (min: {min_pitch})")
        
        # High pitch range might indicate melody or lead
        if min_pitch >= HIGH_NOTE_THRESHOLD:
            if role == TrackRole.UNKNOWN:
                role = TrackRole.MELODIC
                confidence = 0.50
            evidence.append(f"High pitch range (min: {min_pitch})")
        
        # Wide pitch range might indicate comping or full arrangement
        pitch_range = max_pitch - min_pitch
        if pitch_range > 36:  # More than 3 octaves
            evidence.append(f"Wide pitch range: {pitch_range} semitones")
    
    # Program change analysis (GM interpretation only)
    if program_changes:
        programs = [p for _, p in program_changes]
        unique_programs = set(programs)
        
        # GM program ranges (heuristic only!)
        if any(0 <= p <= 7 for p in unique_programs):
            evidence.append("Uses GM piano programs (0-7) - HEURISTIC")
            if role == TrackRole.UNKNOWN:
                role = TrackRole.KEYBOARD
                confidence = max(confidence, 0.50)
        
        if any(24 <= p <= 31 for p in unique_programs):
            evidence.append("Uses GM guitar programs (24-31) - HEURISTIC")
            if role == TrackRole.UNKNOWN:
                role = TrackRole.GUITAR
                confidence = max(confidence, 0.50)
        
        if any(32 <= p <= 39 for p in unique_programs):
            evidence.append("Uses GM bass programs (32-39) - HEURISTIC")
            if role == TrackRole.UNKNOWN:
                role = TrackRole.BASS
                confidence = max(confidence, 0.50)
        
        if any(80 <= p <= 87 for p in unique_programs):
            evidence.append("Uses GM synth lead programs (80-87) - HEURISTIC")
            if role == TrackRole.UNKNOWN:
                role = TrackRole.MELODIC
                confidence = max(confidence, 0.45)
    
    # If still unknown, check for percussion-like patterns
    if role == TrackRole.UNKNOWN and notes:
        # Check for repetitive rhythmic patterns (possible percussion)
        durations = [n.duration_ticks for n in notes if n.duration_ticks > 0]
        if durations:
            avg_duration = sum(durations) / len(durations)
            if avg_duration < 120:  # Short notes
                evidence.append("Short average note duration suggests percussive playing")
                role = TrackRole.PERCUSSION
                confidence = 0.40
    
    # Cap confidence for purely heuristic determinations
    if role == TrackRole.UNKNOWN:
        evidence.append("No strong evidence for specific role")
        confidence = 0.0
    
    return role, min(confidence, 0.99), evidence


def analyze_track_rhythm(
    notes: list[NoteEvent],
    ticks_per_beat: int
) -> dict[str, Any]:
    """
    Analyze rhythmic characteristics of a track.
    
    Args:
        notes: List of note events
        ticks_per_beat: PPQN value
    
    Returns:
        Dictionary with rhythm analysis
    """
    if not notes or ticks_per_beat <= 0:
        return {"rhythm_analysis": "insufficient_data"}
    
    # Calculate inter-onset intervals
    sorted_notes = sorted(notes, key=lambda n: n.absolute_tick)
    ioi_list = []
    
    for i in range(1, len(sorted_notes)):
        ioi = sorted_notes[i].absolute_tick - sorted_notes[i-1].absolute_tick
        if ioi > 0:
            ioi_list.append(ioi)
    
    if not ioi_list:
        return {"rhythm_analysis": "no_intervals"}
    
    # Convert to beat units
    ioi_beats = [ioi / ticks_per_beat for ioi in ioi_list]
    
    # Common subdivisions
    sixteenth = 0.25
    eighth = 0.5
    quarter = 1.0
    
    def count_near(value: float, target: float, tolerance: float = 0.1) -> int:
        return sum(1 for v in ioi_beats if abs(v - target) < tolerance)
    
    total = len(ioi_beats)
    
    return {
        "inter_onset_intervals": {
            "count": total,
            "min_beats": min(ioi_beats),
            "max_beats": max(ioi_beats),
            "mean_beats": sum(ioi_beats) / total
        },
        "subdivision_analysis": {
            "sixteenth_notes": count_near(sixteenth),
            "eighth_notes": count_near(eighth),
            "quarter_notes": count_near(quarter),
            "sixteenth_ratio": count_near(sixteenth) / total if total > 0 else 0,
            "eighth_ratio": count_near(eighth) / total if total > 0 else 0,
            "quarter_ratio": count_near(quarter) / total if total > 0 else 0
        }
    }


def compute_track_density(
    notes: list[NoteEvent],
    duration_ticks: int
) -> float:
    """
    Compute note density (notes per tick).
    
    Args:
        notes: List of note events
        duration_ticks: Total duration in ticks
    
    Returns:
        Note density value
    """
    if duration_ticks <= 0:
        return 0.0
    return len(notes) / duration_ticks
