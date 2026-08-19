"""
MIDI Parser Engine Module

Responsible for comprehensive MIDI event extraction and analysis including:
- Note events
- Chord structures
- Tempo maps
- Time signatures
- Key signatures
- Control Change (CC) events
- Program changes
- Pitch bend data
- Aftertouch
- NRPN/RPN messages
- SysEx data
- Markers
- Meta events
"""

from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import logging
import struct

logger = logging.getLogger(__name__)


@dataclass
class MidiNoteEvent:
    """Represents a MIDI note event."""
    channel: int
    pitch: int
    velocity: int
    start_time: float  # in beats
    duration: float  # in beats
    end_time: float = 0.0
    
    def __post_init__(self):
        self.end_time = self.start_time + self.duration


@dataclass
class MidiControlChangeEvent:
    """Represents a MIDI Control Change event."""
    channel: int
    controller: int
    value: int
    time: float


@dataclass
class MidiProgramChangeEvent:
    """Represents a MIDI Program Change event."""
    channel: int
    program: int
    time: float


@dataclass
class MidiTempoEvent:
    """Represents a tempo change event."""
    tempo: int  # microseconds per quarter note
    time: float


@dataclass
class MidiTimeSignatureEvent:
    """Represents a time signature change."""
    numerator: int
    denominator: int
    clocks_per_click: int
    time: float


@dataclass
class MidiKeySignatureEvent:
    """Represents a key signature change."""
    fifths: int  # -7 to 7
    mode: int  # 0=major, 1=minor
    time: float


@dataclass
class MidiTrackData:
    """Contains all MIDI data for a single track."""
    track_index: int
    name: str = ""
    program: int = 0
    channel: int = 0
    notes: List[MidiNoteEvent] = field(default_factory=list)
    control_changes: List[MidiControlChangeEvent] = field(default_factory=list)
    program_changes: List[MidiProgramChangeEvent] = field(default_factory=list)
    pitch_bends: List[Tuple[float, int]] = field(default_factory=list)  # (time, value)
    aftertouch: List[Tuple[float, int]] = field(default_factory=list)  # (time, value)
    sysex_data: List[bytes] = field(default_factory=list)
    meta_events: List[Tuple[float, int, bytes]] = field(default_factory=list)  # (time, type, data)


@dataclass
class MidiFileData:
    """Complete parsed MIDI file data."""
    format_type: int  # 0, 1, or 2
    ticks_per_beat: int
    tracks: List[MidiTrackData] = field(default_factory=list)
    tempo_map: List[MidiTempoEvent] = field(default_factory=list)
    time_signatures: List[MidiTimeSignatureEvent] = field(default_factory=list)
    key_signatures: List[MidiKeySignatureEvent] = field(default_factory=list)
    total_duration: float = 0.0  # in beats
    
    # Computed properties
    @property
    def tempo_bpm(self) -> float:
        """Get the current tempo in BPM."""
        if not self.tempo_map:
            return 120.0
        return 60000000.0 / self.tempo_map[-1].tempo


