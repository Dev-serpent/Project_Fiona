"""Base CAD Object — every model entity derives from this."""

from __future__ import annotations

import uuid
from typing import Any, Callable

from cad.core.property import Property, PropertyType


class CADObject:
    """Base class for all CAD entities (primitives, sketches, features, etc.).

    Each object has:
    - A unique identifier
    - A name and label
    - Typed properties with change notification
    - A dependency list (what this object depends on)
    - A list of dependents (what depends on this object)
    - A dirty flag (needs recomputation)
    """

    def __init__(self, name: str, label: str | None = None) -> None:
        self.uid = uuid.uuid4()
        self.name = name
        self.label = label or name
        self._properties: dict[str, Property] = {}
        self._dependencies: list[str] = []  # UIDs of objects we depend on
        self._dependents: list[str] = []    # UIDs of objects depending on us
        self._dirty: bool = True
        self._document = None

        self._define_properties()

    # ── Property System ──────────────────────────────────────────────

    def _define_properties(self) -> None:
        """Override in subclasses to define typed properties."""
        pass

    def add_property(
        self,
        name: str,
        type_: PropertyType,
        value: Any = None,
        default: Any = None,
        description: str = "",
        unit: str = "",
        readonly: bool = False,
        visible: bool = True,
        choices: list[tuple[str, Any]] | None = None,
    ) -> Property:
        prop = Property(name, type_, value, default, description, unit, readonly, visible, choices)
        self._properties[name] = prop
        prop.on_change(lambda n, o, new: self._on_property_changed(n, o, new))
        return prop

    def get_property(self, name: str) -> Property | None:
        return self._properties.get(name)

    def set_property(self, name: str, value: Any) -> None:
        prop = self.get_property(name)
        if prop is None:
            raise KeyError(f"Unknown property: {name}")
        prop.value = value

    def get_property_value(self, name: str) -> Any:
        prop = self.get_property(name)
        if prop is None:
            raise KeyError(f"Unknown property: {name}")
        return prop.value

    @property
    def properties(self) -> dict[str, Property]:
        return dict(self._properties)

    # ── Dependency Tracking ──────────────────────────────────────────

    def add_dependency(self, obj: CADObject) -> None:
        uid_str = str(obj.uid)
        if uid_str not in self._dependencies:
            self._dependencies.append(uid_str)
            obj._dependents.append(str(self.uid))
            self._mark_dirty()

    def get_dependencies(self) -> list[str]:
        return list(self._dependencies)

    def get_dependents(self) -> list[str]:
        return list(self._dependents)

    # ── Dirty / Recomputation ────────────────────────────────────────

    def _mark_dirty(self) -> None:
        self._dirty = True
        # Propagate dirty to all dependents
        if self._document:
            for dep_uid in self._dependents:
                dep_obj = self._document.get_object(dep_uid)
                if dep_obj:
                    dep_obj._mark_dirty()

    def is_dirty(self) -> bool:
        return self._dirty

    def recompute(self) -> None:
        """Recompute this object's geometry/state. Override in subclasses."""
        self._dirty = False

    # ── Events ───────────────────────────────────────────────────────

    def _on_property_changed(self, name: str, old: Any, new: Any) -> None:
        self._mark_dirty()

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": str(self.uid),
            "name": self.name,
            "label": self.label,
            "type": type(self).__name__,
            "properties": {k: v.to_dict() for k, v in self._properties.items()},
            "dependencies": list(self._dependencies),
        }

    # ── Utility ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self.name}')"

    def __str__(self) -> str:
        return f"{self.label} ({type(self).__name__})"
