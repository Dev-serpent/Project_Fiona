"""Tests for the geometry kernel."""

from __future__ import annotations

import math
import unittest

from cad.geometry.math import Vector2, Vector3, Matrix4, Plane


class TestVector2(unittest.TestCase):
    def test_basics(self) -> None:
        v = Vector2(3, 4)
        self.assertEqual(v.x, 3)
        self.assertEqual(v.y, 4)
        self.assertAlmostEqual(v.length(), 5.0)

    def test_operations(self) -> None:
        a = Vector2(1, 2)
        b = Vector2(3, 4)
        self.assertEqual(a + b, Vector2(4, 6))
        self.assertEqual(a - b, Vector2(-2, -2))
        self.assertAlmostEqual(a.dot(b), 11)
        self.assertAlmostEqual(a.cross(b), -2)

    def test_normalized(self) -> None:
        v = Vector2(3, 4)
        n = v.normalized()
        self.assertAlmostEqual(n.length(), 1.0)
        self.assertAlmostEqual(n.x, 0.6)


class TestVector3(unittest.TestCase):
    def test_basics(self) -> None:
        v = Vector3(1, 2, 3)
        self.assertEqual(v.x, 1)
        self.assertEqual(v.y, 2)
        self.assertEqual(v.z, 3)

    def test_cross(self) -> None:
        x = Vector3.unit_x()
        y = Vector3.unit_y()
        z = x.cross(y)
        self.assertEqual(z, Vector3.unit_z())

    def test_normalized(self) -> None:
        v = Vector3(3, 4, 0)
        n = v.normalized()
        self.assertAlmostEqual(n.length(), 1.0)

    def test_zero_length_normalized(self) -> None:
        z = Vector3.zero()
        n = z.normalized()
        self.assertEqual(n, Vector3.zero())


class TestMatrix4(unittest.TestCase):
    def test_identity(self) -> None:
        m = Matrix4.identity()
        p = Vector3(1, 2, 3)
        result = m.transform_point(p)
        self.assertEqual(result, p)

    def test_translation(self) -> None:
        m = Matrix4.translation(10, 20, 30)
        p = m.transform_point(Vector3(1, 1, 1))
        self.assertEqual(p, Vector3(11, 21, 31))

    def test_rotation_roundtrip(self) -> None:
        p = Vector3(1, 0, 0)
        m = Matrix4.rotation_z(math.pi)  # 180 degrees
        result = m.transform_point(p)
        self.assertAlmostEqual(result.x, -1, places=10)
        self.assertAlmostEqual(result.y, 0, places=10)
        self.assertAlmostEqual(result.z, 0, places=10)

    def test_composition(self) -> None:
        t = Matrix4.translation(5, 10, 15)
        s = Matrix4.scaling(2, 2, 2)
        combined = t @ s
        p = combined.transform_point(Vector3(1, 1, 1))
        self.assertEqual(p, Vector3(7, 12, 17))

    def test_inverse(self) -> None:
        t = Matrix4.translation(10, 20, 30)
        inv = t.inverse()
        p = Vector3(100, 200, 300)
        result = inv.transform_point(t.transform_point(p))
        self.assertAlmostEqual(result.x, p.x, places=10)
        self.assertAlmostEqual(result.y, p.y, places=10)
        self.assertAlmostEqual(result.z, p.z, places=10)


class TestPlane(unittest.TestCase):
    def test_project_2d_3d_roundtrip(self) -> None:
        plane = Plane.XY()
        p3d = plane.project_3d(Vector2(10, 20))
        self.assertAlmostEqual(p3d.x, 10)
        self.assertAlmostEqual(p3d.y, 20)
        self.assertAlmostEqual(p3d.z, 0)
        p2d = plane.project_2d(p3d)
        self.assertAlmostEqual(p2d.x, 10)
        self.assertAlmostEqual(p2d.y, 20)

    def test_distance_to(self) -> None:
        plane = Plane(Vector3(0, 0, 0), Vector3.unit_z())
        d = plane.distance_to(Vector3(0, 0, 5))
        self.assertAlmostEqual(d, 5)

        d2 = plane.distance_to(Vector3(0, 0, -5))
        self.assertAlmostEqual(d2, -5)


if __name__ == "__main__":
    unittest.main()
