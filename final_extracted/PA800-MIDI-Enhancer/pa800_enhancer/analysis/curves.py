from __future__ import annotations

from dataclasses import dataclass

from ..domain.song import Song
from .controllers import ControllerEvent, controller_events


PARAMETER_CONTROLLERS = frozenset({6, 38, 96, 97, 98, 99, 100, 101})
BANK_CONTROLLERS = frozenset({0, 32})
DISCRETE_CONTROLLERS = frozenset({64, 65, 66, 67, 68, 69, 80, 81, 82, 83, 84})
CHANNEL_MODE_CONTROLLERS = frozenset(range(120, 128))
NEVER_THIN_CONTROLLERS = (
    PARAMETER_CONTROLLERS
    | BANK_CONTROLLERS
    | DISCRETE_CONTROLLERS
    | CHANNEL_MODE_CONTROLLERS
)


@dataclass(frozen=True, slots=True)
class CurvePoint:
    event_id: str
    absolute_tick: int
    value: int
    order: int


@dataclass(frozen=True, slots=True)
class ControllerCurve:
    track_index: int
    channel: int
    controller: int
    points: tuple[CurvePoint, ...]

    @property
    def can_thin(self) -> bool:
        return self.controller not in NEVER_THIN_CONTROLLERS and len(self.points) > 2

    @property
    def protected_reason(self) -> str | None:
        if self.controller in PARAMETER_CONTROLLERS:
            return "NRPN/RPN and Data Entry controllers are atomic parameter data"
        if self.controller in BANK_CONTROLLERS:
            return "Bank Select is part of instrument identity"
        if self.controller in DISCRETE_CONTROLLERS:
            return "pedal, switch or discrete controller"
        if self.controller in CHANNEL_MODE_CONTROLLERS:
            return "Channel Mode messages must not be curve-thinned"
        if len(self.points) <= 2:
            return "curve has no removable interior points"
        return None


@dataclass(frozen=True, slots=True)
class CurveSimplification:
    curve: ControllerCurve
    tolerance: float
    kept_event_ids: tuple[str, ...]
    removed_event_ids: tuple[str, ...]
    protected_event_ids: tuple[str, ...]
    maximum_error: float
    applied: bool
    reason: str

    @property
    def original_count(self) -> int:
        return len(self.curve.points)

    @property
    def retained_count(self) -> int:
        return len(self.kept_event_ids)


def build_controller_curves(song: Song) -> tuple[ControllerCurve, ...]:
    grouped: dict[tuple[int, int, int], list[ControllerEvent]] = {}
    for event in controller_events(song):
        grouped.setdefault(
            (event.track_index, event.channel, event.controller), []
        ).append(event)
    return tuple(
        ControllerCurve(
            track_index,
            channel,
            controller,
            tuple(
                CurvePoint(item.event_id, item.absolute_tick, item.value, item.order)
                for item in sorted(events, key=lambda value: (value.absolute_tick, value.order))
            ),
        )
        for (track_index, channel, controller), events in sorted(grouped.items())
    )


def simplify_curve(
    curve: ControllerCurve, tolerance: float = 1.0
) -> CurveSimplification:
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    if not curve.can_thin:
        ids = tuple(point.event_id for point in curve.points)
        return CurveSimplification(
            curve,
            tolerance,
            ids,
            (),
            ids,
            0.0,
            False,
            curve.protected_reason or "curve is protected",
        )

    protected = _protected_indices(curve.points)
    kept = set(protected)
    anchors = sorted(protected)
    for start, end in zip(anchors, anchors[1:]):
        _rdp(curve.points, start, end, tolerance, kept)

    kept_indices = sorted(kept)
    removed_indices = [index for index in range(len(curve.points)) if index not in kept]
    maximum_error = max(
        (_error_against_kept(curve.points, index, kept_indices) for index in removed_indices),
        default=0.0,
    )
    if maximum_error > tolerance + 1e-9:
        raise AssertionError("curve simplification exceeded its requested tolerance")
    return CurveSimplification(
        curve,
        tolerance,
        tuple(curve.points[index].event_id for index in kept_indices),
        tuple(curve.points[index].event_id for index in removed_indices),
        tuple(curve.points[index].event_id for index in sorted(protected)),
        maximum_error,
        bool(removed_indices),
        "within tolerance" if removed_indices else "no point can be removed within tolerance",
    )


def simplify_song_curves(
    song: Song, tolerance: float = 1.0
) -> tuple[CurveSimplification, ...]:
    return tuple(simplify_curve(curve, tolerance) for curve in build_controller_curves(song))


def _protected_indices(points: tuple[CurvePoint, ...]) -> set[int]:
    protected = {0, len(points) - 1}
    ticks: dict[int, list[int]] = {}
    for index, point in enumerate(points):
        ticks.setdefault(point.absolute_tick, []).append(index)
    for indices in ticks.values():
        if len(indices) > 1:
            protected.update(indices)

    index = 1
    while index < len(points) - 1:
        run_start = index
        run_end = index
        while run_end + 1 < len(points) and points[run_end + 1].value == points[index].value:
            run_end += 1
        if run_end < len(points) - 1:
            previous = points[run_start - 1].value
            current = points[run_start].value
            following = points[run_end + 1].value
            if (current > previous and current > following) or (
                current < previous and current < following
            ):
                protected.add(run_start)
                protected.add(run_end)
        index = run_end + 1
    return protected


def _rdp(
    points: tuple[CurvePoint, ...],
    start: int,
    end: int,
    tolerance: float,
    kept: set[int],
) -> None:
    if end <= start + 1:
        return
    maximum = -1.0
    split: int | None = None
    for index in range(start + 1, end):
        error = _interpolation_error(points[index], points[start], points[end])
        if error > maximum:
            maximum = error
            split = index
    if split is not None and maximum > tolerance:
        kept.add(split)
        _rdp(points, start, split, tolerance, kept)
        _rdp(points, split, end, tolerance, kept)


def _interpolation_error(point: CurvePoint, left: CurvePoint, right: CurvePoint) -> float:
    span = right.absolute_tick - left.absolute_tick
    if span <= 0:
        return float("inf")
    fraction = (point.absolute_tick - left.absolute_tick) / span
    expected = left.value + fraction * (right.value - left.value)
    return abs(point.value - expected)


def _error_against_kept(
    points: tuple[CurvePoint, ...], index: int, kept_indices: list[int]
) -> float:
    left = max(item for item in kept_indices if item < index)
    right = min(item for item in kept_indices if item > index)
    return _interpolation_error(points[index], points[left], points[right])