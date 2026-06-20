"""3D viewport widget — Tkinter Canvas with orbit/zoom/pan controls."""

from __future__ import annotations

import math
import tkinter as tk
from typing import Any, Callable

from cad.core.document import Document
from cad.rendering.viewport import Viewport, Camera, ViewportBackend
from cad.geometry.primitives import Box, Cylinder, Sphere
from cad.geometry.math import Vector3
from cad.geometry.intersection import (
    ray_aabb_intersect,
    ray_sphere_intersect,
    ray_cylinder_intersect,
)


# ── Constants ──────────────────────────────────────────────────────────

BOX_BASE_COLOR = "#2fffd3"
CYL_BASE_COLOR = "#35a7ff"
SPH_BASE_COLOR = "#9fffe8"
HIGHLIGHT_COLOR = "#ff8800"
HIGHLIGHT_WIRE_COLOR = "#ffff00"
DRAG_THRESHOLD = 3  # pixels
ORBIT_SENSITIVITY = 0.005
PAN_SENSITIVITY = 0.1


# ══════════════════════════════════════════════════════════════════════
# Backend
# ══════════════════════════════════════════════════════════════════════


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

    def draw_polygon(self, points: list[tuple[float, float]],
                     fill_color: str = "#aaaaaa",
                     outline_color: str | None = None,
                     outline_width: float = 1.0) -> None:
        flat_coords = []
        for pt in points:
            flat_coords.append(pt[0])
            flat_coords.append(pt[1])
        kwargs = {
            "fill": fill_color,
            "outline": outline_color or fill_color,
        }
        if outline_width:
            kwargs["width"] = outline_width
        self.canvas.create_polygon(*flat_coords, **kwargs)

    def present(self) -> None:
        pass  # Tkinter renders immediately


