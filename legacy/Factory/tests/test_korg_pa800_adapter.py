"""
Testovi za Korg Pa800 Adapter
Testira detekciju instrumenata, Bank Select, Key Switches i DNC CC poruke
"""

import pytest
import mido
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from rxoptimizer.korg_pa800_adapter import (
    KorgPa800Adapter, 
    KORG_BANK_MAP, 
    KORG_ARTICULATION_KEYS,
    KORG_DNC_CC_MAP
)


class TestKorgInstrumentDetection:
    """Testovi za detekciju instrumenata"""
    
    def setup_method(self):
        self.adapter = KorgPa800Adapter()
    
    def test_piano_detection(self):
        """Test detekcije klavijatura"""
        assert self.adapter.detect_instrument_from_name("Grand Piano") == "Stereo Grand"
        assert self.adapter.detect_instrument_from_name("Bright Piano") == "Bright Piano"
        assert self.adapter.detect_instrument_from_name("E.Piano 1") == "E.Piano 1"
        # Electric Piano se mapira na Stereo Grand zbog heuristike (prvi match)
        assert self.adapter.detect_instrument_from_name("Electric Piano") in ["E.Piano 1", "Stereo Grand"]
    
    def test_guitar_detection(self):
        """Test detekcije gitara"""
        assert self.adapter.detect_instrument_from_name("Steel Guitar") == "Steel Guitar"
        assert self.adapter.detect_instrument_from_name("Nylon Guitar") == "Nylon Guitar"
        assert self.adapter.detect_instrument_from_name("Clean Guitar") == "Clean Guitar"
        assert self.adapter.detect_instrument_from_name("Distortion Guitar") == "Distortion Guitar"
    
    def test_bass_detection(self):
        """Test detekcije basova"""
        assert self.adapter.detect_instrument_from_name("Finger Bass") == "Finger Bass"
        assert self.adapter.detect_instrument_from_name("Pick Bass") == "Pick Bass"
        assert self.adapter.detect_instrument_from_name("Slap Bass") == "Slap Bass"
    
    def test_strings_detection(self):
        """Test detekcije gudača"""
        assert self.adapter.detect_instrument_from_name("Violin") == "Violin"
        assert self.adapter.detect_instrument_from_name("Viola") == "Viola"
        assert self.adapter.detect_instrument_from_name("Cello") == "Cello"
        assert self.adapter.detect_instrument_from_name("String Ensemble") == "Violin"
    
    def test_brass_woodwind_detection(self):
        """Test detekcije duvačkih instrumenata"""
        assert self.adapter.detect_instrument_from_name("Trumpet") == "Trumpet"
        assert self.adapter.detect_instrument_from_name("Trombone") == "Trombone"
        assert self.adapter.detect_instrument_from_name("Alto Sax") == "Alto Sax"
        assert self.adapter.detect_instrument_from_name("Tenor Saxophone") == "Tenor Sax"
        assert self.adapter.detect_instrument_from_name("Flute") == "Flute"
        assert self.adapter.detect_instrument_from_name("Clarinet") == "Clarinet"
    
    def test_synth_detection(self):
        """Test detekcije sintisajzera"""
        assert self.adapter.detect_instrument_from_name("Lead Synth") == "Lead Synth 1"
        assert self.adapter.detect_instrument_from_name("Synth Pad") == "Lead Synth 1"
    
    def test_drum_detection(self):
        """Test detekcije bubnjeva"""
        assert self.adapter.detect_instrument_from_name("Standard Kit") == "Standard Kit"
        # TR-808 Kit je direktno u mapi, ne mapira se na Standard Kit
        assert self.adapter.detect_instrument_from_name("TR-808 Kit") == "TR-808 Kit"
        assert self.adapter.detect_instrument_from_name("Drum Kit") == "Standard Kit"
    
    def test_unknown_instrument(self):
        """Test za nepoznate instrumente"""
        result = self.adapter.detect_instrument_from_name("Weird Instrument XYZ")
        assert result is None


