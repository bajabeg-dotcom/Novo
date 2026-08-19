from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ARTIFACT_MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    artifact_type: str
    relative_path: str
    sha256: str
    size: int
    schema_version: int | None = None
    status: str = "candidate"


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    schema_version: int
    artifacts: tuple[ArtifactRecord, ...]

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"


@dataclass(frozen=True, slots=True)
class ArtifactAudit:
    checked: int
    valid: int
    missing: tuple[str, ...]
    mismatched: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.mismatched


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(root: Path, specifications: tuple[tuple[str, str, Path, int | None, str], ...]) -> ArtifactManifest:
    records = []
    root = root.resolve()
    for artifact_id, artifact_type, path, schema_version, status in specifications:
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise ValueError(f"artifact must be inside resource root: {resolved}") from error
        if not resolved.is_file():
            raise FileNotFoundError(f"artifact does not exist: {resolved}")
        records.append(ArtifactRecord(artifact_id, artifact_type, relative.as_posix(),
                                      file_sha256(resolved), resolved.stat().st_size,
                                      schema_version, status))
    return ArtifactManifest(ARTIFACT_MANIFEST_SCHEMA_VERSION, tuple(records))


def load_manifest(path: Path) -> ArtifactManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != ARTIFACT_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported artifact manifest schema")
    return ArtifactManifest(raw["schema_version"], tuple(ArtifactRecord(**item) for item in raw.get("artifacts", [])))


def write_manifest(manifest: ArtifactManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(manifest.dumps(), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def audit_manifest(manifest: ArtifactManifest, root: Path) -> ArtifactAudit:
    missing, mismatched = [], []
    valid = 0
    for record in manifest.artifacts:
        path = root / Path(record.relative_path)
        if not path.is_file():
            missing.append(record.artifact_id)
        elif path.stat().st_size != record.size or file_sha256(path) != record.sha256:
            mismatched.append(record.artifact_id)
        else:
            valid += 1
    return ArtifactAudit(len(manifest.artifacts), valid, tuple(missing), tuple(mismatched))
