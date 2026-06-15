from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from typing import Any

from FionaCore.gui_theme import apply_fiona_theme, BG_COLOR, PANEL_COLOR, ACCENT_COLOR, HIGHLIGHT_COLOR, TEXT_COLOR, DIM_TEXT
from Mantatree.pipeline import get_pipeline, MantaMessage


class MantatreeApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mantatree │ Fiona Universal Hub")
        self.root.geometry("1100x750")
        apply_fiona_theme(self.root)
        
        self.pipeline = get_pipeline()
        self.messages: list[MantaMessage] = []
        self._setup_ui()
        
        # Subscribe to all messages for debug log
        # In a real implementation, we'd add wildcard support to Mantatree
        # For now, we'll manually hook into the publish method for debug
        self._original_publish = self.pipeline.publish
        self.pipeline.publish = self._monitored_publish

    def _monitored_publish(self, topic: str, payload: Any, sender: str = "system"):
        msg = self._original_publish(topic, payload, sender)
        self.messages.append(msg)
        if len(self.messages) > 100:
            self.messages.pop(0)
        self._update_debug_log()
        return msg

    def _setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG_COLOR)
        header.pack(fill="x", padx=20, pady=20)
        ttk.Label(header, text="MANTATREE COMMUNICATION HUB", style="Header.TLabel").pack(side="left")
        
        # Main Layout: Sidebar and Main Area
        container = tk.Frame(self.root, bg=BG_COLOR)
        container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Sidebar: Universal Launcher
        sidebar = ttk.Frame(container, style="Panel.TFrame", width=280)
        sidebar.pack(side="left", fill="both", padx=(0, 15))
        sidebar.pack_propagate(False)
        
        ttk.Label(sidebar, text="UNIVERSAL LAUNCHER", style="Sub.TLabel").pack(pady=15)
        
        apps = [
            ("fAT Dashboard", "fat-gui", self._launch_fat),
            ("PhiConnect", "secure-node", self._launch_phiconnect),
            ("DataClient", "research", self._launch_dataclient),
            ("Vsee Holography", "vsee", self._launch_vsee),
            ("Config Editor", "settings", self._launch_editor),
        ]
        
        for name, icon, cmd in apps:
            btn = tk.Button(
                sidebar, text=f"🚀 {name}", bg="#2d2f39", fg=TEXT_COLOR,
                relief="flat", anchor="w", pady=10, padx=15, font=("Arial", 10),
                command=cmd
            )
            btn.pack(fill="x", pady=4, padx=15)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg="#3d3f49"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg="#2d2f39"))

        # Main Area: Pipeline Debug
        main_pane = ttk.Frame(container, style="Panel.TFrame")
        main_pane.pack(side="right", fill="both", expand=True)
        
        ttk.Label(main_pane, text="MANTA PIPELINE DEBUG", style="Sub.TLabel").pack(anchor="w", padx=15, pady=15)
        
        # Message Log
        self.debug_log = tk.Text(
            main_pane, bg="#05070a", fg=ACCENT_COLOR, font=("Monospace", 9),
            padx=15, pady=15, highlightthickness=0, borderwidth=0, wrap=tk.NONE
        )
        self.debug_log.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        # Controls
        ctrl_frame = tk.Frame(main_pane, bg=PANEL_COLOR)
        ctrl_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        tk.Label(ctrl_frame, text="PUBLISH TEST:", bg=PANEL_COLOR, fg=DIM_TEXT, font=("Arial", 8, "bold")).pack(side="left", padx=(0, 10))
        
        self.topic_var = tk.StringVar(value="test/ping")
        tk.Entry(ctrl_frame, textvariable=self.topic_var, bg="#0f172a", fg=TEXT_COLOR, relief="flat", width=15).pack(side="left", padx=5)
        
        self.payload_var = tk.StringVar(value='{"status": "active"}')
        tk.Entry(ctrl_frame, textvariable=self.payload_var, bg="#0f172a", fg=TEXT_COLOR, relief="flat").pack(side="left", fill="x", expand=True, padx=5)
        
        tk.Button(ctrl_frame, text="SEND", bg=HIGHLIGHT_COLOR, fg=BG_COLOR, relief="flat", font=("Arial", 8, "bold"), padx=15, command=self._test_publish).pack(side="right", padx=5)

    def _update_debug_log(self):
        self.debug_log.delete("1.0", tk.END)
        for msg in self.messages:
            self.debug_log.insert(tk.END, f"[{msg.timestamp[-13:-1]}] [{msg.sender.upper()}] {msg.topic} -> {json.dumps(msg.payload)}\n")
        self.debug_log.see(tk.END)

    def _test_publish(self):
        topic = self.topic_var.get().strip()
        payload_str = self.payload_var.get().strip()
        try:
            payload = json.loads(payload_str)
        except:
            payload = payload_str
        self.pipeline.publish(topic, payload, sender="hub-debug")

    def _launch_fat(self):
        threading.Thread(target=lambda: os.system("fiona fat gui"), daemon=True).start()

    def _launch_phiconnect(self):
        threading.Thread(target=lambda: os.system("fiona phiconnect"), daemon=True).start()

    def _launch_dataclient(self):
        threading.Thread(target=lambda: os.system("fiona dataclient gui"), daemon=True).start()

    def _launch_vsee(self):
        threading.Thread(target=lambda: os.system("fiona vsee"), daemon=True).start()

    def _launch_editor(self):
        threading.Thread(target=lambda: os.system("fiona edit"), daemon=True).start()

    def run(self):
        self.root.mainloop()


def run_mantatree_gui():
    app = MantatreeApp()
    app.run()
