"""RX Safety Engine: runs identity-lock -> safety-check before any
optimization. BLOCKs changes that could trigger unconfirmed or
contextually-wrong RX articulations; UNKNOWN never triggers. See
docs/RX_SPECIFICATION.md "Decision rules". Depends on
musical.instrument_identity (Vertical B) and mapping.gm_to_rx. Not
implemented yet.

Owning vertical: C.
"""
