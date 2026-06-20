"""Geometry primitives — all basic shapes as CADObjects with parametric properties."""

from __future__ import annotations

import math
from typing import Any

from cad.core.object import CADObject, PropertyType
from cad.geometry.math import Vector2, Vector3, Matrix4, Plane, distance


# ══════════════════════════════════════════════════════════════════════
# 2D Primitives
# ══════════════════════════════════════════════════════════════════════

class Point2D(CADObject):
    def _define_properties(self) -> None:
        self.add_property("x", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("y", PropertyType.FLOAT, 0.0, unit="mm")

    @property
    def position(self) -> Vector2:
        return Vector2(self.get_property_value("x"), self.get_property_value("y"))

    @position.setter
    def position(self, pos: Vector2) -> None:
        self.set_property("x", pos.x)
        self.set_property("y", pos.y)


class Line(CADObject):
    """Infinite line defined by two points."""

    def _define_properties(self) -> None:
        self.add_property("x1", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("y1", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("x2", PropertyType.FLOAT, 10.0, unit="mm")
        self.add_property("y2", PropertyType.FLOAT, 10.0, unit="mm")

    @property
    def start(self) -> Vector2:
        return Vector2(self.get_property_value("x1"), self.get_property_value("y1"))

    @property
    def end(self) -> Vector2:
        return Vector2(self.get_property_value("x2"), self.get_property_value("y2"))

    @property
    def direction(self) -> Vector2:
        return (self.end - self.start).normalized()

    @property
    def length(self) -> float:
        return (self.end - self.start).length()


class LineSegment(Line):
    """A finite line segment between two points."""


class Ray(CADObject):
    """A ray from an origin in a direction."""

    def _define_properties(self) -> None:
        self.add_property("ox", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("oy", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("dx", PropertyType.FLOAT, 1.0, unit="mm")
        self.add_property("dy", PropertyType.FLOAT, 0.0, unit="mm")

    @property
    def origin(self) -> Vector2:
        return Vector2(self.get_property_value("ox"), self.get_property_value("oy"))

    @property
    def direction(self) -> Vector2:
        return Vector2(self.get_property_value("dx"), self.get_property_value("dy")).normalized()


class Circle(CADObject):
    def _define_properties(self) -> None:
        self.add_property("cx", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("cy", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("radius", PropertyType.FLOAT, 10.0, unit="mm")

    @property
    def center(self) -> Vector2:
        return Vector2(self.get_property_value("cx"), self.get_property_value("cy"))

    @property
    def radius(self) -> float:
        return self.get_property_value("radius")

    @property
    def diameter(self) -> float:
        return self.radius * 2.0

    @property
    def area(self) -> float:
        return math.pi * self.radius ** 2

    @property
    def circumference(self) -> float:
        return 2.0 * math.pi * self.radius


class Arc(CADObject):
    def _define_properties(self) -> None:
        self.add_property("cx", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("cy", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("radius", PropertyType.FLOAT, 10.0, unit="mm")
        self.add_property("start_angle", PropertyType.FLOAT, 0.0, unit="deg")
        self.add_property("end_angle", PropertyType.FLOAT, 90.0, unit="deg")

    @property
    def center(self) -> Vector2:
        return Vector2(self.get_property_value("cx"), self.get_property_value("cy"))

    @property
    def start_point(self) -> Vector2:
        a = math.radians(self.get_property_value("start_angle"))
        r = self.get_property_value("radius")
        return self.center + Vector2(math.cos(a) * r, math.sin(a) * r)

    @property
    def end_point(self) -> Vector2:
        a = math.radians(self.get_property_value("end_angle"))
        r = self.get_property_value("radius")
        return self.center + Vector2(math.cos(a) * r, math.sin(a) * r)

    @property
    def sweep_angle(self) -> float:
        return self.get_property_value("end_angle") - self.get_property_value("start_angle")


class Ellipse(CADObject):
    def _define_properties(self) -> None:
        self.add_property("cx", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("cy", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("radius_x", PropertyType.FLOAT, 20.0, unit="mm")
        self.add_property("radius_y", PropertyType.FLOAT, 10.0, unit="mm")

    @property
    def center(self) -> Vector2:
        return Vector2(self.get_property_value("cx"), self.get_property_value("cy"))


class BezierCurve(CADObject):
    def _define_properties(self) -> None:
        self.add_property("points", PropertyType.STRING, "0,0; 10,0; 10,10; 20,10",
                          description="Semicolon-separated control points: x,y; x,y; ...")

    def get_control_points(self) -> list[Vector2]:
        raw = self.get_property_value("points")
        pts = []
        for token in raw.split(";"):
            token = token.strip()
            if not token:
                continue
            parts = token.split(",")
            if len(parts) == 2:
                pts.append(Vector2(float(parts[0]), float(parts[1])))
        return pts

    def evaluate(self, t: float) -> Vector2:
        """De Casteljau algorithm."""
        pts = self.get_control_points()
        if not pts:
            return Vector2()
        while len(pts) > 1:
            pts = [pts[i] * (1 - t) + pts[i + 1] * t for i in range(len(pts) - 1)]
        return pts[0]


class Spline(CADObject):
    """Catmull-Rom spline through a set of points."""

    def _define_properties(self) -> None:
        self.add_property("points", PropertyType.STRING, "0,0; 5,5; 10,0; 15,5",
                          description="Semicolon-separated points: x,y; x,y; ...")

    def get_points(self) -> list[Vector2]:
        raw = self.get_property_value("points")
        pts = []
        for token in raw.split(";"):
            token = token.strip()
            if not token:
                continue
            parts = token.split(",")
            if len(parts) == 2:
                pts.append(Vector2(float(parts[0]), float(parts[1])))
        return pts


class Polygon(CADObject):
    def _define_properties(self) -> None:
        self.add_property("vertices", PropertyType.STRING, "0,0; 10,0; 10,10; 0,10",
                          description="Semicolon-separated vertices: x,y; x,y; ...")

    def get_vertices(self) -> list[Vector2]:
        raw = self.get_property_value("vertices")
        pts = []
        for token in raw.split(";"):
            token = token.strip()
            if not token:
                continue
            parts = token.split(",")
            if len(parts) == 2:
                pts.append(Vector2(float(parts[0]), float(parts[1])))
        return pts

    @property
    def vertex_count(self) -> int:
        return len(self.get_vertices())


# ══════════════════════════════════════════════════════════════════════
# 3D Primitives
# ══════════════════════════════════════════════════════════════════════

class Point3D(CADObject):
    def _define_properties(self) -> None:
        self.add_property("x", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("y", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("z", PropertyType.FLOAT, 0.0, unit="mm")

    @property
    def position(self) -> Vector3:
        return Vector3(
            self.get_property_value("x"),
            self.get_property_value("y"),
            self.get_property_value("z"),
        )


class Box(CADObject):
    def _define_properties(self) -> None:
        self.add_property("width", PropertyType.FLOAT, 10.0, unit="mm")
        self.add_property("height", PropertyType.FLOAT, 20.0, unit="mm")
        self.add_property("depth", PropertyType.FLOAT, 30.0, unit="mm")
        self.add_property("x", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("y", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("z", PropertyType.FLOAT, 0.0, unit="mm")

    @property
    def volume(self) -> float:
        return (self.get_property_value("width") *
                self.get_property_value("height") *
                self.get_property_value("depth"))

    def get_vertices(self) -> list[Vector3]:
        w = self.get_property_value("width") / 2
        h = self.get_property_value("height") / 2
        d = self.get_property_value("depth") / 2
        cx = self.get_property_value("x")
        cy = self.get_property_value("y")
        cz = self.get_property_value("z")
        return [
            Vector3(cx - w, cy - h, cz - d),
            Vector3(cx + w, cy - h, cz - d),
            Vector3(cx + w, cy + h, cz - d),
            Vector3(cx - w, cy + h, cz - d),
            Vector3(cx - w, cy - h, cz + d),
            Vector3(cx + w, cy - h, cz + d),
            Vector3(cx + w, cy + h, cz + d),
            Vector3(cx - w, cy + h, cz + d),
        ]

    def get_edges(self) -> list[tuple[int, int]]:
        return [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]


class Cylinder(CADObject):
    def _define_properties(self) -> None:
        self.add_property("radius", PropertyType.FLOAT, 10.0, unit="mm")
        self.add_property("height", PropertyType.FLOAT, 25.0, unit="mm")
        self.add_property("x", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("y", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("z", PropertyType.FLOAT, 0.0, unit="mm")

    @property
    def volume(self) -> float:
        return math.pi * self.get_property_value("radius") ** 2 * self.get_property_value("height")

    @property
    def surface_area(self) -> float:
        r = self.get_property_value("radius")
        h = self.get_property_value("height")
        return 2 * math.pi * r * (r + h)


class Cone(CADObject):
    def _define_properties(self) -> None:
        self.add_property("radius", PropertyType.FLOAT, 10.0, unit="mm")
        self.add_property("height", PropertyType.FLOAT, 25.0, unit="mm")
        self.add_property("x", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("y", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("z", PropertyType.FLOAT, 0.0, unit="mm")

    @property
    def volume(self) -> float:
        return (1.0 / 3.0) * math.pi * self.get_property_value("radius") ** 2 * self.get_property_value("height")


class Sphere(CADObject):
    def _define_properties(self) -> None:
        self.add_property("radius", PropertyType.FLOAT, 10.0, unit="mm")
        self.add_property("x", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("y", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("z", PropertyType.FLOAT, 0.0, unit="mm")

    @property
    def volume(self) -> float:
        return (4.0 / 3.0) * math.pi * self.get_property_value("radius") ** 3

    @property
    def surface_area(self) -> float:
        return 4.0 * math.pi * self.get_property_value("radius") ** 2


class Torus(CADObject):
    def _define_properties(self) -> None:
        self.add_property("major_radius", PropertyType.FLOAT, 20.0, unit="mm")
        self.add_property("minor_radius", PropertyType.FLOAT, 5.0, unit="mm")
        self.add_property("x", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("y", PropertyType.FLOAT, 0.0, unit="mm")
        self.add_property("z", PropertyType.FLOAT, 0.0, unit="mm")

    @property
    def volume(self) -> float:
        R = self.get_property_value("major_radius")
        r = self.get_property_value("minor_radius")
        return 2 * math.pi ** 2 * R * r ** 2

    @property
    def surface_area(self) -> float:
        R = self.get_property_value("major_radius")
        r = self.get_property_value("minor_radius")
        return 4 * math.pi ** 2 * R * r
