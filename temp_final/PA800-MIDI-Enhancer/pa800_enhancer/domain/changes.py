from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Iterable

from .events import EventKind, MidiEvent


class RiskLevel(IntEnum):
    INFORMATION = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True, slots=True)
class Change:
    """One scalar event mutation with an optimistic-lock precondition."""

    change_id: str
    module: str
    reason: str
    risk: RiskLevel
    event_id: str
    field: str
    old_value: int
    new_value: int
    approved: bool = False
    group_id: str | None = None

    def approved_copy(self) -> "Change":
        return replace(self, approved=True)

    def inverse(self) -> "Change":
        return replace(
            self,
            change_id=f"undo:{self.change_id}",
            reason=f"Undo: {self.reason}",
            old_value=self.new_value,
            new_value=self.old_value,
            approved=True,
        )


@dataclass(frozen=True, slots=True)
class InsertEvent:
    """Insert one immutable event if its identity is still absent."""

    change_id: str
    module: str
    reason: str
    risk: RiskLevel
    event: MidiEvent
    approved: bool = True

    @property
    def event_id(self) -> str:
        return self.event.event_id

    @property
    def field(self) -> str:
        return "__insert__"

    def inverse(self) -> "DeleteEvent":
        return DeleteEvent(
            f"undo:{self.change_id}",
            self.module,
            f"Undo: {self.reason}",
            self.risk,
            self.event,
            True,
        )


@dataclass(frozen=True, slots=True)
class DeleteEvent:
    """Delete one event only while its full semantic snapshot still matches."""

    change_id: str
    module: str
    reason: str
    risk: RiskLevel
    expected_event: MidiEvent
    approved: bool = True

    @property
    def event_id(self) -> str:
        return self.expected_event.event_id

    @property
    def field(self) -> str:
        return "__delete__"

    def inverse(self) -> InsertEvent:
        return InsertEvent(
            f"undo:{self.change_id}",
            self.module,
            f"Undo: {self.reason}",
            self.risk,
            self.expected_event,
            True,
        )


EventChange = Change | InsertEvent | DeleteEvent


@dataclass(slots=True)
class ChangeSet:
    """Backward-compatible flat suggestion container.

    New code should convert approved suggestions to a ChangeTransaction before
    applying them. Changes with the same group_id become one atomic group.
    """

    changes: list[Change] = field(default_factory=list)

    def approved(self) -> list[Change]:
        grouped: dict[str, list[Change]] = {}
        for change in self.changes:
            if change.group_id is not None:
                grouped.setdefault(change.group_id, []).append(change)
        approved_groups = {
            group_id
            for group_id, changes in grouped.items()
            if all(change.approved for change in changes)
        }
        return [
            change
            for change in self.changes
            if (change.group_id is None and change.approved)
            or change.group_id in approved_groups
        ]

    def approve_all(self) -> "ChangeSet":
        self.changes = [change.approved_copy() for change in self.changes]
        return self

    def to_transaction(self, transaction_id: str = "approved-changes") -> "ChangeTransaction":
        grouped: dict[str, list[Change]] = {}
        order: list[str] = []
        for change in self.approved():
            key = change.group_id or change.change_id
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(change)
        groups = tuple(
            ChangeGroup(group_id=key, changes=tuple(grouped[key])) for key in order
        )
        modules = {change.module for change in self.approved()}
        module = modules.pop() if len(modules) == 1 else "multiple"
        return ChangeTransaction(transaction_id, groups, module=module)


@dataclass(frozen=True, slots=True)
class ChangeGroup:
    """Changes that must either all succeed or leave the song untouched."""

    group_id: str
    changes: tuple[EventChange, ...]
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("group_id must not be empty")
        if not self.changes:
            raise ValueError("a change group must contain at least one change")

    @property
    def risk(self) -> RiskLevel:
        return max((change.risk for change in self.changes), default=RiskLevel.INFORMATION)

    def inverse(self) -> "ChangeGroup":
        return ChangeGroup(
            group_id=f"undo:{self.group_id}",
            changes=tuple(change.inverse() for change in reversed(self.changes)),
            reason=f"Undo: {self.reason}" if self.reason else "Undo change group",
        )


@dataclass(frozen=True, slots=True)
class ChangeTransaction:
    """Approved atomic unit recorded by command history."""

    transaction_id: str
    groups: tuple[ChangeGroup, ...]
    module: str = "manual"
    reason: str = ""
    base_revision: str | None = None

    def __post_init__(self) -> None:
        if not self.transaction_id:
            raise ValueError("transaction_id must not be empty")
        ids = [group.group_id for group in self.groups]
        if len(ids) != len(set(ids)):
            raise ValueError("group_id values must be unique within a transaction")

    @classmethod
    def from_changes(
        cls,
        transaction_id: str,
        changes: Iterable[EventChange],
        *,
        module: str = "manual",
        reason: str = "",
        base_revision: str | None = None,
    ) -> "ChangeTransaction":
        grouped: dict[str, list[EventChange]] = {}
        order: list[str] = []
        for change in changes:
            key = change.group_id if isinstance(change, Change) and change.group_id else change.change_id
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(change)
        groups = tuple(ChangeGroup(key, tuple(grouped[key])) for key in order)
        return cls(transaction_id, groups, module, reason, base_revision)

    @property
    def changes(self) -> tuple[EventChange, ...]:
        return tuple(change for group in self.groups for change in group.changes)

    def inverse(self, base_revision: str | None = None) -> "ChangeTransaction":
        return ChangeTransaction(
            transaction_id=f"undo:{self.transaction_id}",
            groups=tuple(group.inverse() for group in reversed(self.groups)),
            module=self.module,
            reason=f"Undo: {self.reason}" if self.reason else "Undo transaction",
            base_revision=base_revision,
        )


