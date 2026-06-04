from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from CamComs import DEFAULT_FIONA_CONFIG_PATH, DEFAULT_TRUSTED_DIR, private_key_path

RESET = "\033[0m"
CYAN = "\033[38;5;51m"
BLUE = "\033[38;5;39m"
GREEN = "\033[38;5;48m"
YELLOW = "\033[38;5;220m"
RED = "\033[38;5;203m"
DIM = "\033[38;5;245m"
BOLD = "\033[1m"
WHITE = "\033[38;5;255m"


@dataclass(frozen=True)
class FatPanel:
    title: str
    rows: tuple[str, ...]


def get_cpu_load() -> str:
    try:
        with open("/proc/loadavg", "r") as f:
            load = f.read().split()[:3]
            return " / ".join(load)
    except Exception:
        return "unknown"


def get_mem_info() -> str:
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
            total = 0
            avail = 0
            for line in lines:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
            if total > 0:
                used = total - avail
                percent = (used / total) * 100
                return f"{used // 1024}MB / {total // 1024}MB ({percent:.1f}%)"
    except Exception:
        pass
    return "unknown"


def get_uptime() -> str:
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    except Exception:
        return "unknown"


def get_disk_usage() -> str:
    try:
        usage = shutil.disk_usage("/")
        used = usage.used // (1024**3)
        total = usage.total // (1024**3)
        percent = (usage.used / usage.total) * 100
        return f"{used}GB / {total}GB ({percent:.1f}%)"
    except Exception:
        return "unknown"


def get_os_info() -> str:
    try:
        with open("/etc/os-release", "r") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=")[1].strip().strip('"')
    except Exception:
        pass
    return os.uname().sysname


def terminal_assist_status() -> dict[str, object]:
    zellij_path = shutil.which("zellij")
    python_executable = sys.executable
    checks = {
        "host_config": DEFAULT_FIONA_CONFIG_PATH.exists(),
        "host_private_key": private_key_path("host").exists(),
        "trusted_senders": DEFAULT_TRUSTED_DIR.exists(),
        "zellij": bool(zellij_path),
    }
    return {
        "ready": all(checks.values()),
        "zellij_path": zellij_path,
        "python": python_executable,
        "checks": checks,
        "cpu": get_cpu_load(),
        "mem": get_mem_info(),
        "disk": get_disk_usage(),
        "uptime": get_uptime(),
        "os": get_os_info(),
        "user": os.getlogin(),
        "commands": [
            "fiona fat status",
            "fiona fat layout --print",
            "fiona fat run",
        ],
    }


def build_dashboard(*, color: bool = True, width: int = 96, height: int = 24) -> str:
    status = terminal_assist_status()
    checks = status["checks"]
    assert isinstance(checks, dict)
    
    # Header bar
    rendered = [_paint(f" fAT Dashboard ".center(width, "━"), CYAN + BOLD, color)]
    
    # System info row
    sys_line = (
        f" CPU: {status['cpu']} "
        f"│ MEM: {status['mem']} "
        f"│ DISK: {status['disk']} "
    )
    rendered.append(_paint("┏" + "━" * (width - 2) + "┓", BLUE, color))
    rendered.append("┃ " + _paint(sys_line.ljust(width - 4), GREEN, color) + " ┃")
    rendered.append(_paint("┣" + "━" * (width - 2) + "┫", BLUE, color))
    
    # Main content panels
    remaining_height = height - 5
    
    panels = [
        FatPanel(
            "FIONA ENVIRONMENT",
            (
                f"User:        {status['user']}",
                f"OS:          {status['os']}",
                f"Architecture: {os.uname().machine}",
                f"Uptime:      {status['uptime']}",
                f"Python Path: {status['python']}",
                f"Zellij Bin:  {status['zellij_path'] or 'not found'}",
                f"System Ready: {'yes' if status['ready'] else 'partial'}",
            ),
        ),
        FatPanel(
            "CORE COMPONENTS",
            (
                _check_row("Config File", bool(checks["host_config"])),
                _check_row("Private Key", bool(checks["host_private_key"])),
                _check_row("Trust Store", bool(checks["trusted_senders"])),
                _check_row("Zellij Link", bool(checks["zellij"])),
            ),
        ),
    ]

    # Add a dynamic 'Action Statistics' panel if space permits
    if remaining_height > 12:
        from CmdTrace import read_trace
        history = read_trace(limit=5)
        stats_rows = []
        if history:
            for event in history:
                ok_str = "OK" if event.get("ok") else "FAIL"
                stats_rows.append(f"{event.get('action', '???')}: {ok_str} ({event.get('elapsed_ms', 0)}ms)")
        else:
            stats_rows.append("(no recent actions)")
        panels.append(FatPanel("RECENT ACTIVITY", tuple(stats_rows)))

    for i, panel in enumerate(panels):
        # Render panel title
        rendered.append("┃ " + _paint(f" {panel.title} ".ljust(width - 4, "─"), WHITE + BOLD, color) + " ┃")
        # Render rows
        for row in panel.rows:
            rendered.append(_row(row, inner_width=width - 4, color=color))
        
        # If not the last panel, maybe add a separator or empty space to fill height
        # For simplicity, we just add the rows. If we want true fullscreen filling, 
        # we'd need to calculate padding per panel.
        if i < len(panels) - 1:
             rendered.append("┃ " + " " * (width - 4) + " ┃")
    
    # Pad to height
    current_len = len(rendered)
    if current_len < height - 1:
        for _ in range(height - 1 - current_len):
            rendered.append("┃ " + " " * (width - 4) + " ┃")

    rendered.append(_paint("┗" + "━" * (width - 2) + "┛", BLUE, color))
    return "\n".join(rendered)


