"""Document — the top-level container for all CAD objects in a project."""

from __future__ import annotations

import uuid
from typing import Any

from cad.core.object import CADObject


class Document:
    """A CAD document holds all objects (geometry, sketches, features, assemblies).

    The document owns the dependency graph and manages recomputation.
    """

    def __init__(self, name: str = "Untitled") -> None:
        self.uid = uuid.uuid4()
        self.name = name
        self._objects: dict[str, CADObject] = {}  # uid → object
        self._objects_by_name: dict[str, CADObject] = {}
        self._metadata: dict[str, Any] = {
            "author": "",
            "description": "",
            "created": None,
            "modified": None,
        }

    # ── Object Management ─────────────────────────────────────────────

    def add_object(self, obj: CADObject, name: str | None = None) -> CADObject:
        if name:
            obj.name = name
        uid_str = str(obj.uid)
        self._objects[uid_str] = obj
        self._objects_by_name[obj.name] = obj
        obj._document = self
        return obj

    def remove_object(self, obj: CADObject) -> None:
        uid_str = str(obj.uid)
        self._objects.pop(uid_str, None)
        self._objects_by_name.pop(obj.name, None)
        obj._document = None
        # Clean up dependency references
        for other in list(self._objects.values()):
            if uid_str in other._dependencies:
                other._dependencies.remove(uid_str)
            if uid_str in other._dependents:
                other._dependents.remove(uid_str)

    def get_object(self, uid_or_name: str) -> CADObject | None:
        if uid_or_name in self._objects:
            return self._objects[uid_or_name]
        return self._objects_by_name.get(uid_or_name)

    def find_by_type(self, cls: type) -> list[CADObject]:
        return [obj for obj in self._objects.values() if isinstance(obj, cls)]

    def find_by_name(self, name: str) -> CADObject | None:
        return self._objects_by_name.get(name)

    @property
    def objects(self) -> list[CADObject]:
        return list(self._objects.values())

    @property
    def object_count(self) -> int:
        return len(self._objects)

    # ── Recomputation ────────────────────────────────────────────────

    def recompute(self) -> None:
        """Recompute all dirty objects in dependency order."""
        sorted_objs = self._topological_sort()
        for obj in sorted_objs:
            if obj.is_dirty():
                obj.recompute()

    def _topological_sort(self) -> list[CADObject]:
        """Topological sort of objects based on dependency DAG."""
        visited: set[str] = set()
        result: list[CADObject] = []

        def dfs(uid: str) -> None:
            if uid in visited:
                return
            visited.add(uid)
            obj = self._objects.get(uid)
            if obj:
                for dep_uid in obj._dependencies:
                    dfs(dep_uid)
                result.append(obj)

        for uid in self._objects:
            dfs(uid)

        return result

    # ── Query ────────────────────────────────────────────────────────

    def get_all_property_values(self, property_name: str) -> dict[str, Any]:
        return {obj.name: obj.get_property_value(property_name)
                for obj in self._objects.values()
                if obj.get_property(property_name) is not None}

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": str(self.uid),
            "name": self.name,
            "metadata": self._metadata,
            "objects": [obj.to_dict() for obj in self._objects.values()],
        }

    def clear(self) -> None:
        self._objects.clear()
        self._objects_by_name.clear()

    def __repr__(self) -> str:
        return f"Document('{self.name}', {self.object_count} objects)"

    def __len__(self) -> int:
        return self.object_count


# ── Module-Level Helpers ─────────────────────────────────────────────

_default_document: Document | None = None


def new_document(name: str = "Untitled") -> Document:
    """Create a new document and set it as the active default."""
    global _default_document
    doc = Document(name)
    _default_document = doc
    return doc


def active_document() -> Document | None:
    return _default_document
