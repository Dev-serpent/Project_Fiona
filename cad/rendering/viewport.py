"""Viewport and camera abstractions for 3D rendering."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from cad.geometry.math import Vector3, Matrix4


class ProjectionType(Enum):
    PERSPECTIVE = "perspective"
    ORTHOGRAPHIC = "orthographic"


class Camera:
    """Virtual camera for 3D viewport rendering."""

    def __init__(self) -> None:
        self.position = Vector3(50.0, 50.0, 100.0)
        self.target = Vector3(0.0, 0.0, 0.0)
        self.up = Vector3.unit_z()
        self.projection = ProjectionType.PERSPECTIVE
        self.fov = 45.0
        self.near = 1.0
        self.far = 1000.0
        self.ortho_size = 100.0

    def get_view_matrix(self) -> Matrix4:
        return Matrix4.look_at(self.position, self.target, self.up)

    def get_projection_matrix(self, aspect: float) -> Matrix4:
        if self.projection == ProjectionType.PERSPECTIVE:
            return Matrix4.perspective(self.fov, aspect, self.near, self.far)
        else:
            h = self.ortho_size
            w = h * aspect
            m = Matrix4()
            m.data[0] = 2.0 / w
            m.data[5] = 2.0 / h
            m.data[10] = -2.0 / (self.far - self.near)
            m.data[12] = 0.0
            m.data[13] = 0.0
            m.data[14] = -(self.far + self.near) / (self.far - self.near)
            m.data[15] = 1.0
            return m

    def orbit(self, delta_azimuth: float, delta_elevation: float) -> None:
        direction = self.target - self.position
        distance = direction.length()
        azimuth = math.atan2(direction.y, direction.x)
        elevation = math.asin(direction.z / max(distance, 1e-10))
        azimuth += delta_azimuth
        elevation = max(-math.pi / 2 + 0.01, min(math.pi / 2 - 0.01, elevation + delta_elevation))
        self.position = self.target + Vector3(
            distance * math.cos(elevation) * math.cos(azimuth),
            distance * math.cos(elevation) * math.sin(azimuth),
            distance * math.sin(elevation),
        )

    def zoom(self, factor: float) -> None:
        direction = self.target - self.position
        distance = direction.length()
        new_distance = max(1.0, distance * factor)
        self.position = self.target - direction.normalized() * new_distance

    def pan(self, delta_x: float, delta_y: float) -> None:
        forward = (self.target - self.position).normalized()
        right = forward.cross(self.up).normalized()
        up = right.cross(forward)
        self.position = self.position + right * delta_x + up * delta_y
        self.target = self.target + right * delta_x + up * delta_y


class ViewportBackend(ABC):
    """Abstract render backend for a 3D viewport."""

    @abstractmethod
    def initialize(self, width: int, height: int) -> None: ...
    @abstractmethod
    def resize(self, width: int, height: int) -> None: ...
    @abstractmethod
    def clear(self) -> None: ...
    @abstractmethod
    def draw_line(self, x1: float, y1: float, x2: float, y2: float,
                  color: str = "#ffffff", width: float = 1.0) -> None: ...
    @abstractmethod
    def draw_point(self, x: float, y: float, size: float = 4.0,
                   color: str = "#ffffff", label: str = "") -> None: ...
    @abstractmethod
    def draw_grid(self, spacing: float = 40.0,
                  color: str = "#1b2730", center_color: str = "#34515b") -> None: ...
    @abstractmethod
    def draw_text(self, x: float, y: float, text: str,
                  color: str = "#ffffff") -> None: ...
    @abstractmethod
    def present(self) -> None: ...


class Viewport:
    """High-level viewport combining camera, projection, and backend."""

    def __init__(self, backend: ViewportBackend, width: int = 640, height: int = 480) -> None:
        self.camera = Camera()
        self.backend = backend
        self.width = width
        self.height = height
        self.background_color = "#05070a"
        self.backend.initialize(width, height)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.backend.resize(width, height)

    def render_scene(self, objects: list[dict]) -> None:
        """Render a list of scene objects."""
        self.backend.clear()
        self.backend.draw_grid()

        for obj in objects:
            obj_type = obj.get("type", "")
            if obj_type == "box":
                self._render_box(obj)
            elif obj_type == "cylinder":
                self._render_cylinder(obj)
            elif obj_type == "sphere":
                self._render_sphere(obj)
            elif obj_type == "line":
                self._render_line(obj)

        self.backend.present()

    def _project(self, point: Vector3) -> tuple[float, float] | None:
        """Project a 3D point to 2D screen coordinates."""
        aspect = self.width / max(self.height, 1)
        view = self.camera.get_view_matrix()
        proj = self.camera.get_projection_matrix(aspect)
        world_to_ndc = proj @ view
        p = world_to_ndc.transform_point(point)
        if p.z < -1.0 or p.z > 1.0:
            return None
        x = (p.x + 1.0) * 0.5 * self.width
        y = (1.0 - p.y) * 0.5 * self.height
        return (x, y)

    def _render_box(self, obj: dict) -> None:
        from cad.geometry.primitives import Box as BoxPrim
        w = obj.get("width", 10)
        h = obj.get("height", 10)
        d = obj.get("depth", 10)
        ox = obj.get("x", 0)
        oy = obj.get("y", 0)
        oz = obj.get("z", 0)
        verts = [
            Vector3(ox-w/2, oy-h/2, oz-d/2),
            Vector3(ox+w/2, oy-h/2, oz-d/2),
            Vector3(ox+w/2, oy+h/2, oz-d/2),
            Vector3(ox-w/2, oy+h/2, oz-d/2),
            Vector3(ox-w/2, oy-h/2, oz+d/2),
            Vector3(ox+w/2, oy-h/2, oz+d/2),
            Vector3(ox+w/2, oy+h/2, oz+d/2),
            Vector3(ox-w/2, oy+h/2, oz+d/2),
        ]
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        for i, j in edges:
            p1 = self._project(verts[i])
            p2 = self._project(verts[j])
            if p1 and p2:
                self.backend.draw_line(p1[0], p1[1], p2[0], p2[1], "#2fffd3", 2)

    def _render_cylinder(self, obj: dict) -> None:
        # Simplified cylinder as top/bottom circles + side lines
        r = obj.get("radius", 5)
        h = obj.get("height", 15)
        ox = obj.get("x", 0)
        oy = obj.get("y", 0)
        oz = obj.get("z", 0)
        segments = 24
        top_verts = []
        bot_verts = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            top_verts.append(Vector3(ox + r*math.cos(a), oy + r*math.sin(a), oz + h/2))
            bot_verts.append(Vector3(ox + r*math.cos(a), oy + r*math.sin(a), oz - h/2))
        for i in range(segments):
            j = (i + 1) % segments
            for pair in [(top_verts, top_verts), (bot_verts, bot_verts),
                         (top_verts, bot_verts)]:
                p1 = self._project(pair[0][i])
                p2 = self._project(pair[1][j] if pair is not (top_verts, top_verts) else pair[0][j])
                # Actually simpler: just draw top circle, bottom circle, and side lines
        # Draw top circle
        for i in range(segments):
            j = (i + 1) % segments
            p1 = self._project(top_verts[i])
            p2 = self._project(top_verts[j])
            if p1 and p2:
                self.backend.draw_line(p1[0], p1[1], p2[0], p2[1], "#35a7ff", 1)
        # Draw bottom circle
        for i in range(segments):
            j = (i + 1) % segments
            p1 = self._project(bot_verts[i])
            p2 = self._project(bot_verts[j])
            if p1 and p2:
                self.backend.draw_line(p1[0], p1[1], p2[0], p2[1], "#35a7ff", 1)
        # Draw side lines (every 4th)
        for i in range(0, segments, 4):
            p1 = self._project(top_verts[i])
            p2 = self._project(bot_verts[i])
            if p1 and p2:
                self.backend.draw_line(p1[0], p1[1], p2[0], p2[1], "#35a7ff", 1)

    def _render_sphere(self, obj: dict) -> None:
        r = obj.get("radius", 10)
        ox = obj.get("x", 0)
        oy = obj.get("y", 0)
        oz = obj.get("z", 0)
        segments = 20
        # Draw 3 rings (XY, XZ, YZ)
        for (nx, ny, nz) in [(1,0,0), (0,1,0), (0,0,1)]:
            ring = []
            for i in range(segments):
                a = 2 * math.pi * i / segments
                u = Vector3(math.cos(a), math.sin(a), 0)
                # Rotate ring to align with axis
                if nx == 1:
                    pt = Vector3(ox, oy + r*u.x, oz + r*u.y)
                elif ny == 1:
                    pt = Vector3(ox + r*u.x, oy, oz + r*u.y)
                else:
                    pt = Vector3(ox + r*u.x, oy + r*u.y, oz)
                ring.append(pt)
            for i in range(segments):
                j = (i + 1) % segments
                p1 = self._project(ring[i])
                p2 = self._project(ring[j])
                if p1 and p2:
                    self.backend.draw_line(p1[0], p1[1], p2[0], p2[1], "#9fffe8", 1)

    def _render_line(self, obj: dict) -> None:
        x1 = obj.get("x1", 0)
        y1 = obj.get("y1", 0)
        x2 = obj.get("x2", 10)
        y2 = obj.get("y2", 10)
        z = obj.get("z", 0)
        p1 = self._project(Vector3(x1, y1, z))
        p2 = self._project(Vector3(x2, y2, z))
        if p1 and p2:
            self.backend.draw_line(p1[0], p1[1], p2[0], p2[1], "#ffffff", 2)
