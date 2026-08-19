from __future__ import annotations

from dataclasses import dataclass

from ..domain.song import Song
from ..analysis.notes import pair_notes
from ..domain.changes import Change, ChangeSet, RiskLevel
from ..validation.issues import ValidationIssue
from .articulation import AutomaticArticulationResult, plan_articulations
from .base import OptimizationContext
from .engine import ChangeEngine, clone_song, song_revision
from .velocity import AutomaticVelocityResult, shape_velocity_automatically


@dataclass(frozen=True, slots=True)
class PerformancePipelineResult:
    source_revision: str
    velocity_revision: str
    final_revision: str
    repairs: ChangeSet
    velocity: AutomaticVelocityResult
    articulation: AutomaticArticulationResult
    projected_song: Song
    validation_issues: tuple[ValidationIssue, ...]
    blockers: tuple[str, ...]


def run_performance_pipeline(context: OptimizationContext, catalog, validator) -> PerformancePipelineResult:
    """Project velocity then articulation sequentially without mutating input."""
    source_revision = song_revision(context.song)
    projected = clone_song(context.song)
    repairs = _build_zero_duration_repairs(projected)
    if repairs.changes:
        repairs.approve_all()
        projected = ChangeEngine().apply(projected, repairs)
    velocity_context = OptimizationContext(projected, context.device_profile, context.seed)
    velocity = shape_velocity_automatically(velocity_context, catalog)
    if velocity.changes.changes:
        velocity.changes.approve_all()
        projected = ChangeEngine().apply(projected, velocity.changes)
    velocity_revision = song_revision(projected)

    articulation_context = OptimizationContext(projected, context.device_profile, context.seed)
    articulation = plan_articulations(articulation_context, catalog)
    if articulation.changes.changes:
        articulation.changes.approve_all()
        projected = ChangeEngine().apply(projected, articulation.changes)
    issues = tuple(validator.validate(projected))
    blockers = tuple(issue.message for issue in issues if issue.blocks_export)
    return PerformancePipelineResult(
        source_revision,
        velocity_revision,
        song_revision(projected),
        repairs,
        velocity,
        articulation,
        projected,
        issues,
        blockers,
    )


def _build_zero_duration_repairs(song: Song) -> ChangeSet:
    changes: list[Change] = []
    event_map = {event.event_id: event for track in song.tracks for event in track.events}
    required_track_end: dict[int, int] = {}
    for note in pair_notes(song)[0]:
        if note.end_tick > note.start_tick or note.ambiguous_pairing:
            continue
        changes.append(Change(
            f"performance:minimum-duration:{note.off_event_id}",
            "performance_repair",
            "give an unambiguous zero-duration note a one-tick duration",
            RiskLevel.MEDIUM,
            note.off_event_id,
            "absolute_tick",
            note.end_tick,
            note.start_tick + 1,
        ))
        off_event = event_map[note.off_event_id]
        required_track_end[off_event.track_index] = max(
            required_track_end.get(off_event.track_index, 0), note.start_tick + 1
        )
    for track in song.tracks:
        required = required_track_end.get(track.index)
        if required is None:
            continue
        eot = next((event for event in track.events if event.meta_type == 0x2F), None)
        if eot is not None and eot.absolute_tick < required:
            changes.append(Change(
                f"performance:extend-eot:{eot.event_id}",
                "performance_repair",
                "keep End of Track after repaired note endings",
                RiskLevel.MEDIUM,
                eot.event_id,
                "absolute_tick",
                eot.absolute_tick,
                required,
            ))
    return ChangeSet(changes)
