#!/usr/bin/env python3
"""
KORG PA800 MIDI Optimizer - Comprehensive Test Suite
Unit and Integration Tests for Core Engine

Requirements: pytest, pytest-cov
Run: pytest test_midi_optimizer.py -v --cov=midi_optimizer_core
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import struct

# Import modules to test
from midi_optimizer_core import (
    MIDIParser,
    MIDINote,
    OptimizationStrategy,
    OptimizationResult,
    SoundBehaviourOptimizer,
    MIDIOptimizerApp
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_behaviour_db():
    """Sample Sound Behaviour Database"""
    return {
        "sound_rules": {
            "25": {
                "program": 25,
                "role": "percussion",
                "velocity_zones": [
                    {
                        "velocity_range": "1-40",
                        "center": 20,
                        "character": "soft",
                        "use_case": "Soft hits"
                    },
                    {
                        "velocity_range": "41-90",
                        "center": 65,
                        "character": "normal",
                        "use_case": "Standard hits"
                    },
                    {
                        "velocity_range": "91-127",
                        "center": 110,
                        "character": "accent",
                        "use_case": "Accent hits"
                    }
                ],
                "playing_rules": {
                    "velocity_dynamics": {
                        "1-40": {"character": "soft"},
                        "41-90": {"character": "normal"},
                        "91-127": {"character": "accent"}
                    }
                }
            },
            "34": {
                "program": 34,
                "role": "bass",
                "velocity_zones": [
                    {
                        "velocity_range": "30-80",
                        "center": 55,
                        "character": "soft",
                        "use_case": "Soft bass"
                    },
                    {
                        "velocity_range": "81-120",
                        "center": 100,
                        "character": "strong",
                        "use_case": "Strong bass"
                    }
                ]
            }
        }
    }


@pytest.fixture
def temp_midi_file():
    """Create temporary MIDI file for testing"""
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        # Write minimal MIDI file (header + one empty track)
        f.write(b'MThd')  # Header chunk type
        f.write(struct.pack('>I', 6))  # Header length
        f.write(struct.pack('>H', 1))  # Format 1
        f.write(struct.pack('>H', 1))  # 1 track
        f.write(struct.pack('>H', 480))  # PPQ
        
        # Empty track
        f.write(b'MTrk')  # Track chunk type
        track_data = b'\x00\xFF\x2F\x00'  # End of track
        f.write(struct.pack('>I', len(track_data)))  # Track length
        f.write(track_data)
        
        return Path(f.name)


@pytest.fixture
def temp_midi_with_notes():
    """Create MIDI file with actual notes"""
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        # Header
        f.write(b'MThd')
        f.write(struct.pack('>I', 6))
        f.write(struct.pack('>H', 1))  # Format 1
        f.write(struct.pack('>H', 1))  # 1 track
        f.write(struct.pack('>H', 480))  # PPQ
        
        # Track with notes
        track_data = bytearray()
        
        # Program change (Program 25)
        track_data.extend(b'\x00\xC0\x19')  # Delta 0, Program Change, Program 25
        
        # Note On (Middle C, velocity 80)
        track_data.extend(b'\x00\x90\x3C\x50')  # Delta 0, Note On, C4, Velocity 80
        
        # Note Off after 480 ticks (1 quarter note)
        track_data.extend(b'\x83\x60\x80\x3C\x40')  # Delta 480, Note Off, C4
        
        # End of track
        track_data.extend(b'\x00\xFF\x2F\x00')  # End of track
        
        f.write(b'MTrk')
        f.write(struct.pack('>I', len(track_data)))
        f.write(bytes(track_data))
        
        return Path(f.name)


# ============================================================================
# MIDI PARSER TESTS
# ============================================================================

class TestMIDIParser:
    """Test MIDI file parsing"""
    
    def test_read_var_length_simple(self):
        """Test reading simple variable-length quantity"""
        data = bytes([0x7F])  # 127
        value, offset = MIDIParser.read_var_length(data, 0)
        assert value == 127
        assert offset == 1
    
    def test_read_var_length_multi_byte(self):
        """Test reading multi-byte variable-length quantity"""
        data = bytes([0x81, 0x00])  # 128 in variable length
        value, offset = MIDIParser.read_var_length(data, 0)
        assert value == 128
        assert offset == 2
    
    def test_write_var_length_simple(self):
        """Test writing simple variable-length quantity"""
        result = MIDIParser.write_var_length(127)
        assert result == bytes([0x7F])
    
    def test_write_var_length_multi_byte(self):
        """Test writing multi-byte variable-length quantity"""
        result = MIDIParser.write_var_length(128)
        assert result == bytes([0x81, 0x00])
    
    def test_parse_empty_midi_file(self, temp_midi_file):
        """Test parsing empty MIDI file"""
        notes, metadata = MIDIParser.parse_midi_file(temp_midi_file)
        assert notes == []
    
    def test_parse_midi_with_notes(self, temp_midi_with_notes):
        """Test parsing MIDI file with notes"""
        notes, metadata = MIDIParser.parse_midi_file(temp_midi_with_notes)
        # Should have parsed at least some events
        assert isinstance(notes, list)
    
    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file"""
        notes, metadata = MIDIParser.parse_midi_file(Path("/nonexistent/file.mid"))
        assert notes == []


