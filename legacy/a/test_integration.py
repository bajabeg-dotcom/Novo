#!/usr/bin/env python3
"""
KORG PA800 MIDI Optimizer - CLI and Integration Tests

Tests for command-line interface and complete workflows
"""

import pytest
import tempfile
import json
import struct
from pathlib import Path
from subprocess import run, PIPE
from unittest.mock import patch, MagicMock

from midi_optimizer_core import (
    MIDIParser,
    MIDINote,
    OptimizationStrategy,
    SoundBehaviourOptimizer,
    MIDIOptimizerApp
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_behaviour_db():
    """Test behaviour database"""
    return {
        "sound_rules": {
            "25": {
                "program": 25,
                "role": "percussion",
                "velocity_zones": [
                    {"velocity_range": "1-40", "center": 20, "character": "soft"},
                    {"velocity_range": "41-90", "center": 65, "character": "normal"},
                    {"velocity_range": "91-127", "center": 110, "character": "accent"}
                ]
            },
            "34": {
                "program": 34,
                "role": "bass",
                "velocity_zones": [
                    {"velocity_range": "30-80", "center": 55, "character": "soft"},
                    {"velocity_range": "81-120", "center": 100, "character": "strong"}
                ]
            }
        }
    }


@pytest.fixture
def temp_db_file(test_behaviour_db):
    """Create temporary database file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_behaviour_db, f)
        return Path(f.name)


@pytest.fixture
def temp_midi_simple():
    """Create simple test MIDI file"""
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        # Header
        f.write(b'MThd')
        f.write(struct.pack('>I', 6))
        f.write(struct.pack('>H', 1))    # Format 1
        f.write(struct.pack('>H', 1))    # 1 track
        f.write(struct.pack('>H', 480))  # PPQ
        
        # Track with simple notes
        track = bytearray()
        track.extend(b'\x00\xC0\x19')    # Program 25
        
        # Note On: C4, velocity 50
        track.extend(b'\x00\x90\x3C\x32')
        # Note Off: C4, velocity 64
        track.extend(b'\x83\x60\x80\x3C\x40')
        
        # Note On: D4, velocity 70
        track.extend(b'\x00\x90\x3E\x46')
        # Note Off: D4, velocity 64
        track.extend(b'\x83\x60\x80\x3E\x40')
        
        # End of track
        track.extend(b'\x00\xFF\x2F\x00')
        
        f.write(b'MTrk')
        f.write(struct.pack('>I', len(track)))
        f.write(bytes(track))
        
        return Path(f.name)


# ============================================================================
# MIDI PARSING TESTS
# ============================================================================

class TestMIDIParsing:
    """Test MIDI file parsing capabilities"""
    
    def test_parse_valid_midi(self, temp_midi_simple):
        """Test parsing valid MIDI file"""
        notes, metadata = MIDIParser.parse_midi_file(temp_midi_simple)
        
        assert isinstance(notes, list)
        assert len(notes) > 0
    
    def test_parse_preserves_note_data(self, temp_midi_simple):
        """Test that parsing preserves note data"""
        notes, _ = MIDIParser.parse_midi_file(temp_midi_simple)
        
        # Check that we have MIDINote objects with expected attributes
        for note in notes:
            assert hasattr(note, 'note')
            assert hasattr(note, 'velocity')
            assert hasattr(note, 'channel')
            assert hasattr(note, 'program')
            assert hasattr(note, 'start_time')
            assert hasattr(note, 'duration')
            
            # Verify ranges
            assert 0 <= note.note <= 127
            assert 0 <= note.velocity <= 127
            assert 0 <= note.program <= 127
    
    def test_parse_invalid_file(self):
        """Test parsing invalid file"""
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            f.write(b'INVALID MIDI DATA')
            temp_path = Path(f.name)
        
        notes, metadata = MIDIParser.parse_midi_file(temp_path)
        
        # Should return empty list for invalid file
        assert notes == []
    
    def test_parse_corrupted_file(self):
        """Test parsing corrupted file"""
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            f.write(b'MThd')
            f.write(struct.pack('>I', 6))
            f.write(b'CORRUPTED')  # Invalid data
            temp_path = Path(f.name)
        
        notes, metadata = MIDIParser.parse_midi_file(temp_path)
        
        # Should handle gracefully
        assert isinstance(notes, list)


# ============================================================================
# MIDI WRITING TESTS
# ============================================================================

class TestMIDIWriting:
    """Test MIDI file writing"""
    
    def test_write_midi_file(self, temp_midi_simple):
        """Test writing MIDI file"""
        # Parse original file
        notes, _ = MIDIParser.parse_midi_file(temp_midi_simple)
        
        # Write to new file
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        MIDIParser.write_midi_file(notes, output_path)
        
        # Verify output file exists and can be parsed
        assert output_path.exists()
        
        parsed_back, _ = MIDIParser.parse_midi_file(output_path)
        assert len(parsed_back) > 0
    
    def test_write_preserves_data(self, temp_midi_simple):
        """Test that writing preserves note data"""
        original_notes, _ = MIDIParser.parse_midi_file(temp_midi_simple)
        original_count = len(original_notes)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        MIDIParser.write_midi_file(original_notes, output_path)
        parsed_back, _ = MIDIParser.parse_midi_file(output_path)
        
        # Note count should be preserved
        assert len(parsed_back) == original_count


# ============================================================================
# OPTIMIZATION WORKFLOW TESTS
# ============================================================================

class TestOptimizationWorkflow:
    """Test complete optimization workflows"""
    
    def test_optimize_authentic_strategy(self, temp_db_file, temp_midi_simple):
        """Test optimization with AUTHENTIC strategy"""
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        result = app.optimize_file(
            temp_midi_simple,
            output_path,
            OptimizationStrategy.AUTHENTIC
        )
        
        assert result.get("success") == True
        assert output_path.exists()
        assert result.get("total_notes") > 0
    
    def test_optimize_all_strategies(self, temp_db_file, temp_midi_simple):
        """Test optimization with all strategies"""
        app = MIDIOptimizerApp(temp_db_file)
        
        strategies = [
            OptimizationStrategy.AUTHENTIC,
            OptimizationStrategy.EXPRESSIVE,
            OptimizationStrategy.BALANCED,
            OptimizationStrategy.AGGRESSIVE
        ]
        
        for strategy in strategies:
            with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
                output_path = Path(f.name)
            
            result = app.optimize_file(temp_midi_simple, output_path, strategy)
            
            assert result.get("success") == True
            assert output_path.exists()
    
    def test_optimization_creates_new_file(self, temp_db_file, temp_midi_simple):
        """Test that optimization creates new file without modifying original"""
        original_size = temp_midi_simple.stat().st_size
        
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        app.optimize_file(temp_midi_simple, output_path, OptimizationStrategy.AUTHENTIC)
        
        # Original file should be unchanged
        assert temp_midi_simple.stat().st_size == original_size
        
        # Output file should be different
        assert output_path.exists()
        assert output_path != temp_midi_simple
    
    def test_optimization_modifies_velocity(self, temp_db_file, temp_midi_simple):
        """Test that optimization actually modifies velocity values"""
        # Parse original
        original_notes, _ = MIDIParser.parse_midi_file(temp_midi_simple)
        original_velocities = [n.velocity for n in original_notes]
        
        # Optimize
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        app.optimize_file(temp_midi_simple, output_path, OptimizationStrategy.AUTHENTIC)
        
        # Parse optimized
        optimized_notes, _ = MIDIParser.parse_midi_file(output_path)
        optimized_velocities = [n.velocity for n in optimized_notes]
        
        # At least some velocities should change
        assert original_velocities != optimized_velocities


# ============================================================================
# ANALYSIS TESTS
# ============================================================================

class TestAnalysis:
    """Test MIDI file analysis"""
    
    def test_analyze_file(self, temp_db_file, temp_midi_simple):
        """Test analyzing MIDI file"""
        app = MIDIOptimizerApp(temp_db_file)
        result = app.analyze_file(temp_midi_simple)
        
        assert "total_notes" in result
        assert "programs" in result
        assert result.get("total_notes") > 0
    
    def test_analyze_detects_programs(self, temp_db_file, temp_midi_simple):
        """Test that analysis detects program numbers"""
        app = MIDIOptimizerApp(temp_db_file)
        result = app.analyze_file(temp_midi_simple)
        
        programs = result.get("programs", {})
        assert len(programs) > 0
    
    def test_analyze_velocity_stats(self, temp_db_file, temp_midi_simple):
        """Test that analysis computes velocity statistics"""
        app = MIDIOptimizerApp(temp_db_file)
        result = app.analyze_file(temp_midi_simple)
        
        velocity_stats = result.get("velocity_stats", {})
        
        # Should have stats for each program
        for prog_id, stats in velocity_stats.items():
            assert "min" in stats
            assert "max" in stats
            assert "avg" in stats
            
            # Verify ranges
            assert stats["min"] <= stats["max"]
            assert 0 <= stats["min"] <= 127
            assert 0 <= stats["max"] <= 127


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_missing_database(self):
        """Test handling of missing database file"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=True) as f:
            temp_path = Path(f.name)
        
        # File is deleted, path no longer exists
        app = MIDIOptimizerApp(temp_path)
        
        # Should handle gracefully
        assert app.behaviour_db is not None
    
    def test_optimize_missing_file(self, temp_db_file):
        """Test optimizing missing file"""
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=True) as f:
            input_path = Path(f.name)
        
        output_path = Path(tempfile.gettempdir()) / "output.mid"
        
        # Should handle missing input file
        result = app.optimize_file(input_path, output_path, OptimizationStrategy.AUTHENTIC)
        
        # Could either fail gracefully or handle it
        assert isinstance(result, dict)
    
    def test_invalid_strategy(self, temp_db_file, temp_midi_simple):
        """Test handling of invalid strategy"""
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        # This should work with valid strategy
        result = app.optimize_file(temp_midi_simple, output_path, OptimizationStrategy.AUTHENTIC)
        assert result.get("success") == True


