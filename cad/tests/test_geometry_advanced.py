"""Advanced geometry kernel tests — full coverage for Vector2, Vector3, Matrix4, Plane."""

from __future__ import annotations

import math
import unittest

from cad.geometry.math import (
    Vector2, Vector3, Matrix4, Plane,
    lerp, clamp, distance, normalize,
)


class TestVector2Advanced(unittest.TestCase):
    def setUp(self) -> None:
        self.v = Vector2(3, 4)

    def test_negation(self) -> None:
        neg = -self.v
        self.assertEqual(neg.x, -3)
        self.assertEqual(neg.y, -4)

    def test_multiplication(self) -> None:
        scaled = self.v * 2.5
        self.assertAlmostEqual(scaled.x, 7.5)
        self.assertAlmostEqual(scaled.y, 10.0)

    def test_length_sq(self) -> None:
        self.assertAlmostEqual(self.v.length_sq(), 25.0)

    def test_perpendicular(self) -> None:
        perp = self.v.perpendicular()
        self.assertEqual(perp.x, -4)
        self.assertEqual(perp.y, 3)
        # Perpendicular is rotated 90°, dot product must be ~0
        self.assertAlmostEqual(self.v.dot(perp), 0.0)

    def test_angle(self) -> None:
        v = Vector2(1, 0)
        self.assertAlmostEqual(v.angle(), 0.0)
        v2 = Vector2(0, 1)
        self.assertAlmostEqual(v2.angle(), math.pi / 2)
        v3 = Vector2(-1, 0)
        self.assertAlmostEqual(v3.angle(), math.pi)

    def test_from_angle(self) -> None:
        v = Vector2.from_angle(0)
        self.assertAlmostEqual(v.x, 1.0)
        self.assertAlmostEqual(v.y, 0.0)
        v90 = Vector2.from_angle(math.pi / 2)
        self.assertAlmostEqual(v90.x, 0.0, places=10)
        self.assertAlmostEqual(v90.y, 1.0, places=10)
        scaled = Vector2.from_angle(math.pi / 4, math.sqrt(2))
        self.assertAlmostEqual(scaled.x, 1.0, places=10)
        self.assertAlmostEqual(scaled.y, 1.0, places=10)

    def test_to_dict(self) -> None:
        d = self.v.to_dict()
        self.assertEqual(d, {"x": 3.0, "y": 4.0})

    def test_repr(self) -> None:
        r = repr(self.v)
        self.assertIn("Vector2", r)
        self.assertIn("3", r)

    def test_eq_precision(self) -> None:
        a = Vector2(1.0, 2.0)
        b = Vector2(1.0 + 1e-11, 2.0 - 1e-11)
        self.assertEqual(a, b)  # Within tolerance

    def test_eq_wrong_type(self) -> None:
        self.assertNotEqual(self.v, (3, 4))

    def test_zero_normalized(self) -> None:
        z = Vector2(0, 0)
        n = z.normalized()
        self.assertEqual(n.x, 0.0)
        self.assertEqual(n.y, 0.0)
        self.assertEqual(n.length(), 0.0)


class TestVector3Advanced(unittest.TestCase):
    def setUp(self) -> None:
        self.v = Vector3(1, 2, 3)

    def test_negation(self) -> None:
        neg = -self.v
        self.assertEqual(neg, Vector3(-1, -2, -3))

    def test_multiplication(self) -> None:
        scaled = self.v * 0.5
        self.assertEqual(scaled, Vector3(0.5, 1.0, 1.5))

    def test_length_sq(self) -> None:
        # sqrt(1+4+9) = sqrt(14)
        self.assertAlmostEqual(self.v.length_sq(), 14.0)

    def test_dot(self) -> None:
        a = Vector3(1, 0, 0)
        b = Vector3(0, 1, 0)
        self.assertAlmostEqual(a.dot(b), 0.0)
        self.assertAlmostEqual(a.dot(a), 1.0)

    def test_cross_properties(self) -> None:
        x = Vector3(1, 0, 0)
        y = Vector3(0, 1, 0)
        z = Vector3(0, 0, 1)
        # Right-hand rule
        self.assertEqual(x.cross(y), z)
        self.assertEqual(y.cross(z), x)
        self.assertEqual(z.cross(x), y)
        # Anti-commutative
        self.assertEqual(x.cross(y), -y.cross(x))

    def test_unit_x_y_z(self) -> None:
        self.assertEqual(Vector3.unit_x(), Vector3(1, 0, 0))
        self.assertEqual(Vector3.unit_y(), Vector3(0, 1, 0))
        self.assertEqual(Vector3.unit_z(), Vector3(0, 0, 1))

    def test_to_2d_no_plane(self) -> None:
        v = Vector3(5, -3, 100)
        v2d = v.to_2d()
        self.assertEqual(v2d, Vector2(5, -3))

    def test_to_2d_with_plane(self) -> None:
        plane = Plane.XY()
        v = Vector3(10, 20, 30)
        v2d = v.to_2d(plane)
        self.assertEqual(v2d, Vector2(10, 20))

    def test_to_dict(self) -> None:
        d = self.v.to_dict()
        self.assertEqual(d, {"x": 1.0, "y": 2.0, "z": 3.0})

    def test_eq_precision(self) -> None:
        a = Vector3(1, 2, 3)
        b = Vector3(1 + 1e-11, 2 - 1e-11, 3 + 1e-12)
        self.assertEqual(a, b)

    def test_eq_wrong_type(self) -> None:
        self.assertNotEqual(self.v, (1, 2, 3))


