from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from DataClient.miner import deep_research_topic, mine_topic
from DataClient.table import Rows, add_column, add_row, cell_name, evaluate_formula, load_table, save_table, table_columns


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
        self.table_path: Path | None = None
        self.rows: Rows = []
        self.selected_column_var = tk.StringVar()
        self.cell_value_var = tk.StringVar()
        self.formula_var = tk.StringVar()
        self.active_cell_var = tk.StringVar(value="Cell")
        self._build_ui()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        self._build_menu()
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        research_tab = ttk.Frame(notebook, padding=10)
        table_tab = ttk.Frame(notebook, padding=10)
        notebook.add(research_tab, text="Research")
        notebook.add(table_tab, text="MiniExcel")
        self._build_research_tab(research_tab)
        self._build_table_tab(table_tab)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        miner_menu = tk.Menu(menubar, tearoff=False)
        miner_menu.add_command(label="Run quick miner", command=self._run_quick_from_menu)
        miner_menu.add_command(label="Run deep research", command=self._run_deep_from_menu)
        miner_menu.add_separator()
        miner_menu.add_command(label="Clear miner log", command=lambda: self.log.delete("1.0", tk.END) if hasattr(self, "log") else None)
        menubar.add_cascade(label="Miner", menu=miner_menu)

        table_menu = tk.Menu(menubar, tearoff=False)
        table_menu.add_command(label="Open table", command=self._open_table)
        table_menu.add_command(label="Save table", command=self._save_table)
        table_menu.add_command(label="Save table as", command=self._save_table_as)
        table_menu.add_separator()
        table_menu.add_command(label="Apply formula", command=self._apply_formula)
        menubar.add_cascade(label="MiniExcel", menu=table_menu)
        self.root.configure(menu=menubar)

    def _build_research_tab(self, frame: ttk.Frame) -> None:
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

    def _build_table_tab(self, frame: ttk.Frame) -> None:
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="Open", command=self._open_table).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Save", command=self._save_table).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Save As", command=self._save_table_as).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Add Row", command=self._add_table_row).pack(side="left", padx=(10, 6))
        ttk.Button(toolbar, text="Add Column", command=self._add_table_column).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Delete Row", command=self._delete_table_row).pack(side="left", padx=(0, 6))

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, show="headings")
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.table.bind("<<TreeviewSelect>>", self._load_selected_row_value)

        editor = ttk.Frame(frame)
        editor.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(editor, text="Column").pack(side="left")
        self.column_combo = ttk.Combobox(editor, textvariable=self.selected_column_var, state="readonly", width=18)
        self.column_combo.pack(side="left", padx=(6, 12))
        ttk.Label(editor, text="Value").pack(side="left")
        ttk.Entry(editor, textvariable=self.cell_value_var, width=40).pack(side="left", padx=(6, 12), fill="x", expand=True)
        ttk.Button(editor, text="Set Cell", command=self._set_selected_cell).pack(side="left")

        formula = ttk.Frame(frame)
        formula.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        formula.columnconfigure(2, weight=1)
        ttk.Label(formula, textvariable=self.active_cell_var, width=8).grid(row=0, column=0, sticky="w")
        ttk.Label(formula, text="fx").grid(row=0, column=1, sticky="w", padx=(6, 6))
        ttk.Entry(formula, textvariable=self.formula_var).grid(row=0, column=2, sticky="ew")
        ttk.Button(formula, text="Apply", command=self._apply_formula).grid(row=0, column=3, sticky="e", padx=(8, 0))

        self.table_status_var = tk.StringVar(value="Open a CSV, JSON, or SQLite DB file.")
        ttk.Label(frame, textvariable=self.table_status_var).grid(row=4, column=0, sticky="w", pady=(8, 0))

    def _run_quick_from_menu(self) -> None:
        self.mode_var.set("Quick")
        self._start_miner()

    def _run_deep_from_menu(self) -> None:
        self.mode_var.set("Deep")
        self._start_miner()

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

    def _open_table(self) -> None:
        path = filedialog.askopenfilename(
            title="Open table",
            filetypes=[("Data files", "*.csv *.json *.db *.sqlite *.sqlite3"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.rows = load_table(Path(path))
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))
            return
        self.table_path = Path(path)
        self._refresh_table()

    def _save_table(self) -> None:
        if self.table_path is None:
            self._save_table_as()
            return
        try:
            save_table(self.rows, self.table_path)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.table_status_var.set(f"Saved {len(self.rows)} rows to {self.table_path}")

    def _save_table_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save table as",
            defaultextension=".csv",
            filetypes=[
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("SQLite DB", "*.db *.sqlite *.sqlite3"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.table_path = Path(path)
        self._save_table()

    def _add_table_row(self) -> None:
        add_row(self.rows)
        self._refresh_table()

    def _add_table_column(self) -> None:
        name = simpledialog.askstring("Add column", "Column name:")
        if not name:
            return
        try:
            add_column(self.rows, name)
        except Exception as exc:
            messagebox.showerror("Add column failed", str(exc))
            return
        self._refresh_table()

    def _delete_table_row(self) -> None:
        selected = self.table.selection()
        if not selected:
            return
        indices = sorted((self.table.index(item) for item in selected), reverse=True)
        for index in indices:
            if 0 <= index < len(self.rows):
                del self.rows[index]
        self._refresh_table()

    def _set_selected_cell(self) -> None:
        selected = self.table.selection()
        column = self.selected_column_var.get()
        if not selected or not column:
            return
        index = self.table.index(selected[0])
        if 0 <= index < len(self.rows):
            self.rows[index][column] = self.cell_value_var.get()
            self.formula_var.set(self.cell_value_var.get())
        self._refresh_table()
        if index < len(self.table.get_children()):
            self.table.selection_set(self.table.get_children()[index])

    def _load_selected_row_value(self, _event: object | None = None) -> None:
        selected = self.table.selection()
        column = self.selected_column_var.get()
        if not selected or not column:
            return
        index = self.table.index(selected[0])
        if 0 <= index < len(self.rows):
            columns = table_columns(self.rows)
            column_index = columns.index(column) if column in columns else 0
            value = str(self.rows[index].get(column, ""))
            self.cell_value_var.set(value)
            self.formula_var.set(value)
            self.active_cell_var.set(cell_name(index, column_index))

    def _apply_formula(self) -> None:
        selected = self.table.selection()
        column = self.selected_column_var.get()
        expression = self.formula_var.get()
        if not selected or not column:
            return
        index = self.table.index(selected[0])
        try:
            value = evaluate_formula(expression, self.rows, row_index=index) if expression.strip().startswith("=") else expression
        except Exception as exc:
            messagebox.showerror("Formula error", str(exc))
            return
        if 0 <= index < len(self.rows):
            self.rows[index][column] = value
            self.cell_value_var.set(str(value))
        self._refresh_table()
        if index < len(self.table.get_children()):
            item = self.table.get_children()[index]
            self.table.selection_set(item)
            self.table.focus(item)

    def _refresh_table(self) -> None:
        columns = table_columns(self.rows)
        self.table.configure(columns=columns)
        self.table.delete(*self.table.get_children())
        for column in columns:
            self.table.heading(column, text=column)
            self.table.column(column, width=140, minwidth=80, stretch=True)
        for row in self.rows:
            self.table.insert("", "end", values=[row.get(column, "") for column in columns])
        self.column_combo.configure(values=columns)
        if columns and self.selected_column_var.get() not in columns:
            self.selected_column_var.set(columns[0])
        elif not columns:
            self.selected_column_var.set("")
        source = str(self.table_path) if self.table_path else "unsaved table"
        self.table_status_var.set(f"{source} - {len(self.rows)} rows, {len(columns)} columns")


def launch_dataclient() -> None:
    DataClientApp().run()
