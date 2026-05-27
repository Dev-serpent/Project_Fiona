from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fiona.cli import main


class DataClientCliTests(unittest.TestCase):
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

    def test_dataclient_convert_json_to_csv_and_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "data.json"
            output = root / "data.csv"
            source.write_text(json.dumps([{"name": "Ada", "score": "10"}, {"name": "Grace", "score": "20"}]), encoding="utf-8")

            convert_code, convert_stdout, convert_stderr = self._run_cli("dataclient", "convert", str(source), "--out", str(output))
            view_code, view_stdout, view_stderr = self._run_cli("dataclient", "view", str(output), "--limit", "1")

        self.assertEqual(convert_code, 0)
        self.assertEqual(convert_stderr, "")
        self.assertIn("Converted", convert_stdout)
        self.assertEqual(view_code, 0)
        self.assertEqual(view_stderr, "")
        preview = json.loads(view_stdout)
        self.assertEqual(preview["total_rows"], 2)
        self.assertEqual(preview["rows"], [{"name": "Ada", "score": "10"}])

    def test_dataclient_view_rejects_unsupported_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "data.txt"
            source.write_text("bad", encoding="utf-8")

            with self.assertRaises(ValueError):
                self._run_cli("dataclient", "view", str(source))


if __name__ == "__main__":
    unittest.main()
