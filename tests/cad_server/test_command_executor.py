"""Tests for the CommandExecutor implementation."""

from __future__ import annotations

import pytest

from cad.commands.builtins import register_builtin_commands
from cad.commands.registry import CommandRegistry
from cad.server._command_executor import CommandExecutor
from cad.server._document_manager import DocumentManager
from fiona.interfaces import (
    CommandNotFound,
    CommandResult,
    DocumentNotOpen,
    NothingToRedo,
    NothingToUndo,
)


@pytest.fixture
def registry() -> CommandRegistry:
    r = CommandRegistry()
    register_builtin_commands(r)
    return r


@pytest.fixture
def doc_manager() -> DocumentManager:
    return DocumentManager()


@pytest.fixture
def executor(registry: CommandRegistry, doc_manager: DocumentManager) -> CommandExecutor:
    return CommandExecutor(registry=registry, doc_manager=doc_manager)


def _create_doc(doc_manager: DocumentManager, name: str = "Test") -> str:
    handle = doc_manager.create_document(name)
    return handle.doc_id


class TestCommandExecutorExecute:
    """Tests for ``execute()``."""

    def test_execute_create_box(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        result = executor.execute(doc_id, "create_box", width=10, height=20, depth=30)
        assert isinstance(result, CommandResult)
        assert result.success is True
        assert "create_box" in result.message

    def test_execute_creates_objects(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        result = executor.execute(doc_id, "create_box", width=10, height=20, depth=30, name="MyBox")
        assert len(result.created_objects) == 1
        assert result.document_snapshot is not None
        assert len(result.document_snapshot.get("objects", [])) == 1

    def test_execute_modifies_document(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        doc = doc_manager.get_document(doc_id)
        assert doc is not None
        assert doc.object_count == 0
        executor.execute(doc_id, "create_box", width=10, height=10, depth=10)
        assert doc.object_count == 1

    def test_execute_unknown_command(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        with pytest.raises(CommandNotFound):
            executor.execute(doc_id, "nonexistent_command")

    def test_execute_invalid_doc_id(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        with pytest.raises(DocumentNotOpen):
            executor.execute("nonexistent", "create_box")

    def test_execute_records_undo(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        executor.execute(doc_id, "create_box", width=5, height=5, depth=5)
        assert executor.can_undo(doc_id) is True

    def test_execute_cylinder(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        result = executor.execute(doc_id, "create_cylinder", radius=5, height=10)
        assert result.success is True
        assert len(result.created_objects) == 1

    def test_execute_sphere(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        result = executor.execute(doc_id, "create_sphere", radius=10)
        assert result.success is True

    def test_execute_multiple_commands(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        executor.execute(doc_id, "create_box", width=5, height=5, depth=5, name="Box1")
        executor.execute(doc_id, "create_cylinder", radius=3, height=8, name="Cyl1")
        doc = doc_manager.get_document(doc_id)
        assert doc is not None
        assert doc.object_count == 2

    def test_execute_timing(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        result = executor.execute(doc_id, "create_box")
        assert result.execution_time_ms >= 0


class TestCommandExecutorUndoRedo:
    """Tests for undo/redo functionality."""

    def test_undo_restores_state(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        doc = doc_manager.get_document(doc_id)
        assert doc is not None
        executor.execute(doc_id, "create_box", name="Box1")
        assert doc.object_count == 1

        snapshot = executor.undo(doc_id)
        assert doc.object_count == 0
        assert len(snapshot.get("objects", [])) == 0

    def test_redo_restores_state(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        executor.execute(doc_id, "create_box", name="Box1")
        executor.undo(doc_id)
        snapshot = executor.redo(doc_id)
        doc = doc_manager.get_document(doc_id)
        assert doc is not None
        assert doc.object_count == 1
        assert len(snapshot.get("objects", [])) == 1

    def test_undo_nothing_raises(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        with pytest.raises(NothingToUndo):
            executor.undo(doc_id)

    def test_redo_nothing_raises(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        with pytest.raises(NothingToRedo):
            executor.redo(doc_id)

    def test_can_undo(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        assert executor.can_undo(doc_id) is False
        executor.execute(doc_id, "create_box")
        assert executor.can_undo(doc_id) is True
        executor.undo(doc_id)
        assert executor.can_undo(doc_id) is False

    def test_can_redo(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        assert executor.can_redo(doc_id) is False
        executor.execute(doc_id, "create_box")
        executor.undo(doc_id)
        assert executor.can_redo(doc_id) is True
        executor.redo(doc_id)
        assert executor.can_redo(doc_id) is False

    def test_new_command_clears_redo(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        executor.execute(doc_id, "create_box", name="Box1")
        executor.undo(doc_id)
        assert executor.can_redo(doc_id) is True
        executor.execute(doc_id, "create_cylinder", name="Cyl1")
        assert executor.can_redo(doc_id) is False

    def test_clear_history(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        executor.execute(doc_id, "create_box")
        executor.execute(doc_id, "create_cylinder")
        executor.clear_history(doc_id)
        assert executor.can_undo(doc_id) is False
        assert executor.can_redo(doc_id) is False


class TestCommandExecutorErrors:
    """Tests for error conditions."""

    def test_undo_invalid_doc(self, executor: CommandExecutor) -> None:
        with pytest.raises(DocumentNotOpen):
            executor.undo("nonexistent")

    def test_redo_invalid_doc(self, executor: CommandExecutor) -> None:
        with pytest.raises(DocumentNotOpen):
            executor.redo("nonexistent")

    def test_can_undo_invalid_doc(self, executor: CommandExecutor) -> None:
        with pytest.raises(DocumentNotOpen):
            executor.can_undo("nonexistent")

    def test_can_redo_invalid_doc(self, executor: CommandExecutor) -> None:
        with pytest.raises(DocumentNotOpen):
            executor.can_redo("nonexistent")

    def test_clear_history_invalid_doc(self, executor: CommandExecutor) -> None:
        with pytest.raises(DocumentNotOpen):
            executor.clear_history("nonexistent")

    def test_execute_with_invalid_args(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        # create_box with a non-numeric width should still work (it'll
        # be passed to the command which might handle it, but won't crash
        # the executor)
        result = executor.execute(doc_id, "create_box", width="invalid")
        assert result.success is True  # Command still executes with defaults or error


class TestCommandResult:
    """Tests for CommandResult structure."""

    def test_result_fields(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        result = executor.execute(doc_id, "create_box", width=5, height=10, depth=15)
        assert hasattr(result, "success")
        assert hasattr(result, "message")
        assert hasattr(result, "document_snapshot")
        assert hasattr(result, "created_objects")
        assert hasattr(result, "modified_objects")
        assert hasattr(result, "deleted_objects")
        assert hasattr(result, "execution_time_ms")
        assert hasattr(result, "warnings")

    def test_result_created_objects(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        result = executor.execute(doc_id, "create_box", name="NewBox")
        assert len(result.created_objects) > 0
        # created_objects should contain UUIDs
        for uid in result.created_objects:
            assert isinstance(uid, str)

    def test_result_snapshot_is_dict(self, executor: CommandExecutor, doc_manager: DocumentManager) -> None:
        doc_id = _create_doc(doc_manager)
        result = executor.execute(doc_id, "create_box")
        assert isinstance(result.document_snapshot, dict)
        assert "objects" in result.document_snapshot
        assert "name" in result.document_snapshot
