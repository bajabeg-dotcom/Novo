"""Arhivira stare repozitorije u legacy/ bez gubitka evidencije.

Pravilo: kod, testovi i dokumentacija ulaze u git. Veliki binarni fajlovi
(PDF, korpus arhive, git pack, .deb) NE ulaze, ali se svaki zapisuje u
legacy/MANIFEST.md sa SHA-256, veličinom i izvorom — tako da se u svakom
trenutku može dokazati šta je postojalo i odakle se ponovo nabavlja.

Upotreba:
    python3 tools/archive_legacy.py /tmp/leg legacy --max-bytes 2097152
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from typing import Any

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"}
SKIP_SUFFIX = (".pyc", ".pyo")


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive(src_root: str, dst_root: str, max_bytes: int) -> dict[str, Any]:
    repos: dict[str, Any] = {}

    for repo in sorted(os.listdir(src_root)):
        repo_path = os.path.join(src_root, repo)
        if not os.path.isdir(repo_path):
            continue

        copied = 0
        copied_bytes = 0
        excluded: list[dict[str, Any]] = []

        for base, dirs, names in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in sorted(names):
                if name.endswith(SKIP_SUFFIX):
                    continue
                source = os.path.join(base, name)
                if os.path.islink(source):
                    continue
                rel = os.path.relpath(source, repo_path)
                size = os.path.getsize(source)

                if size > max_bytes:
                    excluded.append(
                        {
                            "path": rel.replace(os.sep, "/"),
                            "size": size,
                            "sha256": sha256(source),
                        }
                    )
                    continue

                target = os.path.join(dst_root, repo, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(source, target)
                copied += 1
                copied_bytes += size

        repos[repo] = {
            "files_archived": copied,
            "bytes_archived": copied_bytes,
            "excluded": sorted(excluded, key=lambda e: -e["size"]),
            "excluded_count": len(excluded),
            "excluded_bytes": sum(e["size"] for e in excluded),
        }

    return repos


DESCRIPTIONS = {
    "a": "Prva generacija: midi_optimizer CLI/GUI/core, forenzicki izvjestaji.",
    "beg": "korg_pa800_optimizer + x10_think_midi + factory_intelligence.",
    "DNA": "song_midi_optimizer i song_midi_optimizer_pro skripte.",
    "Factory": "GM->RX Studio: rxoptimizer (40 modula), 25 DNA baza, web GUI.",
    "Jap": "python-midi-enhancer: 30 modula M01-M10/K01-K03, 28 testova, K01 registar.",
}

SOURCES = {
    "a": "https://github.com/bajabeg-dotcom/a",
    "beg": "https://github.com/bajabeg-dotcom/beg",
    "DNA": "https://github.com/bajabeg-dotcom/DNA",
    "Factory": "https://github.com/bajabeg-dotcom/Factory",
    "Jap": "https://github.com/bajabeg-dotcom/Jap",
}


def write_manifest(repos: dict[str, Any], dst_root: str) -> None:
    lines: list[str] = []
    lines.append("# legacy/ — arhiva prethodnih repozitorija\n")
    lines.append(
        "Ovaj folder je **nepromjenjiv**. Sluzi kao dokaz da nista iz ranijeg\n"
        "rada nije izgubljeno pri konsolidaciji na v0.28.0.\n"
    )
    lines.append(
        "Kod, testovi i dokumentacija su arhivirani u git. Veliki binarni\n"
        "fajlovi nisu — ali je svaki zapisan ispod sa SHA-256, pa se moze\n"
        "provjeriti i ponovo nabaviti iz izvornog repozitorija.\n"
    )

    total_files = sum(r["files_archived"] for r in repos.values())
    total_bytes = sum(r["bytes_archived"] for r in repos.values())
    total_excluded = sum(r["excluded_count"] for r in repos.values())
    total_excluded_bytes = sum(r["excluded_bytes"] for r in repos.values())

    lines.append("## Sazetak\n")
    lines.append("| Repo | Arhivirano | Velicina | Izuzeto | Izuzeta velicina |")
    lines.append("|---|---|---|---|---|")
    for name in sorted(repos):
        r = repos[name]
        lines.append(
            f"| `{name}` | {r['files_archived']} | "
            f"{r['bytes_archived'] / 1048576:.1f} MB | "
            f"{r['excluded_count']} | {r['excluded_bytes'] / 1048576:.1f} MB |"
        )
    lines.append(
        f"| **ukupno** | **{total_files}** | "
        f"**{total_bytes / 1048576:.1f} MB** | "
        f"**{total_excluded}** | **{total_excluded_bytes / 1048576:.1f} MB** |\n"
    )

    lines.append("## Sadrzaj po repozitoriju\n")
    for name in sorted(repos):
        r = repos[name]
        lines.append(f"### `{name}`\n")
        lines.append(f"{DESCRIPTIONS.get(name, '')}\n")
        lines.append(f"Izvor: {SOURCES.get(name, '-')}\n")
        if r["excluded"]:
            lines.append(
                f"Izuzeto {r['excluded_count']} velikih fajlova "
                f"({r['excluded_bytes'] / 1048576:.1f} MB):\n"
            )
            lines.append("| Fajl | Velicina | SHA-256 |")
            lines.append("|---|---|---|")
            for item in r["excluded"]:
                lines.append(
                    f"| `{item['path']}` | {item['size'] / 1048576:.1f} MB | "
                    f"`{item['sha256']}` |"
                )
            lines.append("")
        else:
            lines.append("Nista nije izuzeto.\n")

    os.makedirs(dst_root, exist_ok=True)
    with open(os.path.join(dst_root, "MANIFEST.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    with open(
        os.path.join(dst_root, "manifest.json"), "w", encoding="utf-8"
    ) as handle:
        json.dump(repos, handle, indent=1, ensure_ascii=False, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Arhiviraj legacy repozitorije")
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024)
    args = parser.parse_args()

    repos = archive(args.source, args.destination, args.max_bytes)
    write_manifest(repos, args.destination)

    for name in sorted(repos):
        r = repos[name]
        print(
            f"{name:10s} arhivirano={r['files_archived']:5d} "
            f"({r['bytes_archived'] / 1048576:6.1f} MB)  "
            f"izuzeto={r['excluded_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
