"""Full :class:`ICommandExecutor` implementation.

Executes named commands against documents with per-document
undo/redo stacks backed by snapshot-based state recovery.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from cad.commands.registry import CommandRegistry
from cad.commands.command_stack import UndoRedoStack
from cad.core.document import Document
from cad.server._document_manager import DocumentManager
from fiona.interfaces import (
    CommandError,
    CommandNotFound,
    CommandResult,
    DocumentNotOpen,
    ICommandExecutor,
    InvalidArguments,
    NothingToRedo,
    NothingToUndo,
)

# Maximum number of undo entries per document
_DEFAULT_MAX_UNDO = 50


class CommandExecutor(ICommandExecutor):
    """Thread-safe command executor with snapshot-based undo/redo.

    Each document gets its own :class:`UndoRedoStack`.  Before every
    ``execute()`` call a snapshot of the document is saved so that
    undo restores the previous state.

    Attributes:
        registry: The shared :class:`CommandRegistry` instance.
    """

    def __init__(
        self,
        registry: CommandRegistry,
        doc_manager: DocumentManager | None = None,
        max_undo: int = _DEFAULT_MAX_UNDO,
    ) -> None:
        self._registry = registry
        self._doc_manager: DocumentManager | None = doc_manager
        self._lock = threading.Lock()
        # doc_id → UndoRedoStack
        self._stacks: dict[str, UndoRedoStack] = {}
        self._max_undo = max_undo

    # ------------------------------------------------------------------
    # ICommandExecutor implementation
    # ------------------------------------------------------------------

    def execute(
        self,
        doc_id: str,
        command_name: str,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute a named command on a document.

        Args:
            doc_id: UUID of the target document.
            command_name: Registered command name.
            **kwargs: Command-specific keyword arguments.

        Returns:
            A :class:`CommandResult` describing the outcome.

        Raises:
            DocumentNotOpen: No document with *doc_id* is open.
            CommandNotFound: *command_name* is not in the registry.
            InvalidArguments: The supplied arguments are invalid.
        """
        doc = self._require_document(doc_id)

        # Look up command
        cmd = self._registry.get(command_name)
        if cmd is None:
            raise CommandNotFound(
                f"Command not found: {command_name!r}. "
                f"Available: {', '.join(self._registry.list_names())}"
            )

        # Snapshot before execution
        before = doc.to_dict()
        start = time.perf_counter()

        try:
            result = cmd.execute(doc, **kwargs)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(
                f"Command '{command_name}' failed: {exc}"
            ) from exc

        elapsed = (time.perf_counter() - start) * 1000

        # Snapshot after execution
        after = doc.to_dict()

        # Record on undo stack
        stack = self._get_stack(doc_id)
        stack.push(before, after)

        # Build CommandResult
        created, modified, deleted = _classify_changes(before, after)

        warnings: list[str] = []
        message = f"Command '{command_name}' executed successfully"
        if not result_is_success(result):
            message = f"Command '{command_name}' completed with issues"

        return CommandResult(
            success=True,
            message=message,
            document_snapshot=after,
            created_objects=created,
            modified_objects=modified,
            deleted_objects=deleted,
            execution_time_ms=elapsed,
            warnings=warnings,
        )

    def undo(self, doc_id: str) -> dict[str, Any]:
        """Reverse the most recent command.

        Args:
            doc_id: UUID of the target document.

        Returns:
            Document snapshot after undo.

        Raises:
            DocumentNotOpen: No document with *doc_id* is open.
            NothingToUndo: The undo stack is empty.
        """
        doc = self._require_document(doc_id)
        stack = self._get_stack(doc_id)

        try:
            before_snapshot = stack.undo()
        except IndexError:
            raise NothingToUndo("Nothing to undo") from None

        # Restore document in-place (mutate existing object so all
        # references held by the document manager and other callers
        # remain valid).
        self._apply_snapshot(doc, before_snapshot)
        return doc.to_dict()

    def redo(self, doc_id: str) -> dict[str, Any]:
        """Re-apply the most recently undone command.

        Args:
            doc_id: UUID of the target document.

        Returns:
            Document snapshot after redo.

        Raises:
            DocumentNotOpen: No document with *doc_id* is open.
            NothingToRedo: The redo stack is empty.
        """
        doc = self._require_document(doc_id)
        stack = self._get_stack(doc_id)

        try:
            after_snapshot = stack.redo()
        except IndexError:
            raise NothingToRedo("Nothing to redo") from None

        # Restore document in-place
        self._apply_snapshot(doc, after_snapshot)
        return doc.to_dict()

    def can_undo(self, doc_id: str) -> bool:
        """Check whether undo is available.

        Args:
            doc_id: UUID of the target document.

        Returns:
            True if the undo stack is non-empty.
        """
        self._require_document(doc_id)
        stack = self._get_stack(doc_id)
        return stack.can_undo

    def can_redo(self, doc_id: str) -> bool:
        """Check whether redo is available.

        Args:
            doc_id: UUID of the target document.

        Returns:
            True if the redo stack is non-empty.
        """
        self._require_document(doc_id)
        stack = self._get_stack(doc_id)
        return stack.can_redo

    def clear_history(self, doc_id: str) -> None:
        """Clear both undo and redo stacks for a document.

        Args:
            doc_id: UUID of the target document.

        Raises:
            DocumentNotOpen: No document with *doc_id* is open.
        """
        self._require_document(doc_id)
        with self._lock:
            stack = self._stacks.get(doc_id)
            if stack is not None:
                stack.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_document(self, doc_id: str) -> Document:
        """Return the document or raise :class:`DocumentNotOpen`."""
        doc: Document | None = None
        if self._doc_manager is not None:
            doc = self._doc_manager.get_document(doc_id)
        if doc is None:
            raise DocumentNotOpen(f"Document not open: {doc_id}")
        return doc

    def _get_stack(self, doc_id: str) -> UndoRedoStack:
        """Return (or create) the undo/redo stack for *doc_id*."""
        with self._lock:
            if doc_id not in self._stacks:
                self._stacks[doc_id] = UndoRedoStack(max_size=self._max_undo)
            return self._stacks[doc_id]

    @staticmethod
    def _apply_snapshot(doc: Document, snapshot: dict[str, Any]) -> None:
        """Restore a document's state from a snapshot dict **in-place**.

        Mutates the existing ``doc`` object so that all external references
        remain valid.  Equivalent to ``Document.from_dict()`` but operates
        on an existing instance.
        """
        doc.clear()

        # Restore metadata
        doc.name = snapshot.get("name", doc.name)
        doc._metadata = dict(snapshot.get("metadata", {}))

        # Re-create all objects from the snapshot
        from cad.core.document import Document as DocCls
        temp_doc = DocCls.from_dict(snapshot)
        for obj in temp_doc.objects:
            doc.add_object(obj)

        doc.is_modified = False


def _classify_changes(
    before: dict[str, Any],
    after: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    """Compare two document snapshots and classify object changes.

    Returns:
        A tuple ``(created_uids, modified_uids, deleted_uids)``.
    """
    before_objs = {o.get("uid", ""): o for o in before.get("objects", [])}
    after_objs = {o.get("uid", ""): o for o in after.get("objects", [])}

    before_uids = set(before_objs)
    after_uids = set(after_objs)

    created = list(after_uids - before_uids)
    deleted = list(before_uids - after_uids)

    modified: list[str] = []
    for uid in before_uids & after_uids:
        if before_objs[uid] != after_objs[uid]:
            modified.append(uid)

    return created, modified, deleted


def result_is_success(result: Any) -> bool:
    """Heuristic to determine if a command result indicates success.

    Most commands return the created object, which is truthy.
    Commands that return *None* or raise are considered problematic.
    """
    if result is None:
        return False
    if isinstance(result, bool):
        return result
    return True
