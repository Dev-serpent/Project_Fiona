"""Camera controls dialog — azimuth, elevation, and depth sliders."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from cad.geometry.math import Vector3

if TYPE_CHECKING:
    from cad.gui.viewport import CadViewportWidget


# Per-axis slider configuration: (min, max, resolution_steps, label_suffix)
SLIDER_CFG: dict[str, tuple[float, float, int, str]] = {
    "x": (-180.0, 180.0, 360, "°"),
    "y": (-90.0, 90.0, 180, "°"),
    "z": (-500.0, 500.0, 1000, ""),
}


class CameraControlsDialog:
    """Floating dialog with azimuth, elevation, and depth sliders.

    - X slider → azimuth (rotate left/right around the target, -180° to 180°)
    - Y slider → elevation (tilt up/down, -90° to 90°)
    - Z slider → camera position.z (move forward/back, -500 to 500)
    """

    def __init__(self, parent: tk.Tk, viewport: CadViewportWidget) -> None:
        self.parent = parent
        self.viewport = viewport
        self._window: tk.Toplevel | None = None

        # Track whether values are being set programmatically to avoid
        # recursive slider-triggered updates
        self._updating_sliders: bool = False

    def show(self) -> None:
        """Open or raise the camera controls dialog."""
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            self._window.focus_force()
            return

        self._window = tk.Toplevel(self.parent)
        self._window.title("Camera Controls")
        self._window.geometry("360x250")
        self._window.resizable(False, False)
        self._window.transient(self.parent)
        self._window.grab_set()

        # Keep a reference so garbage collector doesn't close it
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

        # Sync sliders to the current camera state
        self._sync_from_camera()

    def _build_ui(self) -> None:
        """Build the slider layout."""
        frame = ttk.Frame(self._window, padding=12)
        frame.pack(fill="both", expand=True)

        axis_labels = {
            "x": ("X", "#ff4444"),
            "y": ("Y", "#44ff44"),
            "z": ("Z", "#4444ff"),
        }

        self._sliders: dict[str, ttk.Scale] = {}
        self._labels: dict[str, ttk.Label] = {}
        self._vars: dict[str, tk.DoubleVar] = {}

        for row, (axis, (label, color)) in enumerate(axis_labels.items()):
            cfg = SLIDER_CFG[axis]
            lo, hi, _, suffix = cfg

            var = tk.DoubleVar(value=0.0)
            self._vars[axis] = var

            ttk.Label(frame, text=label, foreground=color,
                      font=("", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 4))

            slider = ttk.Scale(
                frame, from_=lo, to=hi,
                variable=var, orient="horizontal",
                command=lambda v, a=axis: self._on_slider_drag(a),
            )
            slider.grid(row=row, column=1, sticky="ew", padx=2, pady=4)
            self._sliders[axis] = slider

            lbl = ttk.Label(frame, text="0.0", width=10, anchor="e")
            lbl.grid(row=row, column=2, padx=(4, 0))
            self._labels[axis] = lbl

        # ── Button row ──────────────────────────────────────────────
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0))

        ttk.Button(
            btn_frame, text="Reset View",
            command=self._on_reset,
        ).pack(side="left", padx=2)

        ttk.Button(
            btn_frame, text="Center on Origin",
            command=self._on_center_origin,
        ).pack(side="left", padx=2)

        ttk.Button(
            btn_frame, text="Top View (Z+)",
            command=self._on_top_view,
        ).pack(side="left", padx=2)

        ttk.Button(
            btn_frame, text="Front View (Y+)",
            command=self._on_front_view,
        ).pack(side="left", padx=2)

        # Help text
        ttk.Label(
            frame,
            text=("X: rotate around Z (azimuth)  |  "
                  "Y: tilt up/down (elevation)  |  "
                  "Z: move forward/back"),
            foreground="#888888",
            font=("", 8),
        ).grid(row=4, column=0, columnspan=3, pady=(8, 0), sticky="w")

        # Make the slider column expand
        frame.columnconfigure(1, weight=1)

    def _on_slider_drag(self, axis: str) -> None:
        """Called when a slider is dragged. Updates camera and viewport."""
        if self._updating_sliders:
            return

        cfg = SLIDER_CFG[axis]
        _, _, _, suffix = cfg

        # Update the value label
        raw = self._vars[axis].get()
        self._labels[axis].config(text=f"{raw:.1f}{suffix}")

        cam = self.viewport.viewport.camera

        if axis == "x":
            cam.set_azimuth(math.radians(raw))
        elif axis == "y":
            cam.set_elevation(math.radians(raw))
        elif axis == "z":
            cam.position = Vector3(cam.position.x, cam.position.y, raw)

        self.viewport.refresh()

    def _on_reset(self) -> None:
        """Reset camera to default position."""
        cam = self.viewport.viewport.camera
        cam.position = Vector3(50.0, 50.0, 100.0)
        cam.target = Vector3(0.0, 0.0, 0.0)
        self._sync_from_camera()
        self.viewport.refresh()

    def _on_center_origin(self) -> None:
        """Move camera above the origin."""
        cam = self.viewport.viewport.camera
        # Keep distance from origin the same, but point at origin
        current_pos = cam.position
        distance = current_pos.length()
        if distance < 1.0:
            distance = 100.0
        cam.position = Vector3(0.0, 0.0, distance)
        cam.target = Vector3(0.0, 0.0, 0.0)
        self._sync_from_camera()
        self.viewport.refresh()

    def _on_top_view(self) -> None:
        """Position camera looking down the Z axis (top view)."""
        cam = self.viewport.viewport.camera
        cam.position = Vector3(0.0, 0.0, 100.0)
        cam.target = Vector3(0.0, 0.0, 0.0)
        self._sync_from_camera()
        self.viewport.refresh()

    def _on_front_view(self) -> None:
        """Position camera looking from the front (along Y axis)."""
        cam = self.viewport.viewport.camera
        cam.position = Vector3(0.0, 100.0, 0.0)
        cam.target = Vector3(0.0, 0.0, 0.0)
        self._sync_from_camera()
        self.viewport.refresh()

    def _sync_from_camera(self) -> None:
        """Read the current camera state and update all sliders."""
        self._updating_sliders = True
        try:
            cam = self.viewport.viewport.camera

            az = math.degrees(cam.get_azimuth())
            el = math.degrees(cam.get_elevation())
            z = cam.position.z

            cfg_x = SLIDER_CFG["x"]
            cfg_y = SLIDER_CFG["y"]
            cfg_z = SLIDER_CFG["z"]

            self._vars["x"].set(max(cfg_x[0], min(cfg_x[1], az)))
            self._vars["y"].set(max(cfg_y[0], min(cfg_y[1], el)))
            self._vars["z"].set(max(cfg_z[0], min(cfg_z[1], z)))

            self._labels["x"].config(text=f"{az:.1f}{cfg_x[3]}")
            self._labels["y"].config(text=f"{el:.1f}{cfg_y[3]}")
            self._labels["z"].config(text=f"{z:.1f}")
        finally:
            self._updating_sliders = False

    def _on_close(self) -> None:
        """Close the dialog."""
        if self._window:
            self._window.destroy()
            self._window = None
