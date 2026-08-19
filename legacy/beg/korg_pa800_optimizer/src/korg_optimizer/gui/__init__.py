"""Web GUI.

Currently: a read-only "Evidence & Analysis" preview
(web_app.py + analysis.py) -- upload a MIDI file, see structural
validation and raw per-track/file facts using the implemented Phase
1-4 pipeline. No optimization exists yet, so there is deliberately no
Safe/Expert/Generative mode switch and no "Optimize" action -- adding
one before optimizer.engine exists would violate docs/PROJECT_GOAL.md's
no-invented-behavior rule. Once the optimizer is implemented
(docs/ROADMAP.md Phase 15+), this module becomes the only place (with
cli.py) allowed to call into it -- see docs/ARCHITECTURE.md "CLI/GUI
shared-engine contract".

Owning vertical: C.
"""
