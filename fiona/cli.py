from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from CamComs import (
    DEFAULT_AUDIT_LOG_PATH,
    DEFAULT_CAMCOMS_DIR,
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
    encrypt_and_send_instruction,
    encrypt_message,
    instruction_from_text,
    instruction_to_text,
    install_host_service_unit,
    list_trusted_senders,
    read_host_service_logs,
    remove_trusted_sender,
    press_instruction,
    private_key_path,
    public_key_path,
    render_host_service_unit,
    run_host_receiver,
    run_user_service_command,
    save_host_service_config,
    save_trusted_sender,
    trusted_public_key_path,
)
from Agent import DEFAULT_OLLAMA_BASE_URL, OllamaClient, command_registry
from CmdTrace import clear_trace, read_trace
from DataClient import convert_table, deep_research_topic, load_table, mine_topic
from FionaCore import (
    ActionRouter,
    MacroStep,
    load_macros,
    notify_result,
    parse_voice_command,
    quick_transcribe,
    run_macro,
    save_macro,
    WhisperEngine,
)
from QuikTieper.remote import RemoteActionRunner
from RecallVault import clear_recall, forget, list_categories, remember, search_recall
from SeeOnDesk import active_window_info, desktop_snapshot
from TerminalAssist import (
    build_cli_preview,
    build_dashboard,
    build_zellij_layout,
    run_terminal_cli,
    terminal_assist_status,
    write_zellij_layout,
)
from TerminalAssist.dashboard import run_zellij


QUIKTIEPER_COMMANDS = {"init", "list", "edit", "run", "import-apps", "assign-keys", "normalize-app-cmds"}


def _run_shell(args: argparse.Namespace) -> None:
    full_cmd = " ".join(args.cmd)
    try:
        # Use os.system for direct shell execution as requested
        code = os.system(full_cmd)
        if code != 0:
            raise SystemExit(code)
    except Exception as e:
        raise SystemExit(f"shell command failed: {e}")


def main() -> None:
    argv = _normalize_help_args(sys.argv[1:])
    if not argv:
        _build_parser().print_help()
        return
    if _should_delegate_to_quiktieper(argv):
        _run_quiktieper(argv)
        return
    if argv and argv[0] in {"quiktieper", "qt"}:
        _run_quiktieper(argv[1:])
        return

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.layer in {"camcoms", "cc"}:
        _run_camcoms(args)
        return

    if args.layer == "host":
        _run_camcoms_service(args)
        return

    if args.layer == "agent":
        _run_agent(args)
        return

    if args.layer in {"dataclient", "data"}:
        _run_dataclient(args)
        return

    if args.layer == "action":
        _run_action_router(args)
        return

    if args.layer == "voice":
        _run_voice(args)
        return

    if args.layer == "macro":
        _run_macro(args)
        return

    if args.layer == "recall":
        _run_recall(args)
        return

    if args.layer in {"fat", "terminal-assist"}:
        _run_fat(args)
        return

    if args.layer == "cli":
        _run_cli_center(args)
        return

    if args.layer == "api":
        args.fat_command = "api"
        _run_fat(args)
        return

    if args.layer == "run-shell":
        _run_shell(args)
        return

    if args.layer == "vsee":
        _run_vsee(args)
        return

    if args.layer == "phiconnect":
        _run_phiconnect(args)
        return

    if args.layer in {"seeondesk", "sod"}:
        _run_seeondesk(args)
        return

    parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fiona",
        description="Fiona umbrella CLI for local control, encrypted communication, data gathering, holography, and agent bridges.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Command groups:
  fiona quiktieper ...   QuikTieper app bindings, listener, and GUI editor
  fiona host ...         Unified host service setup, status, logs, and lifecycle
  fiona camcoms ...      Encrypted envelopes, keys, trust, receiver, and transport
  fiona agent ...        LM Studio bridge and agent-visible command registry
  fiona dataclient ...   Search, scrape, summarize, and export topic research
  fiona action ...       Shared action router, command tracing, permissions, and notifications
  fiona voice ...        Deterministic typed/voice phrase to action translation
  fiona macro ...        Named reusable action macros
  fiona recall ...       RecallVault structured remembrance storage
  fiona fat ...          Fiona Terminal Assistance dashboard and Zellij layout
  fiona cli              Sliding Fiona terminal command center
  fiona seeondesk ...    Desktop awareness and active-window identification
  fiona vsee             Standalone Vsee Holography app
  fiona phiconnect       Standalone encrypted PhiConnect chat app

Shortcuts:
  fiona edit             Same as fiona quiktieper edit
  fiona run              Same as fiona quiktieper run
  fiona list             Same as fiona quiktieper list

