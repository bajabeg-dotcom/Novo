from dataclasses import dataclass, field
from pathlib import Path
from .resources import ResourceResolver


@dataclass(frozen=True, slots=True)
class AppConfig:
    project_suffix: str = ".pa800-project.json"
    default_ppq: int = 384
    max_file_size: int = 64 * 1024 * 1024
    max_tracks: int = 1024
    max_chunks: int = 4096
    max_chunk_size: int = 32 * 1024 * 1024
    max_events_per_track: int = 2_000_000
    autosave_versions: int = 5
    profile_directory: Path = field(
        default_factory=lambda: (
            ResourceResolver().find(Path("profiles"), required=False)
            or ResourceResolver().locations().profiles
        )
    )
