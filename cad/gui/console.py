"""Interactive Python console panel — execute CAD commands and scripts."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from cad.core.document import Document
from cad.commands.registry import CommandRegistry
from cad.scripting.console import ScriptingConsole


class ConsolePanel(ttk.Frame):
    """Interactive Python console for CAD scripting within the GUI."""

    def __init__(self, parent: tk.Widget, registry: CommandRegistry,
                 doc: Document) -> None:
        super().__init__(parent)
        self.registry = registry
        self.doc = doc
        self.console = ScriptingConsole(registry, doc)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Output area
        output_frame = ttk.LabelFrame(self, text="Console Output", padding=4)
        output_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.output_text = tk.Text(output_frame, height=6, wrap="word",
                                    bg="#0a0e14", fg="#d4d4d4",
                                    insertbackground="#d4d4d4",
                                    font=("Consolas", 10))
        self.output_text.grid(row=0, column=0, sticky="nsew")
        self.output_text.config(state=tk.DISABLED)

        scrollbar = ttk.Scrollbar(output_frame, orient="vertical",
                                  command=self.output_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output_text.config(yscrollcommand=scrollbar.set)

        # Input area
        input_frame = ttk.Frame(self)
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.columnconfigure(0, weight=1)

        self.prompt_label = ttk.Label(input_frame, text=">>> ")
        self.prompt_label.grid(row=0, column=0, sticky="w")

        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_var,
                                     font=("Consolas", 10))
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=4)
        self.input_entry.bind("<Return>", self._execute_input)
        self.input_entry.bind("<Up>", self._history_up)
        self.input_entry.bind("<Down>", self._history_down)

        ttk.Button(input_frame, text="Run", command=self._execute_input_click).grid(
            row=0, column=2, padx=4)

        # Help text
        help_frame = ttk.Frame(self)
        help_frame.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(help_frame, text="Commands: create_box(w=10,h=20,d=30), "
                  "create_cylinder(r=5,h=15), recompute(), list_objects()",
                  foreground="#888888", font=("", 8)).pack(anchor="w")

        # Command history
        self._history: list[str] = []
        self._history_index = 0

    def append_output(self, text: str) -> None:
        """Append text to the output area."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def _execute_input(self, event: tk.Event | None = None) -> None:
        code = self.input_var.get().strip()
        if not code:
            return
        self._history.append(code)
        self._history_index = len(self._history)
        self.input_var.set("")

        self.append_output(f">>> {code}")
        result = self.console.execute(code)
        if result:
            self.append_output(result)

        # Refresh panels
        self.event_generate("<<CADCommandExecuted>>")

    def _execute_input_click(self) -> None:
        self._execute_input()

    def _history_up(self, event: tk.Event) -> None:
        if not self._history:
            return
        self._history_index = max(0, self._history_index - 1)
        self.input_var.set(self._history[self._history_index])

    def _history_down(self, event: tk.Event) -> None:
        if not self._history:
            return
        self._history_index = min(len(self._history), self._history_index + 1)
        if self._history_index >= len(self._history):
            self.input_var.set("")
        else:
            self.input_var.set(self._history[self._history_index])
