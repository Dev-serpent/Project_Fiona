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
        self._modified: bool = False

    # ── Object Management ─────────────────────────────────────────────

    def add_object(self, obj: CADObject, name: str | None = None) -> CADObject:
        if name:
            obj.name = name
        uid_str = str(obj.uid)
        self._objects[uid_str] = obj
        self._objects_by_name[obj.name] = obj
        obj._document = self
        self._modified = True
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
        self._modified = True

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

    # ── Modified Flag ────────────────────────────────────────────────

    @property
    def is_modified(self) -> bool:
        """Whether the document has unsaved changes."""
        return self._modified

    @is_modified.setter
    def is_modified(self, value: bool) -> None:
        self._modified = value

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": str(self.uid),
            "name": self.name,
            "metadata": self._metadata,
            "objects": [obj.to_dict() for obj in self._objects.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        """Reconstruct a Document from a serialized dictionary.

        This is the inverse of to_dict(). Used for undo/restore and loading.
        Unknown object types are skipped gracefully.
        The resulting document will have is_modified == False.
        """
        doc = cls(data.get("name", "Untitled"))

        # Restore UID if present (preserves identity across snapshots)
        if "uid" in data:
            doc.uid = uuid.UUID(data["uid"])

        doc._metadata = dict(data.get("metadata", {}))

        # Type map — maps type name strings to classes
        # Import here to avoid circular imports
        from cad.geometry.primitives import Box, Cylinder, Sphere, Cone, Torus  # noqa: F401
        from cad.sketch.workspace import Sketch  # noqa: F401
        from cad.assembly.assembly import Assembly, PartInstance  # noqa: F401
        from cad.part.features import Pad, Pocket, Revolve  # noqa: F401

        TYPE_MAP: dict[str, type] = {
            "Box": Box,
            "Cylinder": Cylinder,
            "Sphere": Sphere,
            "Cone": Cone,
            "Torus": Torus,
            "Sketch": Sketch,
            "Assembly": Assembly,
            "PartInstance": PartInstance,
            "Pad": Pad,
            "Pocket": Pocket,
            "Revolve": Revolve,
        }

        for obj_data in data.get("objects", []):
            obj_type = obj_data.get("type", "")
            obj_name = obj_data.get("name", "Unknown")
            cls_type = TYPE_MAP.get(obj_type)
            if cls_type is None:
                # Skip unknown types gracefully
                continue

            # Create object (this calls _define_properties which sets defaults)
            obj = cls_type(obj_name)

            # Restore label if present
            if "label" in obj_data:
                obj.label = obj_data["label"]

            # Restore UID (preserve identity across snapshots for undo/redo)
            if "uid" in obj_data:
                obj.uid = uuid.UUID(obj_data["uid"])

            # Restore properties (use _value directly to avoid triggering change events)
            for prop_name, prop_data in obj_data.get("properties", {}).items():
                prop = obj.get_property(prop_name)
                if prop is not None:
                    prop._value = prop_data.get("value", prop._default)

            # Restore dependencies
            if "dependencies" in obj_data:
                obj._dependencies = list(obj_data["dependencies"])

            doc.add_object(obj)

        # Loading from dict is not a modification
        doc._modified = False
        return doc

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
