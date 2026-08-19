"""Single entrypoint for the full pipeline: import -> identity ->
structure -> musical analysis -> RX safety -> Factory/Gold DNA lookup
-> optimization -> validation -> audit -> export. See
docs/ARCHITECTURE.md "Pipeline overview" and "CLI/GUI shared-engine
contract" -- cli.py and gui/main_window.py must call only this. Not
implemented yet.

Owning vertical: C.
"""
