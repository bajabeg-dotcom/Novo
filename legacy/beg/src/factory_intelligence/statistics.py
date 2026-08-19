"""
KORG PA800 Factory Intelligence - Statistics

Aggregate statistics for the Factory dataset.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any

from .models import (
    DatasetReport,
    FactoryStyle,
    TrackAnalysis,
    VelocityStats
)


logger = logging.getLogger(__name__)


def compute_aggregate_statistics(report: DatasetReport) -> dict[str, Any]:
    """
    Compute aggregate statistics across all analyzed styles.
    
    Args:
        report: DatasetReport with analyzed styles
    
    Returns:
        Dictionary with aggregate statistics
    """
    if not report.styles:
        return {"error": "No styles to analyze"}
    
    # Collect data points
    track_counts: list[int] = []
    event_counts: list[int] = []
    note_counts: list[int] = []
    ppqn_values: list[int] = []
    midi_types: list[int] = []
    all_velocities: list[int] = []
    channel_usage: dict[int, int] = {}
    program_usage: dict[int, int] = {}
    cc_usage: dict[int, int] = {}
    sysex_total = 0
    pattern_lengths: list[int] = []
    
    for style in report.styles:
        track_counts.append(style.track_count)
        event_counts.append(sum(t.event_count for t in style.tracks))
        note_counts.append(sum(t.note_count for t in style.tracks))
        ppqn_values.append(style.ticks_per_beat)
        midi_types.append(style.midi_type)
        
        for track in style.tracks:
            # Channel distribution
            for ch in track.channels:
                channel_usage[ch] = channel_usage.get(ch, 0) + 1
            
            # Program distribution
            for _, prog in track.program_changes:
                program_usage[prog] = program_usage.get(prog, 0) + 1
            
            # CC distribution
            for cc_num, events in track.control_changes.items():
                cc_usage[cc_num] = cc_usage.get(cc_num, 0) + len(events)
            
            # Collect velocities
            if track.velocity_stats:
                all_velocities.extend([track.velocity_stats.min] * max(1, track.note_count // 10))
            
            sysex_total += track.sysex_count
        
        # Pattern lengths
        for pattern in style.patterns:
            pattern_lengths.append(pattern.length_ticks)
    
    # Compute statistics
    def safe_list_stats(values: list[int | float]) -> dict[str, float]:
        if not values:
            return {}
        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0.0
        }
    
    result = {
        "style_count": len(report.styles),
        "track_counts": safe_list_stats(track_counts),
        "event_counts": safe_list_stats(event_counts),
        "note_counts": safe_list_stats(note_counts),
        "ppqn_distribution": dict(sorted({v: ppqn_values.count(v) for v in set(ppqn_values)}.items())),
        "midi_type_distribution": {i: midi_types.count(i) for i in range(3)},
        "channel_distribution": dict(sorted(channel_usage.items())),
        "program_distribution": dict(sorted(program_usage.items())),
        "cc_distribution": dict(sorted(cc_usage.items())),
        "sysex_total": sysex_total,
        "pattern_lengths": safe_list_stats(pattern_lengths) if pattern_lengths else {}
    }
    
    # Velocity statistics across all tracks
    velocity_stats_all = {}
    if all_velocities:
        sorted_vels = sorted(all_velocities)
        n = len(sorted_vels)
        
        def percentile(p: float) -> float:
            k = (n - 1) * p / 100
            f = int(k)
            c = min(f + 1, n - 1)
            return sorted_vels[f] + (sorted_vels[c] - sorted_vels[f]) * (k - f)
        
        velocity_stats_all = {
            "min": min(all_velocities),
            "max": max(all_velocities),
            "mean": statistics.mean(all_velocities),
            "median": statistics.median(all_velocities),
            "p10": percentile(10),
            "p25": percentile(25),
            "p50": percentile(50),
            "p75": percentile(75),
            "p90": percentile(90)
        }
    
    result["velocity_stats"] = velocity_stats_all
    
    return result


def compute_note_range_statistics(styles: list[FactoryStyle]) -> dict[str, Any]:
    """
    Compute statistics about note ranges across all styles.
    
    Args:
        styles: List of analyzed FactoryStyle objects
    
    Returns:
        Dictionary with note range statistics
    """
    all_notes: list[int] = []
    
    for style in styles:
        for track in style.tracks:
            for note_event in track.notes:
                all_notes.append(note_event.note)
    
    if not all_notes:
        return {"note_range": "no_data"}
    
    # Pitch class distribution
    pitch_class_counts = [0] * 12
    for note in all_notes:
        pitch_class_counts[note % 12] += 1
    
    # Octave distribution
    octave_counts: dict[int, int] = {}
    for note in all_notes:
        octave = (note // 12) - 1
        octave_counts[octave] = octave_counts.get(octave, 0) + 1
    
    return {
        "total_notes": len(all_notes),
        "min_note": min(all_notes),
        "max_note": max(all_notes),
        "mean_note": statistics.mean(all_notes),
        "pitch_class_distribution": pitch_class_counts,
        "octave_distribution": dict(sorted(octave_counts.items())),
        "most_common_pitch_class": pitch_class_counts.index(max(pitch_class_counts)),
        "most_common_octave": max(octave_counts, key=octave_counts.get) if octave_counts else None
    }


def compute_rhythmic_density_statistics(styles: list[FactoryStyle]) -> dict[str, Any]:
    """
    Compute rhythmic density statistics.
    
    Args:
        styles: List of analyzed FactoryStyle objects
    
    Returns:
        Dictionary with rhythmic density statistics
    """
    densities: list[float] = []
    
    for style in styles:
        if style.duration_ticks > 0:
            total_notes = sum(t.note_count for t in style.tracks)
            density = total_notes / style.duration_ticks
            densities.append(density)
    
    if not densities:
        return {"rhythmic_density": "no_data"}
    
    return {
        "min_density": min(densities),
        "max_density": max(densities),
        "mean_density": statistics.mean(densities),
        "median_density": statistics.median(densities),
        "styles_analyzed": len(densities)
    }
