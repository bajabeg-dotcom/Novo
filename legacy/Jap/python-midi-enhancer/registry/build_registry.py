#!/usr/bin/env python3
"""Validate the G00 registry and generate its deterministic Markdown view."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent
DEFAULT_INPUT = ROOT / "master_registry.json"
DEFAULT_OUTPUT = ROOT / "MASTER_REGISTRY.md"
ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-[0-9]{3}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
KINDS = {
    "RESOURCE", "MODULE", "TEST", "TEST_RUN", "CLAIM", "EVIDENCE",
    "ISSUE", "DECISION", "CERTIFICATION",
}
LIFECYCLES = {
    "ACTIVE", "PROPOSED", "BLOCKED", "FAILED", "SUPERSEDED",
    "IDEA_CATALOG", "HISTORICAL",
}
AXIS_STATES = {
    "NOT_APPLICABLE", "NONE", "PROPOSED", "PARTIAL", "BLOCKED", "FAIL",
    "PASS", "CONFIRMED",
}
AXES = ("evidence", "implementation", "validation", "certification")
KIND_PREFIXES = {
    "RESOURCE": "DATA",
    "MODULE": "MOD",
    "TEST": "TEST",
    "TEST_RUN": "RUN",
    "CLAIM": "CLAIM",
    "EVIDENCE": "EVID",
    "ISSUE": "ISSUE",
    "DECISION": "DEC",
    "CERTIFICATION": "CERT",
}
REQUIRED = {"id", "kind", "title", "summary", "lifecycle", *AXES, "refs"}
OPTIONAL = {
    "external_id", "path", "sha256", "source_scope", "command",
    "observations", "observation_unit",
}


class RegistryError(ValueError):
    """Raised when registry invariants are violated."""


def load_registry(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RegistryError("registry root must be an object")
    return data


def _validate_axis(record_id: str, name: str, value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"state", "detail"}:
        raise RegistryError(f"{record_id}: {name} must contain only state/detail")
    if value["state"] not in AXIS_STATES:
        raise RegistryError(f"{record_id}: invalid {name} state {value['state']!r}")
    if not isinstance(value["detail"], str) or not value["detail"].strip():
        raise RegistryError(f"{record_id}: {name}.detail must be non-empty")


def validate_registry(data: dict[str, Any]) -> list[dict[str, Any]]:
    if set(data) != {"registry_version", "as_of", "records"}:
        raise RegistryError("root must contain only registry_version, as_of and records")
    if not re.fullmatch(r"0\.[0-9]+\.[0-9]+", str(data["registry_version"])):
        raise RegistryError("registry_version must be a 0.x.y version")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", str(data["as_of"])):
        raise RegistryError("as_of must be YYYY-MM-DD")
    records = data["records"]
    if not isinstance(records, list):
        raise RegistryError("records must be an array")

    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise RegistryError(f"record {index} must be an object")
        missing = REQUIRED - set(record)
        unknown = set(record) - REQUIRED - OPTIONAL
        if missing or unknown:
            raise RegistryError(
                f"record {index}: missing={sorted(missing)} unknown={sorted(unknown)}"
            )
        record_id = record["id"]
        if not isinstance(record_id, str) or not ID_RE.fullmatch(record_id):
            raise RegistryError(f"record {index}: invalid id {record_id!r}")
        if record_id in seen:
            raise RegistryError(f"duplicate id: {record_id}")
        seen.add(record_id)
        if record["kind"] not in KINDS:
            raise RegistryError(f"{record_id}: invalid kind")
        expected_prefix = KIND_PREFIXES[record["kind"]] + "-"
        if not record_id.startswith(expected_prefix):
            raise RegistryError(
                f"{record_id}: kind {record['kind']} requires {expected_prefix} prefix"
            )
        if record["lifecycle"] not in LIFECYCLES:
            raise RegistryError(f"{record_id}: invalid lifecycle")
        for key in ("title", "summary"):
            if not isinstance(record[key], str) or not record[key].strip():
                raise RegistryError(f"{record_id}: {key} must be non-empty")
        for axis in AXES:
            _validate_axis(record_id, axis, record[axis])
        if record["lifecycle"] == "IDEA_CATALOG":
            if record["kind"] != "RESOURCE":
                raise RegistryError(f"{record_id}: IDEA_CATALOG must be a RESOURCE")
            for axis in ("implementation", "validation", "certification"):
                if record[axis]["state"] != "NONE":
                    raise RegistryError(
                        f"{record_id}: IDEA_CATALOG {axis} must remain NONE"
                    )
        refs = record["refs"]
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            raise RegistryError(f"{record_id}: refs must be a unique array")
        if record_id in refs:
            raise RegistryError(f"{record_id}: self-reference is not allowed")
        if "sha256" in record and not SHA_RE.fullmatch(record["sha256"]):
            raise RegistryError(f"{record_id}: invalid sha256")
        if "observations" in record and (
            not isinstance(record["observations"], int) or record["observations"] < 0
        ):
            raise RegistryError(f"{record_id}: observations must be a non-negative integer")

    for record in records:
        missing_refs = sorted(set(record["refs"]) - seen)
        if missing_refs:
            raise RegistryError(f"{record['id']}: unknown refs {missing_refs}")

    return records


def _workspace_path(workspace_root: Path, record_id: str, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise RegistryError(f"{record_id}: path must stay inside workspace")
    return workspace_root / relative


def validate_workspace(
    data: dict[str, Any], workspace_root: Path = WORKSPACE_ROOT
) -> list[dict[str, Any]]:
    """Validate claims that depend on files in this concrete workspace."""
    records = validate_registry(data)
    for record in records:
        record_id = record["id"]
        if "path" not in record:
            continue
        path = _workspace_path(workspace_root, record_id, record["path"])
        if not path.is_file():
            raise RegistryError(f"{record_id}: missing workspace file {record['path']}")
        if "sha256" in record:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != record["sha256"]:
                raise RegistryError(f"{record_id}: sha256 mismatch for {record['path']}")
        if record["kind"] == "TEST":
            source = path.read_text(encoding="utf-8")
            test_token = record.get("external_id", record["title"])
            if test_token not in source:
                raise RegistryError(
                    f"{record_id}: test token {test_token!r} not found in {record['path']}"
                )
    return records


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(data: dict[str, Any]) -> str:
    records = validate_registry(data)
    lines = [
        "# MASTER REGISTRY",
        "",
        "> Generirano iz `registry/master_registry.json`; ne uređivati ručno.",
        "",
        f"Registry verzija: `{data['registry_version']}`  ",
        f"Stanje na datum: `{data['as_of']}`  ",
        f"Broj zapisa: `{len(records)}`",
        "",
        "Četiri statusne osi su namjerno neovisne: dokaz, implementacija, validacija i certifikacija.",
        "",
    ]
    for kind in sorted(KINDS):
        group = sorted((r for r in records if r["kind"] == kind), key=lambda r: r["id"])
        if not group:
            continue
        lines.extend([
            f"## {kind}", "",
            "| ID | Naziv | Lifecycle | Dokaz | Implementacija | Validacija | Certifikacija | Veze |",
            "|---|---|---|---|---|---|---|---|",
        ])
        for record in group:
            refs = ", ".join(f"`{ref}`" for ref in record["refs"]) or "—"
            lines.append(
                "| {id} | {title} | `{life}` | `{ev}` | `{im}` | `{va}` | `{ce}` | {refs} |".format(
                    id=f"`{record['id']}`",
                    title=_escape(record["title"]), life=record["lifecycle"],
                    ev=record["evidence"]["state"], im=record["implementation"]["state"],
                    va=record["validation"]["state"], ce=record["certification"]["state"], refs=refs,
                )
            )
        lines.append("")
        for record in group:
            lines.extend([
                f"### {record['id']} — {record['title']}", "",
                record["summary"], "",
                f"- Dokaz: **{record['evidence']['state']}** — {record['evidence']['detail']}",
                f"- Implementacija: **{record['implementation']['state']}** — {record['implementation']['detail']}",
                f"- Validacija: **{record['validation']['state']}** — {record['validation']['detail']}",
                f"- Certifikacija: **{record['certification']['state']}** — {record['certification']['detail']}",
            ])
            if record.get("path"):
                lines.append(f"- Putanja: `{record['path']}`")
            if record.get("sha256"):
                lines.append(f"- SHA-256: `{record['sha256']}`")
            if record.get("command"):
                lines.append(f"- Naredba: `{record['command']}`")
            if "observations" in record:
                lines.append(
                    f"- Opažanja: `{record['observations']}` {record.get('observation_unit', '')}".rstrip()
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> None:
    data = load_registry(input_path)
    validate_workspace(data)
    output_path.write_text(render_markdown(data), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail if Markdown is stale")
    args = parser.parse_args(argv)
    try:
        data = load_registry(args.input)
        validate_workspace(data)
        rendered = render_markdown(data)
        if args.check:
            if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
                raise RegistryError(f"generated file is stale: {args.output}")
        else:
            args.output.write_text(rendered, encoding="utf-8")
    except (OSError, json.JSONDecodeError, RegistryError) as exc:
        print(f"registry error: {exc}", file=sys.stderr)
        return 1
    print(f"registry OK: {len(data['records'])} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())