from __future__ import annotations

from collections.abc import Iterable

from ..analysis.curves import CurveSimplification
from ..domain.changes import ChangeGroup, ChangeTransaction, DeleteEvent, RiskLevel
from ..domain.song import Song


def build_curve_thinning_transaction(
    song: Song,
    plans: Iterable[CurveSimplification],
    *,
    approved: bool = False,
    transaction_id: str = "controller-thinning",
) -> ChangeTransaction:
    """Convert explicitly approved read-only plans into atomic deletions."""

    if not approved:
        raise PermissionError("controller thinning requires explicit approval")
    event_map = {
        event.event_id: event for track in song.tracks for event in track.events
    }
    groups: list[ChangeGroup] = []
    targeted: set[str] = set()
    for plan in plans:
        if not plan.applied or not plan.removed_event_ids:
            continue
        deletions: list[DeleteEvent] = []
        for event_id in plan.removed_event_ids:
            if event_id in targeted:
                raise ValueError(f"event {event_id} appears in multiple curve plans")
            try:
                event = event_map[event_id]
            except KeyError as error:
                raise ValueError(f"curve plan references missing event {event_id}") from error
            if (
                event.track_index != plan.curve.track_index
                or event.channel != plan.curve.channel
                or event.message_type != 0xB0
                or len(event.data) != 2
                or event.data[0] != plan.curve.controller
            ):
                raise ValueError(f"event {event_id} no longer belongs to the planned CC curve")
            targeted.add(event_id)
            deletions.append(
                DeleteEvent(
                    change_id=f"thin:{event_id}",
                    module="controller_thinning",
                    reason=(
                        f"remove redundant CC{plan.curve.controller} point within "
                        f"tolerance {plan.tolerance:g}"
                    ),
                    risk=RiskLevel.HIGH,
                    expected_event=event,
                    approved=True,
                )
            )
        groups.append(
            ChangeGroup(
                group_id=(
                    f"cc:{plan.curve.track_index}:{plan.curve.channel}:"
                    f"{plan.curve.controller}"
                ),
                changes=tuple(deletions),
                reason=(
                    f"thin CC{plan.curve.controller}; measured maximum error "
                    f"{plan.maximum_error:g}"
                ),
            )
        )
    if not groups:
        raise ValueError("approved curve plans contain no removable events")
    return ChangeTransaction(
        transaction_id,
        tuple(groups),
        module="controller_thinning",
        reason="approved controller curve thinning",
    )