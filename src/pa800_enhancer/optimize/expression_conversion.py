from __future__ import annotations

from dataclasses import dataclass

from ..analysis.expression import (
    ExpressionConversionPlan,
    ExpressionPlanStatus,
    analyze_cc7_to_cc11,
)
from ..domain.changes import (
    Change,
    ChangeGroup,
    ChangeTransaction,
    DeleteEvent,
    InsertEvent,
    RiskLevel,
)
from ..domain.events import EventKind, MidiEvent
from ..domain.song import Song
from .engine import ChangeEngine, song_revision


@dataclass(frozen=True, slots=True)
class ExpressionABPoint:
    absolute_tick: int
    original_product: int
    projected_product: int
    gain_error_db: float


@dataclass(frozen=True, slots=True)
class ExpressionABPreview:
    channel: int
    original_revision: str
    projected_revision: str
    original_event_count: int
    projected_event_count: int
    inserted_events: int
    deleted_events: int
    updated_events: int
    maximum_gain_error_db: float
    points: tuple[ExpressionABPoint, ...]


def preview_expression_conversion(
    song: Song, plan: ExpressionConversionPlan
) -> ExpressionABPreview:
    transaction = _build_transaction(song, plan)
    projected = ChangeEngine().apply(song, transaction)
    inserts = sum(isinstance(item, InsertEvent) for item in transaction.changes)
    deletes = sum(isinstance(item, DeleteEvent) for item in transaction.changes)
    updates = sum(isinstance(item, Change) for item in transaction.changes)
    return ExpressionABPreview(
        plan.channel,
        song_revision(song),
        song_revision(projected),
        song.event_count,
        projected.event_count,
        inserts,
        deletes,
        updates,
        plan.maximum_gain_error_db,
        tuple(
            ExpressionABPoint(
                point.absolute_tick,
                point.original_product,
                point.proposed_product,
                point.gain_error_db,
            )
            for point in plan.preview_points
        ),
    )


def project_expression_conversion(
    song: Song, plan: ExpressionConversionPlan
) -> Song:
    """Return a converted copy for preview without mutating the source song."""

    return ChangeEngine().apply(song, _build_transaction(song, plan))


def build_expression_conversion_transaction(
    song: Song,
    plan: ExpressionConversionPlan,
    *,
    approved: bool = False,
) -> ChangeTransaction:
    if not approved:
        raise PermissionError("CC7/CC11 conversion requires explicit approval")
    return _build_transaction(song, plan)


def _build_transaction(song: Song, plan: ExpressionConversionPlan) -> ChangeTransaction:
    if plan.status is not ExpressionPlanStatus.READY_FOR_REVIEW or plan.blockers:
        raise ValueError("blocked CC7/CC11 plan cannot be converted")
    if plan.track_index is None or plan.base_volume is None:
        raise ValueError("CC7/CC11 plan has no deterministic target track or base volume")
    refreshed = next(
        (
            item
            for item in analyze_cc7_to_cc11(song, plan.maximum_allowed_error_db)
            if item.channel == plan.channel
        ),
        None,
    )
    if refreshed != plan:
        raise ValueError("CC7/CC11 preview is stale; analyze the current song again")
    event_map = {
        event.event_id: event for track in song.tracks for event in track.events
    }
    try:
        cc7_events = [event_map[event_id] for event_id in plan.cc7_event_ids]
        cc11_events = [event_map[event_id] for event_id in plan.cc11_event_ids]
    except KeyError as error:
        raise ValueError(f"expression plan references missing event {error.args[0]}") from error
    _validate_source_events(plan, cc7_events, cc11_events)

    operations: list[Change | InsertEvent | DeleteEvent] = []
    baseline = min(cc7_events, key=lambda item: (item.absolute_tick, item.order))
    if baseline.data[1] != plan.base_volume:
        operations.append(
            Change(
                f"expression:base:{baseline.event_id}",
                "cc7_cc11_conversion",
                "set one stable Channel Volume baseline",
                RiskLevel.HIGH,
                baseline.event_id,
                "controller_value",
                baseline.data[1],
                plan.base_volume,
                True,
            )
        )
    for event in cc7_events:
        if event.event_id == baseline.event_id:
            continue
        operations.append(
            DeleteEvent(
                f"expression:delete:{event.event_id}",
                "cc7_cc11_conversion",
                "replace dynamic CC7 point with CC11 expression",
                RiskLevel.HIGH,
                event,
                True,
            )
        )

    cc11_by_tick = {event.absolute_tick: event for event in cc11_events}
    for point in plan.preview_points:
        existing = cc11_by_tick.get(point.absolute_tick)
        if existing is not None:
            if existing.data[1] != point.proposed_expression:
                operations.append(
                    Change(
                        f"expression:update:{existing.event_id}",
                        "cc7_cc11_conversion",
                        "merge Channel Volume and Expression into CC11",
                        RiskLevel.HIGH,
                        existing.event_id,
                        "controller_value",
                        existing.data[1],
                        point.proposed_expression,
                        True,
                    )
                )
            continue
        source_events = [event_map[event_id] for event_id in point.source_event_ids]
        order = max(event.order for event in source_events)
        inserted = MidiEvent(
            event_id=f"zexpr:ch{plan.channel}:tick{point.absolute_tick}",
            kind=EventKind.CHANNEL,
            absolute_tick=point.absolute_tick,
            track_index=plan.track_index,
            order=order,
            status=0xB0 | (plan.channel - 1),
            data=bytes((11, point.proposed_expression)),
        )
        operations.append(
            InsertEvent(
                f"expression:insert:{inserted.event_id}",
                "cc7_cc11_conversion",
                "insert projected CC11 expression point",
                RiskLevel.HIGH,
                inserted,
                True,
            )
        )
    if not operations:
        raise ValueError("CC7/CC11 plan produces no model changes")
    return ChangeTransaction(
        transaction_id=f"cc7-cc11-channel-{plan.channel}",
        groups=(
            ChangeGroup(
                group_id=f"cc7-cc11-channel-{plan.channel}",
                changes=tuple(operations),
                reason="convert approved CC7 automation to CC11 expression",
            ),
        ),
        module="cc7_cc11_conversion",
        reason="explicitly approved CC7/CC11 conversion",
    )


def _validate_source_events(
    plan: ExpressionConversionPlan,
    cc7_events: list[MidiEvent],
    cc11_events: list[MidiEvent],
) -> None:
    for event in cc7_events:
        if (
            event.track_index != plan.track_index
            or event.channel != plan.channel
            or event.message_type != 0xB0
            or event.data[0] != 7
        ):
            raise ValueError(f"event {event.event_id} no longer belongs to the CC7 curve")
    for event in cc11_events:
        if (
            event.track_index != plan.track_index
            or event.channel != plan.channel
            or event.message_type != 0xB0
            or event.data[0] != 11
        ):
            raise ValueError(f"event {event.event_id} no longer belongs to the CC11 curve")
