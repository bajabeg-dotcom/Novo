"""
Safety Gate Module - P0 Critical Component
Blokira izvoz ako bilo koji track ili nota nestane.
"""

class SafetyGateError(Exception):
    pass

class SafetyGate:
    def __init__(self, baseline_data):
        self.baseline = baseline_data
        self.original_tracks = baseline_data['total_tracks']
        self.original_notes = baseline_data['total_notes']
        self.locked_tracks = baseline_data.get('critical_tracks', [])
        
    def validate_integrity(self, result_data):
        """Provjera da nema gubitka podataka."""
        errors = []
        
        # Provjera broja trackova
        if result_data['total_tracks'] < self.original_tracks:
            errors.append(f"KRITIČNO: Izgubljeno {self.original_tracks - result_data['total_tracks']} trackova!")
            
        # Provjera broja nota
        if result_data['total_notes'] < self.original_notes:
            errors.append(f"KRITIČNO: Izgubljeno {self.original_notes - result_data['total_notes']} nota!")
            
        # Provjera locked trackova
        for locked in self.locked_tracks:
            if not result_data.get(f"track_{locked['index']}_preserved", False):
                errors.append(f"KRITIČNO: Zaključani track '{locked['name']}' je modificiran ili obrisan!")
                
        if errors:
            raise SafetyGateError("\n".join(errors))
            
        return True
        
    def generate_report(self, result_data):
        """Generira izvještaj o uspješnosti."""
        return {
            "status": "PASSED",
            "original_tracks": self.original_tracks,
            "result_tracks": result_data['total_tracks'],
            "original_notes": self.original_notes,
            "result_notes": result_data['total_notes'],
            "integrity": "100% Očuvano",
            "timestamp": datetime.now().isoformat()
        }
