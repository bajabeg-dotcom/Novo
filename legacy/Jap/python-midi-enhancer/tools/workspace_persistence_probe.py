#!/usr/bin/env python3
"""Verify that a checkpointed Git commit and its required files persisted.

A checkpoint intentionally references an earlier commit.  The checkpoint can
then be committed in a child commit without creating a circular self-hash.  A
later workspace session proves persistence by verifying that the referenced
commit still exists, is an ancestor of HEAD, and contains the exact Python and
test artifacts recorded in the checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = ROOT / "audit" / "PERSISTENCE_CHECKPOINT.json"


class PersistenceError(RuntimeError):
    """Raised when a persistence checkpoint does not verify."""


def _git(root: Path, *args: str, text: bool = True) -> str | bytes:
    process = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=text, check=False
    )
    if process.returncode:
        stderr = process.stderr.strip() if text else process.stderr.decode(errors="replace").strip()
        raise PersistenceError(f"git {' '.join(args)} failed: {stderr}")
    return process.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_checkpoint(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PersistenceError(f"cannot load checkpoint {path}: {exc}") from exc
    required = {"schema_version", "token", "created_at", "expected_commit", "required_files"}
    if not isinstance(data, dict) or set(data) != required:
        raise PersistenceError(f"checkpoint keys must be exactly {sorted(required)}")
    if data["schema_version"] != "1.0.0":
        raise PersistenceError("unsupported checkpoint schema")
    if not isinstance(data["required_files"], dict) or not data["required_files"]:
        raise PersistenceError("required_files must be a non-empty object")
    return data


def verify_checkpoint(path: Path = DEFAULT_CHECKPOINT, root: Path = ROOT) -> dict[str, Any]:
    data = load_checkpoint(path)
    expected = str(data["expected_commit"])
    _git(root, "cat-file", "-e", f"{expected}^{{commit}}")
    process = subprocess.run(
        ["git", "merge-base", "--is-ancestor", expected, "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise PersistenceError(f"checkpoint commit {expected} is not an ancestor of HEAD")

    verified: list[dict[str, str]] = []
    for relative, expected_hash in sorted(data["required_files"].items()):
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise PersistenceError(f"unsafe required path: {relative}")
        committed = _git(root, "show", f"{expected}:{relative}", text=False)
        assert isinstance(committed, bytes)
        committed_hash = _sha256(committed)
        if committed_hash != expected_hash:
            raise PersistenceError(
                f"checkpoint hash mismatch for committed {relative}: {committed_hash} != {expected_hash}"
            )
        worktree_path = root / relative
        if not worktree_path.is_file():
            raise PersistenceError(f"required worktree file is missing: {relative}")
        worktree_hash = _sha256(worktree_path.read_bytes())
        if worktree_hash != expected_hash:
            raise PersistenceError(
                f"worktree hash mismatch for {relative}: {worktree_hash} != {expected_hash}"
            )
        verified.append({"path": relative, "sha256": expected_hash})

    head = str(_git(root, "rev-parse", "HEAD")).strip()
    return {
        "status": "PASS",
        "token": data["token"],
        "checkpoint_commit": expected,
        "current_head": head,
        "verified_files": verified,
        "scope_note": (
            "This verifies commit/file persistence only. Cross-message persistence is proven "
            "only when this command succeeds in a later user turn or reloaded workspace."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = verify_checkpoint(args.checkpoint, args.root)
    except PersistenceError as exc:
        print(f"persistence verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
