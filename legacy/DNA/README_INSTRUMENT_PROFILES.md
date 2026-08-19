# Song MIDI Optimizer - Instrument Profiles

## 🎹 SONG MIDI OPTIMIZER SA GUI-jem

Profesionalni alat za optimizaciju MIDI datoteka baziran na **Factory Styles** i **Gold Standards** principima.

---

## 📋 KLJUČNA KARAKTERISTIKA: INSTRUMENT PROFILI

**Svaki instrument ima svoj profil koji radi na principu: `VELOCITY.TIMING.DURATION`**

### Format Profila: `120.222.112`

| Vrijednost | Raspon | Opis | Primjer (120.222.112) |
|------------|--------|------|----------------------|
| **VELOCITY** | 1-127 | Ciljna prosječna velocity | 120 = Visoka dinamika |
| **TIMING** | 50-500 | Strogoća timinga/quantization | 222 = Precizan timing |
| **DURATION** | 50-200 | Faktor trajanja nota (%) | 112 = 112% originalnog trajanja |

---

## 🎼 DOSTUPNI INSTRUMENTI I PROFILI

### Keyboard Instruments
| Instrument | Profil | Opis |
|------------|--------|------|
| Piano | `120.222.112` | Akustični klavir - Balansirana dinamika |
| Electric_Piano | `110.200.130` | E.Piano - Mekši attack |
| Organ | `100.180.150` | Orgulje - Održane note |
| Harpsichord | `95.240.090` | Čembalo - Trzalački, precizan |

### String Instruments
| Instrument | Profil | Opis |
|------------|--------|------|
| Violin | `115.210.140` | Violina - Ekspresivno gudačenje |
| Viola | `105.200.145` | Viola - Tople srednje frekvencije |
| Cello | `110.190.155` | Violončelo - Duboka rezonanca |
| Guitar_Acoustic | `105.220.100` | Akustična gitara - Strumming |
| Guitar_Electric | `125.230.095` | Električna gitara - Udarne note |
| Guitar_Bass | `115.240.140` | Bas gitara - Čvrst ritam |

### Wind/Brass Instruments
| Instrument | Profil | Opis |
|------------|--------|------|
| Flute | `90.200.130` | Flauta - Lagano, zračno |
| Saxophone | `120.190.125` | Saksofon - Ekspresivan jazz |
| Trumpet | `130.220.110` | Truba - Svijetli limeni zvuk |
| Trombone | `125.200.120` | Trombon - Bogati limeni zvuk |

### Percussion/Drums
| Instrument | Profil | Opis |
|------------|--------|------|
| Drums_Full | `127.250.080` | Puni bubanj set - Udarne note |
| Drums_Soft | `95.230.090` | Meke četkice - Jazz |
| Timpani | `115.200.150` | Timpani - Orkestralni |

### Synth/Electronic
| Instrument | Profil | Opis |
|------------|--------|------|
| Synth_Lead | `115.250.100` | Synth Lead - Elektronički |
| Synth_Pad | `90.180.180` | Synth Pad - Atmosferski |
| Synth_Bass | `120.245.130` | Synth Bass - Čvrst |

### Voice/Choir
| Instrument | Profil | Opis |
|------------|--------|------|
| Voice_Solo | `105.190.145` | Solo vokal |
| Choir | `100.185.160` | Zbor - Ansambl |

---

## 🔄 WORKFLOW: IMPORT - OPTIMIZE - EXPORT

### 1. 📥 IMPORT
- Učitaj MIDI datoteku (.mid, .midi)
- Automatska analiza trackova i instrumenata
- Detekcija problema (niska velocity, nema dinamike, prazni trackovi)
- Quality Score (0-100)

### 2. 🎹 INSTRUMENT PROFILES
- Auto-detekcija profila za svaki instrument
- Ručno podešavanje profila (V.T.D vrijednosti)
- Odabir iz preset profila
- Profile string format: `120.222.112`

### 3. 🔍 ANALYSIS
- Statistika po tracku (note, velocity, raspon)
- Detektovani instrumenti po programu
- Identifikacija problema
- Quality Score prikaz

### 4. ⚙️ OPTIMIZATION
- **Corpus Rules**: Factory Styles / Gold Standards / Balanced
- **Optimization Options**:
  - ✓ Optimize Velocities
  - ✓ Optimize Timing
  - ✓ Optimize Durations
  - ✓ Optimize Note Density
