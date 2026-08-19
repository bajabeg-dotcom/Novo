from dataclasses import dataclass
from typing import Protocol

from ..domain.changes import ChangeSet
from ..domain.song import Song
from ..profiles.models import DeviceProfile


@dataclass(slots=True)
class OptimizationContext:
    song: Song
    device_profile: DeviceProfile
    seed: int = 0


class OptimizationModule(Protocol):
    name: str

    def suggest(self, context: OptimizationContext) -> ChangeSet: ...