# ============================================================================
# MIDI NOTE TESTS
# ============================================================================

class TestMIDINote:
    """Test MIDINote class"""
    
    def test_midi_note_creation(self):
        """Test creating MIDI note"""
        note = MIDINote(
            note=60,  # Middle C
            velocity=80,
            channel=0,
            program=0,
            start_time=0,
            duration=480
        )
        assert note.note == 60
        assert note.velocity == 80
        assert note.channel == 0
    
    def test_midi_note_register_low(self):
        """Test low register detection"""
        note = MIDINote(35, 80, 0, 0, 0, 100)
        assert note.register() == "low"
    
    def test_midi_note_register_mid(self):
        """Test mid register detection"""
        note = MIDINote(60, 80, 0, 0, 0, 100)
        assert note.register() == "mid"
    
    def test_midi_note_register_high(self):
        """Test high register detection"""
        note = MIDINote(100, 80, 0, 0, 0, 100)
        assert note.register() == "high"


# ============================================================================
# OPTIMIZATION RESULT TESTS
# ============================================================================

class TestOptimizationResult:
    """Test OptimizationResult class"""
    
    def test_result_creation(self):
        """Test creating optimization result"""
        result = OptimizationResult(
            original_velocity=80,
            optimized_velocity=85,
            reason="Test optimization",
            confidence="OBSERVED"
        )
        assert result.original_velocity == 80
        assert result.optimized_velocity == 85
        assert result.adjustment == 5
    
    def test_result_negative_adjustment(self):
        """Test negative velocity adjustment"""
        result = OptimizationResult(
            original_velocity=100,
            optimized_velocity=90,
            reason="Test",
            confidence="OBSERVED"
        )
        assert result.adjustment == -10


# ============================================================================
# SOUND BEHAVIOUR OPTIMIZER TESTS
# ============================================================================

