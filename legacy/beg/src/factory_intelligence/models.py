"""
KORG PA800 Factory Intelligence - Data Models

This module defines the data structures for representing Factory Style MIDI analysis results.
All models use explicit terminology to distinguish between OBSERVED, DERIVED, HEURISTIC, and UNKNOWN data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceType(Enum):
    """Type of evidence for a claim."""
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    HEURISTIC = "HEURISTIC"
    UNKNOWN = "UNKNOWN"


class TrackRole(Enum):
    """Possible track roles in a Factory Style."""
    DRUM = "DRUM"
    PERCUSSION = "PERCUSSION"
    BASS = "BASS"
    GUITAR = "GUITAR"
    KEYBOARD = "KEYBOARD"
    PAD = "PAD"
    STRING = "STRING"
    BRASS = "BRASS"
    WIND = "WIND"
    MELODIC = "MELODIC"
    UNKNOWN = "UNKNOWN"


class SectionType(Enum):
    """Possible section types in a Factory Style."""
    INTRO = "INTRO"
    VARIATION_A = "VARIATION_A"
    VARIATION_B = "VARIATION_B"
    VARIATION_C = "VARIATION_C"
    VARIATION_D = "VARIATION_D"
    FILL = "FILL"
    BREAK = "BREAK"
    ENDING = "ENDING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MidiEvent:
    """Represents a single MIDI event."""
    absolute_tick: int
    delta_tick: int
    event_type: str
    channel: int | None = None
    note: int | None = None
    velocity: int | None = None
    data: tuple[int, ...] = field(default_factory=tuple)
    raw_bytes: bytes = field(default_factory=bytes)
    
    def is_note_on(self) -> bool:
        return self.event_type == "note_on"
    
    def is_note_off(self) -> bool:
        return self.event_type == "note_off"
    
    def is_control_change(self) -> bool:
        return self.event_type == "control_change"
    
    def is_program_change(self) -> bool:
        return self.event_type == "program_change"
    
    def is_pitch_wheel(self) -> bool:
        return self.event_type == "pitchwheel"
    
    def is_sysex(self) -> bool:
        return self.event_type == "sysex"


@dataclass(frozen=True)
class NoteEvent:
    """Represents a complete note (on + off pair)."""
    absolute_tick: int
    delta_tick: int
    channel: int
    note: int
    velocity: int
    duration_ticks: int
    end_tick: int
    
    @property
    def pitch_class(self) -> int:
        return self.note % 12
    
    @property
    def octave(self) -> int:
        return (self.note // 12) - 1


@dataclass(frozen=True)
class VelocityStats:
    """Velocity statistics for a track or style."""
    min: int
    max: int
    mean: float
    median: float
    std: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    count: int


@dataclass(frozen=True)
class TimingStats:
    """Timing statistics for a track or style."""
    min_delta_tick: int
    max_delta_tick: int
    mean_delta_tick: float
    median_delta_tick: float
    total_ticks: int
    event_count: int


@dataclass
class ControlChangeStats:
    """Statistics for control changes."""
    cc_number: int
    count: int
    values: list[int] = field(default_factory=list)
    
    @property
    def mean_value(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)


@dataclass(frozen=True)
class SysExEvent:
    """Represents a System Exclusive event."""
    track_index: int
    absolute_tick: int
    length: int
    manufacturer_id: bytes
    raw_hex: str
    device_id: bytes | None = None
    command: bytes | None = None
    subcommand: bytes | None = None
    payload: bytes | None = None
    
    @property
    def is_korg(self) -> bool:
        """Check if this is a KORG SysEx (manufacturer ID 0x42)."""
        return len(self.manufacturer_id) >= 1 and self.manufacturer_id[0] == 0x42


@dataclass
class TrackAnalysis:
    """Analysis results for a single track."""
    track_index: int
    track_name: str | None
    event_count: int
    note_count: int
    channels: set[int]
    program_changes: list[tuple[int, int]]  # (tick, program)
    control_changes: dict[int, list[tuple[int, int]]]  # cc_number -> [(tick, value)]
    pitch_bends: list[tuple[int, int]]  # (tick, value)
    aftertouch_count: int
    polytouch_count: int
    sysex_count: int
    meta_events: list[tuple[str, Any]]
    absolute_tick_length: int
    
    # Derived statistics
    velocity_stats: VelocityStats | None = None
    timing_stats: TimingStats | None = None
    notes: list[NoteEvent] = field(default_factory=list)
    
    # Role analysis
    role: TrackRole = TrackRole.UNKNOWN
    role_confidence: float = 0.0
    role_evidence: list[str] = field(default_factory=list)


@dataclass
class PatternCandidate:
    """A candidate pattern detected in a track."""
    start_tick: int
    end_tick: int
    length_ticks: int
    length_beats: float
    length_bars: float
    confidence: float
    evidence: list[str] = field(default_factory=list)
    source_type: str = "HEURISTIC"


@dataclass
class SectionCandidate:
    """A candidate section detected in a style."""
    section_type: SectionType
    start_tick: int
    end_tick: int
    confidence: float
    evidence: list[str] = field(default_factory=list)
    source_type: str = "HEURISTIC"


@dataclass(frozen=True)
class StyleFingerprint:
    """Deterministic fingerprint for a Factory Style."""
    style_id: str
    track_count: int
    event_count: int
    note_count: int
    channel_distribution: tuple[int, ...]  # count per channel 0-15
    velocity_distribution: tuple[float, ...]  # histogram buckets
    pitch_distribution: tuple[int, ...]  # count per pitch class 0-11
    duration_distribution: tuple[float, ...]  # histogram buckets
    rhythmic_density: float
    timing_density: float
    program_distribution: tuple[int, ...]  # count per program 0-127
    cc_distribution: tuple[int, ...]  # count per CC number 0-127
    sysex_signature: str  # hash of sysex content
    pattern_lengths: tuple[int, ...]
    
    def to_hash(self) -> str:
        """Generate a deterministic hash string."""
        import hashlib
        data = f"{self.style_id}:{self.track_count}:{self.event_count}:{self.note_count}"
        data += f":{','.join(map(str, self.channel_distribution))}"
        data += f":{','.join(map(str, self.program_distribution))}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class FactoryStyle:
    """Complete analysis of a Factory Style."""
    file_path: str
    filename: str
    style_id: str
    sha256: str
    
    # MIDI file properties
    midi_type: int  # 0, 1, or 2
    ticks_per_beat: int
    track_count: int
    duration_ticks: int
    tempo_bpm: float | None
    
    # Track analyses
    tracks: list[TrackAnalysis] = field(default_factory=list)
    
    # Pattern and section candidates
    patterns: list[PatternCandidate] = field(default_factory=list)
    sections: list[SectionCandidate] = field(default_factory=list)
    
    # Fingerprint
    fingerprint: StyleFingerprint | None = None
    
    # SysEx events
    sysex_events: list[SysExEvent] = field(default_factory=list)


@dataclass
class DatasetReport:
    """Complete report for the Factory dataset."""
    expected_styles: int
    found_styles: int
    readable_styles: int
    failed_styles: int
    duplicates: int
    
    styles: list[FactoryStyle] = field(default_factory=list)
    
    # Aggregate statistics
    total_tracks: int = 0
    total_notes: int = 0
    total_events: int = 0
    
    track_count_stats: dict[str, float] = field(default_factory=dict)
    velocity_stats: dict[str, float] = field(default_factory=dict)
    ppqn_distribution: dict[int, int] = field(default_factory=dict)
    midi_type_distribution: dict[int, int] = field(default_factory=dict)
    channel_distribution: dict[int, int] = field(default_factory=dict)
    program_distribution: dict[int, int] = field(default_factory=dict)
    cc_distribution: dict[int, int] = field(default_factory=dict)
    sysex_count: int = 0
    
    pattern_count: int = 0
    section_candidate_count: int = 0
    
    validation_result: str = "PENDING"
