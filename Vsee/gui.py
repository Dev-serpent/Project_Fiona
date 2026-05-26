from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from Vsee.model import DEFAULT_EDGES_TEXT, DEFAULT_POINTS_TEXT, HologramModel, VseeModelError


class VseeHolographyApp:
    def __init__(self, *, points_text: str = DEFAULT_POINTS_TEXT, edges_text: str = DEFAULT_EDGES_TEXT) -> None:
        self.root = tk.Tk()
        self.root.title("Vsee Holography")
        self.root.geometry("980x620")
        self.status_var = tk.StringVar(value="Vsee Holography")
        self._build_ui()
        self._set_text(self.points_text, points_text)
        self._set_text(self.edges_text, edges_text)
        self.render()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        body = ttk.Frame(self.root, padding=12)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        controls = ttk.Frame(body)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        controls.columnconfigure(0, weight=1)
        controls.rowconfigure(1, weight=1)
        controls.rowconfigure(3, weight=1)

        ttk.Label(controls, text="Points").grid(row=0, column=0, sticky="w")
        self.points_text = tk.Text(controls, wrap="none", height=10)
        self.points_text.grid(row=1, column=0, sticky="nsew", pady=(4, 10))

        ttk.Label(controls, text="Edges").grid(row=2, column=0, sticky="w")
        self.edges_text = tk.Text(controls, wrap="none", height=10)
        self.edges_text.grid(row=3, column=0, sticky="nsew", pady=(4, 10))

        sliders = ttk.Frame(controls)
        sliders.grid(row=4, column=0, sticky="ew")
        sliders.columnconfigure(1, weight=1)
        self.rotation_x_var = tk.DoubleVar(value=20.0)
        self.rotation_y_var = tk.DoubleVar(value=-30.0)
        self.scale_var = tk.DoubleVar(value=130.0)
        self._add_slider(sliders, 0, "Rotate X", self.rotation_x_var, -180.0, 180.0)
        self._add_slider(sliders, 1, "Rotate Y", self.rotation_y_var, -180.0, 180.0)
        self._add_slider(sliders, 2, "Scale", self.scale_var, 40.0, 260.0)

        actions = ttk.Frame(controls)
        actions.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        for column in range(4):
            actions.columnconfigure(column, weight=1)
        ttk.Button(actions, text="Render", command=self.render).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(actions, text="Cube", command=self.load_cube).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(actions, text="Load", command=self.load_files).grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Button(actions, text="Save", command=self.save_files).grid(row=0, column=3, sticky="ew", padx=(4, 0))

        viewer = ttk.Frame(body)
        viewer.grid(row=0, column=1, sticky="nsew")
        viewer.columnconfigure(0, weight=1)
        viewer.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(viewer, background="#05070a", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self.render())

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.grid(row=1, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

    def _add_slider(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.DoubleVar,
        from_value: float,
        to_value: float,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Scale(
            parent,
            from_=from_value,
            to=to_value,
            variable=variable,
            command=lambda _value: self.render(),
        ).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=4)

    def load_cube(self) -> None:
        self._set_text(self.points_text, DEFAULT_POINTS_TEXT)
        self._set_text(self.edges_text, DEFAULT_EDGES_TEXT)
        self.render()

    def load_files(self) -> None:
        points_path = filedialog.askopenfilename(title="Choose points CSV", filetypes=(("CSV files", "*.csv"), ("All files", "*")))
        if not points_path:
            return
        edges_path = filedialog.askopenfilename(title="Choose edges CSV", filetypes=(("CSV files", "*.csv"), ("All files", "*")))
        if not edges_path:
            return
        self._set_text(self.points_text, Path(points_path).read_text(encoding="utf-8"))
        self._set_text(self.edges_text, Path(edges_path).read_text(encoding="utf-8"))
        self.render()

    def save_files(self) -> None:
        points_path = filedialog.asksaveasfilename(title="Save points CSV", defaultextension=".csv")
        if not points_path:
            return
        edges_path = filedialog.asksaveasfilename(title="Save edges CSV", defaultextension=".csv")
        if not edges_path:
            return
        Path(points_path).write_text(self._get_text(self.points_text).rstrip("\n") + "\n", encoding="utf-8")
        Path(edges_path).write_text(self._get_text(self.edges_text).rstrip("\n") + "\n", encoding="utf-8")
        self.status_var.set("Saved Vsee scene tables")

    def render(self) -> None:
        try:
            model = HologramModel.from_text(self._get_text(self.points_text), self._get_text(self.edges_text))
            width = max(self.canvas.winfo_width(), 320)
            height = max(self.canvas.winfo_height(), 260)
            projected = model.projected(
                width=width,
                height=height,
                rotation_x_degrees=self.rotation_x_var.get(),
                rotation_y_degrees=self.rotation_y_var.get(),
                scale=self.scale_var.get(),
            )
        except VseeModelError as exc:
            self.status_var.set(f"Vsee model error: {exc}")
            return
        except tk.TclError:
            return

        self.canvas.delete("all")
        self._draw_grid(width, height)
        points = projected["points"]
        for source, target in projected["edges"]:
            x1, y1, z1 = points[source]
            x2, y2, z2 = points[target]
            color = "#2fffd3" if (z1 + z2) / 2 >= 0 else "#35a7ff"
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
        for point_id, (x_pos, y_pos, _z_pos) in points.items():
            self.canvas.create_oval(x_pos - 4, y_pos - 4, x_pos + 4, y_pos + 4, fill="#ffffff", outline="#9fffe8")
            self.canvas.create_text(x_pos + 10, y_pos - 10, text=point_id, fill="#d8fff8", anchor="w")
        self.status_var.set(f"Rendered {len(points)} points and {len(projected['edges'])} edges")

    def _draw_grid(self, width: int, height: int) -> None:
        spacing = 40
        for x_pos in range(0, width + spacing, spacing):
            self.canvas.create_line(x_pos, 0, x_pos, height, fill="#1b2730")
        for y_pos in range(0, height + spacing, spacing):
            self.canvas.create_line(0, y_pos, width, y_pos, fill="#1b2730")

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)

    def _get_text(self, widget: tk.Text) -> str:
        return widget.get("1.0", tk.END)


def launch_holography(points_path: Path | None = None, edges_path: Path | None = None) -> None:
    points_text = points_path.read_text(encoding="utf-8") if points_path else DEFAULT_POINTS_TEXT
    edges_text = edges_path.read_text(encoding="utf-8") if edges_path else DEFAULT_EDGES_TEXT
    VseeHolographyApp(points_text=points_text, edges_text=edges_text).run()
