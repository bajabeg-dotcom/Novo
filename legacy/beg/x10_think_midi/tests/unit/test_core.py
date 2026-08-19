"""
Unit Tests for X10 Think MIDI Intelligence Engine.
"""

import pytest
from pathlib import Path


class TestMidiUtils:
    """Tests for MIDI utility functions."""
    
    def test_midi_pitch_to_frequency(self):
        """Test MIDI pitch to frequency conversion."""
        from x10_think.utils.midi_utils import MidiUtils
        
        # A4 = 440 Hz
        assert abs(MidiUtils.midi_pitch_to_frequency(69) - 440.0) < 0.01
        
        # C4 = ~261.63 Hz
        assert abs(MidiUtils.midi_pitch_to_frequency(60) - 261.63) < 0.1
    
    def test_midi_pitch_to_note_name(self):
        """Test MIDI pitch to note name conversion."""
        from x10_think.utils.midi_utils import MidiUtils
        
        assert MidiUtils.midi_pitch_to_note_name(60) == "C4"
        assert MidiUtils.midi_pitch_to_note_name(69) == "A4"
        assert MidiUtils.midi_pitch_to_note_name(71) == "B4"
    
    def test_valid_midi_pitch(self):
        """Test MIDI pitch validation."""
        from x10_think.utils.midi_utils import MidiUtils
        
        assert MidiUtils.is_valid_midi_pitch(0) is True
        assert MidiUtils.is_valid_midi_pitch(127) is True
        assert MidiUtils.is_valid_midi_pitch(-1) is False
        assert MidiUtils.is_valid_midi_pitch(128) is False
    
    def test_valid_midi_velocity(self):
        """Test MIDI velocity validation."""
        from x10_think.utils.midi_utils import MidiUtils
        
        assert MidiUtils.is_valid_midi_velocity(0) is True
        assert MidiUtils.is_valid_midi_velocity(127) is True
        assert MidiUtils.is_valid_midi_velocity(-1) is False
        assert MidiUtils.is_valid_midi_velocity(128) is False


class TestMusicTheory:
    """Tests for music theory utilities."""
    
    def test_get_scale_notes_major(self):
        """Test major scale note generation."""
        from x10_think.utils.music_theory import MusicTheory
        
        # C major: C D E F G A B
        c_major = MusicTheory.get_scale_notes(0, 'major')
        assert c_major == [0, 2, 4, 5, 7, 9, 11]
    
    def test_get_scale_notes_minor(self):
        """Test natural minor scale note generation."""
        from x10_think.utils.music_theory import MusicTheory
        
        # A minor: A B C D E F G
        a_minor = MusicTheory.get_scale_notes(9, 'natural_minor')
        assert a_minor == [9, 11, 0, 2, 4, 5, 7]
    
    def test_get_chord_notes_major(self):
        """Test major chord note generation."""
        from x10_think.utils.music_theory import MusicTheory
        
        # C major: C E G
        c_major = MusicTheory.get_chord_notes(0, 'major')
        assert c_major == [0, 4, 7]
    
    def test_get_chord_notes_minor(self):
        """Test minor chord note generation."""
        from x10_think.utils.music_theory import MusicTheory
        
        # C minor: C Eb G
        c_minor = MusicTheory.get_chord_notes(0, 'minor')
        assert c_minor == [0, 3, 7]
    
    def test_is_diatonic(self):
        """Test diatonic pitch checking."""
        from x10_think.utils.music_theory import MusicTheory
        
        # E is diatonic to C major
        assert MusicTheory.is_diatonic(4, 0, 'major') is True
        
        # Eb is not diatonic to C major
        assert MusicTheory.is_diatonic(3, 0, 'major') is False
    
    def test_get_interval(self):
        """Test interval naming."""
        from x10_think.utils.music_theory import MusicTheory
        
        assert MusicTheory.get_interval(0) == "Perfect Unison"
        assert MusicTheory.get_interval(4) == "Major Third"
        assert MusicTheory.get_interval(7) == "Perfect Fifth"
        assert MusicTheory.get_interval(12) == "Perfect Octave"


class TestEventBus:
    """Tests for the event bus system."""
    
    def test_subscribe_and_publish(self):
        """Test event subscription and publishing."""
        from x10_think.core.event_bus import EventBus, Event
        
        bus = EventBus()
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        bus.subscribe("test.event", handler)
        bus.publish(Event(name="test.event", payload={"data": "test"}))
        
        assert len(received_events) == 1
        assert received_events[0].name == "test.event"
        assert received_events[0].payload["data"] == "test"
    
    def test_unsubscribe(self):
        """Test event unsubscription."""
        from x10_think.core.event_bus import EventBus, Event
        
        bus = EventBus()
        call_count = [0]
        
        def handler(event: Event):
            call_count[0] += 1
        
        bus.subscribe("test.event", handler)
        bus.publish(Event(name="test.event"))
        bus.unsubscribe("test.event", handler)
        bus.publish(Event(name="test.event"))
        
        assert call_count[0] == 1
    
    def test_event_history(self):
        """Test event history tracking."""
        from x10_think.core.event_bus import EventBus, Event
        
        bus = EventBus()
        bus.publish(Event(name="event1"))
        bus.publish(Event(name="event2"))
        bus.publish(Event(name="event1"))
        
        all_events = bus.get_history()
        assert len(all_events) == 3
        
        filtered = bus.get_history("event1")
        assert len(filtered) == 2


class TestConfigManager:
    """Tests for configuration management."""
    
    def test_default_config(self):
        """Test default configuration values."""
        from x10_think.core.config_manager import ConfigManager
        
        config = ConfigManager()
        assert config.app_config.debug_mode is False
        assert config.app_config.theme == "dark"
        assert config.app_config.parser_engine.enabled is True
    
    def test_get_set_value(self):
        """Test getting and setting configuration values."""
        from x10_think.core.config_manager import ConfigManager
        
        config = ConfigManager()
        config.set("debug_mode", True)
        assert config.get("debug_mode") is True
        
        config.set("parser_engine.enabled", False)
        assert config.app_config.parser_engine.enabled is False
    
    def test_validation(self):
        """Test configuration validation."""
        from x10_think.core.config_manager import ConfigManager
        
        config = ConfigManager()
        errors = config.validate()
        assert isinstance(errors, list)


class TestTrackIntelligence:
    """Tests for track classification."""
    
    def test_program_based_classification(self):
        """Test classification by GM program number."""
        from x10_think.engines.track_intelligence import TrackIntelligenceEngine
        
        engine = TrackIntelligenceEngine()
        
        # Piano programs (0-7) should classify as PIANO
        assert engine._classify_by_program(0).value == "piano"
        assert engine._classify_by_program(4).value == "piano"
        
        # Bass programs (32-39) should classify as BASS
        assert engine._classify_by_program(32).value == "bass"
        
        # Drum channel detection
        assert engine._classify_by_program(0).value != "drum"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
