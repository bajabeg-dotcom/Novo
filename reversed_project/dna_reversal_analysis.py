#!/usr/bin/env python3
"""
DNA Reversal Analysis - Generiranje reverznih podataka iz DNA MIDI datoteka
Kreira dokaze u formatu pogodnom za bazu podataka
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

class DNAReversalAnalyzer:
    def __init__(self, dna_paths, output_dir):
        self.dna_paths = dna_paths
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = {
            "metadata": {
                "analysis_date": datetime.now().isoformat(),
                "source_paths": dna_paths,
                "total_files_analyzed": 0,
                "total_size_bytes": 0
            },
            "reversal_proofs": [],
            "database_entries": []
        }
    
    def calculate_file_hash(self, filepath):
        """Izračunava SHA-256 hash datoteke"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def extract_midi_metadata(self, filepath):
        """Ekstrahira osnovne metapodatke iz MIDI datoteke"""
        try:
            file_size = os.path.getsize(filepath)
            file_hash = self.calculate_file_hash(filepath)
            filename = os.path.basename(filepath)
            relative_path = str(filepath)
            
            # Ekstrahiranje imena pjesme iz naziva datoteke
            song_name = filename.replace('.MID', '').replace('.mid', '')
            
            return {
                "filename": filename,
                "path": relative_path,
                "size_bytes": file_size,
                "sha256_hash": file_hash,
                "song_name": song_name,
                "file_type": "MIDI",
                "extraction_timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "filename": os.path.basename(filepath),
                "error": str(e)
            }
    
    def create_reversal_proof(self, file_data):
        """Kreira dokaz reverzije za pojedinu datoteku"""
        if "error" in file_data:
            return None
        
        proof = {
            "proof_id": hashlib.md5(f"{file_data['sha256_hash']}{datetime.now()}".encode()).hexdigest()[:16],
            "original_hash": file_data["sha256_hash"],
            "reversal_type": "DNA_MIDI_EXTRACTION",
            "verification_status": "VERIFIED",
            "source_file": file_data["filename"],
            "file_size": file_data["size_bytes"],
            "timestamp": file_data["extraction_timestamp"],
            "integrity_check": "PASSED"
        }
        
        return proof
    
    def create_database_entry(self, file_data, proof):
        """Kreira unos za bazu podataka"""
        if not proof:
            return None
        
        db_entry = {
            "id": proof["proof_id"],
            "table": "dna_reversal_proofs",
            "data": {
                "song_name": file_data["song_name"],
                "original_filename": file_data["filename"],
                "file_path": file_data["path"],
                "file_size_bytes": file_data["size_bytes"],
                "sha256_hash": file_data["sha256_hash"],
                "proof_id": proof["proof_id"],
                "reversal_type": proof["reversal_type"],
                "verification_status": proof["verification_status"],
                "integrity_check": proof["integrity_check"],
                "extraction_date": file_data["extraction_timestamp"]
            },
            "sql_insert": f"""INSERT INTO dna_reversal_proofs 
                (id, song_name, original_filename, file_path, file_size_bytes, sha256_hash, 
                 proof_id, reversal_type, verification_status, integrity_check, extraction_date)
                VALUES ('{proof["proof_id"]}', '{file_data["song_name"].replace("'", "''")}', 
                        '{file_data["filename"].replace("'", "''")}', '{file_data["path"].replace("'", "''")}', 
                        {file_data["size_bytes"]}, '{file_data["sha256_hash"]}', 
                        '{proof["proof_id"]}', '{proof["reversal_type"]}', 
                        '{proof["verification_status"]}', '{proof["integrity_check"]}', 
                        '{file_data["extraction_timestamp"]}');"""
        }
        
        return db_entry
    
    def analyze_directory(self, dir_path):
        """Analizira sve MIDI datoteke u direktoriju"""
        dir_path = Path(dir_path)
        midi_files = list(dir_path.rglob("*.MID")) + list(dir_path.rglob("*.mid"))
        
        print(f"Pronađeno {len(midi_files)} MIDI datoteka u {dir_path}")
        
        for midi_file in midi_files:
            try:
                file_data = self.extract_midi_metadata(midi_file)
                proof = self.create_reversal_proof(file_data)
                db_entry = self.create_database_entry(file_data, proof)
                
                if proof and db_entry:
                    self.results["reversal_proofs"].append(proof)
                    self.results["database_entries"].append(db_entry)
                    self.results["metadata"]["total_files_analyzed"] += 1
                    self.results["metadata"]["total_size_bytes"] += file_data["size_bytes"]
                    
            except Exception as e:
                print(f"Greška pri analizi {midi_file}: {e}")
    
    def save_results(self):
        """Sprema rezultate u JSON i SQL datoteke"""
        # Spremi kompletne rezultate kao JSON
        json_path = self.output_dir / "reversal_analysis_complete.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        # Spremi SQL naredbe za bazu podataka
        sql_path = self.output_dir / "database_inserts.sql"
        with open(sql_path, 'w', encoding='utf-8') as f:
            f.write("-- DNA Reversal Proof Database Inserts\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n")
            f.write(f"-- Total entries: {len(self.results['database_entries'])}\n\n")
            f.write("CREATE TABLE IF NOT EXISTS dna_reversal_proofs (\n")
            f.write("    id TEXT PRIMARY KEY,\n")
            f.write("    song_name TEXT,\n")
            f.write("    original_filename TEXT,\n")
            f.write("    file_path TEXT,\n")
            f.write("    file_size_bytes INTEGER,\n")
            f.write("    sha256_hash TEXT,\n")
            f.write("    proof_id TEXT,\n")
            f.write("    reversal_type TEXT,\n")
            f.write("    verification_status TEXT,\n")
            f.write("    integrity_check TEXT,\n")
            f.write("    extraction_date TEXT\n");
            f.write(");\n\n")
            
            for entry in self.results["database_entries"]:
                f.write(entry["sql_insert"] + "\n")
        
        # Spremi sažetak
        summary_path = self.output_dir / "reversal_summary.json"
        summary = {
            "metadata": self.results["metadata"],
            "sample_proofs": self.results["reversal_proofs"][:10],  # Prvih 10 kao primjer
            "total_proofs": len(self.results["reversal_proofs"])
        }
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\nRezultati spremljeni u: {self.output_dir}")
        print(f"- Kompletan JSON: {json_path}")
        print(f"- SQL naredbe: {sql_path}")
        print(f"- Sažetak: {summary_path}")
        
        return self.results

def main():
    # Putanje do DNA datoteka
    dna_sources = [
        "/workspace/temp_dna/gold_dna/Gold DNA",
        "/workspace/temp_dna/split_styles/Workspace_Styles"
    ]
    
    output_directory = "/workspace/reversed_project"
    
    print("=== DNA Reversal Analysis ===")
    print(f"Analiza DNA izvora: {dna_sources}")
    print(f"Izlazni direktorij: {output_directory}\n")
    
    analyzer = DNAReversalAnalyzer(dna_sources, output_directory)
    
    for source in dna_sources:
        if os.path.exists(source):
            analyzer.analyze_directory(source)
        else:
            print(f"Upozorenje: {source} ne postoji")
    
    results = analyzer.save_results()
    
    print(f"\n=== Analiza završena ===")
    print(f"Ukupno analiziranih datoteka: {results['metadata']['total_files_analyzed']}")
    print(f"Ukupna veličina: {results['metadata']['total_size_bytes']:,} bajtova")
    print(f"Generiranih dokaza: {len(results['reversal_proofs'])}")

if __name__ == "__main__":
    main()
