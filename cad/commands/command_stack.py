"""Undo/Redo command stack — snapshot-based undo management."""

from __future__ import annotations

from typing import Any


class UndoRedoStack:
    """A stack of document snapshots for undo/redo.

    Each entry stores a ``(before, after)`` pair of document dicts
    (the output of ``Document.to_dict()``).

    *   ``undo()`` restores the *before* snapshot.
    *   ``redo()`` restores the *after* snapshot.

    The stack is limited to ``max_size`` entries.  When the limit is
    exceeded the oldest entry is discarded (FIFO eviction).

    Pushing a new snapshot **clears the redo stack** because the
    action creates a new branch in the undo history.
    """

    def __init__(self, max_size: int = 50) -> None:
        self._undo_stack: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self._redo_stack: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self._max_size = max_size

    # ── Core Operations ───────────────────────────────────────────────

    def push(
        self,
        before_snapshot: dict[str, Any],
        after_snapshot: dict[str, Any],
    ) -> None:
        """Record a mutation.

        Args:
            before_snapshot: Document state **before** the mutation.
            after_snapshot: Document state **after** the mutation.

        Clears the redo stack because we are starting a new undo branch.
        """
        self._undo_stack.append((before_snapshot, after_snapshot))
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)

    def undo(self) -> dict[str, Any]:
        """Undo the last operation.

        Returns:
            The *before* snapshot to restore.

        Raises:
            IndexError: If there is nothing to undo.
        """
        if not self._undo_stack:
            raise IndexError("Nothing to undo")
        entry = self._undo_stack.pop()
        self._redo_stack.append(entry)
        return entry[0]  # before snapshot

    def redo(self) -> dict[str, Any]:
        """Redo the last undone operation.

        Returns:
            The *after* snapshot to restore.

        Raises:
            IndexError: If there is nothing to redo.
        """
        if not self._redo_stack:
            raise IndexError("Nothing to redo")
        entry = self._redo_stack.pop()
        self._undo_stack.append(entry)
        return entry[1]  # after snapshot

    # ── Query ─────────────────────────────────────────────────────────

    @property
    def can_undo(self) -> bool:
        """True if there is at least one operation to undo."""
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """True if there is at least one operation to redo."""
        return len(self._redo_stack) > 0

    # ── Lifecycle ─────────────────────────────────────────────────────

    def clear(self) -> None:
        """Clear all stored snapshots (e.g., on new document)."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ── Container Protocol ────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._undo_stack)

    def __repr__(self) -> str:
        return (
            f"UndoRedoStack(undo={len(self._undo_stack)}, "
            f"redo={len(self._redo_stack)})"
        )
