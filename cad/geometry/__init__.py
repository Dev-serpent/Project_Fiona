"""Geometry kernel — primitives, transformations, boolean operations, modifiers."""

from cad.geometry.math import (
    Vector2, Vector3, Matrix4, Plane,
    lerp, clamp, distance, normalize,
)
from cad.geometry.primitives import (
    Point2D, Point3D,
    Line, LineSegment, Ray,
    Circle, Arc, Ellipse,
    BezierCurve, Spline,
    Polygon,
    Box, Cylinder, Cone, Sphere, Torus,
)
from cad.geometry.transforms import (
    translate, rotate, scale, mirror,
    transform_point, transform_vector,
)
from cad.geometry.modifiers import (
    extrude, revolve, sweep, loft,
    project_point, project_vector,
)
from cad.geometry.boolean import (
    boolean_union, boolean_difference, boolean_intersect,
)

__all__ = [
    "Vector2", "Vector3", "Matrix4", "Plane",
    "lerp", "clamp", "distance", "normalize",
    "Point2D", "Point3D",
    "Line", "LineSegment", "Ray",
    "Circle", "Arc", "Ellipse",
    "BezierCurve", "Spline",
    "Polygon",
    "Box", "Cylinder", "Cone", "Sphere", "Torus",
    "translate", "rotate", "scale", "mirror",
    "transform_point", "transform_vector",
    "extrude", "revolve", "sweep", "loft",
    "project_point", "project_vector",
    "boolean_union", "boolean_difference", "boolean_intersect",
]
