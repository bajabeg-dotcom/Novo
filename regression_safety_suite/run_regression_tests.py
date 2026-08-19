"""
Regression Test Runner
Pokreće sve testove protiv Safety Gate-a.
"""
import json
import sys
import os

# Dodajemo parent directory u path da možemo importirati safety_gate
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from safety_gates.safety_gate import SafetyGate, SafetyGateError

def run_nevera_moja_test():
    print("="*60)
    print("POKRETANJE TESTA: NEVERA MOJA (Case Study)")
    print("="*60)
    
    # Učitaj baseline
    with open('test_cases/nevera_moja_baseline.json', 'r', encoding='utf-8') as f:
        baseline = json.load(f)
        
    gate = SafetyGate(baseline)
    
    # TEST 1: Simulacija LOŠEG optimizera (Mora biti BLOKIRAN)
    print("\n[TEST 1] Simulacija starog buga (gubitak trackova)...")
    try:
        bad_result = {
            "total_tracks": 7,
            "total_notes": 4492,
            "track_0_preserved": False
        }
        gate.validate_integrity(bad_result)
        print("❌ GREŠKA: Loš rezultat nije bio blokiran! (Ovo ne smije proći)")
        return False
    except SafetyGateError as e:
        print(f"✅ USPJEH: Safety Gate je blokirao loš rezultat.")
        print(f"   Razlog: {str(e)[:50]}...")
        
    # TEST 2: Simulacija DOBROG optimizera (Mora PROĆI)
    print("\n[TEST 2] Simulacija novog sigurnog optimizera...")
    try:
        good_result = {
            "total_tracks": 16,
            "total_notes": 8340,
            "track_0_preserved": True,
            "track_1_preserved": True,
            "track_5_preserved": True
        }
        gate.validate_integrity(good_result)
        report = gate.generate_report(good_result)
        print("✅ USPJEH: Dobri rezultat je prošao.")
        print(f"   Status: {report['status']}")
        print(f"   Integritet: {report['integrity']}")
        
        # Spremi rezultat
        with open('results/nevera_moja_test_result.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        return True
        
    except SafetyGateError as e:
        print(f"❌ GREŠKA: Dobar rezultat je bio blokiran! {e}")
        return False

if __name__ == "__main__":
    success = run_nevera_moja_test()
    if success:
        print("\n" + "="*60)
        print("REGRESIJSKI TESTOVI PROŠLI - SUSTAV JE SIGURAN")
        print("="*60)
    else:
        print("\nREGRESIJSKI TESTOVI PALI - SUSTAV NIJE SIGURAN")
        sys.exit(1)
