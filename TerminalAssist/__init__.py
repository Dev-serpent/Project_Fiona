"""Fiona Terminal Assistance (fAT)."""

from __future__ import annotations

from .dashboard import FatPanel, build_dashboard, build_zellij_layout, terminal_assist_status, write_zellij_layout
from .gui import run_gui
from .tui import CommandResult, build_cli_preview, command_pages, format_command_output, run_terminal_cli, strip_ansi

__all__ = [
    "CommandResult",
    "FatPanel",
    "build_dashboard",
    "build_cli_preview",
    "build_zellij_layout",
    "command_pages",
    "format_command_output",
    "run_gui",
    "run_terminal_cli",
    "strip_ansi",
    "terminal_assist_status",
    "write_zellij_layout",
]
