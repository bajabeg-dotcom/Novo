"""
RX Smart Mapper & Articulation Injector
Ovaj modul prevodi DNA profile u stvarne MIDI poruke:
1. Bank Select MSB/LSB + Program Change za tačan RX zvuk.
2. Key Switches (KS) ili CC poruke za artikulacije (Staccato, Legato, Trill).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import mido

# --- KONFIGURACIJA ROLAND RX BAZE (PRIMJER ZA FANTOM/GROM) ---
# Format: { General_MIDI_Broj: (MSB, LSB, Program_Number, Ime) }
RX_SOUND_MAP = {
    # PIANOS
    1: (0x00, 0x00, 0x00, "Concert Grand"),      # Acoustic Piano -> RX Concert
    2: (0x00, 0x00, 0x01, "Bright Grand"),       # Bright Piano
    4: (0x00, 0x00, 0x04, "Electric Piano 1"),   # E.Piano 1 -> RX MkI
    5: (0x00, 0x00, 0x05, "Chorus Electric"),    # E.Piano 2 -> RX MkII Chorus
    
    # STRINGS
    40: (0x01, 0x00, 0x00, "Violin Solo"),       # Violin
    41: (0x01, 0x00, 0x01, "Viola"),             # Viola
    42: (0x01, 0x00, 0x02, "Cello Solo"),        # Cello
    43: (0x01, 0x00, 0x03, "Contrabass"),        # Double Bass
    44: (0x01, 0x00, 0x04, "Harp"),              # Harp
    
    # GUITARS
    24: (0x02, 0x00, 0x00, "Nylon Guitar"),      # Acoustic Guitar (Nylon)
    25: (0x02, 0x00, 0x01, "Steel Guitar"),      # Acoustic Guitar (Steel)
    26: (0x02, 0x00, 0x02, "Electric Jazz"),     # Electric Guitar (Jazz)
    27: (0x02, 0x00, 0x03, "Electric Clean"),    # Electric Guitar (Clean)
    28: (0x02, 0x00, 0x04, "Muted Guitar"),      # Muted Guitar
    29: (0x02, 0x00, 0x05, "Overdrive Guitar"),  # Overdriven Guitar
    
    # BASSES
    32: (0x03, 0x00, 0x00, "Acoustic Bass"),     # Acoustic Bass
    33: (0x03, 0x00, 0x01, "Finger Bass"),       # Electric Bass (Finger)
    34: (0x03, 0x00, 0x02, "Pick Bass"),         # Electric Bass (Pick)
    35: (0x03, 0x00, 0x03, "Fretless Bass"),     # Fretless Bass
    36: (0x03, 0x00, 0x04, "Slap Bass 1"),       # Slap Bass 1
    37: (0x03, 0x00, 0x05, "Slap Bass 2"),       # Slap Bass 2
    38: (0x03, 0x00, 0x06, "Synth Bass 1"),      # Synth Bass 1
    
    # SYNTH LEADS & PAD
    80: (0x04, 0x00, 0x00, "Square Lead"),       # Square Lead
    81: (0x04, 0x00, 0x01, "Sawtooth Lead"),     # Sawtooth Lead
    88: (0x04, 0x00, 0x08, "Fantasia Pad"),      # Fantasia
    89: (0x04, 0x00, 0x09, "Warm Pad"),          # Warm Pad
    
    # DRUMS (Channel 10 special handling)
    128: (0x7F, 0x00, 0x00, "Standard Kit"),     # Standard Drum Kit
}

# --- ARTIKULACIJE (KEY SWITCHES & CC) ---
# Ključni switchevi su note ispod C1 (obično C0 do B0) koje mijenjaju način sviranja
# Format: { Articulacija_Ime: (Note_Number, Velocity, Duration_ticks) }
ARTICULATION_MAP = {
    # STRINGS ARTICULATIONS
    "staccato": {"type": "keyswitch", "note": 36, "vel": 80},   # C1 (primjer)
    "legato": {"type": "keyswitch", "note": 37, "vel": 80},    # C#1
    "spiccato": {"type": "keyswitch", "note": 38, "vel": 90},  # D1
    "tremolo": {"type": "keyswitch", "note": 39, "vel": 70},   # D#1
    "pizzicato": {"type": "keyswitch", "note": 40, "vel": 100},# E1
    "sustain": {"type": "keyswitch", "note": 41, "vel": 60},   # F1
    
    # GUITAR ARTICULATIONS
    "hammer_on": {"type": "cc", "cc": 80, "val": 127},         # CC80 Hammer
    "pull_off": {"type": "cc", "cc": 81, "val": 127},          # CC81 Pull-off
    "slide_up": {"type": "cc", "cc": 82, "val": 127},          # CC82 Slide Up
    "mute": {"type": "keyswitch", "note": 35, "vel": 50},      # B0 Mute
    
    # WIND/BRASS
    "flutter_tongue": {"type": "cc", "cc": 85, "val": 100},
    "fall": {"type": "cc", "cc": 86, "val": 127},
    
    # DEFAULT (Ako nema specifične artikulacije)
    "normal": {"type": "none"}
}

@dataclass
class RxConfig:
    """Konfiguracija za RX Engine"""
    use_bank_select: bool = True
    use_keyswitches: bool = True
    keyswitch_octave: int = 0  # Oktava gdje živu keyswitchi (0 = C0-B0)
    debug_mode: bool = False

class RxArticulationInjector:
    """
    Ubacuje RX zvukove i Artikulacije u MIDI stream.
    Radi se 'in-place' na listi trackova.
    """
    
    def __init__(self, config: Optional[RxConfig] = None):
        self.config = config or RxConfig()
        self.stats = {"programs_changed": 0, "articulations_injected": 0}

    def inject_rx_sounds(self, tracks: List[mido.MidiTrack], dna_profiles: Dict[int, dict]) -> List[mido.MidiTrack]:
        """
        1. Analizira trackove da nađe instrumente.
        2. Ubacuje Bank Select + Program Change na početak tracka.
        3. Zamjenjuje originalni Program Change sa RX verzijom.
        """
        for track_idx, track in enumerate(tracks):
            # Preskoči perkusije (Channel 10) za sada, imaju poseban tretman
            channel = self._detect_channel(track)
            if channel == 9: # Channel 10 (0-indexed)
                continue
                
            # Probaj naći program iz DNA profila ako postoji
            program_number = None
            original_pc_index = -1
            
            # Heuristika: Uzmi prvi Program Change iz originalnog MIDI-a
            for i, msg in enumerate(track):
                if msg.type == 'program_change':
                    program_number = msg.program
                    original_pc_index = i
                    break
            
            if program_number is None:
                program_number = 0 # Default Piano
            
            # Nađi RX ekvivalent
            rx_data = RX_SOUND_MAP.get(program_number)
            
            if rx_data:
                msb, lsb, prog, name = rx_data
                
                # Kreiraj nove poruke
                new_msgs = []
                if self.config.use_bank_select:
                    new_msgs.append(mido.Message('control_change', control=0, value=msb, time=0, channel=channel))
                    new_msgs.append(mido.Message('control_change', control=32, value=lsb, time=0, channel=channel))
                
                new_msgs.append(mido.Message('program_change', program=prog, time=0, channel=channel))
                
                # Ubaci NA POČETAK (indeks 0), prije svega
                for i, msg in enumerate(reversed(new_msgs)):
                    track.insert(0, msg)
                
                # Optional: Ukloni originalni Program Change ako želimo čistoću
                # Za sada ga ostavljamo jer neki DAW-ovi očekuju PC na početku
                
                self.stats["programs_changed"] += 1
                if self.config.debug_mode:
                    print(f"[RX] Track {track_idx}: Postavljen zvuk '{name}' (Bank {msb}:{lsb}, Prog {prog})")
            else:
                if self.config.debug_mode:
                    print(f"[RX] Track {track_idx}: Nema RX mape za program {program_number}, ostaje original.")

        return tracks

    def inject_articulations(self, tracks: List[mido.MidiTrack], dna_analysis: Dict[int, list]) -> List[mido.MidiTrack]:
        """
        Analizira DNA (trileri, staccato fraze) i ubacuje Key Switcheve ili CC poruke
        neposredno PRIJE grupe nota koja zahtijeva tu artikulaciju.
        
        dna_analysis format: { track_index: [ {start_tick, end_tick, type: 'staccato'}, ... ] }
        """
        for track_idx, track in enumerate(tracks):
            if track_idx not in dna_analysis:
                continue
                
            events = dna_analysis[track_idx]
            # Sortiraj evente po vremenu
            events.sort(key=lambda x: x['start_tick'])
            
            current_time = 0
            msgs_to_insert = []
            
            for event in events:
                art_type = event.get('type', 'normal')
                start_tick = event['start_tick']
                
                if art_type not in ARTICULATION_MAP:
                    continue
                    
                art_def = ARTICULATION_MAP[art_type]
                
                if art_def['type'] == 'none':
                    continue
                
                # Izračunaj delta vrijeme do početka eventa
                # Ovo je pojednostavljeno; u produkciji treba preciznije računanje delta vremena
                delta = start_tick - current_time
                
                if art_def['type'] == 'keyswitch':
                    # Ubaci Key Switch Note (kratka nota)
                    ks_note = art_def['note']
                    ks_vel = art_def['vel']
                    
                    # Poruka Note On (Keyswitch)
                    msgs_to_insert.append((delta, mido.Message('note_on', note=ks_note, velocity=ks_vel, channel=self._detect_channel(track))))
                    # Poruka Note Off (odmah nakon, npr. 1 tick)
                    msgs_to_insert.append((0, mido.Message('note_off', note=ks_note, velocity=0, channel=self._detect_channel(track))))
                    
                    self.stats["articulations_injected"] += 1
                    if self.config.debug_mode:
                        print(f"[ART] Track {track_idx}: Ubacen Keyswitch '{art_type}' na tick {start_tick}")
                        
                elif art_def['type'] == 'cc':
                    cc_num = art_def['cc']
                    cc_val = art_def['val']
                    msgs_to_insert.append((delta, mido.Message('control_change', control=cc_num, value=cc_val, channel=self._detect_channel(track))))
                    
                    self.stats["articulations_injected"] += 1
                    if self.config.debug_mode:
                        print(f"[ART] Track {track_idx}: Ubacen CC '{art_type}' ({cc_num}={cc_val}) na tick {start_tick}")
                
                current_time = start_tick

            # Sada moramo fizički ubaciti ove poruke u track
            # Ovo je malo tricky jer mido koristi delta times. 
            # Za jednostavnost, kreirat ćemo novi track sa ubačenim porukama.
            if msgs_to_insert:
                new_track = self._merge_events(track, msgs_to_insert)
                tracks[track_idx] = new_track

        return tracks

    def _detect_channel(self, track: mido.MidiTrack) -> int:
        """Detektuje MIDI kanal tracka."""
        for msg in track:
            if hasattr(msg, 'channel'):
                return msg.channel
        return 0 # Default

    def _merge_events(self, original_track: mido.MidiTrack, insertions: List[Tuple[int, mido.Message]]) -> mido.MidiTrack:
        """
        Spaja originalne evente sa novim insercijama uz očuvanje delta vremena.
        insertions: lista (absolute_tick, message)
        """
        new_track = mido.MidiTrack()
        current_tick = 0
        
        # Pretvori originalni track u listu (absolute_tick, msg)
        original_events = []
        tick = 0
        for msg in original_track:
            tick += msg.time
            original_events.append((tick, msg))
        
        # Spoji liste
        all_events = original_events + [(t, m) for t, m in insertions]
        all_events.sort(key=lambda x: x[0])
        
        # Konvertuj nazad u delta times i dodaj u novi track
        last_tick = 0
        for abs_tick, msg in all_events:
            delta = abs_tick - last_tick
            new_msg = msg.copy(time=delta)
            new_track.append(new_msg)
            last_tick = abs_tick
            
        return new_track

# Helper funkcija za vanjsku upotrebu
def apply_rx_and_articulations(midi_file_path: str, output_path: str, dna_profiles: dict, dna_analysis: dict):
    mid = mido.MidiFile(midi_file_path)
    injector = RxArticulationInjector(config=RxConfig(debug_mode=True))
    
    # 1. Postavi RX Zvukove
    mid.tracks = injector.inject_rx_sounds(mid.tracks, dna_profiles)
    
    # 2. Ubaci Artikulacije
    mid.tracks = injector.inject_articulations(mid.tracks, dna_analysis)
    
    mid.save(output_path)
    print(f"✅ RX & Artikulacije primijenjene. Sačuvano u: {output_path}")
    print(f"📊 Statistika: {injector.stats}")
