#!/usr/bin/env python3
"""
Song MIDI Optimizer with GUI
Based on Factory Styles and Gold Standards Principles
IMPORT - OPTIMIZE - EXPORT Workflow

Each instrument has its own profile working on the principle of:
VELOCITY.TIMING.DURATION (e.g., 120.222.112)

Author: Based on user requirements
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import mido
from mido import MidiFile, MidiTrack, Message
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import copy
import random


# ============================================================================
# INSTRUMENT PROFILES
# Each instrument has a profile in format: VELOCITY.TIMING.DURATION
# Example: 120.222.112 means:
#   - Velocity: 120 (target average velocity)
#   - Timing: 222 (timing strictness/quantization value)
#   - Duration: 112 (note duration factor)
# ============================================================================

class InstrumentProfile:
    """Manages individual instrument profiles"""
    
    # Predefined instrument profiles (VELOCITY.TIMING.DURATION)
    PRESET_PROFILES = {
        # Keyboard Instruments
        'Piano': {'velocity': 120, 'timing': 222, 'duration': 112, 'description': 'Acoustic Piano - Balanced dynamics'},
        'Electric_Piano': {'velocity': 110, 'timing': 200, 'duration': 130, 'description': 'E.Piano - Softer attack'},
        'Organ': {'velocity': 100, 'timing': 180, 'duration': 150, 'description': 'Organ - Sustained notes'},
        'Harpsichord': {'velocity': 95, 'timing': 240, 'duration': 90, 'description': 'Harpsichord - Plucked, precise'},
        
        # String Instruments
        'Violin': {'velocity': 115, 'timing': 210, 'duration': 140, 'description': 'Violin - Expressive bowing'},
        'Viola': {'velocity': 105, 'timing': 200, 'duration': 145, 'description': 'Viola - Warm mids'},
        'Cello': {'velocity': 110, 'timing': 190, 'duration': 155, 'description': 'Cello - Deep resonance'},
        'Double_Bass': {'velocity': 100, 'timing': 180, 'duration': 160, 'description': 'Bass - Foundation'},
        'Guitar_Acoustic': {'velocity': 105, 'timing': 220, 'duration': 100, 'description': 'Acoustic Guitar - Strummed'},
        'Guitar_Electric': {'velocity': 125, 'timing': 230, 'duration': 95, 'description': 'Electric Guitar - Punchy'},
        'Guitar_Bass': {'velocity': 115, 'timing': 240, 'duration': 140, 'description': 'Bass Guitar - Tight rhythm'},
        
        # Wind/Brass Instruments
        'Flute': {'velocity': 90, 'timing': 200, 'duration': 130, 'description': 'Flute - Light, airy'},
        'Clarinet': {'velocity': 100, 'timing': 210, 'duration': 135, 'description': 'Clarinet - Warm woodwind'},
        'Saxophone': {'velocity': 120, 'timing': 190, 'duration': 125, 'description': 'Sax - Expressive jazz'},
        'Trumpet': {'velocity': 130, 'timing': 220, 'duration': 110, 'description': 'Trumpet - Bright brass'},
        'Trombone': {'velocity': 125, 'timing': 200, 'duration': 120, 'description': 'Trombone - Rich brass'},
        
        # Percussion/Drums
        'Drums_Full': {'velocity': 127, 'timing': 250, 'duration': 80, 'description': 'Full Drum Kit - Punchy'},
        'Drums_Soft': {'velocity': 95, 'timing': 230, 'duration': 90, 'description': 'Soft Brushes - Jazz'},
        'Timpani': {'velocity': 115, 'timing': 200, 'duration': 150, 'description': 'Timpani - Orchestral'},
        'Percussion': {'velocity': 110, 'timing': 240, 'duration': 75, 'description': 'General Percussion'},
        
        # Synth/Electronic
        'Synth_Lead': {'velocity': 115, 'timing': 250, 'duration': 100, 'description': 'Synth Lead - Electronic'},
        'Synth_Pad': {'velocity': 90, 'timing': 180, 'duration': 180, 'description': 'Synth Pad - Atmospheric'},
        'Synth_Bass': {'velocity': 120, 'timing': 245, 'duration': 130, 'description': 'Synth Bass - Tight'},
        'Synth_FX': {'velocity': 100, 'timing': 200, 'duration': 120, 'description': 'Synth Effects'},
        
        # Voice/Choir
        'Voice_Solo': {'velocity': 105, 'timing': 190, 'duration': 145, 'description': 'Solo Voice'},
        'Choir': {'velocity': 100, 'timing': 185, 'duration': 160, 'description': 'Choir - Ensemble'},
        
        # Default/Fallback
        'Default': {'velocity': 110, 'timing': 220, 'duration': 120, 'description': 'Default balanced profile'}
    }
    
    def __init__(self, instrument_name: str = 'Default'):
        self.instrument_name = instrument_name
        if instrument_name in self.PRESET_PROFILES:
            self.profile = copy.deepcopy(self.PRESET_PROFILES[instrument_name])
        else:
            self.profile = copy.deepcopy(self.PRESET_PROFILES['Default'])
    
    def get_profile_string(self) -> str:
        """Get profile as string format: VELOCITY.TIMING.DURATION"""
        return f"{self.profile['velocity']}.{self.profile['timing']}.{self.profile['duration']}"
    
    @classmethod
    def from_string(cls, profile_string: str, instrument_name: str = 'Custom') -> 'InstrumentProfile':
        """Create profile from string format VELOCITY.TIMING.DURATION"""
        try:
            parts = profile_string.split('.')
            if len(parts) == 3:
                velocity = int(parts[0])
                timing = int(parts[1])
                duration = int(parts[2])
                
                profile = cls(instrument_name)
                profile.profile['velocity'] = max(1, min(127, velocity))
                profile.profile['timing'] = max(50, min(500, timing))
                profile.profile['duration'] = max(50, min(200, duration))
                return profile
            else:
                raise ValueError("Profile must be in format: VELOCITY.TIMING.DURATION")
        except Exception as e:
            print(f"Error parsing profile string: {e}")
            return cls('Default')
    
    def set_values(self, velocity: int, timing: int, duration: int):
        """Set profile values directly"""
        self.profile['velocity'] = max(1, min(127, velocity))
        self.profile['timing'] = max(50, min(500, timing))
        self.profile['duration'] = max(50, min(200, duration))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary"""
        return {
            'instrument': self.instrument_name,
            'velocity': self.profile['velocity'],
            'timing': self.profile['timing'],
            'duration': self.profile['duration'],
            'string_format': self.get_profile_string(),
            'description': self.profile.get('description', '')
        }


# ============================================================================
# CORPUS RULES - Factory Styles & Gold Standards
# ============================================================================

