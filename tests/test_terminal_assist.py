from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from TerminalAssist import (
    CommandResult,
    build_cli_preview,
    build_dashboard,
    build_zellij_layout,
    command_pages,
    format_command_output,
    strip_ansi,
    terminal_assist_status,
    write_zellij_layout,
)
from fiona.cli import main


class TerminalAssistTests(unittest.TestCase):
    def test_status_is_serializable_and_reports_zellij(self) -> None:
        status = terminal_assist_status()

        self.assertIn("ready", status)
        self.assertIn("zellij_path", status)
        self.assertIn("checks", status)

    def test_dashboard_renders_without_color(self) -> None:
        dashboard = build_dashboard(color=False, width=72, height=22)

        self.assertIn("fAT Dashboard", dashboard)
        self.assertIn("FIONA ENVIRONMENT", dashboard)
        self.assertIn("CORE COMPONENTS", dashboard)
        self.assertEqual(len(dashboard.splitlines()), 22)

    def test_command_pages_include_core_surfaces(self) -> None:
        pages = command_pages()
        titles = {page.title for page in pages}

        self.assertIn("Dashboard", titles)
        self.assertIn("Management", titles)
        self.assertIn("QuikTieper", titles)
        self.assertIn("CamComs", titles)
        self.assertIn("Host", titles)
        self.assertIn("Core", titles)
        self.assertIn("Apps", titles)
        self.assertIn("History", titles)
        self.assertIn("Recall", titles)

    def test_command_pages_mark_interactive_actions_external(self) -> None:
        actions = {action.label: action for page in command_pages() for action in page.actions}

        self.assertTrue(actions["System Monitor (btop)"].external)
        self.assertFalse(actions["Host status"].external)
        self.assertTrue(actions["Open editor"].external)
        self.assertTrue(actions["Run listener"].external)
        self.assertTrue(actions["Receiver"].external)

    def test_cli_preview_lists_sliding_pages(self) -> None:
        preview = build_cli_preview(width=72)

        self.assertIn("fAT / Fiona CLI", preview)
        self.assertIn("[Dashboard]", preview)
        self.assertIn("[Management]", preview)
        self.assertIn("[QuikTieper]", preview)
        self.assertIn("fiona camcoms smoke-test", preview)

    def test_format_command_output_combines_stdout_and_stderr(self) -> None:
        result = CommandResult(
            command=("fat", "status"),
            returncode=2,
            stdout="out\n",
            stderr="err\n",
        )

        lines = format_command_output(result)

        self.assertEqual(lines[0], "$ fiona fat status")
        self.assertIn("[exit 2]", lines)
        self.assertIn("out", lines)
        self.assertIn("[stderr]", lines)
        self.assertIn("err", lines)

    def test_strip_ansi_removes_dashboard_escape_codes(self) -> None:
        self.assertEqual(strip_ansi("\033[38;5;51mhello\033[0m"), "hello")

    def test_status_dashboard_action_uses_no_color_inside_tui(self) -> None:
        management = command_pages()[1]
        status_action = [a for a in management.actions if a.label == "Status dashboard"][0]

        self.assertEqual(status_action.label, "Status dashboard")
        self.assertEqual(status_action.command, ("fat", "status", "--no-color"))

    def test_zellij_layout_contains_fiona_panes(self) -> None:
        layout = build_zellij_layout(python_executable="/usr/bin/python3", working_directory=Path("/tmp/fiona"))

        self.assertIn("layout {", layout)
        self.assertIn('cwd "/tmp/fiona"', layout)
        self.assertIn('"fiona.cli" "fat" "status"', layout)
        self.assertIn('"fiona.cli" "host" "status"', layout)
        self.assertIn('"fiona.cli" "camcoms" "paths"', layout)

    def test_write_zellij_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_zellij_layout(Path(tmp) / "fat.kdl", python_executable="/usr/bin/python3")

            self.assertTrue(path.exists())
            self.assertIn("Fiona", path.read_text(encoding="utf-8"))

    def test_cli_fat_status_defaults_without_subcommand(self) -> None:
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["fiona", "fat"]), contextlib.redirect_stdout(stdout):
            main()

        self.assertIn("fAT Dashboard", stdout.getvalue())

    def test_cli_fat_layout_can_print(self) -> None:
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["fiona", "fat", "layout", "--print"]), contextlib.redirect_stdout(stdout):
            main()

        self.assertIn("layout {", stdout.getvalue())

    def test_cli_preview_command_prints_without_curses(self) -> None:
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["fiona", "cli", "--preview"]), contextlib.redirect_stdout(stdout):
            main()

        self.assertIn("fAT / Fiona CLI", stdout.getvalue())

    def test_fat_tui_falls_back_to_preview_without_tty(self) -> None:
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["fiona", "fat", "tui"]), contextlib.redirect_stdout(stdout):
            main()

        self.assertIn("fAT / Fiona CLI", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
