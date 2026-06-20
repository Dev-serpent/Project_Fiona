"""Main CAD application window — Tkinter GUI frontend."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any

from cad.core.document import Document, new_document
from cad.commands.registry import CommandRegistry
from cad.commands.builtins import register_builtin_commands
from cad.gui.viewport import CadViewportWidget
from cad.gui.project_tree import ProjectTreePanel
from cad.gui.property_editor import PropertyEditorPanel
from cad.gui.console import ConsolePanel


class CadMainWindow:
    """Main CAD application window with docked panels."""

    def __init__(self, title: str = "CAD Platform") -> None:
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("1280x800")

        # Core systems
        self.doc = new_document("Untitled")
        self.registry = CommandRegistry()
        register_builtin_commands(self.registry)

        # Build UI
        self._build_menu()
        self._build_layout()
        self._update_title()

    def run(self) -> None:
        self.root.mainloop()

    # ── Menu ─────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self._file_new, accelerator="Ctrl+N")
        file_menu.add_command(label="Open", command=self._file_open, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self._file_save, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self._file_save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Export STL...", command=self._export_stl)
        file_menu.add_command(label="Export OBJ...", command=self._export_obj)
        file_menu.add_command(label="Export SVG...", command=self._export_svg)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self._undo)
        edit_menu.add_command(label="Redo", command=self._redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Recompute", command=self._recompute)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Reset View", command=self._reset_view)
        view_menu.add_command(label="Toggle Grid", command=self._toggle_grid)

        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Run Script...", command=self._run_script)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    # ── Layout ──────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=0)
        self.root.rowconfigure(0, weight=1)

        # Left: Project Tree
        left_frame = ttk.Frame(self.root, width=250)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(4, 2), pady=4)
        left_frame.grid_propagate(False)
        self.tree_panel = ProjectTreePanel(left_frame, self.doc, self._on_select_object)

        # Center: 3D Viewport
        center_frame = ttk.Frame(self.root)
        center_frame.grid(row=0, column=1, sticky="nsew", padx=2, pady=4)
        center_frame.columnconfigure(0, weight=1)
        center_frame.rowconfigure(0, weight=1)
        self.viewport = CadViewportWidget(center_frame, self.doc)
        self.viewport.grid(row=0, column=0, sticky="nsew")

        # Right: Property Editor
        right_frame = ttk.Frame(self.root, width=280)
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 4), pady=4)
        right_frame.grid_propagate(False)
        self.prop_panel = PropertyEditorPanel(right_frame, self.doc)

        # Bottom: Console
        bottom_frame = ttk.Frame(self.root, height=150)
        bottom_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=4, pady=(0, 4))
        bottom_frame.grid_propagate(False)
        self.console_panel = ConsolePanel(bottom_frame, self.registry, self.doc)

    # ── Callbacks ────────────────────────────────────────────────────

    def _on_select_object(self, obj_name: str) -> None:
        obj = self.doc.find_by_name(obj_name)
        self.prop_panel.show_object(obj)

    def _file_new(self) -> None:
        self.doc = new_document("Untitled")
        self.tree_panel.set_document(self.doc)
        self.viewport.set_document(self.doc)
        self.prop_panel.clear()
        self._update_title()

    def _file_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Open CAD File",
            filetypes=[("CAD files", "*.cad"), ("All files", "*")],
        )
        if path:
            from cad.io.native_format import CadSerializer
            self.doc = CadSerializer.deserialize_from_file(path)
            self.tree_panel.set_document(self.doc)
            self.viewport.set_document(self.doc)
            self._update_title()

    def _file_save(self) -> None:
        from cad.io.native_format import CadSerializer
        CadSerializer.serialize_to_file(self.doc, f"{self.doc.name}.cad")

    def _file_save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save CAD File",
            defaultextension=".cad",
            filetypes=[("CAD files", "*.cad"), ("All files", "*")],
        )
        if path:
            from cad.io.native_format import CadSerializer
            CadSerializer.serialize_to_file(self.doc, path)

    def _export_stl(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export STL", defaultextension=".stl",
            filetypes=[("STL files", "*.stl")])
        if path:
            from cad.io.export_stl import export_stl
            export_stl(self.doc, path)
            messagebox.showinfo("Export", f"Exported to {path}")

    def _export_obj(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export OBJ", defaultextension=".obj",
            filetypes=[("OBJ files", "*.obj")])
        if path:
            from cad.io.export_obj import export_obj
            export_obj(self.doc, path)
            messagebox.showinfo("Export", f"Exported to {path}")

    def _export_svg(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export SVG", defaultextension=".svg",
            filetypes=[("SVG files", "*.svg")])
        if path:
            from cad.io.export_svg import export_svg
            export_svg(self.doc, path)
            messagebox.showinfo("Export", f"Exported to {path}")

    def _undo(self) -> None:
        pass  # Future: undo stack

    def _redo(self) -> None:
        pass

    def _recompute(self) -> None:
        self.doc.recompute()
        self.viewport.refresh()

    def _reset_view(self) -> None:
        self.viewport.reset_camera()

    def _toggle_grid(self) -> None:
        self.viewport.show_grid = not self.viewport.show_grid
        self.viewport.refresh()

    def _run_script(self) -> None:
        path = filedialog.askopenfilename(
            title="Run Script",
            filetypes=[("Python files", "*.py"), ("All files", "*")])
        if path:
            from cad.scripting.console import execute_script
            output = execute_script(path, self.registry, self.doc)
            self.console_panel.append_output(output)
            self.tree_panel.refresh()
            self.viewport.refresh()

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About CAD Platform",
            "CAD Platform v0.1.0\n"
            "Parametric 3D CAD System\n"
            "Inspired by FreeCAD"
        )

    def _update_title(self) -> None:
        self.root.title(f"CAD Platform - {self.doc.name}")