@dataclass(frozen=True, slots=True)
class ChangeConflict:
    code: str
    message: str
    transaction_id: str
    group_id: str | None = None
    change_id: str | None = None
    event_id: str | None = None
    field: str | None = None
    expected: int | str | None = None
    actual: int | str | None = None


class ChangeConflictError(ValueError):
    def __init__(self, conflicts: Iterable[ChangeConflict]) -> None:
        self.conflicts = tuple(conflicts)
        message = "; ".join(conflict.message for conflict in self.conflicts)
        super().__init__(message or "change transaction conflicts")


def transaction_to_dict(transaction: ChangeTransaction) -> dict[str, object]:
    """Serialize a transaction without relying on enum implementation details."""

    return {
        "transaction_id": transaction.transaction_id,
        "module": transaction.module,
        "reason": transaction.reason,
        "base_revision": transaction.base_revision,
        "groups": [
            {
                "group_id": group.group_id,
                "reason": group.reason,
                "changes": [
                    _change_to_dict(change)
                    for change in group.changes
                ],
            }
            for group in transaction.groups
        ],
    }


def transaction_from_dict(data: dict[str, object]) -> ChangeTransaction:
    """Load and validate a transaction from project JSON data."""

    groups: list[ChangeGroup] = []
    for group_data in _list_of_dicts(data.get("groups"), "groups"):
        changes = tuple(
            _change_from_dict(change_data)
            for change_data in _list_of_dicts(group_data.get("changes"), "changes")
        )
        groups.append(
            ChangeGroup(
                group_id=_string(group_data, "group_id"),
                changes=changes,
                reason=str(group_data.get("reason", "")),
            )
        )
    return ChangeTransaction(
        transaction_id=_string(data, "transaction_id"),
        groups=tuple(groups),
        module=str(data.get("module", "manual")),
        reason=str(data.get("reason", "")),
        base_revision=_optional_string(data.get("base_revision")),
    )


def _change_to_dict(change: EventChange) -> dict[str, object]:
    common: dict[str, object] = {
        "change_id": change.change_id,
        "module": change.module,
        "reason": change.reason,
        "risk": int(change.risk),
        "approved": change.approved,
    }
    if isinstance(change, Change):
        return {
            **common,
            "operation": "update",
            "event_id": change.event_id,
            "field": change.field,
            "old_value": change.old_value,
            "new_value": change.new_value,
            "group_id": change.group_id,
        }
    if isinstance(change, InsertEvent):
        return {**common, "operation": "insert", "event": _event_to_dict(change.event)}
    return {
        **common,
        "operation": "delete",
        "expected_event": _event_to_dict(change.expected_event),
    }


def _change_from_dict(data: dict[str, object]) -> EventChange:
    operation = data.get("operation", "update")
    common = dict(
        change_id=_string(data, "change_id"),
        module=_string(data, "module"),
        reason=_string(data, "reason"),
        risk=RiskLevel(_integer(data, "risk")),
        approved=_boolean(data.get("approved", False), "approved"),
    )
    if operation == "update":
        return Change(
            **common,
            event_id=_string(data, "event_id"),
            field=_string(data, "field"),
            old_value=_integer(data, "old_value"),
            new_value=_integer(data, "new_value"),
            group_id=_optional_string(data.get("group_id")),
        )
    if operation == "insert":
        return InsertEvent(**common, event=_event_from_dict(_object(data, "event")))
    if operation == "delete":
        return DeleteEvent(
            **common,
            expected_event=_event_from_dict(_object(data, "expected_event")),
        )
    raise ValueError(f"unknown change operation {operation}")


def _event_to_dict(event: MidiEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "kind": event.kind.value,
        "absolute_tick": event.absolute_tick,
        "track_index": event.track_index,
        "order": event.order,
        "status": event.status,
        "data": event.data.hex(),
        "meta_type": event.meta_type,
        "original_delta_time": event.original_delta_time,
    }


def _event_from_dict(data: dict[str, object]) -> MidiEvent:
    encoded = _string(data, "data")
    try:
        payload = bytes.fromhex(encoded)
        kind = EventKind(_string(data, "kind"))
    except ValueError as error:
        raise ValueError(f"invalid serialized MIDI event: {error}") from error
    meta_type = data.get("meta_type")
    if meta_type is not None and (not isinstance(meta_type, int) or isinstance(meta_type, bool)):
        raise ValueError("meta_type must be an integer or null")
    return MidiEvent(
        event_id=_string(data, "event_id"),
        kind=kind,
        absolute_tick=_integer(data, "absolute_tick"),
        track_index=_integer(data, "track_index"),
        order=_integer(data, "order"),
        status=_integer(data, "status"),
        data=payload,
        meta_type=meta_type,
        original_delta_time=_integer(data, "original_delta_time"),
    )


def _list_of_dicts(value: object, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{field} must be a list of objects")
    return value


def _string(data: dict[str, object], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional value must be a string or null")
    return value


def _integer(data: dict[str, object], field: str) -> int:
    value = data.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _object(data: dict[str, object], field: str) -> dict[str, object]:
    value = data.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value