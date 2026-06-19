"""
Host service lifecycle management.

Linux: systemd user units via ``systemctl`` / ``journalctl``.
Windows: Startup-folder ``.bat`` shortcut (no systemd equivalent).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from CamComs.service import DEFAULT_FIONA_CONFIG_PATH


DEFAULT_SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
DEFAULT_SERVICE_NAME = "fiona-host.service"


# ---------------------------------------------------------------------------
# Linux — systemd
# ---------------------------------------------------------------------------

def render_host_service_unit(
    *,
    python_executable: str = sys.executable,
    working_directory: Path | None = None,
    config_path: Path = DEFAULT_FIONA_CONFIG_PATH,
) -> str:
    cwd = working_directory or Path.cwd()
    return f"""[Unit]
Description=Fiona host service
After=default.target

[Service]
Type=simple
WorkingDirectory={cwd}
ExecStart={python_executable} -m fiona.cli host run --config {config_path}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def service_unit_path(service_name: str = DEFAULT_SERVICE_NAME) -> Path:
    return DEFAULT_SYSTEMD_USER_DIR / service_name


def install_host_service_unit(
    *,
    service_name: str = DEFAULT_SERVICE_NAME,
    python_executable: str = sys.executable,
    working_directory: Path | None = None,
    config_path: Path = DEFAULT_FIONA_CONFIG_PATH,
) -> Path:
    path = service_unit_path(service_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_host_service_unit(
            python_executable=python_executable,
            working_directory=working_directory,
            config_path=config_path,
        ),
        encoding="utf-8",
    )
    return path


def run_user_service_command(action: str, *, service_name: str = DEFAULT_SERVICE_NAME) -> subprocess.CompletedProcess[str]:
    allowed_actions = {"enable", "disable", "restart", "stop"}
    if action not in allowed_actions:
        raise ValueError(f"unsupported service action: {action}")

    if action == "enable":
        args = ["systemctl", "--user", "enable", "--now", service_name]
    else:
        args = ["systemctl", "--user", action, service_name]
    return subprocess.run(args, check=True, text=True, capture_output=True)


def read_host_service_logs(
    *,
    service_name: str = DEFAULT_SERVICE_NAME,
    lines: int = 80,
    follow: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = ["journalctl", "--user", "-u", service_name, "-n", str(lines), "--no-pager"]
    if follow:
        args.append("-f")
    return subprocess.run(args, check=True, text=True, capture_output=not follow)


# ---------------------------------------------------------------------------
# Windows — Startup-folder shortcut
# ---------------------------------------------------------------------------

def manage_windows_startup(action: str) -> None:
    """Enable or disable Fiona auto-start on Windows.

    Args:
        action: ``"enable"`` or ``"disable"``.

    Raises:
        RuntimeError: If ``APPDATA`` is not set (not on Windows).
        ValueError: If *action* is not supported.
    """
    if action not in ("enable", "disable"):
        raise ValueError(f"unsupported startup action: {action}")

    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is not set — not running on Windows")

    startup_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    bat_path = startup_dir / "fiona-host.bat"

    if action == "disable":
        if bat_path.exists():
            bat_path.unlink()
        return

    # enable — write a silent batch wrapper
    python_exe = sys.executable
    config_path = Path.home() / ".config" / "fiona" / "config.json"

    if getattr(sys, "frozen", False):
        bat_content = (
            f'@echo off\n'
            f'start "" "{python_exe}" host run --config "{config_path}"\n'
        )
    else:
        bat_content = (
            f'@echo off\n'
            f'start "" "{python_exe}" -m fiona.cli host run --config "{config_path}"\n'
        )

    startup_dir.mkdir(parents=True, exist_ok=True)
    bat_path.write_text(bat_content, encoding="utf-8")