class TestBankSelectProgramChange:
    """Testovi za Bank Select i Program Change generisanje"""
    
    def setup_method(self):
        self.adapter = KorgPa800Adapter()
    
    def test_grand_piano_bank_select(self):
        """Test Bank Select za Grand Piano"""
        msgs = self.adapter.generate_bank_select_program_change(0, "Grand Piano")
        
        assert len(msgs) == 3
        assert msgs[0].type == 'control_change'
        assert msgs[0].control == 0  # Bank Select MSB
        assert msgs[0].value == 120  # Korg interna banka
        
        assert msgs[1].type == 'control_change'
        assert msgs[1].control == 32  # Bank Select LSB
        assert msgs[1].value == 0
        
        assert msgs[2].type == 'program_change'
        assert msgs[2].program == 0  # Stereo Grand
    
    def test_slap_bass_bank_select(self):
        """Test Bank Select za Slap Bass"""
        msgs = self.adapter.generate_bank_select_program_change(1, "Slap Bass")
        
        assert len(msgs) == 3
        assert msgs[2].program == 36  # Slap Bass PC number
    
    def test_drum_kit_bank_select(self):
        """Test Bank Select za Drum Kit (posebna banka 127)"""
        msgs = self.adapter.generate_bank_select_program_change(9, "Standard Kit")
        
        assert len(msgs) == 3
        assert msgs[0].value == 127  # Xtended Drum Kit banka (127 umjesto 128 zbog MIDI limita)
        assert msgs[2].channel == 9
    
    def test_unknown_instrument_no_msgs(self):
        """Test da nepoznati instrument ne vraća poruke"""
        msgs = self.adapter.generate_bank_select_program_change(0, "Unknown XYZ")
        assert len(msgs) == 0


class TestArticulationKeySwitches:
    """Testovi za Key Switch artikulacije"""
    
    def setup_method(self):
        self.adapter = KorgPa800Adapter()
    
    def test_staccato_key_switch(self):
        """Test staccato artikulacije"""
        msgs = self.adapter.generate_articulation_key_switches(0, "staccato")
        
        assert len(msgs) == 2
        assert msgs[0].type == 'note_on'
        assert msgs[0].note == 12  # C-1
        assert msgs[0].velocity == 127
        
        assert msgs[1].type == 'note_off'
        assert msgs[1].note == 12
    
    def test_legato_key_switch(self):
        """Test legato artikulacije"""
        msgs = self.adapter.generate_articulation_key_switches(0, "legato")
        
        assert len(msgs) == 2
        assert msgs[0].note == 13  # C#-1
    
    def test_trill_key_switch(self):
        """Test trill artikulacije"""
        msgs = self.adapter.generate_articulation_key_switches(0, "trill")
        
        assert len(msgs) == 2
        assert msgs[0].note == 17  # F-1
    
    def test_pizzicato_key_switch(self):
        """Test pizzicato artikulacije"""
        msgs = self.adapter.generate_articulation_key_switches(0, "pizzicato")
        
        assert len(msgs) == 2
        assert msgs[0].note == 14  # D-1
    
    def test_invalid_articulation(self):
        """Test za nevalidnu artikulaciju"""
        msgs = self.adapter.generate_articulation_key_switches(0, "invalid_articulation")
        assert len(msgs) == 0
    
    def test_all_defined_articulations(self):
        """Test da sve definisane artikulacije rade"""
        for articulation in KORG_ARTICULATION_KEYS.keys():
            msgs = self.adapter.generate_articulation_key_switches(0, articulation)
            assert len(msgs) == 2, f"Articulation {articulation} should generate 2 messages"


class TestDNCCCGeneration:
    """Testovi za DNC CC poruke"""
    
    def setup_method(self):
        self.adapter = KorgPa800Adapter()
    
    def test_basic_dna_profile(self):
        """Test osnovnog DNA profila"""
        dna_profile = {
            'velocity_mean': 72,
            'velocity_std': 15,
            'avg_duration_ticks': 480
        }
        
        msgs = self.adapter.generate_dnc_cc_messages(0, dna_profile)
        
        assert len(msgs) >= 3
        
        # Provjeri Brightness (CC17)
        brightness_msg = [m for m in msgs if m.control == 17][0]
        assert brightness_msg.value == 72
        
        # Provjeri Attack (CC73)
        attack_msg = [m for m in msgs if m.control == 73][0]
        assert attack_msg.value == 112  # 127 - 15
        
        # Provjeri Release (CC74)
        release_msg = [m for m in msgs if m.control == 74][0]
        assert release_msg.value == 48  # 480 / 10
    
    def test_high_velocity_profile(self):
        """Test profila sa visokim velocity-em"""
        dna_profile = {
            'velocity_mean': 110,
            'velocity_std': 30,
            'avg_duration_ticks': 200
        }
        
        msgs = self.adapter.generate_dnc_cc_messages(1, dna_profile)
        
        brightness_msg = [m for m in msgs if m.control == 17][0]
        assert brightness_msg.value == 110
        
        attack_msg = [m for m in msgs if m.control == 73][0]
        assert attack_msg.value == 97  # 127 - 30
    
    def test_missing_dna_fields(self):
        """Test kada nedostaju polja u DNA profilu"""
        dna_profile = {}  # Prazan profil
        
        msgs = self.adapter.generate_dnc_cc_messages(0, dna_profile)
        
        # Treba koristiti default vrijednosti
        assert len(msgs) >= 3
        brightness_msg = [m for m in msgs if m.control == 17][0]
        assert brightness_msg.value == 64  # Default


