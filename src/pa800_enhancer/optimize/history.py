from __future__ import annotations

from dataclasses import dataclass, replace

from ..domain.changes import (
    ChangeConflict,
    ChangeConflictError,
    ChangeTransaction,
    transaction_from_dict,
    transaction_to_dict,
)
from ..domain.song import Song
from .engine import ChangeEngine, clone_song, song_revision


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    transaction: ChangeTransaction
    before: Song
    after: Song
    before_revision: str
    after_revision: str


class CommandHistory:
    """Atomic apply/undo/redo history for one imported song."""

    def __init__(self, song: Song, engine: ChangeEngine | None = None) -> None:
        self._engine = engine or ChangeEngine()
        self._initial = clone_song(song)
        self._current = clone_song(song)
        self._undo: list[HistoryEntry] = []
        self._redo: list[HistoryEntry] = []
        self._checkpoints: dict[str, tuple[int, Song, str]] = {}
        self.locked_event_ids: set[str] = set()
        self.locked_track_indices: set[int] = set()

    @property
    def song(self) -> Song:
        return clone_song(self._current)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def transactions(self) -> tuple[ChangeTransaction, ...]:
        return tuple(entry.transaction for entry in self._undo)

    def apply(self, transaction: ChangeTransaction) -> Song:
        before = clone_song(self._current)
        before_revision = song_revision(before)
        prepared = transaction
        if prepared.base_revision is None:
            prepared = replace(prepared, base_revision=before_revision)
        after = self._engine.apply_transaction(
            before,
            prepared,
            locked_event_ids=self.locked_event_ids,
            locked_track_indices=self.locked_track_indices,
        )
        entry = HistoryEntry(
            prepared,
            before,
            clone_song(after),
            before_revision,
            song_revision(after),
        )
        self._undo.append(entry)
        self._redo.clear()
        self._current = after
        return self.song

    def undo(self) -> Song:
        if not self._undo:
            raise IndexError("nothing to undo")
        entry = self._undo[-1]
        self._require_revision(entry.after_revision, "undo")
        self._undo.pop()
        self._redo.append(entry)
        self._current = clone_song(entry.before)
        return self.song

    def redo(self) -> Song:
        if not self._redo:
            raise IndexError("nothing to redo")
        entry = self._redo[-1]
        self._require_revision(entry.before_revision, "redo")
        self._redo.pop()
        self._undo.append(entry)
        self._current = clone_song(entry.after)
        return self.song

    def checkpoint(self, name: str) -> None:
        if not name:
            raise ValueError("checkpoint name must not be empty")
        self._checkpoints[name] = (
            len(self._undo),
            clone_song(self._current),
            song_revision(self._current),
        )

    def restore_checkpoint(self, name: str) -> Song:
        try:
            index, snapshot, revision = self._checkpoints[name]
        except KeyError as error:
            raise KeyError(f"unknown checkpoint {name}") from error
        removed = self._undo[index:]
        self._undo = self._undo[:index]
        self._redo = list(reversed(removed))
        self._current = clone_song(snapshot)
        if song_revision(self._current) != revision:
            raise AssertionError("checkpoint snapshot is corrupt")
        return self.song

    def rollback_module(self, module: str) -> Song:
        """Remove a module's transactions and replay the remaining history."""

        kept = [entry.transaction for entry in self._undo if entry.transaction.module != module]
        self._current = clone_song(self._initial)
        self._undo = []
        self._redo = []
        for transaction in kept:
            rebased = replace(transaction, base_revision=song_revision(self._current))
            self.apply(rebased)
        return self.song

    def lock_event(self, event_id: str) -> None:
        self.locked_event_ids.add(event_id)

    def unlock_event(self, event_id: str) -> None:
        self.locked_event_ids.discard(event_id)

    def lock_track(self, track_index: int) -> None:
        self.locked_track_indices.add(track_index)

    def unlock_track(self, track_index: int) -> None:
        self.locked_track_indices.discard(track_index)

    def to_state(self) -> dict[str, object]:
        """Return JSON-safe history, redo, checkpoint and lock state."""

        return {
            "applied": [transaction_to_dict(entry.transaction) for entry in self._undo],
            "redo": [
                transaction_to_dict(entry.transaction) for entry in reversed(self._redo)
            ],
            "checkpoints": {
                name: {"transaction_index": index, "revision": revision}
                for name, (index, _snapshot, revision) in self._checkpoints.items()
            },
            "locked_event_ids": sorted(self.locked_event_ids),
            "locked_track_indices": sorted(self.locked_track_indices),
        }

    @classmethod
    def from_state(
        cls,
        song: Song,
        state: dict[str, object],
        engine: ChangeEngine | None = None,
    ) -> "CommandHistory":
        """Rebuild history by replaying it against the verified source song."""

        history = cls(song, engine)
        event_locks = _string_set(state.get("locked_event_ids", []))
        track_locks = _integer_set(state.get("locked_track_indices", []))

        applied = _transaction_list(state.get("applied", []), "applied")
        for transaction in applied:
            history.apply(transaction)

        redo_entries: list[HistoryEntry] = []
        redo_song = clone_song(history._current)
        for transaction in _transaction_list(state.get("redo", []), "redo"):
            before = clone_song(redo_song)
            before_revision = song_revision(before)
            prepared = transaction
            if prepared.base_revision != before_revision:
                prepared = replace(prepared, base_revision=before_revision)
            after = history._engine.apply_transaction(
                before,
                prepared,
            )
            redo_entries.append(
                HistoryEntry(
                    prepared,
                    before,
                    clone_song(after),
                    before_revision,
                    song_revision(after),
                )
            )
            redo_song = after
        history._redo = list(reversed(redo_entries))

        checkpoints = state.get("checkpoints", {})
        if not isinstance(checkpoints, dict):
            raise ValueError("checkpoints must be an object")
        for name, checkpoint in checkpoints.items():
            if not isinstance(name, str) or not isinstance(checkpoint, dict):
                raise ValueError("invalid checkpoint entry")
            index = checkpoint.get("transaction_index")
            revision = checkpoint.get("revision")
            if not isinstance(index, int) or isinstance(index, bool):
                raise ValueError("checkpoint transaction_index must be an integer")
            if not isinstance(revision, str) or not 0 <= index <= len(history._undo):
                raise ValueError("invalid checkpoint revision or index")
            snapshot = history._initial if index == 0 else history._undo[index - 1].after
            if song_revision(snapshot) != revision:
                raise ValueError(f"checkpoint {name} revision does not match history")
            history._checkpoints[name] = (index, clone_song(snapshot), revision)
        history.locked_event_ids = event_locks
        history.locked_track_indices = track_locks
        return history

    def _require_revision(self, expected: str, operation: str) -> None:
        actual = song_revision(self._current)
        if actual != expected:
            raise ChangeConflictError(
                [
                    ChangeConflict(
                        "history_diverged",
                        f"cannot {operation}: working song diverged from command history",
                        transaction_id=operation,
                        expected=expected,
                        actual=actual,
                    )
                ]
            )


def _transaction_list(value: object, field: str) -> list[ChangeTransaction]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{field} must be a list of transactions")
    return [transaction_from_dict(item) for item in value]


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("locked_event_ids must be a list of strings")
    return set(value)


def _integer_set(value: object) -> set[int]:
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise ValueError("locked_track_indices must be a list of integers")
    return set(value)
