#!/usr/bin/env python3
"""Generate 252 synthetic Factory Style MIDI files for testing."""

import mido
from pathlib import Path
import random

random.seed(42)  # For reproducibility

output_dir = Path("/workspace/data/factory/Factory Styles")
output_dir.mkdir(parents=True, exist_ok=True)

# Create 252 synthetic Factory Style MIDI files for testing
for i in range(1, 253):
    style_name = f"Style_{i:03d}"
    
    # Create a multi-track MIDI file (type 1)
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    
    # Track 0: Conductor track with tempo and time signature
    track0 = mido.MidiTrack()
    track0.append(mido.MetaMessage('set_tempo', tempo=500000))  # 120 BPM
    track0.append(mido.MetaMessage('time_signature', numerator=4, denominator=4))
    track0.append(mido.MetaMessage('track_name', name=f"{style_name} - Conductor"))
    track0.append(mido.MetaMessage('end_of_track'))
    mid.tracks.append(track0)
    
    # Track 1: Drum track (channel 10)
    track1 = mido.MidiTrack()
    track1.append(mido.MetaMessage('track_name', name=f"{style_name} - Drums"))
    track1.append(mido.Message('program_change', channel=9, program=0))
    
    # Add some drum patterns
    for beat in range(0, 16):  # 4 bars of 4/4
        # Kick on 1 and 3
        if beat % 4 in [0, 2]:
            track1.append(mido.Message('note_on', channel=9, note=36, velocity=100, time=0))
            track1.append(mido.Message('note_off', channel=9, note=36, velocity=0, time=120))
        # Snare on 2 and 4
        if beat % 4 in [1, 3]:
            track1.append(mido.Message('note_on', channel=9, note=38, velocity=90, time=0))
            track1.append(mido.Message('note_off', channel=9, note=38, velocity=0, time=120))
        # Hi-hat every 8th note
        track1.append(mido.Message('note_on', channel=9, note=42, velocity=70 + random.randint(0, 20), time=0))
        track1.append(mido.Message('note_off', channel=9, note=42, velocity=0, time=240))
    
    track1.append(mido.MetaMessage('end_of_track'))
    mid.tracks.append(track1)
    
    # Track 2: Bass track (channel 1)
    track2 = mido.MidiTrack()
    track2.append(mido.MetaMessage('track_name', name=f"{style_name} - Bass"))
    track2.append(mido.Message('program_change', channel=1, program=32))  # Electric Bass
    
    # Simple bass pattern
    for bar in range(4):
        for beat in range(4):
            if beat == 0:
                track2.append(mido.Message('note_on', channel=1, note=36 + random.randint(0, 12), velocity=80 + random.randint(0, 30), time=0))
                track2.append(mido.Message('note_off', channel=1, note=36 + random.randint(0, 12), velocity=0, time=480))
            elif beat == 2:
                track2.append(mido.Message('note_on', channel=1, note=36 + random.randint(0, 12), velocity=75 + random.randint(0, 25), time=0))
                track2.append(mido.Message('note_off', channel=1, note=36 + random.randint(0, 12), velocity=0, time=480))
            else:
                track2.append(mido.Message('note_on', channel=1, note=0, velocity=0, time=0))
                track2.append(mido.Message('note_off', channel=1, note=0, velocity=0, time=480))
    
    track2.append(mido.MetaMessage('end_of_track'))
    mid.tracks.append(track2)
    
    # Track 3: Chord/Piano track (channel 2)
    track3 = mido.MidiTrack()
    track3.append(mido.MetaMessage('track_name', name=f"{style_name} - Piano"))
    track3.append(mido.Message('program_change', channel=2, program=0))  # Grand Piano
    
    # Simple chord pattern
    for bar in range(4):
        for beat in range(4):
            if beat == 0:
                # Play a chord
                root = 48 + random.randint(0, 24)
                for interval in [0, 4, 7]:  # Major triad
                    track3.append(mido.Message('note_on', channel=2, note=root + interval, velocity=70 + random.randint(0, 30), time=0))
                track3.append(mido.Message('note_off', channel=2, note=root, velocity=0, time=480))
                track3.append(mido.Message('note_off', channel=2, note=root+4, velocity=0, time=0))
                track3.append(mido.Message('note_off', channel=2, note=root+7, velocity=0, time=0))
            else:
                track3.append(mido.Message('note_on', channel=2, note=0, velocity=0, time=0))
                track3.append(mido.Message('note_off', channel=2, note=0, velocity=0, time=480))
    
    track3.append(mido.MetaMessage('end_of_track'))
    mid.tracks.append(track3)
    
    # Save the file
    output_path = output_dir / f"{style_name}.mid"
    mid.save(str(output_path))

print(f"Created 252 synthetic Factory Style MIDI files in {output_dir}")