class TestMatrix4Advanced(unittest.TestCase):
    def test_rotation_x(self) -> None:
        p = Vector3(0, 1, 0)
        m = Matrix4.rotation_x(math.pi / 2)
        result = m.transform_point(p)
        self.assertAlmostEqual(result.x, 0, places=10)
        self.assertAlmostEqual(result.y, 0, places=10)
        self.assertAlmostEqual(result.z, 1, places=10)

    def test_rotation_y(self) -> None:
        p = Vector3(1, 0, 0)
        m = Matrix4.rotation_y(math.pi / 2)
        result = m.transform_point(p)
        self.assertAlmostEqual(result.x, 0, places=10)
        self.assertAlmostEqual(result.y, 0, places=10)
        self.assertAlmostEqual(result.z, -1, places=10)

    def test_rotation_z(self) -> None:
        p = Vector3(1, 0, 0)
        m = Matrix4.rotation_z(math.pi / 2)
        result = m.transform_point(p)
        self.assertAlmostEqual(result.x, 0, places=10)
        self.assertAlmostEqual(result.y, 1, places=10)
        self.assertAlmostEqual(result.z, 0, places=10)

    def test_rotation_arbitrary_axis(self) -> None:
        # Rotate 180° around X axis using arbitrary axis API
        axis = Vector3(1, 0, 0)
        m = Matrix4.rotation(axis, math.pi)
        p = Vector3(0, 1, 0)
        result = m.transform_point(p)
        self.assertAlmostEqual(result.x, 0, places=10)
        self.assertAlmostEqual(result.y, -1, places=10)
        self.assertAlmostEqual(result.z, 0, places=10)

    def test_rotation_arbitrary_axis_normalized(self) -> None:
        """Rotation with non-unit axis should still work."""
        axis = Vector3(2, 0, 0)  # not normalized
        m = Matrix4.rotation(axis, math.pi)
        p = Vector3(0, 1, 0)
        result = m.transform_point(p)
        self.assertAlmostEqual(result.x, 0, places=10)
        self.assertAlmostEqual(result.y, -1, places=10)
        self.assertAlmostEqual(result.z, 0, places=10)

    def test_identity_transform_vector(self) -> None:
        m = Matrix4.identity()
        v = Vector3(10, 20, 30)
        result = m.transform_vector(v)
        self.assertEqual(result, v)

    def test_transform_vector_no_translation(self) -> None:
        """transform_vector should NOT apply translation."""
        m = Matrix4.translation(100, 200, 300)
        v = Vector3(1, 2, 3)
        result = m.transform_vector(v)
        self.assertEqual(result, Vector3(1, 2, 3))

    def test_scaling_matrix(self) -> None:
        m = Matrix4.scaling(2, 3, 4)
        p = Vector3(1, 1, 1)
        result = m.transform_point(p)
        self.assertEqual(result, Vector3(2, 3, 4))

    def test_perspective_basic(self) -> None:
        m = Matrix4.perspective(90, 1.0, 1, 100)
        # Should produce a valid 4x4 matrix
        self.assertEqual(len(m.data), 16)
        # Last row should be (0, 0, -1, 0) for OpenGL-style
        self.assertAlmostEqual(m.data[11], -1.0)
        self.assertAlmostEqual(m.data[15], 0.0)

    def test_look_at(self) -> None:
        eye = Vector3(0, 0, 100)
        target = Vector3(0, 0, 0)
        up = Vector3(0, 1, 0)
        m = Matrix4.look_at(eye, target, up)
        # f = (target - eye).normalized() = (0,0,-1)
        # f.dot(eye) = (0,0,-1).dot(0,0,100) = -100
        # So m.data[14] should be -100
        self.assertAlmostEqual(m.data[14], -100.0)
        # Eye should map to view origin
        eye_in_view = m.transform_point(eye)
        self.assertAlmostEqual(eye_in_view.x, 0, places=10)
        self.assertAlmostEqual(eye_in_view.y, 0, places=10)
        self.assertAlmostEqual(eye_in_view.z, 0, places=10)
        # Camera looks down -Z: origin should be at negative z in view
        origin_in_view = m.transform_point(Vector3(0, 0, 0))
        self.assertLess(origin_in_view.z, 0)

    def test_look_at_right_handed(self) -> None:
        """Verify look_at produces right-handed view matrix."""
        eye = Vector3(10, 10, 10)
        target = Vector3(0, 0, 0)
        up = Vector3(0, 0, 1)
        m = Matrix4.look_at(eye, target, up)
        # The forward vector should point from eye to target
        # In view space, the camera looks down -Z
        origin_in_view = m.transform_point(Vector3(0, 0, 0))
        eye_in_view = m.transform_point(eye)
        # Origin in view space should have negative or zero z
        self.assertLessEqual(origin_in_view.z, 0)
        # Eye should map to origin in view space
        self.assertAlmostEqual(eye_in_view.x, 0, places=10)
        self.assertAlmostEqual(eye_in_view.y, 0, places=10)
        self.assertAlmostEqual(eye_in_view.z, 0, places=10)

    def test_inverse_non_translation(self) -> None:
        """Inverse of scaling matrix."""
        s = Matrix4.scaling(2, 3, 4)
        inv = s.inverse()
        p = Vector3(6, 9, 12)
        result = inv.transform_point(s.transform_point(p))
        self.assertAlmostEqual(result.x, p.x, places=10)
        self.assertAlmostEqual(result.y, p.y, places=10)
        self.assertAlmostEqual(result.z, p.z, places=10)

    def test_inverse_rotation(self) -> None:
        """Inverse of rotation is transpose."""
        r = Matrix4.rotation_z(math.pi / 3)
        inv = r.inverse()
        p = Vector3(5, -3, 2)
        result = inv.transform_point(r.transform_point(p))
        self.assertAlmostEqual(result.x, p.x, places=10)
        self.assertAlmostEqual(result.y, p.y, places=10)
        self.assertAlmostEqual(result.z, p.z, places=10)

    def test_inverse_singular(self) -> None:
        """Singular matrix returns a fallback identity."""
        m = Matrix4([0.0] * 16)  # All zeros — singular
        result = m.inverse()
        # Should not crash and should return something finite
        self.assertEqual(len(result.data), 16)
        for v in result.data:
            self.assertTrue(math.isfinite(v))

    def test_compose_identity(self) -> None:
        m = Matrix4.identity()
        # Composing with identity should not change
        result = m @ Matrix4.identity()
        self.assertEqual(result.data, Matrix4.identity().data)

    def test_to_list(self) -> None:
        m = Matrix4.identity()
        lst = m.to_list()
        self.assertEqual(len(lst), 16)
        self.assertEqual(lst[0], 1.0)
        self.assertEqual(lst[15], 1.0)

    def test_to_dict(self) -> None:
        m = Matrix4.identity()
        d = m.to_dict()
        self.assertIn("data", d)
        self.assertEqual(len(d["data"]), 16)


