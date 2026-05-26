from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from CamComs import (
    DEFAULT_AUDIT_LOG_PATH,
    DEFAULT_FIONA_CONFIG_PATH,
    DEFAULT_TRUSTED_DIR,
    AuditLog,
    CamComsIdentity,
    CamComsHttpClient,
    HostService,
    PublicKeyBundle,
    default_host_service_config,
    decode_envelope,
    decrypt_text,
    encode_envelope,
    encrypt_message,
    instruction_from_text,
    instruction_to_text,
    list_trusted_senders,
    press_instruction,
    private_key_path,
    public_key_path,
    remove_trusted_sender,
    save_host_service_config,
)
from QuikTieper.bindings import parse_bindings
from QuikTieper.config import load_config, save_config
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
        self._build_ui()
        self.root.bind_all("<Alt-c>", self.capture_mouse_position_hotkey)
        self.root.bind_all("<Alt-C>", self.capture_mouse_position_hotkey)
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
        camcoms_tab = ttk.Frame(self.notebook, padding=12)
        host_tab = ttk.Frame(self.notebook, padding=12)
        vsee_tab = ttk.Frame(self.notebook, padding=12)
        debug_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(camcoms_tab, text="CamComs")
        self.notebook.add(vsee_tab, text="Vsee")
        self.notebook.add(bindings_tab, text="Bindings")
        self.notebook.add(json_tab, text="Raw Json")
        self.notebook.add(debug_tab, text="Debug")
        self.notebook.add(host_tab, text="Host")

        self._build_bindings_tab(bindings_tab)
        self._build_json_tab(json_tab)
        self._build_camcoms_tab(camcoms_tab)
        self._build_host_tab(host_tab)
        self._build_vsee_tab(vsee_tab)
        self._build_debug_tab(debug_tab)

        footer = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1)

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
        parent.rowconfigure(1, weight=1)

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

        output_frame = ttk.LabelFrame(parent, text="CamComs Output", padding=12)
        output_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
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

    def _build_host_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)

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

        output_frame = ttk.LabelFrame(parent, text="Host Output", padding=12)
        output_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.host_output_text = tk.Text(output_frame, wrap="word", height=18)
        self.host_output_text.grid(row=0, column=0, sticky="nsew")

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
        senders = [bundle.to_dict() for bundle in list_trusted_senders(DEFAULT_TRUSTED_DIR)]
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
        if self.listener_running:
            self._stop_listener()
        self.root.destroy()


def launch_editor(config_path: Path) -> None:
    ConfigEditorApp(config_path).run()
