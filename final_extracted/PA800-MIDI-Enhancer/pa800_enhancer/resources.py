from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


RESOURCE_ENVIRONMENT_VARIABLE = "PA800_ENHANCER_HOME"


@dataclass(frozen=True, slots=True)
class ResourceLocations:
    root: Path
    data: Path
    references: Path
    models: Path
    reports: Path
    generated: Path
    profiles: Path

    @property
    def database(self) -> Path:
        return self.data / "pa800-enhancer.db"

    @property
    def performance_catalog(self) -> Path:
        return self.references / "performance-reference-catalog.json"

    @property
    def standard_model(self) -> Path:
        return self.models / "midi-standard.pt"

    @property
    def manifest(self) -> Path:
        return self.data / "artifact-manifest.json"


class ResourceResolver:
    """Resolve application resources without assuming the process working directory."""

    def __init__(self, explicit_root: Path | None = None) -> None:
        self.explicit_root = explicit_root

    def candidate_roots(self) -> tuple[Path, ...]:
        candidates: list[Path] = []
        if self.explicit_root is not None:
            candidates.append(self.explicit_root)
        configured = os.environ.get(RESOURCE_ENVIRONMENT_VARIABLE)
        if configured:
            candidates.append(Path(configured))
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "PA800MidiEnhancer")
        package_root = Path(__file__).resolve().parent.parent
        candidates.extend((package_root, Path.cwd()))
        unique: list[Path] = []
        for candidate in candidates:
            resolved = candidate.expanduser().resolve()
            if resolved not in unique:
                unique.append(resolved)
        return tuple(unique)

    def resolve_root(self, *, require_existing: bool = False) -> Path:
        candidates = self.candidate_roots()
        if require_existing:
            for candidate in candidates:
                if (candidate / "data").is_dir() or (candidate / "profiles").is_dir():
                    return candidate
            searched = ", ".join(str(item) for item in candidates)
            raise FileNotFoundError(f"no PA800 resource root found; searched: {searched}")
        return candidates[0]

    def locations(self, *, create: bool = False, require_existing: bool = False) -> ResourceLocations:
        root = self.resolve_root(require_existing=require_existing)
        data = root / "data"
        locations = ResourceLocations(
            root, data, data / "reference", data / "models", data / "reports",
            data / "generated", root / "profiles",
        )
        if create:
            for directory in (locations.data, locations.references, locations.models,
                              locations.reports, locations.generated, locations.profiles):
                directory.mkdir(parents=True, exist_ok=True)
        return locations

    def find(self, relative: Path, *, required: bool = True) -> Path | None:
        if relative.is_absolute():
            if relative.exists() or not required:
                return relative
            raise FileNotFoundError(f"resource does not exist: {relative}")
        searched = []
        for root in self.candidate_roots():
            candidate = root / relative
            searched.append(candidate)
            if candidate.exists():
                return candidate
        if required:
            raise FileNotFoundError(
                f"resource {relative} was not found; searched: "
                + ", ".join(str(item) for item in searched)
            )
        return None
