#!/usr/bin/env python
"""Brzi start - Import i Build u jednom koraku."""

import sys
from pathlib import Path
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/workspace/rxoptimizer')

from rxoptimizer.database import connect, analyze_and_store
from rxoptimizer.midi import parse_midi
from rxoptimizer.dna_databases import build_all, dna_status

print("="*70)
print("🚀 QUICK START - IMPORT & BUILD")
print("="*70)

# Setup direktorijuma
data_dir = Path('/workspace/data')
factory_dir = data_dir / 'factory'
dna_dir = data_dir / 'dna'
corpus_db = data_dir / 'factory_corpus.sqlite3'

for d in [factory_dir, dna_dir]:
    d.mkdir(parents=True, exist_ok=True)

# Kopiraj MIDI-jeve ako nisu već tu
import shutil
prism_dir = Path('/workspace/prism-uploads')
if prism_dir.exists():
    for mid in prism_dir.glob('*.mid'):
        dest = factory_dir / mid.name
        if not dest.exists():
            shutil.copy(mid, dest)

midis = list(factory_dir.glob('*.mid')) + list(factory_dir.glob('*.midi'))
print(f"\n📁 Pronađeno MIDI fajlova: {len(midis)}")

if not midis:
    print("❌ Nema MIDI fajlova!")
    sys.exit(1)

# KORAK 1: Import u corpus bazu
print("\n" + "="*70)
print("KORAK 1: Import MIDI fajlova u corpus")
print("="*70)

conn = connect(corpus_db)
imported = 0

for midi_path in midis[:10]:  # Prvih 10 radi demo
    try:
        print(f"  🎵 {midi_path.name}...", end=" ")
        
        with open(midi_path, 'rb') as f:
            midi_data = f.read()
        
        midi = parse_midi(midi_data)
        
        # Sačuvaj u bazu
        file_id = conn.execute(
            "INSERT INTO midi_files(filename,filepath) VALUES(?,?)",
            (midi_path.name, str(midi_path.absolute()))
        ).lastrowid
        
        analyze_and_store(conn, file_id, midi, source='factory')
        conn.commit()
        
        imported += 1
        print("✅")
        
    except Exception as e:
        print(f"❌ {e}")

print(f"\n✅ Importovano {imported} fajlova")

# KORAK 2: Build DNA baza
print("\n" + "="*70)
print("KORAK 2: Kreiranje DNA baza")
print("="*70)

gold_db = data_dir / 'gold_corpus.sqlite3'
if not gold_db.exists():
    print("  ℹ️  Kreiram prazan gold corpus za demo...")
    gold_conn = connect(gold_db)
    gold_conn.execute("""CREATE TABLE IF NOT EXISTS midi_files(
        id INTEGER PRIMARY KEY, filename TEXT, filepath TEXT,
        tempo_bpm REAL, meter_num INTEGER, meter_den INTEGER,
        track_count INTEGER, channel_mask INTEGER)""")
    gold_conn.commit()
    gold_conn.close()

try:
    results = build_all(corpus_db, gold_db, dna_dir)
    
    print("\n📊 REZULTATI:")
    for name, stats in results.items():
        if isinstance(stats, dict):
            created = "✅" if stats.get('created', False) else "⚠️"
            tracks = stats.get('track_count', stats.get('sources_count', 0))
            profiles = stats.get('profile_count', 0)
            print(f"  {created} {name}: {tracks} trackova, {profiles} profila")
    
    print("\n" + "="*70)
    print("🎉 DNA SISTEM JE SPREMAN!")
    print("="*70)
    
except Exception as e:
    print(f"\n❌ GREŠKA pri build-u: {e}")
    import traceback
    traceback.print_exc()

conn.close()

# Provera finalnog statusa
print("\n📋 FINALNI STATUS:")
status = dna_status(dna_dir)
for db, info in status.items():
    exists = "✅" if info.get('exists', False) else "❌"
    print(f"  {exists} {db}")