- Primjena instrument profila
- Preview aktivnih pravila

### 5. 📤 EXPORT
- Postavi izlazni filename
- Format: MIDI 0 (Single Track) ili MIDI 1 (Multiple Tracks)
- Metadata: Title, Artist
- Export log sa promjenama

---

## 🏛️ CORPUS RULES

### Factory Styles
- Profesionalna factory-style pravila
- Velocity: min 40, max 127, target 80
- Timing: quantize 480 ticks
- Channel assignment za drums, bass, melody, harmony

### Gold Standards
- Premium quality standardi
- Velocity: min 50, max 127, target 90
- Timing: quantize 960 ticks (viša rezolucija)
- Articulation support (staccato, legato, accent, tenuto)
- Expression controllers (CC1, CC11, aftertouch)
- Phrase structure i section markers

### Balanced (Preporučeno)
- Kombinacija Factory + Gold
- Najbolje od oba korpusa
- Viša rezolucija (960 ticks)
- Poboljšana expression podrška

---

## 💻 KORIŠTENJE

### Pokretanje GUI-a
```bash
python song_midi_optimizer.py
```

### Programsko korištenje
```python
from song_midi_optimizer import (
    InstrumentProfile, 
    CorpusRules, 
    MIDIAnalyzer, 
    MIDIOptimizer
)
import mido

# 1. Učitaj MIDI
midi = mido.MidiFile('input.mid')

# 2. Kreiraj instrument profile
piano_profile = InstrumentProfile('Piano')  # 120.222.112
bass_profile = InstrumentProfile('Guitar_Bass')  # 115.240.140

instrument_profiles = {
    0: piano_profile,  # Channel 0
    1: bass_profile    # Channel 1
}

# 3. Analiza
analyzer = MIDIAnalyzer()
stats = analyzer.analyze(midi)
print(f"Quality Score: {stats['quality_score']}/100")

# 4. Optimizacija
corpus = CorpusRules()
rules = corpus.get_combined_rules('balanced')
optimizer = MIDIOptimizer(rules, instrument_profiles)
optimized = optimizer.optimize(midi)

# 5. Export
optimized.save('output.mid')
```

### Kreiranje custom profila
```python
# Iz string formata
profile = InstrumentProfile.from_string('120.222.112', 'MyCustomInstrument')

# Ili ručno postavljanje
profile = InstrumentProfile('Custom')
profile.set_values(velocity=125, timing=230, duration=115)
print(profile.get_profile_string())  # "125.230.115"
```

---

## 📊 GUI TABOVI

1. **📥 IMPORT** - Učitavanje MIDI datoteka
2. **🎹 INSTRUMENT PROFILES** - Pregled i editovanje profila
3. **🔍 ANALYSIS** - Detaljna analiza MIDI datoteke
4. **⚙️ OPTIMIZATION** - Postavke i pokretanje optimizacije
5. **📤 EXPORT** - Izvoz optimizirane MIDI datoteke

---

## 🔧 TEHNIČKE KARAKTERISTIKE

- **Jezik**: Python 3
- **GUI Framework**: Tkinter
- **MIDI Library**: mido
- **Formati**: MIDI 0, MIDI 1
- **Platforme**: Windows, macOS, Linux

---

## 📝 PRIMJERI PROFILA

### Piano Ballad
```
Piano:        120.222.112  (Balansirano)
Strings:      105.200.145  (Mekše, duže note)
Bass:         110.230.140  (Čvrst temelj)
```

### Rock Band
```
Electric_Guitar: 125.230.095  (Agresivno, kratko)
Bass_Guitar:     120.245.135  (Punchy)
Drums_Full:      127.250.080  (Maksimalna snaga)
```

### Jazz Ensemble
```
Piano:       110.200.125  (Su suptilnije)
Saxophone:   120.190.125  (Ekspresivno)
Drums_Soft:   95.230.090  (Četkice)
Bass:        110.220.145  (Walking bass)
```

---

## ⚠️ NAPOMENE

- Velocity vrijednosti: 1-127 (MIDI standard)
- Timing vrijednosti: 50-500 (niže = strože)
- Duration vrijednosti: 50-200 (% od originala)
- Svaki instrument na zasebnom channelu može imati različit profil
- Auto-detekcija koristi MIDI program brojeve za mapiranje instrumenata

---

**Verzija**: 1.0  
**Autor**: Bazirano na user requirements  
**Licenca**: Open Source
