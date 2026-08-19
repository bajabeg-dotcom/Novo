"""Stores and queries AuditTrailEntry records (audit_trail table).

Records action-level decisions (e.g. PRESERVE, APPLY, BLOCK), not just
mutations -- see docs/DATA_MODEL.md "audit" and
docs/ARCHITECTURE.md "no-silent-mutation". Populated via calls from
Vertical C's optimizer during a run. Not implemented yet.

Owning vertical: A.
"""
