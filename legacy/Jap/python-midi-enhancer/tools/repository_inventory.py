#!/usr/bin/env python3
"""Audit documented production/test/generator artifacts against a Git tree.

The canonical documentation source is registry/master_registry.json.  The
MODULE_LOG.md status table is also checked for module IDs missing from the
registry.  This tool does not infer that a module is correct merely because a
file is present; it only verifies repository presence and documentation
coverage.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "registry" / "master_registry.json"
DEFAULT_MODULE_LOG = ROOT / "MODULE_LOG.md"
REQUIRED_IMPLEMENTATION_STATES = {"PASS", "PARTIAL"}


class InventoryError(RuntimeError):
    """Raised when the inventory cannot be produced safely."""


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    artifact_type: str
    path: str | None
    record_ids: tuple[str, ...]
    detail: str


def _git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if process.returncode:
        message = process.stderr.strip() or process.stdout.strip()
        raise InventoryError(f"git {' '.join(args)} failed: {message}")
    return process.stdout


def git_tree(root: Path, ref: str) -> tuple[str, set[str]]:
    commit = _git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    paths = {
        line
        for line in _git(root, "ls-tree", "-r", "--name-only", commit).splitlines()
        if line
    }
    return commit, paths


def load_registry(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryError(f"cannot load registry {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise InventoryError("registry must contain a records array")
    return data


def module_log_ids(path: Path) -> set[str]:
    """Read external module IDs from the first status table in MODULE_LOG."""
    text = path.read_text(encoding="utf-8")
    section = text.split("## Trenutno stanje", 1)
    if len(section) != 2:
        raise InventoryError("MODULE_LOG.md has no 'Trenutno stanje' section")
    table = section[1].split("\n## ", 1)[0]
    ids: set[str] = set()
    for line in table.splitlines():
        match = re.match(r"^\|\s*([A-Z][A-Z0-9]*\d+)\s*\|", line)
        if match:
            ids.add(match.group(1))
    return ids


def artifact_type(record: dict[str, Any]) -> str:
    if record["kind"] == "TEST":
        return "test"
    path = str(record.get("path", "")).lower()
    title = str(record.get("title", "")).lower()
    if Path(path).name.startswith(("build_", "generate_")) or "generator" in title:
        return "generator"
    return "production"


def _candidate_tracked_artifacts(paths: Iterable[str]) -> set[str]:
    candidates: set[str] = set()
    for path in paths:
        item = Path(path)
        if item.parts and item.parts[0] == "tests" and item.name.startswith("test_") and item.suffix == ".py":
            candidates.add(path)
        elif item.suffix == ".py" and (
            len(item.parts) == 1
            or item.parts[0] in {"registry", "tools"}
            and "__pycache__" not in item.parts
        ):
            candidates.add(path)
    return candidates


def build_inventory(
    root: Path = ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    module_log_path: Path = DEFAULT_MODULE_LOG,
    ref: str = "HEAD",
) -> dict[str, Any]:
    commit, tracked = git_tree(root, ref)
    data = load_registry(registry_path)
    records = data["records"]
    findings: list[Finding] = []
    checked_records = 0
    documented_paths: dict[str, list[str]] = {}

    for record in records:
        if record.get("kind") not in {"MODULE", "TEST"}:
            continue
        implementation = record.get("implementation", {}).get("state")
        if implementation not in REQUIRED_IMPLEMENTATION_STATES:
            continue
        checked_records += 1
        record_id = str(record.get("id", "<missing-id>"))
        kind = artifact_type(record)
        path = record.get("path")
        if not isinstance(path, str) or not path:
            findings.append(
                Finding(
                    code="DOCUMENTED_IMPLEMENTATION_WITHOUT_PATH",
                    severity="ERROR",
                    artifact_type=kind,
                    path=None,
                    record_ids=(record_id,),
                    detail=f"{record_id} claims implementation={implementation} but has no path",
                )
            )
            continue
        documented_paths.setdefault(path, []).append(record_id)
        worktree_file = root / path
        if not worktree_file.is_file():
            findings.append(
                Finding(
                    code="MISSING_FROM_WORKTREE",
                    severity="ERROR",
                    artifact_type=kind,
                    path=path,
                    record_ids=(record_id,),
                    detail="documented artifact is absent from the current worktree",
                )
            )
        if path not in tracked:
            findings.append(
                Finding(
                    code="MISSING_FROM_GIT_TREE",
                    severity="ERROR",
                    artifact_type=kind,
                    path=path,
                    record_ids=(record_id,),
                    detail=f"documented artifact is absent from git ls-tree {commit}",
                )
            )

    registry_module_ids = {
        str(record["external_id"])
        for record in records
        if record.get("kind") == "MODULE" and record.get("external_id")
    }
    for external_id in sorted(module_log_ids(module_log_path) - registry_module_ids):
        findings.append(
            Finding(
                code="MODULE_LOG_ID_MISSING_FROM_REGISTRY",
                severity="ERROR",
                artifact_type="documentation",
                path="MODULE_LOG.md",
                record_ids=(external_id,),
                detail="module appears in MODULE_LOG status table but not as a registry MODULE",
            )
        )

    for path in sorted(_candidate_tracked_artifacts(tracked) - set(documented_paths)):
        # The audit tools test themselves but do not claim a product module ID.
        severity = "INFO" if path.startswith("tools/") else "WARNING"
        findings.append(
            Finding(
                code="TRACKED_ARTIFACT_WITHOUT_REGISTRY_RECORD",
                severity=severity,
                artifact_type=("test" if path.startswith("tests/") else "production"),
                path=path,
                record_ids=(),
                detail="tracked Python artifact is not referenced by an implemented MODULE/TEST record",
            )
        )

    status = "FAIL" if any(item.severity == "ERROR" for item in findings) else "PASS"
    dirty_lines = [line for line in _git(root, "status", "--porcelain").splitlines() if line]
    type_counts = {
        name: sum(1 for path in documented_paths if artifact_type_from_path(path, records) == name)
        for name in ("production", "test", "generator")
    }
    return {
        "schema_version": "1.0.0",
        "audit_date": date.today().isoformat(),
        "status": status,
        "audited_ref": ref,
        "audited_commit": commit,
        "registry_version": data.get("registry_version"),
        "summary": {
            "tracked_files": len(tracked),
            "implemented_records_checked": checked_records,
            "unique_documented_artifacts": len(documented_paths),
            "artifact_counts": type_counts,
            "errors": sum(item.severity == "ERROR" for item in findings),
            "warnings": sum(item.severity == "WARNING" for item in findings),
            "info": sum(item.severity == "INFO" for item in findings),
            "dirty_entries_at_audit": len(dirty_lines),
        },
        "findings": [asdict(item) for item in findings],
        "dirty_paths": dirty_lines,
        "scope_note": (
            "PASS proves only that documented production/test/generator artifacts are present "
            "in the selected Git tree and worktree. It does not prove musical correctness, "
            "test success, Pa800 behavior, or consistency of narrative claims in main.tex."
        ),
    }


def artifact_type_from_path(path: str, records: list[dict[str, Any]]) -> str:
    matching = [record for record in records if record.get("path") == path and record.get("kind") in {"MODULE", "TEST"}]
    types = {artifact_type(record) for record in matching}
    if "test" in types:
        return "test"
    if "generator" in types:
        return "generator"
    return "production"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Repository inventory audit",
        "",
        f"- Status: **{report['status']}**",
        f"- Audit date: `{report['audit_date']}`",
        f"- Git ref: `{report['audited_ref']}`",
        f"- Commit: `{report['audited_commit']}`",
        f"- Registry version: `{report['registry_version']}`",
        f"- Tracked files: `{summary['tracked_files']}`",
        f"- Implemented records checked: `{summary['implemented_records_checked']}`",
        f"- Unique documented artifacts: `{summary['unique_documented_artifacts']}`",
        f"- Errors / warnings / info: `{summary['errors']} / {summary['warnings']} / {summary['info']}`",
        "",
        "## Findings",
        "",
    ]
    if not report["findings"]:
        lines.append("No findings.")
    else:
        lines.extend([
            "| Severity | Code | Type | Path | Records | Detail |",
            "|---|---|---|---|---|---|",
        ])
        for item in report["findings"]:
            records = ", ".join(item["record_ids"]) or "—"
            path = item["path"] or "—"
            detail = str(item["detail"]).replace("|", "\\|")
            lines.append(
                f"| {item['severity']} | `{item['code']}` | {item['artifact_type']} | "
                f"`{path}` | {records} | {detail} |"
            )
    lines.extend(["", "## Scope", "", report["scope_note"], ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--module-log", type=Path, default=DEFAULT_MODULE_LOG)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_inventory(args.root, args.registry, args.module_log, args.ref)
    except (InventoryError, OSError) as exc:
        print(f"inventory error: {exc}", file=sys.stderr)
        return 2
    rendered_json = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered_json, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        print(rendered_json, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
