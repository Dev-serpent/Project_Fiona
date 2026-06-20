"""Property editor panel — view and edit object properties."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from cad.core.document import Document
from cad.core.object import CADObject


class PropertyEditorPanel(ttk.Frame):
    """Panel for viewing and editing properties of selected CAD objects."""

    def __init__(self, parent: tk.Widget, doc: Document) -> None:
        super().__init__(parent)
        self.doc = doc
        self._current_object: CADObject | None = None
        self._widgets: dict[str, tk.Widget] = {}

        ttk.Label(self, text="Properties", font=("", 10, "bold")).pack(anchor="w", padx=4, pady=2)

        self._name_label = ttk.Label(self, text="No object selected")
        self._name_label.pack(anchor="w", padx=4, pady=2)

        self._props_frame = ttk.Frame(self)
        self._props_frame.pack(fill="both", expand=True, padx=4, pady=2)

        self._info_label = ttk.Label(self, text="", foreground="#888888")
        self._info_label.pack(anchor="w", padx=4, pady=2)

    def show_object(self, obj: CADObject | None) -> None:
        """Display the properties of the given object."""
        self._clear_widgets()
        self._current_object = obj

        if obj is None:
            self._name_label.config(text="No object selected")
            return

        self._name_label.config(text=f"{obj.label} ({type(obj).__name__})")

        row = 0
        for prop_name, prop in obj.properties.items():
            if not prop.visible:
                continue

            label = ttk.Label(self._props_frame, text=prop_name)
            label.grid(row=row, column=0, sticky="w", padx=2, pady=1)

            unit_suffix = f" [{prop.unit}]" if prop.unit else ""

            if prop.readonly:
                val_label = ttk.Label(
                    self._props_frame,
                    text=f"{prop.value}{unit_suffix}",
                    foreground="#888888",
                )
                val_label.grid(row=row, column=1, sticky="ew", padx=2, pady=1)
                self._widgets[prop_name] = val_label
            elif prop.type.value == "bool":
                var = tk.BooleanVar(value=bool(prop.value))
                cb = ttk.Checkbutton(
                    self._props_frame, variable=var,
                    command=lambda n=prop_name, v=var: self._on_property_change(n, v.get()),
                )
                cb.grid(row=row, column=1, sticky="w", padx=2, pady=1)
                self._widgets[prop_name] = cb
            elif prop.type.value == "float":
                var = tk.StringVar(value=f"{prop.value}")
                entry = ttk.Entry(self._props_frame, textvariable=var, width=12)
                entry.grid(row=row, column=1, sticky="ew", padx=2, pady=1)
                unit_label = ttk.Label(self._props_frame, text=prop.unit)
                unit_label.grid(row=row, column=2, sticky="w", padx=2)
                entry.bind("<FocusOut>",
                           lambda e, n=prop_name, v=var: self._on_float_change(n, v.get()))
                entry.bind("<Return>",
                           lambda e, n=prop_name, v=var: self._on_float_change(n, v.get()))
                self._widgets[prop_name] = entry
            elif prop.type.value == "int":
                var = tk.StringVar(value=f"{prop.value}")
                entry = ttk.Entry(self._props_frame, textvariable=var, width=12)
                entry.grid(row=row, column=1, sticky="ew", padx=2, pady=1)
                entry.bind("<FocusOut>",
                           lambda e, n=prop_name, v=var: self._on_int_change(n, v.get()))
                entry.bind("<Return>",
                           lambda e, n=prop_name, v=var: self._on_int_change(n, v.get()))
                self._widgets[prop_name] = entry
            elif prop.type.value == "string":
                var = tk.StringVar(value=f"{prop.value}")
                entry = ttk.Entry(self._props_frame, textvariable=var)
                entry.grid(row=row, column=1, sticky="ew", padx=2, pady=1)
                entry.bind("<FocusOut>",
                           lambda e, n=prop_name, v=var: self._on_property_change(n, v.get()))
                self._widgets[prop_name] = entry
            else:
                val_label = ttk.Label(
                    self._props_frame,
                    text=f"{prop.value}{unit_suffix}",
                )
                val_label.grid(row=row, column=1, sticky="w", padx=2, pady=1)
                self._widgets[prop_name] = val_label

            row += 1

        self._info_label.config(text=f"{len(obj.properties)} properties")

    def clear(self) -> None:
        self.show_object(None)

    def _on_property_change(self, name: str, value: Any) -> None:
        if self._current_object:
            self._current_object.set_property(name, value)
            self.doc.recompute()

    def _on_float_change(self, name: str, text: str) -> None:
        try:
            value = float(text)
            self._on_property_change(name, value)
        except ValueError:
            pass

    def _on_int_change(self, name: str, text: str) -> None:
        try:
            value = int(text)
            self._on_property_change(name, value)
        except ValueError:
            pass

    def _clear_widgets(self) -> None:
        for widget in self._widgets.values():
            widget.destroy()
        self._widgets.clear()
        for child in self._props_frame.winfo_children():
            child.destroy()
