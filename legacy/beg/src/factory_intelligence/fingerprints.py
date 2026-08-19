"""
KORG PA800 Factory Intelligence - Fingerprints

Generates deterministic fingerprints for Factory Styles.
"""

from __future__ import annotations

import hashlib
import logging
import statistics
from typing import Any

from .config import VELOCITY_HISTOGRAM_BUCKETS, DURATION_HISTOGRAM_BUCKETS
from .models import StyleFingerprint, FactoryStyle, TrackAnalysis


logger = logging.getLogger(__name__)


def compute_velocity_histogram(velocities: list[int], buckets: int = VELOCITY_HISTOGRAM_BUCKETS) -> tuple[float, ...]:
    """
    Compute velocity histogram with fixed buckets.
    
    Args:
        velocities: List of velocity values (0-127)
        buckets: Number of histogram buckets
    
    Returns:
        Tuple of normalized bucket values
    """
    if not velocities:
        return tuple([0.0] * buckets)
    
    # Bucket size: 128 / buckets
    bucket_size = 128 / buckets
    histogram = [0] * buckets
    
    for v in velocities:
        bucket_index = min(int(v / bucket_size), buckets - 1)
        histogram[bucket_index] += 1
    
    # Normalize to proportions
    total = len(velocities)
    return tuple(h / total for h in histogram)


def compute_pitch_class_distribution(notes: list[Any]) -> tuple[int, ...]:
    """
    Compute pitch class distribution (0-11).
    
    Args:
        notes: List of note events or pitch values
    
    Returns:
        Tuple of counts per pitch class
    """
    distribution = [0] * 12
    
    for note in notes:
        if hasattr(note, 'note'):
            pitch = note.note
        else:
            pitch = note
        distribution[pitch % 12] += 1
    
    return tuple(distribution)


def compute_duration_histogram(durations: list[int], buckets: int = DURATION_HISTOGRAM_BUCKETS) -> tuple[float, ...]:
    """
    Compute duration histogram with fixed buckets.
    
    Args:
        durations: List of duration values in ticks
        buckets: Number of histogram buckets
    
    Returns:
        Tuple of normalized bucket values
    """
    if not durations:
        return tuple([0.0] * buckets)
    
    max_duration = max(durations)
    if max_duration <= 0:
        return tuple([0.0] * buckets)
    
    bucket_size = max_duration / buckets
    histogram = [0] * buckets
    
    for d in durations:
        if d > 0:
            bucket_index = min(int(d / bucket_size), buckets - 1)
            histogram[bucket_index] += 1
    
    # Normalize to proportions
    total = len(durations)
    return tuple(h / total for h in histogram)


def compute_channel_distribution(tracks: list[TrackAnalysis]) -> tuple[int, ...]:
    """
    Compute channel usage distribution (channels 0-15).
    
    Args:
        tracks: List of track analyses
    
    Returns:
        Tuple of counts per channel
    """
    distribution = [0] * 16
    
    for track in tracks:
        for ch in track.channels:
            if 0 <= ch < 16:
                distribution[ch] += 1
    
    return tuple(distribution)


def compute_program_distribution(tracks: list[TrackAnalysis]) -> tuple[int, ...]:
    """
    Compute program change distribution (programs 0-127).
    
    Args:
        tracks: List of track analyses
    
    Returns:
        Tuple of counts per program
    """
    distribution = [0] * 128
    
    for track in tracks:
        for _, program in track.program_changes:
            if 0 <= program < 128:
                distribution[program] += 1
    
    return tuple(distribution)


def compute_cc_distribution(tracks: list[TrackAnalysis]) -> tuple[int, ...]:
    """
    Compute control change distribution (CC numbers 0-127).
    
    Args:
        tracks: List of track analyses
    
    Returns:
        Tuple of counts per CC number
    """
    distribution = [0] * 128
    
    for track in tracks:
        for cc_num, events in track.control_changes.items():
            if 0 <= cc_num < 128:
                distribution[cc_num] += len(events)
    
    return tuple(distribution)


def compute_sysex_signature(sysex_data: list[bytes]) -> str:
    """
    Compute a hash signature for SysEx content.
    
    Args:
        sysex_data: List of raw SysEx byte sequences
    
    Returns:
        Hex string hash
    """
    if not sysex_data:
        return hashlib.sha256(b"").hexdigest()[:16]
    
    # Concatenate all SysEx data
    combined = b"".join(sysex_data)
    return hashlib.sha256(combined).hexdigest()[:16]


def generate_fingerprint(style: FactoryStyle) -> StyleFingerprint:
    """
    Generate a deterministic fingerprint for a Factory Style.
    
    Args:
        style: Analyzed FactoryStyle object
    
    Returns:
        StyleFingerprint object
    """
    # Collect all velocities
    all_velocities: list[int] = []
    all_notes: list[Any] = []
    all_durations: list[int] = []
    sysex_data: list[bytes] = []
    pattern_lengths: list[int] = []
    
    for track in style.tracks:
        for note in track.notes:
            all_velocities.append(note.velocity)
            all_notes.append(note)
            if note.duration_ticks > 0:
                all_durations.append(note.duration_ticks)
        
        sysex_data.extend(track.sysex_data if hasattr(track, 'sysex_data') else [])
    
    for pattern in style.patterns:
        pattern_lengths.append(pattern.length_ticks)
    
    # Compute distributions
    velocity_histogram = compute_velocity_histogram(all_velocities)
    pitch_distribution = compute_pitch_class_distribution(all_notes)
    duration_histogram = compute_duration_histogram(all_durations)
    channel_distribution = compute_channel_distribution(style.tracks)
    program_distribution = compute_program_distribution(style.tracks)
    cc_distribution = compute_cc_distribution(style.tracks)
    sysex_signature = compute_sysex_signature(sysex_data)
    
    # Compute densities
    rhythmic_density = 0.0
    timing_density = 0.0
    
    if style.duration_ticks > 0:
        total_notes = sum(t.note_count for t in style.tracks)
        total_events = sum(t.event_count for t in style.tracks)
        rhythmic_density = total_notes / style.duration_ticks
        timing_density = total_events / style.duration_ticks
    
    return StyleFingerprint(
        style_id=style.style_id,
        track_count=style.track_count,
        event_count=sum(t.event_count for t in style.tracks),
        note_count=sum(t.note_count for t in style.tracks),
        channel_distribution=channel_distribution,
        velocity_distribution=velocity_histogram,
        pitch_distribution=pitch_distribution,
        duration_distribution=duration_histogram,
        rhythmic_density=rhythmic_density,
        timing_density=timing_density,
        program_distribution=program_distribution,
        cc_distribution=cc_distribution,
        sysex_signature=sysex_signature,
        pattern_lengths=tuple(sorted(pattern_lengths))
    )