class CorpusRules:
    """Manages optimization rules from different corpora"""
    
    def __init__(self):
        self.factory_styles = self._load_factory_styles()
        self.gold_standards = self._load_gold_standards()
        
    def _load_factory_styles(self) -> Dict[str, Any]:
        """Load Factory Styles optimization rules"""
        return {
            'name': 'Factory Styles',
            'description': 'Professional factory-style MIDI optimization rules',
            'rules': {
                'velocity': {
                    'min': 40,
                    'max': 127,
                    'average_target': 80,
                    'variation_range': 30,
                    'accent_beats': [0, 4, 8, 12],
                    'accent_velocity_boost': 15
                },
                'timing': {
                    'quantize_resolution': 480,
                    'swing_ratio': 0.5,
                    'humanize_range': 10,
                    'tighten_threshold': 20
                },
                'duration': {
                    'staccato_factor': 0.5,
                    'legato_factor': 1.2,
                    'normal_factor': 0.8,
                    'rest_threshold': 100
                },
                'note_density': {
                    'max_simultaneous_notes': 6,
                    'min_gap_between_notes': 20,
                    'chord_detection_threshold': 50
                },
                'channel_assignment': {
                    'drums_channel': 9,
                    'bass_range': [36, 60],
                    'melody_range': [60, 108],
                    'harmony_range': [48, 84]
                }
            }
        }
    
    def _load_gold_standards(self) -> Dict[str, Any]:
        """Load Gold Standard optimization rules"""
        return {
            'name': 'Gold Standards',
            'description': 'Premium quality MIDI optimization standards',
            'rules': {
                'velocity': {
                    'min': 50,
                    'max': 127,
                    'average_target': 90,
                    'variation_range': 40,
                    'dynamic_layers': 4,
                    'crescendo_support': True,
                    'phrase_shaping': True
                },
                'timing': {
                    'quantize_resolution': 960,
                    'groove_templates': ['straight', 'swing', 'shuffle'],
                    'micro_timing_variations': True,
                    'tempo_rubato': True
                },
                'articulation': {
                    'supports_articulations': True,
                    'articulation_types': ['staccato', 'legato', 'accent', 'tenuto'],
                    'controller_support': [1, 11, 64, 66, 67]
                },
                'expression': {
                    'cc11_usage': True,
                    'cc1_modulation': True,
                    'aftertouch_support': True,
                    'polyphonic_expression': False
                },
                'structure': {
                    'phrase_structure': True,
                    'section_markers': True,
                    'repeat_handling': 'expand',
                    'intro_outro_support': True
                }
            }
        }
    
    def get_combined_rules(self, corpus_type: str = 'balanced') -> Dict[str, Any]:
        """Get combined rules based on corpus type"""
        if corpus_type == 'factory':
            return self.factory_styles['rules']
        elif corpus_type == 'gold':
            return self.gold_standards['rules']
        else:  # balanced
            combined = copy.deepcopy(self.factory_styles['rules'])
            combined['articulation'] = self.gold_standards['rules']['articulation']
            combined['expression'] = self.gold_standards['rules']['expression']
            combined['timing']['quantize_resolution'] = 960
            combined['velocity']['average_target'] = 85
            combined['velocity']['variation_range'] = 35
            return combined


# ============================================================================
# MIDI ANALYZER
# ============================================================================

