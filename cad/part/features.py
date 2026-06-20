"""Part design features — parametric feature operations on sketches or solids."""

from __future__ import annotations

from cad.core.object import CADObject, PropertyType
from cad.sketch.workspace import Sketch


class Feature(CADObject):
    """Base class for all part design features."""

    def __init__(self, name: str, base: CADObject | None = None) -> None:
        super().__init__(name)
        self._base = base
        if base:
            self.add_dependency(base)

    def _define_properties(self) -> None:
        self.add_property("base", PropertyType.STRING,
                          self._base.name if self._base else "",
                          readonly=True, description="Base object name")


class Pad(Feature):
    """Extrude a sketch into a solid (additive)."""

    def __init__(self, name: str, sketch: Sketch, height: float = 10.0,
                 reverse: bool = False) -> None:
        self._sketch = sketch
        super().__init__(name, sketch)
        self._height = height
        self._reverse = reverse

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("height", PropertyType.FLOAT, self._height, unit="mm")
        self.add_property("reverse", PropertyType.BOOL, self._reverse)

    def recompute(self) -> None:
        # In production: generates the extruded solid mesh/BREP
        self._dirty = False


class Pocket(Feature):
    """Cut/extrude a sketch into a solid (subtractive)."""

    def __init__(self, name: str, sketch: Sketch, depth: float = 10.0) -> None:
        self._sketch = sketch
        super().__init__(name, sketch)
        self._depth = depth

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("depth", PropertyType.FLOAT, self._depth, unit="mm")

    def recompute(self) -> None:
        self._dirty = False


class Revolve(Feature):
    """Revolve a sketch around an axis."""

    def __init__(self, name: str, sketch: Sketch, angle: float = 360.0,
                 axis: str = "z") -> None:
        self._sketch = sketch
        super().__init__(name, sketch)
        self._angle = angle
        self._axis = axis

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("angle", PropertyType.FLOAT, self._angle, unit="deg")
        self.add_property("axis", PropertyType.STRING, self._axis)

    def recompute(self) -> None:
        self._dirty = False


class Loft(Feature):
    """Loft between multiple sketches/profiles."""

    def __init__(self, name: str, sketches: list[Sketch]) -> None:
        self._sketches = sketches
        super().__init__(name, sketches[0] if sketches else None)
        for s in sketches[1:]:
            self.add_dependency(s)

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("profile_count", PropertyType.INT, len(self._sketches), readonly=True)

    def recompute(self) -> None:
        self._dirty = False


class Sweep(Feature):
    """Sweep a profile along a path."""

    def __init__(self, name: str, profile: Sketch, path: Sketch) -> None:
        self._profile = profile
        self._path = path
        super().__init__(name, profile)
        self.add_dependency(path)

    def _define_properties(self) -> None:
        super()._define_properties()

    def recompute(self) -> None:
        self._dirty = False


class Fillet(Feature):
    """Round edges of a solid."""

    def __init__(self, name: str, base: CADObject, radius: float = 5.0,
                 edges: list[int] | None = None) -> None:
        super().__init__(name, base)
        self._radius = radius
        self._edges = edges or []

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("radius", PropertyType.FLOAT, self._radius, unit="mm")
        self.add_property("edge_count", PropertyType.INT, len(self._edges), readonly=True)

    def recompute(self) -> None:
        self._dirty = False


class Chamfer(Feature):
    """Bevel edges of a solid."""

    def __init__(self, name: str, base: CADObject, size: float = 5.0,
                 edges: list[int] | None = None) -> None:
        super().__init__(name, base)
        self._size = size
        self._edges = edges or []

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("size", PropertyType.FLOAT, self._size, unit="mm")

    def recompute(self) -> None:
        self._dirty = False


class Shell(Feature):
    """Hollow out a solid with a wall thickness."""

    def __init__(self, name: str, base: CADObject, thickness: float = 2.0) -> None:
        super().__init__(name, base)
        self._thickness = thickness

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("thickness", PropertyType.FLOAT, self._thickness, unit="mm")

    def recompute(self) -> None:
        self._dirty = False


class LinearPattern(Feature):
    """Repeat a feature in a linear pattern."""

    def __init__(self, name: str, feature: Feature,
                 count_x: int = 3, count_y: int = 1,
                 spacing_x: float = 20.0, spacing_y: float = 20.0) -> None:
        super().__init__(name, feature)
        self._feature = feature
        self._count_x = count_x
        self._count_y = count_y
        self._spacing_x = spacing_x
        self._spacing_y = spacing_y

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("count_x", PropertyType.INT, self._count_x)
        self.add_property("count_y", PropertyType.INT, self._count_y)
        self.add_property("spacing_x", PropertyType.FLOAT, self._spacing_x, unit="mm")
        self.add_property("spacing_y", PropertyType.FLOAT, self._spacing_y, unit="mm")

    def recompute(self) -> None:
        self._dirty = False


class CircularPattern(Feature):
    """Repeat a feature in a circular pattern."""

    def __init__(self, name: str, feature: Feature,
                 count: int = 6, angle: float = 360.0) -> None:
        super().__init__(name, feature)
        self._feature = feature
        self._count = count
        self._angle = angle

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("count", PropertyType.INT, self._count)
        self.add_property("angle", PropertyType.FLOAT, self._angle, unit="deg")

    def recompute(self) -> None:
        self._dirty = False


class MirrorFeature(Feature):
    """Mirror a feature across a plane."""

    def __init__(self, name: str, feature: Feature,
                 mirror_plane: str = "xz") -> None:
        super().__init__(name, feature)
        self._feature = feature
        self._mirror_plane = mirror_plane

    def _define_properties(self) -> None:
        super()._define_properties()
        self.add_property("mirror_plane", PropertyType.STRING, self._mirror_plane)

    def recompute(self) -> None:
        self._dirty = False
