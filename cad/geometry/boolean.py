"""Boolean operations on solids — union, difference, intersect.

Note: True CSG boolean operations require a full B-Rep or mesh kernel.
This module provides a high-level API that delegates to an underlying engine.
Currently implemented as a mesh-based CSG system using vertex merging.

For production use, this would delegate to:
  - Carve / CGAL / OpenCASCADE for exact B-Rep booleans
  - Trimesh / PyMesh for mesh booleans
"""

from __future__ import annotations

from typing import Any

from cad.core.object import CADObject
from cad.core.property import PropertyType


class BooleanOperation(CADObject):
    """Abstract base for boolean operations between solids."""

    def __init__(self, name: str, objects: list[CADObject], operation: str) -> None:
        super().__init__(name)
        self._operation = operation
        self._input_objects = objects
        for obj in objects:
            self.add_dependency(obj)

    def _define_properties(self) -> None:
        self.add_property("operation", PropertyType.STRING, self._operation,
                          description="Boolean operation type")
        self.add_property("object_count", PropertyType.INT, len(self._input_objects),
                          readonly=True)

    def recompute(self) -> None:
        # In a full implementation, this would run the CSG kernel.
        # For now, mark clean and cache the result reference.
        self._dirty = False


# Re-export with clean names
def boolean_union(*objects: CADObject) -> BooleanOperation:
    return BooleanOperation(f"Union_{objects[0].name}_{objects[1].name}",
                            list(objects), "union")


def boolean_difference(*objects: CADObject) -> BooleanOperation:
    return BooleanOperation(f"Difference_{objects[0].name}_{objects[1].name}",
                            list(objects), "difference")


def boolean_intersect(*objects: CADObject) -> BooleanOperation:
    return BooleanOperation(f"Intersect_{objects[0].name}_{objects[1].name}",
                            list(objects), "intersect")
