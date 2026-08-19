# 🎹 RX Smart Mapper & Artikulacije - KOMPLETNO UPUTSTVO

## ✅ Šta Je Implementirano

### 1. **Automatsko Postavljanje RX Zvukova**
Sistem sada **automatski** prepoznaje instrumente iz tvog MIDI fajla i postavlja tačne Roland RX zvukove koristeći:
- **Bank Select MSB/LSB** (Control Change 0 i 32)
- **Program Change** za specifični zvuk unutar banke

**Primjer:**
```
Originalni MIDI: Program 1 (Acoustic Piano GM)
       ↓
RX Mapper ubacuje:
  - CC0=0x00 (Bank MSB: Piano bank)
  - CC32=0x00 (Bank LSB)
  - PC=0x00 (Concert Grand iz RX kolekcije)
```

### 2. **Artikulacije (Key Switches & CC)**
Za svaki instrument koji podržava artikulacije, sistem automatski ubacuje:
- **Key Switches** (note ispod C1) za promjenu načina sviranja
- **Control Change (CC)** poruke za efekte kao što su Hammer-On, Pull-Off, Slide

**Podržane artikulacije:**

| Instrument | Artikulacija | Tip | Parametri |
|------------|--------------|-----|-----------|
| Violin/Viola/Cello | Staccato | Keyswitch | Note 36 (C1), Vel 80 |
| Violin/Viola/Cello | Legato | Keyswitch | Note 37 (C#1), Vel 80 |
| Violin/Viola/Cello | Spiccato | Keyswitch | Note 38 (D1), Vel 90 |
| Violin/Viola/Cello | Tremolo | Keyswitch | Note 39 (D#1), Vel 70 |
| Violin/Viola/Cello | Pizzicato | Keyswitch | Note 40 (E1), Vel 100 |
| Violin/Viola/Cello | Sustain | Keyswitch | Note 41 (F1), Vel 60 |
| Guitar | Hammer-On | CC | CC80=127 |
| Guitar | Pull-Off | CC | CC81=127 |
| Guitar | Slide Up | CC | CC82=127 |
| Guitar | Mute | Keyswitch | Note 35 (B0), Vel 50 |
| Wind/Brass | Flutter Tongue | CC | CC85=100 |
| Wind/Brass | Fall | CC | CC86=127 |

---

## 📋 Kako Funkcioniše

### Korak 1: Detekcija Instrumenta
```python
# Sistem čita originalni Program Change iz MIDI-a
for msg in track:
    if msg.type == 'program_change':
        program_number = msg.program  # npr. 40 = Violin
        break
```

### Korak 2: Mapiranje na RX Bazu
```python
# Traži u RX_SOUND_MAP
rx_data = RX_SOUND_MAP.get(40)  
# Rezultat: (0x01, 0x00, 0x00, "Violin Solo")
#           (MSB,   LSB,  Prog, Ime)
```

### Korak 3: Ubacivanje Poruki
```python
# Ubacuje NA POČETAK tracka (prije prve note)
track.insert(0, Message('control_change', control=0, value=0x01))   # Bank MSB
track.insert(0, Message('control_change', control=32, value=0x00))  # Bank LSB
track.insert(0, Message('program_change', program=0x00))            # RX Program
```

### Korak 4: Detekcija i Ubacivanje Artikulacija
```python
# DNA analiza kaže: "na ticku 50 ima staccato fraza"
dna_analysis = {
    track_idx: [
        {'start_tick': 50, 'end_tick': 100, 'type': 'staccato'}
    ]
}

# Sistem ubacuje Keyswitch note (C1) neposredno prije te fraze
track.insert(tick_49, Message('note_on', note=36, velocity=80))   # Staccato KS
track.insert(tick_49, Message('note_off', note=36, velocity=0))   # Odmah ugasi
```

---

## 🔧 Korištenje u Kodu

### Opcija 1: Direktno Kroz Funkciju
```python
from rxoptimizer.rx_smart_mapper import apply_rx_and_articulations

apply_rx_and_articulations(
    midi_file_path="input/moj_midi.mid",
    output_path="output/moj_midi_rx.mid",
    dna_profiles={},          # Optional: profili iz DNA baze
    dna_analysis={}           # Optional: analiza za artikulacije
)
```

### Opcija 2: Ručno Kroz Klasu
```python
import mido
from rxoptimizer.rx_smart_mapper import RxArticulationInjector, RxConfig

# Učitaj MIDI
mid = mido.MidiFile("input.mid")

# Konfiguriši injector
config = RxConfig(
    use_bank_select=True,
    use_keyswitches=True,
    debug_mode=True  # Ispisuje šta radi
)

injector = RxArticulationInjector(config=config)

# 1. Postavi RX zvukove
mid.tracks = injector.inject_rx_sounds(mid.tracks, dna_profiles={})

# 2. Ubaci artikulacije (ako imaš DNA analizu)
dna_analysis = {
    0: [{'start_tick': 480, 'end_tick': 960, 'type': 'staccato'}]
}
mid.tracks = injector.inject_articulations(mid.tracks, dna_analysis)

# Sačuvaj
mid.save("output.mid")

# Pregled statistike
print(f"Promijenjeno programa: {injector.stats['programs_changed']}")
print(f"Ubaceno artikulacija: {injector.stats['articulations_injected']}")
```

---

## 🎯 RX Sound Mapa (Dio)

Sistem trenutno mapira ove General MIDI brojeve na Roland RX zvukove:

### Klavijature
| GM # | Ime | RX Bank | RX Program |
|------|-----|---------|------------|
| 1 | Acoustic Piano | 0x00:0x00 | 0x00 (Concert Grand) |
| 2 | Bright Piano | 0x00:0x00 | 0x01 (Bright Grand) |
| 4 | Electric Piano 1 | 0x00:0x00 | 0x04 (RX MkI) |
| 5 | Electric Piano 2 | 0x00:0x00 | 0x05 (RX MkII Chorus) |

### Gudači
| GM # | Ime | RX Bank | RX Program |
|------|-----|---------|------------|
| 40 | Violin | 0x01:0x00 | 0x00 (Violin Solo) |
| 41 | Viola | 0x01:0x00 | 0x01 (Viola) |
| 42 | Cello | 0x01:0x00 | 0x02 (Cello Solo) |
| 43 | Contrabass | 0x01:0x00 | 0x03 (Double Bass) |
| 44 | Harp | 0x01:0x00 | 0x04 (Harp) |

### Gitare
| GM # | Ime | RX Bank | RX Program |
|------|-----|---------|------------|
| 24 | Nylon Guitar | 0x02:0x00 | 0x00 (Nylon Guitar) |
| 25 | Steel Guitar | 0x02:0x00 | 0x01 (Steel Guitar) |
| 26 | Electric Jazz | 0x02:0x00 | 0x02 (Electric Jazz) |
| 27 | Electric Clean | 0x02:0x00 | 0x03 (Electric Clean) |
| 28 | Muted Guitar | 0x02:0x00 | 0x04 (Muted Guitar) |
| 29 | Overdrive Guitar | 0x02:0x00 | 0x05 (Overdrive Guitar) |

### Basovi
| GM # | Ime | RX Bank | RX Program |
|------|-----|---------|------------|
| 32 | Acoustic Bass | 0x03:0x00 | 0x00 (Acoustic Bass) |
| 33 | Finger Bass | 0x03:0x00 | 0x01 (Finger Bass) |
| 34 | Pick Bass | 0x03:0x00 | 0x02 (Pick Bass) |
| 35 | Fretless Bass | 0x03:0x00 | 0x03 (Fretless Bass) |
| 36 | Slap Bass 1 | 0x03:0x00 | 0x04 (Slap Bass 1) |
| 37 | Slap Bass 2 | 0x03:0x00 | 0x05 (Slap Bass 2) |
| 38 | Synth Bass 1 | 0x03:0x00 | 0x06 (Synth Bass 1) |

### Sintisajzeri
| GM # | Ime | RX Bank | RX Program |
|------|-----|---------|------------|
| 80 | Square Lead | 0x04:0x00 | 0x00 (Square Lead) |
| 81 | Sawtooth Lead | 0x04:0x00 | 0x01 (Sawtooth Lead) |
| 88 | Fantasia Pad | 0x04:0x00 | 0x08 (Fantasia Pad) |
| 89 | Warm Pad | 0x04:0x00 | 0x09 (Warm Pad) |

### Bubnjevi
| GM # | Ime | RX Bank | RX Program |
|------|-----|---------|------------|
| 128 | Standard Kit | 0x7F:0x00 | 0x00 (Standard Kit) |

*Napomena: Channel 10 (percussion) ima poseban tretman i ne mijenja mu se program.*

---

## 🧪 Testiranje

Pokreni testove da vidiš da li sve radi ispravno:

```bash
cd /workspace
python -m pytest tests/test_rx_smart_mapper.py -v
```

**Očekivani rezultati:**
```
✅ test_inject_piano_rx_sound - PASSED
✅ test_inject_violin_rx_sound - PASSED
✅ test_unknown_program_fallback - PASSED
✅ test_inject_staccato_keyswitch - PASSED
✅ test_inject_guitar_cc_articulation - PASSED
✅ test_merge_preserves_timing - PASSED
✅ test_full_pipeline - PASSED
```

---

## ⚠️ Važne Napomene

### 1. **Tvoj Sintisajzer Mora Imati RX Zvukove**
Ovaj sistem šalje tačne MIDI komande, ali ako tvoj sintisajzer/sampler nema Roland RX biblioteku, neće čuti tačne zvukove. Rješenja:
- Koristi **Roland Cloud** VST
- Koristi **Fantom/GROM** hardware
- Koristi **SampleTank** sa Roland bibliotekama
- Mapiraj RX banke na svoje zvukove u DAW-u

### 2. **Keyswitch Opseg**
Keyswitch note su smještene u opsegu **C0-B0** (note 24-35). Ako tvoj instrument koristi druge keyswitcheve, moraš podesiti `ARTICULATION_MAP` u kodu.

### 3. **Nepoznati Instrumenti**
Ako MIDI koristi program broj koji nije u `RX_SOUND_MAP`, sistem će ga preskočiti i ostaviti originalni zvuk. Ovo je sigurnosna mjera.

### 4. **Redoslijed Poruka**
RX poruke se uvijek ubacuju **NA POČETAK** tracka, prije prve note. Originalni Program Change se zadržava radi kompatibilnosti sa DAW-ovima.

---

## 🚀 Sledeći Koraci

1. **Proširi RX Sound Mapu** - Dodaj više instrumenata u `RX_SOUND_MAP`
2. **Dodaj Više Artikulacija** - Za brass, woodwinds, orkestralne perkusije
3. **Integracija sa GUI-jem** - Doda opcije u Streamlit app za kontrolu RX i artikulacija
4. **Auto-Detekcija Artikulacija** - Pametnija DNA analiza koja sama prepoznaje staccato/legato fraze

---

## 📞 Podrška

Ako naiđeš na problem:
1. Pokreni sa `debug_mode=True` da vidiš logove
2. Provjeri da li tvoj sintisajzer prima Bank Select poruke
3. Testiraj sa jednostavnim MIDI fajlom prvo

**Sretno sa muzikom! 🎵**
