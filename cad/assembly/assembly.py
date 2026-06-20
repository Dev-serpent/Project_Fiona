"""Assembly system — hierarchical part and subassembly management."""

from __future__ import annotations

from typing import Any

from cad.core.object import CADObject, PropertyType
from cad.geometry.math import Vector3, Matrix4


class PartInstance(CADObject):
    """An instance of a part/feature placed in an assembly."""

    def __init__(self, name: str,
                 source: CADObject | None = None,
                 placement: Matrix4 | None = None) -> None:
        super().__init__(name)
        self._source = source
        self._placement = placement or Matrix4.identity()
        if source:
            self.add_dependency(source)

    def _define_properties(self) -> None:
        self.add_property("px", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("py", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("pz", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("rx", PropertyType.FLOAT, 0.0, unit="deg")
        self.add_property("ry", PropertyType.FLOAT, 0.0, unit="deg")
        self.add_property("rz", PropertyType.FLOAT, 0.0, unit="deg")
        self.add_property("sx", PropertyType.FLOAT, 1.0)
        self.add_property("sy", PropertyType.FLOAT, 1.0)
        self.add_property("sz", PropertyType.FLOAT, 1.0)

    def get_transform(self) -> Matrix4:
        t = Matrix4.translation(
            self.get_property_value("px"),
            self.get_property_value("py"),
            self.get_property_value("pz"),
        )
        rx = Matrix4.rotation_x(math.radians(self.get_property_value("rx")))
        ry = Matrix4.rotation_y(math.radians(self.get_property_value("ry")))
        rz = Matrix4.rotation_z(math.radians(self.get_property_value("rz")))
        s = Matrix4.scaling(
            self.get_property_value("sx"),
            self.get_property_value("sy"),
            self.get_property_value("sz"),
        )
        return t @ rz @ ry @ rx @ s

    def recompute(self) -> None:
        self._dirty = False


class AssemblyConstraint(CADObject):
    """A constraint between two parts in an assembly (mate, align, etc.)."""

    def __init__(self, name: str,
                 part_a: PartInstance, part_b: PartInstance,
                 constraint_type: str = "coincident") -> None:
        self._part_a = part_a
        self._part_b = part_b
        self._constraint_type = constraint_type
        super().__init__(name)
        self.add_dependency(part_a)
        self.add_dependency(part_b)

    def _define_properties(self) -> None:
        self.add_property("type", PropertyType.STRING, self._constraint_type, readonly=True)
        self.add_property("part_a", PropertyType.STRING, self._part_a.name, readonly=True)
        self.add_property("part_b", PropertyType.STRING, self._part_b.name, readonly=True)

    def recompute(self) -> None:
        self._dirty = False


class Assembly(CADObject):
    """Top-level assembly containing parts and subassemblies."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._parts: dict[str, PartInstance] = {}
        self._subassemblies: dict[str, Assembly] = {}
        self._constraints: list[AssemblyConstraint] = []

    def _define_properties(self) -> None:
        self.add_property("part_count", PropertyType.INT, 0, readonly=True)
        self.add_property("subassembly_count", PropertyType.INT, 0, readonly=True)
        self.add_property("constraint_count", PropertyType.INT, 0, readonly=True)

    def add_part(self, part: PartInstance) -> PartInstance:
        self._parts[part.name] = part
        self.add_dependency(part)
        self.set_property("part_count", len(self._parts))
        return part

    def remove_part(self, name: str) -> None:
        self._parts.pop(name, None)
        self.set_property("part_count", len(self._parts))

    def get_part(self, name: str) -> PartInstance | None:
        return self._parts.get(name)

    @property
    def parts(self) -> list[PartInstance]:
        return list(self._parts.values())

    def add_subassembly(self, assembly: Assembly) -> Assembly:
        self._subassemblies[assembly.name] = assembly
        self.add_dependency(assembly)
        self.set_property("subassembly_count", len(self._subassemblies))
        return assembly

    @property
    def subassemblies(self) -> list[Assembly]:
        return list(self._subassemblies.values())

    def add_constraint(self, constraint: AssemblyConstraint) -> None:
        self._constraints.append(constraint)
        self.add_dependency(constraint)
        self.set_property("constraint_count", len(self._constraints))

    @property
    def constraints(self) -> list[AssemblyConstraint]:
        return list(self._constraints)

    def get_all_parts(self) -> list[PartInstance]:
        """Recursively collect all parts including subassemblies."""
        result = list(self._parts.values())
        for sub in self._subassemblies.values():
            result.extend(sub.get_all_parts())
        return result

    def recompute(self) -> None:
        self._dirty = False

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["parts"] = [p.to_dict() for p in self._parts.values()]
        data["subassemblies"] = [s.to_dict() for s in self._subassemblies.values()]
        data["constraints"] = [c.to_dict() for c in self._constraints]
        return data


import math  # noqa: E402