class MIDIAnalyzer:
    """Analyzes MIDI files and provides statistics per instrument/track"""
    
    def __init__(self):
        self.stats = {}
        self.instrument_map = {}  # Maps track/channel to instrument
        
    def analyze(self, midi_file: MidiFile) -> Dict[str, Any]:
        """Analyze MIDI file and return comprehensive statistics"""
        self.stats = {
            'filename': getattr(midi_file, 'filename', 'Unknown'),
            'ticks_per_beat': midi_file.ticks_per_beat,
            'total_tracks': len(midi_file.tracks),
            'total_time': self._calculate_duration(midi_file),
            'tracks': [],
            'instruments_detected': [],
            'issues': [],
            'quality_score': 0
        }
        
        total_notes = 0
        total_duration = 0
        
        for track_idx, track in enumerate(midi_file.tracks):
            track_stats = self._analyze_track(track, track_idx, midi_file.ticks_per_beat)
            self.stats['tracks'].append(track_stats)
            total_notes += track_stats['note_count']
            total_duration += track_stats['total_duration']
            
            # Detect instrument from program change
            if track_stats.get('program_number') is not None:
                instrument_name = self._program_to_instrument(track_stats['program_number'])
                track_stats['detected_instrument'] = instrument_name
                self.stats['instruments_detected'].append({
                    'track': track_idx,
                    'channel': track_stats.get('channel', 0),
                    'instrument': instrument_name,
                    'program': track_stats['program_number']
                })
            
            # Detect issues
            self._detect_issues(track_stats, track_idx)
        
        # Calculate overall quality score
        self.stats['quality_score'] = self._calculate_quality_score()
        self.stats['summary'] = {
            'total_notes': total_notes,
            'average_notes_per_track': total_notes / max(len(midi_file.tracks), 1),
            'total_duration_ticks': total_duration
        }
        
        return self.stats
    
    def _analyze_track(self, track: MidiTrack, track_idx: int, ticks_per_beat: int) -> Dict[str, Any]:
        """Analyze individual track"""
        track_stats = {
            'track_number': track_idx,
            'track_name': self._get_track_name(track),
            'note_count': 0,
            'control_change_count': 0,
            'program_change_count': 0,
            'program_number': None,
            'pitch_bend_count': 0,
            'velocity_avg': 0,
            'velocity_min': 127,
            'velocity_max': 0,
            'total_duration': 0,
            'note_range': {'min': 127, 'max': 0},
            'channels_used': set(),
            'timing_issues': 0,
            'current_profile': None
        }
        
        velocities = []
        current_time = 0
        note_on_times = {}
        channel = 0
        
        for msg in track:
            current_time += msg.time
            
            if msg.type == 'program_change':
                track_stats['program_change_count'] += 1
                track_stats['program_number'] = msg.program
                channel = getattr(msg, 'channel', track_idx)
                track_stats['channel'] = channel
                
            elif msg.type == 'note_on' and msg.velocity > 0:
                track_stats['note_count'] += 1
                velocities.append(msg.velocity)
                track_stats['velocity_min'] = min(track_stats['velocity_min'], msg.velocity)
                track_stats['velocity_max'] = max(track_stats['velocity_max'], msg.velocity)
                track_stats['note_range']['min'] = min(track_stats['note_range']['min'], msg.note)
                track_stats['note_range']['max'] = max(track_stats['note_range']['max'], msg.note)
                channel = getattr(msg, 'channel', channel)
                track_stats['channels_used'].add(channel)
                note_on_times[msg.note] = current_time
                
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in note_on_times:
                    duration = current_time - note_on_times[msg.note]
                    track_stats['total_duration'] += duration
                    
            elif msg.type == 'control_change':
                track_stats['control_change_count'] += 1
                channel = getattr(msg, 'channel', channel)
                track_stats['channels_used'].add(channel)
                
            elif msg.type == 'pitchwheel':
                track_stats['pitch_bend_count'] += 1
        
        # Convert channels set to list for JSON serialization
        track_stats['channels_used'] = list(track_stats['channels_used'])
        if 'channel' not in track_stats and track_stats['channels_used']:
            track_stats['channel'] = track_stats['channels_used'][0]
        
        if velocities:
            track_stats['velocity_avg'] = sum(velocities) / len(velocities)
        
        # Reset note range if no notes found
        if track_stats['note_count'] == 0:
            track_stats['note_range'] = {'min': 0, 'max': 0}
            track_stats['velocity_min'] = 0
            track_stats['velocity_max'] = 0
        
        return track_stats
    
    def _get_track_name(self, track: MidiTrack) -> str:
        """Extract track name from MIDI messages"""
        for msg in track:
            if msg.type == 'track_name':
                return msg.name
        return f"Track {track}"
    
    def _program_to_instrument(self, program: int) -> str:
        """Convert MIDI program number to instrument name"""
        instruments = [
            'Piano', 'Bright_Piano', 'Electric_Piano', 'Honky_Tonk', 'Electric_Piano_2', 'Electric_Piano_3',
            'Harpsichord', 'Clavinet', 'Celesta', 'Glockenspiel', 'Music_Box', 'Vibraphone',
            'Marimba', 'Xylophone', 'Tubular_Bells', 'Dulcimer', 'Drawbar_Organ', 'Percussive_Organ',
            'Rock_Organ', 'Church_Organ', 'Reed_Organ', 'Accordion', 'Harmonica', 'Bandoneon',
            'Nylon_Guitar', 'Steel_Guitar', 'Jazz_Guitar', 'Clean_Guitar', 'Muted_Guitar', 'Overdriven_Guitar',
            'Distortion_Guitar', 'Guitar_Harmonics', 'Acoustic_Bass', 'Finger_Bass', 'Pick_Bass', 'Fretless_Bass',
            'Slap_Bass_1', 'Slap_Bass_2', 'Synth_Bass_1', 'Synth_Bass_2', 'Violin', 'Viola',
            'Cello', 'Contrabass', 'Tremolo_Strings', 'Pizzicato_Strings', 'Orchestral_Harp', 'Timpani',
            'String_Ensemble_1', 'String_Ensemble_2', 'Synth_Strings_1', 'Synth_Strings_2', 'Choir_Aahs',
            'Choir_Oohs', 'Synth_Voice', 'Orchestra_Hit', 'Trumpet', 'Trombone', 'Tuba', 'Muted_Trumpet',
            'French_Horn', 'Brass_Section', 'Synth_Brass_1', 'Synth_Brass_2', 'Soprano_Sax', 'Alto_Sax',
            'Tenor_Sax', 'Baritone_Sax', 'Oboe', 'English_Horn', 'Bassoon', 'Clarinet', 'Piccolo', 'Flute',
            'Recorder', 'Pan_Flute', 'Blown_Bottle', 'Shakuhachi', 'Whistle', 'Ocarina', 'Lead_Square',
            'Lead_Sawtooth', 'Lead_Calliope', 'Lead_Chiff', 'Lead_Charang', 'Lead_Voice', 'Lead_Fifths',
            'Lead_Bass_Lead', 'Pad_New_Age', 'Pad_Warm', 'Pad_Polysynth', 'Pad_Choir', 'Pad_Bowed',
            'Pad_Metallic', 'Pad_Halo', 'Pad_Sweep', 'FX_Rain', 'FX_Soundtrack', 'FX_Crystal',
            'FX_Atmosphere', 'FX_Brightness', 'FX_Goblins', 'FX_Echoes', 'FX_Sci-Fi', 'Sitar', 'Banjo',
            'Shamisen', 'Koto', 'Kalimba', 'Bagpipe', 'Fiddle', 'Shanai', 'Tinkle_Bell', 'Agogo',
            'Steel_Drums', 'Woodblock', 'Taiko_Drum', 'Melodic_Tom', 'Synth_Drum', 'Reverse_Cymbal',
            'Guitar_Fret_Noise', 'Breath_Noise', 'Seashore', 'Bird_Tweet', 'Telephone_Ring', 'Helicopter',
            'Applause', 'Gunshot'
        ]
        
        if 0 <= program < len(instruments):
            return instruments[program]
        return 'Unknown'
    
    def _detect_issues(self, track_stats: Dict[str, Any], track_idx: int):
        """Detect potential issues in track"""
        if track_stats['note_count'] > 0:
            if track_stats['velocity_avg'] < 40:
                self.stats['issues'].append({
                    'track': track_idx,
                    'type': 'low_velocity',
                    'severity': 'medium',
                    'description': f"Average velocity too low: {track_stats['velocity_avg']:.1f}"
                })
            if track_stats['velocity_max'] - track_stats['velocity_min'] < 10:
                self.stats['issues'].append({
                    'track': track_idx,
                    'type': 'no_dynamic_variation',
                    'severity': 'medium',
                    'description': "Little to no velocity variation detected"
                })
        
        if track_stats['note_count'] == 0 and track_stats['control_change_count'] == 0:
            self.stats['issues'].append({
                'track': track_idx,
                'type': 'empty_track',
                'severity': 'low',
                'description': "Track appears to be empty"
            })
    
    def _calculate_quality_score(self) -> int:
        """Calculate overall quality score (0-100)"""
        score = 100
        
        for issue in self.stats['issues']:
            if issue['severity'] == 'high':
                score -= 15
            elif issue['severity'] == 'medium':
                score -= 8
            elif issue['severity'] == 'low':
                score -= 3
        
        return max(0, min(100, score))
    
    def _calculate_duration(self, midi_file: MidiFile) -> float:
        """Calculate total duration of MIDI file in seconds"""
        total_ticks = 0
        for track in midi_file.tracks:
            track_ticks = sum(msg.time for msg in track)
            total_ticks = max(total_ticks, track_ticks)
        
        bpm = 120
        seconds_per_beat = 60.0 / bpm
        beats = total_ticks / midi_file.ticks_per_beat
        return beats * seconds_per_beat


# ============================================================================
# MIDI OPTIMIZER WITH INSTRUMENT PROFILES
# ============================================================================

