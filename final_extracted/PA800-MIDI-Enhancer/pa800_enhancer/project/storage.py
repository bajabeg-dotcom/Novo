import json
import os
from copy import deepcopy
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .model import CURRENT_SCHEMA_VERSION, Project


class ProjectFormatError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RecoveryCandidate:
    path: Path
    project: Project
    modified_at: float
    newer_than_manual_save: bool


class ProjectStorage:
    def save(self, project: Project, path: Path) -> None:
        project.updated_at = datetime.now(timezone.utc).isoformat()
        self._atomic_write(path, self._project_data(project))

    def load(self, path: Path) -> Project:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProjectFormatError(f"cannot read project {path}: {error}") from error
        if not isinstance(data, dict):
            raise ProjectFormatError("project root must be a JSON object")
        migrated = self._migrate(data)
        field_names = set(Project.__dataclass_fields__) - {"extensions"}
        known = {key: value for key, value in migrated.items() if key in field_names}
        extensions = {key: value for key, value in migrated.items() if key not in field_names}
        try:
            return Project(**known, extensions=extensions)
        except TypeError as error:
            raise ProjectFormatError(f"invalid project fields: {error}") from error

    def autosave(self, project: Project, path: Path, generations: int = 3) -> Path:
        if generations < 1:
            raise ValueError("generations must be at least 1")
        for index in range(generations, 1, -1):
            older = self.autosave_path(path, index - 1)
            newer = self.autosave_path(path, index)
            if older.exists():
                older.replace(newer)
        target = self.autosave_path(path, 1)
        project.updated_at = datetime.now(timezone.utc).isoformat()
        self._atomic_write(target, self._project_data(project))
        return target

    def recovery_candidates(self, path: Path) -> list[RecoveryCandidate]:
        manual_mtime = path.stat().st_mtime if path.exists() else float("-inf")
        candidates: list[RecoveryCandidate] = []
        for candidate_path in path.parent.glob(f"{path.name}.autosave.*"):
            try:
                project = self.load(candidate_path)
                modified_at = candidate_path.stat().st_mtime
            except (OSError, ProjectFormatError):
                continue
            candidates.append(
                RecoveryCandidate(
                    candidate_path,
                    project,
                    modified_at,
                    modified_at > manual_mtime,
                )
            )
        return sorted(candidates, key=lambda item: item.modified_at, reverse=True)

    def recover_latest(self, path: Path, output: Path | None = None) -> RecoveryCandidate:
        candidates = self.recovery_candidates(path)
        if not candidates:
            raise FileNotFoundError(f"no valid autosave exists for {path}")
        candidate = candidates[0]
        self.save(candidate.project, output or path)
        return candidate

    @staticmethod
    def autosave_path(path: Path, generation: int) -> Path:
        return path.with_name(f"{path.name}.autosave.{generation}")

    def _atomic_write(self, path: Path, data: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.tmp")
        encoded = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _project_data(project: Project) -> dict[str, object]:
        data = asdict(project)
        extensions = data.pop("extensions", {})
        if isinstance(extensions, dict):
            for key, value in extensions.items():
                data.setdefault(key, value)
        data["schema_version"] = CURRENT_SCHEMA_VERSION
        return data

    def _migrate(self, source: dict[str, object]) -> dict[str, object]:
        data = deepcopy(source)
        version = data.get("schema_version", 1)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ProjectFormatError("schema_version must be a positive integer")
        if version > CURRENT_SCHEMA_VERSION:
            raise ProjectFormatError(
                f"project schema {version} is newer than supported schema {CURRENT_SCHEMA_VERSION}"
            )
        while version < CURRENT_SCHEMA_VERSION:
            if version == 1:
                data = self._migrate_v1_to_v2(data)
            version += 1
        data["schema_version"] = CURRENT_SCHEMA_VERSION
        return data

    @staticmethod
    def _migrate_v1_to_v2(data: dict[str, object]) -> dict[str, object]:
        migrated = dict(data)
        event_locks = migrated.get("locked_event_ids", [])
        migrated.setdefault(
            "command_history",
            {
                "applied": [],
                "redo": [],
                "checkpoints": {},
                "locked_event_ids": list(event_locks) if isinstance(event_locks, list) else [],
                "locked_track_indices": [],
            },
        )
        migrated.setdefault("rejected_change_ids", [])
        migrated.setdefault("locked_track_indices", [])
        migrated.setdefault("review_markers", [])
        migrated.setdefault("profile_snapshot", None)
        migrated.setdefault("ui_state", {})
        migrated.setdefault("updated_at", migrated.get("created_at", ""))
        migrated["schema_version"] = 2
        return migrated