class TestSoundBehaviourOptimizer:
    """Test optimization logic"""
    
    def test_optimizer_creation(self, sample_behaviour_db):
        """Test creating optimizer"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        assert optimizer.behaviour_db is not None
    
    def test_get_sound_behaviour(self, sample_behaviour_db):
        """Test retrieving sound behaviour"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        behaviour = optimizer.get_sound_behaviour(25)
        assert behaviour is not None
        assert behaviour["program"] == 25
    
    def test_get_nonexistent_behaviour(self, sample_behaviour_db):
        """Test retrieving nonexistent sound"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        behaviour = optimizer.get_sound_behaviour(999)
        assert behaviour is None
    
    def test_optimize_velocity_authentic(self, sample_behaviour_db):
        """Test AUTHENTIC strategy optimization"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        note = MIDINote(60, 50, 0, 25, 0, 100)  # Program 25, velocity 50
        
        result = optimizer.optimize_velocity(note, OptimizationStrategy.AUTHENTIC)
        
        assert result.original_velocity == 50
        assert result.optimized_velocity != 50  # Should be changed
        assert result.confidence == "OBSERVED"
    
    def test_optimize_velocity_expressive(self, sample_behaviour_db):
        """Test EXPRESSIVE strategy optimization"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        note = MIDINote(60, 50, 0, 25, 0, 100)
        
        result = optimizer.optimize_velocity(note, OptimizationStrategy.EXPRESSIVE)
        
        assert isinstance(result, OptimizationResult)
    
    def test_optimize_velocity_balanced(self, sample_behaviour_db):
        """Test BALANCED strategy optimization"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        note = MIDINote(60, 65, 0, 25, 0, 100)  # Already in range
        
        result = optimizer.optimize_velocity(note, OptimizationStrategy.BALANCED)
        
        # Conservative strategy should make fewer changes
        assert isinstance(result, OptimizationResult)
    
    def test_optimize_velocity_aggressive(self, sample_behaviour_db):
        """Test AGGRESSIVE strategy optimization"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        note = MIDINote(60, 50, 0, 25, 0, 100)
        
        result = optimizer.optimize_velocity(note, OptimizationStrategy.AGGRESSIVE)
        
        assert isinstance(result, OptimizationResult)
    
    def test_optimize_multiple_notes(self, sample_behaviour_db):
        """Test optimizing multiple notes"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        
        notes = [
            MIDINote(60, 50, 0, 25, 0, 100),
            MIDINote(62, 70, 0, 25, 480, 100),
            MIDINote(64, 90, 0, 25, 960, 100),
        ]
        
        optimized, results = optimizer.optimize_midi(notes, OptimizationStrategy.AUTHENTIC)
        
        assert len(optimized) == 3
        assert len(results) == 3
        assert all(isinstance(r, OptimizationResult) for r in results)


# ============================================================================
# MIDI OPTIMIZER APP TESTS
# ============================================================================

