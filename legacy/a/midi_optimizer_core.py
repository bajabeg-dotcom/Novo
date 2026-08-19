#!/usr/bin/env python3
"""
KORG PA800 MIDI Optimizer

Optimize MIDI files using Sound Behaviour Models from factory analysis.

Features:
- Analyze MIDI structure
- Apply velocity optimization
- Generate realistic dynamics
- Preserve musicality
- Batch processing
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import struct
from enum import Enum


class OptimizationStrategy(Enum):
    """Optimization approaches"""
    AUTHENTIC = "authentic"      # Use real factory patterns
    EXPRESSIVE = "expressive"    # Emphasize dynamics
    BALANCED = "balanced"        # Conservative optimization
    AGGRESSIVE = "aggressive"    # Maximize character


@dataclass
class MIDINote:
    """MIDI note event"""
    note: int
    velocity: int
    channel: int
    program: int
    start_time: int
    duration: int
    
    def register(self) -> str:
        """Get note register"""
        if self.note < 36:
            return "low"
        elif self.note < 96:
            return "mid"
        else:
            return "high"


@dataclass
class OptimizationResult:
    """Result of optimization"""
    original_velocity: int
    optimized_velocity: int
    reason: str
    confidence: str
    adjustment: int = field(init=False)
    
    def __post_init__(self):
        self.adjustment = self.optimized_velocity - self.original_velocity


class MIDIParser:
    """Parse and write MIDI files"""
    
    @staticmethod
    def read_var_length(data: bytes, offset: int) -> Tuple[int, int]:
        value = 0
        while True:
            byte = data[offset]
            offset += 1
            value = (value << 7) | (byte & 0x7F)
            if not (byte & 0x80):
                break
        return value, offset
    
    @staticmethod
    def write_var_length(value: int) -> bytes:
        """Write variable-length quantity"""
        if value < 128:
            return bytes([value])
        
        # Encode in reverse
        encoded = []
        encoded.append(value & 0x7F)
        value >>= 7
        
        while value > 0:
            encoded.append((value & 0x7F) | 0x80)
            value >>= 7
        
        return bytes(reversed(encoded))
    
    @staticmethod
    def parse_midi_file(path: Path) -> Tuple[List[MIDINote], List[Dict]]:
        """
        Parse MIDI file
        Returns: (note_events, track_metadata)
        """
        notes = []
        metadata = []
        
        try:
            with open(path, 'rb') as f:
                data = f.read()
            
            if data[:4] != b'MThd':
                return [], []
            
            num_tracks = struct.unpack('>H', data[10:12])[0]
            ppq = struct.unpack('>H', data[12:14])[0]
            
            offset = 14
            
            for track_idx in range(num_tracks):
                if offset + 8 > len(data) or data[offset:offset+4] != b'MTrk':
                    break
                
                track_length = struct.unpack('>I', data[offset+4:offset+8])[0]
                offset += 8
                track_end = offset + track_length
                
                # Track state
                active_notes = defaultdict(dict)  # channel -> {note: (start_time, velocity)}
                channel_programs = defaultdict(int)
                running_status = 0
                timestamp = 0
                tempo = 500000  # Default: 120 BPM
                
                while offset < track_end and offset < len(data):
                    delta, offset = MIDIParser.read_var_length(data, offset)
                    timestamp += delta
                    
                    if offset >= track_end:
                        break
                    
                    status = data[offset]
                    offset += 1
                    
                    if status == 0xFF:  # Meta event
                        meta_type = data[offset]
                        offset += 1
                        length, offset = MIDIParser.read_var_length(data, offset)
                        
                        if meta_type == 0x51 and length == 3:  # Tempo
                            tempo = int.from_bytes(data[offset:offset+3], 'big')
                        
                        offset += length
                        continue
                    
                    if status == 0xF0 or status == 0xF7:
                        length, offset = MIDIParser.read_var_length(data, offset)
                        offset += length
                        continue
                    
                    if status & 0x80:
                        running_status = status
                    else:
                        offset -= 1
                        status = running_status
                    
                    channel = status & 0x0F
                    status_type = status & 0xF0
                    
                    if status_type == 0x90:  # Note On
                        if offset + 2 > track_end:
                            break
                        note = data[offset]
                        velocity = data[offset + 1]
                        offset += 2
                        
                        if velocity > 0:
                            active_notes[channel][note] = (timestamp, velocity)
                    
                    elif status_type == 0x80:  # Note Off
                        if offset + 2 > track_end:
                            break
                        note = data[offset]
                        velocity = data[offset + 1]
                        offset += 2
                        
                        if note in active_notes[channel]:
                            start_time, on_velocity = active_notes[channel][note]
                            duration = timestamp - start_time
                            
                            midi_note = MIDINote(
                                note=note,
                                velocity=on_velocity,
                                channel=channel,
                                program=channel_programs[channel],
                                start_time=start_time,
                                duration=duration
                            )
                            notes.append(midi_note)
                            del active_notes[channel][note]
                    
                    elif status_type == 0xC0:  # Program Change
                        if offset + 1 > track_end:
                            break
                        program = data[offset]
                        offset += 1
                        channel_programs[channel] = program
                    
                    elif status_type in [0xB0, 0xE0]:
                        if offset + 2 > track_end:
                            break
                        offset += 2
        
        except Exception as e:
            print(f"Error parsing MIDI: {e}")
        
        return notes, metadata
    
    @staticmethod
    def write_midi_file(notes: List[MIDINote], output_path: Path, ppq: int = 480):
        """Write optimized MIDI file - preserves track structure and order"""
        
        # Group notes by (channel, program) preserving first appearance order
        tracks = {}
        channel_order = []
        
        for note in notes:
            key = (note.channel, note.program)
            if key not in tracks:
                tracks[key] = []
                channel_order.append(key)
            tracks[key].append(note)
        
        # Build MIDI data
        # Header
        midi_data = b'MThd'
        midi_data += struct.pack('>I', 6)  # Header length
        midi_data += struct.pack('>H', 1)  # Format 1
        midi_data += struct.pack('>H', len(channel_order))  # Number of tracks
        midi_data += struct.pack('>H', ppq)  # PPQ
        
        # Tracks in order of first appearance
        for channel, program in channel_order:
            channel_notes = tracks[(channel, program)]
            track_data = b''
            
            # Sort notes by start time within this channel
            channel_notes.sort(key=lambda n: n.start_time)
            
            # Track name
            track_name = f"Channel {channel + 1}".encode()
            track_data += b'\x00\xFF\x03'
            track_data += MIDIParser.write_var_length(len(track_name))
            track_data += track_name
            
            # Program change
            track_data += b'\x00' + bytes([0xC0 | channel, program])
            
            # Notes
            last_time = 0
            for midi_note in channel_notes:
                # Note On
                delta = midi_note.start_time - last_time
                track_data += MIDIParser.write_var_length(delta)
                track_data += bytes([0x90 | channel, midi_note.note, midi_note.velocity])
                
                # Note Off
                delta = midi_note.duration
                track_data += MIDIParser.write_var_length(delta)
                track_data += bytes([0x80 | channel, midi_note.note, 64])
                
                last_time = midi_note.start_time + midi_note.duration
            
            # End of track
            track_data += b'\x00\xFF\x2F\x00'
            
            # Track header
            midi_data += b'MTrk'
            midi_data += struct.pack('>I', len(track_data))
            midi_data += track_data
        
        # Write file
        with open(output_path, 'wb') as f:
            f.write(midi_data)


class SoundBehaviourOptimizer:
    """Optimize MIDI using Sound Behaviour Models"""
    
    def __init__(self, behaviour_db: Dict):
        self.behaviour_db = behaviour_db
    
    def get_sound_behaviour(self, program: int) -> Optional[Dict]:
        """Get behaviour model for program"""
        return self.behaviour_db.get("sound_rules", {}).get(str(program))
    
    def optimize_velocity(self, note: MIDINote, strategy: OptimizationStrategy) -> OptimizationResult:
        """Optimize single note velocity"""
        
        behaviour = self.get_sound_behaviour(note.program)
        
        if not behaviour:
            return OptimizationResult(
                original_velocity=note.velocity,
                optimized_velocity=note.velocity,
                reason="No behaviour model found",
                confidence="UNKNOWN"
            )
        
        # Get role and zones
        role = behaviour.get("role", "unknown")
        zones = behaviour.get("velocity_zones", [])
        
        if not zones:
            return OptimizationResult(
                original_velocity=note.velocity,
                optimized_velocity=note.velocity,
                reason="No velocity zones defined",
                confidence="UNKNOWN"
            )
        
        # Strategy: AUTHENTIC — use zones from factory patterns
        if strategy == OptimizationStrategy.AUTHENTIC:
            optimized = self._optimize_authentic(note, zones, role)
        
        # Strategy: EXPRESSIVE — emphasize dynamics
        elif strategy == OptimizationStrategy.EXPRESSIVE:
            optimized = self._optimize_expressive(note, zones, role)
        
        # Strategy: BALANCED — conservative
        elif strategy == OptimizationStrategy.BALANCED:
            optimized = self._optimize_balanced(note, zones, role)
        
        # Strategy: AGGRESSIVE — maximize character
        elif strategy == OptimizationStrategy.AGGRESSIVE:
            optimized = self._optimize_aggressive(note, zones, role)
        
        else:
            optimized = note.velocity
        
        return OptimizationResult(
            original_velocity=note.velocity,
            optimized_velocity=optimized,
            reason=f"{strategy.value} optimization for {role}",
            confidence="OBSERVED"
        )
    
    def _optimize_authentic(self, note: MIDINote, zones: List[Dict], role: str) -> int:
        """Optimize to match authentic factory patterns"""
        
        # Find matching zone
        for zone in zones:
            zone_range = zone.get("velocity_range", "")
            if "-" in zone_range:
                vel_min, vel_max = map(int, zone_range.split("-"))
                if vel_min <= note.velocity <= vel_max:
                    # Return zone center
                    center = (vel_min + vel_max) // 2
                    return center
        
        # If not in any zone, snap to nearest zone
        distances = []
        for zone in zones:
            zone_range = zone.get("velocity_range", "")
            if "-" in zone_range:
                vel_min, vel_max = map(int, zone_range.split("-"))
                center = (vel_min + vel_max) // 2
                distance = abs(note.velocity - center)
                distances.append((distance, center))
        
        if distances:
            return min(distances, key=lambda x: x[0])[1]
        
        return note.velocity
    
    def _optimize_expressive(self, note: MIDINote, zones: List[Dict], role: str) -> int:
        """Optimize with increased dynamics"""
        
        # Get zone info
        zones_sorted = sorted(zones, key=lambda z: int(z.get("velocity_range", "0-0").split("-")[0]))
        
        if not zones_sorted:
            return note.velocity
        
        # Classify note into soft/normal/strong based on original velocity
        if note.velocity < 45:
            # Make softer
            target_zone = zones_sorted[0]
        elif note.velocity < 95:
            # Make normal
            target_zone = zones_sorted[len(zones_sorted)//2]
        else:
            # Make stronger
            target_zone = zones_sorted[-1]
        
        vel_range = target_zone.get("velocity_range", "")
        if "-" in vel_range:
            vel_min, vel_max = map(int, vel_range.split("-"))
            # Use higher end of zone for more expression
            return int(vel_min + (vel_max - vel_min) * 0.7)
        
        return note.velocity
    
    def _optimize_balanced(self, note: MIDINote, zones: List[Dict], role: str) -> int:
        """Optimize conservatively"""
        
        # Only adjust if significantly off
        for zone in zones:
            zone_range = zone.get("velocity_range", "")
            if "-" in zone_range:
                vel_min, vel_max = map(int, zone_range.split("-"))
                center = (vel_min + vel_max) // 2
                
                # Only adjust if far from center
                if abs(note.velocity - center) > 15:
                    return center
        
        return note.velocity
    
    def _optimize_aggressive(self, note: MIDINote, zones: List[Dict], role: str) -> int:
        """Optimize aggressively"""
        
        zones_sorted = sorted(zones, key=lambda z: int(z.get("velocity_range", "0-0").split("-")[0]))
        
        if not zones_sorted:
            return note.velocity
        
        # Emphasize character more
        if note.velocity < 50:
            # Very soft
            target_zone = zones_sorted[0]
            vel_range = target_zone.get("velocity_range", "")
            if "-" in vel_range:
                vel_min, vel_max = map(int, vel_range.split("-"))
                return vel_min  # Minimum of zone
        
        elif note.velocity < 90:
            # Normal
            target_zone = zones_sorted[len(zones_sorted)//2]
            vel_range = target_zone.get("velocity_range", "")
            if "-" in vel_range:
                vel_min, vel_max = map(int, vel_range.split("-"))
                return int(vel_min + (vel_max - vel_min) * 0.5)
        
        else:
            # Strong
            target_zone = zones_sorted[-1]
            vel_range = target_zone.get("velocity_range", "")
            if "-" in vel_range:
                vel_min, vel_max = map(int, vel_range.split("-"))
                return vel_max  # Maximum of zone
        
        return note.velocity
    
    def optimize_midi(self, notes: List[MIDINote], 
                     strategy: OptimizationStrategy = OptimizationStrategy.AUTHENTIC) -> Tuple[List[MIDINote], List[OptimizationResult]]:
        """Optimize all notes in MIDI"""
        
        optimized_notes = []
        results = []
        
        for note in notes:
            result = self.optimize_velocity(note, strategy)
            
            # Create optimized note
            optimized_note = MIDINote(
                note=note.note,
                velocity=result.optimized_velocity,
                channel=note.channel,
                program=note.program,
                start_time=note.start_time,
                duration=note.duration
            )
            
            optimized_notes.append(optimized_note)
            results.append(result)
        
        return optimized_notes, results


class MIDIOptimizerApp:
    """Main MIDI Optimizer Application"""
    
    def __init__(self, behaviour_db_path: Path):
        self.behaviour_db_path = behaviour_db_path
        self.behaviour_db = self._load_behaviour_db()
        self.optimizer = SoundBehaviourOptimizer(self.behaviour_db)
    
    def _load_behaviour_db(self) -> Dict:
        """Load Sound Behaviour Database"""
        try:
            with open(self.behaviour_db_path) as f:
                return json.load(f)
        except:
            print(f"⚠️  Could not load behaviour database from {self.behaviour_db_path}")
            return {"sound_rules": {}}
    
    def optimize_file(self, input_path: Path, output_path: Path, 
                     strategy: OptimizationStrategy = OptimizationStrategy.AUTHENTIC) -> Dict:
        """Optimize MIDI file"""
        
        print(f"\n🎵 Optimizing: {input_path.name}")
        print(f"   Strategy: {strategy.value}")
        
        # Parse MIDI
        print("   • Parsing MIDI...")
        notes, metadata = MIDIParser.parse_midi_file(input_path)
        
        if not notes:
            print("   ❌ No notes found in MIDI file")
            return {"success": False, "error": "No notes found"}
        
        print(f"   • Found {len(notes)} notes")
        
        # Optimize
        print("   • Optimizing velocities...")
        optimized_notes, results = self.optimizer.optimize_midi(notes, strategy)
        
        # Write output
        print("   • Writing optimized MIDI...")
        MIDIParser.write_midi_file(optimized_notes, output_path)
        
        # Statistics
        total_adjustments = len([r for r in results if r.adjustment != 0])
        avg_adjustment = sum(r.adjustment for r in results) / len(results) if results else 0
        
        print(f"   ✅ Optimization complete!")
        print(f"      Total notes: {len(notes)}")
        print(f"      Adjusted: {total_adjustments} ({total_adjustments*100/len(notes):.1f}%)")
        print(f"      Avg adjustment: {avg_adjustment:.1f}")
        
        return {
            "success": True,
            "input_file": str(input_path),
            "output_file": str(output_path),
            "total_notes": len(notes),
            "adjusted_notes": total_adjustments,
            "average_adjustment": avg_adjustment,
            "strategy": strategy.value
        }
    
    def analyze_file(self, input_path: Path) -> Dict:
        """Analyze MIDI file"""
        
        print(f"\n📊 Analyzing: {input_path.name}")
        
        notes, metadata = MIDIParser.parse_midi_file(input_path)
        
        if not notes:
            return {"error": "No notes found"}
        
        # Statistics
        programs = defaultdict(int)
        velocity_stats = defaultdict(lambda: {"min": 127, "max": 0, "sum": 0, "count": 0})
        registers = defaultdict(int)
        
        for note in notes:
            programs[note.program] += 1
            velocity_stats[note.program]["min"] = min(velocity_stats[note.program]["min"], note.velocity)
            velocity_stats[note.program]["max"] = max(velocity_stats[note.program]["max"], note.velocity)
            velocity_stats[note.program]["sum"] += note.velocity
            velocity_stats[note.program]["count"] += 1
            registers[note.register()] += 1
        
        print(f"   Total notes: {len(notes)}")
        print(f"   Programs used: {len(programs)}")
        print(f"   Registers: {dict(registers)}")
        print("\n   Velocity by Program:")
        
        for prog in sorted(programs.keys()):
            stats = velocity_stats[prog]
            avg = stats["sum"] / stats["count"] if stats["count"] > 0 else 0
            print(f"      Program {prog:3d}: {stats['min']:3d}-{stats['max']:3d} (avg: {avg:6.1f}) [{programs[prog]:5d} notes]")
        
        return {
            "total_notes": len(notes),
            "programs": dict(programs),
            "velocity_stats": {str(k): {
                "min": v["min"],
                "max": v["max"],
                "avg": v["sum"] / v["count"] if v["count"] > 0 else 0
            } for k, v in velocity_stats.items()},
            "registers": dict(registers)
        }


def main():
    print("\n" + "="*70)
    print("KORG PA800 MIDI OPTIMIZER")
    print("="*70)
    
    # Load behaviour database
    db_path = Path("/mnt/user-data/outputs/ai_database.json")
    
    if not db_path.exists():
        print(f"❌ Behaviour database not found: {db_path}")
        return
    
    app = MIDIOptimizerApp(db_path)
    
    # Example: Optimize a test file
    print("\n✅ Application initialized successfully")
    print(f"   Sound Behaviour Database: {db_path.name}")
    print(f"   Ready to optimize MIDI files")
    
    # Show usage
    print("\n📖 Usage:")
    print("   app.optimize_file(input_path, output_path, strategy)")
    print("   app.analyze_file(input_path)")
    print("\nAvailable strategies:")
    print("   - AUTHENTIC: Match factory patterns exactly")
    print("   - EXPRESSIVE: Emphasize dynamics")
    print("   - BALANCED: Conservative adjustments")
    print("   - AGGRESSIVE: Maximize character")


if __name__ == "__main__":
    main()
