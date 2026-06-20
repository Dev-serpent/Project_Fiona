"""Main CAD application window — Tkinter GUI frontend."""

from __future__ import annotations

import copy
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any

from cad.commands.command_stack import UndoRedoStack
from cad.core.document import Document, new_document
from cad.commands.registry import CommandRegistry
from cad.commands.builtins import register_builtin_commands
from cad.core.recent_files import RecentFilesManager
from cad.gui.viewport import CadViewportWidget
from cad.gui.project_tree import ProjectTreePanel
from cad.gui.property_editor import PropertyEditorPanel
from cad.gui.console import ConsolePanel
from cad.gui.camera_controls import CameraControlsDialog


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

        # Phase 6 attributes
        self._file_path: str | None = None
        self._undo_stack = UndoRedoStack(max_size=50)
        self._recent_files = RecentFilesManager()
        self._dirty: bool = False
        self._undo_before: dict[str, Any] | None = None
        self._camera_controls: CameraControlsDialog | None = None

        # Build UI
        self._build_menu()
        self._build_toolbar()
        self._build_layout()
        self._build_status_bar()
        self._build_keyboard_shortcuts()

        # Save-on-close confirmation (M4.5)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._update_title()

    # ── Lifecycle ────────────────────────────────────────────────────

    def run(self) -> None:
        self.root.mainloop()

    # ── Menu (M1.9, M4.4) ────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # ── File menu ───────────────────────────────────────────────
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self._file_new, accelerator="Ctrl+N")
        file_menu.add_command(label="Open", command=self._file_open, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self._file_save, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self._file_save_as)
        file_menu.add_separator()

        # Recent Files (M4.4)
        self._recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Recent Files", menu=self._recent_menu)
        self._update_recent_files_menu()

        file_menu.add_separator()
        file_menu.add_command(label="Export STL...", command=self._export_stl)
        file_menu.add_command(label="Export OBJ...", command=self._export_obj)
        file_menu.add_command(label="Export SVG...", command=self._export_svg)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # ── Edit menu ───────────────────────────────────────────────
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self._undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self._redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Recompute", command=self._recompute, accelerator="F5")

        # ── View menu ───────────────────────────────────────────────
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Camera Controls...", command=self._show_camera_controls)
        view_menu.add_separator()
        view_menu.add_command(label="Reset View", command=self._reset_view, accelerator="Ctrl+R")
        view_menu.add_command(label="Toggle Grid", command=self._toggle_grid, accelerator="Ctrl+G")

        # ── Tools menu ──────────────────────────────────────────────
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Run Script...", command=self._run_script)

        # ── Help menu ───────────────────────────────────────────────
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    # ── Toolbar (M1.1) ───────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root, relief=tk.RAISED, padding=(2, 2))
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=2, pady=(2, 0))

        # Create section
        ttk.Label(toolbar, text="Create:", font=("", 9, "bold")).pack(side="left", padx=2)
        for ptype in ["Box", "Cylinder", "Sphere"]:
            btn = ttk.Button(
                toolbar,
                text=ptype,
                command=lambda t=ptype: self._create_primitive(t),
            )
            btn.pack(side="left", padx=1)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=4)

        # Actions section
        ttk.Label(toolbar, text="Actions:", font=("", 9, "bold")).pack(side="left", padx=2)
        actions = [
            ("\u21bb Recompute", self._recompute),
            ("\u2302 Reset View", self._reset_view),
            ("\u229e Grid", self._toggle_grid),
        ]
        for text, cmd in actions:
            ttk.Button(toolbar, text=text, command=cmd).pack(side="left", padx=1)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=4)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=4)

        # Camera section
        ttk.Label(toolbar, text="Camera:", font=("", 9, "bold")).pack(side="left", padx=2)
        ttk.Button(toolbar, text="\u25c6 Position", command=self._show_camera_controls).pack(side="left", padx=1)

        # File section
        ttk.Button(toolbar, text="\u2399 Save", command=self._file_save).pack(side="left", padx=1)

    # ── Status Bar (M1.2) ────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        self._status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(4, 2))
        self._status_bar.grid(row=3, column=0, columnspan=3, sticky="ew", padx=2, pady=(0, 2))

        self._object_count_label = ttk.Label(self._status_bar, text="Objects: 0")
        self._object_count_label.pack(side="left", padx=4)

        self._coord_label = ttk.Label(self._status_bar, text="")
        self._coord_label.pack(side="left", padx=4)

        self._mode_label = ttk.Label(self._status_bar, text="Mode: Orbit")
        self._mode_label.pack(side="right", padx=4)

        self._status_msg = ttk.Label(self._status_bar, text="Ready")
        self._status_msg.pack(side="right", padx=4)

    def _update_status_bar(self) -> None:
        """Refresh the object count and other static status info."""
        self._object_count_label.config(text=f"Objects: {self.doc.object_count}")

    def set_status(self, message: str) -> None:
        """Set a status message in the status bar."""
        self._status_msg.config(text=message)

    def _on_viewport_mouse_move(self, x: float, y: float) -> None:
        """Update coordinate display in the status bar on mouse move."""
        self._coord_label.config(text=f"X: {x:.1f}  Y: {y:.1f}")

    # ── Keyboard Shortcuts (M1.4, M1.6) ──────────────────────────────

    def _build_keyboard_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda e: self._file_new())
        self.root.bind("<Control-N>", lambda e: self._file_new())
        self.root.bind("<Control-o>", lambda e: self._file_open())
        self.root.bind("<Control-O>", lambda e: self._file_open())
        self.root.bind("<Control-s>", lambda e: self._file_save())
        self.root.bind("<Control-S>", lambda e: self._file_save())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-Z>", lambda e: self._undo())
        self.root.bind("<Control-y>", lambda e: self._redo())
        self.root.bind("<Control-Y>", lambda e: self._redo())
        self.root.bind("<Control-g>", lambda e: self._toggle_grid())
        self.root.bind("<Control-G>", lambda e: self._toggle_grid())
        self.root.bind("<Control-r>", lambda e: self._reset_view())
        self.root.bind("<Control-R>", lambda e: self._reset_view())
        self.root.bind("<F5>", lambda e: self._recompute())
        self.root.bind("<Delete>", lambda e: self._delete_selected())
        self.root.bind("<Control-a>", lambda e: self._select_all())
        self.root.bind("<Control-A>", lambda e: self._select_all())

    # ── Layout (M1.8) ────────────────────────────────────────────────

    def _build_layout(self) -> None:
        # Row and column configuration
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=0)
        self.root.rowconfigure(0, weight=0)    # Toolbar
        self.root.rowconfigure(1, weight=1)    # Main content
        self.root.rowconfigure(2, weight=0)    # Console
        self.root.rowconfigure(3, weight=0)    # Status bar

        # Col 0: Project Tree (width=250)
        left_frame = ttk.Frame(self.root, width=250)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(4, 2), pady=4)
        left_frame.grid_propagate(False)
        self.tree_panel = ProjectTreePanel(
            left_frame, self.doc, on_select=self._select_object,
        )

        # Col 1: 3D Viewport (weight=1)
        center_frame = ttk.Frame(self.root)
        center_frame.grid(row=1, column=1, sticky="nsew", padx=2, pady=4)
        center_frame.columnconfigure(0, weight=1)
        center_frame.rowconfigure(0, weight=1)
        self.viewport = CadViewportWidget(center_frame, self.doc)
        self.viewport.grid(row=0, column=0, sticky="nsew")

        # Wire viewport selection callback
        self.viewport._selection_callback = self._select_object

        # Wire viewport context menu callbacks
        self.viewport._context_callbacks = {
            "select_all": self._select_all,
            "delete_selected": self._delete_selected,
            "duplicate": self._duplicate_selected,
            "reset_view": self._reset_view,
            "toggle_grid": self._toggle_grid,
            "create_box": lambda: self._create_primitive("Box"),
            "create_cylinder": lambda: self._create_primitive("Cylinder"),
            "create_sphere": lambda: self._create_primitive("Sphere"),
        }

        # Bind mouse motion on viewport canvas for coordinate display
        self.viewport.canvas.bind(
            "<Motion>",
            lambda e: self._on_viewport_mouse_move(e.x, e.y),
        )

        # Col 2: Property Editor (width=280)
        right_frame = ttk.Frame(self.root, width=280)
        right_frame.grid(row=1, column=2, sticky="nsew", padx=(2, 4), pady=4)
        right_frame.grid_propagate(False)
        self.prop_panel = PropertyEditorPanel(right_frame, self.doc)

        # Row 2: Console (height=150)
        bottom_frame = ttk.Frame(self.root, height=150)
        bottom_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=4, pady=(0, 4))
        bottom_frame.grid_propagate(False)
        self.console_panel = ConsolePanel(bottom_frame, self.registry, self.doc)

        # Listen for console command execution to refresh panels
        self.root.bind(
            "<<CADCommandExecuted>>",
            lambda e: self._on_console_executed(),
        )

    # ── Selection Coordinator (M3.5) ──────────────────────────────────

    def _select_object(self, obj_name: str | None) -> None:
        """Called when an object is selected (from viewport or tree).

        Coordinates selection across viewport, property editor, and status bar.
        """
        # Update viewport highlight
        if obj_name:
            self.viewport.set_selection({obj_name})
        else:
            self.viewport.set_selection(set())

        # Update property editor
        if obj_name:
            obj = self.doc.find_by_name(obj_name)
            self.prop_panel.show_object(obj)
        else:
            self.prop_panel.clear()

        # Update status bar
        if obj_name:
            self.set_status(f"Selected: {obj_name}")
        else:
            self.set_status("Ready")

    # ── Console Event Handler ─────────────────────────────────────────

    def _on_console_executed(self) -> None:
        """Refresh all panels after a console command executes."""
        self.tree_panel.refresh()
        self.viewport.refresh()
        self._update_status_bar()

    # ── File Operations ───────────────────────────────────────────────

    def _file_new(self) -> None:
        self.doc = new_document("Untitled")
        self._file_path = None
        self._dirty = False
        self._undo_stack.clear()
        self._undo_before = None
        self._refresh_all()
        self.set_status("New document created")

    def _file_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Open CAD File",
            filetypes=[("CAD files", "*.cad"), ("All files", "*")],
        )
        if not path:
            return

        from cad.io.native_format import CadSerializer
        try:
            self.doc = CadSerializer.deserialize_from_file(path)
            self._file_path = path
            self._dirty = False
            self._undo_stack.clear()
            self._undo_before = None
            self._recent_files.add_file(path)
            self._update_recent_files_menu()
            self._refresh_all()
            self.set_status(f"Opened: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open {path}: {e}")

    def _file_save(self) -> None:
        if self._file_path is None:
            self._file_save_as()
            return

        from cad.io.native_format import CadSerializer
        try:
            CadSerializer.serialize_to_file(self.doc, self._file_path)
            self._dirty = False
            self.doc.is_modified = False
            self._recent_files.add_file(self._file_path)
            self._update_recent_files_menu()
            self._update_title()
            self.set_status(f"Saved: {self._file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _file_save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save CAD File",
            defaultextension=".cad",
            filetypes=[("CAD files", "*.cad"), ("All files", "*")],
        )
        if not path:
            return

        from cad.io.native_format import CadSerializer
        try:
            CadSerializer.serialize_to_file(self.doc, path)
            self._file_path = path
            self._dirty = False
            self.doc.is_modified = False
            self._recent_files.add_file(path)
            self._update_recent_files_menu()
            self._update_title()
            self.set_status(f"Saved as: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    # ── Recent Files (M4.4) ───────────────────────────────────────────

    def _update_recent_files_menu(self) -> None:
        """Rebuild the Recent Files submenu from RecentFilesManager."""
        self._recent_menu.delete(0, "end")
        files = self._recent_files.get_files()
        if not files:
            self._recent_menu.add_command(label="No recent files", state="disabled")
        else:
            for i, path in enumerate(files):
                label = f"{i + 1}. {os.path.basename(path)}"
                self._recent_menu.add_command(
                    label=label,
                    command=lambda p=path: self._open_recent_file(p),
                )

    def _open_recent_file(self, path: str) -> None:
        """Open a file from the recent files list."""
        from cad.io.native_format import CadSerializer
        try:
            self.doc = CadSerializer.deserialize_from_file(path)
            self._file_path = path
            self._dirty = False
            self._undo_stack.clear()
            self._undo_before = None
            self._recent_files.add_file(path)
            self._update_recent_files_menu()
            self._refresh_all()
            self.set_status(f"Opened: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open {path}: {e}")
            self._recent_files.remove_file(path)
            self._update_recent_files_menu()

    # ── Save-on-Close (M4.5) ──────────────────────────────────────────

    def _on_close(self) -> None:
        """Handle window close with unsaved changes confirmation."""
        if self._dirty or self.doc.is_modified:
            result = messagebox.askyesnocancel(
                "Unsaved Changes",
                f"Save changes to '{self.doc.name}' before closing?",
                detail="Your changes will be lost if you don't save them.",
                icon="warning",
            )
            if result is None:  # Cancel
                return
            elif result:  # Yes
                self._file_save()

        # Close camera controls dialog if open
        if self._camera_controls is not None:
            self._camera_controls._on_close()

        self.root.destroy()

    # ── Undo / Redo (M4.1, M4.2) ──────────────────────────────────────

    def _push_undo(self) -> None:
        """Call BEFORE a mutation to capture the 'before' state."""
        self._undo_before = self.doc.to_dict()

    def _pop_undo(self) -> None:
        """Call AFTER a mutation to capture the 'after' state and push."""
        if self._undo_before is not None:
            after = self.doc.to_dict()
            self._undo_stack.push(self._undo_before, after)
            self._undo_before = None
            self._dirty = True
            self.doc.is_modified = True

    def _undo(self) -> None:
        if not self._undo_stack.can_undo:
            self.set_status("Nothing to undo")
            return
        snapshot = self._undo_stack.undo()
        self.doc = Document.from_dict(snapshot)
        self._dirty = True
        self.doc.is_modified = True
        self._refresh_all()
        self.set_status("Undo")

    def _redo(self) -> None:
        if not self._undo_stack.can_redo:
            self.set_status("Nothing to redo")
            return
        snapshot = self._undo_stack.redo()
        self.doc = Document.from_dict(snapshot)
        self._dirty = True
        self.doc.is_modified = True
        self._refresh_all()
        self.set_status("Redo")

    # ── Create Primitive (M1.1 support method) ────────────────────────

    def _create_primitive(self, primitive_type: str) -> None:
        self._push_undo()
        cmd_name = f"create_{primitive_type.lower()}"
        try:
            result = self.registry.execute(cmd_name, self.doc)
            self.doc.recompute()
            self._pop_undo()
            self._refresh_all()
            obj_name = getattr(result, "name", primitive_type)
            self.set_status(f"Created {primitive_type}: {obj_name}")
        except Exception as e:
            self._undo_before = None  # Clear undo on failure
            messagebox.showerror("Error", f"Failed to create {primitive_type}: {e}")

    # ── Delete Selected ───────────────────────────────────────────────

    def _delete_selected(self) -> None:
        # Try to get selection from viewport first
        selected = getattr(self.viewport, "_selected_objects", set())
        if not selected:
            self.set_status("Nothing selected to delete")
            return

        obj_name = next(iter(selected))
        obj = self.doc.find_by_name(obj_name)
        if obj is None:
            return

        self._push_undo()
        self.doc.remove_object(obj)
        self._pop_undo()
        self._select_object(None)
        self._refresh_all()
        self.set_status(f"Deleted: {obj_name}")

    # ── Duplicate Selected ────────────────────────────────────────────

    def _duplicate_selected(self) -> None:
        selected = getattr(self.viewport, "_selected_objects", set())
        if not selected:
            self.set_status("Nothing selected to duplicate")
            return

        obj_name = next(iter(selected))
        obj = self.doc.find_by_name(obj_name)
        if obj is None:
            return

        self._push_undo()
        new_obj = copy.deepcopy(obj)
        import uuid
        new_obj.uid = uuid.uuid4()

        # Generate a unique name with _copy suffix
        base_name = obj_name
        copy_name = f"{base_name}_copy"
        counter = 1
        while self.doc.find_by_name(copy_name) is not None:
            copy_name = f"{base_name}_copy_{counter}"
            counter += 1
        new_obj.name = copy_name

        # Offset position slightly
        for prop_name in ["x", "y", "z"]:
            prop = new_obj.get_property(prop_name)
            if prop and hasattr(prop.value, "__add__"):
                try:
                    new_obj.set_property(prop_name, prop.value + 10)
                except (TypeError, ValueError):
                    pass

        self.doc.add_object(new_obj)
        self.doc.recompute()
        self._pop_undo()
        self._refresh_all()
        self._select_object(copy_name)
        self.set_status(f"Duplicated: {obj_name} \u2192 {copy_name}")

    # ── Select All ────────────────────────────────────────────────────

    def _select_all(self) -> None:
        names = [obj.name for obj in self.doc.objects]
        self.viewport.set_selection(set(names))
        if names:
            self._select_object(names[0])
        else:
            self._select_object(None)
        self.set_status(f"Selected {len(names)} objects")

    # ── Refresh All ───────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        """Refresh tree, viewport, property editor, status bar, and title."""
        self.tree_panel.set_document(self.doc)
        self.viewport.set_document(self.doc)
        self.prop_panel.clear()
        self._update_status_bar()
        self._update_title()

    # ── Window Title (M1.5) ───────────────────────────────────────────

    def _update_title(self) -> None:
        if self._file_path:
            self.root.title(f"Fiona CAD \u2014 {self.doc.name} ({self._file_path})")
        else:
            self.root.title(f"Fiona CAD \u2014 {self.doc.name}")

    # ── Export ─────────────────────────────────────────────────────────

    def _export_stl(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export STL",
            defaultextension=".stl",
            filetypes=[("STL files", "*.stl")],
        )
        if path:
            from cad.io.export_stl import export_stl
            export_stl(self.doc, path)
            self.set_status(f"Exported STL: {path}")
            messagebox.showinfo("Export", f"Exported to {path}")

    def _export_obj(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export OBJ",
            defaultextension=".obj",
            filetypes=[("OBJ files", "*.obj")],
        )
        if path:
            from cad.io.export_obj import export_obj
            export_obj(self.doc, path)
            self.set_status(f"Exported OBJ: {path}")
            messagebox.showinfo("Export", f"Exported to {path}")

    def _export_svg(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export SVG",
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg")],
        )
        if path:
            from cad.io.export_svg import export_svg
            export_svg(self.doc, path)
            self.set_status(f"Exported SVG: {path}")
            messagebox.showinfo("Export", f"Exported to {path}")

    # ── Actions ───────────────────────────────────────────────────────

    def _recompute(self) -> None:
        self.doc.recompute()
        self.viewport.refresh()
        self.set_status("Recomputed")

    def _show_camera_controls(self) -> None:
        """Open the camera position controls dialog."""
        if self._camera_controls is None:
            self._camera_controls = CameraControlsDialog(self.root, self.viewport)
        self._camera_controls.show()

    def _reset_view(self) -> None:
        self.viewport.reset_camera()
        self.set_status("View reset")

    def _toggle_grid(self) -> None:
        self.viewport.show_grid = not self.viewport.show_grid
        self.viewport.refresh()
        self.set_status(f"Grid {'on' if self.viewport.show_grid else 'off'}")

    # ── Tools ─────────────────────────────────────────────────────────

    def _run_script(self) -> None:
        path = filedialog.askopenfilename(
            title="Run Script",
            filetypes=[("Python files", "*.py"), ("All files", "*")],
        )
        if path:
            from cad.scripting.console import execute_script
            output = execute_script(path, self.registry, self.doc)
            self.console_panel.append_output(output)
            self.tree_panel.refresh()
            self.viewport.refresh()
            self._update_status_bar()

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About CAD Platform",
            "Fiona CAD v0.1.0\n"
            "Parametric 3D CAD System\n"
            "Inspired by FreeCAD",
        )
