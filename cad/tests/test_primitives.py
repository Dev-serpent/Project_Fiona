"""Tests for all geometry primitives — 2D and 3D shapes."""

from __future__ import annotations

import math
import unittest

from cad.geometry.math import Vector2, Vector3
from cad.geometry.primitives import (
    Point2D, Point3D, Line, LineSegment, Ray,
    Circle, Arc, Ellipse, BezierCurve, Spline, Polygon,
    Box, Cylinder, Cone, Sphere, Torus,
)
from cad.core.property import PropertyType


class TestPoint2D(unittest.TestCase):
    def test_create(self) -> None:
        p = Point2D("P")
        self.assertEqual(p.get_property_value("x"), 0.0)
        self.assertEqual(p.get_property_value("y"), 0.0)

    def test_set_position(self) -> None:
        p = Point2D("P")
        p.set_property("x", 3.5)
        p.set_property("y", -2.5)
        pos = p.position
        self.assertAlmostEqual(pos.x, 3.5)
        self.assertAlmostEqual(pos.y, -2.5)

    def test_position_property(self) -> None:
        p = Point2D("P")
        p.position = Vector2(7, 8)
        self.assertEqual(p.get_property_value("x"), 7)
        self.assertEqual(p.get_property_value("y"), 8)


class TestPoint3D(unittest.TestCase):
    def test_create(self) -> None:
        p = Point3D("P")
        self.assertEqual(p.get_property_value("x"), 0.0)
        self.assertEqual(p.get_property_value("z"), 0.0)

    def test_position(self) -> None:
        p = Point3D("P")
        p.set_property("x", 1)
        p.set_property("y", 2)
        p.set_property("z", 3)
        pos = p.position
        self.assertEqual(pos, Vector3(1, 2, 3))


class TestLinePrimitive(unittest.TestCase):
    def test_create(self) -> None:
        l = Line("L")
        self.assertEqual(l.get_property_value("x1"), 0.0)
        self.assertEqual(l.get_property_value("x2"), 10.0)

    def test_start_end(self) -> None:
        l = Line("L")
        l.set_property("x1", 1); l.set_property("y1", 2)
        l.set_property("x2", 3); l.set_property("y2", 4)
        self.assertEqual(l.start, Vector2(1, 2))
        self.assertEqual(l.end, Vector2(3, 4))

    def test_direction(self) -> None:
        l = Line("L")
        l.set_property("x1", 0); l.set_property("y1", 0)
        l.set_property("x2", 10); l.set_property("y2", 0)
        self.assertEqual(l.direction, Vector2(1, 0))

    def test_length(self) -> None:
        l = Line("L")
        l.set_property("x1", 0); l.set_property("y1", 0)
        l.set_property("x2", 3); l.set_property("y2", 4)
        self.assertAlmostEqual(l.length, 5.0)

    def test_zero_length_direction(self) -> None:
        l = Line("L")
        l.set_property("x1", 0); l.set_property("y1", 0)
        l.set_property("x2", 0); l.set_property("y2", 0)
        self.assertEqual(l.direction, Vector2(0, 0))


class TestRay(unittest.TestCase):
    def test_create(self) -> None:
        r = Ray("R")
        self.assertEqual(r.origin, Vector2(0, 0))
        self.assertEqual(r.direction, Vector2(1, 0))

    def test_direction_normalized(self) -> None:
        r = Ray("R")
        r.set_property("dx", 3)
        r.set_property("dy", 4)
        d = r.direction
        self.assertAlmostEqual(d.length(), 1.0)
        self.assertAlmostEqual(d.x, 0.6, places=10)


class TestCircle(unittest.TestCase):
    def test_create(self) -> None:
        c = Circle("C")
        self.assertEqual(c.center, Vector2(0, 0))
        self.assertEqual(c.radius, 10.0)

    def test_diameter(self) -> None:
        c = Circle("C")
        c.set_property("radius", 5)
        self.assertEqual(c.diameter, 10.0)

    def test_area(self) -> None:
        c = Circle("C")
        c.set_property("radius", 2)
        self.assertAlmostEqual(c.area, 4 * math.pi, places=10)

    def test_circumference(self) -> None:
        c = Circle("C")
        c.set_property("radius", 3)
        self.assertAlmostEqual(c.circumference, 6 * math.pi, places=10)

    def test_set_center(self) -> None:
        c = Circle("C")
        c.set_property("cx", -5)
        c.set_property("cy", 10)
        self.assertEqual(c.center, Vector2(-5, 10))


