"""Project tree panel — hierarchical view of document objects."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

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

        ttk.Label(self, text="Project Tree", font=("", 10, "bold")).pack(anchor="w", padx=4, pady=2)

        self.tree = ttk.Treeview(self, columns=("type",), selectmode="browse")
        self.tree.heading("#0", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.column("#0", width=160)
        self.tree.column("type", width=80)
        self.tree.pack(fill="both", expand=True, padx=4, pady=2)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Refresh button
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=4, pady=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).pack(side="left", padx=2)

        self.refresh()

    def set_document(self, doc: Document) -> None:
        self.doc = doc
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the tree from the document's object list."""
        self.tree.delete(*self.tree.get_children())

        for obj in self.doc.objects:
            obj_type = type(obj).__name__
            obj_name = obj.name

            if isinstance(obj, Assembly):
                parent_id = self.tree.insert("", "end", text=obj_name,
                                             values=(obj_type,), tags=("assembly",))
                for part in obj.parts:
                    self.tree.insert(parent_id, "end", text=part.name,
                                     values=("PartInstance",))
                for sub in obj.subassemblies:
                    self.tree.insert(parent_id, "end", text=sub.name,
                                     values=("Assembly",))
            elif isinstance(obj, Sketch):
                parent_id = self.tree.insert("", "end", text=obj_name,
                                             values=(obj_type,), tags=("sketch",))
                for entity in obj.entities:
                    self.tree.insert(parent_id, "end", text=entity.name,
                                     values=(type(entity).__name__,))
                for constraint in obj.constraints:
                    self.tree.insert(parent_id, "end", text=constraint.name,
                                     values=(constraint.kind.value,))
            else:
                self.tree.insert("", "end", text=obj_name,
                                 values=(obj_type,))

        self.tree.tag_configure("assembly", foreground="#35a7ff")
        self.tree.tag_configure("sketch", foreground="#2fffd3")

    def _on_tree_select(self, event: tk.Event) -> None:
        selection = self.tree.selection()
        if selection and self.on_select:
            item = self.tree.item(selection[0])
            self.on_select(item["text"])

    def _delete_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        obj_name = item["text"]
        obj = self.doc.find_by_name(obj_name)
        if obj:
            self.doc.remove_object(obj)
            self.refresh()
