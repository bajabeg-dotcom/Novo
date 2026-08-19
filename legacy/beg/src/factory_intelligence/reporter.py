"""
KORG PA800 Factory Intelligence - Reporter

Generates JSON and human-readable reports for the Factory dataset analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import REPORTS_DIR, JSON_INDENT
from .models import DatasetReport, FactoryStyle


logger = logging.getLogger(__name__)


def style_to_dict(style: FactoryStyle, include_raw_events: bool = False) -> dict[str, Any]:
    """
    Convert a FactoryStyle to a dictionary for JSON serialization.
    
    Args:
        style: FactoryStyle object
        include_raw_events: Whether to include raw MIDI events
    
    Returns:
        Dictionary representation
    """
    tracks_data = []
    
    for track in style.tracks:
        track_dict = {
            "track_index": track.track_index,
            "track_name": track.track_name,
            "event_count": track.event_count,
            "note_count": track.note_count,
            "channels": sorted(list(track.channels)),
            "program_changes": track.program_changes,
            "control_changes": {str(k): v for k, v in track.control_changes.items()},
            "pitch_bends": track.pitch_bends,
            "aftertouch_count": track.aftertouch_count,
            "polytouch_count": track.polytouch_count,
            "sysex_count": track.sysex_count,
            "absolute_tick_length": track.absolute_tick_length,
            "role": track.role.value,
            "role_confidence": track.role_confidence,
            "role_evidence": track.role_evidence
        }
        
        if track.velocity_stats:
            track_dict["velocity_stats"] = {
                "min": track.velocity_stats.min,
                "max": track.velocity_stats.max,
                "mean": track.velocity_stats.mean,
                "median": track.velocity_stats.median,
                "std": track.velocity_stats.std,
                "p10": track.velocity_stats.p10,
                "p25": track.velocity_stats.p25,
                "p50": track.velocity_stats.p50,
                "p75": track.velocity_stats.p75,
                "p90": track.velocity_stats.p90,
                "count": track.velocity_stats.count
            }
        
        if track.timing_stats:
            track_dict["timing_stats"] = {
                "min_delta_tick": track.timing_stats.min_delta_tick,
                "max_delta_tick": track.timing_stats.max_delta_tick,
                "mean_delta_tick": track.timing_stats.mean_delta_tick,
                "median_delta_tick": track.timing_stats.median_delta_tick,
                "total_ticks": track.timing_stats.total_ticks,
                "event_count": track.timing_stats.event_count
            }
        
        # Only include raw events if explicitly requested (for debugging)
        if include_raw_events:
            track_dict["notes"] = [
                {
                    "absolute_tick": n.absolute_tick,
                    "delta_tick": n.delta_tick,
                    "channel": n.channel,
                    "note": n.note,
                    "velocity": n.velocity,
                    "duration_ticks": n.duration_ticks,
                    "end_tick": n.end_tick
                }
                for n in track.notes
            ]
        
        tracks_data.append(track_dict)
    
    patterns_data = [
        {
            "start_tick": p.start_tick,
            "end_tick": p.end_tick,
            "length_ticks": p.length_ticks,
            "length_beats": p.length_beats,
            "length_bars": p.length_bars,
            "confidence": p.confidence,
            "evidence": p.evidence,
            "source_type": p.source_type
        }
        for p in style.patterns
    ]
    
    sections_data = [
        {
            "section_type": s.section_type.value,
            "start_tick": s.start_tick,
            "end_tick": s.end_tick,
            "confidence": s.confidence,
            "evidence": s.evidence,
            "source_type": s.source_type
        }
        for s in style.sections
    ]
    
    sysex_data = [
        {
            "track_index": s.track_index,
            "absolute_tick": s.absolute_tick,
            "length": s.length,
            "manufacturer_id": s.manufacturer_id.hex() if s.manufacturer_id else "",
            "raw_hex": s.raw_hex,
            "is_korg": s.is_korg
        }
        for s in style.sysex_events
    ]
    
    fingerprint_data = None
    if style.fingerprint:
        fingerprint_data = {
            "style_id": style.fingerprint.style_id,
            "track_count": style.fingerprint.track_count,
            "event_count": style.fingerprint.event_count,
            "note_count": style.fingerprint.note_count,
            "channel_distribution": list(style.fingerprint.channel_distribution),
            "velocity_distribution": list(style.fingerprint.velocity_distribution),
            "pitch_distribution": list(style.fingerprint.pitch_distribution),
            "rhythmic_density": style.fingerprint.rhythmic_density,
            "timing_density": style.fingerprint.timing_density,
            "sysex_signature": style.fingerprint.sysex_signature,
            "pattern_lengths": list(style.fingerprint.pattern_lengths),
            "hash": style.fingerprint.to_hash()
        }
    
    return {
        "file_path": style.file_path,
        "filename": style.filename,
        "style_id": style.style_id,
        "sha256": style.sha256,
        "midi_type": style.midi_type,
        "ticks_per_beat": style.ticks_per_beat,
        "track_count": style.track_count,
        "duration_ticks": style.duration_ticks,
        "tempo_bpm": style.tempo_bpm,
        "tracks": tracks_data,
        "patterns": patterns_data,
        "sections": sections_data,
        "sysex_events": sysex_data,
        "fingerprint": fingerprint_data
    }


def generate_json_report(report: DatasetReport, output_path: Path | None = None) -> Path:
    """
    Generate JSON report for the dataset analysis.
    
    Args:
        report: DatasetReport object
        output_path: Optional custom output path
    
    Returns:
        Path to generated report file
    """
    if output_path is None:
        output_path = REPORTS_DIR / "factory_dataset_report.json"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build report structure
    report_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "expected_styles": report.expected_styles,
            "found_styles": report.found_styles,
            "readable_styles": report.readable_styles,
            "failed_styles": report.failed_styles,
            "duplicates": report.duplicates,
            "validation_result": report.validation_result
        },
        "aggregate_statistics": {
            "total_tracks": report.total_tracks,
            "total_notes": report.total_notes,
            "total_events": report.total_events,
            "track_count_stats": report.track_count_stats,
            "velocity_stats": report.velocity_stats,
            "ppqn_distribution": report.ppqn_distribution,
            "midi_type_distribution": report.midi_type_distribution,
            "channel_distribution": report.channel_distribution,
            "program_distribution": report.program_distribution,
            "cc_distribution": report.cc_distribution,
            "sysex_count": report.sysex_count,
            "pattern_count": report.pattern_count,
            "section_candidate_count": report.section_candidate_count
        },
        "styles": [
            style_to_dict(style, include_raw_events=False)
            for style in report.styles
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=JSON_INDENT, ensure_ascii=False)
    
    logger.info(f"JSON report written to {output_path}")
    return output_path


def generate_summary_report(report: DatasetReport, output_path: Path | None = None) -> Path:
    """
    Generate human-readable summary report.
    
    Args:
        report: DatasetReport object
        output_path: Optional custom output path
    
    Returns:
        Path to generated report file
    """
    if output_path is None:
        output_path = REPORTS_DIR / "factory_dataset_summary.txt"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    lines = []
    
    # Header
    lines.append("=" * 60)
    lines.append("KORG PA800 FACTORY INTELLIGENCE — PHASE 1")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Validation Summary
    lines.append("FACTORY DATASET VALIDATION")
    lines.append("-" * 40)
    lines.append(f"Expected styles : {report.expected_styles}")
    lines.append(f"Found styles    : {report.found_styles}")
    lines.append(f"Readable        : {report.readable_styles}")
    lines.append(f"Failed          : {report.failed_styles}")
    lines.append(f"Duplicates      : {report.duplicates}")
    lines.append("")
    lines.append(f"RESULT: {report.validation_result}")
    lines.append("")
    
    # Aggregate Statistics
    lines.append("AGGREGATE STATISTICS")
    lines.append("-" * 40)
    lines.append(f"Total Tracks    : {report.total_tracks}")
    lines.append(f"Total Notes     : {report.total_notes}")
    lines.append(f"Total Events    : {report.total_events}")
    lines.append(f"Patterns        : {report.pattern_count}")
    lines.append(f"Section Candidates: {report.section_candidate_count}")
    lines.append("")
    
    # Track Count Stats
    if report.track_count_stats:
        lines.append("Track Count Statistics")
        lines.append(f"  Min: {report.track_count_stats.get('min', 'N/A')}")
        lines.append(f"  Max: {report.track_count_stats.get('max', 'N/A')}")
        lines.append(f"  Mean: {report.track_count_stats.get('mean', 'N/A'):.2f}" if report.track_count_stats.get('mean') else "  Mean: N/A")
        lines.append(f"  Median: {report.track_count_stats.get('median', 'N/A')}")
        lines.append("")
    
    # Velocity Stats
    if report.velocity_stats:
        lines.append("Velocity Statistics (All Styles)")
        lines.append(f"  Min: {report.velocity_stats.get('min', 'N/A')}")
        lines.append(f"  Max: {report.velocity_stats.get('max', 'N/A')}")
        lines.append(f"  Mean: {report.velocity_stats.get('mean', 'N/A'):.2f}" if report.velocity_stats.get('mean') else "  Mean: N/A")
        lines.append(f"  Median: {report.velocity_stats.get('median', 'N/A'):.2f}" if report.velocity_stats.get('median') else "  Median: N/A")
        lines.append("")
    
    # PPQN Distribution
    if report.ppqn_distribution:
        lines.append("PPQN Distribution")
        for ppqn, count in sorted(report.ppqn_distribution.items()):
            lines.append(f"  {ppqn}: {count} styles")
        lines.append("")
    
    # MIDI Type Distribution
    if report.midi_type_distribution:
        lines.append("MIDI Type Distribution")
        for midi_type, count in sorted(report.midi_type_distribution.items()):
            type_name = {0: "Single-track", 1: "Multi-track", 2: "Multi-song"}.get(midi_type, f"Type {midi_type}")
            lines.append(f"  Type {midi_type} ({type_name}): {count} styles")
        lines.append("")
    
    # Channel Distribution (top channels)
    if report.channel_distribution:
        lines.append("Channel Usage (Top 5)")
        sorted_channels = sorted(report.channel_distribution.items(), key=lambda x: x[1], reverse=True)[:5]
        for ch, count in sorted_channels:
            ch_name = f"Channel {ch + 1}" + (" (Drums)" if ch == 9 else "")
            lines.append(f"  {ch_name}: {count} tracks")
        lines.append("")
    
    # SysEx
    lines.append(f"SysEx Events Total: {report.sysex_count}")
    lines.append("")
    
    # Footer
    lines.append("=" * 60)
    lines.append("STATUS: FACTORY DATASET ANALYZED")
    lines.append("=" * 60)
    
    content = "\n".join(lines)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"Summary report written to {output_path}")
    return output_path


def print_validation_summary(report: DatasetReport) -> None:
    """Print validation summary to console."""
    print("\n" + "=" * 60)
    print("KORG PA800 FACTORY INTELLIGENCE — PHASE 1")
    print("=" * 60)
    print(f"\nFactory Styles : {report.found_styles} / {report.expected_styles}")
    print(f"Readable       : {report.readable_styles}")
    print(f"Failed         : {report.failed_styles}")
    print(f"Duplicates     : {report.duplicates}")
    print(f"\nTracks         : {report.total_tracks}")
    print(f"Notes          : {report.total_notes}")
    print(f"Events         : {report.total_events}")
    print(f"\nPPQN           : {report.ppqn_distribution}")
    print(f"MIDI Types     : {report.midi_type_distribution}")
    print(f"\nPatterns       : {report.pattern_count}")
    print(f"Sections       : {report.section_candidate_count}")
    print(f"\nSTATUS: {report.validation_result}")
    print("=" * 60 + "\n")
