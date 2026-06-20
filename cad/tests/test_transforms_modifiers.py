"""Tests for geometry transforms and modifiers."""

from __future__ import annotations

import math
import unittest

from cad.geometry.math import Vector3, Matrix4, Plane
from cad.geometry.transforms import translate, rotate, scale, mirror, compose, transform_point, transform_vector
from cad.geometry.modifiers import extrude, revolve, sweep, loft, project_point, project_vector


class TestTransforms(unittest.TestCase):
    def test_translate(self) -> None:
        m = translate(Vector3(10, 20, 30))
        p = m.transform_point(Vector3(1, 1, 1))
        self.assertEqual(p, Vector3(11, 21, 31))

    def test_rotate(self) -> None:
        m = rotate(Vector3.unit_z(), math.pi / 2)
        p = m.transform_point(Vector3(1, 0, 0))
        self.assertAlmostEqual(p.x, 0, places=10)
        self.assertAlmostEqual(p.y, 1, places=10)

    def test_scale_uniform(self) -> None:
        m = scale(2, 2, 2)
        p = m.transform_point(Vector3(1, 2, 3))
        self.assertEqual(p, Vector3(2, 4, 6))

    def test_scale_nonuniform(self) -> None:
        m = scale(2, 1, 0.5)
        p = m.transform_point(Vector3(1, 2, 3))
        self.assertEqual(p, Vector3(2, 2, 1.5))

    def test_mirror_x_axis(self) -> None:
        """Mirror across YZ plane (normal = +X)."""
        m = mirror(Vector3(1, 0, 0))
        p = m.transform_point(Vector3(5, 10, 15))
        self.assertEqual(p, Vector3(-5, 10, 15))

    def test_mirror_diagonal(self) -> None:
        """Mirror across plane with normal (1,1,0)."""
        m = mirror(Vector3(1, 1, 0))
        p = m.transform_point(Vector3(1, 0, 0))
        # Reflected point should be (0, -1, 0) — roughly
        result = m.transform_point(p)
        # The dot product with normal should be negated
        self.assertAlmostEqual(p.dot(Vector3(1, 1, 0)), -result.dot(Vector3(1, 1, 0)), places=10)

    def test_mirror_double_is_identity(self) -> None:
        """Mirroring twice should yield the original point."""
        m = mirror(Vector3(0, 0, 1))
        p = Vector3(1, 2, 3)
        double = m.transform_point(m.transform_point(p))
        self.assertEqual(double, p)

    def test_compose_two_translations(self) -> None:
        t1 = translate(Vector3(10, 0, 0))
        t2 = translate(Vector3(0, 20, 0))
        combined = compose(t1, t2)
        p = combined.transform_point(Vector3.zero())
        self.assertEqual(p, Vector3(10, 20, 0))

    def test_compose_translate_then_rotate(self) -> None:
        """Translate then rotate: order matters."""
        t = translate(Vector3(10, 0, 0))
        r = rotate(Vector3.unit_z(), math.pi / 2)
        # First translate then rotate: point at (10,0,0) rotated around origin
        combined = compose(r, t)  # result = r @ t (t then r)
        p = combined.transform_point(Vector3.zero())
        self.assertAlmostEqual(p.x, 0, places=10)
        self.assertAlmostEqual(p.y, 10, places=10)

    def test_transform_point(self) -> None:
        m = Matrix4.translation(5, 10, 15)
        result = transform_point(Vector3.zero(), m)
        self.assertEqual(result, Vector3(5, 10, 15))

    def test_transform_vector(self) -> None:
        m = Matrix4.translation(100, 200, 300)
        result = transform_vector(Vector3(1, 0, 0), m)
        self.assertEqual(result, Vector3(1, 0, 0))  # No translation


