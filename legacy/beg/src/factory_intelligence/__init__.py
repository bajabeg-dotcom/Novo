"""
KORG PA800 Factory Intelligence Package

Factory Style MIDI analysis layer for KORG PA800 arranger workstation.
"""

from .models import (
    EvidenceType,
    TrackRole,
    SectionType,
    MidiEvent,
    NoteEvent,
    VelocityStats,
    TimingStats,
    ControlChangeStats,
    SysExEvent,
    TrackAnalysis,
    PatternCandidate,
    SectionCandidate,
    StyleFingerprint,
    FactoryStyle,
    DatasetReport
)

from .discovery import (
    discover_dataset,
    validate_dataset,
    DiscoveredFile,
    DiscoveryResult
)

from .midi_parser import (
    parse_midi_file,
    parse_midi_events,
    extract_track_name,
    get_tempo_bpm
)

from .event_analyzer import (
    compute_velocity_stats,
    compute_timing_stats,
    analyze_notes,
    analyze_control_changes,
    analyze_program_changes,
    analyze_sysex
)

from .track_analyzer import (
    detect_track_role,
    analyze_track_rhythm,
    compute_track_density
)

from .pattern_analyzer import (
    find_pattern_candidates,
    find_section_candidates,
    analyze_periodicity
)

from .fingerprints import (
    generate_fingerprint
)

from .statistics import (
    compute_aggregate_statistics,
    compute_note_range_statistics,
    compute_rhythmic_density_statistics
)

from .reporter import (
    generate_json_report,
    generate_summary_report,
    print_validation_summary
)


__version__ = "0.1.0"
__all__ = [
    # Models
    "EvidenceType",
    "TrackRole",
    "SectionType",
    "MidiEvent",
    "NoteEvent",
    "VelocityStats",
    "TimingStats",
    "ControlChangeStats",
    "SysExEvent",
    "TrackAnalysis",
    "PatternCandidate",
    "SectionCandidate",
    "StyleFingerprint",
    "FactoryStyle",
    "DatasetReport",
    
    # Discovery
    "discover_dataset",
    "validate_dataset",
    "DiscoveredFile",
    "DiscoveryResult",
    
    # Parser
    "parse_midi_file",
    "parse_midi_events",
    "extract_track_name",
    "get_tempo_bpm",
    
    # Event Analysis
    "compute_velocity_stats",
    "compute_timing_stats",
    "analyze_notes",
    "analyze_control_changes",
    "analyze_program_changes",
    "analyze_sysex",
    
    # Track Analysis
    "detect_track_role",
    "analyze_track_rhythm",
    "compute_track_density",
    
    # Pattern Analysis
    "find_pattern_candidates",
    "find_section_candidates",
    "analyze_periodicity",
    
    # Fingerprints
    "generate_fingerprint",
    
    # Statistics
    "compute_aggregate_statistics",
    "compute_note_range_statistics",
    "compute_rhythmic_density_statistics",
    
    # Reporting
    "generate_json_report",
    "generate_summary_report",
    "print_validation_summary",
]
