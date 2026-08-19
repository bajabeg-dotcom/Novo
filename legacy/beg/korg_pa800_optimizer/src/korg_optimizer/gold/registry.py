"""Query interface other modules (musical/, rx/, optimizer/) will use
to look up Gold DNA rules by category/rule_id, once they exist
(Phase 7+). Consumers must never bypass this to read factory_dna or
raw evidence directly -- see docs/ARCHITECTURE.md "four knowledge
layers". Never exposes a blocked (UNKNOWN evidence_level) row -- only
genuinely promoted rules are visible through this interface.

Owning vertical: B.
"""

from __future__ import annotations

import sqlite3

from .gold_dna import GoldDNARule, load_gold_dna, get_by_rule_id as _get_by_rule_id


def get_rules_by_category(conn: sqlite3.Connection, category: str) -> list[GoldDNARule]:
    return load_gold_dna(conn, category=category, promoted_only=True)


def get_rule(conn: sqlite3.Connection, rule_id: str) -> GoldDNARule | None:
    rule = _get_by_rule_id(conn, rule_id)
    return rule if rule is not None and rule.is_promoted else None
