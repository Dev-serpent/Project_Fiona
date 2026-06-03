from __future__ import annotations

import shutil
import subprocess
import sys
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


@dataclass(frozen=True)
class FatPanel:
    title: str
    rows: tuple[str, ...]


def terminal_assist_status() -> dict[str, object]:
    zellij_path = shutil.which("zellij")
    python_executable = sys.executable
    checks = {
        "zellij": bool(zellij_path),
        "host_config": DEFAULT_FIONA_CONFIG_PATH.exists(),
        "host_private_key": private_key_path("host").exists(),
        "trusted_senders": DEFAULT_TRUSTED_DIR.exists(),
    }
    return {
        "ready": all(checks.values()),
        "zellij_path": zellij_path,
        "python": python_executable,
        "checks": checks,
        "commands": [
            "fiona fat status",
            "fiona fat layout --print",
            "fiona fat layout --out /tmp/fiona-fat.kdl",
            "fiona fat run",
        ],
    }


def build_dashboard(*, color: bool = True, width: int = 96) -> str:
    status = terminal_assist_status()
    checks = status["checks"]
    assert isinstance(checks, dict)
    panels = (
        FatPanel(
            "SYSTEM",
            (
                f"Python: {status['python']}",
                f"Zellij: {status['zellij_path'] or 'not found'}",
                f"Ready:  {'yes' if status['ready'] else 'partial'}",
            ),
        ),
        FatPanel(
            "FIONA",
            (
                _check_row("host config", bool(checks["host_config"])),
                _check_row("host key", bool(checks["host_private_key"])),
                _check_row("trusted senders", bool(checks["trusted_senders"])),
                _check_row("zellij binary", bool(checks["zellij"])),
            ),
        ),
        FatPanel(
            "COMMANDS",
            tuple(str(command) for command in status["commands"]),
        ),
    )
    rendered = [_header("fAT / Fiona Terminal Assistance", width=width, color=color)]
    rendered.extend(_render_panel(panel, width=width, color=color) for panel in panels)
    rendered.append(_footer(width=width, color=color))
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
