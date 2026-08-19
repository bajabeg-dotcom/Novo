"""Puna forenzika SQLite baze `pa800-enhancer.db`.

Provjerava integritet, shemu, referencijalnu konzistentnost, sadržaj i
— ako je dat korpus — unakrsnu podudarnost baze sa stvarnim izvorima.

Upotreba:
    python3 tools/forensics/db_forensics.py data/pa800-enhancer.db \
        --corpus-records /tmp/fx/corpus_records.json --json out.json
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import sqlite3
import statistics
from typing import Any

EXPECTED_ROLES = {"solo", "accompaniment", "bass", "drums", "guitar"}


def _rows(conn: sqlite3.Connection, sql: str, *params: Any) -> list[tuple]:
    return conn.execute(sql, params).fetchall()


def integrity(conn: sqlite3.Connection) -> dict[str, Any]:
    quick = [r[0] for r in _rows(conn, "PRAGMA integrity_check")]
    fk = _rows(conn, "PRAGMA foreign_key_check")
    return {
        "integrity_check": quick,
        "ok": quick == ["ok"],
        "foreign_key_violations": len(fk),
        "foreign_key_details": [list(r) for r in fk[:20]],
        "page_size": _rows(conn, "PRAGMA page_size")[0][0],
        "page_count": _rows(conn, "PRAGMA page_count")[0][0],
        "freelist_count": _rows(conn, "PRAGMA freelist_count")[0][0],
        "journal_mode": _rows(conn, "PRAGMA journal_mode")[0][0],
        "encoding": _rows(conn, "PRAGMA encoding")[0][0],
        "user_version": _rows(conn, "PRAGMA user_version")[0][0],
        "application_id": _rows(conn, "PRAGMA application_id")[0][0],
    }


def schema(conn: sqlite3.Connection) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    for name, sql in _rows(
        conn, "select name, sql from sqlite_master where type='table' order by name"
    ):
        count = _rows(conn, f"select count(*) from [{name}]")[0][0]
        cols = _rows(conn, f"PRAGMA table_info([{name}])")
        fks = _rows(conn, f"PRAGMA foreign_key_list([{name}])")
        tables[name] = {
            "rows": count,
            "columns": [
                {
                    "name": c[1],
                    "type": c[2],
                    "notnull": bool(c[3]),
                    "pk": bool(c[5]),
                }
                for c in cols
            ],
            "foreign_keys": [{"table": f[2], "from": f[3], "to": f[4]} for f in fks],
            "has_check": "CHECK" in (sql or ""),
        }
    indices = [
        {"name": n, "sql": s}
        for n, s in _rows(
            conn,
            "select name, sql from sqlite_master where type='index' and sql is not null",
        )
    ]
    return {
        "tables": tables,
        "table_count": len(tables),
        "index_count": len(indices),
        "indices": [i["name"] for i in indices],
        "empty_tables": sorted(n for n, t in tables.items() if t["rows"] == 0),
        "populated_tables": sorted(n for n, t in tables.items() if t["rows"] > 0),
    }


def fingerprints(conn: sqlite3.Connection) -> dict[str, Any]:
    total = _rows(conn, "select count(*) from midi_fingerprints")[0][0]
    sources = _rows(conn, "select count(*) from midi_fingerprint_sources")[0][0]
    roles = _rows(conn, "select count(*) from midi_fingerprint_roles")[0][0]

    orphan_roles = _rows(
        conn,
        """select count(*) from midi_fingerprint_roles r
           left join midi_fingerprints f on f.fingerprint_id=r.fingerprint_id
           where f.fingerprint_id is null""",
    )[0][0]
    orphan_sources = _rows(
        conn,
        """select count(*) from midi_fingerprint_sources s
           left join midi_fingerprints f on f.fingerprint_id=s.fingerprint_id
           where f.fingerprint_id is null""",
    )[0][0]
    fp_without_roles = _rows(
        conn,
        """select count(*) from midi_fingerprints f
           left join midi_fingerprint_roles r on r.fingerprint_id=f.fingerprint_id
           where r.fingerprint_id is null""",
    )[0][0]

    role_hist = dict(
        _rows(conn, "select role, count(*) from midi_fingerprint_roles group by 1")
    )
    role_notes = dict(
        _rows(
            conn,
            "select role, sum(note_count) from midi_fingerprint_roles group by 1",
        )
    )
    per_fp = collections.Counter(
        c
        for _, c in _rows(
            conn,
            "select fingerprint_id, count(*) from midi_fingerprint_roles group by 1",
        )
    )
    corpus = dict(
        _rows(conn, "select corpus_kind, count(*) from midi_fingerprints group by 1")
    )
    corpus_src = dict(
        _rows(
            conn,
            "select corpus_kind, count(*) from midi_fingerprint_sources group by 1",
        )
    )
    ppq = dict(_rows(conn, "select ppq, count(*) from midi_fingerprints group by 1"))

    zero_notes = _rows(
        conn, "select count(*) from midi_fingerprint_roles where note_count<=0"
    )[0][0]
    bad_roles = _rows(
        conn,
        "select distinct role from midi_fingerprint_roles where role not in "
        "('solo','accompaniment','bass','drums','guitar')",
    )

    # dedup: koliko locator-a dijeli isti fingerprint
    shared = _rows(
        conn,
        """select fingerprint_id, count(*) c from midi_fingerprint_sources
           group by 1 having c>1 order by c desc""",
    )

    imported = _rows(
        conn,
        "select min(imported_at), max(imported_at) from midi_fingerprints",
    )[0]

    return {
        "counts": {
            "fingerprints": total,
            "sources": sources,
            "roles": roles,
            "role_notes_total": sum(v for v in role_notes.values() if v),
        },
        "referential": {
            "orphan_roles": orphan_roles,
            "orphan_sources": orphan_sources,
            "fingerprints_without_roles": fp_without_roles,
            "clean": orphan_roles == 0
            and orphan_sources == 0
            and fp_without_roles == 0,
        },
        "role_histogram": role_hist,
        "role_notes": role_notes,
        "roles_per_fingerprint": dict(sorted(per_fp.items())),
        "complete_5_role_sources": per_fp.get(5, 0),
        "corpus_fingerprints": corpus,
        "corpus_sources": corpus_src,
        "ppq_histogram": {str(k): v for k, v in ppq.items()},
        "zero_note_roles": zero_notes,
        "invalid_role_labels": [r[0] for r in bad_roles],
        "shared_fingerprint_groups": len(shared),
        "shared_fingerprint_top": [list(r) for r in shared[:10]],
        "imported_at_range": list(imported),
        "missing_roles": {
            role: total - role_hist.get(role, 0) for role in sorted(EXPECTED_ROLES)
        },
    }


def vectors(conn: sqlite3.Connection, sample: int = 4000) -> dict[str, Any]:
    """Provjera kvaliteta feature vektora — NaN, inf, konstante, dimenzije."""
    rows = _rows(
        conn,
        "select role, vector_json, features_json, note_count "
        "from midi_fingerprint_roles limit ?",
        sample,
    )
    dims: collections.Counter[int] = collections.Counter()
    nan_count = inf_count = 0
    per_role_dim: dict[str, set[int]] = collections.defaultdict(set)
    feature_keys: collections.Counter[str] = collections.Counter()
    all_values: dict[int, list[float]] = collections.defaultdict(list)
    mismatched_notes = 0
    bad_json = 0

    for role, vec_json, feat_json, note_count in rows:
        try:
            vec = json.loads(vec_json)
            feat = json.loads(feat_json)
        except json.JSONDecodeError:
            bad_json += 1
            continue
        dims[len(vec)] += 1
        per_role_dim[role].add(len(vec))
        for i, v in enumerate(vec):
            if isinstance(v, float):
                if math.isnan(v):
                    nan_count += 1
                elif math.isinf(v):
                    inf_count += 1
                else:
                    all_values[i].append(v)
        for k in feat:
            feature_keys[k] += 1
        if feat.get("note_count") not in (None, note_count):
            mismatched_notes += 1

    constant_dims = [
        i for i, vals in all_values.items() if vals and len(set(vals)) == 1
    ]
    ranges = {
        str(i): {
            "min": round(min(v), 4),
            "max": round(max(v), 4),
            "mean": round(statistics.mean(v), 4),
        }
        for i, v in sorted(all_values.items())
        if v
    }
    return {
        "sampled": len(rows),
        "dimension_histogram": dict(dims),
        "consistent_dimension": len(dims) == 1,
        "per_role_dimensions": {k: sorted(v) for k, v in per_role_dim.items()},
        "nan_values": nan_count,
        "inf_values": inf_count,
        "bad_json": bad_json,
        "feature_keys": dict(feature_keys.most_common()),
        "constant_dimensions": constant_dims,
        "dimension_ranges": ranges,
        "note_count_mismatch": mismatched_notes,
    }


def cross_check(conn: sqlite3.Connection, records_path: str) -> dict[str, Any]:
    """Unakrsna provjera baze prema nezavisno skeniranom korpusu."""
    with open(records_path, encoding="utf-8") as handle:
        records = json.load(handle)

    by_hash: dict[str, dict[str, Any]] = {}
    for r in records:
        by_hash.setdefault(r["sha256"], r)

    db_hashes = {
        h: (fid, ppq, end)
        for h, fid, ppq, end in _rows(
            conn,
            "select source_sha256, fingerprint_id, ppq, end_tick from midi_fingerprints",
        )
    }
    db_notes = dict(
        _rows(
            conn,
            """select f.source_sha256, sum(r.note_count)
               from midi_fingerprints f
               join midi_fingerprint_roles r on r.fingerprint_id=f.fingerprint_id
               group by 1""",
        )
    )

    in_corpus_not_db = sorted(set(by_hash) - set(db_hashes))
    in_db_not_corpus = sorted(set(db_hashes) - set(by_hash))

    ppq_mismatch = []
    end_mismatch = []
    note_delta: list[dict[str, Any]] = []
    for h, rec in by_hash.items():
        if h not in db_hashes:
            continue
        _fid, ppq, end = db_hashes[h]
        if rec["ppq"] != ppq:
            ppq_mismatch.append({"path": rec["path"], "smf": rec["ppq"], "db": ppq})
        if rec["end_tick"] != end:
            end_mismatch.append(
                {"path": rec["path"], "smf": rec["end_tick"], "db": end}
            )
        delta = rec["note_on"] - db_notes.get(h, 0)
        if delta:
            note_delta.append(
                {
                    "path": rec["path"],
                    "smf_note_on": rec["note_on"],
                    "db_notes": db_notes.get(h, 0),
                    "lost": delta,
                    "unbalanced": rec["note_on"] - rec["note_off"],
                }
            )

    note_delta.sort(key=lambda d: -d["lost"])
    total_smf = sum(r["note_on"] for r in by_hash.values())
    total_db = sum(db_notes.values())

    return {
        "corpus_unique_files": len(by_hash),
        "db_fingerprints": len(db_hashes),
        "in_corpus_not_in_db": len(in_corpus_not_db),
        "in_db_not_in_corpus": len(in_db_not_corpus),
        "hash_coverage_complete": not in_corpus_not_db and not in_db_not_corpus,
        "ppq_mismatches": len(ppq_mismatch),
        "ppq_mismatch_sample": ppq_mismatch[:10],
        "end_tick_mismatches": len(end_mismatch),
        "end_tick_mismatch_sample": end_mismatch[:10],
        "note_totals": {
            "smf_note_on": total_smf,
            "db_role_notes": total_db,
            "lost": total_smf - total_db,
            "lost_pct": round(100 * (total_smf - total_db) / total_smf, 4)
            if total_smf
            else 0,
        },
        "files_with_note_loss": len(note_delta),
        "note_loss_top": note_delta[:25],
    }


def artifact_audit(root: str) -> dict[str, Any]:
    manifest_path = os.path.join(root, "data", "artifact-manifest.json")
    if not os.path.exists(manifest_path):
        return {"available": False}
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    results = []
    for artifact in manifest.get("artifacts", []):
        path = os.path.join(root, artifact["relative_path"])
        entry = {
            "artifact_id": artifact["artifact_id"],
            "status": artifact.get("status"),
            "expected_sha256": artifact["sha256"],
            "exists": os.path.exists(path),
        }
        if entry["exists"]:
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            entry["actual_sha256"] = digest
            entry["size_ok"] = os.path.getsize(path) == artifact["size"]
            entry["match"] = digest == artifact["sha256"] and entry["size_ok"]
        else:
            entry["match"] = False
        results.append(entry)
    return {
        "available": True,
        "artifacts": results,
        "all_match": all(a["match"] for a in results),
        "status_histogram": dict(
            collections.Counter(a.get("status") for a in results)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Forenzika pa800-enhancer.db")
    parser.add_argument("database")
    parser.add_argument("--corpus-records")
    parser.add_argument("--project-root")
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    report: dict[str, Any] = {
        "database": {
            "path": os.path.abspath(args.database),
            "size": os.path.getsize(args.database),
            "sha256": hashlib.sha256(
                open(args.database, "rb").read()
            ).hexdigest(),
        },
        "integrity": integrity(conn),
        "schema": schema(conn),
        "fingerprints": fingerprints(conn),
        "vectors": vectors(conn),
    }
    if args.corpus_records:
        report["cross_check"] = cross_check(conn, args.corpus_records)
    if args.project_root:
        report["artifacts"] = artifact_audit(args.project_root)

    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, ensure_ascii=False, sort_keys=True)

    print(json.dumps(report["integrity"], indent=1))
    print(json.dumps(report["fingerprints"]["referential"], indent=1))
    if "cross_check" in report:
        print(json.dumps(report["cross_check"]["note_totals"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
