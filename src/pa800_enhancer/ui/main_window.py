from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..domain.changes import ChangeSet, ChangeTransaction


def parse_user_path(value: str) -> Path:
    """Accept pasted Windows paths with or without matching outer quotes."""
    normalized = value.strip()
    if (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in {'"', "'"}
    ):
        normalized = normalized[1:-1].strip()
    return Path(normalized)


def build_selected_transaction(
    changes: ChangeSet, selected_indices: Iterable[int]
) -> ChangeTransaction:
    """Approve a selection while expanding every selected atomic group."""
    selected = {int(index) for index in selected_indices}
    if not selected:
        raise ValueError("select at least one optimization suggestion")
    if min(selected) < 0 or max(selected) >= len(changes.changes):
        raise IndexError("optimization selection is outside the suggestion list")
    selected_groups = {
        changes.changes[index].group_id
        for index in selected
        if changes.changes[index].group_id is not None
    }
    approved = [
        change.approved_copy()
        for index, change in enumerate(changes.changes)
        if index in selected
        or (change.group_id is not None and change.group_id in selected_groups)
    ]
    return ChangeSet(approved).to_transaction("gui-basic-optimization")


def format_dashboard(app, song) -> str:
    summary = app.summarize(song)
    issues = app.validate(song)
    rhythms = app.detect_rhythms(song)[:5]
    lines = [
        "Korg Pa800 MIDI Enhancer",
        "=" * 40,
        f"Source: {song.source_path or '<memory>'}",
        f"Format: {summary.format_type}  Tracks: {summary.track_count}  Events: {summary.event_count}",
        f"PPQ: {summary.ppq or 'SMPTE'}  End tick: {summary.end_tick}",
        f"Channels: {', '.join(map(str, summary.channels)) or '-'}",
        f"Notes: {summary.note_count}  Unpaired: {summary.unmatched_notes}  Sustained: {summary.sustained_notes}",
        f"Polyphony: {summary.maximum_polyphony}  Duration: {summary.duration_seconds:.3f}s",
        f"Tempo: {summary.tempo_events}  Meter: {summary.meter_events}  SysEx: {summary.sysex_events}",
        f"CC: {summary.controller_events}  NRPN/RPN: {summary.parameter_changes}  Parameter issues: {summary.parameter_issues}",
        "",
        "Validation:",
    ]
    lines.extend(f"  {item.severity.value}: {item.code} - {item.message}" for item in issues)
    if not issues:
        lines.append("  OK")
    lines.extend(("", "Rhythm candidates:"))
    lines.extend(f"  {item.score:.2f} {item.profile_id}: {item.reason}" for item in rhythms)
    return "\n".join(lines)


