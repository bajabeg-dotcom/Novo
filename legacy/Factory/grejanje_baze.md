# 📖 KAKO SE GREJE BAZA

## Problem
DNA sistem zahteva **prethodno analizirane MIDI fajlove** u SQLite formatu pre nego što može da kreira DNA baze. 
Sistem ne može direktno da koristi `.mid` fajlove - mora prvo da se pokrene **Import Archive** proces.

## Rešenje - Dva Koraka

### KORAK 1: Import MIDI Fajlova (Prvi Put)

```bash
cd /workspace
python -m rxoptimizer.webui  # ILI
streamlit run app.py
```

U GUI-u:
1. Idi na **"Upload & Import"** tab
2. Upload-uj MIDI fajlove (ili koristi postojeće iz `prism-uploads/`)
3. Klikni na **"Run Import Archive"**
4. Sačekaj da se završi analiza

Ovo će kreirati:
- `data/factory_corpus.sqlite3` - analizirani factory MIDI-jevi
- `data/gold_corpus.sqlite3` - analizirani gold MIDI-jevi (ako ih ima)

### KORAK 2: Build DNA Baza

Nakon što import završi, u GUI-u:
1. Idi na **"Settings"** ili **"DNA Management"**
2. Klikni na **"Build DNA Databases"**
3. Sistem će automatski kreirati sve DNA baze iz analiziranog korpusa

Ili preko komandne linije:
```bash
cd /workspace
python -c "
from pathlib import Path
from rxoptimizer.dna_databases import build_all

factory = Path('data/factory_corpus.sqlite3')
gold = Path('data/gold_corpus.sqlite3')
dna_dir = Path('data/dna')

if factory.exists():
    results = build_all(factory, gold, dna_dir)
    print('✅ DNA baze kreirane:', results.keys())
else:
    print('❌ Prvo pokreni Import Archive!')
"
```

## Šta Se Dešava U Pozadini?

### Import Archive Proces:
1. **Učitava MIDI fajl** → parsira note, kontrolere, tempo
2. **Ekstrahuje featire** → rhythm patterns, velocity, duration
3. **Klasifikuje instrumente** → bass, drums, guitar, melody
4. **Čuva u SQLite** → `midi_files`, `performance_features` tabele

### DNA Build Proces:
1. **Čita analizirane podatke** iz factory/gold corpus-a
2. **Grupiše po stilovima/sekcijama** → 8thNote, 16thNote, Ballad, etc.
3. **Računa statistiku** → mean, std, min, max za velocity/timing
4. **Kreira DNA profile** → section_profiles, performance_models
5. **Čuva u DNA baze** → rhythm_dna.sqlite3, performance_dna.sqlite3, etc.

## Brzi Start Sa Postojećim Fajlovima

```bash
# Kopiraj postojeće MIDI-jeve
cp /workspace/prism-uploads/*.mid /workspace/data/factory/

# Pokreni Streamlit
cd /workspace
streamlit run app.py --server.port 8501
```

Zatim u browseru (http://localhost:8501):
1. Upload tab → vidićeš već učitane fajlove
2. Process tab → klikni "Analyze & Build DNA"
3. Transfer tab → spremno za Gold Style Transfer!

## Provera Statusa

```bash
python -c "
from pathlib import Path
from rxoptimizer.dna_databases import dna_status

status = dna_status(Path('data/dna'))
print('DNA Baze:')
for db, info in status.items():
    print(f'  {db}: {\"✅\" if info.get(\"exists\") else \"❌\"}')"
```

## Zašto Ovakav Dizajn?

1. **Performanse** - MIDI parsing je spor, radi se samo jednom
2. **Incremental Updates** - Možeš dodavati nove MIDI-jeve bez rebuild cele baze
3. **Cache** - Analizirani podaci se keširaju za brzi transfer
4. **Validation** - Svaki MIDI se validira pre nego što uđe u DNA

## Troubleshooting

### "no such table: performance_features"
→ Nisi pokrenuo Import Archive pre Build DNA

### "Factory corpus je prazan"
→ Proveri da li su MIDI fajlovi kopirani u data/factory/

### "unable to open database file"
→ Proveri permissions: `chmod -R 755 data/`
