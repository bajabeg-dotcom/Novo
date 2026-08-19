"""Launcher for the KORG PA800 GM -> RX Optimizer.

``python app.py`` starts the local web GUI (korg_optimizer.gui.web_app)
and opens it in your default browser at http://127.0.0.1:5000/.

This currently launches a read-only "Evidence & Analysis" preview --
see korg_optimizer/gui/web_app.py and gui/analysis.py for exactly what
it does (and docs/ROADMAP.md for what it does not do yet: there is no
optimizer implemented, so there is no "Optimize" action). Both this
launcher and a future CLI (korg_optimizer.cli) must call into the same
optimizer engine once it exists -- see docs/ARCHITECTURE.md "CLI/GUI
shared-engine contract".

Owning vertical: C (RX/Optimizer/Validation/GUI).
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from korg_optimizer.gui import web_app
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from korg_optimizer.gui import web_app


if __name__ == "__main__":
    web_app.run()
