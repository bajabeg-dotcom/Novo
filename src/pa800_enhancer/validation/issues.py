from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: Severity
    track_index: int | None = None
    tick: int | None = None

    @property
    def is_critical(self) -> bool:
        return self.severity is Severity.CRITICAL

    @property
    def blocks_export(self) -> bool:
        return self.severity in (Severity.ERROR, Severity.CRITICAL)
