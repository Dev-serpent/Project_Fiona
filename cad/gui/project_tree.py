"""Project tree panel — hierarchical view of document objects."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

import uuid

from cad.core.document import Document
from cad.sketch.workspace import Sketch
from cad.assembly.assembly import Assembly


class ProjectTreePanel(ttk.Frame):
    """Tree view of all objects in the CAD document."""

    def __init__(self, parent: tk.Widget, doc: Document,
                 on_select: Callable[[str], None] | None = None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.on_select = on_select
        self._delete_no_confirm = False

        ttk.Label(self, text="Project Tree", font=("", 10, "bold")).pack(anchor="w", padx=4, pady=2)

        # ── Search / Filter field (M5.3) ──────────────────────────────
        search_frame = ttk.Frame(self)
        search_frame.pack(fill="x", padx=4, pady=(0, 2))
        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(search_frame, textvariable=self._search_var,
                                        font=("", 9))
        self._search_entry.pack(side="left", fill="x", expand=True)
        self._search_entry.bind("<KeyRelease>", self._filter_tree)
        self._search_entry.bind("<Escape>", lambda e: self._clear_search())
        ttk.Button(search_frame, text="✕", width=3,
                   command=self._clear_search).pack(side="right", padx=(2, 0))

        # Filter info label (shows "Showing X/Y" when filtering)
        self._filter_label = ttk.Label(self, font=("", 8), foreground="#888888")
        self._filter_label.pack(anchor="w", padx=4, pady=(0, 1))

        self.tree = ttk.Treeview(self, columns=("type",), selectmode="browse")
        self.tree.heading("#0", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.column("#0", width=160)
        self.tree.column("type", width=80)
        self.tree.pack(fill="both", expand=True, padx=4, pady=2)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # ── Context menu on tree (M5.2) ───────────────────────────────
        self._build_context_menu()
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<ButtonPress-2>", self._show_context_menu)

        # Refresh button
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=4, pady=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).pack(side="left", padx=2)

        self.refresh()

    # ── Document Management ──────────────────────────────────────────

    def set_document(self, doc: Document) -> None:
        self.doc = doc
        self._clear_search()

    # ── Search / Filter (M5.3) ───────────────────────────────────────

    def _filter_tree(self, *args: Any) -> None:
        """Called on each keystroke in the search entry. Rebuilds tree with filter."""
        self.refresh(self._search_var.get())

    def _clear_search(self) -> None:
        """Clear the search field and show all items."""
        self._search_var.set("")
        self.refresh()
        if self._search_entry.winfo_exists():
            self._search_entry.icursor(0)

    # ── Tree Rebuild ─────────────────────────────────────────────────

    def refresh(self, filter_text: str = "") -> None:
        """Rebuild the tree from the document's object list.

        If *filter_text* is provided (non-empty), only objects whose name
        or type contains the filter string (case-insensitive) are shown.
        """
        self.tree.delete(*self.tree.get_children())
        filter_lower = filter_text.strip().lower()

        visible_count = 0
        for obj in self.doc.objects:
            obj_type = type(obj).__name__
            obj_name = obj.name

            # Check filter match
            if filter_lower:
                name_match = filter_lower in obj_name.lower()
                type_match = filter_lower in obj_type.lower()
                if not name_match and not type_match:
                    # For containers, check if any child matches
                    if isinstance(obj, Assembly):
                        child_match = any(
                            filter_lower in p.name.lower()
                            for p in obj.parts
                        ) or any(
                            filter_lower in s.name.lower()
                            for s in obj.subassemblies
                        )
                    elif isinstance(obj, Sketch):
                        child_match = any(
                            filter_lower in e.name.lower()
                            for e in obj.entities
                        ) or any(
                            filter_lower in c.name.lower()
                            for c in obj.constraints
                        )
                    else:
                        child_match = False

                    if not child_match:
                        continue

            if isinstance(obj, Assembly):
                parent_id = self.tree.insert("", "end", text=obj_name,
                                             values=(obj_type,), tags=("assembly",))
                for part in obj.parts:
                    if filter_lower:
                        pn = part.name.lower()
                        pt = "PartInstance".lower()
                        if filter_lower not in pn and filter_lower not in pt:
                            continue
                    self.tree.insert(parent_id, "end", text=part.name,
                                     values=("PartInstance",))
                for sub in obj.subassemblies:
                    if filter_lower:
                        sn = sub.name.lower()
                        st = "Assembly".lower()
                        if filter_lower not in sn and filter_lower not in st:
                            continue
                    self.tree.insert(parent_id, "end", text=sub.name,
                                     values=("Assembly",))
                visible_count += 1
            elif isinstance(obj, Sketch):
                parent_id = self.tree.insert("", "end", text=obj_name,
                                             values=(obj_type,), tags=("sketch",))
                for entity in obj.entities:
                    if filter_lower:
                        en = entity.name.lower()
                        et = type(entity).__name__.lower()
                        if filter_lower not in en and filter_lower not in et:
                            continue
                    self.tree.insert(parent_id, "end", text=entity.name,
                                     values=(type(entity).__name__,))
                for constraint in obj.constraints:
                    if filter_lower:
                        cn = constraint.name.lower()
                        ck = constraint.kind.value.lower()
                        if filter_lower not in cn and filter_lower not in ck:
                            continue
                    self.tree.insert(parent_id, "end", text=constraint.name,
                                     values=(constraint.kind.value,))
                visible_count += 1
            else:
                self.tree.insert("", "end", text=obj_name,
                                 values=(obj_type,))
                visible_count += 1

        self.tree.tag_configure("assembly", foreground="#35a7ff")
        self.tree.tag_configure("sketch", foreground="#2fffd3")

        # Update filter status label
        total = len(self.doc.objects)
        if filter_lower:
            self._filter_label.config(text=f"Showing {visible_count}/{total}")
        else:
            self._filter_label.config(text="")

    # ── Tree Selection ───────────────────────────────────────────────

    def _on_tree_select(self, event: tk.Event) -> None:
        selection = self.tree.selection()
        if selection and self.on_select:
            item = self.tree.item(selection[0])
            self.on_select(item["text"])

    # ── Context Menu (M5.2) ──────────────────────────────────────────

    def _build_context_menu(self) -> None:
        self._context_menu = tk.Menu(self.tree, tearoff=0)
        self._context_menu.add_command(label="Rename", command=self._rename_selected)
        self._context_menu.add_command(label="Duplicate", command=self._duplicate_selected)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Delete", command=self._delete_selected)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Select All", command=self._select_all)

    def _show_context_menu(self, event: tk.Event) -> None:
        """Display the right-click context menu."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        else:
            self.tree.selection_remove(self.tree.selection())
        self._context_menu.post(event.x_root, event.y_root)

    # ── Rename Selected (M5.2) ───────────────────────────────────────

    def _rename_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        obj_name = item["text"]
        obj = self.doc.find_by_name(obj_name)
        if obj is None:
            return

        new_name = simpledialog.askstring(
            "Rename",
            f"New name for '{obj_name}':",
            initialvalue=obj_name,
        )
        if new_name and new_name.strip():
            obj.name = new_name.strip()
            self.refresh(self._search_var.get() if hasattr(self, '_search_var') else "")
            # Re-select the renamed item so the property editor updates
            new_selection = self._find_item_by_text(new_name.strip())
            if new_selection:
                self.tree.selection_set(new_selection)
                if self.on_select:
                    self.on_select(new_name.strip())

    # ── Duplicate Selected (M5.2) ────────────────────────────────────

    def _duplicate_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        obj_name = item["text"]
        obj = self.doc.find_by_name(obj_name)
        if obj is None:
            return

        new_obj = copy.deepcopy(obj)
        new_obj.name = f"{obj_name}_copy"
        new_obj.uid = uuid.uuid4()

        # Offset position slightly
        for prop_name in ["x", "y", "z"]:
            prop = new_obj.get_property(prop_name)
            if prop and hasattr(prop.value, '__add__'):
                try:
                    new_obj.set_property(prop_name, prop.value + 10)
                except (TypeError, ValueError):
                    pass

        self.doc.add_object(new_obj)
        self.doc.recompute()
        self.refresh(self._search_var.get() if hasattr(self, '_search_var') else "")
        # Select the duplicated item
        new_selection = self._find_item_by_text(new_obj.name)
        if new_selection:
            self.tree.selection_set(new_selection)
            if self.on_select:
                self.on_select(new_obj.name)

    # ── Select All (M5.2) ────────────────────────────────────────────

    def _select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children())

    # ── Delete Selected (M4.3) ───────────────────────────────────────

    def _delete_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        obj_name = item["text"]
        obj = self.doc.find_by_name(obj_name)
        if obj is None:
            return

        # Confirmation dialog (M4.3)
        if not self._delete_no_confirm:
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Delete '{obj_name}'?\n\nThis action can be undone with Ctrl+Z.",
                icon="warning"
            )
            if not confirm:
                return

        self.doc.remove_object(obj)
        self.refresh(self._search_var.get() if hasattr(self, '_search_var') else "")

    # ── Helpers ──────────────────────────────────────────────────────

    def _find_item_by_text(self, text: str) -> str | None:
        """Find a tree item ID whose display text matches *text*."""
        for item_id in self.tree.get_children():
            if self.tree.item(item_id, "text") == text:
                return item_id
            # Check children too
            for child_id in self.tree.get_children(item_id):
                if self.tree.item(child_id, "text") == text:
                    return child_id
        return None
