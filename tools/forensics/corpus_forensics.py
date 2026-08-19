"""Puna forenzika DNA korpusa (Factory + Gold).

Skenira svaki MIDI nezavisnim parserom i gradi izvještaj:
integritet, duplikati, strukturne anomalije, statistika po korpusu i ulozi.

Upotreba:
    python3 tools/forensics/corpus_forensics.py CORPUS_DIR --json out.json
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smf_probe import SmfError, probe, summarize  # noqa: E402

GM_DRUM_CHANNEL = 10


def classify_role(channel: int, programs: list[int]) -> str:
    """Gruba GM klasifikacija — samo za agregatnu statistiku, ne za odluke."""
    if channel == GM_DRUM_CHANNEL:
        return "drums"
    if not programs:
        return "unknown"
    p = programs[0]
    if 32 <= p <= 39:
        return "bass"
    if 24 <= p <= 31:
        return "guitar"
    if 0 <= p <= 7:
        return "piano"
    if 40 <= p <= 55:
        return "strings"
    if 56 <= p <= 79:
        return "brass_wind"
    return "other"


def scan(root: str) -> dict[str, Any]:
    files: list[str] = []
    for base, _dirs, names in os.walk(root):
        for name in names:
            if name.lower().endswith((".mid", ".midi")):
                files.append(os.path.join(base, name))
    files.sort()

    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for path in files:
        rel = os.path.relpath(path, root)
        try:
            facts = probe(path)
        except SmfError as exc:
            with open(path, "rb") as handle:
                blob = handle.read()
            failures.append(
                {
                    "path": rel,
                    "error": str(exc),
                    "size": len(blob),
                    "sha256": hashlib.sha256(blob).hexdigest(),
                }
            )
            continue
        record = summarize(facts)
        record["path"] = rel
        record["corpus"] = rel.split(os.sep)[0]
        record["style"] = rel.split(os.sep)[1] if os.sep in rel else ""
        records.append(record)

    return {"root": root, "records": records, "failures": failures}


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def analyze(scan_result: dict[str, Any]) -> dict[str, Any]:
    records = scan_result["records"]
    failures = scan_result["failures"]

    by_hash: dict[str, list[str]] = collections.defaultdict(list)
    for r in records:
        by_hash[r["sha256"]].append(r["path"])
    duplicates = {h: p for h, p in by_hash.items() if len(p) > 1}

    corpora = collections.Counter(r["corpus"] for r in records)
    formats = collections.Counter(r["format"] for r in records)
    ppqs = collections.Counter(r["ppq"] for r in records)
    track_counts = collections.Counter(r["tracks"] for r in records)

    all_warnings: collections.Counter[str] = collections.Counter()
    files_with_warnings = 0
    for r in records:
        if r["warnings"]:
            files_with_warnings += 1
        for w in r["warnings"]:
            key = w.split(":", 1)[-1].strip()
            key = "".join("N" if c.isdigit() else c for c in key)
            all_warnings[key] += 1

    velocities = [r["velocity_mean"] for r in records if r["velocity_mean"] is not None]
    notes = [r["note_on"] for r in records]

    # per-korpus statistika
    per_corpus: dict[str, Any] = {}
    for corpus in sorted(corpora):
        subset = [r for r in records if r["corpus"] == corpus]
        vel = [r["velocity_mean"] for r in subset if r["velocity_mean"] is not None]
        per_corpus[corpus] = {
            "files": len(subset),
            "unique_sha256": len({r["sha256"] for r in subset}),
            "notes_total": sum(r["note_on"] for r in subset),
            "formats": dict(collections.Counter(r["format"] for r in subset)),
            "ppq": dict(collections.Counter(r["ppq"] for r in subset)),
            "tracks_mean": round(
                statistics.mean([r["tracks"] for r in subset]), 2
            )
            if subset
            else None,
            "velocity_mean": round(statistics.mean(vel), 2) if vel else None,
            "velocity_p10": round(_pct(vel, 0.10), 2) if vel else None,
            "velocity_p90": round(_pct(vel, 0.90), 2) if vel else None,
            "sysex_files": sum(1 for r in subset if r["sysex_count"]),
            "pitch_bend_files": sum(1 for r in subset if r["pitch_bend"]),
            "files_with_warnings": sum(1 for r in subset if r["warnings"]),
            "channels_used": sorted(
                {c for r in subset for c in r["channels"]}
            ),
            "empty_files": sum(1 for r in subset if r["note_on"] == 0),
        }

    # bank/program pokrivenost
    cc0 = collections.Counter(v for r in records for v in r["cc0"])
    cc32 = collections.Counter(v for r in records for v in r["cc32"])
    programs = collections.Counter(p for r in records for p in r["programs"])
    controllers: collections.Counter[int] = collections.Counter()
    for r in records:
        for cc, n in r["controllers"].items():
            controllers[int(cc)] += n

    # anomalije
    anomalies = {
        "zero_note_files": [r["path"] for r in records if r["note_on"] == 0],
        "no_eot_tracks": [
            r["path"] for r in records if r.get("tracks_without_eot", 0)
        ],
        "trailing_bytes": [
            r["path"] for r in records if r.get("trailing_file_bytes", 0)
        ],
        "unbalanced_notes": [
            {"path": r["path"], "on": r["note_on"], "off": r["note_off"]}
            for r in records
            if r["note_on"] != r["note_off"]
        ],
        "smpte_files": [r["path"] for r in records if r["smpte"]],
        "format2_files": [r["path"] for r in records if r["format"] == 2],
        "velocity_127_only": [
            r["path"]
            for r in records
            if r["velocity_min"] == 127 and r["velocity_max"] == 127
        ],
        "channel_overflow": [
            r["path"] for r in records if any(c > 16 or c < 1 for c in r["channels"])
        ],
    }

    tempos = [t for r in records for t in r["tempo_us"] if t]
    bpms = [60_000_000 / t for t in tempos]
    meters = collections.Counter(tuple(m) for r in records for m in r["meters"])

    return {
        "totals": {
            "files_scanned": len(records) + len(failures),
            "parsed_ok": len(records),
            "parse_failures": len(failures),
            "unique_sha256": len(by_hash),
            "duplicate_groups": len(duplicates),
            "duplicate_files": sum(len(v) for v in duplicates.values()),
            "notes_total": sum(notes),
            "files_with_warnings": files_with_warnings,
        },
        "per_corpus": per_corpus,
        "formats": dict(formats),
        "ppq": {str(k): v for k, v in ppqs.items()},
        "track_count_histogram": dict(sorted(track_counts.items())),
        "warning_kinds": dict(all_warnings.most_common(30)),
        "duplicates": {h: p for h, p in list(duplicates.items())},
        "bank_program": {
            "cc0_values": dict(sorted(cc0.items())),
            "cc32_values": dict(sorted(cc32.items())),
            "program_histogram": dict(sorted(programs.items())),
            "distinct_programs": len(programs),
        },
        "controllers": dict(controllers.most_common(40)),
        "tempo": {
            "count": len(bpms),
            "min_bpm": round(min(bpms), 2) if bpms else None,
            "max_bpm": round(max(bpms), 2) if bpms else None,
            "mean_bpm": round(statistics.mean(bpms), 2) if bpms else None,
        },
        "meters": {f"{n}/{d}": c for (n, d), c in meters.most_common(20)},
        "velocity_overall": {
            "mean_of_file_means": round(statistics.mean(velocities), 2)
            if velocities
            else None,
        },
        "anomalies": {k: v for k, v in anomalies.items()},
        "anomaly_counts": {k: len(v) for k, v in anomalies.items()},
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Forenzika DNA korpusa")
    parser.add_argument("root")
    parser.add_argument("--json", dest="json_out")
    parser.add_argument("--records", dest="records_out")
    args = parser.parse_args()

    scan_result = scan(args.root)
    report = analyze(scan_result)

    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, ensure_ascii=False, sort_keys=True)
    if args.records_out:
        with open(args.records_out, "w", encoding="utf-8") as handle:
            json.dump(scan_result["records"], handle, ensure_ascii=False)

    print(json.dumps(report["totals"], indent=1))
    print(json.dumps(report["anomaly_counts"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