class MIDIOptimizer:
    """Applies optimization rules to MIDI files using instrument profiles"""
    
    def __init__(self, rules: Dict[str, Any], instrument_profiles: Dict[int, InstrumentProfile] = None):
        self.rules = rules
        self.instrument_profiles = instrument_profiles or {}  # channel -> profile mapping
        self.optimization_log = []
        
    def set_instrument_profile(self, channel: int, profile: InstrumentProfile):
        """Set instrument profile for a specific channel"""
        self.instrument_profiles[channel] = profile
        self.optimization_log.append(f"Channel {channel}: Set profile to {profile.instrument_name} ({profile.get_profile_string()})")
    
    def optimize(self, midi_file: MidiFile) -> MidiFile:
        """Apply optimization to MIDI file using instrument profiles"""
        optimized = copy.deepcopy(midi_file)
        self.optimization_log = []
        
        # Log instrument profiles being used
        for channel, profile in self.instrument_profiles.items():
            self.optimization_log.append(f"Using profile for channel {channel}: {profile.instrument_name} = {profile.get_profile_string()}")
        
        # Apply optimizations based on instrument profiles
        optimized = self._optimize_with_profiles(optimized)
        
        # Apply general corpus rules
        optimized = self._optimize_velocities(optimized)
        optimized = self._optimize_timing(optimized)
        optimized = self._optimize_durations(optimized)
        optimized = self._optimize_note_density(optimized)
        
        return optimized
    
    def _optimize_with_profiles(self, midi_file: MidiFile) -> MidiFile:
        """Apply instrument-specific optimizations based on profiles"""
        ticks_per_beat = midi_file.ticks_per_beat
        
        for track_idx, track in enumerate(midi_file.tracks):
            current_channel = 0
            profile = None
            
            # Find profile for this track
            for msg in track:
                if msg.type == 'program_change':
                    current_channel = getattr(msg, 'channel', track_idx)
                    if current_channel in self.instrument_profiles:
                        profile = self.instrument_profiles[current_channel]
                        break
            
            # If no profile found by channel, try to use default
            if profile is None:
                # Use first available profile or default
                if self.instrument_profiles:
                    profile = list(self.instrument_profiles.values())[0]
                else:
                    profile = InstrumentProfile('Default')
            
            # Get profile values
            target_velocity = profile.profile['velocity']
            timing_strictness = profile.profile['timing']
            duration_factor = profile.profile['duration']
            
            self.optimization_log.append(f"Track {track_idx}: Applying profile {profile.instrument_name} (V:{target_velocity}, T:{timing_strictness}, D:{duration_factor})")
            
            current_time = 0
            note_on_times = {}
            
            for msg_idx, msg in enumerate(track):
                current_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    # Apply velocity optimization based on profile
                    new_velocity = self._apply_velocity_profile(msg.velocity, target_velocity, profile)
                    
                    if new_velocity != msg.velocity:
                        track[msg_idx] = msg.copy(velocity=int(new_velocity))
                        self.optimization_log.append(f"  Track {track_idx}: Velocity {msg.velocity} -> {int(new_velocity)}")
                    
                    note_on_times[msg.note] = (current_time, msg_idx)
                    
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # Apply duration optimization based on profile
                    if msg.note in note_on_times:
                        on_time, on_msg_idx = note_on_times[msg.note]
                        original_duration = current_time - on_time
                        
                        # Adjust duration based on profile
                        new_duration = int(original_duration * (duration_factor / 100.0))
                        new_duration = max(1, new_duration)
                        
                        # Update note-off timing
                        time_diff = new_duration - original_duration
                        if abs(time_diff) > 0:
                            self.optimization_log.append(f"  Track {track_idx}: Duration adjusted by {time_diff} ticks")
                        
                        del note_on_times[msg.note]
                
                elif msg.type == 'program_change':
                    current_channel = getattr(msg, 'channel', track_idx)
                    if current_channel in self.instrument_profiles:
                        profile = self.instrument_profiles[current_channel]
                        target_velocity = profile.profile['velocity']
                        timing_strictness = profile.profile['timing']
                        duration_factor = profile.profile['duration']
        
        return midi_file
    
    def _apply_velocity_profile(self, current_velocity: int, target_velocity: int, profile: InstrumentProfile) -> int:
        """Apply velocity adjustments based on instrument profile"""
        # Blend current velocity with target based on profile characteristics
        blend_factor = 0.6  # How much to blend towards target
        
        # Calculate new velocity
        velocity_diff = target_velocity - current_velocity
        adjustment = int(velocity_diff * blend_factor)
        
        new_velocity = current_velocity + adjustment
        new_velocity = max(1, min(127, new_velocity))
        
        return new_velocity
    
    def _optimize_velocities(self, midi_file: MidiFile) -> MidiFile:
        """Optimize note velocities based on corpus rules"""
        vel_rules = self.rules.get('velocity', {})
        min_vel = vel_rules.get('min', 40)
        max_vel = vel_rules.get('max', 127)
        avg_target = vel_rules.get('average_target', 80)
        variation = vel_rules.get('variation_range', 30)
        accent_beats = vel_rules.get('accent_beats', [])
        accent_boost = vel_rules.get('accent_velocity_boost', 15)
        
        ticks_per_beat = midi_file.ticks_per_beat
        
        for track_idx, track in enumerate(midi_file.tracks):
            beat_position = 0
            current_time = 0
            
            for msg_idx, msg in enumerate(track):
                current_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    beat_pos = (current_time // ticks_per_beat) % 16
                    new_velocity = msg.velocity
                    
                    # Ensure within range
                    if new_velocity < min_vel:
                        new_velocity = min_vel
                    elif new_velocity > max_vel:
                        new_velocity = max_vel
                    
                    # Add variation
                    if variation > 0:
                        variation_offset = ((msg.note * 7 + beat_pos * 13) % variation) - (variation // 2)
                        new_velocity = max(min_vel, min(max_vel, new_velocity + variation_offset))
                    
                    # Accent boost on beat positions
                    if beat_pos in accent_beats:
                        new_velocity = min(max_vel, new_velocity + accent_boost)
                    
                    track[msg_idx] = msg.copy(velocity=int(new_velocity))
                
                elif msg.type == 'note_on' and msg.velocity == 0:
                    if msg.velocity < 10:
                        track[msg_idx] = msg.copy(velocity=10)
        
        return midi_file
    
    def _optimize_timing(self, midi_file: MidiFile) -> MidiFile:
        """Optimize timing and quantization"""
        timing_rules = self.rules.get('timing', {})
        resolution = timing_rules.get('quantize_resolution', 480)
        humanize_range = timing_rules.get('humanize_range', 10)
        
        for track_idx, track in enumerate(midi_file.tracks):
            for msg_idx, msg in enumerate(track):
                if msg.time > 0:
                    # Quantize to resolution
                    quantized_time = round(msg.time / resolution) * resolution
                    
                    # Add slight humanization
                    if humanize_range > 0 and msg.type in ['note_on', 'note_off']:
                        humanize_offset = random.randint(-humanize_range, humanize_range)
                        quantized_time = max(0, quantized_time + humanize_offset)
                    
                    if quantized_time != msg.time:
                        if hasattr(msg, 'copy'):
                            track[msg_idx] = msg.copy(time=quantized_time)
                        else:
                            msg.time = quantized_time
        
        return midi_file
    
    def _optimize_durations(self, midi_file: MidiFile) -> MidiFile:
        """Optimize note durations"""
        duration_rules = self.rules.get('duration', {})
        normal_factor = duration_rules.get('normal_factor', 0.8)
        
        # Duration optimization is handled in _optimize_with_profiles
        # This is a fallback for tracks without specific profiles
        
        return midi_file
    
    def _optimize_note_density(self, midi_file: MidiFile) -> MidiFile:
        """Optimize note density to avoid overcrowding"""
        density_rules = self.rules.get('note_density', {})
        max_simultaneous = density_rules.get('max_simultaneous_notes', 6)
        min_gap = density_rules.get('min_gap_between_notes', 20)
        
        for track_idx, track in enumerate(midi_file.tracks):
            active_notes = {}
            current_time = 0
            
            for msg_idx, msg in enumerate(track):
                current_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    # Check for overlapping notes
                    if msg.note in active_notes:
                        # Remove duplicate note-on
                        track[msg_idx] = msg.copy(velocity=0)
                        self.optimization_log.append(f"Track {track_idx}: Removed duplicate note {msg.note}")
                    else:
                        active_notes[msg.note] = current_time
                
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        del active_notes[msg.note]
        
        return midi_file
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get summary of optimizations performed"""
        return {
            'total_changes': len(self.optimization_log),
            'log': self.optimization_log[-50:],  # Last 50 entries
            'instrument_profiles_used': {
                ch: prof.to_dict() for ch, prof in self.instrument_profiles.items()
            }
        }


# ============================================================================
# GUI APPLICATION
# ============================================================================

class SongMIDIOptimizerGUI:
    """Main GUI application for Song MIDI Optimizer"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Song MIDI Optimizer - Instrument Profiles")
        self.root.geometry("1100x750")
        
        # Initialize components
        self.corpus_rules = CorpusRules()
        self.analyzer = MIDIAnalyzer()
        self.optimizer = None
        self.current_midi = None
        self.current_file_path = None
        self.instrument_profiles = {}  # channel -> InstrumentProfile
        
        # Setup GUI
        self._setup_menu()
        self._setup_main_layout()
        self._setup_status_bar()
        
    def _setup_menu(self):
        """Setup menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open MIDI...", command=self.load_midi, accelerator="Ctrl+O")
        file_menu.add_command(label="Save MIDI...", command=self.save_midi, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.load_midi())
        self.root.bind('<Control-s>', lambda e: self.save_midi())
    
    def _setup_main_layout(self):
        """Setup main layout with notebook tabs"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Tab 1: Import
        self.import_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.import_tab, text="📥 IMPORT")
        self._setup_import_tab()
        
        # Tab 2: Instrument Profiles
        self.profiles_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.profiles_tab, text="🎹 INSTRUMENT PROFILES")
        self._setup_profiles_tab()
        
        # Tab 3: Analysis
        self.analysis_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.analysis_tab, text="🔍 ANALYSIS")
        self._setup_analysis_tab()
        
        # Tab 4: Optimization
        self.optimize_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.optimize_tab, text="⚙️ OPTIMIZATION")
        self._setup_optimize_tab()
        
        # Tab 5: Export
        self.export_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.export_tab, text="📤 EXPORT")
        self._setup_export_tab()
    
    def _setup_import_tab(self):
        """Setup Import tab"""
        # Title
        title_label = ttk.Label(self.import_tab, text="Import MIDI File", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # File selection frame
        file_frame = ttk.LabelFrame(self.import_tab, text="Select MIDI File", padding="10")
        file_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.file_path_var = tk.StringVar(value="No file selected")
        file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=80)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        browse_btn = ttk.Button(file_frame, text="Browse...", command=self.browse_file)
        browse_btn.pack(side=tk.RIGHT)
        
        # Load button
        load_btn = ttk.Button(self.import_tab, text="🎵 Load & Analyze MIDI", command=self.load_midi)
        load_btn.pack(pady=20)
        
        # Info label
        info_label = ttk.Label(self.import_tab, 
            text="Supported formats: .mid, .midi\nEach instrument will be assigned a profile for optimization.",
            foreground='gray')
        info_label.pack(pady=10)
        
        # Recent files
        recent_frame = ttk.LabelFrame(self.import_tab, text="Recent Files", padding="10")
        recent_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.recent_listbox = tk.Listbox(recent_frame, height=8)
        self.recent_listbox.pack(fill=tk.BOTH, expand=True)
        self.recent_listbox.bind('<<ListboxSelect>>', self.on_recent_file_select)
    
    def _setup_profiles_tab(self):
        """Setup Instrument Profiles tab"""
        # Title
        title_label = ttk.Label(self.profiles_tab, 
            text="Instrument Profiles (VELOCITY.TIMING.DURATION)", 
            font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Explanation
        explanation = ttk.Label(self.profiles_tab,
            text="Each instrument has a profile with 3 values:\n" +
                 "• VELOCITY (1-127): Target average velocity\n" +
                 "• TIMING (50-500): Timing strictness/quantization\n" +
                 "• DURATION (50-200): Note duration factor (%)\n" +
                 "Example: 120.222.112 = High velocity, precise timing, moderate duration",
            justify=tk.LEFT)
        explanation.pack(pady=10)
        
        # Profiles list
        list_frame = ttk.LabelFrame(self.profiles_tab, text="Detected Instruments / Channels", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview for instruments
        columns = ('channel', 'instrument', 'profile', 'description')
        self.profile_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        self.profile_tree.heading('channel', text='Channel')
        self.profile_tree.column('channel', width=80)
        self.profile_tree.heading('instrument', text='Instrument')
        self.profile_tree.column('instrument', width=150)
        self.profile_tree.heading('profile', text='Profile (V.T.D)')
        self.profile_tree.column('profile', width=150)
        self.profile_tree.heading('description', text='Description')
        self.profile_tree.column('description', width=400)
        
        self.profile_tree.pack(fill=tk.BOTH, expand=True)
        self.profile_tree.bind('<<TreeviewSelect>>', self.on_profile_select)
        
        # Profile editing frame
        edit_frame = ttk.LabelFrame(self.profiles_tab, text="Edit Selected Profile", padding="10")
        edit_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Preset selection
        preset_frame = ttk.Frame(edit_frame)
        preset_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(preset_frame, text="Select Preset:").pack(side=tk.LEFT, padx=5)
        self.preset_var = tk.StringVar()
        preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_var, 
                                     values=list(InstrumentProfile.PRESET_PROFILES.keys()),
                                     width=25, state='readonly')
        preset_combo.pack(side=tk.LEFT, padx=5)
        preset_combo.bind('<<ComboboxSelected>>', self.on_preset_select)
        
        apply_preset_btn = ttk.Button(preset_frame, text="Apply Preset", command=self.apply_preset)
        apply_preset_btn.pack(side=tk.LEFT, padx=10)
        
        # Manual editing
        manual_frame = ttk.Frame(edit_frame)
        manual_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(manual_frame, text="Manual Edit:").pack(side=tk.LEFT, padx=5)
        
        ttk.Label(manual_frame, text="Velocity:").pack(side=tk.LEFT, padx=10)
        self.velocity_var = tk.StringVar(value="120")
        velocity_spin = ttk.Spinbox(manual_frame, from_=1, to=127, textvariable=self.velocity_var, width=5)
        velocity_spin.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(manual_frame, text="Timing:").pack(side=tk.LEFT, padx=10)
        self.timing_var = tk.StringVar(value="222")
        timing_spin = ttk.Spinbox(manual_frame, from_=50, to=500, textvariable=self.timing_var, width=5)
        timing_spin.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(manual_frame, text="Duration:").pack(side=tk.LEFT, padx=10)
        self.duration_var = tk.StringVar(value="112")
        duration_spin = ttk.Spinbox(manual_frame, from_=50, to=200, textvariable=self.duration_var, width=5)
        duration_spin.pack(side=tk.LEFT, padx=5)
        
        # Profile string display
        self.profile_string_var = tk.StringVar(value="120.222.112")
        string_frame = ttk.Frame(edit_frame)
        string_frame.pack(fill=tk.X, pady=5)
        ttk.Label(string_frame, text="Profile String:").pack(side=tk.LEFT, padx=5)
        string_entry = ttk.Entry(string_frame, textvariable=self.profile_string_var, width=20)
        string_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(string_frame, text="Parse", command=self.parse_profile_string).pack(side=tk.LEFT, padx=5)
        
        # Action buttons
        btn_frame = ttk.Frame(edit_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="Update Profile", command=self.update_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reset to Default", command=self.reset_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Auto-Detect All", command=self.auto_detect_profiles).pack(side=tk.LEFT, padx=5)
        
        # Status
        self.profile_status_var = tk.StringVar(value="Select an instrument to edit its profile")
        status_label = ttk.Label(self.profiles_tab, textvariable=self.profile_status_var, foreground='blue')
        status_label.pack(pady=5)
    
    def _setup_analysis_tab(self):
        """Setup Analysis tab"""
        # Title
        title_label = ttk.Label(self.analysis_tab, text="MIDI Analysis Results", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Summary frame
        summary_frame = ttk.LabelFrame(self.analysis_tab, text="Summary", padding="10")
        summary_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.summary_text = tk.Text(summary_frame, height=4, wrap=tk.WORD)
        self.summary_text.pack(fill=tk.X)
        
        # Tracks analysis
        tracks_frame = ttk.LabelFrame(self.analysis_tab, text="Track Analysis", padding="10")
        tracks_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Treeview for tracks
        columns = ('track', 'name', 'notes', 'velocity', 'range', 'instrument')
        self.track_tree = ttk.Treeview(tracks_frame, columns=columns, show='headings', height=10)
        
        self.track_tree.heading('track', text='Track')
        self.track_tree.column('track', width=60)
        self.track_tree.heading('name', text='Name')
        self.track_tree.column('name', width=200)
        self.track_tree.heading('notes', text='Notes')
        self.track_tree.column('notes', width=80)
        self.track_tree.heading('velocity', text='Avg Velocity')
        self.track_tree.column('velocity', width=100)
        self.track_tree.heading('range', text='Note Range')
        self.track_tree.column('range', width=120)
        self.track_tree.heading('instrument', text='Detected Instrument')
        self.track_tree.column('instrument', width=200)
        
        self.track_tree.pack(fill=tk.BOTH, expand=True)
        
        # Issues
        issues_frame = ttk.LabelFrame(self.analysis_tab, text="Detected Issues", padding="10")
        issues_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.issues_text = scrolledtext.ScrolledText(issues_frame, height=8, wrap=tk.WORD)
        self.issues_text.pack(fill=tk.BOTH, expand=True)
        
        # Quality score
        self.quality_score_var = tk.StringVar(value="Quality Score: --/100")
        quality_label = ttk.Label(self.analysis_tab, textvariable=self.quality_score_var, 
                                   font=('Arial', 12, 'bold'), foreground='green')
        quality_label.pack(pady=10)
    
    def _setup_optimize_tab(self):
        """Setup Optimization tab"""
        # Title
        title_label = ttk.Label(self.optimize_tab, text="Optimization Settings", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Corpus selection
        corpus_frame = ttk.LabelFrame(self.optimize_tab, text="Select Corpus Rules", padding="10")
        corpus_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.corpus_var = tk.StringVar(value='balanced')
        ttk.Radiobutton(corpus_frame, text="Factory Styles", variable=self.corpus_var, value='factory').pack(side=tk.LEFT, padx=20)
        ttk.Radiobutton(corpus_frame, text="Gold Standards", variable=self.corpus_var, value='gold').pack(side=tk.LEFT, padx=20)
        ttk.Radiobutton(corpus_frame, text="Balanced (Recommended)", variable=self.corpus_var, value='balanced').pack(side=tk.LEFT, padx=20)
        
        # Options
        options_frame = ttk.LabelFrame(self.optimize_tab, text="Optimization Options", padding="10")
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.optimize_velocity = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Optimize Velocities", variable=self.optimize_velocity).pack(side=tk.LEFT, padx=20)
        
        self.optimize_timing = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Optimize Timing", variable=self.optimize_timing).pack(side=tk.LEFT, padx=20)
        
        self.optimize_duration = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Optimize Durations", variable=self.optimize_duration).pack(side=tk.LEFT, padx=20)
        
        self.optimize_density = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Optimize Note Density", variable=self.optimize_density).pack(side=tk.LEFT, padx=20)
        
        # Rules preview
        rules_frame = ttk.LabelFrame(self.optimize_tab, text="Active Rules Preview", padding="10")
        rules_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.rules_text = scrolledtext.ScrolledText(rules_frame, height=12, wrap=tk.WORD)
        self.rules_text.pack(fill=tk.BOTH, expand=True)
        
        # Run button
        run_btn = ttk.Button(self.optimize_tab, text="🚀 Run Optimization", command=self.run_optimization)
        run_btn.pack(pady=20)
        
        # Progress
        self.progress_var = tk.StringVar(value="Ready to optimize")
        progress_label = ttk.Label(self.optimize_tab, textvariable=self.progress_var)
        progress_label.pack(pady=5)
    
    def _setup_export_tab(self):
        """Setup Export tab"""
        # Title
        title_label = ttk.Label(self.export_tab, text="Export Optimized MIDI", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Filename
        filename_frame = ttk.LabelFrame(self.export_tab, text="Output Filename", padding="10")
        filename_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.output_filename_var = tk.StringVar(value="optimized_song.mid")
        filename_entry = ttk.Entry(filename_frame, textvariable=self.output_filename_var, width=60)
        filename_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(filename_frame, text="Browse...", command=self.browse_output).pack(side=tk.LEFT)
        
        # Format options
        format_frame = ttk.LabelFrame(self.export_tab, text="Format Options", padding="10")
        format_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.format_var = tk.StringVar(value='Format 1')
        ttk.Radiobutton(format_frame, text="Format 0 (Single Track)", variable=self.format_var, value='Format 0').pack(side=tk.LEFT, padx=20)
        ttk.Radiobutton(format_frame, text="Format 1 (Multiple Tracks)", variable=self.format_var, value='Format 1').pack(side=tk.LEFT, padx=20)
        
        # Metadata
        meta_frame = ttk.LabelFrame(self.export_tab, text="Metadata", padding="10")
        meta_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(meta_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.meta_title_var = tk.StringVar()
        ttk.Entry(meta_frame, textvariable=self.meta_title_var, width=40).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(meta_frame, text="Artist:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.meta_artist_var = tk.StringVar()
        ttk.Entry(meta_frame, textvariable=self.meta_artist_var, width=40).grid(row=1, column=1, padx=5, pady=5)
        
        # Export log
        log_frame = ttk.LabelFrame(self.export_tab, text="Export Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.export_log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD)
        self.export_log_text.pack(fill=tk.BOTH, expand=True)
        
        # Export button
        export_btn = ttk.Button(self.export_tab, text="💾 Export MIDI File", command=self.export_midi)
        export_btn.pack(pady=20)
    
    def _setup_status_bar(self):
        """Setup status bar"""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # ==================== Event Handlers ====================
    
    def browse_file(self):
        """Browse for MIDI file"""
        filename = filedialog.askopenfilename(
            title="Select MIDI File",
            filetypes=[("MIDI Files", "*.mid *.midi"), ("All Files", "*.*")]
        )
        if filename:
            self.file_path_var.set(filename)
    
    def browse_output(self):
        """Browse for output file location"""
        filename = filedialog.asksaveasfilename(
            title="Save Optimized MIDI",
            defaultextension=".mid",
            filetypes=[("MIDI Files", "*.mid"), ("All Files", "*.*")]
        )
        if filename:
            self.output_filename_var.set(filename)
    
    def on_recent_file_select(self, event):
        """Handle recent file selection"""
        selection = self.recent_listbox.curselection()
        if selection:
            index = selection[0]
            # Would load the selected recent file
            pass
    
    def on_profile_select(self, event):
        """Handle profile selection in treeview"""
        selection = self.profile_tree.selection()
        if selection:
            item = self.profile_tree.item(selection[0])
            values = item['values']
            if len(values) >= 4:
                channel = values[0]
                instrument = values[1]
                profile_str = values[2]
                
                # Parse profile string
                parts = profile_str.split('.')
                if len(parts) == 3:
                    self.velocity_var.set(parts[0])
                    self.timing_var.set(parts[1])
                    self.duration_var.set(parts[2])
                    self.profile_string_var.set(profile_str)
                
                self.profile_status_var.set(f"Editing: {instrument} (Channel {channel})")
    
    def on_preset_select(self, event):
        """Handle preset selection"""
        preset_name = self.preset_var.get()
        if preset_name in InstrumentProfile.PRESET_PROFILES:
            profile = InstrumentProfile.PRESET_PROFILES[preset_name]
            self.velocity_var.set(str(profile['velocity']))
            self.timing_var.set(str(profile['timing']))
            self.duration_var.set(str(profile['duration']))
            self.profile_string_var.set(f"{profile['velocity']}.{profile['timing']}.{profile['duration']}")
    
    def apply_preset(self):
        """Apply selected preset to current instrument"""
        selection = self.profile_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an instrument first")
            return
        
        preset_name = self.preset_var.get()
        if preset_name not in InstrumentProfile.PRESET_PROFILES:
            messagebox.showwarning("Warning", "Please select a valid preset")
            return
        
        item = self.profile_tree.item(selection[0])
        values = item['values']
        channel = int(values[0])
        
        profile = InstrumentProfile(preset_name)
        self.instrument_profiles[channel] = profile
        
        # Update treeview
        self.profile_tree.set(selection[0], 'profile', profile.get_profile_string())
        self.profile_tree.set(selection[0], 'description', profile.profile.get('description', ''))
        
        self.profile_status_var.set(f"Applied preset '{preset_name}' to channel {channel}")
    
    def update_profile(self):
        """Update profile with manual values"""
        selection = self.profile_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an instrument first")
            return
        
        try:
            velocity = int(self.velocity_var.get())
            timing = int(self.timing_var.get())
            duration = int(self.duration_var.get())
            
            item = self.profile_tree.item(selection[0])
            values = item['values']
            channel = int(values[0])
            instrument = values[1]
            
            profile = InstrumentProfile(instrument)
            profile.set_values(velocity, timing, duration)
            self.instrument_profiles[channel] = profile
            
            # Update treeview
            profile_str = profile.get_profile_string()
            self.profile_tree.set(selection[0], 'profile', profile_str)
            self.profile_string_var.set(profile_str)
            
            self.profile_status_var.set(f"Updated profile for channel {channel}: {profile_str}")
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid values: {e}")
    
    def reset_profile(self):
        """Reset profile to default"""
        selection = self.profile_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an instrument first")
            return
        
        item = self.profile_tree.item(selection[0])
        values = item['values']
        channel = int(values[0])
        instrument = values[1]
        
        profile = InstrumentProfile(instrument)
        self.instrument_profiles[channel] = profile
        
        # Update UI
        self.velocity_var.set(str(profile.profile['velocity']))
        self.timing_var.set(str(profile.profile['timing']))
        self.duration_var.set(str(profile.profile['duration']))
        profile_str = profile.get_profile_string()
        self.profile_string_var.set(profile_str)
        self.profile_tree.set(selection[0], 'profile', profile_str)
        
        self.profile_status_var.set(f"Reset profile for channel {channel} to default")
    
    def parse_profile_string(self):
        """Parse profile string into values"""
        profile_str = self.profile_string_var.get()
        try:
            parts = profile_str.split('.')
            if len(parts) == 3:
                velocity = int(parts[0])
                timing = int(parts[1])
                duration = int(parts[2])
                
                self.velocity_var.set(str(velocity))
                self.timing_var.set(str(timing))
                self.duration_var.set(str(duration))
                
                self.profile_status_var.set(f"Parsed: V={velocity}, T={timing}, D={duration}")
            else:
                raise ValueError("Must have 3 parts")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid profile string format. Use: VELOCITY.TIMING.DURATION\nError: {e}")
    
    def auto_detect_profiles(self):
        """Auto-detect and assign profiles to all instruments"""
        if not self.current_midi:
            messagebox.showwarning("Warning", "Please load a MIDI file first")
            return
        
        self.instrument_profiles = {}
        
        # Clear treeview
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)
        
        # Analyze and assign profiles
        analyzer = MIDIAnalyzer()
        stats = analyzer.analyze(self.current_midi)
        
        for inst_info in stats.get('instruments_detected', []):
            channel = inst_info['channel']
            instrument = inst_info['instrument']
            
            # Find matching profile
            profile = InstrumentProfile('Default')
            for preset_name in InstrumentProfile.PRESET_PROFILES:
                if preset_name.lower() in instrument.lower() or instrument.lower() in preset_name.lower():
                    profile = InstrumentProfile(preset_name)
                    break
            
            self.instrument_profiles[channel] = profile
            
            # Add to treeview
            self.profile_tree.insert('', tk.END, values=(
                channel,
                instrument,
                profile.get_profile_string(),
                profile.profile.get('description', '')
            ))
        
        self.profile_status_var.set(f"Auto-detected {len(self.instrument_profiles)} instrument profiles")
        messagebox.showinfo("Success", f"Auto-detected {len(self.instrument_profiles)} instrument profiles")
    
    def load_midi(self):
        """Load MIDI file"""
        if not self.file_path_var.get() or self.file_path_var.get() == "No file selected":
            messagebox.showwarning("Warning", "Please select a MIDI file first")
            return
        
        filepath = self.file_path_var.get()
        
        try:
            self.current_midi = mido.MidiFile(filepath)
            self.current_file_path = filepath
            
            # Add to recent files
            self.recent_listbox.insert(0, filepath)
            
            # Analyze
            self.analyzer = MIDIAnalyzer()
            stats = self.analyzer.analyze(self.current_midi)
            
            # Update analysis tab
            self._update_analysis_display(stats)
            
            # Auto-detect profiles
            self.auto_detect_profiles()
            
            # Update output filename
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            self.output_filename_var.set(f"{base_name}_optimized.mid")
            
            # Switch to analysis tab
            self.notebook.select(2)
            
            self.status_var.set(f"Loaded: {filepath}")
            messagebox.showinfo("Success", f"MIDI file loaded successfully!\n{stats['summary']['total_notes']} notes across {stats['total_tracks']} tracks")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load MIDI file:\n{str(e)}")
    
    def _update_analysis_display(self, stats):
        """Update analysis tab display"""
        # Summary
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, 
            f"File: {stats['filename']}\n"
            f"Tracks: {stats['total_tracks']} | "
            f"Total Notes: {stats['summary']['total_notes']} | "
            f"Duration: {stats['total_time']:.2f}s | "
            f"Ticks/Beat: {stats['ticks_per_beat']}")
        
        # Quality score
        self.quality_score_var.set(f"Quality Score: {stats['quality_score']}/100")
        
        # Tracks
        for item in self.track_tree.get_children():
            self.track_tree.delete(item)
        
        for track in stats['tracks']:
            note_range = f"{track['note_range']['min']}-{track['note_range']['max']}"
            instrument = track.get('detected_instrument', 'Unknown')
            
            self.track_tree.insert('', tk.END, values=(
                track['track_number'],
                track['track_name'][:30],
                track['note_count'],
                f"{track['velocity_avg']:.1f}",
                note_range,
                instrument
            ))
        
        # Issues
        self.issues_text.delete(1.0, tk.END)
        if stats['issues']:
            for issue in stats['issues']:
                self.issues_text.insert(tk.END, 
                    f"[{issue['severity'].upper()}] Track {issue['track']}: {issue['type']}\n"
                    f"  → {issue['description']}\n\n")
        else:
            self.issues_text.insert(tk.END, "No issues detected!")
    
    def run_optimization(self):
        """Run optimization process"""
        if not self.current_midi:
            messagebox.showwarning("Warning", "Please load a MIDI file first")
            return
        
        self.progress_var.set("Starting optimization...")
        self.root.update()
        
        try:
            # Get corpus rules
            corpus_type = self.corpus_var.get()
            rules = self.corpus_rules.get_combined_rules(corpus_type)
            
            # Create optimizer with instrument profiles
            self.optimizer = MIDIOptimizer(rules, self.instrument_profiles)
            
            # Show rules preview
            self.rules_text.delete(1.0, tk.END)
            self.rules_text.insert(tk.END, f"Corpus: {corpus_type.upper()}\n\n")
            self.rules_text.insert(tk.END, json.dumps(rules, indent=2))
            
            self.progress_var.set("Applying instrument profiles...")
            self.root.update()
            
            # Optimize
            optimized_midi = self.optimizer.optimize(self.current_midi)
            
            self.progress_var.set("Optimization complete!")
            
            # Store optimized MIDI
            self.optimized_midi = optimized_midi
            
            # Update export log
            self.export_log_text.delete(1.0, tk.END)
            summary = self.optimizer.get_optimization_summary()
            self.export_log_text.insert(tk.END, f"Optimization Summary:\n")
            self.export_log_text.insert(tk.END, f"Total Changes: {summary['total_changes']}\n\n")
            self.export_log_text.insert(tk.END, "Recent Changes:\n")
            for log_entry in summary['log'][-20:]:
                self.export_log_text.insert(tk.END, f"  • {log_entry}\n")
            
            # Switch to export tab
            self.notebook.select(4)
            
            self.status_var.set("Optimization completed successfully")
            
        except Exception as e:
            self.progress_var.set("Optimization failed!")
            messagebox.showerror("Error", f"Optimization failed:\n{str(e)}")
    
    def save_midi(self):
        """Save MIDI file"""
        if hasattr(self, 'optimized_midi') and self.optimized_midi:
            self.export_midi()
        else:
            messagebox.showinfo("Info", "No optimized MIDI to save. Please run optimization first.")
    
    def export_midi(self):
        """Export optimized MIDI file"""
        if not hasattr(self, 'optimized_midi') or self.optimized_midi is None:
            messagebox.showwarning("Warning", "Please run optimization first")
            return
        
        output_path = self.output_filename_var.get()
        
        try:
            # Save MIDI file
            self.optimized_midi.save(output_path)
            
            # Add metadata if provided
            title = self.meta_title_var.get()
            artist = self.meta_artist_var.get()
            
            # Log export
            self.export_log_text.insert(tk.END, f"\n{'='*50}\n")
            self.export_log_text.insert(tk.END, f"Exported: {output_path}\n")
            self.export_log_text.insert(tk.END, f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if title:
                self.export_log_text.insert(tk.END, f"Title: {title}\n")
            if artist:
                self.export_log_text.insert(tk.END, f"Artist: {artist}\n")
            
            self.status_var.set(f"Exported: {output_path}")
            messagebox.showinfo("Success", f"MIDI file exported successfully!\n\nSaved to:\n{output_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{str(e)}")
    
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About Song MIDI Optimizer",
            "Song MIDI Optimizer v1.0\n\n"
            "A professional MIDI optimization tool based on:\n"
            "• Factory Styles\n"
            "• Gold Standards\n\n"
            "Features:\n"
            "• Instrument Profiles (VELOCITY.TIMING.DURATION)\n"
            "• IMPORT - OPTIMIZE - EXPORT workflow\n"
            "• Comprehensive analysis\n"
            "• Customizable corpus rules\n\n"
            "Each instrument profile uses 3 values:\n"
            "Example: 120.222.112\n"
            "  - Velocity: 120 (target average)\n"
            "  - Timing: 222 (strictness)\n"
            "  - Duration: 112 (duration factor %)")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    root = tk.Tk()
    app = SongMIDIOptimizerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
