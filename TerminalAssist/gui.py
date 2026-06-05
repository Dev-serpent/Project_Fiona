from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from typing import Any

from FionaCore import ActionRouter, quick_transcribe, parse_voice_command, speak
from FionaCore.gui_theme import BG_COLOR, PANEL_COLOR, ACCENT_COLOR, HIGHLIGHT_COLOR, TEXT_COLOR, DIM_TEXT, GREEN, YELLOW, RED, apply_fiona_theme
from .dashboard import terminal_assist_status, get_mouse_info
from .tui import get_quick_actions


class FancyGauge(tk.Canvas):
    def __init__(self, master, label: str, **kwargs):
        super().__init__(master, bg=PANEL_COLOR, highlightthickness=0, width=120, height=120, **kwargs)
        self.label = label
        self.value = 0.0
        self._draw()

    def update_value(self, value: float):
        self.value = value
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = 120, 120
        cx, cy = w // 2, h // 2
        r = 45
        
        # Background arc
        self.create_arc(cx-r, cy-r, cx+r, cy+r, start=-30, extent=240, style="arc", outline="#334155", width=8)
        
        # Value arc
        color = GREEN
        if self.value > 85: color = RED
        elif self.value > 60: color = YELLOW
            
        extent = (self.value / 100.0) * 240
        self.create_arc(cx-r, cy-r, cx+r, cy+r, start=210, extent=-extent, style="arc", outline=color, width=8)
        
        # Text
        self.create_text(cx, cy, text=f"{self.value:.1f}%", fill=TEXT_COLOR, font=("Arial", 12, "bold"))
        self.create_text(cx, cy+20, text=self.label, fill=DIM_TEXT, font=("Arial", 8))


class MiniGraph(tk.Canvas):
    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, bg=PANEL_COLOR, highlightthickness=0, height=80, **kwargs)
        self.title = title
        self.data = []

    def update_data(self, history: list[float]):
        self.data = list(history)
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or not self.data: return

        self.create_text(5, 10, text=self.title, fill=ACCENT_COLOR, anchor="nw", font=("Arial", 9, "bold"))
        
        points = []
        max_val = max(self.data) if max(self.data) > 0 else 1.0
        
        step = w / 50
        for i, val in enumerate(self.data):
            x = i * step
            y = h - (val / max_val * (h - 20)) - 5
            points.extend([x, y])
            
        if len(points) >= 4:
            self.create_line(points, fill=ACCENT_COLOR, width=2, smooth=True)


class FatGuiApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("fAT │ Fiona Terminal Assistant")
        self.root.geometry("960x680")
        apply_fiona_theme(self.root)
        
        self.status = terminal_assist_status()
        self._setup_ui()

    def _setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG_COLOR)
        header.pack(fill="x", padx=20, pady=20)
        
        ttk.Label(header, text="FIONA COMMAND CENTER", style="Header.TLabel").pack(side="left")
        self.lbl_time = ttk.Label(header, text="", style="TLabel")
        self.lbl_time.configure(foreground=DIM_TEXT, font=("Monospace", 11))
        self.lbl_time.pack(side="right")

        # Main Layout
        main_body = tk.Frame(self.root, bg=BG_COLOR)
        main_body.pack(fill="both", expand=True, padx=20, pady=5)
        
        left_pane = tk.Frame(main_body, bg=BG_COLOR)
        left_pane.pack(side="left", fill="both", expand=True)
        
        right_pane = tk.Frame(main_body, bg=BG_COLOR, width=280)
        right_pane.pack(side="right", fill="both", padx=(20, 0))

        # --- LEFT PANE CONTENT ---
        
        # Resource row
        res_frame = ttk.Frame(left_pane, style="Panel.TFrame")
        res_frame.pack(fill="x", pady=5)
        
        self.gauge_cpu = FancyGauge(res_frame, "CPU LOAD")
        self.gauge_cpu.pack(side="left", expand=True, padx=10, pady=15)
        
        self.gauge_mem = FancyGauge(res_frame, "MEMORY")
        self.gauge_mem.pack(side="left", expand=True, padx=10, pady=15)
        
        self.gauge_dsk = FancyGauge(res_frame, "DISK USAGE")
        self.gauge_dsk.pack(side="left", expand=True, padx=10, pady=15)

        # Network Graphs
        net_frame = ttk.Frame(left_pane, style="Panel.TFrame")
        net_frame.pack(fill="x", pady=15)
        
        self.graph_rx = MiniGraph(net_frame, "NETWORK RX (DOWNLOAD)")
        self.graph_rx.pack(fill="x", padx=15, pady=10)
        
        self.graph_tx = MiniGraph(net_frame, "NETWORK TX (UPLOAD)")
        self.graph_tx.pack(fill="x", padx=15, pady=10)

        # System Info Card
        info_frame = ttk.Frame(left_pane, style="Panel.TFrame")
        info_frame.pack(fill="both", expand=True)
        
        ttk.Label(info_frame, text="SYSTEM INTELLIGENCE", style="Sub.TLabel").pack(anchor="w", padx=15, pady=(15, 5))
        
        grid_frame = tk.Frame(info_frame, bg=PANEL_COLOR)
        grid_frame.pack(fill="x", padx=15, pady=5)
        
        self.lbl_os = self._info_row(grid_frame, 1, "Operating System:", self.status["os"])
        self.lbl_kernel = self._info_row(grid_frame, 2, "Kernel Version:", self.status["kernel"])
        self.lbl_uptime = self._info_row(grid_frame, 3, "System Uptime:", self.status["uptime"])
        self.lbl_gpu = self._info_row(grid_frame, 4, "Graphics Unit:", str(self.status["gpu"]))

        # --- RIGHT PANE CONTENT ---
        
        # Spatial Radar
        radar_frame = ttk.Frame(right_pane, style="Panel.TFrame")
        radar_frame.pack(fill="x")
        ttk.Label(radar_frame, text="SPATIAL RADAR", style="Sub.TLabel").pack(pady=(15, 0))
        
        self.radar_canvas = tk.Canvas(radar_frame, bg="#000", width=240, height=140, highlightthickness=1, highlightbackground=HIGHLIGHT_COLOR)
        self.radar_canvas.pack(pady=15, padx=15)
        self.lbl_coords = tk.Label(radar_frame, text="0, 0", background=PANEL_COLOR, foreground=DIM_TEXT, font=("Monospace", 10))
        self.lbl_coords.pack(pady=(0, 15))

        # Voice Trigger
        voice_frame = ttk.Frame(right_pane, style="Panel.TFrame")
        voice_frame.pack(fill="x", pady=15)
        
        self.btn_mic = tk.Button(
            voice_frame, text="🎙 LISTEN", bg="#3b82f6", fg="white", 
            font=("Arial", 11, "bold"), relief="flat", padx=25, pady=10,
            command=self._trigger_voice
        )
        self.btn_mic.pack(pady=(20, 5))
        self.lbl_voice_status = tk.Label(voice_frame, text="READY", background=PANEL_COLOR, foreground=DIM_TEXT, font=("Arial", 9))
        self.lbl_voice_status.pack(pady=(0, 20))

        # Quick Actions
        act_frame = ttk.Frame(right_pane, style="Panel.TFrame")
        act_frame.pack(fill="both", expand=True)
        ttk.Label(act_frame, text="QUICK ACTIONS", style="Sub.TLabel").pack(pady=(15, 10))
        
        for action in get_quick_actions():
            btn = tk.Button(
                act_frame, text=f"⚡ {action.label}", bg="#2d2f39", fg=TEXT_COLOR,
                relief="flat", anchor="w", pady=8, padx=15, font=("Arial", 10),
                command=lambda a=action: self._run_action(a)
            )
            btn.pack(fill="x", pady=2, padx=15)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg="#3d3f49"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg="#2d2f39"))

    def _info_row(self, master, row, label, value):
        tk.Label(master, text=label, bg=PANEL_COLOR, fg=DIM_TEXT, font=("Arial", 10)).grid(row=row, column=0, sticky="w", pady=4)
        v = tk.Label(master, text=value, bg=PANEL_COLOR, fg=TEXT_COLOR, font=("Arial", 10, "bold"))
        v.grid(row=row, column=1, sticky="w", padx=15)
        return v

    def _trigger_voice(self):
        self.btn_mic.configure(text="🔴 RECORDING", bg=RED)
        self.lbl_voice_status.configure(text="LISTENING FOR 3s...")
        self.root.update()
        
        def _voice_thread():
            try:
                phrase = quick_transcribe(phrase_seconds=3.0)
                if phrase:
                    self.root.after(0, lambda: self.lbl_voice_status.configure(text=f"\"{phrase.upper()}\""))
                    parsed = parse_voice_command(phrase)
                    if parsed:
                        self.root.after(0, lambda: self.lbl_voice_status.configure(text=f"ACTION: {parsed.action}"))
                        ActionRouter().run(parsed.action, source="voice", permission_profile="local")
                        speak(f"Triggered {parsed.action}")
                    else:
                        self.root.after(0, lambda: self.lbl_voice_status.configure(text="UNKNOWN COMMAND"))
                else:
                    self.root.after(0, lambda: self.lbl_voice_status.configure(text="SILENCE DETECTED"))
            except Exception as e:
                self.root.after(0, lambda: self.lbl_voice_status.configure(text=f"ERROR: {e}"))
            finally:
                self.root.after(0, lambda: self.btn_mic.configure(text="🎙 LISTEN", bg="#3b82f6"))

        threading.Thread(target=_voice_thread, daemon=True).start()

    def _run_action(self, action):
        confirm = messagebox.askyesno("System Confirmation", f"Trigger {action.label}?")
        if confirm:
            os.system(f"fiona run-shell {' '.join(action.command[1:])}")

    def _refresh_metrics(self):
        self.status = terminal_assist_status()
        self.gauge_cpu.update_value(self.status["cpu_usage_raw"])
        self.gauge_mem.update_value(self.status["mem_raw"])
        self.gauge_dsk.update_value(self.status["disk_raw"])
        
        self.graph_rx.update_data(self.status["net_history_rx"])
        self.graph_tx.update_data(self.status["net_history_tx"])
        
        self.lbl_os.configure(text=self.status["os"])
        self.lbl_kernel.configure(text=self.status["kernel"])
        self.lbl_uptime.configure(text=self.status["uptime"])
        self.lbl_gpu.configure(text=str(self.status["gpu"]))
        self.lbl_time.configure(text=time.strftime("%H:%M:%S"))
        
        self.root.after(1000, self._refresh_metrics)

    def _refresh_mouse(self):
        mouse = get_mouse_info()
        mx, my = mouse["x"], mouse["y"]
        sw = self.status.get("mouse_sw", 1920)
        sh = self.status.get("mouse_sh", 1080)
        
        rx = (mx / sw) * 240
        ry = (my / sh) * 140
        self.radar_canvas.delete("ptr")
        self.radar_canvas.create_oval(rx-5, ry-5, rx+5, ry+5, fill=ACCENT_COLOR, outline="white", width=2, tags="ptr")
        self.lbl_coords.configure(text=f"COORD: {mx}, {my}")

        self.root.after(200, self._refresh_mouse)

    def run(self):
        self._refresh_metrics()
        self._refresh_mouse()
        self.root.mainloop()


def run_gui():
    app = FatGuiApp()
    app.run()
