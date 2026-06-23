"""Full :class:`IDocumentManager` implementation.

Manages the lifecycle of CAD documents in memory with thread-safe
access and file I/O via :class:`CadSerializer`.
"""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any

from cad.core.document import Document
from cad.io.native_format import CadSerializer
from fiona.interfaces import (
    DocumentClosed,
    DocumentCreated,
    DocumentHandle,
    DocumentLoadError,
    DocumentModified,
    DocumentNotOpen,
    DocumentSaveError,
    DocumentSaved,
    EventBus,
    IDocumentManager,
)


class DocumentManager(IDocumentManager):
    """Thread-safe in-memory document manager.

    Documents are stored in a dict keyed by their UUID string.
    The first document created becomes the active document.
    Thread-safety is guaranteed via ``threading.Lock``.

    If *event_bus* is provided, lifecycle events (``DocumentCreated``,
    ``DocumentModified``, ``DocumentSaved``, ``DocumentClosed``) are
    published automatically.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._lock = threading.Lock()
        self._documents: dict[str, Document] = {}
        self._active_doc_id: str | None = None
        # Track saved paths: doc_id → str path
        self._saved_paths: dict[str, str] = {}
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # IDocumentManager implementation
    # ------------------------------------------------------------------

    def create_document(self, name: str = "Untitled") -> DocumentHandle:
        """Create a new, empty document and register it.

        Args:
            name: Human-readable name for the document.

        Returns:
            A :class:`DocumentHandle` for the new document.
        """
        doc = Document(name=name)
        doc_id = str(doc.uid)

        with self._lock:
            self._documents[doc_id] = doc
            if self._active_doc_id is None:
                self._active_doc_id = doc_id

        self._publish(DocumentCreated(timestamp=time.time(), source="DocumentManager", doc_id=doc_id))
        return self._build_handle(doc, doc_id)

    def open_document(self, path: str) -> DocumentHandle:
        """Load a ``.cad`` file from disk and register it.

        Args:
            path: Filesystem path to the ``.cad`` file.

        Returns:
            A :class:`DocumentHandle` for the opened document.

        Raises:
            DocumentLoadError: The file could not be read or parsed.
        """
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            raise DocumentLoadError(f"File not found: {resolved}")

        try:
            doc = CadSerializer.deserialize_from_file(str(resolved))
        except Exception as exc:
            raise DocumentLoadError(
                f"Failed to load document from {resolved}: {exc}"
            ) from exc

        doc_id = str(doc.uid)
        with self._lock:
            self._documents[doc_id] = doc
            self._saved_paths[doc_id] = str(resolved)
            if self._active_doc_id is None:
                self._active_doc_id = doc_id

        return self._build_handle(doc, doc_id, saved_path=str(resolved))

    def save_document(self, doc_id: str, path: str | None = None) -> str:
        """Persist a document to disk.

        Args:
            doc_id: UUID of the document to save.
            path: Destination file path.  Uses the document's current
                path if *None*.

        Returns:
            The absolute path where the document was saved.

        Raises:
            DocumentNotOpen: No document with *doc_id* is open.
            DocumentSaveError: The file could not be written.
        """
        doc = self.get_document(doc_id)
        if doc is None:
            raise DocumentNotOpen(f"Document not open: {doc_id}")

        # Resolve save path
        with self._lock:
            current_path = self._saved_paths.get(doc_id)
        save_path = Path(path or current_path or f"{doc.name}.cad").expanduser().resolve()

        # Ensure parent directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            CadSerializer.serialize_to_file(doc, str(save_path))
        except Exception as exc:
            raise DocumentSaveError(
                f"Failed to save document to {save_path}: {exc}"
            ) from exc

        with self._lock:
            self._saved_paths[doc_id] = str(save_path)
            doc.is_modified = False

        self._publish(DocumentSaved(timestamp=time.time(), source="DocumentManager", doc_id=doc_id))
        return str(save_path)

    def get_document(self, doc_id: str) -> Document | None:
        """Retrieve a document by its identifier.

        Args:
            doc_id: UUID of the target document.

        Returns:
            The :class:`Document` instance, or *None*.
        """
        with self._lock:
            return self._documents.get(doc_id)

    def close_document(self, doc_id: str) -> None:
        """Close a document and release its resources.

        Args:
            doc_id: UUID of the document to close.

        Raises:
            DocumentNotOpen: The document is not open.
        """
        with self._lock:
            if doc_id not in self._documents:
                raise DocumentNotOpen(f"Document not open: {doc_id}")
            del self._documents[doc_id]
            self._saved_paths.pop(doc_id, None)
            if self._active_doc_id == doc_id:
                # Pick the next available document as active, or None
                self._active_doc_id = next(
                    iter(self._documents.keys()), None
                )

        self._publish(DocumentClosed(timestamp=time.time(), source="DocumentManager", doc_id=doc_id))

    def list_documents(self) -> list[DocumentHandle]:
        """Return metadata for every open document.

        Returns:
            A list of :class:`DocumentHandle` objects.
        """
        with self._lock:
            handles: list[DocumentHandle] = []
            for doc_id, doc in self._documents.items():
                saved_path = self._saved_paths.get(doc_id)
                handles.append(self._build_handle(doc, doc_id, saved_path))
            return handles

    def active_document(self) -> Document | None:
        """Return the currently active document.

        Returns:
            The active :class:`Document`, or *None*.
        """
        with self._lock:
            if self._active_doc_id is None:
                return None
            return self._documents.get(self._active_doc_id)

    # ------------------------------------------------------------------
    # Internal helpers — used by server components
    # ------------------------------------------------------------------

    def _replace_document(self, doc_id: str, new_doc: Document) -> None:
        """Replace the in-memory document for *doc_id*.

        This is used by :class:`CommandExecutor` to restore document
        state from undo/redo snapshots.  Not part of the public
        :class:`IDocumentManager` interface.
        """
        with self._lock:
            if doc_id in self._documents:
                self._documents[doc_id] = new_doc

        self._publish(DocumentModified(timestamp=time.time(), source="DocumentManager", doc_id=doc_id))

    # ------------------------------------------------------------------
    # Handle building
    # ------------------------------------------------------------------

    def _build_handle(
        self,
        doc: Document,
        doc_id: str,
        saved_path: str | None = None,
    ) -> DocumentHandle:
        """Build a :class:`DocumentHandle` from a document instance."""
        created_at = _extract_timestamp(doc_id)

        return DocumentHandle(
            doc_id=doc_id,
            name=doc.name,
            path=saved_path,
            object_count=doc.object_count,
            is_modified=doc.is_modified,
            created_at=created_at,
            modified_at=time.time() if doc.is_modified else created_at,
        )

    def _publish(self, event: Any) -> None:
        """Publish an event on the optional event bus."""
        if self._event_bus is not None:
            self._event_bus.publish(event)


def _extract_timestamp(doc_id: str) -> float:
    """Extract an approximate creation timestamp from a UUID string.

    For UUID1, the timestamp is embedded.  For UUID4, returns current time.
    """
    try:
        u = uuid.UUID(doc_id)
        if u.version == 1:
            return (u.time - 0x01B21DD213814000) / 1e7
    except (ValueError, AttributeError):
        pass
    return time.time()
