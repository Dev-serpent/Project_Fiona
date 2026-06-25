from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class FionaCliCommandSurfaceTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    _BOOTSTRAP = textwrap.dedent(
        """
        import contextlib
        import io
        import json
        import sys
        import types
        from pathlib import Path

        root = Path(sys.argv[1])
        argv = json.loads(sys.argv[2])

        # Avoid importing the real package initializer, which eagerly loads
        # GUI-heavy modules that are not available in every test environment.
        fiona_pkg = types.ModuleType("fiona")
        fiona_pkg.__path__ = [str(root / "fiona")]
        sys.modules["fiona"] = fiona_pkg

        terminal_assist = types.ModuleType("TerminalAssist")
        terminal_assist.__path__ = []
        terminal_assist.build_cli_preview = lambda: "preview"
        terminal_assist.build_dashboard = lambda *args, **kwargs: "dashboard"
        terminal_assist.build_zellij_layout = lambda *args, **kwargs: "layout"
        terminal_assist.run_terminal_cli = lambda *args, **kwargs: 0
        terminal_assist.terminal_assist_status = lambda *args, **kwargs: {"ok": True, "mem": {}, "os": {}}

        def write_zellij_layout(path, **kwargs):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("layout\\n", encoding="utf-8")
            return path

        terminal_assist.write_zellij_layout = write_zellij_layout
        sys.modules["TerminalAssist"] = terminal_assist

        terminal_assist_dashboard = types.ModuleType("TerminalAssist.dashboard")
        terminal_assist_dashboard.run_zellij = lambda *args, **kwargs: 0
        sys.modules["TerminalAssist.dashboard"] = terminal_assist_dashboard

        terminal_assist_gui = types.ModuleType("TerminalAssist.gui")
        terminal_assist_gui.run_gui = lambda *args, **kwargs: None
        sys.modules["TerminalAssist.gui"] = terminal_assist_gui

        terminal_assist_tui = types.ModuleType("TerminalAssist.tui")
        terminal_assist_tui.build_cli_preview = terminal_assist.build_cli_preview
        terminal_assist_tui.build_dashboard = terminal_assist.build_dashboard
        terminal_assist_tui.run_terminal_cli = terminal_assist.run_terminal_cli
        terminal_assist_tui.terminal_assist_status = terminal_assist.terminal_assist_status
        terminal_assist_tui.write_zellij_layout = terminal_assist.write_zellij_layout
        sys.modules["TerminalAssist.tui"] = terminal_assist_tui

        sys.path.insert(0, str(root))
        from fiona.cli import main

        results = []
        original_argv = list(sys.argv)
        for command in argv:
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = 0
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    sys.argv = ["fiona", *command]
                    try:
                        main()
                    except SystemExit as exc:
                        if isinstance(exc.code, int):
                            code = exc.code
                        elif exc.code is None:
                            code = 0
                        else:
                            code = 1
                finally:
                    sys.argv = list(original_argv)
            results.append({
                "argv": command,
                "code": code,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
            })

        print(json.dumps(results))
        """
    )

    def _run_cli_batch(self, commands: list[tuple[str, ...]], cwd: Path | None = None) -> list[dict[str, object]]:
        env = os.environ.copy()
        env["PYTHONPATH"] = (
            str(self.ROOT)
            if not env.get("PYTHONPATH")
            else str(self.ROOT) + os.pathsep + env["PYTHONPATH"]
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                self._BOOTSTRAP,
                str(self.ROOT),
                json.dumps([[str(arg) for arg in command] for command in commands]),
            ],
            cwd=cwd or self.ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        return [dict(item) for item in json.loads(result.stdout)]

    def test_every_command_node_accepts_help(self) -> None:
        help_paths: list[tuple[str, ...]] = [
            (),
            ("quiktieper",),
            ("qt",),
            ("host",),
            ("agent",),
            ("dataclient",),
            ("data",),
            ("action",),
            ("voice",),
            ("macro",),
            ("recall",),
            ("fat",),
            ("terminal-assist",),
            ("cli",),
            ("api",),
            ("run-shell",),
            ("seeondesk",),
            ("sod",),
            ("vsee",),
            ("ficad",),
            ("cad",),
            ("browser",),
            ("br",),
            ("approval",),
            ("phiconnect",),
            ("camcoms",),
            ("cc",),
        ]

        results = self._run_cli_batch([((*path, "help") if path else ("help",)) for path in help_paths])
        for path, result in zip(help_paths, results, strict=True):
            with self.subTest(path=path):
                self.assertEqual(result["code"], 0, msg=f"{path}\nSTDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}")
                self.assertNotIn("Traceback", str(result["stdout"]))
                self.assertNotIn("Traceback", str(result["stderr"]))

    def test_safe_commands_execute_without_tracebacks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fiona-cli-smoke-") as tmpdir:
            tmp = Path(tmpdir)

            host_config = tmp / "host-config.json"
            qt_config = tmp / "quiktieper.json"
            trace_path = tmp / "trace.jsonl"
            macros_path = tmp / "macros.json"
            recall_path = tmp / "recall.json"
            csv_input = tmp / "input.csv"
            csv_output = tmp / "output.json"
            csv_input.write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")

            sender_private = tmp / "sender-private.json"
            sender_public = tmp / "sender-public.json"
            recipient_private = tmp / "recipient-private.json"
            recipient_public = tmp / "recipient-public.json"

            smoke_commands: list[tuple[str, ...]] = [
                ("api",),
                ("host", "init", "--config", str(host_config)),
                ("host", "status", "--config", str(host_config)),
                ("qt", "--config", str(qt_config), "init"),
                ("qt", "--config", str(qt_config), "list"),
                ("cc", "paths"),
                ("cc", "keygen", "--device-id", "sender", "--private-out", str(sender_private), "--public-out", str(sender_public)),
                ("cc", "keygen", "--device-id", "recipient", "--private-out", str(recipient_private), "--public-out", str(recipient_public)),
                ("cc", "smoke-test"),
                ("action", "run", "host.status", "--dry-run", "--trace-path", str(trace_path)),
                ("macro", "save", "demo", "host.status", "camcoms.smoke", "--path", str(macros_path)),
                ("macro", "run", "demo", "--dry-run", "--path", str(macros_path), "--trace-path", str(trace_path)),
                ("recall", "remember", "key", "value", "--path", str(recall_path)),
                ("recall", "search", "key", "--path", str(recall_path)),
                ("dataclient", "view", str(csv_input)),
                ("dataclient", "convert", str(csv_input), "--out", str(csv_output)),
                ("agent", "commands"),
                ("agent", "status"),
                ("voice", "parse", "show", "host", "status"),
                ("voice", "run", "show", "host", "status", "--dry-run", "--trace-path", str(trace_path)),
                ("voice", "wake-test"),
                ("fat", "status", "--json"),
                ("cli", "--preview"),
                ("seeondesk", "status"),
                ("browser", "status"),
                ("approval", "pending"),
                ("cad", "--headless", "info"),
            ]

            results = self._run_cli_batch(smoke_commands)
            for args, result in zip(smoke_commands, results, strict=True):
                with self.subTest(args=args):
                    self.assertEqual(
                        result["code"],
                        0,
                        msg=f"{' '.join(args)}\nSTDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}",
                    )
                    self.assertNotIn("Traceback", str(result["stdout"]))
                    self.assertNotIn("Traceback", str(result["stderr"]))
                    if args[:2] == ("cc", "keygen"):
                        self.assertTrue(sender_private.exists())
                        self.assertTrue(sender_public.exists())
                    if args == ("browser", "status"):
                        payload = json.loads(result["stdout"])
                        self.assertEqual(payload["state"], "stopped")
                        self.assertIn("config", payload)
                        self.assertIn("browser_type", payload["config"])
                        self.assertIn("headless", payload["config"])
                        self.assertIn("viewport_width", payload["config"])
                        self.assertIn("viewport_height", payload["config"])


if __name__ == "__main__":
    unittest.main()
