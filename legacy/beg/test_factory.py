#!/usr/bin/env python3
"""
KORG PA800 Factory Intelligence - Main Analysis Script

Analyzes all 252 Factory Style MIDI files and generates reports.
"""

from __future__ import annotations

import logging
import statistics
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from factory_intelligence.config import (
    CANONICAL_FACTORY_DIR,
    EXPECTED_STYLE_COUNT,
    DRUM_CHANNEL,
    BASS_NOTE_THRESHOLD
)
from factory_intelligence.discovery import discover_dataset, DiscoveryResult
from factory_intelligence.midi_parser import parse_midi_file
from factory_intelligence.event_analyzer import (
    compute_velocity_stats,
    analyze_control_changes,
    analyze_program_changes,
    analyze_sysex
)
from factory_intelligence.track_analyzer import detect_track_role
from factory_intelligence.pattern_analyzer import (
    find_pattern_candidates,
    find_section_candidates
)
from factory_intelligence.fingerprints import generate_fingerprint
from factory_intelligence.statistics import compute_aggregate_statistics
from factory_intelligence.reporter import (
    generate_json_report,
    generate_summary_report,
    print_validation_summary
)
from factory_intelligence.models import (
    DatasetReport,
    FactoryStyle,
    TrackAnalysis,
    SysExEvent,
    SectionType
)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_track_analysis(track_data: dict) -> TrackAnalysis:
    """Convert parsed track data to TrackAnalysis model."""
    from factory_intelligence.models import VelocityStats, TimingStats
    
    # Compute velocity stats from notes
    velocities = [n.velocity for n in track_data["notes"]]
    velocity_stats = compute_velocity_stats(velocities) if velocities else None
    
    # Compute timing stats from events
    timing_stats = None
    if track_data["events"]:
        delta_ticks = [e.delta_tick for e in track_data["events"] if e.delta_tick > 0]
        if delta_ticks:
            from factory_intelligence.models import TimingStats
            timing_stats = TimingStats(
                min_delta_tick=min(delta_ticks),
                max_delta_tick=max(delta_ticks),
                mean_delta_tick=statistics.mean(delta_ticks),
                median_delta_tick=statistics.median(delta_ticks),
                total_ticks=max(e.absolute_tick for e in track_data["events"]),
                event_count=len(track_data["events"])
            )
    
    # Detect track role
    role, confidence, evidence = detect_track_role(
        channels=track_data["channels"],
        notes=track_data["notes"],
        program_changes=track_data["program_changes"],
        track_name=track_data["track_name"]
    )
    
    return TrackAnalysis(
        track_index=track_data["track_index"],
        track_name=track_data["track_name"],
        event_count=track_data["event_count"],
        note_count=track_data["note_count"],
        channels=track_data["channels"],
        program_changes=track_data["program_changes"],
        control_changes=track_data["control_changes"],
        pitch_bends=track_data["pitch_bends"],
        aftertouch_count=track_data["aftertouch_count"],
        polytouch_count=track_data["polytouch_count"],
        sysex_count=track_data["sysex_count"],
        meta_events=track_data["meta_events"],
        absolute_tick_length=track_data["absolute_tick_length"],
        velocity_stats=velocity_stats,
        timing_stats=timing_stats,
        notes=track_data["notes"],
        role=role,
        role_confidence=confidence,
        role_evidence=evidence
    )


def build_sysex_events(track_data_list: list[dict]) -> list[SysExEvent]:
    """Extract SysEx events from all tracks."""
    sysex_events = []
    
    for track_data in track_data_list:
        sysex_data = track_data.get("sysex_data", [])
        for i, data in enumerate(sysex_data):
            if len(data) >= 1:
                manufacturer_id = bytes([data[0]]) if data else b""
                sysex_events.append(SysExEvent(
                    track_index=track_data["track_index"],
                    absolute_tick=0,  # Would need to track this during parsing
                    length=len(data),
                    manufacturer_id=manufacturer_id,
                    raw_hex=data.hex()
                ))
    
    return sysex_events


def analyze_style(discovered_file, midi_data: dict) -> FactoryStyle:
    """Build complete FactoryStyle analysis from parsed MIDI data."""
    # Build track analyses
    tracks = [build_track_analysis(td) for td in midi_data["tracks"]]
    
    # Build SysEx events
    sysex_events = build_sysex_events(midi_data["tracks"])
    
    # Collect all notes for pattern/section analysis
    all_notes = []
    for track in tracks:
        all_notes.extend(track.notes)
    
    # Find pattern candidates
    patterns = []
    for track in tracks:
        if track.notes:
            track_patterns = find_pattern_candidates(
                track.notes,
                midi_data["ticks_per_beat"],
                midi_data["duration_ticks"]
            )
            patterns.extend(track_patterns)
    
    # Find section candidates (style-level)
    sections = find_section_candidates(
        all_notes,
        midi_data["ticks_per_beat"],
        midi_data["duration_ticks"]
    )
    
    # Create temporary style for fingerprint generation
    style = FactoryStyle(
        file_path=midi_data["file_path"],
        filename=midi_data["filename"],
        style_id=discovered_file.style_id,
        sha256=discovered_file.sha256,
        midi_type=midi_data["midi_type"],
        ticks_per_beat=midi_data["ticks_per_beat"],
        track_count=midi_data["track_count"],
        duration_ticks=midi_data["duration_ticks"],
        tempo_bpm=midi_data["tempo_bpm"],
        tracks=tracks,
        patterns=patterns,
        sections=sections,
        sysex_events=sysex_events
    )
    
    # Generate fingerprint
    style.fingerprint = generate_fingerprint(style)
    
    return style