# ══════════════════════════════════════════════════════════════════════
# Viewport Widget
# ══════════════════════════════════════════════════════════════════════


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

        # ── Selection state ───────────────────────────────────────────
        self._selected_objects: set[str] = set()
        self._selection_callback: Callable[[str | None], None] | None = None
        self._context_callbacks: dict[str, Callable[[], None]] = {}
        self._mode_callback: Callable[[str], None] | None = None

        # ── Left-button drag / click discrimination ───────────────────
        self._drag_start: tuple[int, int] | None = None
        self._last_x = 0
        self._last_y = 0

        # ── Pan state (middle / right button) ─────────────────────────
        self._pan_start: tuple[int, int] | None = None
        self._pan_last: tuple[int, int] | None = None

        # Right-click context-menu discrimination
        self._right_drag_start: tuple[int, int] | None = None
        self._right_dragged: bool = False

        # ── Context menu ──────────────────────────────────────────────
        self._context_menu = tk.Menu(self.canvas, tearoff=0)
        self._build_context_menu()

        # ── Mouse and keyboard bindings ───────────────────────────────
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-4>", self._on_scroll)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_scroll)  # Linux scroll down

        # Pan bindings
        self.canvas.bind("<ButtonPress-2>", self._on_pan_down)
        self.canvas.bind("<ButtonPress-3>", self._on_pan_down)
        self.canvas.bind("<B2-Motion>", self._on_pan_drag)
        self.canvas.bind("<B3-Motion>", self._on_pan_drag)

        # Right-click release → context menu if not a drag
        self.canvas.bind("<ButtonRelease-2>", self._on_middle_release)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)

        self.refresh()

    # ── Public API ──────────────────────────────────────────────────

    def set_document(self, doc: Document) -> None:
        self.doc = doc
        self.refresh()

    def set_selection(self, names: set[str]) -> None:
        """Update the set of selected object names and re-render."""
        self._selected_objects = set(names)
        self._update_context_menu_state()
        self.refresh()

    def reset_camera(self) -> None:
        self.viewport.camera.position = Vector3(50, 50, 100)
        self.viewport.camera.target = Vector3(0, 0, 0)
        self.refresh()

    # ── Refresh ─────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Rebuild the scene from document and re-render."""
        self.canvas.delete("all")

        if self.show_grid:
            self.backend.draw_grid()

        scene_objects = self._build_scene_objects()
        for obj in scene_objects:
            self._render_object(obj)

        self._draw_axes_indicator()

    # ── Scene Building ──────────────────────────────────────────────

    def _build_scene_objects(self) -> list[dict]:
        """Convert document objects to renderable dicts."""
        result = []
        for cad_obj in self.doc.objects:
            obj_type = type(cad_obj).__name__
            entry: dict[str, Any] = {
                "type": obj_type,
                "name": cad_obj.name,
                "is_selected": cad_obj.name in self._selected_objects,
            }

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

    # ── Rendering Dispatcher ────────────────────────────────────────

    def _render_object(self, obj: dict) -> None:
        """Render a single scene object onto the canvas."""
        obj_type = obj.get("type", "")

        if obj_type == "Box":
            self._render_box(obj)
        elif obj_type == "Cylinder":
            self._render_cylinder(obj)
        elif obj_type == "Sphere":
            self._render_sphere(obj)

    # ── Shading helpers ─────────────────────────────────────────────

    @staticmethod
    def _face_brightness(face_center: Vector3, face_normal: Vector3,
                         camera_pos: Vector3) -> float:
        """Compute brightness factor (0.3–1.0) based on orientation to camera."""
        view_dir = (camera_pos - face_center).normalized()
        dot = -face_normal.dot(view_dir)  # positive when facing camera
        dot = max(0.0, min(1.0, dot))
        return 0.3 + 0.7 * dot

    @staticmethod
    def _shade_color(hex_color: str, brightness: float) -> str:
        """Scale RGB channels of a hex colour by *brightness* (0–1)."""
        brightness = max(0.0, min(1.0, brightness))
        r = int(int(hex_color[1:3], 16) * brightness)
        g = int(int(hex_color[3:5], 16) * brightness)
        b = int(int(hex_color[5:7], 16) * brightness)
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _get_base_color(self, obj_type: str) -> str:
        if obj_type == "Box":
            return BOX_BASE_COLOR
        elif obj_type == "Cylinder":
            return CYL_BASE_COLOR
        elif obj_type == "Sphere":
            return SPH_BASE_COLOR
        return "#888888"

    def _get_fill_color(self, obj: dict) -> str:
        """Return the fill (face) colour for an object."""
        if obj.get("is_selected"):
            return HIGHLIGHT_COLOR
        return self._get_base_color(obj.get("type", ""))

    def _get_wire_color(self, obj: dict) -> str:
        """Return the wireframe colour for an object."""
        if obj.get("is_selected"):
            return HIGHLIGHT_WIRE_COLOR
        return self._get_base_color(obj.get("type", ""))

    def _get_wire_width(self, obj: dict) -> int:
        return 3 if obj.get("is_selected") else 1

    # ── Polygon fill helper ─────────────────────────────────────────

    def _draw_filled_poly(self, world_points: list[Vector3],
                          fill_color: str) -> None:
        """Project a list of 3D points to 2D and draw a filled polygon."""
        screen_points: list[tuple[float, float]] = []
        for wp in world_points:
            sp = self._project(wp)
            if sp is None:
                return  # abort if any point is behind camera
            screen_points.append(sp)
        if len(screen_points) >= 3:
            self.backend.draw_polygon(screen_points, fill_color=fill_color)

    # ── Box Rendering ───────────────────────────────────────────────

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

        # Face definitions: (indices, normal)
        faces = [
            ([0, 1, 2, 3], Vector3(0, 0, -1)),  # front
            ([4, 5, 6, 7], Vector3(0, 0, +1)),  # back
            ([0, 4, 7, 3], Vector3(-1, 0, 0)),  # left
            ([1, 5, 6, 2], Vector3(+1, 0, 0)),  # right
            ([0, 1, 5, 4], Vector3(0, -1, 0)),  # bottom
            ([3, 2, 6, 7], Vector3(0, +1, 0)),  # top
        ]

        cam_pos = self.viewport.camera.position
        base_color = self._get_fill_color(obj)

        # ── Filled faces ─────────────────────────────────────────────
        for indices, normal in faces:
            face_verts = [verts[i] for i in indices]
            center = Vector3(
                sum(v.x for v in face_verts) / 4,
                sum(v.y for v in face_verts) / 4,
                sum(v.z for v in face_verts) / 4,
            )
            brightness = self._face_brightness(center, normal, cam_pos)
            fill = self._shade_color(base_color, brightness)
            self._draw_filled_poly(face_verts, fill)

        # ── Wireframe overlay ────────────────────────────────────────
        wire_color = self._get_wire_color(obj)
        wire_width = self._get_wire_width(obj)
        edges = [(0, 1), (1, 2), (2, 3), (3, 0),
                 (4, 5), (5, 6), (6, 7), (7, 4),
                 (0, 4), (1, 5), (2, 6), (3, 7)]
        for i, j in edges:
            p1 = self._project(verts[i])
            p2 = self._project(verts[j])
            if p1 and p2:
                self.canvas.create_line(
                    p1[0], p1[1], p2[0], p2[1],
                    fill=wire_color, width=wire_width,
                )

    # ── Cylinder Rendering ──────────────────────────────────────────

    def _render_cylinder(self, obj: dict) -> None:
        r = obj.get("radius", 5)
        h = obj.get("height", 15)
        ox = obj.get("x", 0)
        oy = obj.get("y", 0)
        oz = obj.get("z", 0)
        seg = 24

        top = [Vector3(ox + r * math.cos(2 * math.pi * i / seg),
                       oy + r * math.sin(2 * math.pi * i / seg),
                       oz + h / 2) for i in range(seg)]
        bot = [Vector3(ox + r * math.cos(2 * math.pi * i / seg),
                       oy + r * math.sin(2 * math.pi * i / seg),
                       oz - h / 2) for i in range(seg)]

        cam_pos = self.viewport.camera.position
        cyl_center = Vector3(ox, oy, oz)
        base_color = self._get_fill_color(obj)
        is_selected = obj.get("is_selected", False)

        # ── Filled faces ─────────────────────────────────────────────

        # Top cap (normal = +Z)
        top_normal = Vector3(0, 0, 1)
        top_center = Vector3(ox, oy, oz + h / 2)
        if self._face_brightness(top_center, top_normal, cam_pos) > 0.3:
            fill = self._shade_color(base_color,
                                     self._face_brightness(top_center, top_normal, cam_pos))
            self._draw_filled_poly(top, fill)

        # Bottom cap (normal = -Z)
        bot_normal = Vector3(0, 0, -1)
        bot_center = Vector3(ox, oy, oz - h / 2)
        if self._face_brightness(bot_center, bot_normal, cam_pos) > 0.3:
            fill = self._shade_color(base_color,
                                     self._face_brightness(bot_center, bot_normal, cam_pos))
            self._draw_filled_poly(bot, fill)

        # Body segments
        for i in range(seg):
            j = (i + 1) % seg
            quad = [top[i], top[j], bot[j], bot[i]]
            # Face normal points radially outward
            angle = 2 * math.pi * (i + 0.5) / seg
            normal = Vector3(math.cos(angle), math.sin(angle), 0)
            quad_center = Vector3(
                (top[i].x + top[j].x + bot[j].x + bot[i].x) / 4,
                (top[i].y + top[j].y + bot[j].y + bot[i].y) / 4,
                (top[i].z + top[j].z + bot[j].z + bot[i].z) / 4,
            )
            if self._face_brightness(quad_center, normal, cam_pos) > 0.3:
                fill = self._shade_color(
                    base_color,
                    self._face_brightness(quad_center, normal, cam_pos),
                )
                self._draw_filled_poly(quad, fill)

        # ── Wireframe overlay ────────────────────────────────────────
        wire_color = self._get_wire_color(obj)
        wire_width = self._get_wire_width(obj)

        # Top circle
        for i in range(seg):
            j = (i + 1) % seg
            p1 = self._project(top[i])
            p2 = self._project(top[j])
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill=wire_color, width=wire_width)
        # Bottom circle
        for i in range(seg):
            j = (i + 1) % seg
            p1 = self._project(bot[i])
            p2 = self._project(bot[j])
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill=wire_color, width=wire_width)
        # Side lines
        stride = 4 if not is_selected else 2
        for i in range(0, seg, stride):
            p1 = self._project(top[i])
            p2 = self._project(bot[i])
            if p1 and p2:
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill=wire_color, width=wire_width)

        # If selected, also draw every side line for full visibility
        if is_selected:
            for i in range(seg):
                if i % stride == 0:
                    continue
                p1 = self._project(top[i])
                p2 = self._project(bot[i])
                if p1 and p2:
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                            fill=wire_color, width=wire_width)

    # ── Sphere Rendering ────────────────────────────────────────────

    def _render_sphere(self, obj: dict) -> None:
        r = obj.get("radius", 10)
        ox = obj.get("x", 0)
        oy = obj.get("y", 0)
        oz = obj.get("z", 0)

        cam_pos = self.viewport.camera.position
        center = Vector3(ox, oy, oz)
        base_color = self._get_fill_color(obj)

        # ── Filled faces (lat/lon grid) ──────────────────────────────
        lat_divs = 8
        lon_divs = 12

        for lat in range(lat_divs):
            theta1 = math.pi * lat / lat_divs
            theta2 = math.pi * (lat + 1) / lat_divs
            for lon in range(lon_divs):
                phi1 = 2 * math.pi * lon / lon_divs
                phi2 = 2 * math.pi * (lon + 1) / lon_divs

                p1 = Vector3(
                    ox + r * math.sin(theta1) * math.cos(phi1),
                    oy + r * math.sin(theta1) * math.sin(phi1),
                    oz + r * math.cos(theta1),
                )
                p2 = Vector3(
                    ox + r * math.sin(theta1) * math.cos(phi2),
                    oy + r * math.sin(theta1) * math.sin(phi2),
                    oz + r * math.cos(theta1),
                )
                p3 = Vector3(
                    ox + r * math.sin(theta2) * math.cos(phi2),
                    oy + r * math.sin(theta2) * math.sin(phi2),
                    oz + r * math.cos(theta2),
                )
                p4 = Vector3(
                    ox + r * math.sin(theta2) * math.cos(phi1),
                    oy + r * math.sin(theta2) * math.sin(phi1),
                    oz + r * math.cos(theta2),
                )

                # Facet center and outward normal
                fc = Vector3(
                    (p1.x + p2.x + p3.x + p4.x) / 4,
                    (p1.y + p2.y + p3.y + p4.y) / 4,
                    (p1.z + p2.z + p3.z + p4.z) / 4,
                )
                normal = (fc - center).normalized()
                brightness = self._face_brightness(fc, normal, cam_pos)
                if brightness > 0.3:
                    fill = self._shade_color(base_color, brightness)
                    self._draw_filled_poly([p1, p2, p3, p4], fill)

        # ── Wireframe overlay (three orthogonal rings) ───────────────
        wire_color = self._get_wire_color(obj)
        wire_width = self._get_wire_width(obj)
        ring_seg = 20

        for (nx, ny, nz) in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:
            ring = []
            for i in range(ring_seg):
                a = 2 * math.pi * i / ring_seg
                if nx == 1:
                    pt = Vector3(ox, oy + r * math.cos(a), oz + r * math.sin(a))
                elif ny == 1:
                    pt = Vector3(ox + r * math.cos(a), oy, oz + r * math.sin(a))
                else:
                    pt = Vector3(ox + r * math.cos(a), oy + r * math.sin(a), oz)
                ring.append(pt)
            for i in range(ring_seg):
                j = (i + 1) % ring_seg
                p1 = self._project(ring[i])
                p2 = self._project(ring[j])
                if p1 and p2:
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                            fill=wire_color, width=wire_width)

    # ── Axes Indicator (M2.2) ───────────────────────────────────────

    def _draw_axes_indicator(self) -> None:
        """Draw XYZ axes triad in the bottom-left corner of the viewport."""
        w = self.canvas.winfo_width() or 640
        h = self.canvas.winfo_height() or 480
        origin_x, origin_y = 55, h - 55
        size = 28

        cam = self.viewport.camera
        fwd = (cam.target - cam.position).normalized()
        right = fwd.cross(cam.up).normalized()
        up = right.cross(fwd)

        axes_data = [
            (right, "#ff4444", "X"),
            (up, "#44ff44", "Y"),
            (fwd, "#4444ff", "Z"),
        ]

        ref_point = cam.target

        for direction, color, label in axes_data:
            offset = ref_point + direction * 2.0  # small offset in world space
            ref_screen = self._project(ref_point)
            if ref_screen is None:
                continue
            end_screen = self._project(offset)
            if end_screen is None:
                continue

            # Compute screen-space direction from the projected offset
            dx = end_screen[0] - ref_screen[0]
            dy = end_screen[1] - ref_screen[1]
            length = math.sqrt(dx * dx + dy * dy)
            if length < 0.001:
                continue

            # Normalize and scale to fixed pixel size
            dx = dx / length * size
            dy = dy / length * size
            ex = origin_x + dx
            ey = origin_y + dy

            # Draw axis line with arrowhead
            self.canvas.create_line(
                origin_x, origin_y, ex, ey,
                fill=color, width=2, arrow=tk.LAST,
                arrowshape=(8, 10, 5),
            )

            # Label placed slightly beyond the tip
            label_dx = 8 if dx >= 0 else -16
            label_dy = -8 if dy <= 0 else 16
            self.canvas.create_text(
                ex + label_dx, ey + label_dy,
                text=label, fill=color,
                font=("", 10, "bold"),
            )

    # ── Ray-Picking (M3.1) ──────────────────────────────────────────

    def _on_select_click(self, event: tk.Event) -> None:
        """Cast a ray through the click point and select the closest object."""
        w = self.canvas.winfo_width() or 640
        h = self.canvas.winfo_height() or 480
        aspect = w / max(h, 1)

        # Convert to NDC
        ndc_x = (2.0 * event.x / w) - 1.0
        ndc_y = 1.0 - (2.0 * event.y / h)

        # Get view-projection matrix
        view = self.viewport.camera.get_view_matrix()
        proj = self.viewport.camera.get_projection_matrix(aspect)
        view_proj = proj @ view

        # Invert it
        inv_vp = view_proj.inverse()
        if inv_vp is None:
            return

        # Create ray in world space
        near_point = inv_vp.transform_point(Vector3(ndc_x, ndc_y, -1.0))
        far_point = inv_vp.transform_point(Vector3(ndc_x, ndc_y, 1.0))
        ray_origin = near_point
        ray_dir = (far_point - near_point).normalized()

        closest_obj: Any = None
        closest_t = float("inf")

        for cad_obj in self.doc.objects:
            obj_type = type(cad_obj).__name__

            if isinstance(cad_obj, Box):
                w = cad_obj.get_property_value("width") / 2
                h = cad_obj.get_property_value("height") / 2
                d = cad_obj.get_property_value("depth") / 2
                ox = cad_obj.get_property_value("x")
                oy = cad_obj.get_property_value("y")
                oz = cad_obj.get_property_value("z")
                aabb_min = Vector3(ox - w, oy - h, oz - d)
                aabb_max = Vector3(ox + w, oy + h, oz + d)
                t = ray_aabb_intersect(ray_origin, ray_dir, aabb_min, aabb_max)
            elif isinstance(cad_obj, Cylinder):
                r = cad_obj.get_property_value("radius")
                h_val = cad_obj.get_property_value("height")
                ox = cad_obj.get_property_value("x")
                oy = cad_obj.get_property_value("y")
                oz = cad_obj.get_property_value("z")
                t = ray_cylinder_intersect(
                    ray_origin, ray_dir,
                    Vector3(ox, oy, oz), r, h_val,
                )
            elif isinstance(cad_obj, Sphere):
                r = cad_obj.get_property_value("radius")
                ox = cad_obj.get_property_value("x")
                oy = cad_obj.get_property_value("y")
                oz = cad_obj.get_property_value("z")
                t = ray_sphere_intersect(
                    ray_origin, ray_dir,
                    Vector3(ox, oy, oz), r,
                )
            else:
                continue

            if t is not None and 0 < t < closest_t:
                closest_t = t
                closest_obj = cad_obj

        if closest_obj and self._selection_callback:
            self._selection_callback(closest_obj.name)
        elif self._selection_callback:
            self._selection_callback(None)

    # ── 2D Projection ───────────────────────────────────────────────

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

    # ── Context Menu (M5.1) ─────────────────────────────────────────

    def _build_context_menu(self) -> None:
        """Build the right-click context menu."""
        menu = self._context_menu
        menu.add_command(
            label="Select All",
            command=lambda: self._dispatch_context_action("select_all"),
        )
        self._ctx_delete_idx = menu.index("end")
        menu.add_command(
            label="Delete Selected",
            command=lambda: self._dispatch_context_action("delete_selected"),
        )
        self._ctx_dup_idx = menu.index("end")
        menu.add_command(
            label="Duplicate",
            command=lambda: self._dispatch_context_action("duplicate"),
        )
        menu.add_separator()
        menu.add_command(
            label="Reset View",
            command=lambda: self._dispatch_context_action("reset_view"),
        )
        menu.add_command(
            label="Toggle Grid",
            command=lambda: self._dispatch_context_action("toggle_grid"),
        )
        menu.add_separator()
        menu.add_command(
            label="Create Box",
            command=lambda: self._dispatch_context_action("create_box"),
        )
        menu.add_command(
            label="Create Cylinder",
            command=lambda: self._dispatch_context_action("create_cylinder"),
        )
        menu.add_command(
            label="Create Sphere",
            command=lambda: self._dispatch_context_action("create_sphere"),
        )

        # Initially disable delete/duplicate
        self._update_context_menu_state()

    def _update_context_menu_state(self) -> None:
        """Enable/disable item-specific menu entries based on selection."""
        state = "normal" if self._selected_objects else "disabled"
        try:
            self._context_menu.entryconfig(self._ctx_delete_idx, state=state)
            self._context_menu.entryconfig(self._ctx_dup_idx, state=state)
        except tk.TclError:
            pass  # menu not fully built yet

    def _dispatch_context_action(self, action: str) -> None:
        """Look up and call the registered callback for *action*."""
        cb = self._context_callbacks.get(action)
        if cb:
            cb()

    def _show_context_menu(self, event: tk.Event) -> None:
        self._update_context_menu_state()
        self._context_menu.post(event.x_root, event.y_root)

    # ── Mouse Handlers — Pan (M1.3) ─────────────────────────────────

    def _on_pan_down(self, event: tk.Event) -> None:
        self._pan_start = (event.x, event.y)
        self._pan_last = (event.x, event.y)

        # Track right-button separately for context-menu discrimination
        if event.num == 3:
            self._right_drag_start = (event.x, event.y)
            self._right_dragged = False

    def _on_pan_drag(self, event: tk.Event) -> None:
        if self._pan_last is None:
            return
        dx = event.x - self._pan_last[0]
        dy = event.y - self._pan_last[1]
        self._pan_last = (event.x, event.y)

        # Shift+pan moves along the world Z axis instead of the camera XY plane
        if event.state & 0x0001:  # Shift key held — move directly along world Z
            cam = self.viewport.camera
            cam.position = Vector3(
                cam.position.x,
                cam.position.y,
                cam.position.z - dy * PAN_SENSITIVITY,
            )
        else:
            self.viewport.camera.pan(-dx * PAN_SENSITIVITY, -dy * PAN_SENSITIVITY)
        self.refresh()

        # Mark as drag for context-menu discrimination
        if self._right_drag_start is not None:
            total_dx = abs(event.x - self._right_drag_start[0])
            total_dy = abs(event.y - self._right_drag_start[1])
            if total_dx >= DRAG_THRESHOLD or total_dy >= DRAG_THRESHOLD:
                self._right_dragged = True

    def _on_middle_release(self, event: tk.Event) -> None:
        """Middle-button release — just clean up (no context menu)."""
        self._pan_start = None
        self._pan_last = None

    def _on_right_release(self, event: tk.Event) -> None:
        """Right-button release — show context menu if no drag occurred."""
        if (self._right_drag_start is not None
                and not self._right_dragged):
            total_dx = abs(event.x - self._right_drag_start[0])
            total_dy = abs(event.y - self._right_drag_start[1])
            if total_dx < DRAG_THRESHOLD and total_dy < DRAG_THRESHOLD:
                self._show_context_menu(event)

        self._pan_start = None
        self._pan_last = None
        self._right_drag_start = None
        self._right_dragged = False

    # ── Mouse Handlers — Left button orbit / select (M3.1) ──────────

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

        # Once we've moved past threshold, it's definitely a drag
        if (abs(event.x - self._drag_start[0]) >= DRAG_THRESHOLD
                or abs(event.y - self._drag_start[1]) >= DRAG_THRESHOLD):
            self.viewport.camera.orbit(-dx * ORBIT_SENSITIVITY,
                                       dy * ORBIT_SENSITIVITY)
            self.refresh()

    def _on_mouse_up(self, event: tk.Event) -> None:
        if self._drag_start is not None:
            total_dx = abs(event.x - self._drag_start[0])
            total_dy = abs(event.y - self._drag_start[1])
            if total_dx < DRAG_THRESHOLD and total_dy < DRAG_THRESHOLD:
                self._on_select_click(event)
        self._drag_start = None

    # ── Mouse Handlers — Scroll zoom ────────────────────────────────

    def _on_scroll(self, event: tk.Event) -> None:
        factor = 0.9 if event.delta < 0 or event.num == 5 else 1.1
        self.viewport.camera.zoom(factor)
        self.refresh()

    # ── Mouse Handlers — Resize ─────────────────────────────────────

    def _on_resize(self, event: tk.Event) -> None:
        self.viewport.resize(event.width, event.height)
        self.refresh()