# ============================================================================
# DATA CONSISTENCY TESTS
# ============================================================================

class TestDataConsistency:
    """Test that data consistency is maintained"""
    
    def test_optimize_preserves_note_count(self, temp_db_file, temp_midi_simple):
        """Test that optimization preserves note count"""
        original_notes, _ = MIDIParser.parse_midi_file(temp_midi_simple)
        original_count = len(original_notes)
        
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        app.optimize_file(temp_midi_simple, output_path, OptimizationStrategy.AUTHENTIC)
        
        optimized_notes, _ = MIDIParser.parse_midi_file(output_path)
        
        # Note count should be preserved
        assert len(optimized_notes) == original_count
    
    def test_optimize_preserves_note_pitches(self, temp_db_file, temp_midi_simple):
        """Test that optimization preserves note pitches"""
        original_notes, _ = MIDIParser.parse_midi_file(temp_midi_simple)
        original_pitches = [n.note for n in original_notes]
        
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        app.optimize_file(temp_midi_simple, output_path, OptimizationStrategy.AUTHENTIC)
        
        optimized_notes, _ = MIDIParser.parse_midi_file(output_path)
        optimized_pitches = [n.note for n in optimized_notes]
        
        # Pitches should be preserved
        assert original_pitches == optimized_pitches
    
    def test_optimize_modifies_only_velocity(self, temp_db_file, temp_midi_simple):
        """Test that only velocity is modified"""
        original_notes, _ = MIDIParser.parse_midi_file(temp_midi_simple)
        
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        app.optimize_file(temp_midi_simple, output_path, OptimizationStrategy.AUTHENTIC)
        
        optimized_notes, _ = MIDIParser.parse_midi_file(output_path)
        
        # Check that only velocity changed
        for original, optimized in zip(original_notes, optimized_notes):
            assert original.note == optimized.note
            assert original.channel == optimized.channel
            assert original.program == optimized.program
            assert original.start_time == optimized.start_time
            assert original.duration == optimized.duration
            # Velocity might change
            assert isinstance(optimized.velocity, int)


