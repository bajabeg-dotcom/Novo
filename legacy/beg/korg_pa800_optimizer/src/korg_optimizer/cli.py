"""Command-line interface.

Intended commands (per docs/ROADMAP.md, not yet implemented):
import, analyze, optimize, validate, export, build-dna,
evidence-inventory, audit, test. Must call into optimizer.engine only
-- see docs/ARCHITECTURE.md "CLI/GUI shared-engine contract". No
optimizer logic may live here.

Owning vertical: C (RX/Optimizer/Validation/GUI).
"""