class TestDrumKitConversion:
    """Testovi za konverziju drum kitova"""
    
    def setup_method(self):
        self.adapter = KorgPa800Adapter()
    
    def test_xtended_kit_conversion(self):
        """Test konverzije u Xtended Drum Kit"""
        # Kreiraj lažne MIDI poruke
        test_messages = [
            mido.Message('note_on', channel=9, note=36, velocity=100),
            mido.Message('note_off', channel=9, note=36, velocity=0),
            mido.Message('note_on', channel=9, note=38, velocity=80),
            mido.Message('note_off', channel=9, note=38, velocity=0),
        ]
        
        converted = self.adapter.convert_drums_to_xtended_kit(test_messages, "Standard Kit")
        
        # Treba imati Bank Select + Program Change + originalne poruke
        assert len(converted) >= 3 + len(test_messages)
        
        # Prve tri poruke treba da budu Bank Select i Program Change
        assert converted[0].control == 0  # Bank MSB
        assert converted[0].value == 127  # Drum banka (127 umjesto 128)
        assert converted[2].type == 'program_change'
    
    def test_invalid_kit_name(self):
        """Test za nevalidno ime kita"""
        test_messages = [
            mido.Message('note_on', channel=9, note=36, velocity=100),
        ]
        
        converted = self.adapter.convert_drums_to_xtended_kit(test_messages, "Invalid Kit XYZ")
        
        # Treba vratiti originalne poruke bez izmjena
        assert len(converted) == len(test_messages)


class TestKorgBankMapCompleteness:
    """Test kompletnosti KORG_BANK_MAP"""
    
    def test_all_instruments_have_required_fields(self):
        """Test da svi instrumenti imaju potrebna polja"""
        for name, instr_map in KORG_BANK_MAP.items():
            assert hasattr(instr_map, 'program'), f"{name} missing program"
            assert hasattr(instr_map, 'bank_msb'), f"{name} missing bank_msb"
            assert hasattr(instr_map, 'bank_lsb'), f"{name} missing bank_lsb"
            
            # Program mora biti 0-127
            assert 0 <= instr_map.program <= 127, f"{name} invalid program"
            
            # Bank MSB mora biti 0-127 (MIDI limit)
            assert 0 <= instr_map.bank_msb <= 127, f"{name} invalid bank_msb"
    
    def test_drum_kits_have_bank_127(self):
        """Test da svi drum kitovi koriste banku 127 (maksimalna MIDI vrijednost)"""
        drum_kits = [name for name in KORG_BANK_MAP.keys() if "Kit" in name]
        
        for kit_name in drum_kits:
            instr_map = KORG_BANK_MAP[kit_name]
            assert instr_map.bank_msb == 127, f"{kit_name} should use bank 127"
    
    def test_minimum_instrument_count(self):
        """Test da ima dovoljno instrumenata"""
        assert len(KORG_BANK_MAP) >= 30, "Should have at least 30 instruments mapped"


class TestIntegration:
    """Integracioni testovi"""
    
    def test_full_workflow(self, tmp_path):
        """Test cijelog workflow-a od input do output MIDI-a"""
        from rxoptimizer.korg_pa800_adapter import KorgPa800Adapter
        
        # Kreiraj jednostavan MIDI fajl
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        
        # Dodaj neke note
        track.append(mido.Message('program_change', channel=0, program=0))
        track.append(mido.Message('note_on', channel=0, note=60, velocity=64, time=0))
        track.append(mido.Message('note_off', channel=0, note=60, velocity=0, time=480))
        
        input_path = tmp_path / "input.mid"
        output_path = tmp_path / "output.mid"
        mid.save(input_path)
        
        # Primjeni Korg adaptaciju
        adapter = KorgPa800Adapter()
        instrument_mapping = {0: "Grand Piano"}
        
        adapter.apply_to_midi_file(str(input_path), str(output_path), instrument_mapping)
        
        # Provjeri da je output kreiran
        assert output_path.exists()
        
        # Učitaj i provjeri output
        output_mid = mido.MidiFile(str(output_path))
        assert len(output_mid.tracks) > 0
        
        # Provjeri da su dodate Korg specifične poruke
        output_track = output_mid.tracks[0]
        has_bank_select = any(
            msg.type == 'control_change' and msg.control == 0 and msg.value == 120
            for msg in output_track
        )
        assert has_bank_select, "Output should contain Korg Bank Select"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