class TestPlaneAdvanced(unittest.TestCase):
    def test_xy_plane(self) -> None:
        p = Plane.XY()
        self.assertEqual(p.origin, Vector3(0, 0, 0))
        self.assertEqual(p.normal, Vector3(0, 0, 1))

    def test_xz_plane(self) -> None:
        p = Plane.XZ()
        self.assertEqual(p.origin, Vector3(0, 0, 0))
        self.assertEqual(p.normal, Vector3(0, 1, 0))

    def test_yz_plane(self) -> None:
        p = Plane.YZ()
        self.assertEqual(p.origin, Vector3(0, 0, 0))
        self.assertEqual(p.normal, Vector3(1, 0, 0))

    def test_project_xy_roundtrip(self) -> None:
        plane = Plane.XY()
        for x, y in [(0, 0), (10, 20), (-5, 3.5), (1000, -500)]:
            p2d = Vector2(x, y)
            p3d = plane.project_3d(p2d)
            back = plane.project_2d(p3d)
            self.assertAlmostEqual(back.x, x, places=10)
            self.assertAlmostEqual(back.y, y, places=10)

    def test_project_xz_roundtrip(self) -> None:
        plane = Plane.XZ()
        for x, z in [(0, 0), (10, 20), (-5, 3.5)]:
            p2d = Vector2(x, z)
            p3d = plane.project_3d(p2d)
            self.assertAlmostEqual(p3d.x, x, places=10)
            self.assertAlmostEqual(p3d.z, z, places=10)
            self.assertAlmostEqual(p3d.y, 0, places=10)
            back = plane.project_2d(p3d)
            self.assertAlmostEqual(back.x, x, places=10)
            self.assertAlmostEqual(back.y, z, places=10)

    def test_project_yz_roundtrip(self) -> None:
        plane = Plane.YZ()
        for y, z in [(0, 0), (10, 20), (-5, 3.5)]:
            p2d = Vector2(y, z)
            p3d = plane.project_3d(p2d)
            self.assertAlmostEqual(p3d.y, y, places=10)
            self.assertAlmostEqual(p3d.z, z, places=10)
            self.assertAlmostEqual(p3d.x, 0, places=10)
            back = plane.project_2d(p3d)
            self.assertAlmostEqual(back.x, y, places=10)
            self.assertAlmostEqual(back.y, z, places=10)

    def test_arbitrary_plane_roundtrip(self) -> None:
        """Non-standard plane: origin at (1,2,3) with normal (1,1,0)."""
        p = Plane(Vector3(1, 2, 3), Vector3(1, 1, 0))
        # Test arbitrary point
        test_points = [Vector2(5, 10), Vector2(-3, 7), Vector2(0, 0)]
        for pt in test_points:
            p3d = p.project_3d(pt)
            back = p.project_2d(p3d)
            self.assertAlmostEqual(back.x, pt.x, places=8)
            self.assertAlmostEqual(back.y, pt.y, places=8)

    def test_distance_to_arbitrary(self) -> None:
        # Plane: x + y = 0, normal is (1,1,0)/sqrt(2)
        p = Plane(Vector3(0, 0, 0), Vector3(1, 1, 0))
        # Point (1, 0, 0): distance = (1+0)/sqrt(2) = 1/sqrt(2) ≈ 0.707
        d = p.distance_to(Vector3(1, 0, 0))
        expected = 1.0 / math.sqrt(2)
        self.assertAlmostEqual(d, expected, places=10)

    def test_side_positive(self) -> None:
        p = Plane.XY()
        self.assertEqual(p.side(Vector3(0, 0, 5)), 1.0)

    def test_side_negative(self) -> None:
        p = Plane.XY()
        self.assertEqual(p.side(Vector3(0, 0, -5)), -1.0)

    def test_side_on_plane(self) -> None:
        p = Plane.XY()
        self.assertEqual(p.side(Vector3(10, 20, 0)), 0.0)

    def test_degenerate_normal(self) -> None:
        """Plane with near-zero normal should handle gracefully."""
        p = Plane(Vector3.zero(), Vector3(1e-10, 1e-10, 1e-10))
        # Should not crash; normal falls back to Z
        self.assertAlmostEqual(p.normal.length(), 1.0)

    def test_to_dict(self) -> None:
        p = Plane.XY()
        d = p.to_dict()
        self.assertIn("origin", d)
        self.assertIn("normal", d)