def build_zellij_layout(*, python_executable: str | None = None, working_directory: Path | None = None) -> str:
    python_executable = python_executable or sys.executable
    working_directory = working_directory or Path.cwd()
    cwd = _kdl_string(str(working_directory))
    py = _kdl_string(python_executable)
    return "\n".join(
        [
            "layout {",
            "    pane size=1 borderless=true {",
            '        plugin location="tab-bar"',
            "    }",
            f"    cwd {cwd}",
            '    pane split_direction="vertical" {',
            '        pane split_direction="horizontal" {',
            f"            pane command={py} name=\"fAT\" {{",
            '                args "-m" "fiona.cli" "fat" "status"',
            "            }",
            f"            pane command={py} name=\"Host\" {{",
            '                args "-m" "fiona.cli" "host" "status"',
            "            }",
            "        }",
            '        pane split_direction="horizontal" {',
            f"            pane command={py} name=\"CamComs\" {{",
            '                args "-m" "fiona.cli" "camcoms" "paths"',
            "            }",
            f"            pane command={py} name=\"SeeOnDesk\" {{",
            '                args "-m" "fiona.cli" "seeondesk" "status"',
            "            }",
            "        }",
            "    }",
            "    pane size=1 borderless=true {",
            '        plugin location="status-bar"',
            "    }",
            "}",
            "",
        ]
    )


def write_zellij_layout(path: Path, *, python_executable: str | None = None, working_directory: Path | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        build_zellij_layout(python_executable=python_executable, working_directory=working_directory),
        encoding="utf-8",
    )
    return path


def run_zellij(layout_path: Path) -> int:
    zellij = shutil.which("zellij")
    if not zellij:
        raise RuntimeError("zellij is not installed or is not on PATH")
    return subprocess.call([zellij, "--layout", str(layout_path)])


def _check_row(label: str, ok: bool) -> str:
    return f"{label}: {'ok' if ok else 'missing'}"


def _header(text: str, *, width: int, color: bool) -> str:
    title = f" {text} "
    line = title.center(width, "━")
    return _paint(line, CYAN + BOLD, color)


def _footer(*, width: int, color: bool) -> str:
    return _paint("━" * width, BLUE, color)


def _render_panel(panel: FatPanel, *, width: int, color: bool) -> str:
    inner_width = max(24, width - 4)
    top = "┏" + "━" * (width - 2) + "┓"
    title = f"┃ {_paint(panel.title, GREEN + BOLD, color)}".ljust(_visible_pad(width - 1, panel.title)) + "┃"
    rows = [_row(row, inner_width=inner_width, color=color) for row in panel.rows]
    bottom = "┗" + "━" * (width - 2) + "┛"
    return "\n".join([_paint(top, BLUE, color), title, *rows, _paint(bottom, BLUE, color)])


def _row(text: str, *, inner_width: int, color: bool) -> str:
    colored = _color_status(text, color)
    visible_text = _strip_known_ansi(colored)
    padding = max(0, inner_width - len(visible_text))
    return f"┃ {colored}{' ' * padding} ┃"


def _color_status(text: str, color: bool) -> str:
    if not color:
        return text
    if text.endswith(": ok"):
        return text[:-2] + GREEN + "ok" + RESET
    if text.endswith(": missing"):
        return text[:-7] + RED + "missing" + RESET
    if text.endswith("partial"):
        return text[:-7] + YELLOW + "partial" + RESET
    return _paint(text, DIM, color)


def _paint(text: str, ansi: str, color: bool) -> str:
    return f"{ansi}{text}{RESET}" if color else text


def _visible_pad(width: int, text: str) -> int:
    return width + len(text) - len(_strip_known_ansi(text))


def _strip_known_ansi(text: str) -> str:
    for code in (RESET, CYAN, BLUE, GREEN, YELLOW, RED, DIM, BOLD):
        text = text.replace(code, "")
    return text


def _kdl_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
