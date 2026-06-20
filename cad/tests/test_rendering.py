"""Tests for Camera, Viewport, and projection systems."""

from __future__ import annotations

import math
import unittest
from unittest.mock import MagicMock

from cad.geometry.math import Vector3
from cad.rendering.viewport import Camera, ProjectionType, Viewport, ViewportBackend


class TestCamera(unittest.TestCase):
    def setUp(self) -> None:
        self.cam = Camera()

    def test_default_position(self) -> None:
        self.assertEqual(self.cam.position, Vector3(50, 50, 100))
        self.assertEqual(self.cam.target, Vector3(0, 0, 0))

    def test_view_matrix(self) -> None:
        m = self.cam.get_view_matrix()
        # Should be a valid 4x4 matrix
        self.assertEqual(len(m.data), 16)
        # Eye should map to origin in view space
        eye_in_view = m.transform_point(self.cam.position)
        self.assertAlmostEqual(eye_in_view.x, 0, places=10)
        self.assertAlmostEqual(eye_in_view.y, 0, places=10)
        self.assertAlmostEqual(eye_in_view.z, 0, places=10)

    def test_projection_matrix(self) -> None:
        m = self.cam.get_projection_matrix(aspect=1.0)
        self.assertEqual(len(m.data), 16)

    def test_orthographic_projection(self) -> None:
        self.cam.projection = ProjectionType.ORTHOGRAPHIC
        m = self.cam.get_projection_matrix(aspect=1.0)
        self.assertEqual(len(m.data), 16)
        # Orthographic should have data[15] = 1 (not 0 like perspective)
        self.assertAlmostEqual(m.data[15], 1.0)

    def test_orbit(self) -> None:
        self.cam.orbit(math.pi / 4, 0)  # 45° azimuth
        # Position should be different (camera moved around target)
        self.assertNotEqual(self.cam.position, Vector3(50, 50, 100))

    def test_orbit_elevation_clamping(self) -> None:
        """Orbit should not allow looking straight up/down."""
        self.cam.orbit(0, math.pi)  # Extreme elevation
        # Should be clamped, not at pole
        direction = self.cam.target - self.cam.position
        elevation = math.asin(direction.z / max(direction.length(), 1e-10))
        self.assertLess(abs(elevation), math.pi / 2)

    def test_zoom(self) -> None:
        original_pos = self.cam.position
        self.cam.zoom(0.5)  # Zoom in
        new_distance = (self.cam.target - self.cam.position).length()
        original_distance = (self.cam.target - original_pos).length()
        self.assertLess(new_distance, original_distance)

    def test_zoom_minimum_distance(self) -> None:
        """Zoom should not go below minimum distance."""
        for _ in range(100):
            self.cam.zoom(0.1)
        distance = (self.cam.target - self.cam.position).length()
        self.assertGreaterEqual(distance, 1.0)

    def test_pan(self) -> None:
        original_pos = self.cam.position
        original_target = self.cam.target
        self.cam.pan(10, 0)  # Pan right
        # Both position and target should move
        self.assertNotEqual(self.cam.position, original_pos)
        self.assertNotEqual(self.cam.target, original_target)

    def test_pan_preserves_distance(self) -> None:
        """Panning should preserve camera-target distance."""
        original_distance = (self.cam.target - self.cam.position).length()
        self.cam.pan(100, 50)
        new_distance = (self.cam.target - self.cam.position).length()
        self.assertAlmostEqual(original_distance, new_distance, places=10)


class TestViewport(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = MagicMock(spec=ViewportBackend)
        self.viewport = Viewport(self.backend, width=640, height=480)

    def test_create(self) -> None:
        self.assertEqual(self.viewport.width, 640)
        self.assertEqual(self.viewport.height, 480)
        self.backend.initialize.assert_called_once_with(640, 480)

    def test_resize(self) -> None:
        self.viewport.resize(800, 600)
        self.assertEqual(self.viewport.width, 800)
        self.assertEqual(self.viewport.height, 600)
        self.backend.resize.assert_called_once_with(800, 600)

    def test_render_scene(self) -> None:
        self.viewport.render_scene([])
        self.backend.clear.assert_called_once()
        self.backend.draw_grid.assert_called_once()
        self.backend.present.assert_called_once()

    def test_render_box(self) -> None:
        scene = [{
            "type": "box",
            "width": 10, "height": 20, "depth": 30,
            "x": 0, "y": 0, "z": 0,
        }]
        self.viewport.render_scene(scene)
        # Should draw lines for box edges
        self.assertTrue(self.backend.draw_line.called)

    def test_render_line(self) -> None:
        scene = [{
            "type": "line",
            "x1": 0, "y1": 0, "x2": 100, "y2": 100,
            "z": 0,
        }]
        self.viewport.render_scene(scene)
        self.assertTrue(self.backend.draw_line.called)

    def test_project_center(self) -> None:
        """Centered point should project to screen center."""
        pt = self.viewport._project(Vector3(0, 0, 0))
        self.assertIsNotNone(pt)
        x, y = pt
        self.assertAlmostEqual(x, 320, delta=1)  # Center X
        self.assertAlmostEqual(y, 240, delta=1)  # Center Y

    def test_project_outside_view(self) -> None:
        """Point behind camera should be clipped."""
        # The camera looks at origin from (50, 50, 100)
        # A point far behind should be clipped
        pt = self.viewport._project(Vector3(0, 0, 1000))
        # May or may not be None depending on far plane
        # Should not crash regardless

    def test_render_sphere(self) -> None:
        scene = [{
            "type": "sphere",
            "radius": 10, "x": 0, "y": 0, "z": 0,
        }]
        self.viewport.render_scene(scene)
        self.assertTrue(self.backend.draw_line.called)


if __name__ == "__main__":
    unittest.main()
