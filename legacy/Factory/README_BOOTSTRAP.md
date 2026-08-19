# 🚀 KAKO SE GREJE BAZA - KOMPLETNO UPUTSTVO

## ⚠️ KLJUČNA STVAR KOJU SI PITAO

**"Kako se greši baza?"** - Baza se **NE MOŽE** grešiti direktno iz `.mid` fajlova!

Sistem zahteva **dva koraka**:

### 📋 PROCES U DVA KORAKA

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  MIDI (.mid)│ ──▶ │  Import Archive  │ ──▶ │ Corpus DB    │
│  fajlovi    │     │  (analyze_and_   │     │ (.sqlite3)   │
│             │     │   store)         │     │              │
└─────────────┘     └──────────────────┘     └──────────────┘
                                                    │
                                                    ▼
                                          ┌──────────────────┐
                                          │  Build DNA       │
                                          │  (build_all)     │
                                          └──────────────────┘
                                                    │
                                                    ▼
                                          ┌──────────────────┐
                                          │  DNA Baze        │
                                          │  (.sqlite3)      │
                                          └──────────────────┘
```

---

## 🎯 ŠTA JE TRENUTNI PROBLEM

Pokušavaš da pokreneš `build_all()` direktno na MIDI fajlovima, ali ta funkcija očekuje:
- ✅ **factory_path** = SQLite corpus baza (sa `midi_files`, `performance_features` tabelama)
- ✅ **gold_path** = SQLite corpus baza (sa istom strukturom)
- ❌ **NIJE** = direktorijum sa `.mid` fajlovima!

---

## ✅ REŠENJE - KORAK PO KORAK

### KORAK 1: Pokreni Streamlit App

```bash
cd /workspace
streamlit run app.py --server.port 8501
```

Otvori browser na: `http://localhost:8501`

### KORAK 2: Upload MIDI Fajlova

U GUI-u:
1. Idi na **"Upload"** tab
2. Vidićeš već postojeće fajlove iz `prism-uploads/`
3. Ili upload-uj nove MIDI fajlove

### KORAK 3: Import Archive

U GUI-u:
1. Idi na **"Import & Process"** tab
2. Klikni na **"Run Import Archive"**
3. Ovo će pozvati `analyze_and_store()` za svaki MIDI
4. Kreiraće `data/factory_corpus.sqlite3`

### KORAK 4: Build DNA

U GUI-u:
1. Idi na **"DNA Management"** ili **"Settings"**
2. Klikni na **"Build DNA Databases"**
3. Ovo će pozvati `build_all()` na corpus bazama
4. Kreiraće sve DNA baze u `data/dna/`

---

## 🛠️ ALTERNATIVA: Komandna Linija

Ako baš želiš preko terminala:

```bash
cd /workspace
python -c "
from pathlib import Path
from rxoptimizer.database import connect, analyze_and_store
from rxoptimizer.midi import parse_midi
from rxoptimizer.dna_databases import build_all

data = Path('data')
corpus_db = data / 'factory_corpus.sqlite3'
dna_dir = data / 'dna'

# 1. Kreiraj corpus bazu
conn = connect(corpus_db)

# 2. Importuj MIDI-jeve
for mid in Path('prism-uploads').glob('*.mid'):
    print(f'Import: {mid.name}')
    midi = parse_midi(mid.read_bytes())
    file_id = conn.execute(
        'INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES(?,?,?,?,?)',
        (mid.name, 'placeholder', 1, 480, 1)
    ).lastrowid
    analyze_and_store(conn, file_id, midi, 'factory')
    conn.commit()

conn.close()

# 3. Build DNA
gold_db = data / 'gold_corpus.sqlite3'  # Mora postojati (može prazna)
results = build_all(corpus_db, gold_db, dna_dir)
print('DNA baze kreirane:', list(results.keys()))
"
```

---

## 📊 ŠTA SE DEŠAVA U POZADINI

### Import Archive (`analyze_and_store`)

