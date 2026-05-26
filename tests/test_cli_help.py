from __future__ import annotations

import contextlib
import io
import sys
import unittest
from unittest.mock import patch

from fiona.cli import main


class FionaCliHelpTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = 0
        with patch.object(sys, "argv", ["fiona", *args]), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                main()
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_top_level_help_shows_fiona_grid(self) -> None:
        code, stdout, stderr = self._run_cli("--help")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Fiona umbrella CLI", stdout)
        self.assertIn("fiona quiktieper ...", stdout)
        self.assertIn("seeondesk", stdout)
        self.assertIn("phiconnect", stdout)

    def test_seeondesk_help_shows_awareness_commands(self) -> None:
        code, stdout, stderr = self._run_cli("seeondesk", "help")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("usage: fiona seeondesk", stdout)
        self.assertIn("active", stdout)
        self.assertIn("status", stdout)

    def test_help_word_maps_to_top_level_help(self) -> None:
        code, stdout, _stderr = self._run_cli("help")

        self.assertEqual(code, 0)
        self.assertIn("Command groups:", stdout)

    def test_layer_help_word_maps_to_layer_help(self) -> None:
        code, stdout, stderr = self._run_cli("host", "help")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("usage: fiona host", stdout)
        self.assertIn("install-service", stdout)

    def test_quiktieper_help_stays_under_quiktieper(self) -> None:
        code, stdout, stderr = self._run_cli("quiktieper", "help")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Launch apps and focused-app shortcuts", stdout)
        self.assertIn("normalize-app-cmds", stdout)


if __name__ == "__main__":
    unittest.main()
