"""Local web GUI: upload a MIDI file and see what the implemented
Phase 1-4 pipeline can tell you about it (structure, tracks, raw
Program Change/CC facts, filename-derived Style Element evidence).

There is deliberately no "Optimize" action -- the optimizer, RX
mapping, and Gold DNA modules (docs/ROADMAP.md Phase 5+) are not
implemented yet, and this GUI must never imply they are. See
gui/analysis.py for what actually runs.

Run via ``python app.py`` (see the package root), which calls
``run()`` below.

Owning vertical: C.
"""

from __future__ import annotations

import tempfile
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from . import analysis

ALLOWED_EXTENSIONS = {".mid", ".midi"}
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB, generous for a single MIDI file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/analyze")
def analyze():
    uploaded = request.files.get("midi_file")
    if uploaded is None or uploaded.filename == "":
        return render_template("index.html", error="Please choose a .mid file first.")

    filename = secure_filename(uploaded.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return render_template(
            "index.html",
            error=f"Unsupported file type '{suffix}' -- only .mid/.midi files are accepted.",
        )

    with tempfile.TemporaryDirectory(prefix="korg_optimizer_upload_") as tmp_dir:
        tmp_path = Path(tmp_dir) / (filename or "upload.mid")
        uploaded.save(tmp_path)
        try:
            result = analysis.analyze_uploaded_file(tmp_path, original_filename=uploaded.filename)
        except Exception as exc:  # noqa: BLE001 -- surface parse errors to the user, don't crash the server
            return render_template(
                "index.html",
                error=f"Could not parse '{uploaded.filename}' as a Standard MIDI File: {exc}",
            )

    return render_template("results.html", result=result)


@app.get("/health")
def health():
    return {"status": "ok"}


def run(host: str = "127.0.0.1", port: int = 5000, *, open_browser: bool = True) -> None:
    """Start the local web GUI. Blocks until interrupted (Ctrl+C)."""
    if open_browser:
        Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}/")).start()
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run()
