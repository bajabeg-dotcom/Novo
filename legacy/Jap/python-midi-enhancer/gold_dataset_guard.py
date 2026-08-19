"""Deterministic Factory-training / Gold-evaluation contamination guard.

The DNA package contains a byte-identical Factory archive. That nested archive
is excluded as contamination. Gold MIDI files are validated and deduplicated by
content SHA-256; no heuristic label or M07 probability calibration is claimed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from style_loader import StandardMidiLoader, sha256_path

FACTORY_SHA256 = "ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e"
DNA_SHA256 = "125f4486625db44f7cdd49bd670aff252a961c88ea14741ec970ec3ae5eec85a"
GOLD_NESTED_SHA256 = "da7d5dd6fac74d4d6a35d5d3bdacc4cabe988873ec0472529e9c6ef2a9b77e5e"


class GoldDatasetError(ValueError):
    """Raised when dataset provenance or contamination invariants fail."""


@dataclass(frozen=True, slots=True)
class DatasetFile:
    member_name: str
    sha256: str
    size_bytes: int
    midi_format: int
    track_count: int
    division: int
    event_count: int
    note_on_count: int


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    sha256: str
    canonical_member: str
    duplicate_members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExcludedContainer:
    outer_member: str
    sha256: str
    reason: str


@dataclass(frozen=True, slots=True)
class GoldDatasetManifest:
    schema_version: str
    factory_source_path: str
    factory_source_sha256: str
    dna_source_path: str
    dna_source_sha256: str
    gold_nested_member: str
    gold_nested_sha256: str
    factory_file_count: int
    factory_unique_hash_count: int
    factory_duplicate_groups: int
    gold_file_count: int
    gold_unique_file_count: int
    gold_duplicate_groups: tuple[DuplicateGroup, ...]
    cross_source_duplicate_hashes: tuple[str, ...]
    excluded_containers: tuple[ExcludedContainer, ...]
    train_source: str
    evaluation_source: str
    evaluation_files: tuple[DatasetFile, ...]
    evaluation_format_counts: tuple[tuple[int, int], ...]
    evaluation_division_counts: tuple[tuple[int, int], ...]
    evaluation_event_count: int
    evaluation_note_on_count: int
    contamination_status: str
    split_status: str
    m07_calibration_status: str
    m07_calibration_reason: str
    safety_policy: str


class GoldDatasetGuard:
    def __init__(self) -> None:
        self.loader = StandardMidiLoader()

    def build(
        self,
        factory_archive: str | Path,
        dna_archive: str | Path,
    ) -> GoldDatasetManifest:
        factory_path = Path(factory_archive)
        dna_path = Path(dna_archive)
        factory_before = sha256_path(factory_path)
        dna_before = sha256_path(dna_path)
        if factory_before != FACTORY_SHA256:
            raise GoldDatasetError(f"Factory archive SHA-256 mismatch: {factory_before}")
        if dna_before != DNA_SHA256:
            raise GoldDatasetError(f"DNA archive SHA-256 mismatch: {dna_before}")

        factory_hashes: defaultdict[str, list[str]] = defaultdict(list)
        with ZipFile(factory_path) as factory:
            validate_safe_zip_names(factory)
            factory_infos = [
                info for info in factory.infolist()
                if not info.is_dir() and info.filename.lower().endswith((".mid", ".midi"))
            ]
            for info in factory_infos:
                digest = hashlib.sha256(factory.read(info)).hexdigest()
                factory_hashes[digest].append(info.filename)

        excluded: list[ExcludedContainer] = []
        gold_bytes: bytes | None = None
        with ZipFile(dna_path) as outer:
            validate_safe_zip_names(outer)
            for info in outer.infolist():
                if info.is_dir():
                    continue
                data = outer.read(info)
                digest = hashlib.sha256(data).hexdigest()
                if digest == FACTORY_SHA256:
                    excluded.append(ExcludedContainer(
                        outer_member=info.filename,
                        sha256=digest,
                        reason="EXACT_FACTORY_ARCHIVE_CONTAMINATION_EXCLUDED",
                    ))
                elif digest == GOLD_NESTED_SHA256 and info.filename == "Gold DNA.zip":
                    gold_bytes = data
                else:
                    raise GoldDatasetError(
                        f"unknown DNA outer member or hash: {info.filename} {digest}"
                    )
        if gold_bytes is None:
            raise GoldDatasetError("Gold DNA.zip with registered hash was not found")
        if len(excluded) != 1:
            raise GoldDatasetError(
                f"expected one exact Factory container exclusion, found {len(excluded)}"
            )

        by_hash: defaultdict[str, list[DatasetFile]] = defaultdict(list)
        try:
            with ZipFile(io.BytesIO(gold_bytes)) as gold:
                validate_safe_zip_names(gold)
                infos = [
                    info for info in gold.infolist()
                    if not info.is_dir() and info.filename.lower().endswith((".mid", ".midi"))
                ]
                for info in infos:
                    data = gold.read(info)
                    model = self.loader.load_bytes(data, source_name=info.filename)
                    events = sum(len(track.events) for track in model.tracks)
                    note_ons = sum(
                        event.is_note_on
                        for track in model.tracks
                        for event in track.events
                    )
                    record = DatasetFile(
                        member_name=info.filename,
                        sha256=model.sha256,
                        size_bytes=len(data),
                        midi_format=model.format,
                        track_count=model.declared_track_count,
                        division=model.division,
                        event_count=events,
                        note_on_count=note_ons,
                    )
                    by_hash[model.sha256].append(record)
        except BadZipFile as exc:
            raise GoldDatasetError(f"invalid nested Gold ZIP: {exc}") from exc

        canonical: list[DatasetFile] = []
        duplicate_groups: list[DuplicateGroup] = []
        for digest in sorted(by_hash):
            records = sorted(by_hash[digest], key=lambda item: item.member_name)
            canonical.append(records[0])
            if len(records) > 1:
                duplicate_groups.append(DuplicateGroup(
                    sha256=digest,
                    canonical_member=records[0].member_name,
                    duplicate_members=tuple(item.member_name for item in records[1:]),
                ))
        canonical.sort(key=lambda item: item.member_name)
        cross = tuple(sorted(set(by_hash) & set(factory_hashes)))
        if cross:
            raise GoldDatasetError(
                f"Gold evaluation contamination detected: {len(cross)} Factory hashes"
            )

        formats = Counter(item.midi_format for item in canonical)
        divisions = Counter(item.division for item in canonical)
        factory_duplicate_groups = sum(
            len(members) > 1 for members in factory_hashes.values()
        )
        manifest = GoldDatasetManifest(
            schema_version="1.0.0",
            factory_source_path=str(factory_path),
            factory_source_sha256=factory_before,
            dna_source_path=str(dna_path),
            dna_source_sha256=dna_before,
            gold_nested_member="Gold DNA.zip",
            gold_nested_sha256=hashlib.sha256(gold_bytes).hexdigest(),
            factory_file_count=len(factory_infos),
            factory_unique_hash_count=len(factory_hashes),
            factory_duplicate_groups=factory_duplicate_groups,
            gold_file_count=sum(len(items) for items in by_hash.values()),
            gold_unique_file_count=len(canonical),
            gold_duplicate_groups=tuple(duplicate_groups),
            cross_source_duplicate_hashes=cross,
            excluded_containers=tuple(excluded),
            train_source="FACTORY_STYLE_REFERENCE_ONLY",
            evaluation_source="GOLD_DNA_DEDUPLICATED_ONLY",
            evaluation_files=tuple(canonical),
            evaluation_format_counts=tuple(sorted(formats.items())),
            evaluation_division_counts=tuple(sorted(divisions.items())),
            evaluation_event_count=sum(item.event_count for item in canonical),
            evaluation_note_on_count=sum(item.note_on_count for item in canonical),
            contamination_status="PASS",
            split_status="PASS_SOURCE_DISJOINT",
            m07_calibration_status="BLOCKED",
            m07_calibration_reason=(
                "Gold MIDI files have no independently human-verified per-part role labels; "
                "heuristic confidence cannot be converted to statistical probability."
            ),
            safety_policy="EVALUATION_ONLY_NO_PROFILE_MERGE_NO_SUGGEST_AUTHORIZATION",
        )
        if sha256_path(factory_path) != factory_before or sha256_path(dna_path) != dna_before:
            raise GoldDatasetError("source archive changed during dataset guard build")
        return manifest


def validate_safe_zip_names(archive: ZipFile) -> None:
    for info in archive.infolist():
        normalized = info.filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts:
            raise GoldDatasetError(f"unsafe ZIP member path: {info.filename}")


def manifest_to_dict(manifest: GoldDatasetManifest) -> dict:
    return asdict(manifest)


def render_manifest(manifest: GoldDatasetManifest) -> str:
    return json.dumps(manifest_to_dict(manifest), ensure_ascii=False, indent=2) + "\n"


def manifest_digest(manifest: GoldDatasetManifest) -> str:
    return hashlib.sha256(render_manifest(manifest).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("factory_archive", type=Path)
    parser.add_argument("dna_archive", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    manifest = GoldDatasetGuard().build(args.factory_archive, args.dna_archive)
    rendered = render_manifest(manifest)
    if args.json_output:
        if args.json_output.resolve() in {
            args.factory_archive.resolve(), args.dna_archive.resolve()
        }:
            raise GoldDatasetError("manifest output cannot overwrite source archive")
        args.json_output.write_text(rendered, encoding="utf-8")
    else:
        print(json.dumps({
            "factory_files": manifest.factory_file_count,
            "factory_unique_hashes": manifest.factory_unique_hash_count,
            "gold_files": manifest.gold_file_count,
            "gold_unique_files": manifest.gold_unique_file_count,
            "cross_source_duplicates": len(manifest.cross_source_duplicate_hashes),
            "excluded_containers": len(manifest.excluded_containers),
            "m07_calibration_status": manifest.m07_calibration_status,
            "digest": manifest_digest(manifest),
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