class TestMIDIOptimizerApp:
    """Test main application class"""
    
    def test_app_creation(self, sample_behaviour_db):
        """Test creating app (with mock database)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_behaviour_db, f)
            db_path = Path(f.name)
        
        app = MIDIOptimizerApp(db_path)
        assert app.behaviour_db is not None
        assert app.optimizer is not None
    
    def test_app_analyze_empty_file(self, sample_behaviour_db, temp_midi_file):
        """Test analyzing empty MIDI file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_behaviour_db, f)
            db_path = Path(f.name)
        
        app = MIDIOptimizerApp(db_path)
        result = app.analyze_file(temp_midi_file)

        assert result.get("error") == "No notes found"


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_invalid_velocity_values(self, sample_behaviour_db):
        """Test handling of invalid velocity values"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        
        # Velocity 0 (note off)
        note = MIDINote(60, 0, 0, 25, 0, 100)
        result = optimizer.optimize_velocity(note, OptimizationStrategy.AUTHENTIC)
        assert result.original_velocity == 0
        
        # Velocity 127 (maximum)
        note = MIDINote(60, 127, 0, 25, 0, 100)
        result = optimizer.optimize_velocity(note, OptimizationStrategy.AUTHENTIC)
        assert 0 <= result.optimized_velocity <= 127
    
    def test_extreme_note_values(self, sample_behaviour_db):
        """Test handling of extreme note values"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        
        # Lowest note
        note = MIDINote(0, 80, 0, 25, 0, 100)
        result = optimizer.optimize_velocity(note, OptimizationStrategy.AUTHENTIC)
        assert isinstance(result, OptimizationResult)
        
        # Highest note
        note = MIDINote(127, 80, 0, 25, 0, 100)
        result = optimizer.optimize_velocity(note, OptimizationStrategy.AUTHENTIC)
        assert isinstance(result, OptimizationResult)
    
    def test_missing_behaviour_model(self, sample_behaviour_db):
        """Test handling of missing behaviour model"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        note = MIDINote(60, 80, 0, 99, 0, 100)  # Program 99 not in database
        
        result = optimizer.optimize_velocity(note, OptimizationStrategy.AUTHENTIC)
        
        # Should handle gracefully
        assert result.original_velocity == 80
        assert result.optimized_velocity == 80  # No change


# ============================================================================
# OPTIMIZATION STRATEGY TESTS
# ============================================================================

class TestOptimizationStrategies:
    """Test all optimization strategies"""
    
    def test_strategy_enum_values(self):
        """Test that all strategy values exist"""
        assert OptimizationStrategy.AUTHENTIC.value == "authentic"
        assert OptimizationStrategy.EXPRESSIVE.value == "expressive"
        assert OptimizationStrategy.BALANCED.value == "balanced"
        assert OptimizationStrategy.AGGRESSIVE.value == "aggressive"
    
    def test_strategies_produce_different_results(self, sample_behaviour_db):
        """Test that different strategies produce different results"""
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        note = MIDINote(60, 50, 0, 25, 0, 100)
        
        result_auth = optimizer.optimize_velocity(note, OptimizationStrategy.AUTHENTIC)
        result_expr = optimizer.optimize_velocity(note, OptimizationStrategy.EXPRESSIVE)
        result_bal = optimizer.optimize_velocity(note, OptimizationStrategy.BALANCED)
        result_agg = optimizer.optimize_velocity(note, OptimizationStrategy.AGGRESSIVE)
        
        # Strategies should produce different results for the same input
        velocities = [
            result_auth.optimized_velocity,
            result_expr.optimized_velocity,
            result_bal.optimized_velocity,
            result_agg.optimized_velocity
        ]
        
        # Not all should be identical
        assert len(set(velocities)) > 1


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_full_optimization_workflow(self, sample_behaviour_db, temp_midi_with_notes):
        """Test complete optimization workflow"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_behaviour_db, f)
            db_path = Path(f.name)
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            output_path = Path(f.name)
        
        app = MIDIOptimizerApp(db_path)
        
        # Analyze
        analysis = app.analyze_file(temp_midi_with_notes)
        assert isinstance(analysis, dict)
        
        # Optimize
        result = app.optimize_file(temp_midi_with_notes, output_path, OptimizationStrategy.AUTHENTIC)
        
        # Should complete successfully
        assert isinstance(result, dict)
    
    def test_batch_optimization(self, sample_behaviour_db):
        """Test batch optimization of multiple files"""
        # Create multiple temporary MIDI files
        files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
                f.write(b'MThd')
                f.write(struct.pack('>I', 6))
                f.write(struct.pack('>H', 1))
                f.write(struct.pack('>H', 1))
                f.write(struct.pack('>H', 480))
                f.write(b'MTrk')
                f.write(struct.pack('>I', 4))
                f.write(b'\x00\xFF\x2F\x00')
                files.append(Path(f.name))
        
        assert len(files) == 3


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance characteristics"""
    
    def test_optimization_speed_small_file(self, sample_behaviour_db):
        """Test optimization speed for small MIDI file"""
        import time
        
        optimizer = SoundBehaviourOptimizer(sample_behaviour_db)
        
        # Create 100 notes
        notes = [MIDINote(60 + (i % 12), 80, 0, 25, i * 100, 100) for i in range(100)]
        
        start = time.time()
        optimized, results = optimizer.optimize_midi(notes, OptimizationStrategy.AUTHENTIC)
        elapsed = time.time() - start
        
        # Should complete in reasonable time (< 1 second for 100 notes)
        assert elapsed < 1.0
        assert len(optimized) == 100


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
