from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from CmdTrace import read_trace
from FionaCore import ActionRouter, MacroStep, load_macros, run_macro, save_macro
from FionaCore.notifications import build_notification
from FionaCore.voice import parse_voice_command
from fiona.cli import main


class FionaCoreTests(unittest.TestCase):
    def test_action_router_records_to_cmdtrace_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            router = ActionRouter(trace_path=trace_path)

            result = router.run("host.status", dry_run=True)
            events = read_trace(limit=5, path=trace_path)

        self.assertTrue(result.ok)
        self.assertEqual(result.detail, "dry-run")
        self.assertEqual(events[0]["action"], "host.status")

    def test_permission_denial_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            router = ActionRouter(trace_path=trace_path)

            result = router.run("host.restart", permission_profile="remote_safe")
            events = read_trace(limit=5, path=trace_path)

        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 126)
        self.assertEqual(events[0]["detail"], "permission denied for profile remote_safe")

    def test_voice_parser_maps_practical_phrases(self) -> None:
        command = parse_voice_command("show host status")

        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual(command.action, "host.status")

    def test_macro_round_trip_uses_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            macro_path = Path(tmp) / "macros.json"
            trace_path = Path(tmp) / "trace.jsonl"
            save_macro("startup-check", [MacroStep("host.status"), MacroStep("camcoms.paths")], path=macro_path)

            macros = load_macros(macro_path)
            results = run_macro(
                "startup-check",
                router=ActionRouter(trace_path=trace_path),
                path=macro_path,
                dry_run=True,
            )

        self.assertEqual([step.action for step in macros["startup-check"]], ["host.status", "camcoms.paths"])
        self.assertEqual([result.action for result in results], ["host.status", "camcoms.paths"])

    def test_notification_summary_uses_result_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = ActionRouter(trace_path=Path(tmp) / "trace.jsonl").run("host.status", dry_run=True)

        notification = build_notification(result)

        self.assertIn("OK", notification.title)
        self.assertIn("host.status", notification.title)
        self.assertEqual(notification.body, "dry-run")

    def test_recall_cli_remembers_and_searches_with_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recall_path = Path(tmp) / "recall.json"
            save_out = io.StringIO()
            search_out = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["fiona", "recall", "remember", "phi-host", "127.0.0.1", "--category", "network", "--path", str(recall_path)],
            ), contextlib.redirect_stdout(save_out):
                main()
            with patch.object(
                sys,
                "argv",
                ["fiona", "recall", "search", "network", "--path", str(recall_path)],
            ), contextlib.redirect_stdout(search_out):
                main()

            payload = json.loads(search_out.getvalue())

        self.assertIn("Saved remembrance phi-host", save_out.getvalue())
        self.assertEqual(payload["entries"][0]["key"], "phi-host")
        self.assertEqual(payload["entries"][0]["value"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
