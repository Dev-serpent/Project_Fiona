"""Constraint types for 2D sketching."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

from cad.core.object import CADObject, PropertyType
from cad.geometry.math import Vector2


class ConstraintKind(Enum):
    COINCIDENT = "coincident"
    PARALLEL = "parallel"
    PERPENDICULAR = "perpendicular"
    TANGENT = "tangent"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    DISTANCE = "distance"
    ANGLE = "angle"
    RADIUS = "radius"
    DIAMETER = "diameter"
    FIX = "fix"
    EQUAL = "equal"


class Constraint(CADObject):
    """Base class for all geometric constraints."""

    def __init__(self, name: str, kind: ConstraintKind,
                 entities: list[CADObject], value: float | None = None) -> None:
        self._kind = kind
        self._entities = entities
        self._target_value = value
        super().__init__(name)
        for ent in entities:
            self.add_dependency(ent)

    def _define_properties(self) -> None:
        self.add_property("kind", PropertyType.STRING, self._kind.value, readonly=True)
        self.add_property("entity_count", PropertyType.INT, len(self._entities), readonly=True)
        if self._target_value is not None:
            self.add_property("value", PropertyType.FLOAT, self._target_value,
                              description="Target value for dimensional constraints")

    @property
    def kind(self) -> ConstraintKind:
        return self._kind

    @property
    def entities(self) -> list[CADObject]:
        return list(self._entities)

    @property
    def target_value(self) -> float | None:
        return self._target_value

    def evaluate(self, solver) -> float:
        """Evaluate the constraint residual. Override in subclasses."""
        return 0.0


# ── Concrete Constraint Types ────────────────────────────────────────

class Coincident(Constraint):
    """Two points must share the same position."""

    def __init__(self, name: str, p1: CADObject, p2: CADObject) -> None:
        super().__init__(name, ConstraintKind.COINCIDENT, [p1, p2])

    def evaluate(self, solver) -> float:
        p1 = self.entities[0]
        p2 = self.entities[1]
        dx = p1.get_property_value("x") - p2.get_property_value("x")
        dy = p1.get_property_value("y") - p2.get_property_value("y")
        return dx * dx + dy * dy


class Parallel(Constraint):
    """Two lines must be parallel."""

    def __init__(self, name: str, line1: CADObject, line2: CADObject) -> None:
        super().__init__(name, ConstraintKind.PARALLEL, [line1, line2])

    def evaluate(self, solver) -> float:
        from cad.geometry.primitives import Line
        l1 = self.entities[0]
        l2 = self.entities[1]
        d1x = l1.get_property_value("x2") - l1.get_property_value("x1")
        d1y = l1.get_property_value("y2") - l1.get_property_value("y1")
        d2x = l2.get_property_value("x2") - l2.get_property_value("x1")
        d2y = l2.get_property_value("y2") - l2.get_property_value("y1")
        # Cross product (z-component) should be zero
        return abs(d1x * d2y - d1y * d2x)


class Perpendicular(Constraint):
    """Two lines must be perpendicular."""

    def __init__(self, name: str, line1: CADObject, line2: CADObject) -> None:
        super().__init__(name, ConstraintKind.PERPENDICULAR, [line1, line2])

    def evaluate(self, solver) -> float:
        l1 = self.entities[0]
        l2 = self.entities[1]
        d1x = l1.get_property_value("x2") - l1.get_property_value("x1")
        d1y = l1.get_property_value("y2") - l1.get_property_value("y1")
        d2x = l2.get_property_value("x2") - l2.get_property_value("x1")
        d2y = l2.get_property_value("y2") - l2.get_property_value("y1")
        return abs(d1x * d2x + d1y * d2y)


class Tangent(Constraint):
    """A line must be tangent to a circle/arc."""

    def __init__(self, name: str, line: CADObject, circle: CADObject) -> None:
        super().__init__(name, ConstraintKind.TANGENT, [line, circle])

    def evaluate(self, solver) -> float:
        # Distance from circle center to line = radius
        line = self.entities[0]
        circle = self.entities[1]
        cx = circle.get_property_value("cx")
        cy = circle.get_property_value("cy")
        r = circle.get_property_value("radius")
        x1 = line.get_property_value("x1")
        y1 = line.get_property_value("y1")
        x2 = line.get_property_value("x2")
        y2 = line.get_property_value("y2")
        dx = x2 - x1
        dy = y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-10:
            return float('inf')
        dist = abs(dx * (y1 - cy) - dy * (x1 - cx)) / length
        return abs(dist - r)


class Horizontal(Constraint):
    """A line segment must be horizontal."""

    def __init__(self, name: str, line: CADObject) -> None:
        super().__init__(name, ConstraintKind.HORIZONTAL, [line])

    def evaluate(self, solver) -> float:
        line = self.entities[0]
        dy = line.get_property_value("y2") - line.get_property_value("y1")
        return abs(dy)


class Vertical(Constraint):
    """A line segment must be vertical."""

    def __init__(self, name: str, line: CADObject) -> None:
        super().__init__(name, ConstraintKind.VERTICAL, [line])

    def evaluate(self, solver) -> float:
        line = self.entities[0]
        dx = line.get_property_value("x2") - line.get_property_value("x1")
        return abs(dx)


class Distance(Constraint):
    """Distance between two points."""

    def __init__(self, name: str, p1: CADObject, p2: CADObject, distance: float) -> None:
        super().__init__(name, ConstraintKind.DISTANCE, [p1, p2], distance)

    def evaluate(self, solver) -> float:
        p1 = self.entities[0]
        p2 = self.entities[1]
        dx = p1.get_property_value("x") - p2.get_property_value("x")
        dy = p1.get_property_value("y") - p2.get_property_value("y")
        current = (dx * dx + dy * dy) ** 0.5
        return abs(current - self.target_value)


class Angle(Constraint):
    """Angle between two lines."""

    def __init__(self, name: str, line1: CADObject, line2: CADObject, angle_deg: float) -> None:
        super().__init__(name, ConstraintKind.ANGLE, [line1, line2], angle_deg)

    def evaluate(self, solver) -> float:
        l1 = self.entities[0]
        l2 = self.entities[1]
        d1x = l1.get_property_value("x2") - l1.get_property_value("x1")
        d1y = l1.get_property_value("y2") - l1.get_property_value("y1")
        d2x = l2.get_property_value("x2") - l2.get_property_value("x1")
        d2y = l2.get_property_value("y2") - l2.get_property_value("y1")
        dot = d1x * d2x + d1y * d2y
        n1 = (d1x * d1x + d1y * d1y) ** 0.5
        n2 = (d2x * d2x + d2y * d2y) ** 0.5
        if n1 * n2 < 1e-10:
            return float('inf')
        current = abs(math.degrees(math.acos(max(-1, min(1, dot / (n1 * n2))))))
        return abs(current - self.target_value)


class Radius(Constraint):
    """Radius of a circle or arc."""

    def __init__(self, name: str, circle: CADObject, radius: float) -> None:
        super().__init__(name, ConstraintKind.RADIUS, [circle], radius)

    def evaluate(self, solver) -> float:
        circle = self.entities[0]
        current = circle.get_property_value("radius")
        return abs(current - self.target_value)


class Diameter(Constraint):
    """Diameter of a circle or arc."""

    def __init__(self, name: str, circle: CADObject, diameter: float) -> None:
        super().__init__(name, ConstraintKind.DIAMETER, [circle], diameter)

    def evaluate(self, solver) -> float:
        circle = self.entities[0]
        current = circle.get_property_value("radius") * 2
        return abs(current - self.target_value)


class Fix(Constraint):
    """Fix a point's position in place."""

    def __init__(self, name: str, point: CADObject, x: float | None = None, y: float | None = None) -> None:
        super().__init__(name, ConstraintKind.FIX, [point])
        self._fix_x = x
        self._fix_y = y

    def evaluate(self, solver) -> float:
        pt = self.entities[0]
        err = 0.0
        if self._fix_x is not None:
            err += (pt.get_property_value("x") - self._fix_x) ** 2
        if self._fix_y is not None:
            err += (pt.get_property_value("y") - self._fix_y) ** 2
        return err


class Equal(Constraint):
    """Two line segments must have equal length."""

    def __init__(self, name: str, line1: CADObject, line2: CADObject) -> None:
        super().__init__(name, ConstraintKind.EQUAL, [line1, line2])

    def evaluate(self, solver) -> float:
        l1 = self.entities[0]
        l2 = self.entities[1]
        d1x = l1.get_property_value("x2") - l1.get_property_value("x1")
        d1y = l1.get_property_value("y2") - l1.get_property_value("y1")
        d2x = l2.get_property_value("x2") - l2.get_property_value("x1")
        d2y = l2.get_property_value("y2") - l2.get_property_value("y1")
        len1 = (d1x * d1x + d1y * d1y) ** 0.5
        len2 = (d2x * d2x + d2y * d2y) ** 0.5
        return abs(len1 - len2)



