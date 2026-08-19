from ..analysis.notes import pair_notes
from ..domain.changes import Change, ChangeSet, RiskLevel
from .base import OptimizationContext


class QuantizeModule:
    name = "quantization"

    def __init__(self, division: int = 16, strength: float = 1.0) -> None:
        if division <= 0 or not 0 <= strength <= 1:
            raise ValueError("invalid quantization settings")
        self.division = division
        self.strength = strength

    def suggest(self, context: OptimizationContext) -> ChangeSet:
        ppq = context.song.header.ppq
        if not ppq:
            return ChangeSet()
        grid = max(1, round(ppq * 4 / self.division))
        notes, _ = pair_notes(context.song)
        changes: list[Change] = []
        for index, note in enumerate(notes):
            target = round(note.start_tick / grid) * grid
            new_start = round(note.start_tick + (target - note.start_tick) * self.strength)
            shift = new_start - note.start_tick
            if not shift:
                continue
            group_id = f"quantize:{index}"
            changes.extend(
                (
                    Change(f"quantize:{index}:on", self.name, f"align note start to 1/{self.division} grid", RiskLevel.MEDIUM, note.on_event_id, "absolute_tick", note.start_tick, new_start, group_id=group_id),
                    Change(f"quantize:{index}:off", self.name, "preserve note duration while moving start", RiskLevel.MEDIUM, note.off_event_id, "absolute_tick", note.end_tick, max(new_start + 1, note.end_tick + shift), group_id=group_id),
                )
            )
        return ChangeSet(changes)