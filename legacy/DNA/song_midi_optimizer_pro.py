#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SONG MIDI OPTIMIZER - Ultimate Modular Edition
Based on Factory Styles & Gold Standards
Architecture: Core -> Services -> Models -> GUI
Profile Principle: VELOCITY.TIMING.DURATION (e.g., 120.222.112)
"""

import os
import sys
import json
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from pathlib import Path
import mido
import numpy as np

# ==============================================================================
# CONFIGURATION & LOGGING
# ==============================================================================

class Config:
    APP_NAME = "Song MIDI Optimizer Pro"
    VERSION = "2.0.0"
    AUTHOR = "AI Assistant"
    SUPPORTED_FORMATS = ['.mid', '.midi']
    DEFAULT_PROFILE = "120.128.100"  # V.T.D
    
    # Paths
    BASE_DIR = Path(__file__).parent
    PROFILES_DIR = BASE_DIR / "profiles"
    LOGS_DIR = BASE_DIR / "logs"
    
    @classmethod
    def init_dirs(cls):
        cls.PROFILES_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOGS_DIR / 'optimizer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MIDIOptimizer")

# ==============================================================================
# MODELS (Data Structures)
# ==============================================================================

@dataclass
class InstrumentProfile:
    """
    Represents an instrument profile based on V.T.D principle.
    Format: Velocity.Timing.Duration
    """
    name: str
    category: str  # e.g., "Keys", "Strings", "Drums", "Bass"
    velocity_base: int  # 0-127
    velocity_variance: int  # +/- variation
    timing_resolution: int  # ticks or ms tolerance
    timing_humanize: float  # 0.0 (strict) to 1.0 (loose)
    duration_base: float  # multiplier of note length
    duration_variance: float
    
    # Derived "Signature" string (e.g., "120.222.112")
    @property
    def signature(self) -> str:
        v = self.velocity_base
        t = int(self.timing_resolution * 10) # Scale for signature
        d = int(self.duration_base * 100)
        return f"{v}.{t}.{d}"
    
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_signature(cls, name: str, signature: str, category: str = "Custom") -> 'InstrumentProfile':
        try:
            parts = signature.split('.')
            if len(parts) != 3: raise ValueError
            v = int(parts[0])
            t = int(parts[1]) / 10.0
            d = int(parts[2]) / 100.0
            return cls(
                name=name, category=category,
                velocity_base=v, velocity_variance=15,
                timing_resolution=t, timing_humanize=0.3,
                duration_base=d, duration_variance=0.1
            )
        except Exception as e:
            logger.error(f"Invalid signature format: {signature}")
            return cls.get_default()

    @classmethod
    def get_default(cls) -> 'InstrumentProfile':
        return cls(name="Default", category="General", velocity_base=100, 
                   velocity_variance=20, timing_resolution=128, timing_humanize=0.2,
                   duration_base=1.0, duration_variance=0.1)

@dataclass
class TrackAnalysis:
    track_index: int
    channel: int
    detected_instrument: str
    note_count: int
    avg_velocity: float
    velocity_range: Tuple[int, int]
    timing_drift: float
    quality_score: float  # 0-100
    issues: List[str]

@dataclass
class OptimizationReport:
    total_changes: int
    velocity_changes: int
    timing_changes: int
    duration_changes: int
    tracks_processed: int
    details: List[str]

# ==============================================================================
# CORE SERVICES (Logic Layer)
# ==============================================================================

class ProfileDatabase:
    """Manages the library of Instrument Profiles (Factory & Gold)"""
    
    def __init__(self):
        self.profiles: Dict[str, InstrumentProfile] = {}
        self._load_factory_profiles()
        self._load_gold_standards()
    
    def _load_factory_profiles(self):
        """Standard Factory Styles (Generic but effective)"""
        factory = [
            InstrumentProfile("Acoustic Piano", "Keys", 110, 20, 120, 0.3, 1.1, 0.1),
            InstrumentProfile("Electric Piano", "Keys", 95, 15, 100, 0.4, 0.9, 0.15),
            InstrumentProfile("Synth Lead", "Synth", 120, 10, 80, 0.1, 0.8, 0.05),
            InstrumentProfile("Bass Guitar", "Bass", 105, 15, 140, 0.2, 1.2, 0.1),
            InstrumentProfile("Drums Kit", "Drums", 127, 5, 20, 0.05, 0.5, 0.0),
            InstrumentProfile("String Ensemble", "Strings", 85, 25, 150, 0.5, 1.4, 0.2),
        ]
        for p in factory:
            self.profiles[p.name] = p
            
    def _load_gold_standards(self):
        """High-end Gold Standard Profiles (Precision tuned)"""
        gold = [
            # Signature: ~120.222.112 style logic mapped to params
            InstrumentProfile("Gold Grand Piano", "Keys", 120, 18, 222, 0.35, 1.12, 0.08),
            InstrumentProfile("Gold Session Bass", "Bass", 115, 12, 210, 0.15, 1.05, 0.05),
            InstrumentProfile("Gold Orchestral Strings", "Strings", 90, 30, 240, 0.6, 1.35, 0.25),
            InstrumentProfile("Gold Drum Room", "Drums", 118, 8, 180, 0.1, 0.6, 0.05),
        ]
        for p in gold:
            self.profiles[p.name] = p

    def get_profile(self, name: str) -> InstrumentProfile:
        return self.profiles.get(name, InstrumentProfile.get_default())
    
    def get_all_names(self) -> List[str]:
        return list(self.profiles.keys())
    
    def match_instrument(self, track_stats: Dict) -> str:
        """Heuristic matching based on track statistics"""
        avg_vel = track_stats.get('avg_velocity', 100)
        note_range = track_stats.get('range', 0)
        note_count = track_stats.get('count', 0)
        
        # Simple heuristic logic
        if note_range < 15 and avg_vel > 100:
            return "Drums Kit"
        elif note_range < 20 and avg_vel > 90:
            return "Bass Guitar"
        elif note_range > 60:
            return "Acoustic Piano" if avg_vel > 80 else "String Ensemble"
        else:
            return "Electric Piano"

class MIDIAnalyzerService:
    """Analyzes MIDI files and detects instruments/issues"""
    
    def analyze_track(self, track: mido.MidiTrack, index: int) -> TrackAnalysis:
        notes = []
        velocities = []
        deltas = []
        channel = 0
        last_time = 0
        
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                notes.append(msg.note)
                velocities.append(msg.velocity)
                channel = msg.channel
            if msg.time > 0:
                deltas.append(msg.time)
            last_time += msg.time
            
        if not notes:
            return TrackAnalysis(index, channel, "Empty", 0, 0, (0,0), 0.0, 0.0, ["No notes found"])
        
        avg_vel = sum(velocities) / len(velocities)
        vel_range = (min(velocities), max(velocities))
        drift = np.std(deltas) if deltas else 0.0
        note_range = max(notes) - min(notes) if notes else 0
        
        # Detect Instrument
        stats = {'avg_velocity': avg_vel, 'range': note_range, 'count': len(notes)}
        db = ProfileDatabase()
        inst_name = db.match_instrument(stats)
        
        # Calculate Quality Score (0-100)
        score = 100
        issues = []
        if avg_vel < 40: score -= 20; issues.append("Low velocity")
        if avg_vel > 120: score -= 10; issues.append("Clipping risk")
        if vel_range[1] - vel_range[0] < 10: score -= 15; issues.append("No dynamics")
        if drift > 50: score -= 10; issues.append("Timing drift")
        if len(notes) < 5: score -= 20; issues.append("Too sparse")
        
        score = max(0, min(100, score))
        
        return TrackAnalysis(
            track_index=index, channel=channel, detected_instrument=inst_name,
            note_count=len(notes), avg_velocity=avg_vel, velocity_range=vel_range,
            timing_drift=drift, quality_score=score, issues=issues
        )

    def analyze_file(self, midi_file: mido.MidiFile) -> List[TrackAnalysis]:
        results = []
        for i, track in enumerate(midi_file.tracks):
            results.append(self.analyze_track(track, i))
        return results

class MIDIOptimizerService:
    """Applies optimization rules based on profiles"""
    
    def __init__(self):
        self.db = ProfileDatabase()
        self.report = OptimizationReport(0,0,0,0,0,[])
        
    def apply_profile(self, track: mido.MidiTrack, profile: InstrumentProfile) -> mido.MidiTrack:
        new_track = mido.MidiTrack()
        changes = {'vel': 0, 'time': 0, 'dur': 0}
        
        last_note_on = {} # Note pitch -> tick time
        
        for msg in track:
            new_msg = msg.copy()
            
            if msg.type == 'note_on' and msg.velocity > 0:
                # 1. Velocity Optimization
                target_v = profile.velocity_base
                variance = profile.velocity_variance
                # Add slight humanization
                import random
                new_v = int(np.clip(
                    target_v + random.randint(-variance, variance), 
                    1, 127
                ))
                if new_v != msg.velocity:
                    new_msg.velocity = new_v
                    changes['vel'] += 1
                
                last_note_on[msg.note] = 0 # Reset relative time tracker
                
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                # 2. Duration Optimization (simplified via timing adjustment)
                # In real MIDI, duration is time between on and off. 
                # We can slightly adjust the note_off timing here if needed.
                pass
                
            # 3. Timing Optimization (Quantize/Humanize)
            # This is complex in a stream, usually done by accumulating ticks
            # For this modular demo, we apply a simple jitter reduction if humanize is low
            if msg.time > 0 and profile.timing_humanize < 0.1:
                # Strict quantization logic would go here
                pass
            
            new_track.append(new_msg)
            
        self.report.velocity_changes += changes['vel']
        self.report.timing_changes += changes['time']
        self.report.duration_changes += changes['dur']
        return new_track

    def optimize_midi(self, midi: mido.MidiFile, assignments: Dict[int, str]) -> mido.MidiFile:
        """
        midi: Input file
        assignments: Dict mapping track_index -> profile_name
        """
        new_midi = mido.MidiFile(ticks_per_beat=midi.ticks_per_beat)
        self.report = OptimizationReport(0,0,0,0, len(assignments), [])
        
        for i, track in enumerate(midi.tracks):
            profile_name = assignments.get(i, "Default")
            profile = self.db.get_profile(profile_name)
            
            logger.info(f"Optimizing Track {i} with profile: {profile.name} ({profile.signature})")
            new_track = self.apply_profile(track, profile)
            new_midi.tracks.append(new_track)
            
            self.report.total_changes += (self.report.velocity_changes + self.report.timing_changes + self.report.duration_changes) // len(assignments) if assignments else 0
            
        return new_midi

# ==============================================================================
# GUI LAYER (Tkinter)
# ==============================================================================

class SongMIDIOptimizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{Config.APP_NAME} v{Config.VERSION}")
        self.root.geometry("1000x700")
        
        # Initialize Services
        self.analyzer = MIDIAnalyzerService()
        self.optimizer = MIDIOptimizerService()
        self.profile_db = ProfileDatabase()
        
        self.current_midi = None
        self.analysis_results = []
        self.track_assignments = {} # Track Index -> Profile Name
        
        self.setup_styles()
        self.create_menu()
        self.create_widgets()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", padding=6, relief="flat", background="#ccc")
        style.configure("TLabel", font=("Arial", 10))
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))
        
    def create_menu(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open MIDI", command=self.load_file)
        filemenu.add_command(label="Export Result", command=self.export_file)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=lambda: messagebox.showinfo("About", Config.APP_NAME))
        menubar.add_cascade(label="Help", menu=helpmenu)
        
        self.root.config(menu=menubar)

    def create_widgets(self):
        # Main Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Import & Analysis
        self.tab_import = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_import, text="📥 Import & Analysis")
        self.setup_import_tab()
        
        # Tab 2: Profile Assignment (The Core Logic)
        self.tab_profiles = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_profiles, text="🎹 Instrument Profiles")
        self.setup_profile_tab()
        
        # Tab 3: Optimization & Export
        self.tab_export = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_export, text="⚙️ Optimize & Export")
        self.setup_export_tab()
        
    def setup_import_tab(self):
        # Top Frame: Controls
        ctrl_frame = ttk.Frame(self.tab_import, padding=10)
        ctrl_frame.pack(fill='x')
        
        ttk.Button(ctrl_frame, text="Load MIDI File", command=self.load_file).pack(side='left', padx=5)
        self.lbl_status = ttk.Label(ctrl_frame, text="No file loaded", foreground="gray")
        self.lbl_status.pack(side='left', padx=10)
        
        # Middle: Analysis Treeview
        tree_frame = ttk.LabelFrame(self.tab_import, text="Track Analysis", padding=10)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        cols = ("ID", "Channel", "Instrument", "Notes", "Avg Vel", "Quality", "Issues")
        self.tree_analysis = ttk.Treeview(tree_frame, columns=cols, show='headings')
        for col in cols:
            self.tree_analysis.heading(col, text=col)
            self.tree_analysis.column(col, width=100)
        self.tree_analysis.column("Issues", width=200)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_analysis.yview)
        self.tree_analysis.configure(yscrollcommand=scrollbar.set)
        self.tree_analysis.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
    def setup_profile_tab(self):
        # Instructions
        ttk.Label(self.tab_profiles, text="Assign Profiles to Tracks (Principle: Velocity.Timing.Duration)", 
                  style="Header.TLabel").pack(pady=10)
        
        # Split View
        paned = ttk.PanedWindow(self.tab_profiles, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left: Track List
        left_frame = ttk.LabelFrame(paned, text="Tracks")
        paned.add(left_frame, weight=1)
        
        self.tree_tracks = ttk.Treeview(left_frame, columns=("ID", "Name"), show='headings')
        self.tree_tracks.heading("ID", text="Track ID")
        self.tree_tracks.heading("Name", text="Detected Instrument")
        self.tree_tracks.pack(fill='both', expand=True)
        self.tree_tracks.bind('<<TreeviewSelect>>', self.on_track_select)
        
        # Right: Profile Editor
        right_frame = ttk.LabelFrame(paned, text="Profile Configuration")
        paned.add(right_frame, weight=2)
        
        self.lbl_selected_track = ttk.Label(right_frame, text="Select a track...", font=("Arial", 12, "bold"))
        self.lbl_selected_track.pack(pady=10)
        
        form_frame = ttk.Frame(right_frame)
        form_frame.pack(fill='x', padx=20)
        
        ttk.Label(form_frame, text="Profile Preset:").grid(row=0, column=0, sticky='w', pady=5)
        self.combo_profiles = ttk.Combobox(form_frame, values=self.profile_db.get_all_names(), state="readonly")
        self.combo_profiles.grid(row=0, column=1, padx=10, pady=5)
        self.combo_profiles.bind('<<ComboboxSelected>>', self.on_profile_change)
        
        ttk.Label(form_frame, text="Signature (V.T.D):").grid(row=1, column=0, sticky='w', pady=5)
        self.entry_signature = ttk.Entry(form_frame, width=20)
        self.entry_signature.grid(row=1, column=1, padx=10, pady=5)
        ttk.Button(form_frame, text="Apply Signature", command=self.apply_custom_signature).grid(row=1, column=2, padx=5)
        
        # Details
        detail_frame = ttk.LabelFrame(right_frame, text="Parameters")
        detail_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        self.txt_details = scrolledtext.ScrolledText(detail_frame, height=10, state='disabled')
        self.txt_details.pack(fill='both', expand=True)
        
        self.btn_save_assignment = ttk.Button(right_frame, text="Save Assignment for Track", command=self.save_assignment)
        self.btn_save_assignment.pack(pady=10)
        self.btn_save_assignment.config(state='disabled')
        
    def setup_export_tab(self):
        frame = ttk.Frame(self.tab_export, padding=20)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text="Optimization Summary", style="Header.TLabel").pack(pady=10)
        
        self.txt_summary = scrolledtext.ScrolledText(frame, height=15, state='disabled')
        self.txt_summary.pack(fill='both', expand=True, pady=10)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')
        
        ttk.Button(btn_frame, text="Run Optimization", command=self.run_optimization).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Export MIDI", command=self.export_file).pack(side='left', padx=5)
        
    # --- Actions ---
    
    def load_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("MIDI Files", "*.mid *.midi")])
        if not filepath:
            return
            
        try:
            self.current_midi = mido.MidiFile(filepath)
            self.lbl_status.config(text=f"Loaded: {Path(filepath).name}", foreground="green")
            
            # Analyze
            self.analysis_results = self.analyzer.analyze_file(self.current_midi)
            
            # Populate Analysis Tab
            for item in self.tree_analysis.get_children():
                self.tree_analysis.delete(item)
            for res in self.analysis_results:
                issues_str = "; ".join(res.issues) if res.issues else "OK"
                self.tree_analysis.insert("", "end", values=(
                    res.track_index, res.channel, res.detected_instrument,
                    res.note_count, f"{res.avg_velocity:.1f}", f"{res.quality_score:.0f}/100", issues_str
                ))
                
            # Populate Profile Tab
            for item in self.tree_tracks.get_children():
                self.tree_tracks.delete(item)
            self.track_assignments = {}
            for res in self.analysis_results:
                self.tree_tracks.insert("", "end", iid=str(res.track_index), values=(res.track_index, res.detected_instrument))
                # Auto-assign detected profile
                self.track_assignments[res.track_index] = res.detected_instrument
                
            messagebox.showinfo("Success", f"Analyzed {len(self.analysis_results)} tracks.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load MIDI: {str(e)}")
            logger.error(e)

    def on_track_select(self, event):
        selection = self.tree_tracks.selection()
        if not selection:
            return
        track_id = int(selection[0])
        current_profile_name = self.track_assignments.get(track_id, "Default")
        
        self.lbl_selected_track.config(text=f"Track {track_id} Configuration")
        self.combo_profiles.set(current_profile_name)
        
        profile = self.profile_db.get_profile(current_profile_name)
        self.entry_signature.delete(0, tk.END)
        self.entry_signature.insert(0, profile.signature)
        
        self.txt_details.config(state='normal')
        self.txt_details.delete(1.0, tk.END)
        self.txt_details.insert(tk.END, f"Profile: {profile.name}\n")
        self.txt_details.insert(tk.END, f"Category: {profile.category}\n")
        self.txt_details.insert(tk.END, f"Velocity Base: {profile.velocity_base} (+/- {profile.velocity_variance})\n")
        self.txt_details.insert(tk.END, f"Timing Res: {profile.timing_resolution} (Humanize: {profile.timing_humanize})\n")
        self.txt_details.insert(tk.END, f"Duration Mult: {profile.duration_base} (+/- {profile.duration_variance})\n")
        self.txt_details.insert(tk.END, f"\nSignature Code: {profile.signature}")
        self.txt_details.config(state='disabled')
        
        self.btn_save_assignment.config(state='normal')
        self.current_editing_track = track_id

    def on_profile_change(self, event):
        # Just updates the preview, needs Save to apply to assignment
        pass

    def apply_custom_signature(self):
        sig = self.entry_signature.get()
        if not self.tree_tracks.selection():
            return
        track_id = int(self.tree_tracks.selection()[0])
        current_name = self.combo_profiles.get()
        
        # Create temp profile from signature
        temp_profile = InstrumentProfile.from_signature(current_name, sig)
        
        self.txt_details.config(state='normal')
        self.txt_details.delete(1.0, tk.END)
        self.txt_details.insert(tk.END, f"Custom Profile applied via Signature: {sig}\n")
        self.txt_details.insert(tk.END, f"Parsed Velocity: {temp_profile.velocity_base}\n")
        self.txt_details.insert(tk.END, f"Parsed Timing: {temp_profile.timing_resolution}\n")
        self.txt_details.insert(tk.END, f"Parsed Duration: {temp_profile.duration_base}")
        self.txt_details.config(state='disabled')

    def save_assignment(self):
        if not hasattr(self, 'current_editing_track'):
            return
        track_id = self.current_editing_track
        profile_name = self.combo_profiles.get()
        self.track_assignments[track_id] = profile_name
        messagebox.showinfo("Saved", f"Track {track_id} assigned to {profile_name}")

    def run_optimization(self):
        if not self.current_midi:
            messagebox.showwarning("Warning", "No MIDI file loaded.")
            return
            
        self.txt_summary.config(state='normal')
        self.txt_summary.delete(1.0, tk.END)
        self.txt_summary.insert(tk.END, "Starting Optimization...\n")
        
        try:
            optimized_midi = self.optimizer.optimize_midi(self.current_midi, self.track_assignments)
            self.optimized_result = optimized_midi
            
            report = self.optimizer.report
            self.txt_summary.insert(tk.END, f"Tracks Processed: {report.tracks_processed}\n")
            self.txt_summary.insert(tk.END, f"Total Changes: {report.total_changes}\n")
            self.txt_summary.insert(tk.END, f"- Velocity Adjustments: {report.velocity_changes}\n")
            self.txt_summary.insert(tk.END, f"- Timing Adjustments: {report.timing_changes}\n")
            self.txt_summary.insert(tk.END, f"- Duration Adjustments: {report.duration_changes}\n")
            self.txt_summary.insert(tk.END, "\nOptimization Complete! Ready to Export.")
            self.txt_summary.config(state='disabled')
            
        except Exception as e:
            self.txt_summary.insert(tk.END, f"Error during optimization: {str(e)}")
            self.txt_summary.config(state='disabled')
            logger.error(e)

    def export_file(self):
        if not hasattr(self, 'optimized_result') or self.optimized_result is None:
            messagebox.showwarning("Warning", "Run optimization first.")
            return
            
        filepath = filedialog.asksaveasfilename(defaultextension=".mid", filetypes=[("MIDI Files", "*.mid")])
        if filepath:
            try:
                self.optimized_result.save(filepath)
                messagebox.showinfo("Success", f"File saved to {filepath}")
                logger.info(f"Exported to {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {str(e)}")

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    Config.init_dirs()
    root = tk.Tk()
    app = SongMIDIOptimizerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
