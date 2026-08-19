#!/usr/bin/env python3
"""Modern Tk desktop interface for the Python MIDI Enhancer analyzer."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from gui_change_workflow import GuiChangeWorkflow, GuiWorkflowError
from midi_enhancer import MidiAnalyzer, MidiError, apply_library_integrations, note_name


COLORS = {
    "window": "#0B1020",
    "panel": "#11182A",
    "card": "#182236",
    "card_hover": "#1E2B43",
    "border": "#2A3852",
    "text": "#F4F7FB",
    "muted": "#8FA0B8",
    "accent": "#6C7CFF",
    "accent_2": "#35D0BA",
    "warning": "#FFB454",
}


class TrackCard(tk.Frame):
    def __init__(self, parent: tk.Misc, slot: int, command):
        super().__init__(
            parent, bg=COLORS["card"], highlightthickness=1,
            highlightbackground=COLORS["border"], cursor="hand2",
        )
        self.slot = slot
        self.command = command
        self.data: dict | None = None
        self.grid_propagate(False)

        self.number = tk.Label(
            self, text=f"TRACK {slot:02d}", bg=COLORS["card"], fg=COLORS["muted"],
            font=("TkDefaultFont", 9, "bold"), anchor="w",
        )
        self.number.place(x=14, y=10)

        self.icon = tk.Label(
            self, text="·", bg=COLORS["card"], fg=COLORS["accent_2"],
            font=("TkDefaultFont", 27), width=2,
        )
        self.icon.place(x=10, y=35)

        self.instrument = tk.Label(
            self, text="Empty", bg=COLORS["card"], fg=COLORS["text"],
            font=("TkDefaultFont", 11, "bold"), anchor="w",
        )
        self.instrument.place(x=67, y=37, relwidth=0.69)

        self.track_name = tk.Label(
            self, text="No MIDI data", bg=COLORS["card"], fg=COLORS["muted"],
            font=("TkDefaultFont", 9), anchor="w",
        )
        self.track_name.place(x=67, y=61, relwidth=0.69)

        self.stats = tk.Label(
            self, text="0 notes  ·  poly 0", bg=COLORS["card"], fg=COLORS["muted"],
            font=("TkDefaultFont", 9), anchor="w",
        )
        self.stats.place(x=14, y=92, relwidth=0.86)

        self.confidence = ttk.Progressbar(
            self, orient="horizontal", mode="determinate", maximum=100,
            style="Confidence.Horizontal.TProgressbar",
        )
        self.confidence.place(x=14, y=119, relwidth=0.86, height=5)

        self.confidence_text = tk.Label(
            self, text="confidence 0%", bg=COLORS["card"], fg=COLORS["muted"],
            font=("TkDefaultFont", 8), anchor="w",
        )
        self.confidence_text.place(x=14, y=129)

        self._bind_tree(self)

    def _bind_tree(self, widget: tk.Misc) -> None:
        widget.bind("<Button-1>", lambda _event: self.command(self.slot))
        widget.bind("<Enter>", lambda _event: self._set_background(COLORS["card_hover"]))
        widget.bind("<Leave>", lambda _event: self._set_background(COLORS["card"]))
        for child in widget.winfo_children():
            self._bind_tree(child)

    def _set_background(self, color: str) -> None:
        self.configure(bg=color)
        for widget in (self.number, self.icon, self.instrument, self.track_name, self.stats, self.confidence_text):
            widget.configure(bg=color)

    def update_data(self, data: dict) -> None:
        self.data = data
        source = data["source"]
        if data.get("physical_track") is None:
            source = "Unused slot"
        self.number.configure(text=f"TRACK {self.slot:02d}  ·  {source.upper()}")
        self.icon.configure(text=data["icon"])
        self.instrument.configure(text=data["instrument"])
        self.track_name.configure(text=data["title"])
        self.stats.configure(text=f"{data['role']}  ·  {data['notes']} notes")
        self.confidence["value"] = data["role_confidence"]
        self.confidence_text.configure(
            text=f"instrument {data['confidence']}%  ·  role {data['role_confidence']}%"
        )


class FactoryReplacementDialog:
    """Bounded K03 GUI: preview -> USER approve -> verify -> save/rollback."""

    def __init__(self, app: "MidiEnhancerApp", workflow: GuiChangeWorkflow):
        self.app = app
        self.workflow = workflow
        self.window = tk.Toplevel(app.root)
        self.window.title("Factory Sound Replacement — bounded workflow")
        self.window.geometry("900x690")
        self.window.minsize(760, 600)
        self.window.configure(bg=COLORS["window"])
        self.window.transient(app.root)

        self.segment_by_label = {item.label: item for item in workflow.segment_options}
        self.target_by_label = {}
        self.segment_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select a segment and Factory target, then Preview.")

        tk.Label(
            self.window,
            text="USER-SELECTED FACTORY SOUND REPLACEMENT",
            bg=COLORS["window"], fg=COLORS["text"],
            font=("TkDefaultFont", 14, "bold"),
        ).pack(anchor="w", padx=22, pady=(18, 4))
        tk.Label(
            self.window,
            text=(
                "No automatic replacement. Preview shows every permitted MIDI byte field. "
                "Save is enabled only after USER approval and Verifier PASS."
            ),
            bg=COLORS["window"], fg=COLORS["muted"], wraplength=840,
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 14))

        form = tk.Frame(self.window, bg=COLORS["panel"])
        form.pack(fill="x", padx=22, pady=4)
        tk.Label(form, text="M10 / K02 segment", bg=COLORS["panel"], fg=COLORS["muted"]).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        self.segment_combo = ttk.Combobox(
            form, textvariable=self.segment_var, state="readonly",
            values=tuple(self.segment_by_label),
        )
        self.segment_combo.pack(fill="x", padx=12, pady=(0, 10))
        self.segment_combo.bind("<<ComboboxSelected>>", self._segment_selected)

        tk.Label(form, text="User-selected K01 Factory target", bg=COLORS["panel"], fg=COLORS["muted"]).pack(
            anchor="w", padx=12, pady=(0, 2)
        )
        self.target_combo = ttk.Combobox(
            form, textvariable=self.target_var, state="readonly", values=()
        )
        self.target_combo.pack(fill="x", padx=12, pady=(0, 12))

        if self.segment_by_label:
            first = next(iter(self.segment_by_label))
            self.segment_var.set(first)
            self._load_targets(self.segment_by_label[first].ordinal)

        self.preview_text = ScrolledText(
            self.window, height=17, wrap="word", bg=COLORS["card"],
            fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat",
            font=("TkFixedFont", 10),
        )
        self.preview_text.pack(fill="both", expand=True, padx=22, pady=12)
        self.preview_text.insert("1.0", "No preview yet.\n")
        self.preview_text.configure(state="disabled")

        tk.Label(
            self.window, textvariable=self.status_var, bg=COLORS["window"],
            fg=COLORS["accent_2"], anchor="w", justify="left", wraplength=840,
        ).pack(fill="x", padx=22, pady=(0, 8))

        buttons = tk.Frame(self.window, bg=COLORS["window"])
        buttons.pack(fill="x", padx=22, pady=(0, 18))
        self.preview_button = tk.Button(
            buttons, text="1. Preview exact diff", command=self.preview_change,
            bg=COLORS["panel"], fg=COLORS["text"], relief="flat", padx=12, pady=8,
        )
        self.preview_button.pack(side="left", padx=(0, 8))
        self.approve_button = tk.Button(
            buttons, text="2. USER Approve + Verify", command=self.approve_and_verify,
            state="disabled", bg=COLORS["accent"], fg="white", relief="flat", padx=12, pady=8,
        )
        self.approve_button.pack(side="left", padx=4)
        self.save_button = tk.Button(
            buttons, text="3. Save new MIDI", command=self.save_verified,
            state="disabled", bg=COLORS["accent_2"], fg="#07100E", relief="flat", padx=12, pady=8,
        )
        self.save_button.pack(side="left", padx=4)
        self.rollback_button = tk.Button(
            buttons, text="Rollback saved output", command=self.rollback_saved,
            state="disabled", bg=COLORS["warning"], fg="#201000", relief="flat", padx=12, pady=8,
        )
        self.rollback_button.pack(side="left", padx=4)
        tk.Button(
            buttons, text="Close", command=self.window.destroy,
            bg=COLORS["panel"], fg=COLORS["muted"], relief="flat", padx=12, pady=8,
        ).pack(side="right")

    def _segment_selected(self, _event=None) -> None:
        item = self.segment_by_label.get(self.segment_var.get())
        if item is None:
            return
        self._load_targets(item.ordinal)
        self._reset_after_selection()

    def _load_targets(self, ordinal: int) -> None:
        targets = self.workflow.target_options(ordinal)
        self.target_by_label = {item.label: item for item in targets}
        self.target_combo.configure(values=tuple(self.target_by_label))
        self.target_var.set("")

    def _reset_after_selection(self) -> None:
        self.approve_button.configure(state="disabled")
        self.save_button.configure(state="disabled")
        self.rollback_button.configure(state="disabled")
        self.status_var.set("Selection changed. Create a new preview.")

    def preview_change(self) -> None:
        segment = self.segment_by_label.get(self.segment_var.get())
        target = self.target_by_label.get(self.target_var.get())
        if segment is None or target is None:
            messagebox.showwarning(
                "Selection required", "Select both an eligible segment and a Factory target.",
                parent=self.window,
            )
            return
        try:
            preview = self.workflow.create_preview(
                segment_ordinal=segment.ordinal,
                target_address=target.address,
                user_selected=True,
            )
        except GuiWorkflowError as error:
            messagebox.showerror("Preview blocked", str(error), parent=self.window)
            self.status_var.set(f"BLOCKED: {error}")
            return
        lines = [
            f"SOURCE: {preview.segment.requested_address} — {preview.segment.official_name or 'UNKNOWN'}",
            f"TARGET: {preview.target.address} — {preview.target.name}",
            f"SEGMENT: {preview.segment.ordinal}, channel {preview.segment.channel}, "
            f"ticks {preview.segment.start_tick}-{preview.segment.end_tick}",
            f"RISK: {preview.risk}",
            f"PLAN: {preview.plan.plan_id}",
            "",
            "EXACT ALLOWED DIFFERENCES:",
            *[f"  • {line}" for line in preview.mutation_lines],
            "",
            "PROTECTIONS:",
            *[f"  • {item}" for item in preview.plan.proposals[0].protections],
            "",
            "apply_authorized = false until separate USER approval and execution request",
        ]
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", "\n".join(lines))
        self.preview_text.configure(state="disabled")
        self.approve_button.configure(state="normal")
        self.save_button.configure(state="disabled")
        self.rollback_button.configure(state="disabled")
        self.status_var.set("Preview READY. Review exact diff before USER approval.")

    def approve_and_verify(self) -> None:
        if self.workflow.preview is None:
            return
        accepted = messagebox.askyesno(
            "Explicit USER approval",
            "Approve exactly the displayed event-field changes and run the independent Verifier?",
            parent=self.window,
        )
        if not accepted:
            self.status_var.set("USER did not approve. No MIDI bytes changed.")
            return
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            verification = self.workflow.approve_and_verify(
                decision_time=now,
                execution_time=now,
                user_confirmed=True,
            )
        except GuiWorkflowError as error:
            messagebox.showerror("Verification failed", str(error), parent=self.window)
            self.status_var.set(f"Verifier FAIL: {error}")
            return
        self.save_button.configure(state="normal")
        self.approve_button.configure(state="disabled")
        self.status_var.set(
            f"Verifier {verification.status.value}: {verification.actual_changed_byte_count} "
            "approved byte differences. Save may create a NEW file only."
        )

    def save_verified(self) -> None:
        initial = f"{self.workflow.source_path.stem}_enhanced.mid"
        selected = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save verified MIDI as a new file",
            initialdir=str(self.workflow.source_path.parent),
            initialfile=initial,
            defaultextension=".mid",
            filetypes=(("MIDI files", "*.mid *.midi"),),
        )
        if not selected:
            return
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            result = self.workflow.save(output_midi_path=selected, saved_at=now)
        except GuiWorkflowError as error:
            messagebox.showerror("Save blocked", str(error), parent=self.window)
            self.status_var.set(f"SAVE BLOCKED: {error}")
            return
        self.save_button.configure(state="disabled")
        self.rollback_button.configure(state="normal")
        self.status_var.set(
            f"SAVED new MIDI: {result.output_midi_path}\nJSON: {result.output_report_path}"
        )
        messagebox.showinfo(
            "Verified save complete",
            f"New MIDI and JSON report were saved.\n\n{result.output_midi_path}",
            parent=self.window,
        )

    def rollback_saved(self) -> None:
        accepted = messagebox.askyesno(
            "Rollback saved output",
            "Delete the saved MIDI and JSON only if their hashes still match?",
            parent=self.window,
        )
        if not accepted:
            return
        try:
            result = self.workflow.rollback_saved(user_confirmed=True)
        except GuiWorkflowError as error:
            messagebox.showerror("Rollback blocked", str(error), parent=self.window)
            return
        self.rollback_button.configure(state="disabled")
        self.status_var.set(f"Rollback {result.status.value}. Original MIDI was never overwritten.")


class MidiEnhancerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.result: dict | None = None
        self.path: Path | None = None
        self.workflow: GuiChangeWorkflow | None = None
        self.replacement_dialog: FactoryReplacementDialog | None = None
        self.cards: list[TrackCard] = []

        root.title("Prism MIDI Enhancer")
        root.geometry("1360x900")
        root.minsize(1080, 720)
        root.configure(bg=COLORS["window"])

        self._configure_styles()
        self._build_header()
        self._build_body()
        self._build_empty_tracks()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Confidence.Horizontal.TProgressbar",
            troughcolor=COLORS["border"], background=COLORS["accent_2"], borderwidth=0,
        )

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=COLORS["window"], height=88)
        header.pack(fill="x", padx=28, pady=(18, 8))
        header.pack_propagate(False)

        tk.Label(
            header, text="MIDI ENHANCER", bg=COLORS["window"], fg=COLORS["text"],
            font=("TkDefaultFont", 19, "bold"),
        ).pack(side="left", anchor="n", pady=9)
        tk.Label(
            header, text="ANALYZE  /  IDENTIFY  /  EXPLAIN", bg=COLORS["window"],
            fg=COLORS["accent_2"], font=("TkDefaultFont", 9, "bold"),
        ).place(x=2, y=48)

        self.import_button = tk.Button(
            header, text="＋  Import MIDI", command=self.import_midi,
            bg=COLORS["accent"], fg="white", activebackground="#7B89FF",
            activeforeground="white", relief="flat", bd=0, padx=22, pady=12,
            font=("TkDefaultFont", 10, "bold"), cursor="hand2",
        )
        self.import_button.pack(side="right", pady=11)

        self.factory_button = tk.Button(
            header, text="Factory Sound…", command=self.open_factory_replacement,
            state="disabled", bg=COLORS["panel"], fg=COLORS["muted"],
            activebackground=COLORS["card"], activeforeground=COLORS["text"],
            relief="flat", bd=0, padx=18, pady=12,
            font=("TkDefaultFont", 10), cursor="hand2",
        )
        self.factory_button.pack(side="right", padx=(10, 0), pady=11)

        self.export_button = tk.Button(
            header, text="Export JSON", command=self.export_json, state="disabled",
            bg=COLORS["panel"], fg=COLORS["muted"], activebackground=COLORS["card"],
            activeforeground=COLORS["text"], relief="flat", bd=0, padx=18, pady=12,
            font=("TkDefaultFont", 10), cursor="hand2",
        )
        self.export_button.pack(side="right", padx=10, pady=11)

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=COLORS["window"])
        body.pack(fill="both", expand=True, padx=28, pady=(0, 24))

        sidebar = tk.Frame(body, bg=COLORS["panel"], width=250)
        sidebar.pack(side="left", fill="y", padx=(0, 16))
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar, text="PROJECT OVERVIEW", bg=COLORS["panel"], fg=COLORS["muted"],
            font=("TkDefaultFont", 9, "bold"), anchor="w",
        ).pack(fill="x", padx=20, pady=(22, 15))

        self.summary_vars = {}
        for key, label in (
            ("format", "MIDI FORMAT"), ("tracks", "SOURCE TRACKS"),
            ("duration", "DURATION"), ("tempo", "INITIAL TEMPO"),
            ("notes", "TOTAL NOTES"), ("status", "ANALYSIS STATUS"),
        ):
            frame = tk.Frame(sidebar, bg=COLORS["card"], height=65)
            frame.pack(fill="x", padx=14, pady=4)
            frame.pack_propagate(False)
            tk.Label(
                frame, text=label, bg=COLORS["card"], fg=COLORS["muted"],
                font=("TkDefaultFont", 8, "bold"), anchor="w",
            ).pack(fill="x", padx=12, pady=(9, 0))
            variable = tk.StringVar(value="—")
            self.summary_vars[key] = variable
            tk.Label(
                frame, textvariable=variable, bg=COLORS["card"], fg=COLORS["text"],
                font=("TkDefaultFont", 11, "bold"), anchor="w",
            ).pack(fill="x", padx=12, pady=(2, 8))

        self.path_label = tk.Label(
            sidebar, text="Import a .mid or .midi file", wraplength=205,
            bg=COLORS["panel"], fg=COLORS["muted"], justify="left",
            font=("TkDefaultFont", 9), anchor="w",
        )
        self.path_label.pack(fill="x", padx=20, pady=20)

        content = tk.Frame(body, bg=COLORS["window"])
        content.pack(side="left", fill="both", expand=True)

        title_row = tk.Frame(content, bg=COLORS["window"], height=35)
        title_row.pack(fill="x")
        tk.Label(
            title_row, text="TRACK MAP  ·  16 SLOTS", bg=COLORS["window"],
            fg=COLORS["muted"], font=("TkDefaultFont", 9, "bold"),
        ).pack(side="left")
        self.mapping_label = tk.Label(
            title_row, text="Format-aware mapping", bg=COLORS["window"],
            fg=COLORS["accent_2"], font=("TkDefaultFont", 9),
        )
        self.mapping_label.pack(side="right")

        self.grid = tk.Frame(content, bg=COLORS["window"])
        self.grid.pack(fill="both", expand=True)
        for column in range(4):
            self.grid.columnconfigure(column, weight=1, uniform="tracks")
        for row in range(4):
            self.grid.rowconfigure(row, weight=1, uniform="tracks")

        details = tk.Frame(
            content, bg=COLORS["panel"], height=100,
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        details.pack(fill="x", pady=(12, 0))
        details.pack_propagate(False)
        tk.Label(
            details, text="SELECTED TRACK", bg=COLORS["panel"], fg=COLORS["muted"],
            font=("TkDefaultFont", 8, "bold"),
        ).pack(anchor="w", padx=16, pady=(11, 3))
        self.detail_label = tk.Label(
            details, text="Select a track card to see how the conclusion was reached.",
            bg=COLORS["panel"], fg=COLORS["text"], font=("TkDefaultFont", 9),
            justify="left", anchor="nw", wraplength=900,
        )
        self.detail_label.pack(fill="both", expand=True, padx=16, pady=(0, 10))

    def _build_empty_tracks(self) -> None:
        for slot in range(1, 17):
            card = TrackCard(self.grid, slot, self.select_track)
            row, column = divmod(slot - 1, 4)
            card.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)
            self.cards.append(card)

    def import_midi(self) -> None:
        filename = filedialog.askopenfilename(
            title="Import MIDI file",
            filetypes=(("MIDI files", "*.mid *.midi"), ("All files", "*.*")),
        )
        if not filename:
            return
        if self.replacement_dialog is not None and self.replacement_dialog.window.winfo_exists():
            self.replacement_dialog.window.destroy()
        self.workflow = None
        self.factory_button.configure(state="disabled", fg=COLORS["muted"])
        self.import_button.configure(state="disabled", text="Analyzing…")
        self.summary_vars["status"].set("WORKING")
        threading.Thread(target=self._analyze_worker, args=(Path(filename),), daemon=True).start()

    def _analyze_worker(self, path: Path) -> None:
        try:
            analyzer = MidiAnalyzer(path)
            analyzer.load()
            result = analyzer.analysis()
            apply_library_integrations(path, result)
        except (OSError, MidiError, ValueError) as error:
            message = str(error)
            self.root.after(0, lambda message=message: self._show_error(message))
            return
        workflow = None
        try:
            workflow = GuiChangeWorkflow(path)
        except Exception as error:  # Analyze remains available if bounded K03 is ineligible.
            result["warnings"].append(f"Factory replacement workflow unavailable: {error}")
        self.root.after(
            0,
            lambda path=path, result=result, workflow=workflow: self._show_result(
                path, result, workflow
            ),
        )

    def _show_error(self, error: str) -> None:
        self.import_button.configure(state="normal", text="＋  Import MIDI")
        self.summary_vars["status"].set("ERROR")
        messagebox.showerror("MIDI import failed", error)

    def _show_result(
        self,
        path: Path,
        result: dict,
        workflow: GuiChangeWorkflow | None = None,
    ) -> None:
        self.path = path
        self.result = result
        self.workflow = workflow
        self.import_button.configure(state="normal", text="＋  Import MIDI")
        self.export_button.configure(state="normal", fg=COLORS["text"])
        if workflow is not None and workflow.segment_options:
            self.factory_button.configure(state="normal", fg=COLORS["text"])
        else:
            self.factory_button.configure(state="disabled", fg=COLORS["muted"])
        self.path_label.configure(text=str(path))
        duration = result["duration_seconds"]
        minutes, seconds = divmod(duration or 0, 60)
        self.summary_vars["format"].set(f"FORMAT {result['format']}")
        self.summary_vars["tracks"].set(str(result["tracks"]))
        if result["format"] == 2:
            self.summary_vars["duration"].set("PER SEQUENCE")
            self.summary_vars["tempo"].set("PER SEQUENCE")
            self.summary_vars["status"].set("PARTIAL / READ-ONLY")
            mapping = "Format 2 → independent sequences kept separate"
        else:
            self.summary_vars["duration"].set(f"{int(minutes):02d}:{seconds:05.2f}")
            self.summary_vars["tempo"].set(f"{result['initial_bpm']} BPM")
            self.summary_vars["status"].set(
                "READY" if not result["warnings"] else "CHECK WARNINGS"
            )
            mapping = (
                "Format 0 → channels mapped to slots" if result["format"] == 0
                else "Format 1 → physical tracks mapped to slots"
            )
        self.summary_vars["notes"].set(str(result["notes"]))
        self.mapping_label.configure(text=mapping)
        for card, data in zip(self.cards, result["display_tracks"]):
            card.update_data(data)
        self.select_track(1)

    def open_factory_replacement(self) -> None:
        if self.workflow is None or not self.workflow.segment_options:
            messagebox.showwarning(
                "No eligible segment",
                "This MIDI has no bounded K02 segment eligible for Factory replacement.",
                parent=self.root,
            )
            return
        if self.replacement_dialog is not None and self.replacement_dialog.window.winfo_exists():
            self.replacement_dialog.window.lift()
            self.replacement_dialog.window.focus_force()
            return
        self.replacement_dialog = FactoryReplacementDialog(self, self.workflow)

    def select_track(self, slot: int) -> None:
        card = self.cards[slot - 1]
        data = card.data
        if not data:
            return
        pitch = "—"
        if data["pitch_low"] is not None:
            pitch = f"{note_name(data['pitch_low'])}–{note_name(data['pitch_high'])}"
        channels = ", ".join(map(str, data["channels"])) or "—"
        instrument_evidence = "; ".join(data["evidence"])
        role_evidence = "; ".join(data["role_evidence"])
        self.detail_label.configure(
            text=(
                f"{data['icon']}  {data['instrument']}  ·  {data['role']}  ·  "
                f"instrument {data['confidence']}% / role {data['role_confidence']}%  ·  "
                f"channels {channels}  ·  range {pitch}  ·  max polyphony {data['maximum_polyphony']}\n"
                f"Instrument evidence: {instrument_evidence}\nRole evidence: {role_evidence}"
            )
        )

    def export_json(self) -> None:
        if not self.result or not self.path:
            return
        filename = filedialog.asksaveasfilename(
            title="Export analysis",
            initialfile=f"{self.path.stem}_analysis.json",
            defaultextension=".json",
            filetypes=(("JSON report", "*.json"),),
        )
        if not filename:
            return
        try:
            Path(filename).write_text(
                json.dumps(self.result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as error:
            messagebox.showerror("Export failed", str(error))
            return
        messagebox.showinfo("Export complete", "Analysis report was saved successfully.")


def main() -> None:
    root = tk.Tk()
    MidiEnhancerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()