from dataclasses import dataclass, field
from datetime import datetime, timezone


CURRENT_SCHEMA_VERSION = 2


@dataclass(slots=True)
class Project:
    schema_version: int = CURRENT_SCHEMA_VERSION
    source_path: str | None = None
    source_sha256: str | None = None
    profile_id: str = "pa800-default"
    random_seed: int = 0
    approved_change_ids: list[str] = field(default_factory=list)
    rejected_change_ids: list[str] = field(default_factory=list)
    locked_event_ids: list[str] = field(default_factory=list)
    locked_track_indices: list[int] = field(default_factory=list)
    command_history: dict[str, object] = field(default_factory=dict)
    review_markers: list[dict[str, object]] = field(default_factory=list)
    profile_snapshot: dict[str, object] | None = None
    ui_state: dict[str, object] = field(default_factory=dict)
    selected_rhythm_profile: str | None = None
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extensions: dict[str, object] = field(default_factory=dict, repr=False)