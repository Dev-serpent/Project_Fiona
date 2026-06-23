"""Tests for the DocumentManager implementation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from cad.server._document_manager import DocumentManager
from fiona.interfaces import (
    DocumentHandle,
    DocumentLoadError,
    DocumentNotOpen,
    DocumentSaveError,
)


class TestDocumentManagerCreate:
    """Tests for document creation."""

    def test_create_default(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document()
        assert isinstance(handle, DocumentHandle)
        assert handle.name == "Untitled"
        assert handle.doc_id is not None
        assert handle.path is None
        assert handle.object_count == 0
        assert handle.is_modified is False

    def test_create_named(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document(name="MyModel")
        assert handle.name == "MyModel"
        assert handle.path is None

    def test_create_increments_count(self) -> None:
        mgr = DocumentManager()
        h1 = mgr.create_document("Doc1")
        h2 = mgr.create_document("Doc2")
        assert h1.doc_id != h2.doc_id

    def test_created_document_is_active(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document()
        doc = mgr.active_document()
        assert doc is not None
        assert str(doc.uid) == handle.doc_id


class TestDocumentManagerGet:
    """Tests for ``get_document()``."""

    def test_get_existing(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document("Test")
        doc = mgr.get_document(handle.doc_id)
        assert doc is not None
        assert doc.name == "Test"

    def test_get_nonexistent(self) -> None:
        mgr = DocumentManager()
        doc = mgr.get_document("nonexistent-id")
        assert doc is None

    def test_get_after_close(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document("Temp")
        mgr.close_document(handle.doc_id)
        doc = mgr.get_document(handle.doc_id)
        assert doc is None


class TestDocumentManagerList:
    """Tests for ``list_documents()``."""

    def test_list_empty(self) -> None:
        mgr = DocumentManager()
        assert mgr.list_documents() == []

    def test_list_multiple(self) -> None:
        mgr = DocumentManager()
        mgr.create_document("A")
        mgr.create_document("B")
        mgr.create_document("C")
        handles = mgr.list_documents()
        assert len(handles) == 3
        names = {h.name for h in handles}
        assert names == {"A", "B", "C"}


class TestDocumentManagerClose:
    """Tests for ``close_document()``."""

    def test_close_existing(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document()
        mgr.close_document(handle.doc_id)
        assert mgr.list_documents() == []

    def test_close_invalid_raises(self) -> None:
        mgr = DocumentManager()
        with pytest.raises(DocumentNotOpen):
            mgr.close_document("nonexistent")

    def test_close_updates_active(self) -> None:
        mgr = DocumentManager()
        h1 = mgr.create_document("First")
        h2 = mgr.create_document("Second")
        mgr.close_document(h1.doc_id)
        active = mgr.active_document()
        assert active is not None
        assert str(active.uid) == h2.doc_id

    def test_close_last_document(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document()
        mgr.close_document(handle.doc_id)
        assert mgr.active_document() is None


class TestDocumentManagerActive:
    """Tests for ``active_document()``."""

    def test_active_none_when_empty(self) -> None:
        mgr = DocumentManager()
        assert mgr.active_document() is None

    def test_active_is_first_created(self) -> None:
        mgr = DocumentManager()
        h1 = mgr.create_document("First")
        mgr.create_document("Second")
        active = mgr.active_document()
        assert active is not None
        assert str(active.uid) == h1.doc_id


class TestDocumentManagerSaveOpen:
    """Tests for ``save_document()`` and ``open_document()``."""

    def test_save_and_open_roundtrip(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document("Roundtrip")

        # Add an object via the doc directly
        doc = mgr.get_document(handle.doc_id)
        from cad.geometry.primitives import Box
        doc.add_object(Box("TestBox"))

        with tempfile.NamedTemporaryFile(
            suffix=".cad", delete=False, mode="w"
        ) as f:
            tmp_path = f.name

        try:
            saved = mgr.save_document(handle.doc_id, tmp_path)
            assert Path(saved).exists()

            # Close and reopen
            mgr.close_document(handle.doc_id)
            h2 = mgr.open_document(tmp_path)
            assert h2.name == "Roundtrip"
            assert h2.object_count == 1

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_save_without_path(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document("NoPath")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.cad")
            saved = mgr.save_document(handle.doc_id, path)
            assert Path(saved).exists()

    def test_save_invalid_doc_id(self) -> None:
        mgr = DocumentManager()
        with pytest.raises(DocumentNotOpen):
            mgr.save_document("nonexistent")

    def test_open_nonexistent_file(self) -> None:
        mgr = DocumentManager()
        with pytest.raises(DocumentLoadError):
            mgr.open_document("/nonexistent/path/file.cad")

    def test_open_invalid_file(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".cad", mode="w", delete=False
        ) as f:
            f.write("this is not valid cad json")
            tmp_path = f.name

        mgr = DocumentManager()
        try:
            with pytest.raises(DocumentLoadError):
                mgr.open_document(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_save_updates_path(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document("SavePath")
        with tempfile.NamedTemporaryFile(
            suffix=".cad", delete=False, mode="w"
        ) as f:
            tmp_path = f.name

        try:
            mgr.save_document(handle.doc_id, tmp_path)
            handles = mgr.list_documents()
            h = next(h for h in handles if h.doc_id == handle.doc_id)
            assert h.path == str(Path(tmp_path).resolve())
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_open_updates_active(self) -> None:
        """Opening a document should set it as active if no active doc exists."""
        mgr = DocumentManager()
        with tempfile.NamedTemporaryFile(suffix=".cad", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            # Create and save a doc first
            h = mgr.create_document("Test")
            mgr.save_document(h.doc_id, tmp_path)
            mgr.close_document(h.doc_id)

            h2 = mgr.open_document(tmp_path)
            active = mgr.active_document()
            assert active is not None
            assert str(active.uid) == h2.doc_id
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestDocumentManagerHandle:
    """Tests for DocumentHandle correctness."""

    def test_handle_has_required_fields(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document("Fields")
        assert hasattr(handle, "doc_id")
        assert hasattr(handle, "name")
        assert hasattr(handle, "path")
        assert hasattr(handle, "object_count")
        assert hasattr(handle, "is_modified")
        assert hasattr(handle, "created_at")
        assert hasattr(handle, "modified_at")

    def test_handle_immutable(self) -> None:
        mgr = DocumentManager()
        handle = mgr.create_document()
        # DocumentHandle is a frozen dataclass
        with pytest.raises(AttributeError):
            handle.name = "Changed"  # type: ignore[misc]