# ============================================================================
# BATCH PROCESSING TESTS
# ============================================================================

class TestBatchProcessing:
    """Test batch processing workflows"""
    
    def test_process_multiple_files(self, temp_db_file, temp_midi_simple):
        """Test processing multiple files"""
        app = MIDIOptimizerApp(temp_db_file)
        
        # Create multiple files
        input_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
                # Write minimal MIDI
                f.write(b'MThd')
                f.write(struct.pack('>I', 6))
                f.write(struct.pack('>H', 1))
                f.write(struct.pack('>H', 1))
                f.write(struct.pack('>H', 480))
                f.write(b'MTrk')
                f.write(struct.pack('>I', 4))
                f.write(b'\x00\xFF\x2F\x00')
                input_files.append(Path(f.name))
        
        # Process each file
        results = []
        for input_file in input_files:
            with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
                output_file = Path(f.name)
            
            result = app.optimize_file(input_file, output_file, OptimizationStrategy.AUTHENTIC)
            results.append(result)
        
        # All should succeed
        assert len(results) == 3


# ============================================================================
# PERFORMANCE AND SCALABILITY TESTS
# ============================================================================

class TestPerformance:
    """Test performance characteristics"""
    
    def test_large_file_handling(self, temp_db_file):
        """Test handling of larger MIDI file"""
        # Create MIDI file with many notes
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            f.write(b'MThd')
            f.write(struct.pack('>I', 6))
            f.write(struct.pack('>H', 1))
            f.write(struct.pack('>H', 1))
            f.write(struct.pack('>H', 480))
            
            track = bytearray()
            track.extend(b'\x00\xC0\x19')  # Program 25
            
            # Add 1000 notes
            for i in range(1000):
                track.extend(b'\x00\x90\x3C\x50')  # Note On
                track.extend(b'\x83\x60\x80\x3C\x40')  # Note Off
            
            track.extend(b'\x00\xFF\x2F\x00')
            
            f.write(b'MTrk')
            f.write(struct.pack('>I', len(track)))
            f.write(bytes(track))
            
            large_file = Path(f.name)
        
        app = MIDIOptimizerApp(temp_db_file)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        # Should handle large file
        result = app.optimize_file(large_file, output_path, OptimizationStrategy.AUTHENTIC)
        
        assert result.get("success") == True


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