class TestArc(unittest.TestCase):
    def test_create(self) -> None:
        a = Arc("A")
        self.assertEqual(a.center, Vector2(0, 0))
        self.assertEqual(a.sweep_angle, 90.0)

    def test_start_point(self) -> None:
        a = Arc("A")
        a.set_property("radius", 10)
        a.set_property("start_angle", 0)
        sp = a.start_point
        self.assertAlmostEqual(sp.x, 10, places=10)
        self.assertAlmostEqual(sp.y, 0, places=10)

    def test_end_point(self) -> None:
        a = Arc("A")
        a.set_property("radius", 10)
        a.set_property("end_angle", 90)
        ep = a.end_point
        self.assertAlmostEqual(ep.x, 0, places=10)
        self.assertAlmostEqual(ep.y, 10, places=10)

    def test_sweep_angle(self) -> None:
        a = Arc("A")
        a.set_property("start_angle", 30)
        a.set_property("end_angle", 120)
        self.assertAlmostEqual(a.sweep_angle, 90.0)


class TestEllipse(unittest.TestCase):
    def test_create(self) -> None:
        e = Ellipse("E")
        self.assertEqual(e.center, Vector2(0, 0))
        self.assertEqual(e.get_property_value("radius_x"), 20.0)
        self.assertEqual(e.get_property_value("radius_y"), 10.0)

    def test_center(self) -> None:
        e = Ellipse("E")
        e.set_property("cx", 5); e.set_property("cy", 10)
        self.assertEqual(e.center, Vector2(5, 10))


class TestBezierCurve(unittest.TestCase):
    def test_default_control_points(self) -> None:
        b = BezierCurve("B")
        pts = b.get_control_points()
        self.assertEqual(len(pts), 4)

    def test_evaluate_start(self) -> None:
        b = BezierCurve("B")
        pts = b.get_control_points()
        start = b.evaluate(0)
        self.assertEqual(start, pts[0])

    def test_evaluate_end(self) -> None:
        b = BezierCurve("B")
        pts = b.get_control_points()
        end = b.evaluate(1)
        self.assertEqual(end, pts[-1])

    def test_evaluate_midpoint(self) -> None:
        b = BezierCurve("B")
        b.set_property("points", "0,0; 10,0; 10,10; 20,10")
        mid = b.evaluate(0.5)
        # At t=0.5, for symmetric curve, should be roughly at (10, 5)
        # This is approximate — exact De Casteljau result
        self.assertAlmostEqual(mid.x, 10.0, places=5)
        self.assertAlmostEqual(mid.y, 5.0, places=5)

    def test_evaluate_empty_points(self) -> None:
        b = BezierCurve("B")
        b.set_property("points", "")
        result = b.evaluate(0.5)
        self.assertEqual(result, Vector2(0, 0))

    def test_parse_control_points(self) -> None:
        b = BezierCurve("B")
        b.set_property("points", "1,2; 3,4; 5,6")
        pts = b.get_control_points()
        self.assertEqual(len(pts), 3)
        self.assertEqual(pts[1], Vector2(3, 4))


class TestSpline(unittest.TestCase):
    def test_default_points(self) -> None:
        s = Spline("S")
        pts = s.get_points()
        self.assertEqual(len(pts), 4)

    def test_get_points(self) -> None:
        s = Spline("S")
        s.set_property("points", "0,0; 10,10; 20,0")
        pts = s.get_points()
        self.assertEqual(len(pts), 3)


class TestPolygon(unittest.TestCase):
    def test_default_vertices(self) -> None:
        p = Polygon("P")
        self.assertEqual(p.vertex_count, 4)

    def test_get_vertices(self) -> None:
        p = Polygon("P")
        p.set_property("vertices", "0,0; 5,0; 5,5; 0,5")
        verts = p.get_vertices()
        self.assertEqual(len(verts), 4)
        self.assertEqual(verts[1], Vector2(5, 0))

    def test_empty_vertices(self) -> None:
        p = Polygon("P")
        p.set_property("vertices", "")
        self.assertEqual(p.vertex_count, 0)


