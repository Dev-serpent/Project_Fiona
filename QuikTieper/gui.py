from __future__ import annotations

import datetime
import json
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from CamComs import (
    DEFAULT_AUDIT_LOG_PATH,
    DEFAULT_FIONA_CONFIG_PATH,
    DEFAULT_IDENTITY_PATH,
    DEFAULT_PUBKEY_PATH,
    DEFAULT_TRUSTED_DIR,
    AuditLog,
    CamComsIdentity,
    CamComsHttpClient,
    HostService,
    PAIRING_REQUEST_TIMEOUT,
    PairingHttpServer,
    PairingManager,
    PairingRequest,
    PublicKeyBundle,
    TrustedSender,
    compute_fingerprint,
    default_host_service_config,
    decode_envelope,
    decrypt_text,
    encode_envelope,
    encrypt_message,
    get_fingerprint,
    instruction_from_text,
    instruction_to_text,
    is_trust_expired,
    list_trusted_senders,
    load_identity,
    press_instruction,
    private_key_path,
    prune_expired,
    public_key_path,
    remove_trusted_sender,
    rotate_keys,
    save_host_service_config,
    save_trusted_sender,
)
from QuikTieper.bindings import parse_bindings
from QuikTieper.config import DEFAULT_CONFIG_PATH, load_config, save_config
from QuikTieper.system_tray import SystemTrayIcon, TrayState
from QuikTieper.launcher import get_mouse_location
from Vsee import DEFAULT_EDGES_TEXT, DEFAULT_POINTS_TEXT, HologramModel, VseeModelError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBUG_ALLOWED_DIR_NAMES = ("tests", "scripts", "QuikTieper", "CamComs")
DEBUG_ALLOWED_DIRS = tuple(PROJECT_ROOT / name for name in DEBUG_ALLOWED_DIR_NAMES)
DEBUG_SKIP_DIRS = {"__pycache__", ".pytest_cache"}
DEBUG_TEXT_EXTENSIONS = {
    ".cfg",
    ".css",
    ".html",
    ".ino",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


SERVICE_NAME = "fiona-host.service"


def _get_service_state(service_name: str = SERVICE_NAME) -> dict[str, str]:
    """Query systemd --user for service state properties.

    Returns dict with keys: ActiveState, SubState, LoadState, MainPID, Uptime.
    On error, returns dict with 'error' key.
    """
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", service_name,
             "--property=ActiveState", "--property=SubState",
             "--property=LoadState", "--property=MainPID",
             "--property=ActiveEnterTimestamp"],
            capture_output=True, text=True, timeout=5.0,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "unknown"}
        props: dict[str, str] = {}
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                key, val = line.split("=", 1)
                props[key] = val
        # Compute human-readable uptime from ActiveEnterTimestamp
        raw_ts = props.get("ActiveEnterTimestamp", "")
        if raw_ts and raw_ts != "n/a":
            try:
                # Format: "Mon 2023-01-16 10:15:30 TZ"
                parts = raw_ts.rsplit(" ", 1)
                if len(parts) == 2:
                    dt_str = parts[0]
                    dt_naive = datetime.datetime.strptime(dt_str, "%a %Y-%m-%d %H:%M:%S")
                    dt_aware = dt_naive.replace(tzinfo=datetime.timezone.utc)
                    delta = datetime.datetime.now(datetime.timezone.utc) - dt_aware
                    days = delta.days
                    hours, remainder = divmod(delta.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime_parts = []
                    if days > 0:
                        uptime_parts.append(f"{days}d")
                    if hours > 0:
                        uptime_parts.append(f"{hours}h")
                    if minutes > 0:
                        uptime_parts.append(f"{minutes}m")
                    uptime_parts.append(f"{seconds}s")
                    props["Uptime"] = " ".join(uptime_parts)
                else:
                    props["Uptime"] = raw_ts
            except (ValueError, IndexError):
                props["Uptime"] = raw_ts
        elif raw_ts == "n/a":
            props["Uptime"] = "n/a"
        else:
            props["Uptime"] = "unknown"
        return props
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        return {"error": str(e)}


class ConfigEditorApp:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.root = tk.Tk()
        self.root.title("Fiona")
        self.root.geometry("1040x620")

        self.listener = None
        self.listener_running = False
        self.tree_index: dict[str, dict] = {}
        self.listener_var = tk.StringVar(value="Listener: stopped")
        self.status_var = tk.StringVar(value=f"Config: {self.config_path}")
        self._service_systemd_available = True
        self._service_poll_id: str | None = None
        self.pairing_manager = PairingManager()
        self.pairing_http_server: PairingHttpServer | None = None
        self._pairing_poll_id: str | None = None
        self._trusted_poll_id: str | None = None
        self._seeondesk_poll_id: str | None = None
        self._seeondesk_available = True
        self._tray_poll_id: str | None = None
        self._minimize_to_tray = tk.BooleanVar(value=False)
        self.tray = SystemTrayIcon(on_show=self._tray_show_window, on_quit=self._tray_quit)
        self._build_ui()
        self.root.bind_all("<Alt-c>", self.capture_mouse_position_hotkey)
        self.root.bind_all("<Alt-C>", self.capture_mouse_position_hotkey)
        self._load()
        self.tray.start()
        if self.tray.available:
            self._tray_poll()
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
        camcoms_tab = ttk.Frame(self.notebook, padding=12)
        pairing_tab = ttk.Frame(self.notebook, padding=12)
        host_tab = ttk.Frame(self.notebook, padding=12)
        vsee_tab = ttk.Frame(self.notebook, padding=12)
        voice_tab = ttk.Frame(self.notebook, padding=12)
        debug_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(camcoms_tab, text="CamComs")
        self.notebook.add(vsee_tab, text="Vsee")
        self.notebook.add(bindings_tab, text="Bindings")
        self.notebook.add(json_tab, text="Raw Json")
        self.notebook.add(debug_tab, text="Debug")
        self.notebook.add(pairing_tab, text="Pairing")
        self.notebook.add(host_tab, text="Host")
        self.notebook.add(voice_tab, text="Voice")

        self._build_bindings_tab(bindings_tab)
        self._build_json_tab(json_tab)
        self._build_camcoms_tab(camcoms_tab)
        self._build_pairing_tab(pairing_tab)
        self._build_host_tab(host_tab)
        self._build_vsee_tab(vsee_tab)
        self._build_voice_tab(voice_tab)
        self._build_debug_tab(debug_tab)

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1)

        ttk.Label(footer, textvariable=self.listener_var).grid(row=0, column=0, sticky="w", padx=(0, 18))
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=1, sticky="w")
        self.listener_button = ttk.Button(footer, text="Start Listener", command=self.toggle_listener)
        self.listener_button.grid(row=0, column=2, sticky="e", padx=(12, 6))
        self.tray_checkbox = ttk.Checkbutton(footer, text="Minimize to tray", variable=self._minimize_to_tray)
        self.tray_checkbox.grid(row=0, column=3, sticky="e", padx=(6, 6))
        ttk.Button(footer, text="Save All", command=self.save_all).grid(row=0, column=4, sticky="e")

    def _build_bindings_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.binding_tree = ttk.Treeview(left, show="tree")
        self.binding_tree.grid(row=0, column=0, sticky="nsew")
        self.binding_tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        actions = ttk.Frame(left)
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for index in range(4):
            actions.columnconfigure(index, weight=1)
        ttk.Button(actions, text="Add App", command=self.add_app).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Add Shortcut", command=self.add_shortcut).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(actions, text="Delete", command=self.delete_selected).grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Button(actions, text="Save Selected", command=self.save_selected).grid(
            row=0, column=3, sticky="ew", padx=(6, 0)
        )

        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        app_frame = ttk.LabelFrame(right, text="App", padding=12)
        app_frame.grid(row=0, column=0, sticky="ew")
        app_frame.columnconfigure(1, weight=1)

        ttk.Label(app_frame, text="App Name").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Label(app_frame, text="Window Match").grid(row=1, column=0, sticky="w", pady=6)

        self.app_name_var = tk.StringVar()
        self.window_match_var = tk.StringVar()

        ttk.Entry(app_frame, textvariable=self.app_name_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Entry(app_frame, textvariable=self.window_match_var).grid(row=1, column=1, sticky="ew", pady=6)

        binding_frame = ttk.LabelFrame(right, text="Binding", padding=12)
        binding_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        binding_frame.columnconfigure(1, weight=1)

        ttk.Label(binding_frame, text="Binding Name").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Label(binding_frame, text="Keys").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Label(binding_frame, text="Run Command").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Label(binding_frame, text="Instruction").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Label(binding_frame, text="Fiona Cmds").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Label(binding_frame, text="Cooldown").grid(row=5, column=0, sticky="w", pady=6)

        self.binding_name_var = tk.StringVar()
        self.keys_var = tk.StringVar()
        self.command_var = tk.StringVar()
        self.instruction_var = tk.StringVar()
        self.fiona_cmds_var = tk.StringVar()
        self.cooldown_var = tk.StringVar(value="0.8")

        ttk.Entry(binding_frame, textvariable=self.binding_name_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Entry(binding_frame, textvariable=self.keys_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Entry(binding_frame, textvariable=self.command_var).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Entry(binding_frame, textvariable=self.instruction_var).grid(row=3, column=1, sticky="ew", pady=6)
        ttk.Entry(binding_frame, textvariable=self.fiona_cmds_var).grid(row=4, column=1, sticky="ew", pady=6)
        ttk.Entry(binding_frame, textvariable=self.cooldown_var).grid(row=5, column=1, sticky="ew", pady=6)

        command_actions = ttk.Frame(binding_frame)
        command_actions.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        command_actions.columnconfigure(0, weight=1)
        command_actions.columnconfigure(1, weight=1)
        ttk.Button(command_actions, text="Capture Mouse Position", command=self.capture_mouse_position).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(command_actions, text="Clear Instruction", command=self.clear_instruction).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        hint = (
            "Select an app node to edit app metadata.\n"
            "Select Launch or a shortcut under an app to edit that binding.\n"
            "Press Alt+C inside this window to capture the current mouse position.\n"
            "Use instruction like mouse:1200,420 to move the pointer first.\n"
            "Fiona Cmds accepts values like mouse-left-click, mouse-right-click."
        )
        ttk.Label(binding_frame, text=hint, justify="left").grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

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

    def _build_camcoms_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)

        identity_frame = ttk.LabelFrame(parent, text="Identities", padding=12)
        identity_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        identity_frame.columnconfigure(1, weight=1)

        ttk.Label(identity_frame, text="Device ID").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Label(identity_frame, text="Private Out").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Label(identity_frame, text="Public Out").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Label(identity_frame, text="Private In").grid(row=3, column=0, sticky="w", pady=5)

        self.cam_device_id_var = tk.StringVar(value="host")
        self.cam_private_out_var = tk.StringVar(value=str(private_key_path("host")))
        self.cam_public_out_var = tk.StringVar(value=str(public_key_path("host")))
        self.cam_private_in_var = tk.StringVar(value=str(private_key_path("host")))

        ttk.Entry(identity_frame, textvariable=self.cam_device_id_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Entry(identity_frame, textvariable=self.cam_private_out_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Entry(identity_frame, textvariable=self.cam_public_out_var).grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Entry(identity_frame, textvariable=self.cam_private_in_var).grid(row=3, column=1, sticky="ew", pady=5)
        ttk.Button(identity_frame, text="Browse", command=lambda: self._browse_save(self.cam_private_out_var)).grid(
            row=1, column=2, sticky="ew", padx=(6, 0), pady=5
        )
        ttk.Button(identity_frame, text="Browse", command=lambda: self._browse_save(self.cam_public_out_var)).grid(
            row=2, column=2, sticky="ew", padx=(6, 0), pady=5
        )
        ttk.Button(identity_frame, text="Browse", command=lambda: self._browse_open(self.cam_private_in_var)).grid(
            row=3, column=2, sticky="ew", padx=(6, 0), pady=5
        )

        identity_actions = ttk.Frame(identity_frame)
        identity_actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        identity_actions.columnconfigure(0, weight=1)
        identity_actions.columnconfigure(1, weight=1)
        ttk.Button(identity_actions, text="Generate Identity", command=self.camcoms_generate_identity).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(identity_actions, text="Export Public", command=self.camcoms_export_public).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        message_frame = ttk.LabelFrame(parent, text="Messages", padding=12)
        message_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        message_frame.columnconfigure(1, weight=1)

        ttk.Label(message_frame, text="Sender Private").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Label(message_frame, text="Recipient Public").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Label(message_frame, text="Recipient Private").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Label(message_frame, text="Sender Public").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Label(message_frame, text="Message").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Label(message_frame, text="Host").grid(row=5, column=0, sticky="w", pady=5)

        self.cam_sender_private_var = tk.StringVar(value=str(private_key_path("esp32")))
        self.cam_recipient_public_var = tk.StringVar(value=str(public_key_path("host")))
        self.cam_recipient_private_var = tk.StringVar(value=str(private_key_path("host")))
        self.cam_sender_public_var = tk.StringVar(value=str(public_key_path("esp32")))
        self.cam_message_var = tk.StringVar(value=instruction_to_text(press_instruction(["alt", "s"])))
        self.cam_host_var = tk.StringVar(value="192.168.1.10")
        self.cam_port_var = tk.StringVar(value="8080")
        self.cam_path_var = tk.StringVar(value="/")
        self.cam_json_output_var = tk.BooleanVar(value=False)

        fields = [
            self.cam_sender_private_var,
            self.cam_recipient_public_var,
            self.cam_recipient_private_var,
            self.cam_sender_public_var,
            self.cam_message_var,
            self.cam_host_var,
        ]
        for row, variable in enumerate(fields):
            ttk.Entry(message_frame, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5)
        for row, variable in enumerate(fields[:4]):
            ttk.Button(message_frame, text="Browse", command=lambda var=variable: self._browse_open(var)).grid(
                row=row, column=2, sticky="ew", padx=(6, 0), pady=5
            )

        endpoint = ttk.Frame(message_frame)
        endpoint.grid(row=6, column=0, columnspan=3, sticky="ew", pady=5)
        endpoint.columnconfigure(1, weight=1)
        endpoint.columnconfigure(3, weight=1)
        ttk.Label(endpoint, text="Port").grid(row=0, column=0, sticky="w")
        ttk.Entry(endpoint, textvariable=self.cam_port_var, width=8).grid(row=0, column=1, sticky="ew", padx=(6, 12))
        ttk.Label(endpoint, text="Path").grid(row=0, column=2, sticky="w")
        ttk.Entry(endpoint, textvariable=self.cam_path_var).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        message_actions = ttk.Frame(message_frame)
        message_actions.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for column in range(4):
            message_actions.columnconfigure(column, weight=1)
        ttk.Button(message_actions, text="Encrypt", command=self.camcoms_encrypt).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(message_actions, text="Decrypt", command=self.camcoms_decrypt).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(message_actions, text="Send", command=self.camcoms_send).grid(
            row=0, column=2, sticky="ew", padx=6
        )
        ttk.Button(message_actions, text="Smoke Test", command=self.camcoms_smoke_test).grid(
            row=0, column=3, sticky="ew", padx=(6, 0)
        )
        ttk.Checkbutton(message_frame, text="Show envelope JSON on encrypt", variable=self.cam_json_output_var).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        # ── Key Management ──────────────────────────────────────────────
        keymgmt_frame = ttk.LabelFrame(parent, text="Key Management", padding=12)
        keymgmt_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        keymgmt_frame.columnconfigure(1, weight=1)

        ttk.Label(keymgmt_frame, text="Current Fingerprint").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.cam_fingerprint_var = tk.StringVar(value="(loading…)")
        fp_entry = ttk.Entry(
            keymgmt_frame, textvariable=self.cam_fingerprint_var, state="readonly"
        )
        fp_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=(6, 0))

        ttk.Label(keymgmt_frame, text="Trust Store Location").grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.cam_trust_dir_var = tk.StringVar(value=str(DEFAULT_TRUSTED_DIR))
        ts_entry = ttk.Entry(
            keymgmt_frame, textvariable=self.cam_trust_dir_var, state="readonly"
        )
        ts_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=(6, 0))

        keymgmt_actions = ttk.Frame(keymgmt_frame)
        keymgmt_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        keymgmt_actions.columnconfigure(0, weight=1)
        keymgmt_actions.columnconfigure(1, weight=1)
        ttk.Button(
            keymgmt_actions,
            text="Rotate Keys",
            command=self._camcoms_rotate_keys,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            keymgmt_actions,
            text="Prune Expired Trust",
            command=self._camcoms_prune_trust,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Load fingerprint from disk
        self._update_fingerprint_display()

        output_frame = ttk.LabelFrame(parent, text="CamComs Output", padding=12)
        output_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.cam_output_text = tk.Text(output_frame, wrap="word", height=12)
        self.cam_output_text.grid(row=0, column=0, sticky="nsew")
        output_buttons = ttk.Frame(output_frame)
        output_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        output_buttons.columnconfigure(0, weight=1)
        output_buttons.columnconfigure(1, weight=1)
        ttk.Button(output_buttons, text="Use Output As Message", command=self.camcoms_use_output_as_message).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(output_buttons, text="Clear Output", command=self.camcoms_clear_output).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

    def _build_pairing_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        # ── Server control ──────────────────────────────────────────────
        server_frame = ttk.LabelFrame(parent, text="Device Pairing", padding=12)
        server_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        server_frame.columnconfigure(1, weight=1)

        self.pairing_status_var = tk.StringVar(value="Pairing server: Stopped")
        self.pairing_listen_var = tk.StringVar(value="Listen for Pairing Requests")

        ttk.Label(server_frame, textvariable=self.pairing_status_var).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        self.pairing_listen_button = ttk.Button(
            server_frame,
            textvariable=self.pairing_listen_var,
            command=self._toggle_pairing_server,
        )
        self.pairing_listen_button.grid(row=0, column=1, sticky="w")

        # ── Pending requests ────────────────────────────────────────────
        pending_frame = ttk.LabelFrame(parent, text="Pending Requests", padding=12)
        pending_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 6))
        pending_frame.columnconfigure(0, weight=1)
        pending_frame.rowconfigure(0, weight=1)

        columns = ("device_id", "fingerprint", "received_at", "expires_in")
        self.pairing_tree = ttk.Treeview(
            pending_frame, columns=columns, show="headings", height=5
        )
        self.pairing_tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        self.pairing_tree.heading("device_id", text="Device ID")
        self.pairing_tree.heading("fingerprint", text="Fingerprint")
        self.pairing_tree.heading("received_at", text="Received")
        self.pairing_tree.heading("expires_in", text="Expires In")
        self.pairing_tree.column("device_id", width=140, minwidth=100)
        self.pairing_tree.column("fingerprint", width=160, minwidth=120)
        self.pairing_tree.column("received_at", width=100, minwidth=80)
        self.pairing_tree.column("expires_in", width=80, minwidth=60)

        # Scrollbar for the tree
        tree_scroll = ttk.Scrollbar(
            pending_frame, orient="vertical", command=self.pairing_tree.yview
        )
        tree_scroll.grid(row=0, column=4, sticky="ns")
        self.pairing_tree.configure(yscrollcommand=tree_scroll.set)

        # Approval controls
        approve_frame = ttk.Frame(pending_frame)
        approve_frame.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        approve_frame.columnconfigure(3, weight=1)

        ttk.Label(approve_frame, text="Expires in (days):").grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        self.pairing_expire_days_var = tk.StringVar(value="30")
        ttk.Spinbox(
            approve_frame,
            from_=0,
            to=3650,
            textvariable=self.pairing_expire_days_var,
            width=6,
        ).grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Label(approve_frame, text="(0 = no expiry)").grid(
            row=0, column=2, sticky="w", padx=(0, 12)
        )

        self.pairing_approve_button = ttk.Button(
            approve_frame, text="Approve", command=self._pairing_approve
        )
        self.pairing_approve_button.grid(row=0, column=3, sticky="e", padx=(0, 6))
        self.pairing_deny_button = ttk.Button(
            approve_frame, text="Deny", command=self._pairing_deny
        )
        self.pairing_deny_button.grid(row=0, column=4, sticky="e")

        # ── Trusted Devices ─────────────────────────────────────────────
        trusted_frame = ttk.LabelFrame(parent, text="Trusted Devices", padding=12)
        trusted_frame.grid(row=2, column=0, sticky="nsew", pady=(6, 6))
        trusted_frame.columnconfigure(0, weight=1)
        trusted_frame.rowconfigure(0, weight=1)

        trust_columns = ("device_id", "fingerprint", "added_at", "expires", "status")
        self.trusted_tree = ttk.Treeview(
            trusted_frame, columns=trust_columns, show="headings", height=5
        )
        self.trusted_tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        self.trusted_tree.heading("device_id", text="Device ID")
        self.trusted_tree.heading("fingerprint", text="Fingerprint")
        self.trusted_tree.heading("added_at", text="Added At")
        self.trusted_tree.heading("expires", text="Expires")
        self.trusted_tree.heading("status", text="Status")
        self.trusted_tree.column("device_id", width=130, minwidth=90)
        self.trusted_tree.column("fingerprint", width=150, minwidth=100)
        self.trusted_tree.column("added_at", width=90, minwidth=70)
        self.trusted_tree.column("expires", width=90, minwidth=70)
        self.trusted_tree.column("status", width=140, minwidth=100)

        # Scrollbar for the trusted tree
        trusted_scroll = ttk.Scrollbar(
            trusted_frame, orient="vertical", command=self.trusted_tree.yview
        )
        trusted_scroll.grid(row=0, column=4, sticky="ns")
        self.trusted_tree.configure(yscrollcommand=trusted_scroll.set)

        # Tag for expired entries (red text)
        self.trusted_tree.tag_configure("expired", foreground="red")

        # Trusted devices controls
        trust_actions = ttk.Frame(trusted_frame)
        trust_actions.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        trust_actions.columnconfigure(0, weight=1)
        trust_actions.columnconfigure(1, weight=1)
        ttk.Button(
            trust_actions, text="Remove", command=self._trusted_remove
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            trust_actions, text="Refresh", command=self._trusted_refresh
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # ── Pairing output ──────────────────────────────────────────────
        output_frame = ttk.LabelFrame(parent, text="Pairing Output", padding=12)
        output_frame.grid(row=3, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.pairing_output_text = tk.Text(
            output_frame, wrap="word", height=6, state="disabled"
        )
        self.pairing_output_text.grid(row=0, column=0, sticky="nsew")

        # Start polling
        self._pairing_poll()
        self._trusted_poll()

    def _toggle_pairing_server(self) -> None:
        """Start or stop the pairing HTTP server."""
        if self.pairing_http_server is not None and self.pairing_http_server.is_running:
            self._stop_pairing_server()
        else:
            self._start_pairing_server()

    def _start_pairing_server(self) -> None:
        """Start the threaded pairing HTTP server on port 8090."""
        try:
            server = PairingHttpServer(self.pairing_manager)
            server.start()
            self.pairing_http_server = server
            self.pairing_status_var.set("Pairing server: Listening on port 8090")
            self.pairing_listen_var.set("Stop Listening")
            self._set_pairing_output(f"Pairing server started on port 8090\n")
            self.status_var.set("Pairing server started on port 8090")
        except OSError as exc:
            self._set_pairing_output(f"Error starting pairing server: {exc}\n")
            self.status_var.set(f"Pairing server error: {exc}")

    def _stop_pairing_server(self) -> None:
        """Stop the pairing HTTP server."""
        if self.pairing_http_server is not None:
            try:
                self.pairing_http_server.stop()
            except Exception as exc:
                self._set_pairing_output(f"Error stopping pairing server: {exc}\n")
                self.status_var.set(f"Pairing server stop error: {exc}")
                return
        self.pairing_http_server = None
        self.pairing_status_var.set("Pairing server: Stopped")
        self.pairing_listen_var.set("Listen for Pairing Requests")
        self._set_pairing_output("Pairing server stopped\n")
        self.status_var.set("Pairing server stopped")

    def _pairing_approve(self) -> None:
        """Approve the selected pending pairing request."""
        selection = self.pairing_tree.selection()
        if not selection:
            messagebox.showwarning(
                "No selection", "Select a pending pairing request first."
            )
            return
        item = selection[0]
        values = self.pairing_tree.item(item, "values")
        request_id = values[0] if values else ""  # We store request_id as the first column (hidden)
        # Actually we need to look it up another way. The values are (device_id, fingerprint, ...).
        # Let's find the request_id by matching device_id + fingerprint.
        device_id = values[0] if len(values) > 0 else ""
        fingerprint = values[1] if len(values) > 1 else ""

        # Find the matching pending request by device_id + fingerprint
        found_request_id: str | None = None
        for req in self.pairing_manager.get_pending_requests():
            if req.device_id == device_id and req.fingerprint == fingerprint:
                found_request_id = req.request_id
                break

        if found_request_id is None:
            messagebox.showerror(
                "Request not found",
                "The pairing request is no longer available.",
            )
            return

        days_text = self.pairing_expire_days_var.get().strip()
        try:
            days = int(days_text)
        except ValueError:
            days = 30
        expires_in_days: int | None = days if days > 0 else None

        ok = self.pairing_manager.approve_request(
            found_request_id, expires_in_days=expires_in_days
        )
        if ok:
            self._set_pairing_output(
                f"Approved pairing for device: {device_id} "
                f"(fingerprint: {fingerprint}, "
                f"{'no expiry' if expires_in_days is None else f'expires in {days} days'})\n"
            )
            self.status_var.set(f"Approved {device_id}")
        else:
            self._set_pairing_output(
                f"Failed to approve: request no longer available\n"
            )
            self.status_var.set("Approval failed — request expired")
        self._pairing_refresh()
        self._trusted_refresh()

    def _pairing_deny(self) -> None:
        """Deny the selected pending pairing request."""
        selection = self.pairing_tree.selection()
        if not selection:
            messagebox.showwarning(
                "No selection", "Select a pending pairing request first."
            )
            return
        item = selection[0]
        values = self.pairing_tree.item(item, "values")
        device_id = values[0] if len(values) > 0 else ""
        fingerprint = values[1] if len(values) > 1 else ""

        found_request_id: str | None = None
        for req in self.pairing_manager.get_pending_requests():
            if req.device_id == device_id and req.fingerprint == fingerprint:
                found_request_id = req.request_id
                break

        if found_request_id is None:
            messagebox.showerror(
                "Request not found",
                "The pairing request is no longer available.",
            )
            return

        ok = self.pairing_manager.deny_request(found_request_id)
        if ok:
            self._set_pairing_output(f"Denied pairing for device: {device_id}\n")
            self.status_var.set(f"Denied {device_id}")
        else:
            self._set_pairing_output(
                f"Failed to deny: request no longer available\n"
            )
            self.status_var.set("Deny failed — request expired")
        self._pairing_refresh()

    def _pairing_refresh(self) -> None:
        """Refresh the pending requests treeview."""
        # Clear existing rows
        for row in self.pairing_tree.get_children():
            self.pairing_tree.delete(row)

        now = time.monotonic()
        for req in self.pairing_manager.get_pending_requests():
            remaining = PAIRING_REQUEST_TIMEOUT - (now - req.received_at)
            expires_in = f"{int(remaining)}s" if remaining > 0 else "expired"
            received_str = datetime.datetime.fromtimestamp(
                time.time() - (time.monotonic() - req.received_at)
            ).strftime("%H:%M:%S")
            self.pairing_tree.insert(
                "",
                tk.END,
                values=(
                    req.device_id,
                    req.fingerprint,
                    received_str,
                    expires_in,
                ),
            )
        # Enable/disable approve/deny based on selection
        self._pairing_update_buttons()

    def _pairing_update_buttons(self) -> None:
        """Enable or disable approve/deny buttons based on selection."""
        has_selection = bool(self.pairing_tree.selection())
        state = "normal" if has_selection else "disabled"
        self.pairing_approve_button.configure(state=state)
        self.pairing_deny_button.configure(state=state)

    def _pairing_poll(self) -> None:
        """Poll for new pairing requests every 2 seconds."""
        self._pairing_refresh()
        self._pairing_poll_id = self.root.after(2000, self._pairing_poll)

    def _set_pairing_output(self, value: str) -> None:
        self.pairing_output_text.configure(state="normal")
        self.pairing_output_text.insert(tk.END, value)
        self.pairing_output_text.see(tk.END)
        self.pairing_output_text.configure(state="disabled")

    # ── Trusted Devices helpers ──────────────────────────────────────────

    def _trusted_refresh(self) -> None:
        """Refresh the trusted devices treeview."""
        for row in self.trusted_tree.get_children():
            self.trusted_tree.delete(row)

        import time as _time

        now = _time.time()
        trusted_list = list_trusted_senders(DEFAULT_TRUSTED_DIR)
        for trusted in trusted_list:
            device_id = trusted.bundle.device_id
            fp = compute_fingerprint(trusted.bundle)
            added_at = _time.strftime(
                "%Y-%m-%d", _time.localtime(trusted.added_at)
            ) if trusted.added_at else "unknown"

            if trusted.expires_at is None:
                expires_str = "Never"
                status_str = "Never"
                tags = ()
            elif _time.time() > trusted.expires_at:
                expires_str = _time.strftime(
                    "%Y-%m-%d", _time.localtime(trusted.expires_at)
                )
                status_str = "EXPIRED"
                tags = ("expired",)
            else:
                expires_str = _time.strftime(
                    "%Y-%m-%d", _time.localtime(trusted.expires_at)
                )
                remaining_days = int((trusted.expires_at - now) / 86400)
                status_str = f"OK (expires in {remaining_days}d)"
                tags = ()

            self.trusted_tree.insert(
                "",
                tk.END,
                values=(device_id, fp, added_at, expires_str, status_str),
                tags=tags,
            )

    def _trusted_remove(self) -> None:
        """Remove a trusted device after confirmation."""
        selection = self.trusted_tree.selection()
        if not selection:
            messagebox.showwarning(
                "No selection", "Select a trusted device first."
            )
            return
        item = selection[0]
        values = self.trusted_tree.item(item, "values")
        device_id = values[0] if values else ""

        if not messagebox.askyesno(
            "Remove Trusted Device",
            f"Remove trust for device '{device_id}'?",
        ):
            return

        removed = remove_trusted_sender(device_id, DEFAULT_TRUSTED_DIR)
        if removed:
            self._set_pairing_output(f"Removed trusted device: {device_id}\n")
            self.status_var.set(f"Removed trusted device: {device_id}")
        else:
            self._set_pairing_output(
                f"Device not found (may have been removed already): {device_id}\n"
            )
            self.status_var.set(f"Trusted device not found: {device_id}")
        self._trusted_refresh()

    def _trusted_poll(self) -> None:
        """Poll for trust list changes every 10 seconds."""
        self._trusted_refresh()
        self._trusted_poll_id = self.root.after(10000, self._trusted_poll)

    def _build_host_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(3, weight=1)

        config_frame = ttk.LabelFrame(parent, text="Service Config", padding=12)
        config_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        config_frame.columnconfigure(1, weight=1)

        ttk.Label(config_frame, text="Config Path").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Label(config_frame, text="Trusted Device").grid(row=1, column=0, sticky="w", pady=5)

        self.host_config_path_var = tk.StringVar(value=str(DEFAULT_FIONA_CONFIG_PATH))
        self.host_trusted_device_var = tk.StringVar(value="esp32")
        ttk.Entry(config_frame, textvariable=self.host_config_path_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Entry(config_frame, textvariable=self.host_trusted_device_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(config_frame, text="Browse", command=lambda: self._browse_open(self.host_config_path_var)).grid(
            row=0, column=2, sticky="ew", padx=(6, 0), pady=5
        )

        config_actions = ttk.Frame(config_frame)
        config_actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for column in range(3):
            config_actions.columnconfigure(column, weight=1)
        ttk.Button(config_actions, text="Init Config", command=self.host_init_config).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(config_actions, text="Status", command=self.host_show_status).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(config_actions, text="Audit Log", command=self.host_show_audit).grid(
            row=0, column=2, sticky="ew", padx=(6, 0)
        )

        trust_frame = ttk.LabelFrame(parent, text="Trusted Devices", padding=12)
        trust_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        trust_frame.columnconfigure(0, weight=1)

        ttk.Button(trust_frame, text="List Trusted", command=self.host_list_trusted).grid(
            row=0, column=0, sticky="ew", pady=(0, 6)
        )
        ttk.Button(trust_frame, text="Remove Device", command=self.host_remove_trusted).grid(
            row=1, column=0, sticky="ew", pady=6
        )
        ttk.Button(trust_frame, text="Show Paths", command=self.host_show_paths).grid(
            row=2, column=0, sticky="ew", pady=(6, 0)
        )

        # Import trusted key section
        ttk.Separator(trust_frame, orient="horizontal").grid(row=3, column=0, sticky="ew", pady=(12, 8))
        ttk.Label(trust_frame, text="Import Public Key", font=("", 10, "bold")).grid(
            row=4, column=0, sticky="w", pady=(0, 4)
        )
        import_frame = ttk.Frame(trust_frame)
        import_frame.grid(row=5, column=0, sticky="ew", pady=(0, 6))
        import_frame.columnconfigure(1, weight=1)

        self.host_public_key_var = tk.StringVar(value="")
        ttk.Label(import_frame, text="File:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        ttk.Entry(import_frame, textvariable=self.host_public_key_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(import_frame, text="Browse", command=lambda: self._browse_open(self.host_public_key_var)).grid(
            row=0, column=2, sticky="ew", padx=(4, 0)
        )

        ttk.Label(import_frame, text="Expires (days):").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.host_expire_days_var = tk.StringVar(value="0")
        ttk.Spinbox(import_frame, from_=0, to=3650, textvariable=self.host_expire_days_var, width=6).grid(
            row=1, column=1, sticky="w", pady=(4, 0)
        )
        ttk.Label(import_frame, text="(0 = never)").grid(row=1, column=2, sticky="w", padx=(4, 0), pady=(4, 0))

        ttk.Button(import_frame, text="Import", command=self.host_import_trusted).grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0)
        )

        # ── Service state panel ──────────────────────────────────────────
        service_frame = ttk.LabelFrame(parent, text="Service State", padding=12)
        service_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        service_frame.columnconfigure(1, weight=1)

        self._service_widgets: dict[str, tk.Widget] = {}

        # Row 0: service name
        ttk.Label(service_frame, text="Service:").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 2))
        self._service_widgets["name"] = ttk.Label(
            service_frame, text=SERVICE_NAME, font=("", 10, "bold"))
        self._service_widgets["name"].grid(
            row=0, column=1, columnspan=2, sticky="w", pady=(0, 2))

        # Row 1: colored status dot + ActiveState label
        dot_frame = ttk.Frame(service_frame)
        dot_frame.grid(row=1, column=0, columnspan=3, sticky="w", pady=1)
        self._service_state_dot = tk.Label(dot_frame, text="●", font=("", 14),
                                           fg="gray")
        self._service_state_dot.pack(side="left", padx=(0, 4))
        self._service_widgets["active"] = ttk.Label(
            dot_frame, text="Active: unknown")
        self._service_widgets["active"].pack(side="left")

        # Row 2: SubState + LoadState
        info_frame = ttk.Frame(service_frame)
        info_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=1)
        self._service_widgets["substate"] = ttk.Label(
            info_frame, text="SubState: --")
        self._service_widgets["substate"].pack(side="left", padx=(0, 16))
        self._service_widgets["loadstate"] = ttk.Label(
            info_frame, text="LoadState: --")
        self._service_widgets["loadstate"].pack(side="left")

        # Row 3: MainPID + Uptime
        pid_frame = ttk.Frame(service_frame)
        pid_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=1)
        self._service_widgets["pid"] = ttk.Label(pid_frame, text="PID: --")
        self._service_widgets["pid"].pack(side="left", padx=(0, 16))
        self._service_widgets["uptime"] = ttk.Label(
            pid_frame, text="Uptime: --")
        self._service_widgets["uptime"].pack(side="left")

        # Row 4: State summary label
        self._service_widgets["state"] = ttk.Label(
            service_frame, text="State: unknown")
        self._service_widgets["state"].grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(1, 4))

        # Row 5: Start / Stop / Restart / Journal buttons
        btn_frame = ttk.Frame(service_frame)
        btn_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self._service_start_btn = ttk.Button(
            btn_frame, text="Start", command=self._service_start, width=8)
        self._service_start_btn.pack(side="left", padx=(0, 4))
        self._service_stop_btn = ttk.Button(
            btn_frame, text="Stop", command=self._service_stop, width=8)
        self._service_stop_btn.pack(side="left", padx=4)
        self._service_restart_btn = ttk.Button(
            btn_frame, text="Restart", command=self._service_restart, width=8)
        self._service_restart_btn.pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Journal", command=self._service_journal,
                   width=10).pack(side="left", padx=(4, 0))

        # ── SeeOnDesk info panel ─────────────────────────────────────────
        seeondesk_frame = ttk.LabelFrame(parent, text="SeeOnDesk", padding=12)
        seeondesk_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        seeondesk_frame.columnconfigure(1, weight=1)

        self._seeondesk_workspace_var = tk.StringVar(value="Workspace: --")
        self._seeondesk_processes_var = tk.StringVar(value="Processes: --")

        ttk.Label(seeondesk_frame, textvariable=self._seeondesk_workspace_var).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(seeondesk_frame, textvariable=self._seeondesk_processes_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))

        seeondesk_actions = ttk.Frame(seeondesk_frame)
        seeondesk_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        seeondesk_actions.columnconfigure(0, weight=1)
        seeondesk_actions.columnconfigure(1, weight=1)
        ttk.Button(seeondesk_actions, text="Refresh SeeOnDesk", command=self._seeondesk_refresh).grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        self._seeondesk_available = True

        # ── Output frame ─────────────────────────────────────────────────
        output_frame = ttk.LabelFrame(parent, text="Host Output", padding=12)
        output_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.host_output_text = tk.Text(output_frame, wrap="word", height=18)
        self.host_output_text.grid(row=0, column=0, sticky="nsew")

        # Start polling
        self._poll_service_state()
        self._poll_seeondesk()

    def _build_vsee_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        controls.columnconfigure(0, weight=1)
        controls.rowconfigure(1, weight=1)
        controls.rowconfigure(3, weight=1)

        ttk.Label(controls, text="Points").grid(row=0, column=0, sticky="w")
        self.vsee_points_text = tk.Text(controls, wrap="none", height=9)
        self.vsee_points_text.grid(row=1, column=0, sticky="nsew", pady=(4, 10))

        ttk.Label(controls, text="Edges").grid(row=2, column=0, sticky="w")
        self.vsee_edges_text = tk.Text(controls, wrap="none", height=9)
        self.vsee_edges_text.grid(row=3, column=0, sticky="nsew", pady=(4, 10))

        sliders = ttk.Frame(controls)
        sliders.grid(row=4, column=0, sticky="ew")
        sliders.columnconfigure(1, weight=1)

        self.vsee_rotation_x_var = tk.DoubleVar(value=20.0)
        self.vsee_rotation_y_var = tk.DoubleVar(value=-30.0)
        self.vsee_scale_var = tk.DoubleVar(value=130.0)
        self._add_vsee_slider(sliders, 0, "Rotate X", self.vsee_rotation_x_var, -180.0, 180.0)
        self._add_vsee_slider(sliders, 1, "Rotate Y", self.vsee_rotation_y_var, -180.0, 180.0)
        self._add_vsee_slider(sliders, 2, "Scale", self.vsee_scale_var, 40.0, 260.0)

        actions = ttk.Frame(controls)
        actions.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text="Render", command=self.vsee_render).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Load Cube", command=self.vsee_load_sample).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        viewer = ttk.Frame(parent)
        viewer.grid(row=0, column=1, sticky="nsew")
        viewer.columnconfigure(0, weight=1)
        viewer.rowconfigure(0, weight=1)

        self.vsee_canvas = tk.Canvas(viewer, background="#05070a", highlightthickness=0)
        self.vsee_canvas.grid(row=0, column=0, sticky="nsew")
        self.vsee_canvas.bind("<Configure>", self.vsee_render_event)

        self.vsee_load_sample()

    def _add_vsee_slider(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.DoubleVar,
        from_value: float,
        to_value: float,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        slider = ttk.Scale(
            parent,
            from_=from_value,
            to=to_value,
            variable=variable,
            command=lambda _value: self.vsee_render(),
        )
        slider.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=4)

    def _build_voice_tab(self, parent: ttk.Frame) -> None:
        """Build the Voice Control tab with wake word, push-to-talk, and feedback controls."""
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # ── Wake Word Engine ────────────────────────────────────────────
        wake_frame = ttk.LabelFrame(parent, text="Voice Control", padding=12)
        wake_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        wake_frame.columnconfigure(1, weight=1)

        # Status indicator
        ttk.Label(wake_frame, text="Wake Word Engine:").grid(row=0, column=0, sticky="w", pady=5)
        self.voice_wake_status_var = tk.StringVar(value="Checking...")
        ttk.Label(wake_frame, textvariable=self.voice_wake_status_var, font=("", 10, "bold")).grid(
            row=0, column=1, sticky="w", pady=5
        )

        # Wake word entry
        ttk.Label(wake_frame, text="Wake Word:").grid(row=1, column=0, sticky="w", pady=5)
        self.voice_wake_word_var = tk.StringVar(value="fiona")
        ttk.Entry(wake_frame, textvariable=self.voice_wake_word_var).grid(
            row=1, column=1, sticky="ew", pady=5
        )

        # Start/Stop toggle
        self.voice_listening_var = tk.StringVar(value="Start Listening")
        self.voice_listening_button = ttk.Button(
            wake_frame,
            textvariable=self.voice_listening_var,
            command=self._voice_toggle_listening,
        )
        self.voice_listening_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # Manual trigger button
        self.voice_trigger_button = ttk.Button(
            wake_frame, text="Hey Fiona (Manual Trigger)", command=self._voice_manual_trigger
        )
        self.voice_trigger_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # Status text
        self.voice_wake_detail_var = tk.StringVar(value="")
        ttk.Label(wake_frame, textvariable=self.voice_wake_detail_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

        # ── Feedback ────────────────────────────────────────────────────
        feedback_frame = ttk.LabelFrame(parent, text="Feedback", padding=12)
        feedback_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        feedback_frame.columnconfigure(0, weight=1)

        ttk.Label(feedback_frame, text="Test Sounds").grid(row=0, column=0, sticky="w", pady=(0, 6))

        sound_buttons = ttk.Frame(feedback_frame)
        sound_buttons.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for column in range(3):
            sound_buttons.columnconfigure(column, weight=1)
        ttk.Button(
            sound_buttons, text="Play Ack", command=lambda: self._voice_play_sound("ack")
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            sound_buttons, text="Play Error", command=lambda: self._voice_play_sound("error")
        ).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(
            sound_buttons, text="Play Success", command=lambda: self._voice_play_sound("success")
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        ttk.Separator(feedback_frame, orient="horizontal").grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # Notification test
        ttk.Label(feedback_frame, text="Test Notification").grid(row=3, column=0, sticky="w", pady=(0, 6))

        notify_frame = ttk.Frame(feedback_frame)
        notify_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        notify_frame.columnconfigure(1, weight=1)

        ttk.Label(notify_frame, text="Message:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.voice_notify_msg_var = tk.StringVar(value="Fiona notification test")
        ttk.Entry(notify_frame, textvariable=self.voice_notify_msg_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 4)
        )
        ttk.Button(notify_frame, text="Send", command=self._voice_send_notification).grid(
            row=0, column=2, sticky="ew"
        )

        # Urgency selector
        urgency_frame = ttk.Frame(feedback_frame)
        urgency_frame.grid(row=5, column=0, sticky="ew")
        ttk.Label(urgency_frame, text="Urgency:").pack(side="left", padx=(0, 6))
        self.voice_urgency_var = tk.StringVar(value="normal")
        urgency_menu = ttk.Combobox(
            urgency_frame,
            textvariable=self.voice_urgency_var,
            values=["low", "normal", "critical"],
            state="readonly",
            width=10,
        )
        urgency_menu.pack(side="left")
        ttk.Label(urgency_frame, text="  Sound Dir:").pack(side="left", padx=(12, 4))
        self.voice_sound_dir_var = tk.StringVar(value="")
        ttk.Label(urgency_frame, textvariable=self.voice_sound_dir_var).pack(side="left")

        # ── Push to Talk ────────────────────────────────────────────────
        ptt_frame = ttk.LabelFrame(parent, text="Push to Talk", padding=12)
        ptt_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ptt_frame.columnconfigure(1, weight=1)

        ttk.Label(ptt_frame, text="Status:").grid(row=0, column=0, sticky="w", pady=5)
        self.voice_ptt_status_var = tk.StringVar(value="Checking...")
        ttk.Label(ptt_frame, textvariable=self.voice_ptt_status_var, font=("", 10, "bold")).grid(
            row=0, column=1, sticky="w", pady=5
        )

        ttk.Label(ptt_frame, text="Hotkey:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Label(ptt_frame, text="Ctrl+Space").grid(row=1, column=1, sticky="w", pady=5)

        self.voice_ptt_button_var = tk.StringVar(value="Start Listener")
        self.voice_ptt_button = ttk.Button(
            ptt_frame,
            textvariable=self.voice_ptt_button_var,
            command=self._voice_toggle_ptt,
        )
        self.voice_ptt_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # Initialize voice subsystem
        self._voice_init()

    def _voice_init(self) -> None:
        """Initialize voice module components with graceful degradation."""
        self._voice_engine = None
        self._voice_ptt = None
        self._voice_feedback = None
        self._voice_listening = False
        self._voice_ptt_running = False

        # Initialize wake word engine
        try:
            from Voice import WakeWordEngine
            self._voice_engine = WakeWordEngine()
            if self._voice_engine.available:
                self.voice_wake_status_var.set("Available")
                self.voice_wake_detail_var.set(
                    f"Backend: {self._voice_engine._backend}"
                )
            else:
                self.voice_wake_status_var.set("Unavailable")
                self.voice_wake_detail_var.set(
                    "No detection library installed (pvporcupine/snowboy)"
                )
        except Exception:
            self.voice_wake_status_var.set("Error")
            self.voice_wake_detail_var.set("Failed to initialize")

        # Initialize push-to-talk
        try:
            from Voice import PushToTalk
            self._voice_ptt = PushToTalk()
            if self._voice_ptt.available:
                self.voice_ptt_status_var.set("Available")
            else:
                self.voice_ptt_status_var.set("Unavailable (pynput not found)")
        except Exception:
            self.voice_ptt_status_var.set("Error")

        # Initialize feedback engine
        try:
            from Voice import FeedbackEngine
            self._voice_feedback = FeedbackEngine()
            self.voice_sound_dir_var.set(str(self._voice_feedback.sound_dir))
        except Exception:
            self.voice_sound_dir_var.set("(error)")

    def _voice_toggle_listening(self) -> None:
        """Toggle wake word engine listening state."""
        if self._voice_engine is None:
            return
        if self._voice_listening:
            self._voice_engine.stop()
            self._voice_listening = False
            self.voice_listening_var.set("Start Listening")
            self.voice_listening_button.configure(text="Start Listening")
        else:
            # Update wake word from entry
            wake_word = self.voice_wake_word_var.get().strip().lower()
            if not wake_word:
                wake_word = "fiona"
            self._voice_engine.wake_word = wake_word
            self._voice_engine.start()
            self._voice_listening = True
            self.voice_listening_var.set("Stop Listening")
            self.voice_listening_button.configure(text="Stop Listening")

    def _voice_manual_trigger(self) -> None:
        """Manually trigger the wake event."""
        if self._voice_engine is not None:
            self._voice_engine.trigger()
        # Provide visual feedback
        if self._voice_feedback is not None:
            self._voice_feedback.acknowledge()

    def _voice_play_sound(self, sound_name: str) -> None:
        """Play a test sound through the feedback engine."""
        if self._voice_feedback is not None:
            ok = self._voice_feedback.play_sound(sound_name)
            if ok:
                self.status_var.set(f"Played sound: {sound_name}")
            else:
                self.status_var.set(f"Sound not found: {sound_name} (check sound dir)")
        else:
            self.status_var.set("Feedback engine not available")

    def _voice_send_notification(self) -> None:
        """Send a test desktop notification."""
        if self._voice_feedback is not None:
            msg = self.voice_notify_msg_var.get().strip()
            urgency = self.voice_urgency_var.get()
            ok = self._voice_feedback.notify("Fiona", msg, urgency=urgency)
            if ok:
                self.status_var.set(f"Notification sent (urgency: {urgency})")
            else:
                self.status_var.set("notify-send not available")
        else:
            self.status_var.set("Feedback engine not available")

    def _voice_toggle_ptt(self) -> None:
        """Toggle push-to-talk listener."""
        if self._voice_ptt is None:
            return
        if self._voice_ptt_running:
            self._voice_ptt.stop()
            self._voice_ptt_running = False
            self.voice_ptt_button_var.set("Start Listener")
            self.voice_ptt_button.configure(text="Start Listener")
        else:
            self._voice_ptt.start()
            self._voice_ptt_running = True
            self.voice_ptt_button_var.set("Stop Listener")
            self.voice_ptt_button.configure(text="Stop Listener")

    def _build_debug_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=3)
        parent.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(1, weight=1)

        self.debug_path_var = tk.StringVar(value="")
        ttk.Button(toolbar, text="Refresh", command=self.debug_refresh_files).grid(row=0, column=0, sticky="w")
        ttk.Entry(toolbar, textvariable=self.debug_path_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(toolbar, text="Load", command=self.debug_load_selected).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(toolbar, text="Save", command=self.debug_save_current).grid(row=0, column=3)

        left = ttk.Frame(parent)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.debug_tree = ttk.Treeview(left, show="tree")
        self.debug_tree.grid(row=0, column=0, sticky="nsew")
        self.debug_tree.bind("<<TreeviewSelect>>", self.debug_on_tree_select)
        self.debug_tree_index: dict[str, Path] = {}

        right = ttk.Frame(parent)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.debug_text = tk.Text(right, wrap="none", undo=True)
        self.debug_text.grid(row=0, column=0, sticky="nsew")

        self.debug_refresh_files()

    def _load(self) -> None:
        self.config = load_config(self.config_path)
        self._refresh_tree()
        self._refresh_json_text()
        self._clear_form()
        self.status_var.set(f"Loaded {self.config_path}")

    def _refresh_tree(self) -> None:
        self.binding_tree.delete(*self.binding_tree.get_children())
        self.tree_index.clear()
        for app_index, app in enumerate(self.config.get("apps", [])):
            app_id = self.binding_tree.insert("", tk.END, text=app["name"], open=True)
            self.tree_index[app_id] = {"kind": "app", "app_index": app_index}

            launch = app.get("launch", {})
            launch_keys = " + ".join(launch.get("keys", []))
            launch_id = self.binding_tree.insert(app_id, tk.END, text=f"Launch [{launch_keys}]")
            self.tree_index[launch_id] = {
                "kind": "launch",
                "app_index": app_index,
            }

            for shortcut_index, shortcut in enumerate(app.get("shortcuts", [])):
                shortcut_keys = " + ".join(shortcut.get("keys", []))
                shortcut_id = self.binding_tree.insert(
                    app_id,
                    tk.END,
                    text=f"{shortcut.get('name', 'shortcut')} [{shortcut_keys}]",
                )
                self.tree_index[shortcut_id] = {
                    "kind": "shortcut",
                    "app_index": app_index,
                    "shortcut_index": shortcut_index,
                }

    def _refresh_json_text(self) -> None:
        self.json_text.delete("1.0", tk.END)
        self.json_text.insert("1.0", json.dumps(self.config, indent=2))

    def _clear_form(self) -> None:
        self.app_name_var.set("")
        self.window_match_var.set("")
        self.binding_name_var.set("")
        self.keys_var.set("")
        self.command_var.set("")
        self.instruction_var.set("")
        self.fiona_cmds_var.set("")
        self.cooldown_var.set("0.8")

    def _selected_item(self) -> tuple[str | None, dict | None]:
        selection = self.binding_tree.selection()
        if not selection:
            return None, None
        item_id = selection[0]
        return item_id, self.tree_index.get(item_id)

    def on_tree_select(self, _event: object) -> None:
        _item_id, info = self._selected_item()
        if info is None:
            return

        app = self.config["apps"][info["app_index"]]
        self.app_name_var.set(app.get("name", ""))
        self.window_match_var.set(app.get("window_match", ""))

        if info["kind"] == "app":
            self.binding_name_var.set("")
            self.keys_var.set("")
            self.command_var.set("")
            self.instruction_var.set("")
            self.fiona_cmds_var.set("")
            self.cooldown_var.set("0.8")
            return

        binding = app["launch"] if info["kind"] == "launch" else app["shortcuts"][info["shortcut_index"]]
        self.binding_name_var.set(binding.get("name", ""))
        self.keys_var.set(", ".join(binding.get("keys", [])))
        self.command_var.set(binding.get("cmd", ""))
        self.instruction_var.set(binding.get("instruction", ""))
        self.fiona_cmds_var.set(", ".join(binding.get("fiona_cmds", binding.get("quiktieper_cmds", []))))
        self.cooldown_var.set(str(binding.get("cooldown_seconds", 0.8)))

    def add_app(self) -> None:
        app = {
            "name": "new-app",
            "window_match": "",
            "launch": {
                "name": "launch",
                "keys": ["alt"],
                "cmd": "",
                "instruction": "",
                "fiona_cmds": [],
                "cooldown_seconds": 0.8,
            },
            "shortcuts": [],
        }
        self.config.setdefault("apps", []).append(app)
        self._refresh_tree()
        self._refresh_json_text()
        self.status_var.set("Added app")

    def add_shortcut(self) -> None:
        _item_id, info = self._selected_item()
        if info is None:
            messagebox.showwarning("No selection", "Select an app or one of its bindings first.")
            return

        app = self.config["apps"][info["app_index"]]
        app.setdefault("shortcuts", []).append(
            {
                "name": "new-shortcut",
                "keys": ["alt"],
                "cmd": "",
                "instruction": "",
                "fiona_cmds": [],
                "cooldown_seconds": 0.8,
            }
        )
        self._refresh_tree()
        self._refresh_json_text()
        self.status_var.set(f"Added shortcut under {app['name']}")

    def delete_selected(self) -> None:
        _item_id, info = self._selected_item()
        if info is None:
            messagebox.showwarning("No selection", "Select an app or shortcut to delete.")
            return

        if info["kind"] == "app":
            del self.config["apps"][info["app_index"]]
        elif info["kind"] == "shortcut":
            del self.config["apps"][info["app_index"]]["shortcuts"][info["shortcut_index"]]
        else:
            messagebox.showwarning("Protected binding", "Each app must keep its Launch binding.")
            return

        self._refresh_tree()
        self._refresh_json_text()
        self._clear_form()
        self.status_var.set("Deleted selection")

    def save_selected(self) -> None:
        _item_id, info = self._selected_item()
        if info is None:
            messagebox.showwarning("No selection", "Select an app or binding to save.")
            return

        app = self.config["apps"][info["app_index"]]
        app_name = self.app_name_var.get().strip()
        window_match = self.window_match_var.get().strip().lower()
        if not app_name:
            messagebox.showerror("Missing app name", "App name is required.")
            return

        app["name"] = app_name
        app["window_match"] = window_match

        if info["kind"] != "app":
            binding = self._binding_from_form()
            if binding is None:
                return
            if info["kind"] == "launch":
                app["launch"] = binding
            else:
                app["shortcuts"][info["shortcut_index"]] = binding

        self._refresh_tree()
        self._refresh_json_text()
        self.status_var.set("Saved selection into editor state")

    def validate_json(self) -> None:
        try:
            json.loads(self.json_text.get("1.0", tk.END))
        except json.JSONDecodeError as exc:
            messagebox.showerror("Invalid JSON", str(exc))
            return
        messagebox.showinfo("Valid JSON", "The raw JSON tab is valid.")

    def save_all(self) -> None:
        selected_tab = self.notebook.tab(self.notebook.select(), "text")
        if selected_tab == "Bindings":
            if self.binding_tree.selection():
                self.save_selected()
            parsed = self.config
        elif selected_tab == "Raw Json":
            try:
                parsed = json.loads(self.json_text.get("1.0", tk.END))
            except json.JSONDecodeError as exc:
                messagebox.showerror("Invalid JSON", f"Fix the raw JSON first.\n\n{exc}")
                return
        else:
            parsed = self.config

        save_config(parsed, self.config_path)
        self.config = load_config(self.config_path)
        self._refresh_tree()
        self._refresh_json_text()
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
            from QuikTieper.listener import ChordListener
        except Exception as exc:
            messagebox.showerror("Listener error", f"Could not import keyboard hook.\n\n{exc}")
            return

        try:
            bindings = parse_bindings(self.config.get("apps", []))
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

    def _binding_from_form(self) -> dict | None:
        name = self.binding_name_var.get().strip()
        command = self.command_var.get().strip()
        instruction = self.instruction_var.get().strip()
        fiona_cmds = [item.strip() for item in self.fiona_cmds_var.get().split(",") if item.strip()]
        keys = [key.strip().lower() for key in self.keys_var.get().split(",") if key.strip()]
        cooldown_text = self.cooldown_var.get().strip()

        if not name or not keys:
            messagebox.showerror("Missing fields", "Binding name and keys are required.")
            return None

        if not command and not instruction and not fiona_cmds:
            messagebox.showerror(
                "Missing action",
                "Provide at least one of Run Command, Instruction, or Fiona Cmds.",
            )
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
            "instruction": instruction,
            "fiona_cmds": fiona_cmds,
            "cooldown_seconds": cooldown_seconds,
        }

    def capture_mouse_position(self) -> None:
        position = get_mouse_location()
        if position is None:
            messagebox.showerror("Mouse capture failed", "Could not read the current mouse position from xdotool.")
            return
        x_pos, y_pos = position
        self.instruction_var.set(f"mouse:{x_pos},{y_pos}")
        self.status_var.set(f"Captured mouse position {x_pos},{y_pos}")

    def capture_mouse_position_hotkey(self, _event: tk.Event[tk.Misc]) -> str:
        self.capture_mouse_position()
        return "break"

    def clear_instruction(self) -> None:
        self.instruction_var.set("")
        self.status_var.set("Cleared instruction")

    def camcoms_generate_identity(self) -> None:
        identity = CamComsIdentity.generate(self.cam_device_id_var.get().strip() or None)
        private_path = self.cam_private_out_var.get().strip()
        public_path = self.cam_public_out_var.get().strip()
        private_data = identity.to_private_dict()
        public_data = identity.public_bundle.to_dict()

        if private_path:
            self._write_json_path(private_path, private_data)
        if public_path:
            self._write_json_path(public_path, public_data)

        output = {
            "private": private_data,
            "public": public_data,
        }
        self._set_camcoms_output(json.dumps(output, indent=2, sort_keys=True))
        self.status_var.set(f"Generated CamComs identity {identity.device_id}")

    def camcoms_export_public(self) -> None:
        private_path = self.cam_private_in_var.get().strip()
        if not private_path:
            messagebox.showerror("Missing private key", "Choose a private identity file first.")
            return

        identity = CamComsIdentity.from_private_dict(self._read_json_path(private_path))
        public_data = identity.public_bundle.to_dict()
        public_path = self.cam_public_out_var.get().strip()
        if public_path:
            self._write_json_path(public_path, public_data)
        self._set_camcoms_output(json.dumps(public_data, indent=2, sort_keys=True))
        self.status_var.set(f"Exported public keys for {identity.device_id}")

    def camcoms_encrypt(self) -> None:
        sender_private = self.cam_sender_private_var.get().strip()
        recipient_public = self.cam_recipient_public_var.get().strip()
        message = self.cam_message_var.get()
        if not sender_private or not recipient_public:
            messagebox.showerror("Missing keys", "Choose sender private and recipient public key files.")
            return
        if not message:
            messagebox.showerror("Missing message", "Enter a message to encrypt.")
            return

        sender = CamComsIdentity.from_private_dict(self._read_json_path(sender_private))
        recipient = PublicKeyBundle.from_dict(self._read_json_path(recipient_public))
        instruction_text = instruction_to_text(instruction_from_text(message))
        envelope = encrypt_message(instruction_text, sender=sender, recipient=recipient)
        output = json.dumps(envelope, indent=2, sort_keys=True) if self.cam_json_output_var.get() else encode_envelope(envelope)
        self._set_camcoms_output(output)
        self.status_var.set(f"Encrypted message from {sender.device_id} to {recipient.device_id}")

    def camcoms_decrypt(self) -> None:
        recipient_private = self.cam_recipient_private_var.get().strip()
        if not recipient_private:
            messagebox.showerror("Missing recipient key", "Choose the host recipient private key file.")
            return

        raw_input = self._get_camcoms_output().strip() or self.cam_message_var.get().strip()
        if not raw_input:
            messagebox.showerror("Missing encrypted message", "Put an encoded envelope in output or message first.")
            return

        recipient = CamComsIdentity.from_private_dict(self._read_json_path(recipient_private))
        sender_public_path = self.cam_sender_public_var.get().strip()
        expected_sender = PublicKeyBundle.from_dict(self._read_json_path(sender_public_path)) if sender_public_path else None
        envelope = self._parse_camcoms_envelope(raw_input)
        plaintext = decrypt_text(envelope, recipient=recipient, expected_sender=expected_sender)
        self._set_camcoms_output(plaintext)
        self.status_var.set(f"Decrypted message for {recipient.device_id}")

    def camcoms_send(self) -> None:
        encoded = self._get_camcoms_output().strip() or self.cam_message_var.get().strip()
        if not encoded:
            messagebox.showerror("Missing encoded message", "Put an encoded envelope in output or message first.")
            return
        if encoded.startswith("{"):
            encoded = encode_envelope(json.loads(encoded))

        try:
            port = int(self.cam_port_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid port", "Port must be an integer.")
            return

        client = CamComsHttpClient(
            host=self.cam_host_var.get().strip(),
            port=port,
            path=self.cam_path_var.get().strip() or "/",
        )
        response = client.send_encoded(encoded)
        self._set_camcoms_output(response)
        self.status_var.set(f"Sent CamComs message to {client.url}")

    def camcoms_smoke_test(self) -> None:
        esp32_sender = CamComsIdentity.generate("esp32")
        host_receiver = CamComsIdentity.generate("host")
        instruction_text = instruction_to_text(press_instruction(["alt", "s"]))
        envelope = encrypt_message(instruction_text, sender=esp32_sender, recipient=host_receiver.public_bundle)
        plaintext = decrypt_text(envelope, recipient=host_receiver, expected_sender=esp32_sender.public_bundle)
        self._set_camcoms_output(plaintext)
        self.status_var.set("CamComs smoke test passed")

    def camcoms_use_output_as_message(self) -> None:
        self.cam_message_var.set(self._get_camcoms_output().strip())
        self.status_var.set("Copied CamComs output into message field")

    def camcoms_clear_output(self) -> None:
        self._set_camcoms_output("")
        self.status_var.set("Cleared CamComs output")

    def _update_fingerprint_display(self) -> None:
        """Reload fingerprint from identity.json and update the display."""
        identity = load_identity(DEFAULT_IDENTITY_PATH)
        self.cam_fingerprint_var.set(get_fingerprint(identity))

    def _camcoms_rotate_keys(self) -> None:
        """Rotate keys after confirmation."""
        if not messagebox.askyesno(
            "Rotate Keys",
            "Rotating keys will break all existing paired connections. Continue?",
        ):
            return
        try:
            old_fp, new_fp = rotate_keys()
            self._update_fingerprint_display()
            self._set_camcoms_output(
                f"Old fingerprint: {old_fp}\n"
                f"New fingerprint: {new_fp}\n"
                "Keys rotated. Existing trusted senders will need to re-pair "
                "using the new public key.\n"
            )
            self.status_var.set(f"Keys rotated: {old_fp} → {new_fp}")
        except Exception as exc:
            self._set_camcoms_output(f"Key rotation failed: {exc}\n")
            self.status_var.set(f"Key rotation error: {exc}")

    def _camcoms_prune_trust(self) -> None:
        """Remove expired trust entries and report count."""
        try:
            removed = prune_expired(DEFAULT_TRUSTED_DIR)
            count = len(removed)
            if count > 0:
                msg = f"Removed {count} expired trust entr{'y' if count == 1 else 'ies'}"
                self._set_camcoms_output(
                    f"{msg}:\n  " + "\n  ".join(removed) + "\n"
                )
            else:
                msg = "No expired trust entries found."
                self._set_camcoms_output(msg + "\n")
            self.status_var.set(msg)
        except Exception as exc:
            self._set_camcoms_output(f"Prune failed: {exc}\n")
            self.status_var.set(f"Prune error: {exc}")

    def host_init_config(self) -> None:
        path = Path(self.host_config_path_var.get().strip() or DEFAULT_FIONA_CONFIG_PATH)
        written = save_host_service_config(default_host_service_config(), path)
        self._set_host_output(json.dumps({"config": str(written)}, indent=2, sort_keys=True))
        self.status_var.set(f"Wrote host config {written}")

    def host_show_status(self) -> None:
        service = HostService.load(Path(self.host_config_path_var.get().strip() or DEFAULT_FIONA_CONFIG_PATH))
        self._set_host_output(json.dumps(service.status(check_port=True), indent=2, sort_keys=True))
        self.status_var.set("Loaded Fiona host status")

    def host_show_audit(self) -> None:
        self._set_host_output(
            json.dumps(
                {"path": str(DEFAULT_AUDIT_LOG_PATH), "events": AuditLog(DEFAULT_AUDIT_LOG_PATH).read_recent(50)},
                indent=2,
                sort_keys=True,
            )
        )
        self.status_var.set("Loaded CamComs audit log")

    def host_list_trusted(self) -> None:
        senders = [trusted.to_dict() for trusted in list_trusted_senders(DEFAULT_TRUSTED_DIR)]
        self._set_host_output(
            json.dumps({"trusted_dir": str(DEFAULT_TRUSTED_DIR), "senders": senders}, indent=2, sort_keys=True)
        )
        self.status_var.set("Loaded trusted sender list")

    def host_remove_trusted(self) -> None:
        device_id = self.host_trusted_device_var.get().strip()
        if not device_id:
            messagebox.showerror("Missing device", "Device ID is required.")
            return
        removed = remove_trusted_sender(device_id, DEFAULT_TRUSTED_DIR)
        self._set_host_output(json.dumps({"device_id": device_id, "removed": removed}, indent=2, sort_keys=True))
        self.status_var.set(f"Removed trusted device {device_id}" if removed else f"No trusted device {device_id}")

    def host_show_paths(self) -> None:
        self._set_host_output(
            json.dumps(
                {
                    "config": str(DEFAULT_FIONA_CONFIG_PATH),
                    "audit_log": str(DEFAULT_AUDIT_LOG_PATH),
                    "trusted_dir": str(DEFAULT_TRUSTED_DIR),
                    "host_private": str(private_key_path("host")),
                    "host_public": str(public_key_path("host")),
                    "esp32_public": str(public_key_path("esp32")),
                },
                indent=2,
                sort_keys=True,
            )
        )
        self.status_var.set("Loaded host paths")

    def host_import_trusted(self) -> None:
        raw_path = self.host_public_key_var.get().strip()
        if not raw_path:
            messagebox.showerror("Missing file", "Select a public key JSON file first.")
            return
        path = Path(raw_path)
        if not path.exists():
            messagebox.showerror("File not found", f"Public key file not found: {path}")
            return
        bundle = PublicKeyBundle.from_dict(self._read_json_path(str(path)))
        days_text = self.host_expire_days_var.get().strip()
        try:
            days = int(days_text)
        except ValueError:
            days = 0
        import time
        expires_at: int | None = None
        if days > 0:
            expires_at = int(time.time()) + days * 86400
        saved = save_trusted_sender(bundle, DEFAULT_TRUSTED_DIR, expires_at=expires_at)
        self._set_host_output(
            json.dumps(
                {
                    "device_id": bundle.device_id,
                    "path": str(saved),
                    "expires_at": expires_at,
                },
                indent=2,
                sort_keys=True,
            )
        )
        self.status_var.set(f"Imported {bundle.device_id} as trusted")

    # ── Service state systemd helpers ──────────────────────────────────

    def _service_state_color(self, active_state: str) -> str:
        """Return a hex colour for the status dot based on ActiveState."""
        state_map = {
            "active": "#00cc66",
            "activating": "#ffcc00",
            "deactivating": "#ffcc00",
            "reloading": "#ffcc00",
            "failed": "#ff3333",
            "inactive": "#999999",
        }
        return state_map.get(active_state, "#999999")

    def _service_state_label(self, active_state: str, sub_state: str) -> str:
        """Return a human-readable state string."""
        if not active_state or active_state == "unknown":
            return "State: unknown"
        return f"State: {active_state}/{sub_state}"

    def _poll_service_state(self) -> None:
        """Poll systemd service state and update the display."""
        if not self._service_systemd_available:
            return

        state = _get_service_state(SERVICE_NAME)

        if "error" in state:
            err = state["error"]
            # FileNotFoundError means systemctl is not present
            if "No such file or directory" in err or "not found" in err.lower():
                self._service_systemd_available = False
                for widget in self._service_widgets.values():
                    widget.configure(text="systemd not available")
                self._service_state_dot.configure(fg="gray", text="●")
                self._service_start_btn.configure(state="disabled")
                self._service_stop_btn.configure(state="disabled")
                self._service_restart_btn.configure(state="disabled")
                return
            # Transient error — update label and keep polling
            self._service_widgets["state"].configure(text=f"State: error — {err}")
            self._service_state_dot.configure(fg="#ff3333")
        else:
            active = state.get("ActiveState", "unknown")
            sub = state.get("SubState", "unknown")
            load = state.get("LoadState", "unknown")
            pid = state.get("MainPID", "")
            uptime = state.get("Uptime", "unknown")

            # Update dot colour
            self._service_state_dot.configure(
                fg=self._service_state_color(active))

            # Update labels
            self._service_widgets["active"].configure(
                text=f"Active: {active}")
            self._service_widgets["substate"].configure(
                text=f"SubState: {sub}")
            self._service_widgets["loadstate"].configure(
                text=f"LoadState: {load}")
            pid_text = f"PID: {pid}" if pid and pid != "0" else "PID: --"
            self._service_widgets["pid"].configure(text=pid_text)
            self._service_widgets["uptime"].configure(
                text=f"Uptime: {uptime}")
            self._service_widgets["state"].configure(
                text=self._service_state_label(active, sub))

            # Enable/disable buttons based on state
            if active == "active":
                self._service_start_btn.configure(state="disabled")
                self._service_stop_btn.configure(state="normal")
                self._service_restart_btn.configure(state="normal")
            elif active == "inactive":
                self._service_start_btn.configure(state="normal")
                self._service_stop_btn.configure(state="disabled")
                self._service_restart_btn.configure(state="disabled")
            else:
                self._service_start_btn.configure(state="disabled")
                self._service_stop_btn.configure(state="disabled")
                self._service_restart_btn.configure(state="disabled")

        # Schedule next poll (3 s)
        self._service_poll_id = self.root.after(3000, self._poll_service_state)

    def _seeondesk_refresh(self) -> None:
        """Refresh SeeOnDesk workspace and process info with graceful degradation."""
        if not self._seeondesk_available:
            return
        # Workspace info
        try:
            from SeeOnDesk.workspace_watcher import WorkspaceWatcher
            watcher = WorkspaceWatcher()
            active = watcher.get_active_workspace()
            if active:
                self._seeondesk_workspace_var.set(
                    f"Workspace: {active.name} (id={active.id})"
                )
            else:
                self._seeondesk_workspace_var.set(
                    "Workspace: (no workspace info available)"
                )
        except Exception:
            self._seeondesk_workspace_var.set("Workspace: unavailable")
            self._seeondesk_available = False

        # Process info
        try:
            from SeeOnDesk.process_tracker import ProcessTracker
            tracker = ProcessTracker()
            processes = tracker.list_processes()
            # Show top process names by occurrence count
            from collections import Counter
            name_counts = Counter(p.name for p in processes)
            top_names = [name for name, _count in name_counts.most_common(5)]
            if top_names:
                self._seeondesk_processes_var.set(
                    f"Processes: {', '.join(top_names)}"
                )
            else:
                self._seeondesk_processes_var.set("Processes: (none detected)")
        except Exception:
            self._seeondesk_processes_var.set("Processes: unavailable")
            self._seeondesk_available = False

    def _poll_seeondesk(self) -> None:
        """Poll SeeOnDesk info every 5 seconds."""
        self._seeondesk_refresh()
        self._seeondesk_poll_id = self.root.after(5000, self._poll_seeondesk)

    def _run_systemctl(self, action: str, success_msg: str) -> None:
        """Run a systemctl --user action and show output."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", action, SERVICE_NAME],
                capture_output=True, text=True, timeout=30.0,
            )
            if result.returncode == 0:
                self._set_host_output(
                    f"systemctl {action} {SERVICE_NAME} — success\n\n"
                    + (result.stdout.strip() or ""))
                self.status_var.set(success_msg)
            else:
                error = result.stderr.strip() or result.stdout.strip() or "unknown error"
                self._set_host_output(
                    f"systemctl {action} {SERVICE_NAME} — FAILED\n\n{error}")
                self.status_var.set(f"systemctl {action} failed")
        except FileNotFoundError:
            self._set_host_output("systemd not available — systemctl not found")
            self.status_var.set("systemd not available")
            self._service_systemd_available = False
        except subprocess.TimeoutExpired:
            self._set_host_output(
                f"systemctl {action} {SERVICE_NAME} — timed out after 30 s")
            self.status_var.set(f"systemctl {action} timed out")

    def _service_start(self) -> None:
        self._run_systemctl("start", "Service start command issued")

    def _service_stop(self) -> None:
        self._run_systemctl("stop", "Service stop command issued")

    def _service_restart(self) -> None:
        self._run_systemctl("restart", "Service restart command issued")

    def _service_journal(self) -> None:
        """Fetch recent journalctl logs for the service and show in output."""
        try:
            result = subprocess.run(
                ["journalctl", "--user", "--unit", SERVICE_NAME,
                 "--since", "1 hour ago", "--no-pager", "-n", "100"],
                capture_output=True, text=True, timeout=10.0,
            )
            if result.returncode == 0:
                log = result.stdout.strip() or "(empty log)"
                self._set_host_output(f"Journal — last 100 lines (1 h)\n\n{log}")
                self.status_var.set("Loaded journalctl output")
            else:
                self._set_host_output(
                    f"journalctl exited with code {result.returncode}\n\n"
                    + (result.stderr.strip() or result.stdout.strip() or ""))
                self.status_var.set("journalctl failed")
        except FileNotFoundError:
            self._set_host_output("journalctl not available on this system")
            self.status_var.set("journalctl not available")
        except subprocess.TimeoutExpired:
            self._set_host_output("journalctl — timed out after 10 s")
            self.status_var.set("journalctl timed out")

    def vsee_load_sample(self) -> None:
        self._set_text(self.vsee_points_text, DEFAULT_POINTS_TEXT)
        self._set_text(self.vsee_edges_text, DEFAULT_EDGES_TEXT)
        self.vsee_render()

    def vsee_render_event(self, _event: object) -> None:
        self.vsee_render()

    def vsee_render(self) -> None:
        try:
            model = HologramModel.from_text(
                self._get_text(self.vsee_points_text),
                self._get_text(self.vsee_edges_text),
            )
            width = max(self.vsee_canvas.winfo_width(), 320)
            height = max(self.vsee_canvas.winfo_height(), 260)
            projected = model.projected(
                width=width,
                height=height,
                rotation_x_degrees=self.vsee_rotation_x_var.get(),
                rotation_y_degrees=self.vsee_rotation_y_var.get(),
                scale=self.vsee_scale_var.get(),
            )
        except VseeModelError as exc:
            self.status_var.set(f"Vsee model error: {exc}")
            return
        except tk.TclError:
            return

        self.vsee_canvas.delete("all")
        self._draw_vsee_grid(width, height)
        points = projected["points"]
        edges = projected["edges"]
        for source, target in edges:
            x1, y1, z1 = points[source]
            x2, y2, z2 = points[target]
            depth = (z1 + z2) / 2
            color = "#2fffd3" if depth >= 0 else "#35a7ff"
            self.vsee_canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
        for point_id, (x_pos, y_pos, _z_pos) in points.items():
            self.vsee_canvas.create_oval(x_pos - 4, y_pos - 4, x_pos + 4, y_pos + 4, fill="#ffffff", outline="#9fffe8")
            self.vsee_canvas.create_text(x_pos + 10, y_pos - 10, text=point_id, fill="#d8fff8", anchor="w")
        self.status_var.set(f"Rendered Vsee hologram: {len(points)} points, {len(edges)} edges")

    def _draw_vsee_grid(self, width: int, height: int) -> None:
        center_x = width / 2
        center_y = height / 2
        spacing = 40
        for x_pos in range(0, width + spacing, spacing):
            color = "#1b2730" if abs(x_pos - center_x) > 2 else "#34515b"
            self.vsee_canvas.create_line(x_pos, 0, x_pos, height, fill=color)
        for y_pos in range(0, height + spacing, spacing):
            color = "#1b2730" if abs(y_pos - center_y) > 2 else "#34515b"
            self.vsee_canvas.create_line(0, y_pos, width, y_pos, fill=color)

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)

    def _get_text(self, widget: tk.Text) -> str:
        return widget.get("1.0", tk.END)

    def debug_refresh_files(self) -> None:
        self.debug_tree.delete(*self.debug_tree.get_children())
        self.debug_tree_index.clear()
        for directory in DEBUG_ALLOWED_DIRS:
            if not directory.exists():
                continue
            node_id = self.debug_tree.insert("", tk.END, text=directory.name, open=True)
            self.debug_tree_index[node_id] = directory
            self._debug_insert_directory(node_id, directory)
        self.status_var.set("Loaded debug file tree")

    def _debug_insert_directory(self, parent_id: str, directory: Path) -> None:
        for child in sorted(directory.iterdir(), key=lambda path: (path.is_file(), path.name.lower())):
            if child.name in DEBUG_SKIP_DIRS:
                continue
            if child.is_dir():
                node_id = self.debug_tree.insert(parent_id, tk.END, text=child.name, open=False)
                self.debug_tree_index[node_id] = child
                self._debug_insert_directory(node_id, child)
            elif self._debug_is_text_file(child):
                node_id = self.debug_tree.insert(parent_id, tk.END, text=child.name)
                self.debug_tree_index[node_id] = child

    def debug_on_tree_select(self, _event: object) -> None:
        selection = self.debug_tree.selection()
        if not selection:
            return
        path = self.debug_tree_index.get(selection[0])
        if path is None:
            return
        self.debug_path_var.set(str(path.relative_to(PROJECT_ROOT)))
        if path.is_file():
            self.debug_load_selected()

    def debug_load_selected(self) -> None:
        path = self._debug_selected_path()
        if path is None or path.is_dir():
            return
        if not self._debug_is_text_file(path):
            messagebox.showerror("Unsupported file", "Debug mode only opens project text files.")
            return
        self.debug_text.delete("1.0", tk.END)
        self.debug_text.insert("1.0", path.read_text(encoding="utf-8"))
        self.status_var.set(f"Loaded {path.relative_to(PROJECT_ROOT)}")

    def debug_save_current(self) -> None:
        path = self._debug_selected_path()
        if path is None or path.is_dir():
            messagebox.showerror("No file selected", "Select a project file first.")
            return
        if not self._debug_is_text_file(path):
            messagebox.showerror("Unsupported file", "Debug mode only saves project text files.")
            return
        path.write_text(self.debug_text.get("1.0", tk.END).rstrip("\n") + "\n", encoding="utf-8")
        self.status_var.set(f"Saved {path.relative_to(PROJECT_ROOT)}")

    def _debug_selected_path(self) -> Path | None:
        raw_path = self.debug_path_var.get().strip()
        if raw_path:
            path = (PROJECT_ROOT / raw_path).resolve()
        else:
            selection = self.debug_tree.selection()
            if not selection:
                return None
            indexed = self.debug_tree_index.get(selection[0])
            if indexed is None:
                return None
            path = indexed.resolve()
        if not self._debug_path_allowed(path):
            messagebox.showerror("Blocked path", "Debug mode only allows tests, scripts, QuikTieper, and CamComs.")
            return None
        return path

    def _debug_path_allowed(self, path: Path) -> bool:
        try:
            path.relative_to(PROJECT_ROOT)
        except ValueError:
            return False
        for allowed_dir in DEBUG_ALLOWED_DIRS:
            try:
                path.relative_to(allowed_dir)
            except ValueError:
                continue
            return True
        return False

    def _debug_is_text_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in DEBUG_TEXT_EXTENSIONS

    def _parse_camcoms_envelope(self, raw_input: str) -> dict:
        if raw_input.startswith("{"):
            data = json.loads(raw_input)
            if not isinstance(data, dict):
                raise ValueError("CamComs envelope JSON must be an object.")
            return data
        return decode_envelope(raw_input)

    def _set_camcoms_output(self, value: str) -> None:
        self.cam_output_text.delete("1.0", tk.END)
        self.cam_output_text.insert("1.0", value)

    def _get_camcoms_output(self) -> str:
        return self.cam_output_text.get("1.0", tk.END)

    def _set_host_output(self, value: str) -> None:
        self.host_output_text.delete("1.0", tk.END)
        self.host_output_text.insert("1.0", value)

    def _browse_open(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Choose file",
            filetypes=(("JSON files", "*.json"), ("All files", "*")),
        )
        if path:
            variable.set(path)

    def _browse_save(self, variable: tk.StringVar) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose output file",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*")),
        )
        if path:
            variable.set(path)

    def _read_json_path(self, raw_path: str) -> dict:
        data = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{raw_path} must contain a JSON object.")
        return data

    def _write_json_path(self, raw_path: str, data: dict) -> None:
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _on_close(self) -> None:
        """Handle window close button.

        If minimize-to-tray is enabled, hide the window instead of closing.
        Otherwise perform full shutdown.
        """
        if self._minimize_to_tray.get():
            self.root.withdraw()
            self.status_var.set("Fiona minimized to tray")
            return

        self._full_shutdown()

    def _full_shutdown(self) -> None:
        """Stop all services, tray, and destroy the window."""
        if self.listener_running:
            self._stop_listener()
        if self._service_poll_id is not None:
            self.root.after_cancel(self._service_poll_id)
            self._service_poll_id = None
        if self._pairing_poll_id is not None:
            self.root.after_cancel(self._pairing_poll_id)
            self._pairing_poll_id = None
        if self._trusted_poll_id is not None:
            self.root.after_cancel(self._trusted_poll_id)
            self._trusted_poll_id = None
        if self._tray_poll_id is not None:
            self.root.after_cancel(self._tray_poll_id)
            self._tray_poll_id = None
        if self.pairing_http_server is not None:
            try:
                self.pairing_http_server.stop()
            except Exception:
                pass
            self.pairing_http_server = None
        # Stop voice subsystems
        if self._voice_listening and self._voice_engine is not None:
            self._voice_engine.stop()
        if self._voice_ptt_running and self._voice_ptt is not None:
            self._voice_ptt.stop()
        self.tray.stop()
        self.root.destroy()

    # ── System tray helpers ────────────────────────────────────────────

    def _tray_show_window(self) -> None:
        """Deiconify and raise the main window."""
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass  # Window was destroyed

    def _tray_quit(self) -> None:
        """Quit Fiona from tray menu — always performs full shutdown."""
        self._minimize_to_tray.set(False)
        self._on_close()

    def _tray_update_state(self) -> None:
        """Read current state from services and update tray icon."""
        if not self.tray.available:
            return

        service_running = False
        if self._service_systemd_available:
            state = _get_service_state(SERVICE_NAME)
            if "error" not in state:
                service_running = state.get("ActiveState") == "active"

        listening = self.listener_running

        paired_devices = 0
        try:
            trusted = list_trusted_senders(DEFAULT_TRUSTED_DIR)
            paired_devices = len(trusted)
        except Exception:
            pass

        self.tray.update(
            service_running=service_running,
            listening=listening,
            paired_devices=paired_devices,
        )

    def _tray_poll(self) -> None:
        """Periodically update tray icon state every 5 seconds."""
        self._tray_update_state()
        self._tray_poll_id = self.root.after(5000, self._tray_poll)


def launch_editor(config_path: Path) -> None:
    ConfigEditorApp(config_path).run()


if __name__ == "__main__":
    import sys

    if "--tray" in sys.argv:
        # Start tray icon only (useful if GUI window start fails)
        from QuikTieper.system_tray import SystemTrayIcon

        tray = SystemTrayIcon()
        tray.start()
        try:
            while True:
                import time

                time.sleep(1)
        except KeyboardInterrupt:
            tray.stop()
    else:
        launch_editor(DEFAULT_CONFIG_PATH)
