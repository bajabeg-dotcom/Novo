from dataclasses import dataclass, field
from dataclasses import asdict
import json
from pathlib import Path


@dataclass(slots=True)
class ExportReport:
    input_sha256: str | None
    output_sha256: str
    output_path: str
    profile_id: str
    export_mode: str
    applied_changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def write_json(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")