class EnhancerGui:
    """Small dependency-free Tk desktop shell over the tested application core."""

    def __init__(self, root, initial_path: Path | None = None) -> None:
        import tkinter as tk
        from tkinter import ttk

        from ..app import EnhancerApplication

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.app = EnhancerApplication()
        self.song = None
        self.history = None
        self.suggestions = ChangeSet()
        self.current_path: Path | None = None
        self.performance_result = None
        self.optimizing = False

        root.title("Korg Pa800 MIDI Enhancer")
        root.geometry("1120x760")
        root.minsize(860, 580)
        self._build_menu()
        self._build_layout()
        self._set_loaded_state(False)
        if initial_path is not None:
            root.after(50, lambda: self.open_path(initial_path))

    def _build_menu(self) -> None:
        menu = self.tk.Menu(self.root)
        file_menu = self.tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Import MIDI...", command=self.open_dialog, accelerator="Ctrl+O")
        file_menu.add_command(label="Generate MIDI with CPU model...", command=self.generate_midi_dialog)
        file_menu.add_command(label="Export MIDI...", command=self.export_dialog, accelerator="Ctrl+E")
        file_menu.add_command(label="Save Project...", command=self.save_project_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = self.tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        menu.add_cascade(label="Edit", menu=edit_menu)

        analysis_menu = self.tk.Menu(menu, tearoff=False)
        analysis_menu.add_command(label="Refresh analysis", command=self.refresh)
        analysis_menu.add_command(label="Generate basic suggestions", command=self.generate_suggestions)
        analysis_menu.add_command(label="Optimize performance", command=self.optimize_performance)
        menu.add_cascade(label="Analysis", menu=analysis_menu)
        self.root.config(menu=menu)
        self.root.bind("<Control-o>", lambda _event: self.open_dialog())
        self.root.bind("<Control-e>", lambda _event: self.export_dialog())
        self.root.bind("<Control-z>", lambda _event: self.undo())
        self.root.bind("<Control-y>", lambda _event: self.redo())

    def generate_midi_dialog(self) -> None:
        from tkinter import filedialog, messagebox, simpledialog
        from ..generator import KEYS, ROLES, SCALES, STYLE_PRESETS, SongForm, arrange_harmonically, fit_song_form, generate_notes, write_generated_midi

        checkpoint = filedialog.askopenfilename(parent=self.root, title="Select PyTorch checkpoint", filetypes=(("PyTorch checkpoint", "*.pt"), ("All files", "*.*")))
        if not checkpoint:
            return
        output = filedialog.asksaveasfilename(parent=self.root, title="Generated MIDI", defaultextension=".mid", filetypes=(("MIDI", "*.mid"),))
        if not output:
            return
        count = simpledialog.askinteger("Generation length", "Notes per role:", initialvalue=256, minvalue=8, maxvalue=4096, parent=self.root)
        if count is None:
            return
        bars = simpledialog.askinteger("Song form", "Length in bars:", initialvalue=32, minvalue=4, maxvalue=256, parent=self.root)
        if bars is None:
            return
        style_name = simpledialog.askstring("Factory style", "Style (pop, ballad, dance, folk, rock):", initialvalue="pop", parent=self.root)
        if style_name is None:
            return
        style_name = style_name.strip().lower()
        if style_name not in STYLE_PRESETS:
            messagebox.showerror("Invalid style", "Use pop, ballad, dance, folk or rock.", parent=self.root)
            return
        key = simpledialog.askstring("Tonal center", "Key (C, C#, D ... B):", initialvalue="C", parent=self.root)
        if key is None:
            return
        key = key.strip().upper()
        scale = simpledialog.askstring("Scale", "Scale (major or minor):", initialvalue="major", parent=self.root)
        if scale is None:
            return
        scale = scale.strip().lower()
        if key not in KEYS or scale not in SCALES:
            messagebox.showerror("Invalid harmony", "Use a chromatic key C..B and major or minor scale.", parent=self.root)
            return
        try:
            generated = {}; config = None
            for index, role in enumerate(ROLES):
                raw, config = generate_notes(Path(checkpoint), role, count, seed=index)
                harmonic = arrange_harmonically(raw, role, key=key, scale=scale)
                generated[role] = fit_song_form(harmonic, role, SongForm(bars), style=STYLE_PRESETS[style_name])
            write_generated_midi(Path(output), generated, config, tempo=STYLE_PRESETS[style_name].tempo, bars=bars)
            song = self.app.import_midi(Path(output))
            blockers = [item.message for item in self.app.validate(song) if item.blocks_export]
            if blockers:
                raise ValueError("; ".join(blockers[:5]))
            self.open_path(Path(output))
            self.status.set(f"Generated {style_name} MIDI in {key} {scale}. Optimize is ready.")
        except Exception as error:
            messagebox.showerror("Generation failed", str(error), parent=self.root)

    def _build_layout(self) -> None:
        toolbar = self.ttk.Frame(self.root, padding=(10, 8))
        toolbar.pack(fill="x")
        self.open_button = self.ttk.Button(toolbar, text="1. Import", command=self.open_dialog)
        self.open_button.pack(side="left")
        self.optimize_button = self.ttk.Button(toolbar, text="2. Optimize", command=self.optimize_performance)
        self.optimize_button.pack(side="left", padx=(8, 0))
        self.analyze_button = self.ttk.Button(toolbar, text="Analyze", command=self.refresh)
        self.suggest_button = self.ttk.Button(
            toolbar, text="Optimization suggestions", command=self.generate_suggestions
        )
        self.undo_button = self.ttk.Button(toolbar, text="Undo", command=self.undo)
        self.undo_button.pack(side="left", padx=(24, 0))
        self.redo_button = self.ttk.Button(toolbar, text="Redo", command=self.redo)
        self.redo_button.pack(side="left", padx=(8, 0))
        self.export_button = self.ttk.Button(toolbar, text="3. Export", command=self.export_dialog)
        self.export_button.pack(side="right")

        self.notebook = self.ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.summary_text = self._text_tab("Summary")
        self.issues_tree = self._tree_tab(
            "Validation",
            ("severity", "code", "location", "message"),
            (90, 180, 130, 650),
        )
        self.rhythms_tree = self._tree_tab(
            "Rhythms", ("score", "profile", "reason"), (90, 220, 720)
        )
        self.performance_text = self._text_tab("Performance")
        suggestions_frame = self.ttk.Frame(self.notebook, padding=8)
        self.notebook.add(suggestions_frame, text="Suggestions")
        self.suggestions_tree = self.ttk.Treeview(
            suggestions_frame,
            columns=("risk", "module", "target", "change", "reason"),
            show="headings",
            selectmode="extended",
        )
        for name, width in zip(
            ("risk", "module", "target", "change", "reason"),
            (80, 150, 180, 220, 470),
        ):
            self.suggestions_tree.heading(name, text=name.title())
            self.suggestions_tree.column(name, width=width, anchor="w")
        suggestion_scroll = self.ttk.Scrollbar(
            suggestions_frame, orient="vertical", command=self.suggestions_tree.yview
        )
        self.suggestions_tree.configure(yscrollcommand=suggestion_scroll.set)
        self.suggestions_tree.pack(side="left", fill="both", expand=True)
        suggestion_scroll.pack(side="right", fill="y")

        action_bar = self.ttk.Frame(self.root, padding=(10, 0, 10, 8))
        action_bar.pack(fill="x")
        self.apply_button = self.ttk.Button(
            action_bar, text="Apply selected suggestions", command=self.apply_selected
        )
        self.apply_button.pack(side="right")
        self.status = self.tk.StringVar(value="Open a Standard MIDI File to begin.")
        self.ttk.Label(action_bar, textvariable=self.status).pack(side="left", fill="x", expand=True)

    def _text_tab(self, title: str):
        frame = self.ttk.Frame(self.notebook, padding=8)
        self.notebook.add(frame, text=title)
        text = self.tk.Text(frame, wrap="word", font=("Consolas", 10), state="disabled")
        scrollbar = self.ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return text

    def _tree_tab(self, title: str, columns, widths):
        frame = self.ttk.Frame(self.notebook, padding=8)
        self.notebook.add(frame, text=title)
        tree = self.ttk.Treeview(frame, columns=columns, show="headings")
        for name, width in zip(columns, widths):
            tree.heading(name, text=name.title())
            tree.column(name, width=width, anchor="w")
        scrollbar = self.ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree

    def _set_loaded_state(self, loaded: bool) -> None:
        state = "normal" if loaded else "disabled"
        for button in (
            self.analyze_button,
            self.optimize_button,
            self.suggest_button,
            self.export_button,
            self.apply_button,
        ):
            button.configure(state=state)
        self._update_history_buttons()

    def optimize_performance(self) -> None:
        import threading
        from tkinter import messagebox

        from ..reference_learning import load_reference_catalog
        from ..strategy import DEFAULT_PERFORMANCE_STRATEGY

        if self.song is None or self.optimizing:
            return
        factory_catalog=Path("data/factory-pattern-catalog.json")
        if factory_catalog.exists():
            self._optimize_conservative(factory_catalog)
            return
        catalog_path = Path(DEFAULT_PERFORMANCE_STRATEGY.reference_catalog)
        try:
            catalog = load_reference_catalog(catalog_path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Optimization unavailable", str(error), parent=self.root)
            return
        self.optimizing = True
        self._set_loaded_state(False)
        self.open_button.configure(state="disabled")
        self.status.set("Optimizing velocity, articulations and validation in background...")
        source_song = self.song

        def worker() -> None:
            try:
                result = self.app.run_performance_pipeline(source_song, catalog)
                fingerprint, dna = self.app.plan_dna_optimization(result.projected_song)
                dna_projected = result.projected_song
                if dna.changes.changes:
                    dna.changes.approve_all()
                    from ..optimize.engine import ChangeEngine
                    dna_projected = ChangeEngine().apply(dna_projected, dna.changes)
                dna_blockers = tuple(
                    issue.message for issue in self.app.validate(dna_projected)
                    if issue.blocks_export
                )
            except Exception as error:
                self.root.after(0, lambda error=error: self._finish_performance_error(error))
                return
            package = (result, fingerprint, dna, dna_blockers)
            self.root.after(0, lambda package=package: self._finish_performance(package))

        threading.Thread(target=worker, name="pa800-performance", daemon=True).start()

    def _optimize_conservative(self, factory_catalog: Path) -> None:
        import threading
        self.optimizing=True; self._set_loaded_state(False); self.open_button.configure(state="disabled")
        self.status.set("Preserving tracks and mapping GM sounds to Pa800 Factory sounds...")
        source_song=self.song
        def worker():
            try:
                from ..retrieval import load_factory_catalog
                result=self.app.optimize_conservatively(source_song,load_factory_catalog(factory_catalog))
                blockers=[item.message for item in self.app.validate(result.song) if item.blocks_export]
                if blockers: raise ValueError("conservative optimization blocked: "+"; ".join(blockers[:5]))
            except Exception as error:
                self.root.after(0,lambda error=error:self._finish_performance_error(error)); return
            self.root.after(0,lambda result=result:self._finish_conservative(result))
        threading.Thread(target=worker,name="pa800-conservative",daemon=True).start()

    def _finish_conservative(self, result) -> None:
        from tkinter import messagebox
        self.optimizing=False; self.open_button.configure(state="normal"); self._set_loaded_state(True)
        lines=["Conservative Pa800 optimization","",f"Preserved tracks: {result.preserved_tracks}",f"Preserved notes: {result.preserved_notes}",f"Mapped channels: {len(result.mappings)}",f"Skipped channels: {', '.join(map(str,result.skipped_channels)) or '-'}","","Factory sound evidence:"]
        lines.extend(f"  Ch {m.channel}: {m.role}  {m.bank_msb}/{m.bank_lsb}/{m.program}  evidence notes={m.evidence_notes}" for m in result.mappings)
        self._replace_text(self.performance_text,"\n".join(lines)); self.notebook.select(self.performance_text.master)
        if not messagebox.askyesno("Apply safe Pa800 optimization",f"Keep all {result.preserved_tracks} tracks and {result.preserved_notes} notes, and apply {len(result.mappings)} Factory sound mappings?",parent=self.root):
            self.status.set("Safe optimization preview completed; result was not applied."); return
        self.song=result.song; self.history=self.app.create_command_history(self.song); self.performance_result=result
        self.refresh(); self.status.set("Original tracks preserved; Pa800 Factory sounds applied. Export is ready.")

    def _optimize_factory(self, factory_source: Path) -> None:
        import threading
        from tkinter import messagebox

        style=None
        self.optimizing=True; self._set_loaded_state(False); self.open_button.configure(state="disabled")
        self.status.set("Factory arranging, Gold dynamics and output mastering...")
        source_song=self.song

        def worker():
            try:
                from ..analysis.harmony import analyze_harmony
                from ..analysis.structure import analyze_structure
                from ..arranging import FactorySourceRepository, arrange_song_plan, materialize_arrangement, transfer_gold_performance
                from ..evaluation import evaluate_arrangement
                from ..planning import FactorySongPlanner, map_section_energy
                from ..reference_learning import load_reference_catalog
                from ..retrieval import FactoryIndex, derive_factory_query, load_factory_catalog
                energy=map_section_energy(analyze_structure(source_song)); harmony=analyze_harmony(source_song,temporal_decode=True)
                grooves=FactoryIndex.load(Path("data/factory-variation-groove-analysis.json")); patterns=load_factory_catalog(Path("data/factory-pattern-catalog.json"))
                plan=FactorySongPlanner(grooves,patterns).plan(energy,derive_factory_query(source_song,style=style))
                preview=arrange_song_plan(plan,energy,harmony,FactorySourceRepository(factory_source),target_ppq=source_song.header.ppq)
                transfer=transfer_gold_performance(preview.patterns,load_reference_catalog(Path("data/performance-reference-catalog-v2.json")),ppq=source_song.header.ppq)
                evaluation=evaluate_arrangement(transfer.patterns,harmony.chords,ppq=source_song.header.ppq)
                if evaluation.status=="blocked": raise ValueError("musical gate blocked arrangement: "+"; ".join(item.message for item in evaluation.issues[:5]))
                materialized=materialize_arrangement(transfer.patterns,source_song)
                blockers=[item.message for item in self.app.validate(materialized.song) if item.blocks_export]
                if blockers: raise ValueError("MIDI validation blocked arrangement: "+"; ".join(blockers[:5]))
                package=(plan,preview,transfer,evaluation,materialized)
            except Exception as error:
                self.root.after(0,lambda error=error:self._finish_performance_error(error)); return
            self.root.after(0,lambda package=package:self._finish_factory(package))
        threading.Thread(target=worker,name="pa800-factory-gold",daemon=True).start()

    def _finish_factory(self, package) -> None:
        from tkinter import messagebox
        plan,preview,transfer,evaluation,materialized=package
        self.optimizing=False; self.open_button.configure(state="normal"); self._set_loaded_state(True)
        lines=["Factory + Gold mastered preview","",f"Style: {plan.style} (automatic evidence ranking)",f"Style score: {plan.score:.3f}",f"Musical gate: {evaluation.status} ({evaluation.score:.3f})",f"Notes: {materialized.note_count}",f"Gold velocity changes: {transfer.changed_velocities}",f"Gold articulation changes: {transfer.changed_durations}",f"Matched instruments: {len(transfer.evidence)}",f"Unmatched instruments: {len(transfer.unmatched_addresses)}",f"Overlap repairs: {materialized.trimmed_overlaps}","","Mixer:"]
        lines.extend(f"  Ch {channel}: {role}  Volume {volume}  Expression {expression}" for channel,role,volume,expression in materialized.mixer_levels)
        self._replace_text(self.performance_text,"\n".join(lines)); self.notebook.select(self.performance_text.master)
        if not messagebox.askyesno("Apply Factory + Gold optimization",f"Apply {plan.style} arrangement and mastered mixer?",parent=self.root):
            self.status.set("Factory preview completed; result was not applied."); return
        self.song=materialized.song; self.history=self.app.create_command_history(self.song); self.performance_result=package
        self.refresh(); self.status.set(f"Applied {plan.style} Factory + Gold mastering. Export is ready.")

    def _finish_performance_error(self, error: Exception) -> None:
        from tkinter import messagebox

        self.optimizing = False
        self.open_button.configure(state="normal")
        self._set_loaded_state(self.song is not None)
        self.status.set(f"Optimization failed: {error}")
        messagebox.showerror("Optimization failed", str(error), parent=self.root)

    def _finish_performance(self, package) -> None:
        from tkinter import messagebox

        result, fingerprint, dna, dna_blockers = package

        self.optimizing = False
        self.open_button.configure(state="normal")
        self._set_loaded_state(True)
        self.performance_result = result
        unmatched = sorted(
            set(result.velocity.unmatched_addresses)
            | set(result.articulation.unmatched_addresses)
        )
        lines = [
            "Performance optimization preview",
            "",
            f"Safe repairs: {len(result.repairs.changes)}",
            f"Velocity changes: {len(result.velocity.changes.changes)}",
            f"Articulation changes: {len(result.articulation.changes.changes)}",
            f"Gold DNA changes: {len(dna.changes.changes)}",
            f"DNA roles: {', '.join(role.role for role in fingerprint.roles) or '-'}",
            f"Instrument segments: {len(result.velocity.segments)}",
            f"Unknown addresses: {len(unmatched)}",
            f"Export blockers: {len(dna_blockers)}",
        ]
        if dna.matches:
            lines.extend(("", "Gold evidence:"))
            lines.extend(
                f"  {item.role}: distance={item.distance:.4f}  {item.source_locator}"
                for item in dna.matches
            )
        if unmatched:
            lines.extend(("", "Unknown addresses:", *(f"  {item}" for item in unmatched[:50])))
        if dna_blockers:
            lines.extend(("", "Blockers:", *(f"  {item}" for item in dna_blockers[:50])))
        self._replace_text(self.performance_text, "\n".join(lines))
        self.notebook.select(self.performance_text.master)
        if dna_blockers:
            self.status.set(f"Optimization preview blocked by {len(dna_blockers)} validation findings.")
            messagebox.showwarning(
                "Optimization blocked",
                "Preview completed, but blocking validation findings remain. No changes were applied.",
                parent=self.root,
            )
            return
        total = len(result.repairs.changes) + len(result.velocity.changes.changes) + len(result.articulation.changes.changes) + len(dna.changes.changes)
        if not messagebox.askyesno(
            "Apply performance optimization",
            f"Apply {total} validated changes? They remain available through Undo.",
            parent=self.root,
        ):
            self.status.set("Optimization preview completed; changes were not applied.")
            return
        try:
            for changes in (result.repairs, result.velocity.changes, result.articulation.changes, dna.changes):
                if changes.changes:
                    self.song = self.history.apply(changes.to_transaction())
        except ValueError as error:
            messagebox.showerror("Cannot apply optimization", str(error), parent=self.root)
            self.status.set(f"Apply failed: {error}")
            return
        self.refresh()
        self.status.set(f"Applied {total} performance changes. Export is ready.")

    def _update_history_buttons(self) -> None:
        self.undo_button.configure(
            state="normal" if self.history is not None and self.history.can_undo else "disabled"
        )
        self.redo_button.configure(
            state="normal" if self.history is not None and self.history.can_redo else "disabled"
        )

    def open_dialog(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askopenfilename(
            title="Open MIDI file",
            filetypes=(("MIDI files", "*.mid *.midi"), ("All files", "*.*")),
        )
        if selected:
            self.open_path(parse_user_path(selected))

    def open_path(self, path: Path | str) -> None:
        from tkinter import messagebox

        source = parse_user_path(path) if isinstance(path, str) else path
        try:
            song = self.app.import_midi(source)
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot open MIDI", str(error), parent=self.root)
            self.status.set(f"Open failed: {error}")
            return
        self.song = song
        self.history = self.app.create_command_history(song)
        self.current_path = source
        self.suggestions = ChangeSet()
        self._clear_tree(self.suggestions_tree)
        self._set_loaded_state(True)
        self.refresh()
        self.root.title(f"Korg Pa800 MIDI Enhancer — {source.name}")

    def refresh(self) -> None:
        from tkinter import messagebox

        if self.song is None:
            return
        try:
            summary = self.app.summarize(self.song)
            issues = self.app.validate(self.song)
            rhythms = self.app.detect_rhythms(self.song)[:20]
        except (OSError, ValueError) as error:
            messagebox.showerror("Analysis failed", str(error), parent=self.root)
            return
        source = self.current_path or self.song.source_path or "<memory>"
        summary_lines = [
            f"Source: {source}",
            f"SHA-256: {self.song.source_sha256 or '-'}",
            "",
            f"SMF format: {summary.format_type}",
            f"Tracks: {summary.track_count}",
            f"Events: {summary.event_count}",
            f"PPQ: {summary.ppq or 'SMPTE'}",
            f"Duration: {summary.duration_seconds:.3f} seconds",
            f"End tick: {summary.end_tick}",
            f"Channels: {', '.join(map(str, summary.channels)) or '-'}",
            f"Notes: {summary.note_count}",
            f"Unpaired notes: {summary.unmatched_notes}",
            f"Sustained notes: {summary.sustained_notes}",
            f"Maximum polyphony: {summary.maximum_polyphony}",
            f"Controller events: {summary.controller_events}",
            f"Tempo events: {summary.tempo_events}",
            f"Meter events: {summary.meter_events}",
            f"SysEx events: {summary.sysex_events}",
            f"NRPN/RPN changes: {summary.parameter_changes}",
        ]
        self._replace_text(self.summary_text, "\n".join(summary_lines))
        self._clear_tree(self.issues_tree)
        for issue in issues:
            location = (
                f"track {issue.track_index}, tick {issue.tick}"
                if issue.track_index is not None
                else "song"
            )
            self.issues_tree.insert(
                "", "end", values=(issue.severity.value, issue.code, location, issue.message)
            )
        self._clear_tree(self.rhythms_tree)
        for rhythm in rhythms:
            self.rhythms_tree.insert(
                "", "end", values=(f"{rhythm.score:.2f}", rhythm.profile_id, rhythm.reason)
            )
        blocking = sum(1 for issue in issues if issue.blocks_export)
        self.status.set(
            f"Loaded {Path(str(source)).name}: {summary.track_count} tracks, "
            f"{summary.note_count} notes, {len(issues)} validation findings, "
            f"{blocking} export blockers."
        )
        self._update_history_buttons()

    def generate_suggestions(self) -> None:
        from tkinter import messagebox

        if self.song is None:
            return
        try:
            self.suggestions = self.app.suggest_basic_optimization(self.song)
        except ValueError as error:
            messagebox.showerror("Optimization analysis failed", str(error), parent=self.root)
            return
        self._clear_tree(self.suggestions_tree)
        for index, change in enumerate(self.suggestions.changes):
            target = f"{change.event_id}.{change.field}"
            delta = f"{change.old_value} → {change.new_value}"
            self.suggestions_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(change.risk.name.lower(), change.module, target, delta, change.reason),
            )
        self.notebook.select(self.suggestions_tree.master)
        self.status.set(
            f"Generated {len(self.suggestions.changes)} suggestions. "
            "Select rows and review them before applying."
        )

    def apply_selected(self) -> None:
        from tkinter import messagebox

        if self.song is None or self.history is None:
            return
        selected = tuple(int(item) for item in self.suggestions_tree.selection())
        try:
            transaction = build_selected_transaction(self.suggestions, selected)
        except (ValueError, IndexError) as error:
            messagebox.showwarning("No suggestions selected", str(error), parent=self.root)
            return
        affected = len(transaction.changes)
        if not messagebox.askyesno(
            "Apply optimization",
            f"Apply {affected} reviewed event changes as one undoable transaction?",
            parent=self.root,
        ):
            return
        try:
            self.song = self.history.apply(transaction)
        except ValueError as error:
            messagebox.showerror("Cannot apply optimization", str(error), parent=self.root)
            return
        self.suggestions = ChangeSet()
        self._clear_tree(self.suggestions_tree)
        self.refresh()
        self.status.set(f"Applied {affected} changes. Undo is available.")

    def undo(self) -> None:
        if self.history is None or not self.history.can_undo:
            return
        self.song = self.history.undo()
        self.refresh()
        self.status.set("Last transaction was undone.")

    def redo(self) -> None:
        if self.history is None or not self.history.can_redo:
            return
        self.song = self.history.redo()
        self.refresh()
        self.status.set("Transaction was reapplied.")

    def export_dialog(self) -> None:
        from tkinter import filedialog, messagebox

        if self.song is None:
            return
        initial = (
            f"{self.current_path.stem}-pa800.mid" if self.current_path else "song-pa800.mid"
        )
        selected = filedialog.asksaveasfilename(
            title="Export optimized MIDI",
            defaultextension=".mid",
            initialfile=initial,
            filetypes=(("MIDI files", "*.mid"), ("All files", "*.*")),
        )
        if not selected:
            return
        output = parse_user_path(selected)
        try:
            self.app.export_midi(self.song, output)
        except (OSError, ValueError) as error:
            messagebox.showerror("Export failed", str(error), parent=self.root)
            self.status.set(f"Export failed: {error}")
            return
        messagebox.showinfo("Export complete", f"Saved:\n{output}", parent=self.root)
        self.status.set(f"Exported {output}")

    def save_project_dialog(self) -> None:
        from tkinter import filedialog, messagebox

        if self.song is None:
            return
        selected = filedialog.asksaveasfilename(
            title="Save project",
            defaultextension=".json",
            initialfile="song.pa800-project.json",
            filetypes=(("Pa800 project", "*.json"), ("All files", "*.*")),
        )
        if not selected:
            return
        output = parse_user_path(selected)
        try:
            project = self.app.create_project(self.song, self.history)
            self.app.save_project(project, output)
        except (OSError, ValueError) as error:
            messagebox.showerror("Project save failed", str(error), parent=self.root)
            return
        self.status.set(f"Saved project {output}")

    @staticmethod
    def _clear_tree(tree) -> None:
        children = tree.get_children()
        if children:
            tree.delete(*children)

    @staticmethod
    def _replace_text(widget, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")


def launch_ui(midi_path: Path | str | None = None) -> None:
    """Launch the graphical desktop application."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError as error:
        raise RuntimeError(
            "Tk graphical support is not installed in this Python runtime. "
            "Install the official Windows Python build with Tcl/Tk support."
        ) from error

    initial = None
    if midi_path is not None:
        initial = parse_user_path(str(midi_path))
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise RuntimeError(f"cannot start graphical interface: {error}") from error
    try:
        EnhancerGui(root, initial)
        root.mainloop()
    except Exception as error:
        messagebox.showerror("Korg Pa800 MIDI Enhancer", str(error), parent=root)
        root.destroy()
        raise
