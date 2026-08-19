"""
KORG PA800 Factory Intelligence - Event Analyzer

Analyzes MIDI events for velocity, timing, and other characteristics.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any

from .models import MidiEvent, NoteEvent, VelocityStats, TimingStats


logger = logging.getLogger(__name__)


def compute_velocity_stats(velocities: list[int]) -> VelocityStats | None:
    """
    Compute comprehensive velocity statistics.
    
    Args:
        velocities: List of velocity values (0-127)
    
    Returns:
        VelocityStats object or None if no velocities provided
    """
    if not velocities:
        return None
    
    sorted_velocities = sorted(velocities)
    n = len(sorted_velocities)
    
    # Calculate percentiles
    def percentile(data: list[int], p: float) -> float:
        k = (len(data) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(data) else f
        return data[f] + (data[c] - data[f]) * (k - f) if c != f else float(data[f])
    
    return VelocityStats(
        min=min(velocities),
        max=max(velocities),
        mean=statistics.mean(velocities),
        median=statistics.median(velocities),
        std=statistics.stdev(velocities) if len(velocities) > 1 else 0.0,
        p10=percentile(sorted_velocities, 10),
        p25=percentile(sorted_velocities, 25),
        p50=percentile(sorted_velocities, 50),
        p75=percentile(sorted_velocities, 75),
        p90=percentile(sorted_velocities, 90),
        count=n
    )


def compute_timing_stats(events: list[MidiEvent]) -> TimingStats | None:
    """
    Compute timing statistics from MIDI events.
    
    Args:
        events: List of MIDI events
    
    Returns:
        TimingStats object or None if insufficient data
    """
    if not events:
        return None
    
    delta_ticks = [e.delta_tick for e in events if e.delta_tick > 0]
    
    if not delta_ticks:
        return None
    
    total_ticks = sum(e.absolute_tick for e in events)
    
    return TimingStats(
        min_delta_tick=min(delta_ticks),
        max_delta_tick=max(delta_ticks),
        mean_delta_tick=statistics.mean(delta_ticks),
        median_delta_tick=statistics.median(delta_ticks),
        total_ticks=total_ticks,
        event_count=len(events)
    )


def analyze_notes(notes: list[NoteEvent]) -> dict[str, Any]:
    """
    Analyze note events for pitch, velocity, and duration characteristics.
    
    Args:
        notes: List of NoteEvent objects
    
    Returns:
        Dictionary with note analysis results
    """
    if not notes:
        return {
            "note_count": 0,
            "pitch_stats": {},
            "velocity_stats": None,
            "duration_stats": {}
        }
    
    pitches = [n.note for n in notes]
    velocities = [n.velocity for n in notes]
    durations = [n.duration_ticks for n in notes if n.duration_ticks > 0]
    
    # Pitch statistics
    pitch_stats = {
        "min_note": min(pitches),
        "max_note": max(pitches),
        "mean_note": statistics.mean(pitches),
        "median_note": statistics.median(pitches),
        "pitch_class_distribution": [0] * 12,
        "octave_distribution": {}
    }
    
    for pitch in pitches:
        pitch_class = pitch % 12
        octave = (pitch // 12) - 1
        pitch_stats["pitch_class_distribution"][pitch_class] += 1
        pitch_stats["octave_distribution"][octave] = pitch_stats["octave_distribution"].get(octave, 0) + 1
    
    # Velocity statistics
    velocity_stats = compute_velocity_stats(velocities)
    
    # Duration statistics
    duration_stats = {}
    if durations:
        duration_stats = {
            "min_duration": min(durations),
            "max_duration": max(durations),
            "mean_duration": statistics.mean(durations),
            "median_duration": statistics.median(durations),
            "std_duration": statistics.stdev(durations) if len(durations) > 1 else 0.0
        }
    
    return {
        "note_count": len(notes),
        "pitch_stats": pitch_stats,
        "velocity_stats": velocity_stats,
        "duration_stats": duration_stats
    }


def analyze_velocity_by_position(
    notes: list[NoteEvent],
    ticks_per_beat: int
) -> dict[str, Any]:
    """
    Analyze velocity distribution by beat position within a bar.
    
    Args:
        notes: List of NoteEvent objects
        ticks_per_beat: PPQN value
    
    Returns:
        Dictionary with velocity-by-position analysis
    """
    if not notes or ticks_per_beat <= 0:
        return {}
    
    # Group velocities by subdivision position (16th notes)
    subdivision_ticks = ticks_per_beat // 4  # 16th note
    velocity_by_subdivision: dict[int, list[int]] = {i: [] for i in range(16)}
    
    for note in notes:
        # Calculate position within bar (assuming 4/4 time signature)
        ticks_per_bar = ticks_per_beat * 4
        position_in_bar = note.absolute_tick % ticks_per_bar
        subdivision = (position_in_bar // subdivision_ticks) % 16
        velocity_by_subdivision[subdivision].append(note.velocity)
    
    result = {}
    for sub, vels in velocity_by_subdivision.items():
        if vels:
            result[f"subdivision_{sub}"] = {
                "count": len(vels),
                "mean": statistics.mean(vels),
                "median": statistics.median(vels)
            }
    
    return result


def analyze_control_changes(
    control_changes: dict[int, list[tuple[int, int]]]
) -> dict[str, Any]:
    """
    Analyze control change events.
    
    Args:
        control_changes: Dict mapping CC number to list of (tick, value) tuples
    
    Returns:
        Dictionary with CC analysis results
    """
    if not control_changes:
        return {"cc_count": 0, "cc_distribution": {}, "important_ccs": {}}
    
    cc_distribution = {}
    important_ccs = {}
    
    for cc_num, events in control_changes.items():
        cc_distribution[cc_num] = len(events)
        
        # Track important CC numbers specifically
        if cc_num in [0, 6, 32, 38, 64, 65, 98, 99, 100, 101, 120, 121, 123]:
            values = [v for _, v in events]
            important_ccs[cc_num] = {
                "count": len(events),
                "values": values,
                "mean_value": statistics.mean(values) if values else 0
            }
    
    return {
        "cc_count": sum(len(events) for events in control_changes.values()),
        "cc_distribution": cc_distribution,
        "important_ccs": important_ccs
    }


def analyze_program_changes(
    program_changes: list[tuple[int, int]]
) -> dict[str, Any]:
    """
    Analyze program change events.
    
    Args:
        program_changes: List of (tick, program) tuples
    
    Returns:
        Dictionary with program change analysis
    """
    if not program_changes:
        return {"program_change_count": 0, "programs_used": [], "program_distribution": {}}
    
    programs = [p for _, p in program_changes]
    program_counts: dict[int, int] = {}
    
    for prog in programs:
        program_counts[prog] = program_counts.get(prog, 0) + 1
    
    return {
        "program_change_count": len(program_changes),
        "programs_used": sorted(set(programs)),
        "program_distribution": program_counts
    }


def analyze_sysex(sysex_data: list[bytes]) -> dict[str, Any]:
    """
    Analyze SysEx messages.
    
    Args:
        sysex_data: List of raw SysEx byte sequences
    
    Returns:
        Dictionary with SysEx analysis
    """
    if not sysex_data:
        return {"sysex_count": 0, "manufacturer_ids": {}, "korg_sysex_count": 0}
    
    manufacturer_counts: dict[str, int] = {}
    korg_count = 0
    
    for data in sysex_data:
        if len(data) >= 1:
            # First byte after 0xF0 is manufacturer ID
            manuf_id = data[0]
            manuf_hex = f"0x{manuf_id:02X}"
            manufacturer_counts[manuf_hex] = manufacturer_counts.get(manuf_hex, 0) + 1
            
            # Check for KORG (0x42)
            if manuf_id == 0x42:
                korg_count += 1
    
    return {
        "sysex_count": len(sysex_data),
        "manufacturer_ids": manufacturer_counts,
        "korg_sysex_count": korg_count
    }
