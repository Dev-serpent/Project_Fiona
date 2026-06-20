"""3D viewport widget — Tkinter Canvas with orbit/zoom/pan controls."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from cad.core.document import Document
from cad.rendering.viewport import Viewport, Camera, ViewportBackend
from cad.geometry.primitives import Box, Cylinder, Sphere
from cad.geometry.math import Vector3


class TkinterViewportBackend(ViewportBackend):
    """Tkinter Canvas backend for the 3D viewport."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas

    def initialize(self, width: int, height: int) -> None:
        self.canvas.config(width=width, height=height)

    def resize(self, width: int, height: int) -> None:
        self.canvas.config(width=width, height=height)

    def clear(self) -> None:
        self.canvas.delete("all")

    def draw_line(self, x1: float, y1: float, x2: float, y2: float,
                  color: str = "#ffffff", width: float = 1.0) -> None:
        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

    def draw_point(self, x: float, y: float, size: float = 4.0,
                   color: str = "#ffffff", label: str = "") -> None:
        r = size / 2
        self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline=color)
        if label:
            self.canvas.create_text(x + 10, y - 10, text=label,
                                    fill=color, anchor="w")

    def draw_grid(self, spacing: float = 40.0,
                  color: str = "#1b2730", center_color: str = "#34515b") -> None:
        w = self.canvas.winfo_width() or 640
        h = self.canvas.winfo_height() or 480
        cx, cy = w / 2, h / 2
        for x in range(0, w + int(spacing), int(spacing)):
            c = center_color if abs(x - cx) < 2 else color
            self.canvas.create_line(x, 0, x, h, fill=c)
        for y in range(0, h + int(spacing), int(spacing)):
            c = center_color if abs(y - cy) < 2 else color
            self.canvas.create_line(0, y, w, y, fill=c)

    def draw_text(self, x: float, y: float, text: str,
                  color: str = "#ffffff") -> None:
        self.canvas.create_text(x, y, text=text, fill=color, anchor="nw")

    def present(self) -> None:
        pass  # Tkinter renders immediately


