"""Property system — typed properties with change notifications."""

from __future__ import annotations

import enum
import uuid
from typing import Any, Callable


class PropertyType(enum.Enum):
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"
    VECTOR = "vector"
    POINT = "point"
    OBJECT = "object"
    OBJECT_LIST = "object_list"
    ENUM = "enum"
    COLOR = "color"
    MATRIX = "matrix"


class Property:
    """A typed, observable property on a CADObject."""

    def __init__(
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
    ) -> None:
        self.uid = uuid.uuid4()
        self.name = name
        self.type = type_
        self._value = value if value is not None else default
        self._default = default
        self.description = description
        self.unit = unit
        self.readonly = readonly
        self.visible = visible
        self.choices = choices or []
        self._listeners: list[Callable[[str, Any, Any], None]] = []

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, new_value: Any) -> None:
        old = self._value
        if old != new_value:
            self._value = new_value
            self._notify(old, new_value)

    def on_change(self, callback: Callable[[str, Any, Any], None]) -> Callable:
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def _notify(self, old: Any, new: Any) -> None:
        for cb in self._listeners:
            cb(self.name, old, new)

    def reset(self) -> None:
        self.value = self._default

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self._serialize(self._value),
            "default": self._serialize(self._default),
            "description": self.description,
            "unit": self.unit,
            "readonly": self.readonly,
            "visible": self.visible,
        }

    @staticmethod
    def _serialize(val: Any) -> Any:
        if hasattr(val, "to_dict"):
            return val.to_dict()
        if isinstance(val, (list, tuple)):
            return [Property._serialize(v) for v in val]
        if hasattr(val, "__float__"):
            return float(val)
        return val

    def __repr__(self) -> str:
        return f"Property({self.name}={self._value!r})"
