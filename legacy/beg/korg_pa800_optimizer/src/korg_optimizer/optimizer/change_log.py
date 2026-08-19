"""ChangeLogEntry record definitions (track, event, before, after,
rule, reason, confidence, source). Every mutation the optimizer makes
must produce one of these -- see docs/ARCHITECTURE.md
"no-silent-mutation". This module defines the record shape that
Vertical A's audit/trail.py stores -- see
docs/VERTICAL_DECOMPOSITION.md "cross-vertical data contracts". Not
implemented yet.

Owning vertical: C.
"""
