"""
A/B Blind Testing Framework
Struktura za vođenje slijepih testova na fizičkom Korg Pa800 uređaju.
"""

class ABTestSession:
    def __init__(self, song_name):
        self.song_name = song_name
        self.samples = []
        
    def add_sample(self, version, audio_file_path, notes):
        """Dodaje uzorak za testiranje."""
        self.samples.append({
            "version": version, # "Original" ili "Optimized"
            "file": audio_file_path,
            "notes": notes,
            "blind_id": hash(audio_file_path) % 1000 # Random ID za slijepi test
        })
        
    def generate_scorecard(self):
        """Generira karticu za ocjenjivanje."""
        return f"""
========================================
A/B SCORECARD: {self.song_name}
========================================
Slušatelj: _________________________
Datum: _____________________________

Usporedite dva uzorka (A i B) bez znanja koji je original.

KRITERIJI (1-5):
1. Točnost sounda (Instrument zvuči prirodno)
2. Balans glasnoće (Svi instrumenti se čuju)
3. Dinamika (Ima li života u svirci)
4. Groove (Ritam osjeća dobro)
5. Ukupni dojam

OCJENE:
Uzorak A: [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5
Uzorak B: [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5

PREFERENCIJA:
[ ] Uzorak A je bolji
[ ] Uzorak B je bolji
[ ] Neriješeno

KOMENTARI:
__________________________________________________
__________________________________________________
"""

# Primjer upotrebe
if __name__ == "__main__":
    session = ABTestSession("Nevera Moja")
    session.add_sample("Original", "recordings/nevera_orig.wav", "Original MIDI")
    session.add_sample("Optimized", "recordings/nevera_opt.wav", "Optimized MIDI")
    
    with open("ab_testing/scorecard_template.txt", "w") as f:
        f.write(session.generate_scorecard())
    print("Scorecard generiran u ab_testing/scorecard_template.txt")
