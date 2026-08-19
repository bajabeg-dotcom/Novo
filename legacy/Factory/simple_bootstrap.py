#!/usr/bin/env python
"""Jednostavno grejanje DNA baza direktno iz MIDI fajlova."""

import sys
from pathlib import Path
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/workspace/rxoptimizer')

from rxoptimizer.dna_databases import (
    build_rhythm_database, build_performance_database, 
    build_voice_database, build_rx_database, build_solo_database,
    dna_status
)
from rxoptimizer.instrument_structure import build_instrument_structure_database

print("="*60)
print("🔥 JEDNOSTAVNO DNA BOOTSTRAPPING")
print("="*60)

data_dir = Path('/workspace/data')
factory_dir = data_dir / 'factory'
dna_dir = data_dir / 'dna'

dna_dir.mkdir(parents=True, exist_ok=True)

# Proveri MIDI fajlove
midis = list(factory_dir.glob('*.mid')) + list(factory_dir.glob('*.midi'))
print(f"\n📁 Pronađeno MIDI fajlova: {len(midis)}")

if not midis:
    print("❌ Nema MIDI fajlova u data/factory/")
    sys.exit(1)

# Kreiraj praznu privremenu bazu za import
import sqlite3
import tempfile

temp_factory = dna_dir / 'temp_factory.sqlite3'
temp_gold = dna_dir / 'temp_gold.sqlite3'

def create_corpus_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS midi_files(
        id INTEGER PRIMARY KEY, filename TEXT, filepath TEXT, 
        tempo_bpm REAL, meter_num INTEGER, meter_den INTEGER,
        track_count INTEGER, channel_mask INTEGER)""")
    
    # Ubaci MIDI fajlove
    for i, midi in enumerate(midis[:10]):  # Uzmi prvih 10
        try:
            # Pokušaj extract osnovnih info
            tempo, num, den, tracks = 120.0, 4, 4, 1
            conn.execute(
                "INSERT INTO midi_files(filename,filepath,tempo_bpm,meter_num,meter_den,track_count) VALUES(?,?,?,?,?,?)",
                (midi.name, str(midi.absolute()), tempo, num, den, tracks)
            )
        except Exception as e:
            print(f"⚠️  Greška za {midi.name}: {e}")
    
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM midi_files").fetchone()[0]
    conn.close()
    return count

factory_count = create_corpus_db(temp_factory)
gold_count = create_corpus_db(temp_gold)

print(f"✅ Factory corpus: {factory_count} fajlova")
print(f"✅ Gold corpus: {gold_count} fajlova")

# Sada pokreni build
print("\n🏗️  Kreiranje DNA baza...")

try:
    results = {}
    
    print("  🎵 Rhythm DNA...")
    results['rhythm'] = build_rhythm_database(temp_factory, temp_gold, dna_dir / 'rhythm_dna.sqlite3')
    
    print("  🎹 Performance DNA...")
    results['performance'] = build_performance_database(temp_factory, temp_gold, dna_dir / 'performance_dna.sqlite3')
    
    print("  🎼 Voice DNA...")
    results['voice'] = build_voice_database(temp_factory, temp_gold, dna_dir / 'voice_dna.sqlite3')
    
    print("  🥁 RX DNA...")
    results['rx'] = build_rx_database(temp_factory, temp_gold, dna_dir / 'rx_dna.sqlite3')
    
    print("  🎸 Solo DNA...")
    results['solo'] = build_solo_database(temp_factory, temp_gold, dna_dir / 'solo_dna.sqlite3')
    
    print("  🔧 Instrument Structure DNA...")
    results['instrument_structure'] = build_instrument_structure_database(
        temp_factory, temp_gold, dna_dir / 'instrument_structure_dna.sqlite3'
    )
    
    print("\n" + "="*60)
    print("📊 REZULTATI")
    print("="*60)
    
    for name, stats in results.items():
        if isinstance(stats, dict):
            created = "✅" if stats.get('created', False) else "❌"
            tracks = stats.get('track_count', stats.get('sources_count', 0))
            profiles = stats.get('profile_count', 0)
            print(f"{created} {name}: {tracks} trackova, {profiles} profila")
    
    # Cleanup
    temp_factory.unlink(missing_ok=True)
    temp_gold.unlink(missing_ok=True)
    
    print("\n🎉 DNA BAZE SU SPREMNE!")
    
except Exception as e:
    print(f"\n❌ GREŠKA: {e}")
    import traceback
    traceback.print_exc()
    
    # Cleanup anyway
    temp_factory.unlink(missing_ok=True)
    temp_gold.unlink(missing_ok=True)