def run_full_analysis() -> DatasetReport:
    """Run complete analysis of the Factory dataset."""
    logger.info("Starting Factory dataset analysis...")
    
    # Step 1: Discover dataset
    discovery_result = discover_dataset()
    
    if not discovery_result.files:
        logger.error("No files discovered. Check canonical directory.")
        return DatasetReport(
            expected_styles=EXPECTED_STYLE_COUNT,
            found_styles=0,
            readable_styles=0,
            failed_styles=0,
            duplicates=0,
            validation_result="FAIL: No files discovered"
        )
    
    logger.info(f"Discovered {len(discovery_result.files)} files")
    
    # Step 2: Analyze each style
    styles: list[FactoryStyle] = []
    failed_files: list[str] = []
    
    for discovered_file in discovery_result.files:
        try:
            logger.debug(f"Parsing {discovered_file.filename}...")
            midi_data = parse_midi_file(discovered_file.path)
            style = analyze_style(discovered_file, midi_data)
            styles.append(style)
        except Exception as e:
            logger.error(f"Failed to analyze {discovered_file.filename}: {e}")
            failed_files.append(discovered_file.filename)
    
    logger.info(f"Successfully analyzed {len(styles)} styles, {len(failed_files)} failed")
    
    # Step 3: Build report
    report = DatasetReport(
        expected_styles=EXPECTED_STYLE_COUNT,
        found_styles=len(discovery_result.files),
        readable_styles=len(styles),
        failed_styles=len(failed_files),
        duplicates=discovery_result.duplicates,
        styles=styles
    )
    
    # Compute aggregate statistics
    if styles:
        report.total_tracks = sum(s.track_count for s in styles)
        report.total_notes = sum(sum(t.note_count for t in s.tracks) for s in styles)
        report.total_events = sum(sum(t.event_count for t in s.tracks) for s in styles)
        
        # Track count stats
        track_counts = [s.track_count for s in styles]
        report.track_count_stats = {
            "min": min(track_counts),
            "max": max(track_counts),
            "mean": statistics.mean(track_counts),
            "median": statistics.median(track_counts)
        }
        
        # PPQN distribution
        ppqn_counts: dict[int, int] = {}
        for s in styles:
            ppqn_counts[s.ticks_per_beat] = ppqn_counts.get(s.ticks_per_beat, 0) + 1
        report.ppqn_distribution = ppqn_counts
        
        # MIDI type distribution
        type_counts: dict[int, int] = {}
        for s in styles:
            type_counts[s.midi_type] = type_counts.get(s.midi_type, 0) + 1
        report.midi_type_distribution = type_counts
        
        # Channel distribution
        channel_counts: dict[int, int] = {}
        for s in styles:
            for t in s.tracks:
                for ch in t.channels:
                    channel_counts[ch] = channel_counts.get(ch, 0) + 1
        report.channel_distribution = channel_counts
        
        # Program distribution
        program_counts: dict[int, int] = {}
        for s in styles:
            for t in s.tracks:
                for _, prog in t.program_changes:
                    program_counts[prog] = program_counts.get(prog, 0) + 1
        report.program_distribution = program_counts
        
        # CC distribution
        cc_counts: dict[int, int] = {}
        for s in styles:
            for t in s.tracks:
                for cc_num, events in t.control_changes.items():
                    cc_counts[cc_num] = cc_counts.get(cc_num, 0) + len(events)
        report.cc_distribution = cc_counts
        
        # SysEx count
        report.sysex_count = sum(len(s.sysex_events) for s in styles)
        
        # Pattern count
        report.pattern_count = sum(len(s.patterns) for s in styles)
        
        # Section candidate count
        report.section_candidate_count = sum(len(s.sections) for s in styles)
        
        # Velocity stats (sample from first few styles)
        all_velocities = []
        for s in styles[:50]:  # Sample for performance
            for t in s.tracks:
                if t.velocity_stats and t.note_count > 0:
                    # Approximate by using stats
                    all_velocities.extend([t.velocity_stats.mean] * min(t.note_count, 100))
        
        if all_velocities:
            sorted_vels = sorted(all_velocities)
            n = len(sorted_vels)
            def percentile(p):
                k = (n - 1) * p / 100
                f = int(k)
                c = min(f + 1, n - 1)
                return sorted_vels[f] + (sorted_vels[c] - sorted_vels[f]) * (k - f)
            
            report.velocity_stats = {
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
    
    # Determine validation result
    if (report.readable_styles == EXPECTED_STYLE_COUNT and 
        report.failed_styles == 0 and 
        report.duplicates == 0):
        report.validation_result = "PASS"
    else:
        issues = []
        if report.readable_styles != EXPECTED_STYLE_COUNT:
            issues.append(f"Expected {EXPECTED_STYLE_COUNT}, got {report.readable_styles}")
        if report.failed_styles > 0:
            issues.append(f"{report.failed_styles} failed")
        if report.duplicates > 0:
            issues.append(f"{report.duplicates} duplicates")
        report.validation_result = f"FAIL: {'; '.join(issues)}"
    
    return report


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("KORG PA800 FACTORY INTELLIGENCE — PHASE 1")
    print("=" * 60)
    print(f"\nCanonical directory: {CANONICAL_FACTORY_DIR}")
    print(f"Expected styles: {EXPECTED_STYLE_COUNT}")
    print("\nStarting analysis...\n")
    
    # Run analysis
    report = run_full_analysis()
    
    # Generate reports
    generate_json_report(report)
    generate_summary_report(report)
    
    # Print summary
    print_validation_summary(report)
    
    return 0 if report.validation_result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
