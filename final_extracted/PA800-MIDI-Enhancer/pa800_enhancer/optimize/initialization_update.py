from dataclasses import dataclass

from ..analysis.initialization import InitializationAnalysis, analyze_initialization_bar
from ..domain.changes import Change, ChangeGroup, ChangeTransaction, RiskLevel
from ..domain.song import Song
from .engine import ChangeEngine, song_revision


ALLOWED_CONTROLLERS = {0, 32, 7, 10, 11, 91, 92, 93, 94, 95}


@dataclass(frozen=True, slots=True)
class InitializationChannelTarget:
    channel: int
    program: int | None = None
    controllers: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class InitializationValueUpdate:
    channel: int
    role: str
    controller: int | None
    event_id: str
    old_value: int
    new_value: int


@dataclass(frozen=True, slots=True)
class InitializationUpdatePlan:
    status: str
    source_revision: str
    analysis: InitializationAnalysis
    targets: tuple[InitializationChannelTarget, ...]
    updates: tuple[InitializationValueUpdate, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InitializationUpdatePreview:
    original_revision: str
    projected_revision: str
    original_event_count: int
    projected_event_count: int
    updates: tuple[InitializationValueUpdate, ...]


def plan_initialization_update(
    song: Song,
    targets: tuple[InitializationChannelTarget, ...],
) -> InitializationUpdatePlan:
    analysis = analyze_initialization_bar(song)
    blockers = list(analysis.blockers)
    warnings = list(analysis.warnings)
    revision = song_revision(song)
    if analysis.status != "probable":
        blockers.append(
            "initialization update requires a probable existing initialization bar"
        )
    if not targets:
        blockers.append("at least one channel target is required")

    event_map = {
        event.event_id: event for track in song.tracks for event in track.events
    }
    by_key: dict[tuple[int, str, int | None], list[str]] = {}
    for event in analysis.initialization_events:
        if event.channel is None:
            continue
        key = (event.channel, event.role, event.controller)
        by_key.setdefault(key, []).append(event.event_id)

    updates: list[InitializationValueUpdate] = []
    seen_channels: set[int] = set()
    seen_targets: set[tuple[int, str, int | None]] = set()
    for target in targets:
        if not 1 <= target.channel <= 16:
            blockers.append(f"channel {target.channel} is outside 1--16")
            continue
        if target.channel in seen_channels:
            blockers.append(f"channel {target.channel} appears more than once in the request")
            continue
        seen_channels.add(target.channel)
        requests: list[tuple[str, int | None, int]] = []
        if target.program is not None:
            requests.append(("program", None, _midi_value(target.program, "program")))
        controller_numbers: set[int] = set()
        for controller, value in target.controllers:
            if controller not in ALLOWED_CONTROLLERS:
                blockers.append(f"CC{controller} is not an allowed initialization target")
                continue
            if controller in controller_numbers:
                blockers.append(f"CC{controller} is repeated for channel {target.channel}")
                continue
            controller_numbers.add(controller)
            requests.append((_controller_role(controller), controller, _midi_value(value, f"CC{controller}")))

        for role, controller, value in requests:
            request_key = (target.channel, role, controller)
            if request_key in seen_targets:
                blockers.append(f"duplicate initialization target {request_key}")
                continue
            seen_targets.add(request_key)
            event_ids = by_key.get(request_key, [])
            label = "Program Change" if controller is None else f"CC{controller}"
            if not event_ids:
                blockers.append(
                    f"channel {target.channel} has no existing {label} in the initialization bar"
                )
                continue
            if len(event_ids) > 1:
                blockers.append(
                    f"channel {target.channel} has multiple existing {label} events in the initialization bar"
                )
                continue
            event = event_map[event_ids[0]]
            old_value = event.data[0] if controller is None else event.data[1]
            if old_value != value:
                updates.append(
                    InitializationValueUpdate(
                        target.channel,
                        role,
                        controller,
                        event.event_id,
                        old_value,
                        value,
                    )
                )

    status = "blocked" if blockers else "ready" if updates else "no_changes"
    if status == "no_changes":
        warnings.append("requested initialization values already match the song")
    return InitializationUpdatePlan(
        status,
        revision,
        analysis,
        targets,
        tuple(updates),
        tuple(blockers),
        tuple(warnings),
    )


def preview_initialization_update(
    song: Song, plan: InitializationUpdatePlan
) -> InitializationUpdatePreview:
    transaction = _build_transaction(song, plan)
    projected = ChangeEngine().apply(song, transaction)
    return InitializationUpdatePreview(
        song_revision(song),
        song_revision(projected),
        song.event_count,
        projected.event_count,
        plan.updates,
    )


def build_initialization_update_transaction(
    song: Song,
    plan: InitializationUpdatePlan,
    *,
    approved: bool = False,
) -> ChangeTransaction:
    if not approved:
        raise PermissionError("initialization update requires explicit approval")
    return _build_transaction(song, plan)


def _build_transaction(song: Song, plan: InitializationUpdatePlan) -> ChangeTransaction:
    if plan.status != "ready" or plan.blockers or not plan.updates:
        raise ValueError("blocked or empty initialization plan cannot be applied")
    if song_revision(song) != plan.source_revision:
        raise ValueError("initialization preview is stale; analyze the current song again")
    refreshed = plan_initialization_update(song, plan.targets)
    if refreshed != plan:
        raise ValueError("initialization preview no longer matches the current song")
    groups: list[ChangeGroup] = []
    for channel in sorted({update.channel for update in plan.updates}):
        changes: list[Change] = []
        for update in (item for item in plan.updates if item.channel == channel):
            field = "program" if update.controller is None else "controller_value"
            changes.append(
                Change(
                    f"initialization:{update.event_id}",
                    "initialization_update",
                    f"update existing initialization {update.role}",
                    RiskLevel.HIGH,
                    update.event_id,
                    field,
                    update.old_value,
                    update.new_value,
                    True,
                )
            )
        groups.append(
            ChangeGroup(
                f"initialization-channel-{channel}",
                tuple(changes),
                "update existing initialization values without adding a bar",
            )
        )
    return ChangeTransaction(
        "initialization-update",
        tuple(groups),
        module="initialization_update",
        reason="explicitly approved update of an existing initialization bar",
        base_revision=plan.source_revision,
    )


def _controller_role(controller: int) -> str:
    return {
        0: "bank_msb",
        32: "bank_lsb",
        7: "volume",
        10: "pan",
        11: "expression",
    }.get(controller, "effect_send")


def _midi_value(value: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 127:
        raise ValueError(f"{label} must be an integer in range 0--127")
    return value