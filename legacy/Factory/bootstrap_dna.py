#!/usr/bin/env python
"""Bootstrap DNA databases from factory and gold MIDI corpora."""

import sys
from pathlib import Path

# Add workspace to path
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/workspace/rxoptimizer')

from rxoptimizer.dna_databases import build_all, dna_status
from rxoptimizer.evidence_registry import build_evidence_registry

def bootstrap(minify=False):
    """Grejanje svih DNA baza iz factory i gold korpusa."""
    
    print("="*60)
    print("🔥 DNA BOOTSTRAPPING PROCESS")
    print("="*60)
    
    # Definiši direktorijume
    data_dir = Path('data')
    factory_dir = data_dir / 'factory'
    gold_dir = data_dir / 'gold'
    dna_dir = data_dir / 'dna'
    evidence_dir = data_dir / 'evidence'
    
    # Kreiraj direktorijume ako ne postoje
    for d in [factory_dir, gold_dir, dna_dir, evidence_dir]:
        d.mkdir(parents=True, exist_ok=True)
        print(f"✅ Direktorijum spreman: {d}")
    
    # Proveri da li ima MIDI fajlova
    factory_midis = list(factory_dir.glob('*.mid')) + list(factory_dir.glob('*.midi'))
    gold_midis = list(gold_dir.glob('*.mid')) + list(gold_dir.glob('*.midi'))
    
    print(f"\n📁 Factory MIDI fajlova: {len(factory_midis)}")
    print(f"📁 Gold MIDI fajlova: {len(gold_midis)}")
    
    if not factory_midis and not gold_midis:
        print("\n⚠️  UPOZORENJE: Nema MIDI fajlova za analizu!")
        print("\n📝 UPUTSTVO:")
        print("   1. Kopirajte MIDI fajlove u data/factory/ ili data/gold/")
        print("   2. Pokrenite ponovo: python bootstrap_dna.py")
        print("\n💡 ILI koristite GUI:")
        print("   streamlit run app.py")
        return False
    
    # Inicijalizuj evidence registry
    print("\n🔧 Inicijalizacija Evidence Registry...")
    try:
        if factory_midis or gold_midis:
            evidence_result = build_evidence_registry(
                evidence_dir / 'inventory.json',
                factory_dir,
                evidence_dir / 'evidence_registry.sqlite3'
            )
            print(f"✅ Evidence Registry kreiran: {evidence_result.get('sources_count', 0)} izvora")
        else:
            print("⚠️  Preskačem Evidence Registry (nema MIDI fajlova)")
    except Exception as e:
        print(f"⚠️  Evidence Registry greška: {e}")
    
    # Build svih DNA baza
    print("\n🏗️  Kreiranje DNA baza...")
    try:
        results = build_all(factory_dir, gold_dir, dna_dir)
        
        print("\n" + "="*60)
        print("📊 REZULTATI BUILD PROCESA")
        print("="*60)
        
        for db_name, stats in results.items():
            status = "✅" if stats.get('created', False) else "❌"
            track_count = stats.get('track_count', 0)
            profile_count = stats.get('profile_count', 0)
            print(f"{status} {db_name}: {track_count} trackova, {profile_count} profila")
        
        # Finalni status
        print("\n" + "="*60)
        print("🎯 FINALNI STATUS")
        print("="*60)
        final_status = dna_status(dna_dir)
        
        created_count = sum(1 for v in final_status.values() if v.get('exists', False))
        total_count = len(final_status)
        
        print(f"\n✅ Kreirano baza: {created_count}/{total_count}")
        
        if created_count == total_count:
            print("\n🎉 DNA SISTEM JE SPREMAN ZA RAD!")
            return True
        else:
            print("\n⚠️  Neke baze nisu kreirane. Proverite logove.")
            return False
            
    except Exception as e:
        print(f"\n❌ KRITIČNA GREŠKA: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = bootstrap()
    sys.exit(0 if success else 1)