```python
def analyze_and_store(db, file_id, midi, source):
    # 1. Parsira MIDI note
    for track in midi.tracks:
        # 2. Ekstrahuje:
        #    - note (pitch, velocity, duration)
        #    - kontrolere (CC, PC)
        #    - tempo promene
        # 3. Računa statistiku:
        #    - velocity_mean, velocity_std
        #    - duration_mean, density_per_quarter
        # 4. Čuva u tabele:
        db.execute("INSERT INTO track_stats(...)")
        db.execute("INSERT INTO performance_features(...)")
```

### DNA Build (`build_all`)

```python
def build_all(factory_corpus, gold_corpus, dna_dir):
    # 1. Čita VEĆ ANALIZIRANE podatke iz corpus-a
    rows = db.execute("""
        SELECT pf.file_id, mf.filename, pf.track_index, 
               pf.role, pf.feature_json
        FROM performance_features pf
        JOIN midi_files mf ON pf.file_id = mf.id
    """)
    
    # 2. Grupiše po stilovima i sekcijama
    # 3. Računa aggregate statistiku
    # 4. Kreira DNA profile
    # 5. Čuva u DNA baze
```

---

## 🔍 ZAŠTO OVAKAV DIZAJN?

| Razlog | Objašnjenje |
|--------|-------------|
| **Performanse** | MIDI parsing je spor (30-100ms/fajlu). Radi se samo jednom. |
| **Incremental** | Možeš dodavati nove MIDI-jeve bez rebuild cele DNA baze |
| **Cache** | Analizirani podaci su odmah dostupni za transfer |
| **Validation** | Svaki MIDI se validira pre ulaska u DNA |
| **Gold Transfer** | Gold stilovi se mogu primeniti bez ponovnog parsiranja |

---

## 🧪 TESTIRANJE DA LI RADI

```bash
python -c "
from pathlib import Path
from rxoptimizer.dna_databases import dna_status

status = dna_status(Path('data/dna'))

print('DNA BAZE STATUS:')
print('='*50)
created = sum(1 for v in status.values() if v.get('exists'))
total = len(status)

for db, info in status.items():
    symbol = '✅' if info.get('exists') else '❌'
    print(f'{symbol} {db}')

print('='*50)
print(f'UKUPNO: {created}/{total} baza kreirano')

if created == total:
    print('🎉 SISTEM JE SPREMAN ZA RAD!')
else:
    print('⚠️  Prvo pokreni: streamlit run app.py')
"
```

---

## 🆘 TROUBLESHOOTING

### "table midi_files has no column named filepath"
→ **Rešenje:** Koristi pravu šemu! Nemoj sam kreirati tabele.
```python
from rxoptimizer.database import connect
conn = connect('data/corpus.sqlite3')  # Ovo automatski kreira ispravnu šemu
```

### "Factory corpus je prazan"
→ **Rešenje:** Nisi pokrenuo import. Proveri:
```bash
sqlite3 data/factory_corpus.sqlite3 "SELECT COUNT(*) FROM midi_files;"
# Treba da vrati broj > 0
```

### "no such table: performance_features"
→ **Rešenje:** Import nije završen. Pokreni GUI i idi na Import tab.

### "unable to open database file"
→ **Rešenje:** Permissions problem:
```bash
chmod -R 755 data/
chown -R $USER:$USER data/
```

---

## 📝 ZAKLJUČAK

**Baza se "greje" tako što:**
1. ✅ Upload-uješ MIDI fajlove kroz GUI
2. ✅ Pokreneš "Import Archive" (kreira corpus SQLite)
3. ✅ Pokreneš "Build DNA" (kreira DNA baze iz corpus-a)

**NE MOŽEŠ:**
- ❌ Direktno iz `.mid` fajlova u DNA baze
- ❌ Preskočiti Import Archive korak
- ❌ Koristiti `build_all()` na direktorijumu sa MIDI-jima

**To je kao kuvanje:**
- MIDI fajlovi = sirovi sastojci
- Import Archive = seckanje i priprema
- DNA Build = kuvanje jela
- DNA baze = gotovo jelo za serviranje

Ne možeš staviti sirovo povrće direktno u rernu bez pripreme! 🍳
