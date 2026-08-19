from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Iterable

from ..domain.changes import (
    Change,
    ChangeConflict,
    ChangeConflictError,
    ChangeSet,
    ChangeTransaction,
    DeleteEvent,
    InsertEvent,
)
from ..domain.events import EventKind, MidiEvent
from ..domain.song import Song, Track


def song_revision(song: Song) -> str:
    """Return a deterministic hash of the editable semantic model."""

    payload = {
        "header": [song.header.format_type, song.header.track_count, song.header.division],
        "tracks": [
            [
                [
                    event.event_id,
                    event.kind.value,
                    event.absolute_tick,
                    event.track_index,
                    event.order,
                    event.status,
                    event.data.hex(),
                    event.meta_type,
                ]
                for event in track.events
            ]
            for track in song.tracks
        ],
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def clone_song(song: Song) -> Song:
    """Copy mutable containers while sharing immutable events and raw evidence."""

    return Song(
        song.header,
        [Track(track.index, list(track.events)) for track in song.tracks],
        song.source_path,
        song.source_sha256,
        song.raw_document,
    )


class ChangeEngine:
    """Preflights and atomically applies approved event transactions."""

    def apply(
        self,
        song: Song,
        changes: ChangeSet | ChangeTransaction,
        *,
        locked_event_ids: Iterable[str] = (),
        locked_track_indices: Iterable[int] = (),
    ) -> Song:
        transaction = (
            changes.to_transaction() if isinstance(changes, ChangeSet) else changes
        )
        return self.apply_transaction(
            song,
            transaction,
            locked_event_ids=locked_event_ids,
            locked_track_indices=locked_track_indices,
        )

    def apply_transaction(
        self,
        song: Song,
        transaction: ChangeTransaction,
        *,
        locked_event_ids: Iterable[str] = (),
        locked_track_indices: Iterable[int] = (),
    ) -> Song:
        event_locks = frozenset(locked_event_ids)
        track_locks = frozenset(locked_track_indices)
        event_map = {
            event.event_id: event
            for track in song.tracks
            for event in track.events
        }
        conflicts = self._find_conflicts(
            song, transaction, event_map, event_locks, track_locks
        )
        if conflicts:
            raise ChangeConflictError(conflicts)

        by_event: dict[str, list[Change]] = {}
        deleted = {
            change.event_id for change in transaction.changes if isinstance(change, DeleteEvent)
        }
        inserted = [
            change.event for change in transaction.changes if isinstance(change, InsertEvent)
        ]
        for change in transaction.changes:
            if isinstance(change, Change):
                by_event.setdefault(change.event_id, []).append(change)

        tracks: list[Track] = []
        for track in song.tracks:
            events: list[MidiEvent] = []
            for event in track.events:
                if event.event_id in deleted:
                    continue
                updated = event
                for change in by_event.get(event.event_id, ()):
                    updated = self._apply_change(updated, change)
                events.append(updated)
            events.extend(event for event in inserted if event.track_index == track.index)
            events.sort(key=lambda item: (item.absolute_tick, item.order, item.event_id))
            events = [
                event if event.order == order else replace(event, order=order)
                for order, event in enumerate(events)
            ]
            tracks.append(Track(track.index, events))
        return Song(
            song.header,
            tracks,
            song.source_path,
            song.source_sha256,
            song.raw_document,
        )

    def _find_conflicts(
        self,
        song: Song,
        transaction: ChangeTransaction,
        event_map: dict[str, MidiEvent],
        event_locks: frozenset[str],
        track_locks: frozenset[int],
    ) -> list[ChangeConflict]:
        conflicts: list[ChangeConflict] = []
        revision = song_revision(song)
        if transaction.base_revision is not None and transaction.base_revision != revision:
            conflicts.append(
                ChangeConflict(
                    "revision_mismatch",
                    "transaction was prepared for a different song revision",
                    transaction.transaction_id,
                    expected=transaction.base_revision,
                    actual=revision,
                )
            )

        targets: set[tuple[str, str]] = set()
        event_actions: dict[str, str] = {}
        change_ids: set[str] = set()
        for group in transaction.groups:
            for change in group.changes:
                location = dict(
                    transaction_id=transaction.transaction_id,
                    group_id=group.group_id,
                    change_id=change.change_id,
                    event_id=change.event_id,
                    field=change.field,
                )
                if change.change_id in change_ids:
                    conflicts.append(
                        ChangeConflict(
                            "duplicate_change_id",
                            f"duplicate change id {change.change_id}",
                            **location,
                        )
                    )
                change_ids.add(change.change_id)
                action = (
                    "insert" if isinstance(change, InsertEvent)
                    else "delete" if isinstance(change, DeleteEvent)
                    else "update"
                )
                previous_action = event_actions.get(change.event_id)
                if previous_action is not None and (
                    previous_action != "update" or action != "update"
                ):
                    conflicts.append(
                        ChangeConflict(
                            "structural_target_conflict",
                            f"incompatible {previous_action}/{action} operations target {change.event_id}",
                            **location,
                        )
                    )
                event_actions[change.event_id] = action
                target = (change.event_id, change.field)
                if target in targets:
                    conflicts.append(
                        ChangeConflict(
                            "duplicate_target",
                            f"multiple changes target {change.event_id}.{change.field}",
                            **location,
                        )
                    )
                targets.add(target)

                if isinstance(change, InsertEvent):
                    self._check_insert(song, change, event_map, track_locks, location, conflicts)
                    continue

                event = event_map.get(change.event_id)
                if event is None:
                    conflicts.append(
                        ChangeConflict(
                            "missing_event",
                            f"event {change.event_id} no longer exists",
                            **location,
                        )
                    )
                    continue
                if event.event_id in event_locks:
                    conflicts.append(
                        ChangeConflict(
                            "locked_event",
                            f"event {event.event_id} is locked",
                            **location,
                        )
                    )
                if event.track_index in track_locks:
                    conflicts.append(
                        ChangeConflict(
                            "locked_track",
                            f"track {event.track_index} is locked",
                            **location,
                        )
                    )
                if isinstance(change, DeleteEvent):
                    if event.meta_type == 0x2F:
                        conflicts.append(
                            ChangeConflict(
                                "cannot_delete_eot",
                                "End of Track cannot be deleted",
                                **location,
                            )
                        )
                    if _event_signature(event) != _event_signature(change.expected_event):
                        conflicts.append(
                            ChangeConflict(
                                "delete_precondition_failed",
                                f"event {event.event_id} no longer matches its delete snapshot",
                                **location,
                            )
                        )
                    continue
                try:
                    actual = self._field_value(event, change.field)
                    self._validate_new_value(change)
                except ValueError as error:
                    conflicts.append(
                        ChangeConflict(
                            "unsupported_change",
                            str(error),
                            **location,
                        )
                    )
                    continue
                if actual != change.old_value:
                    conflicts.append(
                        ChangeConflict(
                            "precondition_failed",
                            (
                                f"{change.event_id}.{change.field} expected "
                                f"{change.old_value}, found {actual}"
                            ),
                            expected=change.old_value,
                            actual=actual,
                            **location,
                        )
                    )
        return conflicts

    @staticmethod
    def _check_insert(
        song: Song,
        change: InsertEvent,
        event_map: dict[str, MidiEvent],
        track_locks: frozenset[int],
        location: dict[str, object],
        conflicts: list[ChangeConflict],
    ) -> None:
        event = change.event
        if event.event_id in event_map:
            conflicts.append(
                ChangeConflict("event_already_exists", f"event {event.event_id} already exists", **location)
            )
        if not 0 <= event.track_index < len(song.tracks):
            conflicts.append(
                ChangeConflict("invalid_insert_track", f"track {event.track_index} does not exist", **location)
            )
            return
        if event.track_index in track_locks:
            conflicts.append(
                ChangeConflict("locked_track", f"track {event.track_index} is locked", **location)
            )
        try:
            _validate_inserted_event(event, song.tracks[event.track_index])
        except ValueError as error:
            conflicts.append(ChangeConflict("invalid_insert_event", str(error), **location))

    @staticmethod
    def _field_value(event: MidiEvent, field: str) -> int:
        if field == "absolute_tick":
            return event.absolute_tick
        if field == "velocity" and len(event.data) == 2:
            return event.data[1]
        if field == "note_number" and event.message_type in (0x80, 0x90) and len(event.data) == 2:
            return event.data[0]
        if field == "controller_value" and event.message_type == 0xB0 and len(event.data) == 2:
            return event.data[1]
        if field == "program" and event.message_type == 0xC0 and len(event.data) == 1:
            return event.data[0]
        raise ValueError(f"unsupported change field {field}")

    @staticmethod
    def _validate_new_value(change: Change) -> None:
        if change.field == "absolute_tick" and change.new_value < 0:
            raise ValueError("absolute_tick must be non-negative")
        if change.field == "velocity" and not 0 <= change.new_value <= 127:
            raise ValueError("velocity must be in range 0..127")
        if change.field == "note_number" and not 0 <= change.new_value <= 127:
            raise ValueError("note_number must be in range 0..127")
        if change.field == "controller_value" and not 0 <= change.new_value <= 127:
            raise ValueError("controller_value must be in range 0..127")
        if change.field == "program" and not 0 <= change.new_value <= 127:
            raise ValueError("program must be in range 0..127")

    @staticmethod
    def _apply_change(event: MidiEvent, change: Change) -> MidiEvent:
        if change.field == "absolute_tick":
            return replace(event, absolute_tick=change.new_value)
        if change.field == "velocity":
            return replace(event, data=bytes((event.data[0], change.new_value)))
        if change.field == "note_number":
            return replace(event, data=bytes((change.new_value, event.data[1])))
        if change.field == "controller_value":
            return replace(event, data=bytes((event.data[0], change.new_value)))
        if change.field == "program":
            return replace(event, data=bytes((change.new_value,)))
        raise AssertionError(f"preflight missed unsupported field {change.field}")


def _event_signature(event: MidiEvent) -> tuple[object, ...]:
    return (
        event.event_id,
        event.kind,
        event.absolute_tick,
        event.track_index,
        event.order,
        event.status,
        event.data,
        event.meta_type,
    )


def _validate_inserted_event(event: MidiEvent, track: Track) -> None:
    if not event.event_id:
        raise ValueError("inserted event_id must not be empty")
    if event.absolute_tick < 0 or event.order < 0:
        raise ValueError("inserted event tick and order must be non-negative")
    if event.track_index != track.index:
        raise ValueError("inserted event track_index does not match its target track")
    if event.kind is EventKind.CHANNEL:
        expected_lengths = {0x80: 2, 0x90: 2, 0xA0: 2, 0xB0: 2, 0xC0: 1, 0xD0: 1, 0xE0: 2}
        expected = expected_lengths.get(event.message_type)
        if not 0x80 <= event.status <= 0xEF or expected is None or len(event.data) != expected:
            raise ValueError("inserted channel event has invalid status or data length")
        if any(byte > 0x7F for byte in event.data):
            raise ValueError("inserted channel data byte exceeds 127")
    elif event.kind is EventKind.META:
        if event.status != 0xFF or event.meta_type is None or not 0 <= event.meta_type <= 0x7F:
            raise ValueError("inserted meta event has invalid status or meta type")
    elif event.kind is EventKind.SYSEX:
        if event.status not in (0xF0, 0xF7):
            raise ValueError("inserted SysEx event must use F0 or F7 status")
        body = event.data[:-1] if event.data.endswith(b"\xF7") else event.data
        if any(byte > 0x7F for byte in body):
            raise ValueError("inserted SysEx data byte exceeds 127")
    else:
        raise ValueError("inserted event kind is unsupported")

    eot_events = [item for item in track.events if item.meta_type == 0x2F]
    if event.meta_type == 0x2F:
        raise ValueError("structural End of Track insertion is not supported")
    elif eot_events:
        eot = min(eot_events, key=lambda item: item.order)
        if event.order >= eot.order or event.absolute_tick > eot.absolute_tick:
            raise ValueError("inserted event must remain before End of Track")