class TestBox(unittest.TestCase):
    def setUp(self) -> None:
        self.box = Box("B")
        self.box.set_property("width", 10)
        self.box.set_property("height", 20)
        self.box.set_property("depth", 30)

    def test_volume(self) -> None:
        self.assertAlmostEqual(self.box.volume, 6000.0)

    def test_get_vertices(self) -> None:
        verts = self.box.get_vertices()
        self.assertEqual(len(verts), 8)
        # Check center is at (0,0,0), so vertices are symmetric
        self.assertEqual(verts[0], Vector3(-5, -10, -15))
        self.assertEqual(verts[6], Vector3(5, 10, 15))

    def test_get_edges(self) -> None:
        edges = self.box.get_edges()
        self.assertEqual(len(edges), 12)  # A box has 12 edges

    def test_position_offset(self) -> None:
        self.box.set_property("x", 10)
        self.box.set_property("y", 20)
        self.box.set_property("z", 30)
        verts = self.box.get_vertices()
        # Center is (10, 20, 30)
        self.assertEqual(verts[0], Vector3(5, 10, 15))
        self.assertEqual(verts[6], Vector3(15, 30, 45))


class TestCylinder(unittest.TestCase):
    def setUp(self) -> None:
        self.cyl = Cylinder("C")
        self.cyl.set_property("radius", 5)
        self.cyl.set_property("height", 10)

    def test_volume(self) -> None:
        expected = math.pi * 25 * 10  # πr²h
        self.assertAlmostEqual(self.cyl.volume, expected, places=10)

    def test_surface_area(self) -> None:
        r, h = 5, 10
        expected = 2 * math.pi * r * (r + h)
        self.assertAlmostEqual(self.cyl.surface_area, expected, places=10)


class TestCone(unittest.TestCase):
    def test_volume(self) -> None:
        c = Cone("C")
        c.set_property("radius", 5)
        c.set_property("height", 15)
        expected = (1.0 / 3.0) * math.pi * 25 * 15
        self.assertAlmostEqual(c.volume, expected, places=10)


class TestSphere(unittest.TestCase):
    def setUp(self) -> None:
        self.s = Sphere("S")
        self.s.set_property("radius", 10)

    def test_volume(self) -> None:
        expected = (4.0 / 3.0) * math.pi * 1000
        self.assertAlmostEqual(self.s.volume, expected, places=10)

    def test_surface_area(self) -> None:
        expected = 4.0 * math.pi * 100
        self.assertAlmostEqual(self.s.surface_area, expected, places=10)


class TestTorus(unittest.TestCase):
    def setUp(self) -> None:
        self.t = Torus("T")
        self.t.set_property("major_radius", 20)
        self.t.set_property("minor_radius", 5)

    def test_volume(self) -> None:
        R, r = 20, 5
        expected = 2 * math.pi ** 2 * R * r ** 2
        self.assertAlmostEqual(self.t.volume, expected, places=10)

    def test_surface_area(self) -> None:
        R, r = 20, 5
        expected = 4 * math.pi ** 2 * R * r
        self.assertAlmostEqual(self.t.surface_area, expected, places=10)


class TestPropertyTypes(unittest.TestCase):
    """Verify all primitives have correct property types."""

    def test_point2d_has_float_properties(self) -> None:
        p = Point2D("P")
        self.assertEqual(p.get_property("x").type, PropertyType.FLOAT)
        self.assertEqual(p.get_property("y").type, PropertyType.FLOAT)

    def test_box_has_position_properties(self) -> None:
        b = Box("B")
        self.assertIsNotNone(b.get_property("x"))
        self.assertIsNotNone(b.get_property("y"))
        self.assertIsNotNone(b.get_property("z"))

    def test_circle_has_string_property_type(self) -> None:
        b = BezierCurve("B")
        self.assertEqual(b.get_property("points").type, PropertyType.STRING)


if __name__ == "__main__":
    unittest.main()