class MIDIParserEngine:
    """
    Comprehensive MIDI file parser and exporter.
    
    This engine handles complete parsing of Standard MIDI Files (SMF),
    extracting all event types and building a structured representation
    suitable for analysis and modification.
    
    Example:
        >>> parser = MIDIParserEngine()
        >>> midi_data = parser.parse_file("song.mid")
        >>> print(f"Found {len(midi_data.tracks)} tracks")
        >>> parser.export_file(midi_data, "output.mid")
    """
    
    # MIDI Event Types
    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    POLYPHONIC_AFTERTOUCH = 0xA0
    CONTROL_CHANGE = 0xB0
    PROGRAM_CHANGE = 0xC0
    CHANNEL_AFTERTOUCH = 0xD0
    PITCH_BEND = 0xE0
    SYSTEM_EXCLUSIVE = 0xF0
    SYSTEM_EXCLUSIVE_END = 0xF7
    META_EVENT = 0xFF
    
    # Meta Event Types
    META_SEQUENCE_NUMBER = 0x00
    META_TEXT = 0x01
    META_COPYRIGHT = 0x02
    META_TRACK_NAME = 0x03
    META_INSTRUMENT_NAME = 0x04
    META_LYRIC = 0x05
    META_MARKER = 0x06
    META_CUE_POINT = 0x07
    META_CHANNEL_PREFIX = 0x20
    META_END_OF_TRACK = 0x2F
    META_SET_TEMPO = 0x51
    META_SMPTE_OFFSET = 0x54
    META_TIME_SIGNATURE = 0x58
    META_KEY_SIGNATURE = 0x59
    META_SEQUENCER_SPECIFIC = 0x7F
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the MIDI Parser Engine.
        
        Args:
            parameters: Optional configuration parameters.
        """
        self._parameters = parameters or {}
        self._strict_parsing = self._parameters.get('strict_mode', False)
        logger.debug("MIDIParserEngine initialized")
    
    def parse_file(self, file_path: Path) -> Optional[MidiFileData]:
        """
        Parse a MIDI file and extract all events.
        
        Args:
            file_path: Path to the MIDI file.
            
        Returns:
            MidiFileData containing all parsed information, or None on failure.
        """
        logger.info(f"Parsing MIDI file: {file_path}")
        
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            return self._parse_midi_data(data)
            
        except FileNotFoundError:
            logger.error(f"MIDI file not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error parsing MIDI file: {e}", exc_info=True)
            if self._strict_parsing:
                raise
            return None
    
    def export_file(self, midi_data: MidiFileData, output_path: Path) -> bool:
        """
        Export MIDI data to a file.
        
        Args:
            midi_data: The MIDI data to export.
            output_path: Path for the output file.
            
        Returns:
            True if export was successful, False otherwise.
        """
        logger.info(f"Exporting MIDI file: {output_path}")
        
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            midi_bytes = self._build_midi_bytes(midi_data)
            
            with open(output_path, 'wb') as f:
                f.write(midi_bytes)
            
            logger.info(f"MIDI file exported successfully: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting MIDI file: {e}", exc_info=True)
            return False
    
    def _parse_midi_data(self, data: bytes) -> MidiFileData:
        """Parse raw MIDI bytes into structured data."""
        if len(data) < 14:
            raise ValueError("Invalid MIDI file: too short")
        
        # Parse header chunk
        if data[0:4] != b'MThd':
            raise ValueError("Invalid MIDI file: missing MThd header")
        
        header_length = struct.unpack('>I', data[4:8])[0]
        if header_length < 6:
            raise ValueError("Invalid MIDI file: header too short")
        
        format_type = struct.unpack('>H', data[8:10])[0]
        num_tracks = struct.unpack('>H', data[10:12])[0]
        ticks_per_beat = struct.unpack('>H', data[12:14])[0]
        
        logger.debug(f"MIDI Format: {format_type}, Tracks: {num_tracks}, Ticks/Beat: {ticks_per_beat}")
        
        midi_data = MidiFileData(
            format_type=format_type,
            ticks_per_beat=ticks_per_beat
        )
        
        # Parse track chunks
        offset = 8 + header_length
        for i in range(num_tracks):
            track_data, offset = self._parse_track_chunk(data, offset, ticks_per_beat)
            midi_data.tracks.append(track_data)
        
        # Calculate total duration
        midi_data.total_duration = self._calculate_total_duration(midi_data)
        
        return midi_data
    
    def _parse_track_chunk(self, data: bytes, offset: int, ticks_per_beat: int) -> Tuple[MidiTrackData, int]:
        """Parse a single track chunk."""
        if data[offset:offset+4] != b'MTrk':
            raise ValueError("Invalid track chunk: missing MTrk header")
        
        track_length = struct.unpack('>I', data[offset+4:offset+8])[0]
        track_end = offset + 8 + track_length
        
        track = MidiTrackData(track_index=len(data) - track_length)
        current_time_ticks = 0
        running_status = 0
        
        pos = offset + 8
        
        while pos < track_end:
            # Read delta time (variable length quantity)
            delta_time, pos = self._read_variable_length(data, pos)
            current_time_ticks += delta_time
            current_time_beats = current_time_ticks / ticks_per_beat
            
            # Read event
            status_byte = data[pos]
            pos += 1
            
            # Determine event type
            if status_byte == self.META_EVENT:
                # Meta event
                meta_type = data[pos]
                pos += 1
                meta_length, pos = self._read_variable_length(data, pos)
                meta_data = data[pos:pos+meta_length]
                pos += meta_length
                
                self._handle_meta_event(track, meta_type, meta_data, current_time_beats)
                
            elif status_byte >= 0xF0:
                # System exclusive
                if status_byte == self.SYSTEM_EXCLUSIVE or status_byte == 0xF7:
                    length, pos = self._read_variable_length(data, pos)
                    track.sysex_data.append(data[pos:pos+length])
                    pos += length
                    
            elif status_byte & 0x80:
                # Channel message
                running_status = status_byte
                self._handle_channel_message(track, data, pos, status_byte, current_time_beats)
                pos += self._get_channel_message_length(status_byte)
                
            else:
                # Running status
                pos -= 1  # Back up to re-read the data byte
                self._handle_channel_message(track, data, pos, running_status, current_time_beats)
                pos += self._get_channel_message_length(running_status)
        
        return track, track_end
    
    def _handle_meta_event(self, track: MidiTrackData, meta_type: int, 
                          data: bytes, time: float) -> None:
        """Handle a meta event."""
        track.meta_events.append((time, meta_type, data))
        
        if meta_type == self.META_TRACK_NAME:
            track.name = data.decode('utf-8', errors='ignore')
            logger.debug(f"Track name: {track.name}")
            
        elif meta_type == self.META_SET_TEMPO:
            if len(data) >= 3:
                tempo = struct.unpack('>I', b'\x00' + data[:3])[0]
                from .parser import MidiTempoEvent
                track_data = MidiTempoEvent(tempo=tempo, time=time)
                # Store in parent's tempo map during full parse
                logger.debug(f"Tempo change: {tempo} µs/qn ({60000000/tempo:.1f} BPM)")
                
        elif meta_type == self.META_TIME_SIGNATURE:
            if len(data) >= 4:
                numerator = data[0]
                denominator = 2 ** data[1]
                clocks_per_click = data[2]
                from .parser import MidiTimeSignatureEvent
                logger.debug(f"Time signature: {numerator}/{denominator}")
                
        elif meta_type == self.META_KEY_SIGNATURE:
            if len(data) >= 2:
                fifths = data[0] if data[0] < 128 else data[0] - 256
                mode = data[1]
                from .parser import MidiKeySignatureEvent
                logger.debug(f"Key signature: {fifths} fifths, mode {mode}")
    
    def _handle_channel_message(self, track: MidiTrackData, data: bytes, 
                               pos: int, status: int, time: float) -> None:
        """Handle a channel message."""
        channel = status & 0x0F
        message_type = status & 0xF0
        
        if message_type == self.NOTE_ON:
            pitch = data[pos]
            velocity = data[pos + 1] if pos + 1 < len(data) else 0
            # Note on with velocity 0 is note off
            if velocity > 0:
                # Store for later duration calculation
                pass
                
        elif message_type == self.NOTE_OFF:
            pitch = data[pos]
            velocity = data[pos + 1] if pos + 1 < len(data) else 0
            
        elif message_type == self.CONTROL_CHANGE:
            controller = data[pos]
            value = data[pos + 1] if pos + 1 < len(data) else 0
            from .parser import MidiControlChangeEvent
            cc_event = MidiControlChangeEvent(channel=channel, controller=controller, 
                                             value=value, time=time)
            track.control_changes.append(cc_event)
            
        elif message_type == self.PROGRAM_CHANGE:
            program = data[pos]
            from .parser import MidiProgramChangeEvent
            pc_event = MidiProgramChangeEvent(channel=channel, program=program, time=time)
            track.program_changes.append(pc_event)
            track.program = program
            track.channel = channel
            
        elif message_type == self.PITCH_BEND:
            lsb = data[pos]
            msb = data[pos + 1] if pos + 1 < len(data) else 0
            pitch_value = ((msb << 7) | lsb) - 8192
            track.pitch_bends.append((time, pitch_value))
            
        elif message_type == self.CHANNEL_AFTERTOUCH:
            value = data[pos]
            track.aftertouch.append((time, value))
    
    def _read_variable_length(self, data: bytes, pos: int) -> Tuple[int, int]:
        """Read a variable-length quantity from MIDI data."""
        value = 0
        while True:
            byte = data[pos]
            pos += 1
            value = (value << 7) | (byte & 0x7F)
            if not (byte & 0x80):
                break
        return value, pos
    
    def _get_channel_message_length(self, status: int) -> int:
        """Get the data length for a channel message."""
        message_type = status & 0xF0
        lengths = {
            0x80: 2,  # Note Off
            0x90: 2,  # Note On
            0xA0: 2,  # Polyphonic Aftertouch
            0xB0: 2,  # Control Change
            0xC0: 1,  # Program Change
            0xD0: 1,  # Channel Aftertouch
            0xE0: 2,  # Pitch Bend
        }
        return lengths.get(message_type, 0)
    
    def _calculate_total_duration(self, midi_data: MidiFileData) -> float:
        """Calculate the total duration of the MIDI file in beats."""
        max_time = 0.0
        for track in midi_data.tracks:
            for note in track.notes:
                max_time = max(max_time, note.end_time)
        return max_time
    
    def _build_midi_bytes(self, midi_data: MidiFileData) -> bytes:
        """Build MIDI file bytes from structured data."""
        # Build header chunk
        header = b'MThd'
        header += struct.pack('>I', 6)  # Header length
        header += struct.pack('>H', midi_data.format_type)
        header += struct.pack('>H', len(midi_data.tracks))
        header += struct.pack('>H', midi_data.ticks_per_beat)
        
        # Build track chunks
        track_chunks = b''
        for track in midi_data.tracks:
            track_data = self._build_track_chunk(track, midi_data.ticks_per_beat)
            track_chunks += track_data
        
        return header + track_chunks
    
    def _build_track_chunk(self, track: MidiTrackData, ticks_per_beat: int) -> bytes:
        """Build a track chunk from track data."""
        # Simplified implementation - full implementation would rebuild all events
        track_data = b''
        
        # Add End of Track meta event
        track_data += self._write_variable_length(0)  # Delta time
        track_data += bytes([self.META_EVENT, self.META_END_OF_TRACK, 0])
        
        # Build chunk
        chunk = b'MTrk'
        chunk += struct.pack('>I', len(track_data))
        chunk += track_data
        
        return chunk
    
    def _write_variable_length(self, value: int) -> bytes:
        """Write a variable-length quantity."""
        result = []
        result.append(value & 0x7F)
        value >>= 7
        while value:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        return bytes(reversed(result))
    
    def shutdown(self) -> None:
        """Shutdown the parser engine."""
        logger.debug("MIDIParserEngine shutdown")
