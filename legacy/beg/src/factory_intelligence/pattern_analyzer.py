"""
KORG PA800 Factory Intelligence - Pattern Analyzer

Detects patterns and section candidates in Factory Styles.
IMPORTANT: All pattern/section detection is HEURISTIC, not deterministic.
"""

from __future__ import annotations

import logging
from typing import Any

from .config import (
    MIN_PATTERN_LENGTH_TICKS,
    MAX_PATTERN_LENGTH_TICKS,
    PATTERN_REPETITION_THRESHOLD,
    MIN_SECTION_LENGTH_TICKS,
    SECTION_GAP_THRESHOLD_TICKS
)
from .models import PatternCandidate, SectionCandidate, SectionType, NoteEvent


logger = logging.getLogger(__name__)


def detect_pattern_repetition(
    notes: list[NoteEvent],
    ticks_per_beat: int,
    pattern_length_ticks: int
) -> tuple[float, list[str]]:
    """
    Detect if a pattern repeats at regular intervals.
    
    Args:
        notes: List of note events
        ticks_per_beat: PPQN value
        pattern_length_ticks: Expected pattern length in ticks
    
    Returns:
        Tuple of (confidence, evidence_list)
    """
    if not notes or pattern_length_ticks <= 0:
        return 0.0, ["Insufficient data for pattern detection"]
    
    evidence: list[str] = []
    
    # Group notes by pattern period
    sorted_notes = sorted(notes, key=lambda n: n.absolute_tick)
    
    # Create pitch-time sequences for each potential pattern instance
    pattern_instances: dict[int, list[tuple[int, int]]] = {}  # period_index -> [(pitch, relative_tick)]
    
    for note in sorted_notes:
        period_index = note.absolute_tick // pattern_length_ticks
        relative_tick = note.absolute_tick % pattern_length_ticks
        # Quantize relative tick to nearest 16th note for comparison
        sixteenth_ticks = ticks_per_beat // 4
        quantized_tick = (relative_tick // sixteenth_ticks) * sixteenth_ticks
        
        if period_index not in pattern_instances:
            pattern_instances[period_index] = []
        pattern_instances[period_index].append((note.note, quantized_tick))
    
    if len(pattern_instances) < 2:
        return 0.0, ["Only one pattern instance found"]
    
    # Compare consecutive pattern instances
    matches = 0
    comparisons = 0
    
    periods = sorted(pattern_instances.keys())
    for i in range(len(periods) - 1):
        p1 = pattern_instances[periods[i]]
        p2 = pattern_instances[periods[i + 1]]
        
        # Simple similarity check
        set1 = set(p1)
        set2 = set(p2)
        
        if set1 and set2:
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            similarity = intersection / union if union > 0 else 0
            
            if similarity >= PATTERN_REPETITION_THRESHOLD:
                matches += 1
            comparisons += 1
    
    if comparisons == 0:
        return 0.0, ["No comparable pattern instances"]
    
    repetition_ratio = matches / comparisons
    confidence = min(repetition_ratio, 0.95)
    
    if confidence >= 0.7:
        evidence.append(f"Pattern repeats with {confidence:.0%} similarity")
    if len(pattern_instances) >= 3:
        evidence.append(f"Found {len(pattern_instances)} pattern instances")
    
    return confidence, evidence


def detect_bar_boundaries(
    notes: list[NoteEvent],
    ticks_per_beat: int,
    time_signature: tuple[int, int] = (4, 4)
) -> list[int]:
    """
    Detect likely bar boundaries based on note onsets.
    
    Args:
        notes: List of note events
        ticks_per_beat: PPQN value
        time_signature: (numerator, denominator) tuple
    
    Returns:
        List of tick positions representing bar boundaries
    """
    if not notes:
        return []
    
    beats_per_bar = time_signature[0]
    ticks_per_bar = ticks_per_beat * beats_per_bar
    
    # Find strong onsets (velocity > threshold)
    strong_onsets = [n.absolute_tick for n in notes if n.velocity >= 90]
    
    if not strong_onsets:
        # Fall back to theoretical bar positions
        max_tick = max(n.absolute_tick for n in notes)
        return list(range(0, max_tick + 1, ticks_per_bar))
    
    # Look for onsets that align with theoretical bar positions
    boundaries = []
    for onset in strong_onsets:
        remainder = onset % ticks_per_bar
        if remainder < ticks_per_beat // 4:  # Within first quarter beat
            boundaries.append(onset - remainder)
    
    # Remove duplicates and sort
    boundaries = sorted(set(boundaries))
    
    # Fill gaps with theoretical boundaries
    if boundaries:
        filled = [boundaries[0]]
        for i in range(1, len(boundaries)):
            gap = boundaries[i] - boundaries[i-1]
            if gap > ticks_per_bar * 1.5:
                # Add intermediate boundaries
                current = boundaries[i-1] + ticks_per_bar
                while current < boundaries[i]:
                    filled.append(current)
                    current += ticks_per_bar
            filled.append(boundaries[i])
        boundaries = filled
    
    return boundaries


def find_pattern_candidates(
    notes: list[NoteEvent],
    ticks_per_beat: int,
    duration_ticks: int
) -> list[PatternCandidate]:
    """
    Find candidate patterns in a track.
    
    Args:
        notes: List of note events
        ticks_per_beat: PPQN value
        duration_ticks: Total duration in ticks
    
    Returns:
        List of PatternCandidate objects
    """
    candidates: list[PatternCandidate] = []
    
    if not notes or duration_ticks <= 0:
        return candidates
    
    # Try common pattern lengths (in beats)
    common_lengths_beats = [1, 2, 4, 8]
    
    for length_beats in common_lengths_beats:
        length_ticks = length_beats * ticks_per_beat
        
        if length_ticks < MIN_PATTERN_LENGTH_TICKS:
            continue
        if length_ticks > min(MAX_PATTERN_LENGTH_TICKS, duration_ticks):
            continue
        
        # How many times does this pattern fit?
        num_instances = duration_ticks // length_ticks
        
        if num_instances < 2:
            continue
        
        # Check for repetition
        confidence, evidence = detect_pattern_repetition(notes, ticks_per_beat, length_ticks)
        
        if confidence >= PATTERN_REPETITION_THRESHOLD:
            candidate = PatternCandidate(
                start_tick=0,
                end_tick=length_ticks,
                length_ticks=length_ticks,
                length_beats=length_beats,
                length_bars=length_beats / 4,  # Assuming 4/4
                confidence=confidence,
                evidence=evidence,
                source_type="HEURISTIC"
            )
            candidates.append(candidate)
    
    # Sort by confidence descending
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    
    return candidates


def find_section_candidates(
    notes: list[NoteEvent],
    ticks_per_beat: int,
    duration_ticks: int
) -> list[SectionCandidate]:
    """
    Find candidate sections in a style.
    
    IMPORTANT: This is highly HEURISTIC. Factory Styles don't have
    standardized section markers like songs do.
    
    Args:
        notes: List of note events
        ticks_per_beat: PPQN value
        duration_ticks: Total duration in ticks
    
    Returns:
        List of SectionCandidate objects
    """
    candidates: list[SectionCandidate] = []
    
    if not notes or duration_ticks <= 0:
        return candidates
    
    sorted_notes = sorted(notes, key=lambda n: n.absolute_tick)
    
    # Detect density changes as potential section boundaries
    window_size = ticks_per_beat * 2  # 2-beat windows
    density_changes: list[tuple[int, float]] = []  # (tick, density_change)
    
    prev_density = 0
    current_tick = 0
    
    while current_tick < duration_ticks:
        window_end = current_tick + window_size
        notes_in_window = sum(1 for n in sorted_notes if current_tick <= n.absolute_tick < window_end)
        density = notes_in_window / window_size if window_size > 0 else 0
        
        if prev_density > 0:
            change = abs(density - prev_density) / prev_density
            if change > 0.5:  # 50% change threshold
                density_changes.append((current_tick, change))
        
        prev_density = density
        current_tick += window_size
    
    # Use density changes to suggest section boundaries
    if density_changes:
        # First section (potential INTRO)
        if density_changes and density_changes[0][0] > MIN_SECTION_LENGTH_TICKS:
            candidates.append(SectionCandidate(
                section_type=SectionType.UNKNOWN,
                start_tick=0,
                end_tick=density_changes[0][0],
                confidence=0.40,
                evidence=["Density change detected"],
                source_type="HEURISTIC"
            ))
        
        # Subsequent sections
        for i in range(len(density_changes) - 1):
            start = density_changes[i][0]
            end = density_changes[i + 1][0]
            
            if end - start >= MIN_SECTION_LENGTH_TICKS:
                candidates.append(SectionCandidate(
                    section_type=SectionType.UNKNOWN,
                    start_tick=start,
                    end_tick=end,
                    confidence=0.35,
                    evidence=["Density change between sections"],
                    source_type="HEURISTIC"
                ))
        
        # Last section
        last_start = density_changes[-1][0]
        if duration_ticks - last_start >= MIN_SECTION_LENGTH_TICKS:
            candidates.append(SectionCandidate(
                section_type=SectionType.UNKNOWN,
                start_tick=last_start,
                end_tick=duration_ticks,
                confidence=0.35,
                evidence=["Final section after density change"],
                source_type="HEURISTIC"
            ))
    
    # If no density-based sections found, create a single UNKNOWN section
    if not candidates:
        candidates.append(SectionCandidate(
            section_type=SectionType.UNKNOWN,
            start_tick=0,
            end_tick=duration_ticks,
            confidence=0.20,
            evidence=["No clear section boundaries detected"],
            source_type="HEURISTIC"
        ))
    
    return candidates


def analyze_periodicity(
    notes: list[NoteEvent],
    ticks_per_beat: int
) -> dict[str, Any]:
    """
    Analyze periodicity in note patterns.
    
    Args:
        notes: List of note events
        ticks_per_beat: PPQN value
    
    Returns:
        Dictionary with periodicity analysis
    """
    if not notes or ticks_per_beat <= 0:
        return {"periodicity": "insufficient_data"}
    
    sorted_notes = sorted(notes, key=lambda n: n.absolute_tick)
    
    # Calculate inter-onset intervals
    iois = []
    for i in range(1, len(sorted_notes)):
        ioi = sorted_notes[i].absolute_tick - sorted_notes[i-1].absolute_tick
        if ioi > 0:
            iois.append(ioi)
    
    if not iois:
        return {"periodicity": "no_intervals"}
    
    # Find most common IOI (mode)
    ioi_counts: dict[int, int] = {}
    for ioi in iois:
        # Quantize to nearest 16th note
        sixteenth = ticks_per_beat // 4
        quantized = (ioi // sixteenth) * sixteenth
        ioi_counts[quantized] = ioi_counts.get(quantized, 0) + 1
    
    if not ioi_counts:
        return {"periodicity": "no_quantized_intervals"}
    
    most_common_ioi = max(ioi_counts, key=ioi_counts.get)
    most_common_count = ioi_counts[most_common_ioi]
    
    # Convert to beats
    most_common_beats = most_common_ioi / ticks_per_beat
    
    return {
        "most_common_ioi_ticks": most_common_ioi,
        "most_common_ioi_beats": most_common_beats,
        "occurrence_count": most_common_count,
        "total_intervals": len(iois),
        "periodicity_ratio": most_common_count / len(iois) if iois else 0
    }