class TestUtilityFunctions(unittest.TestCase):
    def test_lerp(self) -> None:
        self.assertEqual(lerp(0, 10, 0.5), 5.0)
        self.assertEqual(lerp(100, 200, 0.25), 125.0)
        self.assertEqual(lerp(5, 5, 100), 5.0)
        self.assertEqual(lerp(0, 10, 0), 0.0)
        self.assertEqual(lerp(0, 10, 1), 10.0)

    def test_clamp(self) -> None:
        self.assertEqual(clamp(5, 0, 10), 5.0)
        self.assertEqual(clamp(-5, 0, 10), 0.0)
        self.assertEqual(clamp(15, 0, 10), 10.0)
        self.assertEqual(clamp(7, 7, 7), 7.0)

    def test_distance(self) -> None:
        a = Vector3(0, 0, 0)
        b = Vector3(3, 4, 0)
        self.assertAlmostEqual(distance(a, b), 5.0)
        self.assertAlmostEqual(distance(a, a), 0.0)

    def test_normalize(self) -> None:
        v = Vector3(3, 4, 0)
        n = normalize(v)
        self.assertAlmostEqual(n.length(), 1.0)
        self.assertAlmostEqual(n.x, 0.6, places=10)

    def test_normalize_zero(self) -> None:
        n = normalize(Vector3(0, 0, 0))
        self.assertEqual(n, Vector3(0, 0, 0))


if __name__ == "__main__":
    unittest.main()