Use "fiona <group> --help" for a group-specific command grid.""",
    )
    subparsers = parser.add_subparsers(dest="layer")

    quiktieper = subparsers.add_parser(
        "quiktieper",
        aliases=["qt"],
        help="Run QuikTieper launcher/listener/editor commands.",
    )
    quiktieper.add_argument("quiktieper_args", nargs=argparse.REMAINDER)

    host = subparsers.add_parser("host", help="Manage the unified Fiona host service.")
    _add_service_subcommands(host)

    agent = subparsers.add_parser("agent", help="Talk to a local Ollama model.")
    agent_subparsers = agent.add_subparsers(dest="agent_command", required=True)
    agent_commands = agent_subparsers.add_parser("commands", help="List Fiona commands available to a future agent.")
    agent_commands.add_argument("--config", type=Path, default=None, help="QuikTieper bindings file used for app names.")
    agent_status = agent_subparsers.add_parser("status", help="Check the Ollama local server.")
    _add_ollama_args(agent_status)
    agent_run = agent_subparsers.add_parser("run", help="Initiate the autonomous agent to solve a goal.")
    _add_ollama_args(agent_run)
    agent_run.add_argument("goal", nargs="+", help="The task you want Fiona to accomplish.")
    agent_run.add_argument("--turns", type=int, default=5, help="Maximum number of thinking turns.")
    agent_ask = agent_subparsers.add_parser("ask", help="Send a prompt to Ollama.")
    _add_ollama_args(agent_ask)
    agent_ask.add_argument("prompt", nargs="+")
    agent_ask.add_argument("--system", default="You are Fiona, a local workstation control assistant.")
    agent_ask.add_argument("--temperature", type=float, default=0.3)
    agent_ask.add_argument("--max-tokens", type=int, default=512)

    dataclient = subparsers.add_parser(
        "dataclient",
        aliases=["data"],
        help="Run Fiona DataClient topic search and scraping tools.",
    )
    dataclient_subparsers = dataclient.add_subparsers(dest="dataclient_command")
    data_mine = dataclient_subparsers.add_parser("mine", help="Search a topic, summarize pages, and save a CSV.")
    data_mine.add_argument("topic", nargs="+")
    data_mine.add_argument("--out", type=Path, required=True, help="CSV output path.")
    data_mine.add_argument("--max-links", type=int, default=30)
    data_mine.add_argument("--max-sentences", type=int, default=5)
    data_mine.add_argument("--sleep", type=float, default=0.5, dest="sleep_seconds")
    data_deep = dataclient_subparsers.add_parser("deep", help="Run bounded deep research from search results.")
    data_deep.add_argument("topic", nargs="+")
    data_deep.add_argument("--out", type=Path, required=True, help="CSV output path.")
    data_deep.add_argument("--seed-links", type=int, default=10)
    data_deep.add_argument("--page-limit", type=int, default=50)
    data_deep.add_argument("--depth", type=int, default=1)
    data_deep.add_argument("--max-sentences", type=int, default=5)
    data_deep.add_argument("--sleep", type=float, default=0.5, dest="sleep_seconds")
    data_deep.add_argument("--cross-domain", action="store_true", help="Allow crawling links outside each seed page domain.")
    data_convert = dataclient_subparsers.add_parser("convert", help="Convert table data between CSV, JSON, and SQLite.")
    data_convert.add_argument("input", type=Path)
    data_convert.add_argument("--out", type=Path, required=True)
    data_convert.add_argument("--table", default="data", help="SQLite table name when writing DB output.")
    data_view = dataclient_subparsers.add_parser("view", help="Print a compact preview of a CSV, JSON, or SQLite table.")
    data_view.add_argument("input", type=Path)
    data_view.add_argument("--limit", type=int, default=10)
    dataclient_subparsers.add_parser("gui", help="Open the standalone DataClient GUI.")

    action = subparsers.add_parser("action", help="Use Fiona's shared action router.")
    action_subparsers = action.add_subparsers(dest="action_command", required=True)
    action_subparsers.add_parser("list", help="List registered Fiona actions.")
    action_run = action_subparsers.add_parser("run", help="Run a registered Fiona action.")
    action_run.add_argument("name")
    action_run.add_argument("--source", default="local")
    action_run.add_argument("--profile", default="local", dest="permission_profile")
    action_run.add_argument("--dry-run", action="store_true")
    action_run.add_argument("--timeout", type=float, default=30.0)
    action_run.add_argument("--notify", choices=["silent", "stdout", "desktop"], default="silent")
    action_run.add_argument("--trace-path", type=Path, default=None)
    action_history = action_subparsers.add_parser("history", help="Show recent action history.")
    action_history.add_argument("--limit", type=int, default=20)
    action_history.add_argument("--name", help="Filter history by action name.")
    action_history.add_argument("--trace-path", type=Path, default=None)
    action_clear = action_subparsers.add_parser("clear", help="Clear the routed command trace log.")
    action_clear.add_argument("--trace-path", type=Path, default=None, dest="path")

    voice = subparsers.add_parser("voice", help="Translate typed speech text into Fiona actions.")
    voice_subparsers = voice.add_subparsers(dest="voice_command", required=True)
    voice_parse = voice_subparsers.add_parser("parse", help="Parse a phrase into an action.")
    voice_parse.add_argument("phrase", nargs="+")
    voice_run = voice_subparsers.add_parser("run", help="Parse and run a phrase through the action router.")
    voice_run.add_argument("phrase", nargs="+")
    voice_run.add_argument("--dry-run", action="store_true")
    voice_run.add_argument("--profile", default="local", dest="permission_profile")
    
    voice_listen = voice_subparsers.add_parser("listen", help="Listen to microphone and run detected action.")
    voice_listen.add_argument("--duration", type=float, default=5.0, help="Recording duration in seconds.")
    voice_listen.add_argument("--model", default="tiny", help="Whisper model size (tiny, base, small).")
    voice_listen.add_argument("--dry-run", action="store_true")

    macro = subparsers.add_parser("macro", help="Save and run named Fiona action macros.")
    macro_subparsers = macro.add_subparsers(dest="macro_command", required=True)
    macro_list = macro_subparsers.add_parser("list", help="List saved macros.")
    macro_list.add_argument("--path", type=Path, default=None)
    macro_save = macro_subparsers.add_parser("save", help="Save a macro from action names.")
    macro_save.add_argument("name")
    macro_save.add_argument("actions", nargs="+")
    macro_save.add_argument("--path", type=Path, default=None)
    macro_run = macro_subparsers.add_parser("run", help="Run a saved macro.")
    macro_run.add_argument("name")
    macro_run.add_argument("--dry-run", action="store_true")
    macro_run.add_argument("--path", type=Path, default=None)
    macro_run.add_argument("--trace-path", type=Path, default=None)

    recall = subparsers.add_parser("recall", help="Use RecallVault remembrance storage.")
    recall_subparsers = recall.add_subparsers(dest="recall_command", required=True)
    recall_list = recall_subparsers.add_parser("list", help="List saved remembrance entries.")
    recall_list.add_argument("--path", type=Path, default=None)
    recall_search = recall_subparsers.add_parser("search", help="Search saved remembrance entries.")
    recall_search.add_argument("query", nargs="?", default="")
    recall_search.add_argument("--path", type=Path, default=None)
    recall_categories = recall_subparsers.add_parser("categories", help="List unique RecallVault categories.")
    recall_categories.add_argument("--path", type=Path, default=None)
    recall_remember = recall_subparsers.add_parser("remember", help="Save or replace a remembrance entry.")
    recall_remember.add_argument("key")
    recall_remember.add_argument("value")
    recall_remember.add_argument("--category", default="general")
    recall_remember.add_argument("--path", type=Path, default=None)
    recall_forget = recall_subparsers.add_parser("forget", help="Remove a remembrance entry by key.")
    recall_forget.add_argument("key")
    recall_forget.add_argument("--path", type=Path, default=None)
    recall_clear = recall_subparsers.add_parser("clear", help="Clear the entire RecallVault.")
    recall_clear.add_argument("--path", type=Path, default=None)

    fat = subparsers.add_parser(
        "fat",
        aliases=["terminal-assist"],
        help="Run Fiona Terminal Assistance dashboard and Zellij helpers.",
    )
    fat_subparsers = fat.add_subparsers(dest="fat_command")
    fat_status = fat_subparsers.add_parser("status", help="Show the btop-style fAT terminal dashboard.")
    fat_status.add_argument("--no-color", action="store_true")
    fat_status.add_argument("--json", action="store_true", help="Output status as JSON.")
    fat_status.add_argument("--width", type=int, default=96)
    fat_subparsers.add_parser("tui", help="Open the sliding Fiona terminal command center.")
    fat_subparsers.add_parser("gui", help="Open the high-fidelity Fiona fAT GUI dashboard.")
    fat_subparsers.add_parser("api", help="Print fAT system status as JSON.")
    fat_layout = fat_subparsers.add_parser("layout", help="Print or write the fAT Zellij layout.")
    fat_layout.add_argument("--out", type=Path, default=None)
    fat_layout.add_argument("--print", action="store_true", dest="print_layout")
    fat_layout.add_argument("--working-directory", type=Path, default=Path.cwd())
    fat_run = fat_subparsers.add_parser("run", help="Launch the fAT Zellij workspace.")
    fat_run.add_argument("--layout", type=Path, default=Path("/tmp/fiona-fat.kdl"))
    fat_run.add_argument("--working-directory", type=Path, default=Path.cwd())

    cli_center = subparsers.add_parser("cli", help="Open the sliding Fiona terminal command center.")
    cli_center.add_argument("--preview", action="store_true", help="Print the non-interactive command-center preview.")
    subparsers.add_parser("api", help="Short for 'fiona fat api'.")
    run_shell = subparsers.add_parser("run-shell", help="Run a shell command (internal helper).")
    run_shell.add_argument("cmd", nargs="+")

    seeondesk = subparsers.add_parser(
        "seeondesk",
        aliases=["sod"],
        help="Identify the current desktop session and focused app/window.",
    )
    seeondesk_subparsers = seeondesk.add_subparsers(dest="seeondesk_command", required=True)
    seeondesk_subparsers.add_parser("active", help="Show the currently focused app/window.")
    seeondesk_subparsers.add_parser("list", help="List all open windows.")
    status = seeondesk_subparsers.add_parser("status", help="Show a desktop-awareness snapshot.")
    status.add_argument("--screenshot", action="store_true", help="Include a screen capture in the snapshot.")
    
    capture = seeondesk_subparsers.add_parser("capture", help="Capture the current screen.")
    capture.add_argument("--out", type=Path, default=Path("screenshot.png"), help="Output path for the screenshot.")
    
    analyze = seeondesk_subparsers.add_parser("analyze", help="Analyze the screen using the local agent.")
    analyze.add_argument("prompt", help="The question to ask about the screen.")
    analyze.add_argument("--image", type=Path, default=None, help="Optional existing image to analyze.")

    vsee = subparsers.add_parser("vsee", help="Open the standalone Vsee Holography window.")
    vsee.add_argument("--points", type=Path, default=None)
    vsee.add_argument("--edges", type=Path, default=None)

    subparsers.add_parser("phiconnect", help="Open the standalone PhiConnect encrypted chat window.")

    camcoms = subparsers.add_parser(
        "camcoms",
        aliases=["cc"],
        help="Run CamComs encryption and encoded IP message commands.",
    )
    camcoms_subparsers = camcoms.add_subparsers(dest="camcoms_command", required=True)

    keygen = camcoms_subparsers.add_parser("keygen", help="Create a CamComs device identity.")
    keygen.add_argument("--device-id", default="host")
    keygen.add_argument("--private-out", type=Path, default=None)
    keygen.add_argument("--public-out", type=Path, default=None)
    keygen.add_argument("--passphrase", default=None)

    public = camcoms_subparsers.add_parser("public", help="Export public keys from a private identity file.")
    public.add_argument("--private", type=Path, default=None)
    public.add_argument("--public-out", type=Path, default=None)
    public.add_argument("--passphrase", default=None)

    camcoms_subparsers.add_parser("paths", help="Show visible default CamComs key storage paths.")

    trust = camcoms_subparsers.add_parser("trust", help="List, add, or remove trusted sender public keys.")
    trust_action = trust.add_mutually_exclusive_group(required=True)
    trust_action.add_argument("--public", type=Path, help="Public key JSON to trust.")
    trust_action.add_argument("--list", action="store_true", help="List trusted sender public keys.")
    trust_action.add_argument("--remove", help="Remove a trusted sender by device id.")
    trust.add_argument("--trusted-dir", type=Path, default=DEFAULT_TRUSTED_DIR)

    encrypt = camcoms_subparsers.add_parser("encrypt", help="Encrypt a message for another device.")
    encrypt.add_argument("--sender-private", type=Path, default=None)
    encrypt.add_argument("--recipient-public", type=Path, default=None)
    encrypt.add_argument("--sender-passphrase", default=None)
    encrypt_input = encrypt.add_mutually_exclusive_group(required=True)
    encrypt_input.add_argument("--instruction-json")
    encrypt_input.add_argument("--press", nargs="+")
    encrypt.add_argument("--type", default="instruction", dest="message_type")
    encrypt.add_argument("--json", action="store_true", help="Print the envelope JSON instead of encoded text.")

    decrypt = camcoms_subparsers.add_parser("decrypt", help="Decrypt an encoded message or envelope JSON.")
    decrypt.add_argument("--recipient-private", type=Path, required=True)
    decrypt.add_argument("--recipient-passphrase", default=None)
    decrypt.add_argument("--sender-public", type=Path, default=None)
    decrypt_input = decrypt.add_mutually_exclusive_group(required=True)
    decrypt_input.add_argument("--encoded")
    decrypt_input.add_argument("--envelope", type=Path)

    send = camcoms_subparsers.add_parser("send", help="POST an encoded CamComs message to an IP endpoint.")
    send.add_argument("--host", required=True)
    send.add_argument("--port", type=int, default=8080)
    send.add_argument("--path", default="/")
    send.add_argument("--timeout", type=float, default=5.0)
    send_input = send.add_mutually_exclusive_group(required=True)
    send_input.add_argument("--encoded")
    send_input.add_argument("--envelope", type=Path)

    compose_send = camcoms_subparsers.add_parser("compose-send", help="Encrypt an instruction and send it in one step.")
    compose_send.add_argument("--host", required=True)
    compose_send.add_argument("--port", type=int, default=8080)
    compose_send.add_argument("--path", default="/")
    compose_send.add_argument("--timeout", type=float, default=5.0)
    compose_send.add_argument("--sender-private", type=Path, default=None)
    compose_send.add_argument("--recipient-public", type=Path, default=None)
    compose_send.add_argument("--sender-passphrase", default=None)
    compose_input = compose_send.add_mutually_exclusive_group(required=True)
    compose_input.add_argument("--instruction-json")
    compose_input.add_argument("--press", nargs="+")

    receive = camcoms_subparsers.add_parser("receive", help="Run the host receiver for ESP32 messages.")
    receive.add_argument("--host", default="0.0.0.0")
    receive.add_argument("--port", type=int, default=8080)
    receive.add_argument("--private", type=Path, default=None)
    receive.add_argument("--passphrase", default=None)
    receive.add_argument("--trusted-dir", type=Path, default=DEFAULT_TRUSTED_DIR)
    receive.add_argument("--execute", action="store_true", help="Execute approved QuikTieper actions instead of dry-run.")

    service = camcoms_subparsers.add_parser("service", help="Manage the CamComs host service.")
    _add_service_subcommands(service)

    audit = camcoms_subparsers.add_parser("audit", help="Show recent CamComs host audit log events.")
    audit.add_argument("--path", type=Path, default=DEFAULT_AUDIT_LOG_PATH)
    audit.add_argument("--limit", type=int, default=50)

    camcoms_subparsers.add_parser("smoke-test", help="Run a local encrypt/decrypt check.")
    return parser


def _add_service_subcommands(parser: argparse.ArgumentParser) -> None:
    service_subparsers = parser.add_subparsers(dest="service_command", required=True)
    service_init = service_subparsers.add_parser("init", help="Write the default Fiona host service config.")
    service_init.add_argument("--config", type=Path, default=DEFAULT_FIONA_CONFIG_PATH)
    service_init.add_argument("--force", action="store_true")
    service_status = service_subparsers.add_parser("status", help="Show host service config and health checks.")
    service_status.add_argument("--config", type=Path, default=DEFAULT_FIONA_CONFIG_PATH)
    service_status.add_argument("--check-port", action="store_true")
    service_run = service_subparsers.add_parser("run", help="Run the Fiona host service.")
    service_run.add_argument("--config", type=Path, default=DEFAULT_FIONA_CONFIG_PATH)
    service_run.add_argument("--passphrase", default=None)
    service_install = service_subparsers.add_parser("install-service", help="Install or print a user systemd service.")
    service_install.add_argument("--config", type=Path, default=DEFAULT_FIONA_CONFIG_PATH)
    service_install.add_argument("--name", default="fiona-host.service")
    service_install.add_argument("--working-directory", type=Path, default=Path.cwd())
    service_install.add_argument("--python", default=sys.executable, dest="python_executable")
    service_install.add_argument("--print", action="store_true", dest="print_only")
    service_logs = service_subparsers.add_parser("logs", help="Show Fiona host user-service logs.")
    service_logs.add_argument("--name", default="fiona-host.service")
    service_logs.add_argument("--lines", type=int, default=80)
    service_logs.add_argument("--follow", action="store_true")
    for action in ("enable", "disable", "restart", "stop"):
        service_action = service_subparsers.add_parser(action, help=f"Run systemctl --user {action} for the Fiona host service.")
        service_action.add_argument("--name", default="fiona-host.service")


def _add_ollama_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--model", default="qwen2:1.5b")
    parser.add_argument("--timeout", type=float, default=60.0)


def _should_delegate_to_quiktieper(argv: list[str]) -> bool:
    if not argv:
        return False
    if argv[0] in {"-h", "--help"}:
        return False
    if argv[0] in QUIKTIEPER_COMMANDS:
        return True
    return argv[0].startswith("--")


def _run_quiktieper(args: list[str]) -> None:
    from QuikTieper.cli import main as quiktieper_main

    if args == ["help"]:
        args = ["--help"]
    original_argv = sys.argv
    try:
        sys.argv = [original_argv[0], *args]
        quiktieper_main()
    finally:
        sys.argv = original_argv


def _normalize_help_args(argv: list[str]) -> list[str]:
    if argv == ["help"]:
        return ["--help"]
    normalized = list(argv)
    if len(normalized) >= 2 and normalized[-1] == "help":
        normalized[-1] = "--help"
    return normalized


def _run_camcoms(args: argparse.Namespace) -> None:
    command = args.camcoms_command
    if command == "keygen":
        identity = CamComsIdentity.generate(args.device_id)
        private_out = args.private_out or private_key_path(identity.device_id)
        public_out = args.public_out or public_key_path(identity.device_id)
        _write_or_print(identity.to_private_dict(args.passphrase), private_out, label="private")
        _write_or_print(identity.public_bundle.to_dict(), public_out, label="public")
        return

    if command == "public":
        private_path = args.private or private_key_path("host")
        identity = CamComsIdentity.from_private_dict(_read_json(private_path), passphrase=args.passphrase)
        public_out = args.public_out or public_key_path(identity.device_id)
        _write_or_print(identity.public_bundle.to_dict(), public_out, label="public")
        return

    if command == "paths":
        print(
            _pretty_json(
                {
                    "camcoms_dir": str(DEFAULT_CAMCOMS_DIR),
                    "host_private": str(private_key_path("host")),
                    "host_public": str(public_key_path("host")),
                    "esp32_private": str(private_key_path("esp32")),
                    "esp32_public": str(public_key_path("esp32")),
                    "trusted_dir": str(DEFAULT_TRUSTED_DIR),
                    "esp32_trusted_public": str(trusted_public_key_path("esp32")),
                }
            )
        )
        return

    if command == "trust":
        if args.list:
            trusted = [bundle.to_dict() for bundle in list_trusted_senders(args.trusted_dir)]
            print(_pretty_json({"trusted_dir": str(args.trusted_dir), "senders": trusted}))
            return
        if args.remove:
            removed = remove_trusted_sender(args.remove, args.trusted_dir)
            print(f"{'Removed' if removed else 'No trusted sender found for'} {args.remove}")
            return
        bundle = PublicKeyBundle.from_dict(_read_json(args.public))
        path = save_trusted_sender(bundle, args.trusted_dir)
        print(f"Trusted sender {bundle.device_id} at {path}")
        return

    if command == "encrypt":
        sender_private = args.sender_private or private_key_path("esp32")
        recipient_public = args.recipient_public or public_key_path("host")
        sender = CamComsIdentity.from_private_dict(_read_json(sender_private), passphrase=args.sender_passphrase)
        recipient = PublicKeyBundle.from_dict(_read_json(recipient_public))
        instruction_text = _instruction_text_from_args(args)
        envelope = encrypt_message(
            instruction_text,
            sender=sender,
            recipient=recipient,
            message_type=args.message_type,
        )
        print(_pretty_json(envelope) if args.json else encode_envelope(envelope))
        return

    if command == "decrypt":
        recipient = CamComsIdentity.from_private_dict(
            _read_json(args.recipient_private),
            passphrase=args.recipient_passphrase,
        )
        expected_sender = PublicKeyBundle.from_dict(_read_json(args.sender_public)) if args.sender_public else None
        envelope = decode_envelope(args.encoded) if args.encoded else _read_json(args.envelope)
        print(decrypt_text(envelope, recipient=recipient, expected_sender=expected_sender))
        return

    if command == "send":
        encoded_message = args.encoded or encode_envelope(_read_json(args.envelope))
        client = CamComsHttpClient(
            host=args.host,
            port=args.port,
            path=args.path,
            timeout_seconds=args.timeout,
        )
        print(client.send_encoded(encoded_message))
        return

    if command == "compose-send":
        sender_private = args.sender_private or private_key_path("host")
        recipient_public = args.recipient_public or public_key_path("esp32")
        sender = CamComsIdentity.from_private_dict(_read_json(sender_private), passphrase=args.sender_passphrase)
        recipient = PublicKeyBundle.from_dict(_read_json(recipient_public))
        print(
            encrypt_and_send_instruction(
                sender=sender,
                recipient=recipient,
                host=args.host,
                port=args.port,
                path=args.path,
                timeout_seconds=args.timeout,
                instruction_json=args.instruction_json,
                press_keys=args.press,
            )
        )
        return

    if command == "receive":
        private_path = args.private or private_key_path("host")
        host_identity = CamComsIdentity.from_private_dict(_read_json(private_path), passphrase=args.passphrase)
        print(f"Listening for CamComs messages on {args.host}:{args.port}")
        print(f"Trusted sender keys: {args.trusted_dir}")
        run_host_receiver(
            host=args.host,
            port=args.port,
            host_identity=host_identity,
            trusted_dir=args.trusted_dir,
            action_runner=RemoteActionRunner(dry_run=not args.execute),
        )
        return

    if command == "service":
        _run_camcoms_service(args)
        return

    if command == "audit":
        print(_pretty_json({"path": str(args.path), "events": AuditLog(args.path).read_recent(args.limit)}))
        return

    if command == "smoke-test":
        esp32_sender = CamComsIdentity.generate("esp32")
        host_receiver = CamComsIdentity.generate("host")
        instruction_text = instruction_to_text(press_instruction(["alt", "s"]))
        envelope = encrypt_message(
            instruction_text,
            sender=esp32_sender,
            recipient=host_receiver.public_bundle,
        )
        print(decrypt_text(envelope, recipient=host_receiver, expected_sender=esp32_sender.public_bundle))
        return

    raise SystemExit(f"unknown CamComs command: {command}")


def _run_camcoms_service(args: argparse.Namespace) -> None:
    service_command = args.service_command
    if service_command == "init":
        if args.config.exists() and not args.force:
            raise SystemExit(f"{args.config} already exists; pass --force to overwrite it")
        path = save_host_service_config(default_host_service_config(), args.config)
        print(f"Wrote host service config to {path}")
        return

    if service_command == "status":
        service = HostService.load(args.config)
        print(_pretty_json(service.status(check_port=args.check_port)))
        return

    if service_command == "run":
        service = HostService.load(args.config, host_passphrase=args.passphrase)
        print(f"Starting CamComs host service from {args.config}")
        service.run()
        return

    if service_command == "install-service":
        if args.print_only:
            print(
                render_host_service_unit(
                    python_executable=args.python_executable,
                    working_directory=args.working_directory,
                    config_path=args.config,
                )
            )
            return
        path = install_host_service_unit(
            service_name=args.name,
            python_executable=args.python_executable,
            working_directory=args.working_directory,
            config_path=args.config,
        )
        print(f"Wrote user service to {path}")
        print("Run: systemctl --user daemon-reload")
        print(f"Run: systemctl --user enable --now {args.name}")
        return

    if service_command in {"enable", "disable", "restart", "stop"}:
        result = run_user_service_command(service_command, service_name=args.name)
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        print(f"{service_command} completed for {args.name}")
        return

    if service_command == "logs":
        result = read_host_service_logs(service_name=args.name, lines=args.lines, follow=args.follow)
        if not args.follow:
            print(result.stdout.rstrip())
        return

    raise SystemExit(f"unknown CamComs service command: {service_command}")


def _run_agent(args: argparse.Namespace) -> None:
    if args.agent_command == "commands":
        registry = command_registry(args.config) if args.config else command_registry()
        print(_pretty_json(registry))
        return
    client = OllamaClient(
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
    )
    if args.agent_command == "status":
        try:
            print(_pretty_json(client.health()))
        except Exception as e:
            print(_pretty_json({"available": False, "error": str(e), "base_url": client.base_url}))
        return

    if args.agent_command == "run":
        from Agent import AgentOrchestrator
        goal = " ".join(args.goal)
        orchestrator = AgentOrchestrator(client=client)
        orchestrator.max_turns = args.turns
        
        print(f"Goal: {goal}")
        print("-" * 40)
        final_thought = orchestrator.run_goal(goal)
        
        print("-" * 40)
        print(f"Final Outcome: {final_thought}")
        return
    if args.agent_command == "ask":
        print(
            client.ask(
                " ".join(args.prompt),
                system_prompt=args.system,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
        )
        return
    raise SystemExit(f"unknown agent command: {args.agent_command}")


def _run_dataclient(args: argparse.Namespace) -> None:
    if args.dataclient_command in {None, "gui"}:
        from DataClient.gui import launch_dataclient

        launch_dataclient()
        return
    if args.dataclient_command == "mine":
        pages = mine_topic(
            " ".join(args.topic),
            args.out,
            max_links=args.max_links,
            max_sentences=args.max_sentences,
            sleep_seconds=args.sleep_seconds,
            log=print,
        )
        print(f"Saved {len(pages)} pages into {args.out}")
        return
    if args.dataclient_command == "deep":
        pages = deep_research_topic(
            " ".join(args.topic),
            args.out,
            seed_links=args.seed_links,
            page_limit=args.page_limit,
            max_depth=args.depth,
            max_sentences=args.max_sentences,
            same_domain_only=not args.cross_domain,
            sleep_seconds=args.sleep_seconds,
            log=print,
        )
        print(f"Saved {len(pages)} pages into {args.out}")
        return
    if args.dataclient_command == "convert":
        path = convert_table(args.input, args.out, table_name=args.table)
        print(f"Converted {args.input} -> {path}")
        return
    if args.dataclient_command == "view":
        rows = load_table(args.input)
        preview = rows[: max(0, args.limit)]
        print(_pretty_json({"path": str(args.input), "rows": preview, "total_rows": len(rows)}))
        return
    raise SystemExit(f"unknown DataClient command: {args.dataclient_command}")


def _run_action_router(args: argparse.Namespace) -> None:
    router = ActionRouter(**({"trace_path": args.trace_path} if getattr(args, "trace_path", None) else {}))
    if args.action_command == "list":
        print(_pretty_json({"actions": router.list_actions()}))
        return
    if args.action_command == "run":
        result = router.run(
            args.name,
            source=args.source,
            permission_profile=args.permission_profile,
            dry_run=args.dry_run,
            timeout_seconds=args.timeout,
        )
        if args.notify != "silent":
            notify_result(result, mode=args.notify)
        print(_pretty_json(result.to_dict()))
        return
    if args.action_command == "history":
        kwargs = {"path": args.trace_path} if args.trace_path else {}
        print(_pretty_json({"events": read_trace(limit=args.limit, action_name=args.name, **kwargs)}))
        return
    if args.action_command == "clear":
        path = args.path or DEFAULT_TRACE_PATH
        cleared = clear_trace(path)
        print(f"{'Cleared' if cleared else 'No trace file found at'} {path}")
        return
    raise SystemExit(f"unknown action command: {args.action_command}")


def _run_voice(args: argparse.Namespace) -> None:
    if args.voice_command == "listen":
        print(f"Listening for {args.duration}s (model: {args.model})...")
        try:
            engine = WhisperEngine(model_size=args.model)
            phrase = engine.listen_and_transcribe(duration_seconds=args.duration)
            print(f"Transcribed: \"{phrase}\"")
            if not phrase:
                print("No speech detected.")
                return
            
            parsed = parse_voice_command(phrase)
            if not parsed:
                print("No matching Fiona action found.")
                return
            
            print(f"Action: {parsed.action} (conf: {parsed.confidence})")
            if args.dry_run:
                print("[dry-run] Would execute action.")
                return
                
            result = ActionRouter().run(
                parsed.action,
                source="voice",
                permission_profile="local",
            )
            print(_pretty_json({"voice": parsed.to_dict(), "result": result.to_dict()}))
        except Exception as e:
            raise SystemExit(f"Voice engine error: {e}")
        return

    phrase = " ".join(args.phrase)
    parsed = parse_voice_command(phrase)
    if parsed is None:
        raise SystemExit(f"could not map phrase to Fiona action: {phrase}")
    if args.voice_command == "parse":
        print(_pretty_json(parsed.to_dict()))
        return
    if args.voice_command == "run":
        result = ActionRouter().run(
            parsed.action,
            source="voice",
            permission_profile=args.permission_profile,
            dry_run=args.dry_run,
        )
        print(_pretty_json({"voice": parsed.to_dict(), "result": result.to_dict()}))
        return
    raise SystemExit(f"unknown voice command: {args.voice_command}")


def _run_macro(args: argparse.Namespace) -> None:
    if args.macro_command == "list":
        macros = {
            name: [step.to_dict() for step in steps]
            for name, steps in sorted(load_macros(**({"path": args.path} if args.path else {})).items())
        }
        print(_pretty_json({"macros": macros}))
        return
    if args.macro_command == "save":
        path = save_macro(args.name, [MacroStep(action) for action in args.actions], **({"path": args.path} if args.path else {}))
        print(f"Saved macro {args.name} to {path}")
        return
    if args.macro_command == "run":
        router = ActionRouter(**({"trace_path": args.trace_path} if args.trace_path else {}))
        results = run_macro(args.name, router=router, dry_run=args.dry_run, **({"path": args.path} if args.path else {}))
        print(_pretty_json({"macro": args.name, "results": [result.to_dict() for result in results]}))
        return
    raise SystemExit(f"unknown macro command: {args.macro_command}")


def _run_recall(args: argparse.Namespace) -> None:
    kwargs = {"path": args.path} if args.path else {}
    if args.recall_command == "list":
        entries = search_recall("", **kwargs)
        print(_pretty_json({"entries": [entry.to_dict() for entry in entries]}))
        return
    if args.recall_command == "search":
        entries = search_recall(args.query, **kwargs)
        print(_pretty_json({"entries": [entry.to_dict() for entry in entries]}))
        return
    if args.recall_command == "categories":
        print(_pretty_json({"categories": list_categories(**kwargs)}))
        return
    if args.recall_command == "remember":
        path = remember(args.key, args.value, category=args.category, **kwargs)
        print(f"Saved remembrance {args.key} to {path}")
        return
    if args.recall_command == "forget":
        forgot = forget(args.key, **kwargs)
        print(f"{'Forgot' if forgot else 'No remembrance found for'} {args.key}")
        return
    if args.recall_command == "clear":
        path = args.path or DEFAULT_RECALL_PATH
        cleared = clear_recall(path)
        print(f"{'Cleared' if cleared else 'No RecallVault file found at'} {path}")
        return
    raise SystemExit(f"unknown recall command: {args.recall_command}")


def _run_fat(args: argparse.Namespace) -> None:
    command = args.fat_command or "status"
    if command == "tui":
        code = run_terminal_cli()
        if code:
            raise SystemExit(code)
        return
    
    if command == "gui":
        from TerminalAssist.gui import run_gui
        run_gui()
        return
    if command == "status":
        if getattr(args, "json", False):
            print(_pretty_json(terminal_assist_status()))
        else:
            print(build_dashboard(color=not getattr(args, "no_color", False), width=getattr(args, "width", 96)))
        return
    if command == "api":
        print(_pretty_json(terminal_assist_status()))
        return
    if command == "json":
        print(_pretty_json(terminal_assist_status()))
        return
    if command == "layout":
        layout = build_zellij_layout(working_directory=args.working_directory)
        if args.out:
            path = write_zellij_layout(args.out, working_directory=args.working_directory)
            print(f"Wrote fAT Zellij layout to {path}")
        if args.print_layout or not args.out:
            print(layout)
        return
    if command == "run":
        layout_path = write_zellij_layout(args.layout, working_directory=args.working_directory)
        raise SystemExit(run_zellij(layout_path))
    raise SystemExit(f"unknown fAT command: {command}")


def _run_cli_center(args: argparse.Namespace) -> None:
    if args.preview:
        print(build_cli_preview())
        return
    code = run_terminal_cli()
    if code:
        raise SystemExit(code)


def _run_vsee(args: argparse.Namespace) -> None:
    from Vsee.gui import launch_holography

    launch_holography(points_path=args.points, edges_path=args.edges)


def _run_phiconnect(_args: argparse.Namespace) -> None:
    from PhiConnect.gui import launch_phiconnect

    launch_phiconnect()


def _run_seeondesk(args: argparse.Namespace) -> None:
    from SeeOnDesk import (
        active_window_info,
        all_windows_info,
        analyze_screen,
        capture_screen,
        desktop_snapshot,
    )

    if args.seeondesk_command == "active":
        print(_pretty_json(active_window_info().to_dict()))
        return
    if args.seeondesk_command == "list":
        windows = [w.to_dict() for w in all_windows_info()]
        print(_pretty_json({"windows": windows}))
        return
    if args.seeondesk_command == "status":
        print(_pretty_json(desktop_snapshot(include_screenshot=args.screenshot).to_dict()))
        return

    if args.seeondesk_command == "capture":
        if capture_screen(args.out):
            print(f"Screenshot saved to: {args.out}")
        else:
            raise SystemExit("Error: Failed to capture screen.")
        return
    if args.seeondesk_command == "analyze":
        print("Analyzing screen... (this may take a few seconds)")
        print(analyze_screen(args.prompt, image_path=args.image))
        return
    raise SystemExit(f"unknown SeeOnDesk command: {args.seeondesk_command}")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def _instruction_text_from_args(args: argparse.Namespace) -> str:
    if args.press:
        return instruction_to_text(press_instruction(args.press))
    return instruction_to_text(instruction_from_text(args.instruction_json))


def _write_or_print(data: dict[str, Any], path: Path | None, *, label: str) -> None:
    if path is None:
        print(_pretty_json(data))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_pretty_json(data) + "\n", encoding="utf-8")
    print(f"Wrote {label} keys to {path}")


def _pretty_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
