from __future__ import annotations

import json
import shutil
import threading
import time
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from Agent.cancellation import CancellationToken
from Agent.chat_store import ChatStore
from Agent.orchestration import ForemanConfig
from PhiConnect.foreman_handler import ForemanChatHandler
from PhiConnect.chat import (
    DEFAULT_PHICONNECT_DIR,
    PhiConnectConfig,
    build_phiconnect_server,
    ensure_identity,
    read_recent_messages,
    run_phiconnect_receiver,
    send_chat_message,
    trust_public_key,
)


class PhiConnectApp(tk.Tk):
    def __init__(self, config: PhiConnectConfig | None = None) -> None:
        super().__init__()
        self.title("PhiConnect")
        self.geometry("900x640")
        self.config_model = config or PhiConnectConfig()
        self.receiver_server = None
        self.receiver_thread: threading.Thread | None = None
        self.status_var = tk.StringVar(value="Receiver stopped")
        self.listen_host = tk.StringVar(value=self.config_model.listen_host)
        self.listen_port = tk.StringVar(value=str(self.config_model.listen_port))
        self.peer_host = tk.StringVar(value=self.config_model.peer_host)
        self.peer_port = tk.StringVar(value=str(self.config_model.peer_port))
        self.use_agent = tk.BooleanVar(value=False)
        ensure_identity(self.config_model)

        # Agent tab state
        agent_db_path = DEFAULT_PHICONNECT_DIR / "agent_chats.db"
        DEFAULT_PHICONNECT_DIR.mkdir(parents=True, exist_ok=True)
        self._agent_store = ChatStore(str(agent_db_path))
        self._agent_handler = ForemanChatHandler(
            chat_store=self._agent_store,
            config=ForemanConfig(parallel_by_default=False),
        )
        self._agent_session_id: str | None = None
        self._agent_cancel_token: CancellationToken | None = None
        self._agent_foreman_var = tk.BooleanVar(value=False)
        self._agent_foreman_status = tk.StringVar(value="Simple chat")
        self._foreman_parallel_var = tk.BooleanVar(value=False)
        self._foreman_max_subagents_var = tk.IntVar(value=5)
        self._foreman_max_turns_var = tk.IntVar(value=10)

        self._build_ui()
        self._refresh_loop()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)
        chat_tab = ttk.Frame(notebook, padding=10)
        settings_tab = ttk.Frame(notebook, padding=10)
        agent_tab = ttk.Frame(notebook, padding=10)
        notebook.add(chat_tab, text="Chat")
        notebook.add(agent_tab, text="Agent")
        notebook.add(settings_tab, text="Settings")
        self._build_chat_tab(chat_tab)
        self._build_agent_tab(agent_tab)
        self._build_settings_tab(settings_tab)

    def _build_chat_tab(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)
        self.toggle_btn = ttk.Button(top, text="Start Receiver", command=self._toggle_receiver)
        self.toggle_btn.pack(side=tk.LEFT)
        ttk.Checkbutton(top, text="Agent Bridge", variable=self.use_agent).pack(side=tk.LEFT, padx=10)
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)
        listen = ttk.Frame(parent)
        listen.pack(fill=tk.X, pady=8)
        ttk.Label(listen, text="Listen host").pack(side=tk.LEFT)
        ttk.Entry(listen, textvariable=self.listen_host, width=18).pack(side=tk.LEFT, padx=6)
        ttk.Label(listen, text="Port").pack(side=tk.LEFT)
        ttk.Entry(listen, textvariable=self.listen_port, width=8).pack(side=tk.LEFT, padx=6)
        peer = ttk.Frame(parent)
        peer.pack(fill=tk.X, pady=8)
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
            ("Peer public key", str(self.config_model.peer_public_path)),
            ("Chat log", str(self.config_model.chat_log_path)),
            ("Listen", f"{self.config_model.listen_host}:{self.config_model.listen_port}"),
        ]
        for label, value in rows:
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
            ttk.Label(row, text=value).pack(side=tk.LEFT)
        button_row = ttk.Frame(parent)
        button_row.pack(anchor=tk.W, pady=10)
        ttk.Button(button_row, text="Set Peer Public Key", command=self._set_peer_key).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Use Local Public Key", command=self._use_local_public_key).pack(side=tk.LEFT)
        ttk.Label(parent, text="Local public key").pack(anchor=tk.W)
        text = tk.Text(parent, height=10, wrap=tk.NONE)
        text.insert("1.0", public_data)
        text.configure(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True)

        # -- Foreman Configuration section
        settings_sep = ttk.Separator(parent, orient=tk.HORIZONTAL)
        settings_sep.pack(fill=tk.X, pady=10)

        foreman_frame = ttk.LabelFrame(parent, text="Foreman Configuration", padding=8)
        foreman_frame.pack(fill=tk.X)

        # Parallel toggle
        pf = ttk.Frame(foreman_frame)
        pf.pack(fill=tk.X, pady=2)
        ttk.Label(pf, text="Parallel execution:").pack(side=tk.LEFT)
        ttk.Checkbutton(
            pf, variable=self._foreman_parallel_var,
            command=self._agent_update_foreman_config,
        ).pack(side=tk.LEFT, padx=6)

        # Max sub-agents
        mf = ttk.Frame(foreman_frame)
        mf.pack(fill=tk.X, pady=2)
        ttk.Label(mf, text="Max sub-agents:").pack(side=tk.LEFT)
        ttk.Spinbox(
            mf, from_=1, to=10, textvariable=self._foreman_max_subagents_var,
            width=5, command=self._agent_update_foreman_config,
        ).pack(side=tk.LEFT, padx=6)

        # Max turns per sub-agent
        tf = ttk.Frame(foreman_frame)
        tf.pack(fill=tk.X, pady=2)
        ttk.Label(tf, text="Max turns per sub-agent:").pack(side=tk.LEFT)
        ttk.Spinbox(
            tf, from_=1, to=50, textvariable=self._foreman_max_turns_var,
            width=5, command=self._agent_update_foreman_config,
        ).pack(side=tk.LEFT, padx=6)

    # ------------------------------------------------------------------
    # Agent tab
    # ------------------------------------------------------------------

    def _build_agent_tab(self, parent: ttk.Frame) -> None:
        """Build the Agent chat tab with personality selector, chat display, and input bar."""
        # -- Top bar: personality combobox + New Chat + Cancel
        top_bar = ttk.Frame(parent)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(top_bar, text="Personality:").pack(side=tk.LEFT)
        self._agent_personality_var = tk.StringVar(value="general")
        personality_names = [
            p.name for p in self._agent_handler._registry.list()
        ]
        personality_combo = ttk.Combobox(
            top_bar,
            textvariable=self._agent_personality_var,
            values=personality_names,
            state="readonly",
            width=14,
        )
        personality_combo.pack(side=tk.LEFT, padx=(4, 10))

        ttk.Checkbutton(
            top_bar, text="\U0001f310 Foreman",
            variable=self._agent_foreman_var,
            command=self._agent_toggle_foreman,
        ).pack(side=tk.LEFT, padx=(10, 4))
        ttk.Label(
            top_bar, textvariable=self._agent_foreman_status,
            foreground="#555",
        ).pack(side=tk.LEFT)

        self._agent_new_btn = ttk.Button(
            top_bar, text="New Chat", command=self._agent_new_chat,
        )
        self._agent_new_btn.pack(side=tk.LEFT, padx=(0, 4))

        self._agent_cancel_btn = ttk.Button(
            top_bar, text="Cancel", command=self._agent_cancel,
            state=tk.DISABLED,
        )
        self._agent_cancel_btn.pack(side=tk.LEFT)

        # -- Chat display
        self._agent_chat_text = tk.Text(
            parent, height=24, state=tk.DISABLED, wrap=tk.WORD,
        )
        self._agent_chat_text.pack(fill=tk.BOTH, expand=True, pady=6)

        # Configure colour tags for message roles
        self._agent_chat_text.tag_config(
            "user", foreground="#4A90D9",
        )
        self._agent_chat_text.tag_config(
            "agent", foreground="#2ECC71",
        )
        self._agent_chat_text.tag_config(
            "system", foreground="#95A5A6",
        )
        self._agent_chat_text.tag_config(
            "error", foreground="#E74C3C",
        )
        self._agent_chat_text.tag_config(
            "cancelled", foreground="#F39C12",
        )

        # -- Bottom bar: message entry + Send button
        bottom_bar = ttk.Frame(parent)
        bottom_bar.pack(fill=tk.X)

        self._agent_message_var = tk.StringVar()
        agent_entry = ttk.Entry(
            bottom_bar, textvariable=self._agent_message_var,
        )
        agent_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        agent_entry.bind("<Return>", lambda _e: self._agent_send_message())

        self._agent_send_btn = ttk.Button(
            bottom_bar, text="Send", command=self._agent_send_message,
        )
        self._agent_send_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Auto-create the first session
        self._agent_new_chat()

    def _agent_send_message(self) -> None:
        """Read the message entry, cancel any previous token, then send."""
        if self._agent_session_id is None:
            return
        message = self._agent_message_var.get().strip()
        if not message:
            return

        self._agent_message_var.set("")
        self._agent_set_busy(True)

        token = CancellationToken()
        self._agent_cancel_token = token

        self._agent_handler.send_message(
            session_id=self._agent_session_id,
            message=message,
            token=token,
            on_message=lambda role, content: self.after(
                0, self._agent_append_message, role, content,
            ),
            on_error=lambda err: self.after(
                0, self._agent_on_message_error, err,
            ),
            on_complete=lambda: self.after(
                0, self._agent_on_message_complete,
            ),
        )

    def _agent_on_message_error(self, error_msg: str) -> None:
        """Handle error callback from the agent handler (runs on main thread)."""
        if error_msg == "Operation cancelled":
            self._agent_append_message("cancelled", error_msg)
        else:
            self._agent_append_message("error", error_msg)
        self._agent_set_busy(False)
        self._agent_cancel_token = None

    def _agent_on_message_complete(self) -> None:
        """Handle completion callback from the agent handler (runs on main thread)."""
        self._agent_set_busy(False)
        self._agent_cancel_token = None

    def _agent_cancel(self) -> None:
        """Cancel the current in-flight message."""
        if self._agent_cancel_token is not None:
            self._agent_cancel_token.cancel()

    def _agent_new_chat(self) -> None:
        """Create a fresh session, clear the display, and reset state."""
        personality = self._agent_personality_var.get()
        try:
            self._agent_session_id = self._agent_handler.create_session(
                personality=personality,
            )
        except Exception as exc:
            messagebox.showerror("Agent Error", f"Could not create session: {exc}")
            return

        self._agent_chat_text.configure(state=tk.NORMAL)
        self._agent_chat_text.delete("1.0", tk.END)
        self._agent_chat_text.configure(state=tk.DISABLED)

        # Reset cancellation
        self._agent_cancel_token = None
        self._agent_set_busy(False)

    def _agent_toggle_foreman(self) -> None:
        """Toggle Foreman orchestration on/off."""
        enabled = self._agent_foreman_var.get()
        self._agent_handler.foreman_enabled = enabled
        self._agent_foreman_status.set("Foreman ON" if enabled else "Simple chat")

    def _agent_update_foreman_config(self) -> None:
        """Push config changes from Settings UI to ForemanChatHandler."""
        self._agent_handler.update_config(
            parallel_by_default=self._foreman_parallel_var.get(),
            max_sub_agents=self._foreman_max_subagents_var.get(),
            max_turns_per_sub_agent=self._foreman_max_turns_var.get(),
        )

    def _agent_append_message(self, role: str, content: str) -> None:
        """Append a colour-coded message to the agent chat display.

        Must be called from the main Tkinter thread (use ``after()``).
        """
        timestamp = time.strftime("%H:%M:%S")
        role_display = {
            "user": "You",
            "agent": "Fiona",
            "system": "System",
            "error": "Error",
            "cancelled": "Cancelled",
        }.get(role, role.capitalize())
        line = f"[{timestamp}] {role_display}: {content}\n"

        self._agent_chat_text.configure(state=tk.NORMAL)
        self._agent_chat_text.insert(tk.END, line, role)
        self._agent_chat_text.see(tk.END)
        self._agent_chat_text.configure(state=tk.DISABLED)

    def _agent_set_busy(self, busy: bool) -> None:
        """Enable or disable the Send, Cancel, and New Chat buttons."""
        if busy:
            self._agent_send_btn.configure(state=tk.DISABLED)
            self._agent_cancel_btn.configure(state=tk.NORMAL)
            self._agent_new_btn.configure(state=tk.DISABLED)
        else:
            self._agent_send_btn.configure(state=tk.NORMAL)
            self._agent_cancel_btn.configure(state=tk.DISABLED)
            self._agent_new_btn.configure(state=tk.NORMAL)

    def _toggle_receiver(self) -> None:
        if self.receiver_server:
            self._stop_receiver()
        else:
            self._start_receiver()

    def _start_receiver(self) -> None:
        if self.receiver_server:
            return
        try:
            self.config_model = replace(
                self.config_model,
                listen_host=self.listen_host.get().strip() or "0.0.0.0",
                listen_port=int(self.listen_port.get().strip()),
            )
        except ValueError as exc:
            messagebox.showerror("Invalid receiver port", str(exc))
            return

        on_message = None
        if self.use_agent.get():
            from PhiConnect.bridge import PhiConnectAgentBridge
            bridge = PhiConnectAgentBridge(config=self.config_model)
            on_message = bridge.handle_message

        try:
            self.receiver_server = build_phiconnect_server(self.config_model, on_message=on_message)
        except Exception as exc:
            messagebox.showerror("Could not start receiver", str(exc))
            return

        self.receiver_thread = threading.Thread(target=self.receiver_server.serve_forever, daemon=True)
        self.receiver_thread.start()
        self.status_var.set(f"Listening on {self.config_model.listen_host}:{self.config_model.listen_port}")
        self.toggle_btn.configure(text="Stop Receiver")

    def _stop_receiver(self) -> None:
        if not self.receiver_server:
            return
        self.receiver_server.shutdown()
        self.receiver_server.server_close()
        self.receiver_server = None
        self.receiver_thread = None
        self.status_var.set("Receiver stopped")
        self.toggle_btn.configure(text="Start Receiver")

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

    def _set_peer_key(self) -> None:
        path = filedialog.askopenfilename(title="Select peer public key", filetypes=[("JSON", "*.json"), ("All files", "*")])
        if not path:
            return
        try:
            self.config_model.peer_public_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, self.config_model.peer_public_path)
            trusted_path = trust_public_key(self.config_model.peer_public_path, self.config_model.trusted_dir)
        except Exception as exc:
            messagebox.showerror("Could not set peer key", str(exc))
            return
        messagebox.showinfo("Peer key ready", f"Peer key saved to {self.config_model.peer_public_path}\nTrusted key saved to {trusted_path}")

    def _use_local_public_key(self) -> None:
        try:
            identity = ensure_identity(self.config_model)
            self.config_model.peer_public_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.config_model.public_path, self.config_model.peer_public_path)
            trusted_path = trust_public_key(self.config_model.public_path, self.config_model.trusted_dir)
        except Exception as exc:
            messagebox.showerror("Could not use local key", str(exc))
            return
        messagebox.showinfo(
            "Local loopback ready",
            f"{identity.device_id} can now send to this receiver on localhost.\nTrusted key saved to {trusted_path}",
        )

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
