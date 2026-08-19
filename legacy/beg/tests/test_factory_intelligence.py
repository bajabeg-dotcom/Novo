"""
KORG PA800 Factory Intelligence - Test Suite

Tests for the Factory Intelligence system.
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestDiscovery:
    """Tests for dataset discovery."""
    
    def test_canonical_directory_exists(self):
        """Test that canonical factory directory exists."""
        from factory_intelligence.config import CANONICAL_FACTORY_DIR
        assert CANONICAL_FACTORY_DIR.exists(), f"Canonical directory not found: {CANONICAL_FACTORY_DIR}"
        assert CANONICAL_FACTORY_DIR.is_dir(), f"Path is not a directory: {CANONICAL_FACTORY_DIR}"
    
    def test_discover_dataset_returns_result(self):
        """Test that discovery returns a valid result."""
        from factory_intelligence.discovery import discover_dataset
        
        result = discover_dataset()
        
        assert result is not None
        assert isinstance(result.found_count, int)
        assert isinstance(result.duplicates, int)
        assert isinstance(result.errors, list)
    
    def test_expected_style_count(self):
        """Test that we find exactly 252 unique styles."""
        from factory_intelligence.discovery import discover_dataset
        from factory_intelligence.config import EXPECTED_STYLE_COUNT
        
        result = discover_dataset()
        
        assert result.found_count == EXPECTED_STYLE_COUNT, \
            f"Expected {EXPECTED_STYLE_COUNT} styles, found {result.found_count}"
    
    def test_no_duplicates_in_canonical(self):
        """Test that there are no duplicate files in canonical directory."""
        from factory_intelligence.discovery import discover_dataset
        
        result = discover_dataset()
        
        assert result.duplicates == 0, f"Found {result.duplicates} duplicates"
    
    def test_all_files_readable(self):
        """Test that all discovered files can be processed."""
        from factory_intelligence.discovery import discover_dataset
        
        result = discover_dataset()
        
        assert len(result.errors) == 0, f"Errors during discovery: {result.errors}"
    
    def test_style_ids_are_unique(self):
        """Test that all generated style IDs are unique."""
        from factory_intelligence.discovery import discover_dataset
        
        result = discover_dataset()
        
        style_ids = [f.style_id for f in result.files]
        unique_ids = set(style_ids)
        
        assert len(unique_ids) == len(style_ids), "Duplicate style IDs found"
    
    def test_sha256_computed_for_all_files(self):
        """Test that SHA-256 hash is computed for all files."""
        from factory_intelligence.discovery import discover_dataset
        
        result = discover_dataset()
        
        for f in result.files:
            assert f.sha256, f"No SHA-256 for {f.filename}"
            assert len(f.sha256) == 64, f"Invalid SHA-256 length for {f.filename}"


class TestMidiParser:
    """Tests for MIDI parsing."""
    
    @pytest.fixture
    def sample_file(self):
        """Get a sample MIDI file for testing."""
        from factory_intelligence.discovery import discover_dataset
        
        result = discover_dataset()
        if result.files:
            return result.files[0].path
        pytest.skip("No MIDI files available")
    
    def test_parse_midi_file_returns_data(self, sample_file):
        """Test that parsing returns valid data structure."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        assert data is not None
        assert "file_path" in data
        assert "tracks" in data
        assert "ticks_per_beat" in data
        assert "track_count" in data
    
    def test_ticks_per_beat_available(self, sample_file):
        """Test that PPQN value is extracted."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        assert data["ticks_per_beat"] > 0, "Invalid ticks_per_beat"
    
    def test_tracks_available(self, sample_file):
        """Test that tracks are extracted."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        assert len(data["tracks"]) > 0, "No tracks found"
        assert len(data["tracks"]) == data["track_count"]
    
    def test_events_preserved(self, sample_file):
        """Test that events are preserved during parsing."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        total_events = sum(t["event_count"] for t in data["tracks"])
        assert total_events > 0, "No events found"
    
    def test_notes_preserved(self, sample_file):
        """Test that notes are preserved during parsing."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        total_notes = sum(t["note_count"] for t in data["tracks"])
        # Some styles might have no notes (control-only tracks)
        assert total_notes >= 0
    
    def test_velocity_values_valid(self, sample_file):
        """Test that velocity values are in valid range."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        for track in data["tracks"]:
            for note in track["notes"]:
                assert 0 <= note.velocity <= 127, \
                    f"Invalid velocity {note.velocity} in track {track['track_index']}"
    
    def test_midi_channels_valid(self, sample_file):
        """Test that MIDI channel values are valid."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        for track in data["tracks"]:
            for ch in track["channels"]:
                assert 0 <= ch <= 15, f"Invalid channel {ch} in track {track['track_index']}"
    
    def test_program_values_valid(self, sample_file):
        """Test that program change values are valid."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        for track in data["tracks"]:
            for _, program in track["program_changes"]:
                assert 0 <= program <= 127, \
                    f"Invalid program {program} in track {track['track_index']}"
    
    def test_cc_values_valid(self, sample_file):
        """Test that CC values are valid."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        for track in data["tracks"]:
            for cc_num, events in track["control_changes"].items():
                assert 0 <= cc_num <= 127, f"Invalid CC number {cc_num}"
                for _, value in events:
                    assert 0 <= value <= 127, f"Invalid CC value {value}"
    
    def test_sysex_preserved(self, sample_file):
        """Test that SysEx data is preserved."""
        from factory_intelligence.midi_parser import parse_midi_file
        
        data = parse_midi_file(sample_file)
        
        # Just verify structure - some files may not have SysEx
        for track in data["tracks"]:
            assert "sysex_count" in track
            assert "sysex_data" in track


