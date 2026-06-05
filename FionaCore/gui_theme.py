from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Brand Colors
BG_COLOR = "#0f111a"
PANEL_COLOR = "#1a1c25"
ACCENT_COLOR = "#00f0ff"  # Neon Cyan
HIGHLIGHT_COLOR = "#38bdf8"
TEXT_COLOR = "#e2e8f0"
DIM_TEXT = "#94a3b8"
GREEN = "#22c55e"
YELLOW = "#eab308"
RED = "#ef4444"


def apply_fiona_theme(root: tk.Tk):
    """Skins the provided Tkinter root and its ttk widgets with the Fiona theme."""
    style = ttk.Style()
    style.theme_use("default")
    
    # Configure colors
    style.configure("TFrame", background=BG_COLOR)
    style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Arial", 10))
    style.configure("TButton", background="#2d2f39", foreground=TEXT_COLOR, relief="flat", padding=6)
    style.map("TButton", background=[("active", "#3d3f49")])
    
    style.configure("TNotebook", background=BG_COLOR, borderwidth=0)
    style.configure("TNotebook.Tab", background=PANEL_COLOR, foreground=DIM_TEXT, padding=[15, 5])
    style.map("TNotebook.Tab", 
              background=[("selected", ACCENT_COLOR)],
              foreground=[("selected", BG_COLOR)])

    style.configure("Treeview", background=PANEL_COLOR, foreground=TEXT_COLOR, fieldbackground=PANEL_COLOR, borderwidth=0)
    style.map("Treeview", background=[("selected", HIGHLIGHT_COLOR)])
    
    style.configure("TEntry", fieldbackground="#1e293b", foreground=TEXT_COLOR, borderwidth=0)
    style.configure("TCombobox", fieldbackground="#1e293b", foreground=TEXT_COLOR)

    # Panels (Custom Card Look)
    style.configure("Panel.TFrame", background=PANEL_COLOR, borderwidth=1, relief="flat")
    style.configure("Header.TLabel", foreground=ACCENT_COLOR, font=("Arial", 14, "bold"))
    style.configure("Sub.TLabel", foreground=HIGHLIGHT_COLOR, font=("Arial", 10, "bold"))
    
    root.configure(bg=BG_COLOR)