class TestModifiers(unittest.TestCase):
    def test_extrude(self) -> None:
        verts = [Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(1, 1, 0), Vector3(0, 1, 0)]
        result = extrude(verts, Vector3.unit_z(), 5)
        # Original 4 + extruded 4 = 8
        self.assertEqual(len(result), 8)
        # Extruded vertices should be at z=5
        self.assertEqual(result[4], Vector3(0, 0, 5))
        self.assertEqual(result[7], Vector3(0, 1, 5))

    def test_extrude_zero_distance(self) -> None:
        verts = [Vector3(0, 0, 0)]
        result = extrude(verts, Vector3.unit_z(), 0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], result[1])  # No offset

    def test_revolve(self) -> None:
        verts = [Vector3(10, 0, 0)]
        result = revolve(verts, Vector3.zero(), Vector3.unit_z(), 360, segments=4)
        # 4 segments + 1 = 5 layers, 1 vertex each = 5
        self.assertEqual(len(result), 5)
        # First vertex at 0°, last at 360° (same position)
        self.assertAlmostEqual(result[0].x, 10, places=10)
        self.assertAlmostEqual(result[0].y, 0, places=10)
        self.assertAlmostEqual(result[-1].x, 10, places=5)
        self.assertAlmostEqual(result[-1].y, 0, places=5)

    def test_revolve_90_degrees(self) -> None:
        verts = [Vector3(10, 0, 0)]
        result = revolve(verts, Vector3.zero(), Vector3.unit_z(), 90, segments=4)
        self.assertEqual(len(result), 5)
        # At 90° (last segment): point should be at (0, 10, 0)
        self.assertAlmostEqual(result[-1].x, 0, places=5)
        self.assertAlmostEqual(result[-1].y, 10, places=5)

    def test_sweep_basic(self) -> None:
        profile = [Vector3(0, 0, 0), Vector3(1, 0, 0)]
        path = [Vector3(0, 0, 0), Vector3(10, 0, 0), Vector3(20, 0, 0)]
        result = sweep(profile, path)
        # path has 3 points, first is skipped, so 2 segments * 2 vertices = 4
        self.assertEqual(len(result), 4)

    def test_sweep_empty_path(self) -> None:
        profile = [Vector3(0, 0, 0)]
        result = sweep(profile, [])
        self.assertEqual(result, profile)

    def test_loft_two_profiles(self) -> None:
        p1 = [Vector3(0, 0, 0), Vector3(1, 0, 0)]
        p2 = [Vector3(0, 1, 0), Vector3(1, 1, 0)]
        result = loft([p1, p2])
        # Should return [p1, interp, p2]
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], p1)
        self.assertEqual(result[2], p2)
        self.assertEqual(len(result[1]), 2)

    def test_loft_one_profile(self) -> None:
        p1 = [Vector3(0, 0, 0)]
        result = loft([p1])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], p1)

    def test_loft_empty(self) -> None:
        result = loft([])
        self.assertEqual(result, [])

    def test_loft_three_profiles(self) -> None:
        p1 = [Vector3(0, 0, 0)]
        p2 = [Vector3(1, 0, 0)]
        p3 = [Vector3(2, 0, 0)]
        result = loft([p1, p2, p3])
        # Returns [p1, interp(p1,p2), interp(p2,p3), p3]
        self.assertEqual(len(result), 4)

    def test_project_point_onto_plane(self) -> None:
        plane = Plane.XY()
        pt = Vector3(10, 20, 30)
        projected = project_point(pt, plane)
        self.assertEqual(projected, Vector3(10, 20, 0))

    def test_project_point_onto_arbitrary_plane(self) -> None:
        plane = Plane(Vector3(0, 0, 5), Vector3.unit_z())
        pt = Vector3(1, 2, 10)
        projected = project_point(pt, plane)
        # Distance from plane is 5, project along -Z
        self.assertEqual(projected, Vector3(1, 2, 5))

    def test_project_vector_onto_plane(self) -> None:
        plane = Plane.XY()
        v = Vector3(1, 2, 3)
        projected = project_vector(v, plane)
        # Z component should be removed
        self.assertEqual(projected, Vector3(1, 2, 0))

    def test_project_vector_already_on_plane(self) -> None:
        plane = Plane.XY()
        v = Vector3(5, -3, 0)
        projected = project_vector(v, plane)
        self.assertEqual(projected, v)


if __name__ == "__main__":
    unittest.main()
