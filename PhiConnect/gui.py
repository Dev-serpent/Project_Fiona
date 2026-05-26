from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PhiConnect.chat import PhiConnectConfig, ensure_identity, read_recent_messages, run_phiconnect_receiver, send_chat_message, trust_public_key


class PhiConnectApp(tk.Tk):
    def __init__(self, config: PhiConnectConfig | None = None) -> None:
        super().__init__()
        self.title("PhiConnect")
        self.geometry("900x640")
        self.config_model = config or PhiConnectConfig()
        self.receiver_thread: threading.Thread | None = None
        self.status_var = tk.StringVar(value="Receiver stopped")
        ensure_identity(self.config_model)
        self._build_ui()
        self._refresh_loop()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)
        chat_tab = ttk.Frame(notebook, padding=10)
        settings_tab = ttk.Frame(notebook, padding=10)
        notebook.add(chat_tab, text="Chat")
        notebook.add(settings_tab, text="Settings")
        self._build_chat_tab(chat_tab)
        self._build_settings_tab(settings_tab)

    def _build_chat_tab(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)
        ttk.Button(top, text="Start Receiver", command=self._start_receiver).pack(side=tk.LEFT)
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)
        peer = ttk.Frame(parent)
        peer.pack(fill=tk.X, pady=8)
        self.peer_host = tk.StringVar(value=self.config_model.peer_host)
        self.peer_port = tk.StringVar(value=str(self.config_model.peer_port))
        ttk.Label(peer, text="Peer host").pack(side=tk.LEFT)
        ttk.Entry(peer, textvariable=self.peer_host, width=18).pack(side=tk.LEFT, padx=6)
        ttk.Label(peer, text="Port").pack(side=tk.LEFT)
        ttk.Entry(peer, textvariable=self.peer_port, width=8).pack(side=tk.LEFT, padx=6)

        self.chat_text = tk.Text(parent, height=24, state=tk.DISABLED, wrap=tk.WORD)
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=8)
        bottom = ttk.Frame(parent)
        bottom.pack(fill=tk.X)
        self.message_var = tk.StringVar()
        ttk.Entry(bottom, textvariable=self.message_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(bottom, text="Send", command=self._send_message).pack(side=tk.LEFT, padx=8)

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        identity = ensure_identity(self.config_model)
        public_data = json.dumps(identity.public_bundle.to_dict(), indent=2, sort_keys=True)
        rows = [
            ("Device ID", identity.device_id),
            ("Private key", str(self.config_model.private_path)),
            ("Public key", str(self.config_model.public_path)),
            ("Trusted keys", str(self.config_model.trusted_dir)),
            ("Chat log", str(self.config_model.chat_log_path)),
            ("Listen", f"{self.config_model.listen_host}:{self.config_model.listen_port}"),
        ]
        for label, value in rows:
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
            ttk.Label(row, text=value).pack(side=tk.LEFT)
        ttk.Button(parent, text="Trust Peer Public Key", command=self._trust_peer_key).pack(anchor=tk.W, pady=10)
        ttk.Label(parent, text="Local public key").pack(anchor=tk.W)
        text = tk.Text(parent, height=10, wrap=tk.NONE)
        text.insert("1.0", public_data)
        text.configure(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True)

    def _start_receiver(self) -> None:
        if self.receiver_thread and self.receiver_thread.is_alive():
            return
        self.receiver_thread = threading.Thread(target=run_phiconnect_receiver, args=(self.config_model,), daemon=True)
        self.receiver_thread.start()
        self.status_var.set(f"Listening on {self.config_model.listen_host}:{self.config_model.listen_port}")

    def _send_message(self) -> None:
        body = self.message_var.get().strip()
        if not body:
            return
        try:
            send_chat_message(
                body,
                config=self.config_model,
                host=self.peer_host.get().strip(),
                port=int(self.peer_port.get().strip()),
            )
        except Exception as exc:
            messagebox.showerror("PhiConnect send failed", str(exc))
            return
        self.message_var.set("")
        self._refresh_messages()

    def _trust_peer_key(self) -> None:
        path = filedialog.askopenfilename(title="Select peer public key", filetypes=[("JSON", "*.json"), ("All files", "*")])
        if not path:
            return
        try:
            trusted_path = trust_public_key(Path(path), self.config_model.trusted_dir)
        except Exception as exc:
            messagebox.showerror("Could not trust key", str(exc))
            return
        messagebox.showinfo("Trusted key", f"Saved trusted key to {trusted_path}")

    def _refresh_loop(self) -> None:
        self._refresh_messages()
        self.after(5000, self._refresh_loop)

    def _refresh_messages(self) -> None:
        messages = read_recent_messages(self.config_model.chat_log_path)
        lines = []
        for event in messages:
            direction = event.get("direction", "event")
            status = "ok" if event.get("ok") else "failed"
            sender = event.get("sender", "")
            body = event.get("body") or event.get("error") or ""
            lines.append(f"[{direction} {status}] {sender}: {body}")
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.insert("1.0", "\n".join(lines) or "No messages in the last 3 minutes.")
        self.chat_text.configure(state=tk.DISABLED)


def launch_phiconnect() -> None:
    PhiConnectApp().mainloop()