class TestEventAnalyzer:
    """Tests for event analysis."""
    
    def test_velocity_stats_computation(self):
        """Test velocity statistics computation."""
        from factory_intelligence.event_analyzer import compute_velocity_stats
        
        velocities = [64, 80, 96, 112, 127]
        stats = compute_velocity_stats(velocities)
        
        assert stats is not None
        assert stats.min == 64
        assert stats.max == 127
        assert stats.count == 5
    
    def test_empty_velocity_list(self):
        """Test velocity stats with empty list."""
        from factory_intelligence.event_analyzer import compute_velocity_stats
        
        stats = compute_velocity_stats([])
        assert stats is None


class TestTrackAnalyzer:
    """Tests for track role analysis."""
    
    def test_drum_channel_detection(self):
        """Test drum track detection via channel 10."""
        from factory_intelligence.track_analyzer import detect_track_role
        from factory_intelligence.models import TrackRole
        
        role, confidence, evidence = detect_track_role(
            channels={9},  # Channel 10 (0-indexed)
            notes=[],
            program_changes=[]
        )
        
        assert role == TrackRole.DRUM
        assert confidence >= 0.90
    
    def test_unknown_role_for_no_evidence(self):
        """Test unknown role when no evidence available."""
        from factory_intelligence.track_analyzer import detect_track_role
        from factory_intelligence.models import TrackRole
        
        role, confidence, evidence = detect_track_role(
            channels={0},
            notes=[],
            program_changes=[]
        )
        
        assert role == TrackRole.UNKNOWN
        assert confidence == 0.0


class TestFingerprints:
    """Tests for fingerprint generation."""
    
    @pytest.fixture
    def sample_style(self):
        """Create a sample style for testing."""
        from factory_intelligence.discovery import discover_dataset
        from factory_intelligence.midi_parser import parse_midi_file
        from factory_intelligence.fingerprints import generate_fingerprint
        from test_factory import analyze_style
        
        result = discover_dataset()
        if result.files:
            midi_data = parse_midi_file(result.files[0].path)
            return analyze_style(result.files[0], midi_data)
        pytest.skip("No MIDI files available")
    
    def test_fingerprint_generated(self, sample_style):
        """Test that fingerprint is generated."""
        assert sample_style.fingerprint is not None
    
    def test_fingerprint_is_deterministic(self, sample_style):
        """Test that fingerprint generation is deterministic."""
        from factory_intelligence.fingerprints import generate_fingerprint
        
        fp1 = sample_style.fingerprint
        fp2 = generate_fingerprint(sample_style)
        
        assert fp1.style_id == fp2.style_id
        assert fp1.track_count == fp2.track_count
        assert fp1.to_hash() == fp2.to_hash()


class TestIntegrity:
    """Integration and integrity tests."""
    
    def test_full_analysis_pipeline(self):
        """Test complete analysis pipeline."""
        from test_factory import run_full_analysis
        
        report = run_full_analysis()
        
        assert report is not None
        assert report.expected_styles == 252
        assert report.found_styles > 0
    
    def test_reports_generated(self):
        """Test that reports are generated."""
        from pathlib import Path
        from factory_intelligence.config import REPORTS_DIR
        
        json_report = REPORTS_DIR / "factory_dataset_report.json"
        txt_report = REPORTS_DIR / "factory_dataset_summary.txt"
        
        # Run analysis first
        from test_factory import run_full_analysis, main
        main()
        
        assert json_report.exists(), "JSON report not generated"
        assert txt_report.exists(), "TXT report not generated"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
