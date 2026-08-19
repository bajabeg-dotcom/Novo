"""
Testovi za RX Smart Mapper i Artikulacije
Provjerava:
1. Da li se Bank Select i Program Change ispravno ubacuju.
2. Da li se Key Switches za artikulacije pravilno generišu.
3. Da li delta vremena ostaju očuvana.
"""

import pytest
import mido
from pathlib import Path
import sys

# Dodaj parent directory u path da možemo importovati modul
sys.path.insert(0, str(Path(__file__).parent.parent))

from rxoptimizer.rx_smart_mapper import (
    RxArticulationInjector, 
    RxConfig, 
    RX_SOUND_MAP, 
    ARTICULATION_MAP,
    apply_rx_and_articulations
)

def create_simple_track(program=0, channel=0):
    """Kreira jednostavan MIDI track za testiranje."""
    track = mido.MidiTrack()
    # Program mora biti 0-127
    safe_program = min(program, 127)
    track.append(mido.Message('program_change', program=safe_program, time=0, channel=channel))
    track.append(mido.Message('note_on', note=60, velocity=80, time=100, channel=channel))
    track.append(mido.Message('note_off', note=60, velocity=0, time=100, channel=channel))
    return track

class TestRxSoundInjection:
    
    def test_inject_piano_rx_sound(self):
        """Testira da li se Acoustic Piano (GM 1) mapira na RX Concert Grand."""
        track = create_simple_track(program=1, channel=0)
        tracks = [track]
        
        injector = RxArticulationInjector()
        result_tracks = injector.inject_rx_sounds(tracks, {})
        
        # Prve poruke trebaju biti Bank Select i Program Change (ubacene na početak)
        # Redoslijed: CC0 (MSB), CC32 (LSB), PC (new program)
        first_msg = result_tracks[0][0]
        second_msg = result_tracks[0][1]
        third_msg = result_tracks[0][2]
        
        assert first_msg.type == 'control_change'
        assert first_msg.control == 0  # Bank MSB
        assert first_msg.value == 0x00 # RX Bank MSB za Piano
        
        assert second_msg.type == 'control_change'
        assert second_msg.control == 32 # Bank LSB
        assert second_msg.value == 0x00 # RX Bank LSB za Piano
        
        assert third_msg.type == 'program_change'
        assert third_msg.program == 0x00 # RX Program za Concert Grand
        
    def test_inject_violin_rx_sound(self):
        """Testira mapiranje Violina (GM 40)."""
        track = create_simple_track(program=40, channel=1)
        tracks = [track]
        
        injector = RxArticulationInjector()
        result_tracks = injector.inject_rx_sounds(tracks, {})
        
        # Provjeri da je Bank MSB 0x01 (Strings bank)
        found_bank_msb = False
        for msg in result_tracks[0]:
            if msg.type == 'control_change' and msg.control == 0:
                assert msg.value == 0x01
                found_bank_msb = True
                break
        
        assert found_bank_msb, "Bank Select MSB nije pronađen"
        
    def test_unknown_program_fallback(self):
        """Testira da nepoznati program ne izaziva grešku."""
        track = create_simple_track(program=127, channel=0) # Posljednji validni GM broj (ali nema mapu)
        tracks = [track]
        
        injector = RxArticulationInjector()
        # Ovo ne smije baciti exception
        result_tracks = injector.inject_rx_sounds(tracks, {})
        
        # Trebao bi ostati originalni program ili default
        # U našem kodu, ako nema mape, samo preskačemo injectiju za taj track
        assert len(result_tracks) == 1

class TestArticulationInjection:
    
    def test_inject_staccato_keyswitch(self):
        """Testira ubacivanje Staccato Keyswitch-a."""
        track = create_simple_track(program=40, channel=0) # Violin
        tracks = [track]
        
        # Simuliraj DNA analizu koja kaže da na ticku 50 treba staccato
        dna_analysis = {
            0: [
                {'start_tick': 50, 'end_tick': 100, 'type': 'staccato'}
            ]
        }
        
        injector = RxArticulationInjector(config=RxConfig(debug_mode=True))
        result_tracks = injector.inject_articulations(tracks, dna_analysis)
        
        # Provjeri da li postoji keyswitch nota (C1 = note 36 po default mapi)
        found_ks = False
        for msg in result_tracks[0]:
            if msg.type == 'note_on' and msg.note == 36: # Staccato KS
                found_ks = True
                assert msg.velocity == 80 # Default velocity iz mape
                break
        
        assert found_ks, "Staccato Keyswitch nije ubačen"
        
    def test_inject_guitar_cc_articulation(self):
        """Testira ubacivanje Guitar Hammer-On CC poruke."""
        track = create_simple_track(program=24, channel=0) # Nylon Guitar
        tracks = [track]
        
        dna_analysis = {
            0: [
                {'start_tick': 60, 'end_tick': 120, 'type': 'hammer_on'}
            ]
        }
        
        injector = RxArticulationInjector()
        result_tracks = injector.inject_articulations(tracks, dna_analysis)
        
        # Traži CC 80 sa vrijednošću 127
        found_cc = False
        for msg in result_tracks[0]:
            if msg.type == 'control_change' and msg.control == 80:
                assert msg.value == 127
                found_cc = True
                break
        
        assert found_cc, "Hammer-On CC poruka nije ubačena"

    def test_merge_preserves_timing(self):
        """Testira da spajanje eventa ne kvari originalna delta vremena."""
        track = mido.MidiTrack()
        track.append(mido.Message('note_on', note=60, velocity=80, time=100))
        track.append(mido.Message('note_off', note=60, velocity=0, time=200)) # Ukupno 300 ticks
        
        injector = RxArticulationInjector()
        
        # Ubaci nešto na tick 50
        insertions = [(50, mido.Message('note_on', note=36, velocity=80, time=0))]
        
        new_track = injector._merge_events(track, insertions)
        
        # Provjeri da su sve note još uvijek prisutne
        notes = [msg for msg in new_track if msg.type == 'note_on' or msg.type == 'note_off']
        assert len(notes) >= 2 # Originalne note + eventualno keyswitch
        
        # Ukupno vrijeme tracka treba biti isto ili veće (zbog dodanih eventa)
        total_time_orig = sum(msg.time for msg in track)
        total_time_new = sum(msg.time for msg in new_track)
        
        # Vrijeme treba biti konzistentno (ne smije biti manje)
        assert total_time_new >= total_time_orig

class TestIntegration:
    
    def test_full_pipeline(self, tmp_path):
        """Testira cijeli proces od čitanja fajla do upisa."""
        # Kreiraj lažni MIDI fajl
        mid = mido.MidiFile()
        track = create_simple_track(program=1, channel=0)
        mid.tracks.append(track)
        
        input_file = tmp_path / "input.mid"
        output_file = tmp_path / "output.mid"
        
        mid.save(input_file)
        
        dna_profiles = {}
        dna_analysis = {0: [{'start_tick': 50, 'end_tick': 100, 'type': 'staccato'}]}
        
        # Pokreni pipeline
        apply_rx_and_articulations(str(input_file), str(output_file), dna_profiles, dna_analysis)
        
        # Provjeri da output fajl postoji i ima više poruka
        assert output_file.exists()
        
        mid_out = mido.MidiFile(str(output_file))
        assert len(mid_out.tracks) > 0
        
        # Broj poruka treba biti veći zbog ubačenih RX i KS poruka
        original_count = sum(len(t) for t in mid.tracks)
        new_count = sum(len(t) for t in mid_out.tracks)
        
        assert new_count > original_count, "Nisu ubačene nove poruke"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
