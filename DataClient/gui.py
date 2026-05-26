from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from DataClient.miner import deep_research_topic, mine_topic


class DataClientApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Fiona DataClient")
        self.root.geometry("760x560")
        self.topic_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="Quick")
        self.max_links_var = tk.StringVar(value="30")
        self.custom_links_var = tk.StringVar(value="50")
        self.depth_var = tk.IntVar(value=1)
        self.page_limit_var = tk.IntVar(value=50)
        self._build_ui()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Topic").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.topic_var, width=56).pack(anchor="w", pady=5)

        ttk.Label(frame, text="Mode").pack(anchor="w", pady=(10, 0))
        ttk.Combobox(frame, values=["Quick", "Deep"], state="readonly", textvariable=self.mode_var).pack(anchor="w", pady=5)

        ttk.Label(frame, text="Number of links to scrape").pack(anchor="w", pady=(10, 0))
        combo = ttk.Combobox(frame, values=["10", "30", "50", "100", "Custom"], state="readonly", textvariable=self.max_links_var)
        combo.pack(anchor="w", pady=5)

        self.custom_entry = ttk.Entry(frame, textvariable=self.custom_links_var, width=10)
        self.custom_entry.pack(anchor="w", pady=5)

        deep_frame = ttk.Frame(frame)
        deep_frame.pack(anchor="w", pady=5)
        ttk.Label(deep_frame, text="Depth").pack(side="left")
        ttk.Spinbox(deep_frame, from_=0, to=3, textvariable=self.depth_var, width=5).pack(side="left", padx=(6, 14))
        ttk.Label(deep_frame, text="Page limit").pack(side="left")
        ttk.Spinbox(deep_frame, from_=1, to=250, textvariable=self.page_limit_var, width=7).pack(side="left", padx=(6, 0))

        ttk.Button(frame, text="Run Miner", command=self._start_miner).pack(anchor="w", pady=10)

        self.log = tk.Text(frame, wrap="word", height=20)
        self.log.pack(fill="both", expand=True)

    def _start_miner(self) -> None:
        topic = self.topic_var.get().strip()
        if not topic:
            messagebox.showwarning("Input error", "Please enter a topic.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save results as",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not save_path:
            return

        try:
            max_links = self._max_links()
        except ValueError:
            messagebox.showwarning("Input error", "Enter a valid number for custom links.")
            return

        self.log.delete("1.0", tk.END)
        thread = threading.Thread(target=self._run_pipeline, args=(topic, Path(save_path), max_links), daemon=True)
        thread.start()

    def _max_links(self) -> int:
        choice = self.max_links_var.get()
        if choice == "Custom":
            return int(self.custom_links_var.get())
        return int(choice)

    def _run_pipeline(self, topic: str, save_path: Path, max_links: int) -> None:
        try:
            if self.mode_var.get() == "Deep":
                pages = deep_research_topic(
                    topic,
                    save_path,
                    seed_links=max_links,
                    page_limit=self.page_limit_var.get(),
                    max_depth=self.depth_var.get(),
                    log=self._append_log,
                )
            else:
                pages = mine_topic(topic, save_path, max_links=max_links, log=self._append_log)
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("DataClient failed", str(exc)))
            return
        self.root.after(0, lambda: messagebox.showinfo("Done", f"Saved {len(pages)} pages into:\n{save_path}"))

    def _append_log(self, message: str) -> None:
        self.root.after(0, self._append_log_now, message)

    def _append_log_now(self, message: str) -> None:
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)


def launch_dataclient() -> None:
    DataClientApp().run()
