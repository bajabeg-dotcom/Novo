"""
KORG PA800 ADAPTER
------------------
Automatski adapter za konverziju DNA profila u Korg Pa800 specifične komande.
Rješava problem Bank Select-a, Key Switches-a i Xtended Drum Kit-ova.

Autor: AI Autonomous Agent
Datum: 2024
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import mido

@dataclass(frozen=True)
class KorgInstrumentMap:
    """Mapping za Korg Pa800 instrumente"""
    program: int
    bank_msb: int = 0  # 0 = GM, 120-127 = Interne banke
    bank_lsb: int = 0
    key_switch_low: Optional[int] = None  # Note za artikulacije (npr. C-1 = 12)
    key_switch_high: Optional[int] = None
    cc_brightness: int = 64  # CC17
    cc_attack: int = 64      # CC73
    cc_release: int = 64     # CC74
    
# KORG PA800 SPECIFIČNE BANKE I INSTRUMENTI
KORG_BANK_MAP: Dict[str, KorgInstrumentMap] = {
    # --- PIANO & KEYS ---
    "Stereo Grand": KorgInstrumentMap(program=0, bank_msb=120, bank_lsb=0),
    "Bright Piano": KorgInstrumentMap(program=1, bank_msb=120, bank_lsb=0),
    "E.Piano 1": KorgInstrumentMap(program=4, bank_msb=120, bank_lsb=0),
    "E.Piano 2": KorgInstrumentMap(program=5, bank_msb=120, bank_lsb=0),
    "Harpsichord": KorgInstrumentMap(program=6, bank_msb=120, bank_lsb=0),
    "Vibraphone": KorgInstrumentMap(program=11, bank_msb=120, bank_lsb=0),
    
    # --- ORGAN ---
    "Drawbar Organ 1": KorgInstrumentMap(program=16, bank_msb=120, bank_lsb=0),
    "Drawbar Organ 2": KorgInstrumentMap(program=17, bank_msb=120, bank_lsb=0),
    "Rotary Organ": KorgInstrumentMap(program=18, bank_msb=120, bank_lsb=0),
    
    # --- GUITAR ---
    "Nylon Guitar": KorgInstrumentMap(program=24, bank_msb=120, bank_lsb=0, 
                                      key_switch_low=12, key_switch_high=24), # C-1 do C1
    "Steel Guitar": KorgInstrumentMap(program=25, bank_msb=120, bank_lsb=0,
                                      key_switch_low=12, key_switch_high=24),
    "Clean Guitar": KorgInstrumentMap(program=27, bank_msb=120, bank_lsb=0,
                                      key_switch_low=12, key_switch_high=24),
    "Muted Guitar": KorgInstrumentMap(program=28, bank_msb=120, bank_lsb=0,
                                      key_switch_low=12, key_switch_high=24),
    "Distortion Guitar": KorgInstrumentMap(program=29, bank_msb=120, bank_lsb=0,
                                          key_switch_low=12, key_switch_high=24),
    
    # --- BASS ---
    "Finger Bass": KorgInstrumentMap(program=32, bank_msb=120, bank_lsb=0,
                                     key_switch_low=12, key_switch_high=20),
    "Pick Bass": KorgInstrumentMap(program=33, bank_msb=120, bank_lsb=0,
                                   key_switch_low=12, key_switch_high=20),
    "Slap Bass": KorgInstrumentMap(program=36, bank_msb=120, bank_lsb=0,
                                   key_switch_low=12, key_switch_high=20),
    "Synth Bass": KorgInstrumentMap(program=38, bank_msb=120, bank_lsb=0),
    
    # --- STRINGS & ORCHESTRA ---
    "Violin": KorgInstrumentMap(program=40, bank_msb=120, bank_lsb=0,
                                key_switch_low=12, key_switch_high=36), # Širi opseg za artikulacije
    "Viola": KorgInstrumentMap(program=41, bank_msb=120, bank_lsb=0,
                               key_switch_low=12, key_switch_high=36),
    "Cello": KorgInstrumentMap(program=42, bank_msb=120, bank_lsb=0,
                               key_switch_low=12, key_switch_high=36),
    "Contrabass": KorgInstrumentMap(program=43, bank_msb=120, bank_lsb=0),
    "Harp": KorgInstrumentMap(program=46, bank_msb=120, bank_lsb=0),
    "Timpani": KorgInstrumentMap(program=47, bank_msb=120, bank_lsb=0),
    
    # --- BRASS & WOODWINDS ---
    "Trumpet": KorgInstrumentMap(program=56, bank_msb=120, bank_lsb=0,
                                 key_switch_low=12, key_switch_high=36),
    "Trombone": KorgInstrumentMap(program=57, bank_msb=120, bank_lsb=0),
    "French Horn": KorgInstrumentMap(program=60, bank_msb=120, bank_lsb=0),
    "Alto Sax": KorgInstrumentMap(program=65, bank_msb=120, bank_lsb=0,
                                  key_switch_low=12, key_switch_high=36),
    "Tenor Sax": KorgInstrumentMap(program=66, bank_msb=120, bank_lsb=0,
                                   key_switch_low=12, key_switch_high=36),
    "Clarinet": KorgInstrumentMap(program=71, bank_msb=120, bank_lsb=0),
    "Flute": KorgInstrumentMap(program=73, bank_msb=120, bank_lsb=0),
    
    # --- SYNTH LEAD ---
    "Lead Synth 1": KorgInstrumentMap(program=80, bank_msb=120, bank_lsb=0),
    "Lead Synth 2": KorgInstrumentMap(program=81, bank_msb=120, bank_lsb=0),
    "Lead Synth 3": KorgInstrumentMap(program=82, bank_msb=120, bank_lsb=0),
    "Lead Synth 4": KorgInstrumentMap(program=83, bank_msb=120, bank_lsb=0),
    
    # --- DRUMS (Xtended Drum Kits) - Banka 127 umjesto 128 jer MIDI CC mora biti 0-127 ---
    "Standard Kit": KorgInstrumentMap(program=0, bank_msb=127, bank_lsb=0),  # Posebna drum banka
    "Room Kit": KorgInstrumentMap(program=8, bank_msb=127, bank_lsb=0),
    "Power Kit": KorgInstrumentMap(program=16, bank_msb=127, bank_lsb=0),
    "Electric Kit": KorgInstrumentMap(program=24, bank_msb=127, bank_lsb=0),
    "TR-808 Kit": KorgInstrumentMap(program=25, bank_msb=127, bank_lsb=0),
    "Jazz Kit": KorgInstrumentMap(program=32, bank_msb=127, bank_lsb=0),
    "Brush Kit": KorgInstrumentMap(program=40, bank_msb=127, bank_lsb=0),
    "Orchestra Kit": KorgInstrumentMap(program=48, bank_msb=127, bank_lsb=0),
}

# KORG ARTIKULACIJE PREKO KEY SWITCHES
# Note: C-1 = 12, C0 = 24, C#0 = 25, D0 = 26...
KORG_ARTICULATION_KEYS = {
    "staccato": 12,      # C-1
    "legato": 13,        # C#-1
    "pizzicato": 14,     # D-1
    "spiccato": 15,      # D#-1
    "tremolo": 16,       # E-1
    "trill": 17,         # F-1
    "hammer_on": 18,     # F#-1
    "pull_off": 19,      # G-1
    "slide_down": 20,    # G#-1
    "slide_up": 21,      # A-1
    "mute": 22,          # A#-1
    "open": 23,          # B-1
    "harmonics": 24,     # C0
    "fall": 25,          # C#0
    "doit": 26,          # D0
    "flip": 27,          # D#0
}

# KORG DNC CC MAPA
KORG_DNC_CC_MAP = {
    "brightness": 17,    # CC17 - Brightness (ključno za Korg)
    "attack": 73,        # CC73 - Attack Time
    "release": 74,       # CC74 - Release Time
    "vibrato_rate": 75,  # CC75 - Vibrato Rate
    "vibrato_depth": 76, # CC76 - Vibrato Depth
    "cutoff": 71,        # CC71 - Resonance/Cutoff
    "reverb_send": 91,   # CC91 - Reverb
    "chorus_send": 93,   # CC93 - Chorus
}


class KorgPa800Adapter:
    """
    Adapter za konverziju MIDI događaja u Korg Pa800 specifične komande.
    Automatski ubacuje Bank Select, Program Change, Key Switches i DNC CC-eve.
    """
    
    def __init__(self, target_device: str = "KORG_PA800"):
        self.target_device = target_device
        self.instrument_cache: Dict[int, str] = {}  # channel -> instrument_name
        
    def detect_instrument_from_name(self, name: str) -> Optional[str]:
        """Pronađi najbolji match u Korg mapi po imenu instrumenta"""
        name_lower = name.lower()
        
        # Direktno podudaranje
        for korg_name in KORG_BANK_MAP.keys():
            if korg_name.lower() in name_lower or name_lower in korg_name.lower():
                return korg_name
        
        # Heuristika za slične instrumente
        if any(x in name_lower for x in ["piano", "grand", "bright"]):
            return "Stereo Grand"
        if any(x in name_lower for x in ["epiano", "e.piano", "electric piano"]):
            return "E.Piano 1"
        if any(x in name_lower for x in ["guitar", "nylon", "steel", "clean"]):
            return "Steel Guitar"
        if any(x in name_lower for x in ["bass", "finger", "pick"]):
            return "Finger Bass"
        if any(x in name_lower for x in ["slap"]):
            return "Slap Bass"
        if any(x in name_lower for x in ["violin", "strings", "ensemble"]):
            return "Violin"
        if any(x in name_lower for x in ["trumpet", "brass"]):
            return "Trumpet"
        if any(x in name_lower for x in ["sax", "alto", "tenor"]):
            return "Alto Sax"
        if any(x in name_lower for x in ["flute", "clarinet", "woodwind"]):
            return "Flute"
        if any(x in name_lower for x in ["synth", "lead", "pad"]):
            return "Lead Synth 1"
        if any(x in name_lower for x in ["drum", "kit", "percussion"]):
            return "Standard Kit"
            
        return None
    
    def generate_bank_select_program_change(self, channel: int, instrument_name: str) -> List[mido.Message]:
        """Generiše Bank Select MSB/LSB i Program Change za Korg"""
        messages = []
        
        korg_name = self.detect_instrument_from_name(instrument_name)
        if not korg_name or korg_name not in KORG_BANK_MAP:
            # Fallback na GM ako nema matcha
            print(f"[KORG] Warning: No match for '{instrument_name}', using GM default")
            return messages
            
        instr_map = KORG_BANK_MAP[korg_name]
        
        # Bank Select MSB (Control Change 0)
        messages.append(mido.Message('control_change', channel=channel, 
                                     control=0, value=instr_map.bank_msb))
        # Bank Select LSB (Control Change 32)
        messages.append(mido.Message('control_change', channel=channel,
                                     control=32, value=instr_map.bank_lsb))
        # Program Change
        messages.append(mido.Message('program_change', channel=channel,
                                     program=instr_map.program))
        
        print(f"[KORG] Channel {channel}: {instrument_name} -> {korg_name} "
              f"(Bank {instr_map.bank_msb}/{instr_map.bank_lsb}, PC {instr_map.program})")
        
        return messages
    
    def generate_articulation_key_switches(self, channel: int, 
                                           articulation: str) -> List[mido.Message]:
        """Generiše Key Switch note za promjenu artikulacija"""
        messages = []
        
        if articulation not in KORG_ARTICULATION_KEYS:
            return messages
            
        key_note = KORG_ARTICULATION_KEYS[articulation]
        
        # Key Switch ON (kratka nota, velocity 127)
        messages.append(mido.Message('note_on', channel=channel, 
                                     note=key_note, velocity=127))
        # Key Switch OFF (odmah nakon)
        messages.append(mido.Message('note_off', channel=channel,
                                     note=key_note, velocity=0))
        
        print(f"[KORG] Channel {channel}: Articulation '{articulation}' -> Key Switch {key_note}")
        
        return messages
    
    def generate_dnc_cc_messages(self, channel: int, 
                                 dna_profile: Dict) -> List[mido.Message]:
        """Generiše DNC CC poruke bazirane na DNA profilu"""
        messages = []
        
        # Mapiranje DNA statistike u Korg CC parametre
        velocity_mean = dna_profile.get('velocity_mean', 64)
        velocity_std = dna_profile.get('velocity_std', 20)
        
        # Brightness (CC17) - bazirano na prosječnom velocity-u
        brightness = int(min(127, max(0, velocity_mean)))
        messages.append(mido.Message('control_change', channel=channel,
                                     control=KORG_DNC_CC_MAP['brightness'], 
                                     value=brightness))
        
        # Attack Time (CC73) - obrnuto proporcionalno velocity_std (brži napad za veći std)
        attack = int(min(127, max(0, 127 - velocity_std)))
        messages.append(mido.Message('control_change', channel=channel,
                                     control=KORG_DNC_CC_MAP['attack'],
                                     value=attack))
        
        # Release Time (CC74) - bazirano na trajanju nota iz DNA
        release = dna_profile.get('avg_duration_ticks', 480)
        release_cc = int(min(127, max(0, release / 10)))  # Skaliranje
        messages.append(mido.Message('control_change', channel=channel,
                                     control=KORG_DNC_CC_MAP['release'],
                                     value=release_cc))
        
        print(f"[KORG] Channel {channel}: DNC CCs -> Brightness={brightness}, "
              f"Attack={attack}, Release={release_cc}")
        
        return messages
    
    def convert_drums_to_xtended_kit(self, track_messages: List[mido.Message],
                                     kit_name: str = "Standard Kit") -> List[mido.Message]:
        """Konvertuje GM bubnjeve u Korg Xtended Drum Kit format"""
        if kit_name not in KORG_BANK_MAP:
            return track_messages
            
        instr_map = KORG_BANK_MAP[kit_name]
        converted = []
        
        # Prvo postavi Bank Select za Drum Kit (Channel 9)
        converted.append(mido.Message('control_change', channel=9,
                                      control=0, value=instr_map.bank_msb))
        converted.append(mido.Message('control_change', channel=9,
                                      control=32, value=instr_map.bank_lsb))
        converted.append(mido.Message('program_change', channel=9,
                                      program=instr_map.program))
        
        # Preslikaj note ako je potrebno (Korg ima drugačije mappinge za neže kitove)
        # Za sada zadržavamo originalne note jer su GM kompatibilne
        for msg in track_messages:
            if msg.type in ['note_on', 'note_off'] and msg.channel == 9:
                # Ovdje bi išla logika za remapping nota za specifične kitove
                # npr. zamjena Kick nota za TR-808 kit
                converted.append(msg.copy())
            else:
                converted.append(msg.copy())
                
        print(f"[KORG] Drums converted to Xtended Kit: {kit_name}")
        return converted
    
    def apply_to_midi_file(self, input_path: str, output_path: str,
                           instrument_mapping: Dict[int, str]) -> None:
        """Primjeni Korg adaptaciju na cijeli MIDI fajl"""
        mid = mido.MidiFile(input_path)
        
        # Kreiraj novi MIDI za izlaz
        new_mid = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat)
        
        for i, track in enumerate(mid.tracks):
            new_track = mido.MidiTrack()
            new_mid.tracks.append(new_track)
            
            # Dodaj instrument specificne poruke na početak tracka
            if i < len(instrument_mapping):
                channel = i % 16  # Pretpostavka da je index tracka = channel
                instr_name = instrument_mapping.get(i, "Unknown")
                
                # Bank Select + Program Change
                bs_pc_msgs = self.generate_bank_select_program_change(channel, instr_name)
                new_track.extend(bs_pc_msgs)
                
                # DNC CC poruke (simulirani DNA profil)
                dummy_dna = {'velocity_mean': 72, 'velocity_std': 15, 'avg_duration_ticks': 480}
                dnc_msgs = self.generate_dnc_cc_messages(channel, dummy_dna)
                new_track.extend(dnc_msgs)
            
            # Kopiraj originalne poruke
            for msg in track:
                new_track.append(msg.copy())
        
        new_mid.save(output_path)
        print(f"[KORG] MIDI file saved to: {output_path}")


# TESTIRANJE
if __name__ == "__main__":
    adapter = KorgPa800Adapter()
    
    # Test detekcije instrumenta
    test_instruments = [
        "Grand Piano",
        "Steel String Guitar",
        "Fingered Bass",
        "Violin Section",
        "Alto Saxophone",
        "TR-808 Drum Kit"
    ]
    
    print("\n=== KORG PA800 INSTRUMENT DETECTION TEST ===\n")
    for instr in test_instruments:
        match = adapter.detect_instrument_from_name(instr)
        if match:
            korg_map = KORG_BANK_MAP[match]
            print(f"✓ '{instr}' -> '{match}' (Bank: {korg_map.bank_msb}/{korg_map.bank_lsb}, PC: {korg_map.program})")
        else:
            print(f"✗ '{instr}' -> No match found")
    
    print("\n=== KEY SWITCH TEST FOR STRINGS ===\n")
    string_articulations = ["staccato", "legato", "pizzicato", "trill", "spiccato"]
    for art in string_articulations:
        ks_msgs = adapter.generate_articulation_key_switches(channel=0, articulation=art)
        if ks_msgs:
            print(f"✓ Articulation '{art}' -> Key Switch Note: {ks_msgs[0].note}")
    
    print("\n=== DNC CC GENERATION TEST ===\n")
    test_dna = {
        'velocity_mean': 85,
        'velocity_std': 25,
        'avg_duration_ticks': 600
    }
    dnc_msgs = adapter.generate_dnc_cc_messages(channel=1, dna_profile=test_dna)
    for msg in dnc_msgs:
        cc_name = [k for k, v in KORG_DNC_CC_MAP.items() if v == msg.control][0]
        print(f"✓ CC{msg.control} ({cc_name}) = {msg.value}")
    
    print("\n=== KORG PA800 ADAPTER READY ===")
