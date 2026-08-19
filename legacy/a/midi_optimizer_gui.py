#!/usr/bin/env python3
"""
KORG PA800 MIDI OPTIMIZER
Desktop GUI Application

Features:
- Drag & drop MIDI files
- Real-time preview
- Multiple optimization strategies
- Batch processing
- Visual feedback
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from midi_optimizer_core import (
    MIDIOptimizerApp, 
    OptimizationStrategy,
    MIDIParser
)
import threading
from datetime import datetime


class MIDIOptimizerGUI:
    """Desktop GUI for MIDI Optimizer"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("KORG PA800 MIDI Optimizer")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        
        # Database
        self.db_path = None
        self.app = None
        
        # Try default locations
        default_paths = [
            Path("ai_database.json"),
            Path("/mnt/user-data/outputs/ai_database.json"),
            Path.home() / "ai_database.json",
            Path.cwd() / "ai_database.json"
        ]
        
        for path in default_paths:
            if path.exists():
                self.db_path = path
                break
        
        self.current_file = None
        self.analysis_data = None
        
        self._create_ui()
        self._load_database()
        self._bind_dnd()
    
    def _create_ui(self):
        """Create user interface"""
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Title
        title = ttk.Label(main_frame, text="🎹 KORG PA800 MIDI Optimizer",
                         font=("Arial", 16, "bold"))
        title.grid(row=0, column=0, columnspan=3, pady=10)
        
        # Database status frame
        db_frame = ttk.LabelFrame(main_frame, text="Sound Behaviour Database", padding="10")
        db_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.db_status_var = tk.StringVar(value="⏳ Loading database...")
        self.db_label = ttk.Label(db_frame, textvariable=self.db_status_var, foreground="gray")
        self.db_label.grid(row=0, column=0, sticky="w", padx=5)
        
        browse_db_btn = ttk.Button(db_frame, text="Browse Database",
                                  command=self.browse_database)
        browse_db_btn.grid(row=0, column=1, padx=5)
        
        refresh_db_btn = ttk.Button(db_frame, text="Reload",
                                   command=self._load_database)
        refresh_db_btn.grid(row=0, column=2, padx=5)
        
        subtitle = ttk.Label(main_frame, text="Optimize MIDI using factory sound behaviour patterns",
                            font=("Arial", 10))
        subtitle.grid(row=1, column=0, columnspan=3, pady=5)
        
        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="Input MIDI File", padding="10")
        file_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.file_path_var = tk.StringVar(value="Drag MIDI file here or click Browse")
        self.file_label = ttk.Label(file_frame, textvariable=self.file_path_var,
                                    foreground="gray", relief="solid", borderwidth=2)
        self.file_label.grid(row=0, column=0, sticky="ew", pady=10)
        file_frame.columnconfigure(0, weight=1)
        
        button_frame = ttk.Frame(file_frame)
        button_frame.grid(row=1, column=0, sticky="ew")
        
        browse_btn = ttk.Button(button_frame, text="Browse MIDI File", 
                               command=self.browse_file)
        browse_btn.pack(side="left", padx=5)
        
        analyze_btn = ttk.Button(button_frame, text="Analyze File",
                                command=self.analyze_file)
        analyze_btn.pack(side="left", padx=5)
        
        # Analysis results frame
        analysis_frame = ttk.LabelFrame(main_frame, text="File Analysis", padding="10")
        analysis_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.analysis_text = tk.Text(analysis_frame, height=6, width=80, 
                                    state="disabled", relief="solid", borderwidth=1)
        self.analysis_text.grid(row=0, column=0, sticky="ew")
        
        scrollbar = ttk.Scrollbar(analysis_frame, orient="vertical", 
                                 command=self.analysis_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.analysis_text.config(yscrollcommand=scrollbar.set)
        
        analysis_frame.columnconfigure(0, weight=1)
        
        # Strategy selection
        strategy_frame = ttk.LabelFrame(main_frame, text="Optimization Strategy", padding="10")
        strategy_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.strategy_var = tk.StringVar(value="AUTHENTIC")
        
        strategies = [
            ("🎯 Authentic - Match factory patterns exactly", "AUTHENTIC"),
            ("🎨 Expressive - Emphasize dynamics", "EXPRESSIVE"),
            ("⚖️  Balanced - Conservative adjustments", "BALANCED"),
            ("💪 Aggressive - Maximize character", "AGGRESSIVE")
        ]
        
        for text, value in strategies:
            rb = ttk.Radiobutton(strategy_frame, text=text, variable=self.strategy_var,
                               value=value)
            rb.pack(anchor="w", pady=5)
        
        # Strategy description
        self.description_var = tk.StringVar()
        desc_label = ttk.Label(strategy_frame, textvariable=self.description_var,
                             foreground="blue", font=("Arial", 9))
        desc_label.pack(anchor="w", pady=5)
        
        self.strategy_var.trace_add("write", self._update_description)
        
        # Output frame
        output_frame = ttk.LabelFrame(main_frame, text="Output Options", padding="10")
        output_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)
        
        ttk.Label(output_frame, text="Output File:").pack(side="left", padx=5)
        
        self.output_path_var = tk.StringVar(value="")
        output_entry = ttk.Entry(output_frame, textvariable=self.output_path_var, 
                               state="readonly", width=50)
        output_entry.pack(side="left", padx=5, expand=True, fill="x")
        
        browse_output_btn = ttk.Button(output_frame, text="Browse",
                                      command=self.browse_output)
        browse_output_btn.pack(side="left", padx=5)
        
        # Progress frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress.pack(side="left", expand=True, fill="x", padx=5)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        status_label.pack(side="left", padx=10)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=20)
        
        optimize_btn = ttk.Button(button_frame, text="🚀 Optimize MIDI",
                                 command=self.optimize)
        optimize_btn.pack(side="left", padx=10, pady=5)
        
        batch_btn = ttk.Button(button_frame, text="📦 Batch Process",
                              command=self.batch_process)
        batch_btn.pack(side="left", padx=10, pady=5)
        
        reset_btn = ttk.Button(button_frame, text="🔄 Reset",
                              command=self.reset)
        reset_btn.pack(side="left", padx=10, pady=5)
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=10)
        main_frame.rowconfigure(8, weight=1)
        
        self.results_text = tk.Text(results_frame, height=8, width=80,
                                   state="disabled", relief="solid", borderwidth=1)
        self.results_text.pack(side="left", fill="both", expand=True)
        
        results_scroll = ttk.Scrollbar(results_frame, orient="vertical",
                                      command=self.results_text.yview)
        results_scroll.pack(side="right", fill="y")
        self.results_text.config(yscrollcommand=results_scroll.set)
    
    def _load_database(self):
        """Load database with status indication"""
        if not self.db_path or not self.db_path.exists():
            self.db_status_var.set("❌ Database not found")
            self.db_label.config(foreground="red")
            self.app = None
            return
        
        try:
            self.app = MIDIOptimizerApp(self.db_path)
            self.db_status_var.set(f"✅ Loaded: {self.db_path.name}")
            self.db_label.config(foreground="green")
        except Exception as e:
            self.db_status_var.set(f"❌ Error loading database: {str(e)}")
            self.db_label.config(foreground="red")
            self.app = None
    
    def browse_database(self):
        """Browse and select database file"""
        filename = filedialog.askopenfilename(
            title="Select Sound Behaviour Database",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=str(Path.home())
        )
        
        if filename:
            self.db_path = Path(filename)
            self._load_database()

    def _update_description(self, *args):
        """Update strategy description"""
        descriptions = {
            "AUTHENTIC": "Use exact factory patterns from KORG PA800 analysis. Best for authentic sound.",
            "EXPRESSIVE": "Enhance dynamics while preserving musicality. Good for more expressive performances.",
            "BALANCED": "Conservative adjustments. Safe option that preserves original intent.",
            "AGGRESSIVE": "Maximize sound character. Bold adjustments for pronounced effect."
        }
        self.description_var.set(descriptions.get(self.strategy_var.get(), ""))
    
    def _bind_dnd(self):
        """Bind drag & drop events (requires tkinterdnd2; skipped otherwise)"""
        def drop(event):
            files = self.root.tk.splitlist(event.data)
            if files:
                self.load_file(Path(files[0]))

        try:
            self.file_label.drop_target_register('*')
            self.file_label.dnd_bind('<<Drop>>', drop)
        except (AttributeError, tk.TclError):
            pass
    
    def browse_file(self):
        """Browse and select MIDI file"""
        filename = filedialog.askopenfilename(
            title="Select MIDI file",
            filetypes=[("MIDI files", "*.mid"), ("All files", "*.*")]
        )
        if filename:
            self.load_file(Path(filename))
    
    def load_file(self, filepath: Path):
        """Load MIDI file"""
        if not filepath.exists():
            messagebox.showerror("Error", f"File not found: {filepath}")
            return
        
        self.current_file = filepath
        self.file_path_var.set(f"📁 {filepath.name}")
        self.file_label.config(foreground="black")
        
        # Set default output
        output_file = filepath.parent / f"{filepath.stem}_optimized.mid"
        self.output_path_var.set(str(output_file))
        
        self.status_var.set(f"Loaded: {filepath.name}")
    
    def browse_output(self):
        """Browse and select output file"""
        filename = filedialog.asksaveasfilename(
            title="Save optimized MIDI as",
            filetypes=[("MIDI files", "*.mid")],
            defaultextension=".mid"
        )
        if filename:
            self.output_path_var.set(filename)
    
    def analyze_file(self):
        """Analyze selected MIDI file"""
        if not self.app:
            messagebox.showerror("Error", "Sound Behaviour Database not loaded!\n\nPlease:\n1. Click 'Browse Database'\n2. Select ai_database.json file\n3. Try again")
            return
        
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a MIDI file first")
            return
        
        self._log_analysis("Analyzing MIDI file...\n")
        
        def _analyze():
            try:
                self.analysis_data = self.app.analyze_file(self.current_file)
                
                # Update display
                analysis_text = f"File: {self.current_file.name}\n"
                analysis_text += f"Size: {self.current_file.stat().st_size} bytes\n"
                analysis_text += f"Total Notes: {self.analysis_data.get('total_notes', 0)}\n"
                analysis_text += f"Programs Used: {len(self.analysis_data.get('programs', {}))}\n"
                analysis_text += f"\nProgram Details:\n"
                
                for prog, count in sorted(self.analysis_data.get('programs', {}).items()):
                    vel_stats = self.analysis_data.get('velocity_stats', {}).get(str(prog), {})
                    analysis_text += f"  Prog {prog:3d}: {count:5d} notes, "
                    analysis_text += f"Vel {vel_stats.get('min', 0):3d}-{vel_stats.get('max', 0):3d}\n"
                
                self._update_analysis_display(analysis_text)
                self.status_var.set("Analysis complete")
            
            except Exception as e:
                messagebox.showerror("Error", f"Analysis failed: {str(e)}")
                self.status_var.set("Error during analysis")
        
        # Run in thread to keep UI responsive
        thread = threading.Thread(target=_analyze, daemon=True)
        thread.start()
    
    def optimize(self):
        """Optimize MIDI file"""
        if not self.app:
            messagebox.showerror("Error", "Sound Behaviour Database not loaded!\n\nPlease:\n1. Click 'Browse Database'\n2. Select ai_database.json file\n3. Try again")
            return
        
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a MIDI file first")
            return
        
        if not self.output_path_var.get():
            messagebox.showwarning("Warning", "Please specify output file")
            return
        
        output_file = Path(self.output_path_var.get())
        strategy = OptimizationStrategy[self.strategy_var.get()]
        
        self._log_result("Starting optimization...\n")
        self.progress.start()
        self.status_var.set("Optimizing...")
        
        def _optimize():
            try:
                result = self.app.optimize_file(self.current_file, output_file, strategy)
                
                if result.get("success"):
                    result_text = f"✅ Optimization successful!\n\n"
                    result_text += f"Input:  {result['input_file']}\n"
                    result_text += f"Output: {result['output_file']}\n"
                    result_text += f"Strategy: {result['strategy']}\n\n"
                    result_text += f"Total Notes: {result['total_notes']}\n"
                    result_text += f"Adjusted: {result['adjusted_notes']} "
                    result_text += f"({result['adjusted_notes']*100/result['total_notes']:.1f}%)\n"
                    result_text += f"Avg Velocity Change: {result['average_adjustment']:.1f}\n"
                    result_text += f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    
                    self._log_result(result_text)
                    self.status_var.set("✅ Optimization complete!")
                    
                    if messagebox.askyesno("Success", "Open optimized file?"):
                        import subprocess
                        try:
                            if Path(output_file).exists():
                                subprocess.Popen(["xdg-open", str(output_file)])
                        except:
                            pass
                else:
                    self._log_result(f"❌ {result.get('error', 'Unknown error')}\n")
                    self.status_var.set("Error during optimization")
            
            except Exception as e:
                messagebox.showerror("Error", f"Optimization failed: {str(e)}")
                self.status_var.set("Error")
            
            finally:
                self.progress.stop()
        
        thread = threading.Thread(target=_optimize, daemon=True)
        thread.start()
    
    def batch_process(self):
        """Batch process multiple MIDI files"""
        if not self.app:
            messagebox.showerror("Error", "Sound Behaviour Database not loaded!\n\nPlease:\n1. Click 'Browse Database'\n2. Select ai_database.json file\n3. Try again")
            return
        
        files = filedialog.askopenfilenames(
            title="Select MIDI files to batch process",
            filetypes=[("MIDI files", "*.mid"), ("All files", "*.*")]
        )
        
        if not files:
            return
        
        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            return
        
        output_dir = Path(output_dir)
        strategy = OptimizationStrategy[self.strategy_var.get()]
        
        self._log_result(f"Batch processing {len(files)} files...\n\n")
        self.progress.start()
        
        def _batch():
            results = []
            for i, filepath in enumerate(files):
                try:
                    input_path = Path(filepath)
                    output_path = output_dir / f"{input_path.stem}_optimized.mid"
                    
                    self.status_var.set(f"Processing {i+1}/{len(files)}: {input_path.name}")
                    
                    result = self.app.optimize_file(input_path, output_path, strategy)
                    results.append((input_path.name, result.get("success")))
                    
                except Exception as e:
                    results.append((filepath, False))
            
            # Summary
            summary = f"\n{'='*60}\n"
            summary += f"BATCH PROCESSING COMPLETE\n"
            summary += f"{'='*60}\n\n"
            summary += f"Total files: {len(results)}\n"
            summary += f"Successful: {sum(1 for _, s in results if s)}\n"
            summary += f"Failed: {sum(1 for _, s in results if not s)}\n\n"
            
            for filename, success in results:
                status = "✅" if success else "❌"
                summary += f"{status} {filename}\n"
            
            self._log_result(summary)
            self.status_var.set(f"Batch complete: {len(results)} files")
            self.progress.stop()
        
        thread = threading.Thread(target=_batch, daemon=True)
        thread.start()
    
    def reset(self):
        """Reset application"""
        self.current_file = None
        self.file_path_var.set("Drag MIDI file here or click Browse")
        self.output_path_var.set("")
        self._update_analysis_display("")
        self._log_result("")
        self.status_var.set("Ready")
    
    def _update_analysis_display(self, text: str):
        """Update analysis display"""
        self.analysis_text.config(state="normal")
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(tk.END, text)
        self.analysis_text.config(state="disabled")
    
    def _log_analysis(self, text: str):
        """Log to analysis display"""
        self.analysis_text.config(state="normal")
        self.analysis_text.insert(tk.END, text)
        self.analysis_text.config(state="disabled")
    
    def _log_result(self, text: str):
        """Log to results display"""
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
        self.results_text.config(state="disabled")
    
    def _update_progress(self, value: int, max_value: int):
        """Update progress bar"""
        self.progress["value"] = (value / max_value * 100) if max_value > 0 else 0
        self.root.update()


def main():
    root = tk.Tk()
    
    # Set window icon (if available)
    try:
        root.iconbitmap("piano.ico")
    except:
        pass
    
    app = MIDIOptimizerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
