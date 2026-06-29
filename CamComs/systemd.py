from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from CamComs.service import DEFAULT_FIONA_CONFIG_PATH


DEFAULT_SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
DEFAULT_SERVICE_NAME = "fiona-host.service"


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
    allowed_actions = {"enable", "disable", "restart", "start", "stop"}
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
