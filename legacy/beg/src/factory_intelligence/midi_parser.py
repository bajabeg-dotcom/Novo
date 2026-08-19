"""
KORG PA800 Factory Intelligence - MIDI Parser

Robust MIDI file parser that preserves raw event ordering and all MIDI data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import mido

from .models import MidiEvent, NoteEvent


logger = logging.getLogger(__name__)


def midi_file_to_messages(file_path: Path) -> mido.MidiFile:
    """Load a MIDI file and return the mido MidiFile object."""
    try:
        return mido.MidiFile(str(file_path))
    except Exception as e:
        logger.error(f"Failed to load MIDI file {file_path}: {e}")
        raise


def extract_track_name(track: mido.MidiTrack) -> str | None:
    """Extract track name from meta events."""
    for msg in track:
        if msg.type == "track_name":
            return msg.name
    return None


def parse_midi_events(
    track: mido.MidiTrack,
    track_index: int,
    ticks_per_beat: int
) -> tuple[list[MidiEvent], list[NoteEvent]]:
    """
    Parse all MIDI events from a track.
    
    Args:
        track: The mido track to parse
        track_index: Index of the track (0-based)
        ticks_per_beat: PPQN value for time calculations
    
    Returns:
        Tuple of (all_events, note_events)
        - all_events: List of all MidiEvent objects
        - note_events: List of complete NoteEvent objects (on+off pairs)
    """
    all_events: list[MidiEvent] = []
    note_events: list[NoteEvent] = []
    
    # Track active notes for pairing on/off events
    # Key: (channel, note), Value: (absolute_tick, delta_tick, velocity)
    active_notes: dict[tuple[int, int], tuple[int, int, int]] = {}
    
    absolute_tick = 0
    
    for msg in track:
        delta_tick = msg.time if hasattr(msg, 'time') else 0
        absolute_tick += delta_tick
        
        event_type = msg.type
        
        # Extract common properties
        channel = getattr(msg, 'channel', None)
        note = getattr(msg, 'note', None)
        velocity = getattr(msg, 'velocity', None)
        
        # Build event data based on type
        data: tuple[int, ...] = ()
        raw_bytes = b""
        
        if event_type == "note_on":
            if velocity > 0:
                # Start of a note
                key = (channel or 0, note or 0)
                active_notes[key] = (absolute_tick, delta_tick, velocity)
            else:
                # note_on with velocity 0 is actually note_off
                event_type = "note_off"
                velocity = 0
                # Try to find matching note_on
                key = (channel or 0, note or 0)
                if key in active_notes:
                    start_tick, start_delta, start_vel = active_notes.pop(key)
                    duration = absolute_tick - start_tick
                    note_event = NoteEvent(
                        absolute_tick=start_tick,
                        delta_tick=start_delta,
                        channel=channel or 0,
                        note=note or 0,
                        velocity=start_vel,
                        duration_ticks=duration,
                        end_tick=absolute_tick
                    )
                    note_events.append(note_event)
        
        elif event_type == "note_off":
            # Try to find matching note_on
            key = (channel or 0, note or 0)
            if key in active_notes:
                start_tick, start_delta, start_vel = active_notes.pop(key)
                duration = absolute_tick - start_tick
                note_event = NoteEvent(
                    absolute_tick=start_tick,
                    delta_tick=start_delta,
                    channel=channel or 0,
                    note=note or 0,
                    velocity=start_vel,
                    duration_ticks=duration,
                    end_tick=absolute_tick
                )
                note_events.append(note_event)
        
        elif event_type == "control_change":
            cc_number = getattr(msg, 'control', 0)
            cc_value = getattr(msg, 'value', 0)
            data = (cc_number, cc_value)
        
        elif event_type == "program_change":
            program = getattr(msg, 'program', 0)
            data = (program,)
        
        elif event_type == "pitchwheel":
            pitch = getattr(msg, 'pitch', 0)
            data = (pitch,)
        
        elif event_type == "aftertouch":
            value = getattr(msg, 'value', 0)
            data = (value,)
        
        elif event_type == "polytouch":
            note_val = getattr(msg, 'note', 0)
            value = getattr(msg, 'value', 0)
            data = (note_val, value)
        
        elif event_type == "sysex":
            raw_bytes = bytes(getattr(msg, 'data', []))
        
        elif event_type == "set_tempo":
            tempo = getattr(msg, 'tempo', 500000)
            data = (tempo,)
        
        elif event_type == "time_signature":
            data = (msg.numerator, msg.denominator, msg.clocks_per_click, msg.notated_32nd_notes_per_beat)
        
        elif event_type == "key_signature":
            data = (msg.key, msg.minor)
        
        # Create MidiEvent
        midi_event = MidiEvent(
            absolute_tick=absolute_tick,
            delta_tick=delta_tick,
            event_type=event_type,
            channel=channel,
            note=note,
            velocity=velocity,
            data=data,
            raw_bytes=raw_bytes
        )
        all_events.append(midi_event)
    
    # Handle any remaining active notes (notes without off events)
    for key, (start_tick, start_delta, start_vel) in active_notes.items():
        note_event = NoteEvent(
            absolute_tick=start_tick,
            delta_tick=start_delta,
            channel=key[0],
            note=key[1],
            velocity=start_vel,
            duration_ticks=0,  # Unknown duration
            end_tick=start_tick
        )
        note_events.append(note_event)
    
    return all_events, note_events


def get_tempo_bpm(midi_file: mido.MidiFile) -> float | None:
    """Extract tempo in BPM from MIDI file."""
    # Look for set_tempo meta events in any track
    for track in midi_file.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                # Tempo is in microseconds per quarter note
                tempo_us = msg.tempo
                bpm = 60000000 / tempo_us
                return bpm
    return None


def get_duration_ticks(midi_file: mido.MidiFile) -> int:
    """Get the total duration of the MIDI file in ticks."""
    max_tick = 0
    for track in midi_file.tracks:
        current_tick = 0
        for msg in track:
            current_tick += msg.time if hasattr(msg, 'time') else 0
        if current_tick > max_tick:
            max_tick = current_tick
    return max_tick


def parse_midi_file(file_path: Path) -> dict[str, Any]:
    """
    Parse a complete MIDI file and extract all information.
    
    Args:
        file_path: Path to the MIDI file
    
    Returns:
        Dictionary containing parsed MIDI data
    """
    midi_file = midi_file_to_messages(file_path)
    
    result = {
        "file_path": str(file_path),
        "filename": file_path.name,
        "midi_type": midi_file.type,
        "ticks_per_beat": midi_file.ticks_per_beat,
        "track_count": len(midi_file.tracks),
        "duration_ticks": get_duration_ticks(midi_file),
        "tempo_bpm": get_tempo_bpm(midi_file),
        "tracks": []
    }
    
    for track_index, track in enumerate(midi_file.tracks):
        track_name = extract_track_name(track)
        all_events, note_events = parse_midi_events(track, track_index, midi_file.ticks_per_beat)
        
        # Count event types
        event_counts: dict[str, int] = {}
        channels: set[int] = set()
        program_changes: list[tuple[int, int]] = []
        control_changes: dict[int, list[tuple[int, int]]] = {}
        pitch_bends: list[tuple[int, int]] = []
        aftertouch_count = 0
        polytouch_count = 0
        sysex_count = 0
        meta_events: list[tuple[str, Any]] = []
        sysex_data: list[bytes] = []
        
        for event in all_events:
            # Count by type
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
            
            # Collect channels
            if event.channel is not None:
                channels.add(event.channel)
            
            # Program changes
            if event.event_type == "program_change" and event.data:
                program_changes.append((event.absolute_tick, event.data[0]))
            
            # Control changes
            if event.event_type == "control_change" and len(event.data) >= 2:
                cc_num, cc_val = event.data[0], event.data[1]
                if cc_num not in control_changes:
                    control_changes[cc_num] = []
                control_changes[cc_num].append((event.absolute_tick, cc_val))
            
            # Pitch bends
            if event.event_type == "pitchwheel" and event.data:
                pitch_bends.append((event.absolute_tick, event.data[0]))
            
            # Aftertouch
            if event.event_type == "aftertouch":
                aftertouch_count += 1
            
            # Polytouch
            if event.event_type == "polytouch":
                polytouch_count += 1
            
            # SysEx
            if event.event_type == "sysex":
                sysex_count += 1
                if event.raw_bytes:
                    sysex_data.append(event.raw_bytes)
            
            # Meta events
            if event.event_type.startswith("meta_") or event.event_type in [
                "track_name", "set_tempo", "time_signature", "key_signature",
                "marker", "text", "copyright", "sequencer_specific"
            ]:
                meta_events.append((event.event_type, event.data))
        
        # Calculate absolute tick length
        absolute_tick_length = max((e.absolute_tick for e in all_events), default=0)
        
        track_data = {
            "track_index": track_index,
            "track_name": track_name,
            "event_count": len(all_events),
            "note_count": len(note_events),
            "channels": channels,
            "program_changes": program_changes,
            "control_changes": control_changes,
            "pitch_bends": pitch_bends,
            "aftertouch_count": aftertouch_count,
            "polytouch_count": polytouch_count,
            "sysex_count": sysex_count,
            "meta_events": meta_events,
            "absolute_tick_length": absolute_tick_length,
            "events": all_events,
            "notes": note_events,
            "sysex_data": sysex_data,
            "event_counts": event_counts
        }
        
        result["tracks"].append(track_data)
    
    return result
