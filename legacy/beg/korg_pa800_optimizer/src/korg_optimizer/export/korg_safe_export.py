"""Writes the final optimized, validated MIDI file via midi.writer,
enforcing the KORG-safe export contract (docs/MIDI_MODEL.md):
preservation-mode content unchanged, only RX-safety-approved triggers,
no undocumented data loss. Not implemented yet.

Owning vertical: C.
"""