class CadViewportWidget(tk.Frame):
    """Interactive 3D viewport widget for the CAD GUI."""

    def __init__(self, parent: tk.Widget, doc: Document,
                 width: int = 640, height: int = 480) -> None:
        super().__init__(parent)
        self.doc = doc
        self.show_grid = True

        self.canvas = tk.Canvas(self, background="#05070a",
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.backend = TkinterViewportBackend(self.canvas)
        self.viewport = Viewport(self.backend, width, height)

        # Mouse interaction
        self._drag_start: tuple[int, int] | None = None
        self._last_x = 0
        self._last_y = 0

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-4>", self._on_scroll)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_scroll)  # Linux scroll down

        self.refresh()

    def set_document(self, doc: Document) -> None:
        self.doc = doc
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the scene from document and re-render."""
        self.canvas.delete("all")

        if self.show_grid:
            self.backend.draw_grid()

        scene_objects = self._build_scene_objects()
        for obj in scene_objects:
            self._render_object(obj)

    def reset_camera(self) -> None:
        self.viewport.camera.position = Vector3(50, 50, 100)
        self.viewport.camera.target = Vector3(0, 0, 0)
        self.refresh()

    def _build_scene_objects(self) -> list[dict]:
        """Convert document objects to renderable dicts."""
        result = []
        for cad_obj in self.doc.objects:
            obj_type = type(cad_obj).__name__
            entry = {"type": obj_type}

            if isinstance(cad_obj, Box):
                entry.update({
                    "width": cad_obj.get_property_value("width"),
                    "height": cad_obj.get_property_value("height"),
                    "depth": cad_obj.get_property_value("depth"),
                    "x": cad_obj.get_property_value("x"),
                    "y": cad_obj.get_property_value("y"),
                    "z": cad_obj.get_property_value("z"),
                })
            elif isinstance(cad_obj, Cylinder):
                entry.update({
                    "radius": cad_obj.get_property_value("radius"),
                    "height": cad_obj.get_property_value("height"),
                    "x": cad_obj.get_property_value("x"),
                    "y": cad_obj.get_property_value("y"),
                    "z": cad_obj.get_property_value("z"),
                })
            elif isinstance(cad_obj, Sphere):
                entry.update({
                    "radius": cad_obj.get_property_value("radius"),
                    "x": cad_obj.get_property_value("x"),
                    "y": cad_obj.get_property_value("y"),
                    "z": cad_obj.get_property_value("z"),
                })

            result.append(entry)
        return result

    def _render_object(self, obj: dict) -> None:
        """Render a single scene object onto the canvas."""
        obj_type = obj.get("type", "")

        if obj_type == "Box":
            self._render_box(obj)
        elif obj_type == "Cylinder":
            self._render_cylinder(obj)
        elif obj_type == "Sphere":
            self._render_sphere(obj)

    def _project(self, point: Vector3) -> tuple[float, float] | None:
        """Project a 3D point to 2D screen coordinates."""
        w = self.canvas.winfo_width() or 640
        h = self.canvas.winfo_height() or 480
        aspect = w / max(h, 1)
        view = self.viewport.camera.get_view_matrix()
        proj = self.viewport.camera.get_projection_matrix(aspect)
        world_to_ndc = proj @ view
        p = world_to_ndc.transform_point(point)
        if p.z < -1.0 or p.z > 1.0:
            return None
        sx = (p.x + 1.0) * 0.5 * w
        sy = (1.0 - p.y) * 0.5 * h
        return (sx, sy)

    def _render_box(self, obj: dict) -> None:
        w = obj.get("width", 10) / 2
        h = obj.get("height", 10) / 2
        d = obj.get("depth", 10) / 2
        ox = obj.get("x", 0)
        oy = obj.get("y", 0)
        oz = obj.get("z", 0)
        verts = [
            Vector3(ox-w, oy-h, oz-d), Vector3(ox+w, oy-h, oz-d),
            Vector3(ox+w, oy+h, oz-d), Vector3(ox-w, oy+h, oz-d),
            Vector3(ox-w, oy-h, oz+d), Vector3(ox+w, oy-h, oz+d),
            Vector3(ox+w, oy+h, oz+d), Vector3(ox-w, oy+h, oz+d),
        ]
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
                 (0,4),(1,5),(2,6),(3,7)]
        for i, j in edges:
            p1 = self._project(verts[i])
            p2 = self._project(verts[j])
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill="#2fffd3", width=2)

    def _render_cylinder(self, obj: dict) -> None:
        r = obj.get("radius", 5)
        h = obj.get("height", 15)
        ox = obj.get("x", 0)
        oy = obj.get("y", 0)
        oz = obj.get("z", 0)
        import math
        seg = 24
        top = [Vector3(ox + r*math.cos(2*math.pi*i/seg),
                       oy + r*math.sin(2*math.pi*i/seg),
                       oz + h/2) for i in range(seg)]
        bot = [Vector3(ox + r*math.cos(2*math.pi*i/seg),
                       oy + r*math.sin(2*math.pi*i/seg),
                       oz - h/2) for i in range(seg)]
        # Top circle
        for i in range(seg):
            j = (i + 1) % seg
            p1 = self._project(top[i])
            p2 = self._project(top[j])
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill="#35a7ff", width=1)
        # Bottom circle
        for i in range(seg):
            j = (i + 1) % seg
            p1 = self._project(bot[i])
            p2 = self._project(bot[j])
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill="#35a7ff", width=1)
        # Side lines
        for i in range(0, seg, 4):
            p1 = self._project(top[i])
            p2 = self._project(bot[i])
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill="#35a7ff", width=1)

    def _render_sphere(self, obj: dict) -> None:
        r = obj.get("radius", 10)
        ox = obj.get("x", 0)
        oy = obj.get("y", 0)
        oz = obj.get("z", 0)
        import math
        seg = 20
        for (nx, ny, nz) in [(1,0,0), (0,1,0), (0,0,1)]:
            ring = []
            for i in range(seg):
                a = 2 * math.pi * i / seg
                if nx == 1:
                    pt = Vector3(ox, oy + r*math.cos(a), oz + r*math.sin(a))
                elif ny == 1:
                    pt = Vector3(ox + r*math.cos(a), oy, oz + r*math.sin(a))
                else:
                    pt = Vector3(ox + r*math.cos(a), oy + r*math.sin(a), oz)
                ring.append(pt)
            for i in range(seg):
                j = (i + 1) % seg
                p1 = self._project(ring[i])
                p2 = self._project(ring[j])
                if p1 and p2:
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                            fill="#9fffe8", width=1)

    # ── Mouse Handlers ──────────────────────────────────────────────

    def _on_resize(self, event: tk.Event) -> None:
        self.viewport.resize(event.width, event.height)
        self.refresh()

    def _on_mouse_down(self, event: tk.Event) -> None:
        self._drag_start = (event.x, event.y)
        self._last_x = event.x
        self._last_y = event.y

    def _on_mouse_drag(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        dx = event.x - self._last_x
        dy = event.y - self._last_y
        self._last_x = event.x
        self._last_y = event.y

        # Orbit on left-button drag
        self.viewport.camera.orbit(-dx * 0.005, dy * 0.005)
        self.refresh()

    def _on_mouse_up(self, event: tk.Event) -> None:
        self._drag_start = None

    def _on_scroll(self, event: tk.Event) -> None:
        factor = 0.9 if event.delta < 0 or event.num == 5 else 1.1
        self.viewport.camera.zoom(factor)
        self.refresh()
