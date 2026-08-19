from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from ..domain.song import Song
from .controllers import ControllerEvent, controller_events
from .sysex import SysexClassification, analyze_sysex


class ExpressionPlanStatus(str, Enum):
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ExpressionPreviewPoint:
    absolute_tick: int
    original_volume: int
    original_expression: int
    proposed_expression: int
    original_product: int
    proposed_product: int
    gain_error_db: float
    source_event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpressionConversionPlan:
    channel: int
    track_index: int | None
    status: ExpressionPlanStatus
    base_volume: int | None
    cc7_event_ids: tuple[str, ...]
    cc11_event_ids: tuple[str, ...]
    preview_points: tuple[ExpressionPreviewPoint, ...]
    maximum_gain_error_db: float
    maximum_allowed_error_db: float
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def requires_confirmation(self) -> bool:
        return True


def analyze_cc7_to_cc11(
    song: Song, maximum_allowed_error_db: float = 0.5
) -> tuple[ExpressionConversionPlan, ...]:
    if maximum_allowed_error_db < 0:
        raise ValueError("maximum_allowed_error_db must be non-negative")
    events = controller_events(song)
    sysex = analyze_sysex(song)
    by_channel = {
        channel: [event for event in events if event.channel == channel]
        for channel in range(1, 17)
    }
    plans: list[ExpressionConversionPlan] = []
    for channel, channel_events in by_channel.items():
        cc7 = [event for event in channel_events if event.controller == 7]
        if not cc7:
            continue
        cc11 = [event for event in channel_events if event.controller == 11]
        blockers: list[str] = []
        warnings: list[str] = []
        related = cc7 + cc11
        tracks = {event.track_index for event in related}
        track_index = next(iter(tracks)) if len(tracks) == 1 else None
        if len(tracks) > 1:
            blockers.append("cc7_cc11_span_multiple_tracks")
        if len({event.value for event in cc7}) < 2:
            blockers.append("cc7_has_no_dynamic_curve")
        if _has_duplicate_ticks(cc7):
            blockers.append("multiple_cc7_events_at_same_tick")
        if _has_duplicate_ticks(cc11):
            blockers.append("multiple_cc11_events_at_same_tick")
        if any(event.controller in (39, 43) for event in channel_events):
            blockers.append("14bit_volume_or_expression_detected")
        if any(event.controller == 121 for event in channel_events):
            blockers.append("reset_all_controllers_changes_curve_state")

        first_cc7 = min(cc7, key=_event_key)
        first_cc11 = min(cc11, key=_event_key) if cc11 else None
        if first_cc11 is not None and _event_key(first_cc11) < _event_key(first_cc7):
            blockers.append("expression_precedes_explicit_volume_baseline")
        first_note = _first_note(song, channel)
        if first_note is not None and not _event_precedes_note(first_cc7, first_note):
            blockers.append("explicit_cc7_baseline_does_not_precede_first_note")
        uncertain_sysex = {
            SysexClassification.UNKNOWN,
            SysexClassification.INCOMPLETE,
            SysexClassification.MALFORMED,
        }
        if any(message.classification in uncertain_sysex for message in sysex.messages):
            blockers.append("unknown_sysex_may_affect_mix_state")
        if any(
            message in sysex.recognized_resets and message.start_tick >= first_cc7.absolute_tick
            for message in sysex.messages
        ):
            blockers.append("system_reset_occurs_during_cc7_curve")

        base_volume = max(event.value for event in cc7)
        if base_volume == 0:
            blockers.append("cc7_curve_is_silent")
        if cc11:
            warnings.append("existing_cc11_will_be_merged_with_cc7_shape")
        if first_cc7.value != base_volume:
            warnings.append("proposed_base_volume_differs_from_initial_cc7")
        warnings.append("conversion_requires_ab_review")

        preview = _build_preview(cc7, cc11, base_volume) if base_volume else ()
        maximum_error = max((point.gain_error_db for point in preview), default=0.0)
        if any(math.isinf(point.gain_error_db) for point in preview):
            blockers.append("low_level_quantization_would_create_silence")
        elif maximum_error > maximum_allowed_error_db:
            blockers.append("preview_exceeds_maximum_gain_error")

        plans.append(
            ExpressionConversionPlan(
                channel,
                track_index,
                ExpressionPlanStatus.BLOCKED if blockers else ExpressionPlanStatus.READY_FOR_REVIEW,
                base_volume,
                tuple(event.event_id for event in cc7),
                tuple(event.event_id for event in cc11),
                preview,
                maximum_error,
                maximum_allowed_error_db,
                tuple(dict.fromkeys(blockers)),
                tuple(dict.fromkeys(warnings)),
            )
        )
    return tuple(plans)


def _build_preview(
    cc7: list[ControllerEvent], cc11: list[ControllerEvent], base_volume: int
) -> tuple[ExpressionPreviewPoint, ...]:
    events = sorted(cc7 + cc11, key=_event_key)
    start = min(cc7, key=_event_key)
    volume = 100
    expression = 127
    points: list[ExpressionPreviewPoint] = []
    index = 0
    while index < len(events):
        tick = events[index].absolute_tick
        at_tick: list[ControllerEvent] = []
        while index < len(events) and events[index].absolute_tick == tick:
            event = events[index]
            at_tick.append(event)
            if event.controller == 7:
                volume = event.value
            else:
                expression = event.value
            index += 1
        if tick < start.absolute_tick:
            continue
        original_product = volume * expression
        proposed_expression = min(127, max(0, round(original_product / base_volume)))
        proposed_product = base_volume * proposed_expression
        points.append(
            ExpressionPreviewPoint(
                tick,
                volume,
                expression,
                proposed_expression,
                original_product,
                proposed_product,
                _gain_error_db(original_product, proposed_product),
                tuple(event.event_id for event in at_tick),
            )
        )
    return tuple(points)


def _gain_error_db(original_product: int, proposed_product: int) -> float:
    if original_product == proposed_product:
        return 0.0
    if original_product == 0 or proposed_product == 0:
        return math.inf
    return abs(40.0 * math.log10(proposed_product / original_product))


def _has_duplicate_ticks(events: list[ControllerEvent]) -> bool:
    ticks = [event.absolute_tick for event in events]
    return len(ticks) != len(set(ticks))


def _event_key(event: ControllerEvent) -> tuple[int, int, int]:
    return event.absolute_tick, event.track_index, event.order


def _first_note(song: Song, channel: int):
    notes = [
        event
        for track in song.tracks
        for event in track.events
        if event.channel == channel and event.is_note_on
    ]
    return min(notes, key=lambda event: (event.absolute_tick, event.track_index, event.order), default=None)


def _event_precedes_note(controller: ControllerEvent, note) -> bool:
    if controller.absolute_tick < note.absolute_tick:
        return True
    return (
        controller.absolute_tick == note.absolute_tick
        and controller.track_index == note.track_index
        and controller.order < note.order
    )
