from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from quiktieper.config import load_config, save_config
from quiktieper.launcher import Binding


class ConfigEditorApp:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.root = tk.Tk()
        self.root.title("QuikTieper")
        self.root.geometry("900x560")

        self.selected_index: int | None = None
        self.listener = None
        self.listener_running = False
        self._build_ui()
        self._load()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        bindings_tab = ttk.Frame(self.notebook, padding=12)
        json_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(bindings_tab, text="Bindings")
        self.notebook.add(json_tab, text="Raw JSON")

        self._build_bindings_tab(bindings_tab)
        self._build_json_tab(json_tab)

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1)

        self.listener_var = tk.StringVar(value="Listener: stopped")
        self.status_var = tk.StringVar(value=f"Config: {self.config_path}")

        ttk.Label(footer, textvariable=self.listener_var).grid(row=0, column=0, sticky="w", padx=(0, 18))
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=1, sticky="w")
        self.listener_button = ttk.Button(footer, text="Start Listener", command=self.toggle_listener)
        self.listener_button.grid(row=0, column=2, sticky="e", padx=(12, 6))
        ttk.Button(footer, text="Save All", command=self.save_all).grid(row=0, column=3, sticky="e")

    def _build_bindings_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.binding_list = tk.Listbox(left, exportselection=False)
        self.binding_list.grid(row=0, column=0, sticky="nsew")
        self.binding_list.bind("<<ListboxSelect>>", self.on_binding_select)

        actions = ttk.Frame(left)
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for index in range(4):
            actions.columnconfigure(index, weight=1)
        ttk.Button(actions, text="Add", command=self.add_binding).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Delete", command=self.delete_binding).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(actions, text="New From Name", command=self.generate_keys_from_name).grid(
            row=0, column=2, sticky="ew", padx=6
        )
        ttk.Button(actions, text="Save Binding", command=self.apply_form_to_selected).grid(
            row=0, column=3, sticky="ew", padx=(6, 0)
        )

        right = ttk.LabelFrame(parent, text="Binding Editor", padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        ttk.Label(right, text="Name").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Label(right, text="Keys").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Label(right, text="Run Command").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Label(right, text="Cooldown").grid(row=3, column=0, sticky="w", pady=6)

        self.name_var = tk.StringVar()
        self.keys_var = tk.StringVar()
        self.command_var = tk.StringVar()
        self.cooldown_var = tk.StringVar(value="0.8")

        ttk.Entry(right, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Entry(right, textvariable=self.keys_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Entry(right, textvariable=self.command_var).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Entry(right, textvariable=self.cooldown_var).grid(row=3, column=1, sticky="ew", pady=6)

        hint = (
            "Keys are comma-separated. Example: alt, b, r, v\n"
            "Use New From Name to build a chord like alt + b + r + v from Brave."
        )
        ttk.Label(right, text=hint, justify="left").grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _build_json_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self.json_text = tk.Text(parent, wrap="none")
        self.json_text.grid(row=0, column=0, sticky="nsew")

        buttons = ttk.Frame(parent)
        buttons.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Reload From Disk", command=self._load).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Validate JSON", command=self.validate_json).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _load(self) -> None:
        self.config = load_config(self.config_path)
        self._refresh_list()
        self._refresh_json_text()
        self._clear_form()
        self.status_var.set(f"Loaded {self.config_path}")

    def _refresh_list(self) -> None:
        self.binding_list.delete(0, tk.END)
        for binding in self.config.get("bindings", []):
            keys = " + ".join(binding.get("keys", []))
            self.binding_list.insert(tk.END, f'{binding.get("name", "unnamed")} [{keys}]')

    def _refresh_json_text(self) -> None:
        self.json_text.delete("1.0", tk.END)
        self.json_text.insert("1.0", json.dumps(self.config, indent=2))

    def _clear_form(self) -> None:
        self.selected_index = None
        self.name_var.set("")
        self.keys_var.set("")
        self.command_var.set("")
        self.cooldown_var.set("0.8")

    def on_binding_select(self, _event: object) -> None:
        selection = self.binding_list.curselection()
        if not selection:
            return

        self.selected_index = selection[0]
        binding = self.config["bindings"][self.selected_index]
        self.name_var.set(binding.get("name", ""))
        self.keys_var.set(", ".join(binding.get("keys", [])))
        self.command_var.set(binding.get("cmd", binding.get("command", "")))
        self.cooldown_var.set(str(binding.get("cooldown_seconds", 0.8)))

    def add_binding(self) -> None:
        binding = self._binding_from_form()
        if binding is None:
            return

        self.config.setdefault("bindings", []).append(binding)
        self._refresh_list()
        self._refresh_json_text()
        self.status_var.set("Added binding")

    def delete_binding(self) -> None:
        selection = self.binding_list.curselection()
        if not selection:
            messagebox.showwarning("No selection", "Select a binding to delete.")
            return

        del self.config["bindings"][selection[0]]
        self._refresh_list()
        self._refresh_json_text()
        self._clear_form()
        self.status_var.set("Deleted binding")

    def apply_form_to_selected(self) -> None:
        binding = self._binding_from_form()
        if binding is None:
            return

        if self.selected_index is None:
            self.config.setdefault("bindings", []).append(binding)
            self.selected_index = len(self.config["bindings"]) - 1
            self.status_var.set("Added binding")
        else:
            self.config["bindings"][self.selected_index] = binding
            self.status_var.set("Updated binding")

        self._refresh_list()
        self._refresh_json_text()
        self.binding_list.selection_clear(0, tk.END)
        self.binding_list.selection_set(self.selected_index)
        self.binding_list.activate(self.selected_index)

    def generate_keys_from_name(self) -> None:
        name = self.name_var.get().strip().lower()
        letters = [char for char in name if char.isalnum()]
        if not letters:
            messagebox.showwarning("Missing name", "Enter a name first.")
            return

        self.keys_var.set(", ".join(["alt", *letters[:4]]))
        self.status_var.set("Generated chord from app name")

    def validate_json(self) -> None:
        try:
            json.loads(self.json_text.get("1.0", tk.END))
        except json.JSONDecodeError as exc:
            messagebox.showerror("Invalid JSON", str(exc))
            return

        messagebox.showinfo("Valid JSON", "The raw JSON tab is valid.")

    def save_all(self) -> None:
        if self.notebook.tab(self.notebook.select(), "text") == "Bindings":
            binding = self._binding_from_form(allow_blank=True)
            if binding is not None:
                if self.selected_index is None:
                    self.config.setdefault("bindings", []).append(binding)
                    self.selected_index = len(self.config["bindings"]) - 1
                else:
                    self.config["bindings"][self.selected_index] = binding
                self._refresh_list()
                self._refresh_json_text()
            parsed = self.config
        else:
            try:
                parsed = json.loads(self.json_text.get("1.0", tk.END))
            except json.JSONDecodeError as exc:
                messagebox.showerror("Invalid JSON", f"Fix the raw JSON first.\n\n{exc}")
                return

        if "bindings" not in parsed or not isinstance(parsed["bindings"], list):
            messagebox.showerror("Invalid config", 'Config must contain a "bindings" list.')
            return

        save_config(parsed, self.config_path)
        self.config = parsed
        self._refresh_list()
        if self.listener_running:
            self._restart_listener()
        self.status_var.set(f"Saved {self.config_path}")

    def toggle_listener(self) -> None:
        if self.listener_running:
            self._stop_listener()
            return

        self._start_listener()

    def _start_listener(self) -> None:
        try:
            from quiktieper.listener import ChordListener
        except Exception as exc:
            messagebox.showerror("Listener error", f"Could not import keyboard hook.\n\n{exc}")
            return

        try:
            bindings = self._bindings_from_config(self.config)
            self.listener = ChordListener(bindings)
            self.listener.start()
        except Exception as exc:
            self.listener = None
            messagebox.showerror("Listener error", f"Could not start listener.\n\n{exc}")
            return

        self.listener_running = True
        self.listener_var.set("Listener: running")
        self.listener_button.configure(text="Stop Listener")
        self.status_var.set("Global chord listener is active")

    def _stop_listener(self) -> None:
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception as exc:
                messagebox.showerror("Listener error", f"Could not stop listener cleanly.\n\n{exc}")
                return

        self.listener = None
        self.listener_running = False
        self.listener_var.set("Listener: stopped")
        self.listener_button.configure(text="Start Listener")
        self.status_var.set("Global chord listener is stopped")

    def _restart_listener(self) -> None:
        self._stop_listener()
        self._start_listener()

    def _binding_from_form(self, allow_blank: bool = False) -> dict | None:
        name = self.name_var.get().strip()
        command = self.command_var.get().strip()
        keys = [key.strip().lower() for key in self.keys_var.get().split(",") if key.strip()]
        cooldown_text = self.cooldown_var.get().strip()

        if allow_blank and not name and not command and not keys and cooldown_text in {"", "0.8"}:
            return None

        if not name or not command or not keys:
            messagebox.showerror("Missing fields", "Name, keys, and command are required.")
            return None

        try:
            cooldown_seconds = float(cooldown_text)
        except ValueError:
            messagebox.showerror("Invalid cooldown", "Cooldown must be a number.")
            return None

        return {
            "name": name,
            "keys": keys,
            "cmd": command,
            "cooldown_seconds": cooldown_seconds,
        }

    def _bindings_from_config(self, config: dict) -> list[Binding]:
        return [
            Binding(
                name=item["name"],
                keys=frozenset(key.lower() for key in item["keys"]),
                command=item.get("cmd") or item["command"],
                cooldown_seconds=float(item.get("cooldown_seconds", 0.8)),
            )
            for item in config.get("bindings", [])
        ]

    def _on_close(self) -> None:
        if self.listener_running:
            self._stop_listener()
        self.root.destroy()


def launch_editor(config_path: Path) -> None:
    ConfigEditorApp(config_path).run()
