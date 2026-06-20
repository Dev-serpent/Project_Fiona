"""Property editor panel — view and edit object properties."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from cad.core.document import Document
from cad.core.object import CADObject
from cad.core.property import PropertyType


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

        self._build_button_bar()

    def _build_button_bar(self) -> None:
        """Build the Apply/Reset button bar at the bottom of the panel."""
        self._btn_frame = ttk.Frame(self)
        self._btn_frame.pack(fill="x", padx=4, pady=2)

        self._apply_btn = ttk.Button(
            self._btn_frame, text="Apply", command=self._on_apply
        )
        self._apply_btn.pack(side="left", padx=2)

        self._reset_btn = ttk.Button(
            self._btn_frame, text="Reset", command=self._on_reset
        )
        self._reset_btn.pack(side="left", padx=2)

        self._status_label = ttk.Label(self._btn_frame, text="")
        self._status_label.pack(side="right", padx=4)

    def _on_apply(self) -> None:
        """Handle Apply button: show visual confirmation."""
        self._status_label.config(text="Applied", foreground="#44ff44")
        self.after(1500, lambda: self._status_label.config(text=""))

    def _on_reset(self) -> None:
        """Handle Reset button: reset all properties to their default values."""
        if self._current_object is None:
            return
        for _prop_name, prop in self._current_object.properties.items():
            prop.reset()
        self.doc.recompute()
        self.show_object(self._current_object)
        self._status_label.config(text="Reset to defaults", foreground="#ffaa00")
        self.after(1500, lambda: self._status_label.config(text=""))

    def show_object(self, obj: CADObject | None) -> None:
        """Display the properties of the given object, grouped by category.

        Properties are sorted alphabetically within each category.
        Categories are sorted alphabetically.
        """
        self._clear_widgets()
        self._current_object = obj

        if obj is None:
            self._name_label.config(text="No object selected")
            return

        self._name_label.config(text=f"{obj.label} ({type(obj).__name__})")

        # Group properties by category
        categories: dict[str, list[tuple[str, Any]]] = {}
        for prop_name, prop in obj.properties.items():
            if not prop.visible:
                continue
            cat = prop.category or "General"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((prop_name, prop))

        # Sort categories alphabetically, then properties within each category
        row = 0
        for category_name in sorted(categories.keys()):
            props = categories[category_name]
            props.sort(key=lambda x: x[0])

            # Render category header (uses 2 rows: separator + label)
            self._render_category_header(category_name, row)
            row += 2

            # Render each property in this category
            for prop_name, prop in props:
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
                elif prop.type == PropertyType.COLOR:
                    self._render_color_property(prop, prop_name, row)
                elif prop.type == PropertyType.BOOL:
                    var = tk.BooleanVar(value=bool(prop.value))
                    cb = ttk.Checkbutton(
                        self._props_frame, variable=var,
                        command=lambda n=prop_name, v=var: self._on_property_change(n, v.get()),
                    )
                    cb.grid(row=row, column=1, sticky="w", padx=2, pady=1)
                    self._widgets[prop_name] = cb
                elif prop.type == PropertyType.FLOAT:
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
                elif prop.type == PropertyType.INT:
                    var = tk.StringVar(value=f"{prop.value}")
                    entry = ttk.Entry(self._props_frame, textvariable=var, width=12)
                    entry.grid(row=row, column=1, sticky="ew", padx=2, pady=1)
                    entry.bind("<FocusOut>",
                               lambda e, n=prop_name, v=var: self._on_int_change(n, v.get()))
                    entry.bind("<Return>",
                               lambda e, n=prop_name, v=var: self._on_int_change(n, v.get()))
                    self._widgets[prop_name] = entry
                elif prop.type == PropertyType.STRING:
                    var = tk.StringVar(value=f"{prop.value}")
                    entry = ttk.Entry(self._props_frame, textvariable=var)
                    entry.grid(row=row, column=1, sticky="ew", padx=2, pady=1)
                    entry.bind("<FocusOut>",
                               lambda e, n=prop_name, v=var: self._on_property_change(n, v.get()))
                    self._widgets[prop_name] = entry
                else:
                    # Fallback: render as read-only label
                    val_label = ttk.Label(
                        self._props_frame,
                        text=f"{prop.value}{unit_suffix}",
                    )
                    val_label.grid(row=row, column=1, sticky="w", padx=2, pady=1)
                    self._widgets[prop_name] = val_label

                row += 1

        visible_count = sum(1 for p in obj.properties.values() if p.visible)
        self._info_label.config(text=f"{visible_count} properties")

    def _render_category_header(self, category_name: str, row: int) -> None:
        """Render a category header: separator line followed by bold label."""
        sep = ttk.Separator(self._props_frame, orient="horizontal")
        sep.grid(row=row, column=0, columnspan=3, sticky="ew", padx=2, pady=(8, 2))
        header = ttk.Label(self._props_frame, text=category_name,
                           font=("", 9, "bold"), foreground="#35a7ff")
        header.grid(row=row + 1, column=0, columnspan=3, sticky="w", padx=2, pady=(0, 4))

    def _render_color_property(self, prop, prop_name: str, row: int) -> None:
        """Render a color property with a swatch button and hex label.

        Clicking the swatch opens a color picker dialog.
        """
        from tkinter import colorchooser

        current_color = prop.value or "#ffffff"

        # Color swatch button (Frame styled as a swatch)
        swatch_frame = tk.Frame(self._props_frame, width=24, height=24,
                                background=current_color,
                                highlightbackground="#888888",
                                highlightthickness=1)
        swatch_frame.grid(row=row, column=1, padx=2, pady=1, sticky="w")
        swatch_frame.pack_propagate(False)

        def pick_color() -> None:
            result = colorchooser.askcolor(
                initialcolor=current_color,
                title=f"Choose {prop_name}",
            )
            if result and result[1]:  # result is ((R, G, B), "#hex")
                hex_color = result[1]
                swatch_frame.config(background=hex_color)
                hex_label.config(text=hex_color)
                self._on_property_change(prop_name, hex_color)

        swatch_frame.bind("<Button-1>", lambda e: pick_color())

        hex_label = ttk.Label(self._props_frame, text=current_color,
                              foreground="#888888", font=("Consolas", 9))
        hex_label.grid(row=row, column=2, padx=2, pady=1, sticky="w")
        hex_label.bind("<Button-1>", lambda e: pick_color())

    def clear(self) -> None:
        """Clear the property editor (deselect current object)."""
        self.show_object(None)

    def _on_property_change(self, name: str, value: Any) -> None:
        """Called when a property value changes via the UI."""
        if self._current_object:
            self._current_object.set_property(name, value)
            self.doc.recompute()

    def _on_float_change(self, name: str, text: str) -> None:
        """Handle float entry change: parse and apply."""
        try:
            value = float(text)
            self._on_property_change(name, value)
        except ValueError:
            pass

    def _on_int_change(self, name: str, text: str) -> None:
        """Handle int entry change: parse and apply."""
        try:
            value = int(text)
            self._on_property_change(name, value)
        except ValueError:
            pass

    def _clear_widgets(self) -> None:
        """Destroy all dynamically created widgets in the properties frame."""
        for widget in self._widgets.values():
            widget.destroy()
        self._widgets.clear()
        for child in self._props_frame.winfo_children():
            child.destroy()
