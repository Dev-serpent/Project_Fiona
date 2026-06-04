from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliRecallTraceTests(unittest.TestCase):
    def test_recall_forget_and_clear_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            # remember
            subprocess.run(
                [sys.executable, "-m", "fiona.cli", "recall", "remember", "key1", "val1", "--path", str(path)],
                check=True,
                capture_output=True,
            )
            self.assertTrue(path.exists())

            # forget
            result = subprocess.run(
                [sys.executable, "-m", "fiona.cli", "recall", "forget", "key1", "--path", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Forgot key1", result.stdout)

            # clear
            subprocess.run(
                [sys.executable, "-m", "fiona.cli", "recall", "remember", "key2", "val2", "--path", str(path)],
                check=True,
                capture_output=True,
            )
            self.assertTrue(path.exists())
            result = subprocess.run(
                [sys.executable, "-m", "fiona.cli", "recall", "clear", "--path", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Cleared", result.stdout)
            self.assertFalse(path.exists())

    def test_action_clear_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            # create trace via some action
            subprocess.run(
                [sys.executable, "-m", "fiona.cli", "action", "run", "fat.status", "--dry-run", "--trace-path", str(path)],
                check=True,
                capture_output=True,
            )
            self.assertTrue(path.exists())

            # clear
            result = subprocess.run(
                [sys.executable, "-m", "fiona.cli", "action", "clear", "--trace-path", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Cleared", result.stdout)
            self.assertFalse(path.exists())

    def test_recall_categories_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            subprocess.run(
                [sys.executable, "-m", "fiona.cli", "recall", "remember", "k1", "v1", "--category", "catA", "--path", str(path)],
                check=True, capture_output=True,
            )
            subprocess.run(
                [sys.executable, "-m", "fiona.cli", "recall", "remember", "k2", "v2", "--category", "catB", "--path", str(path)],
                check=True, capture_output=True,
            )

            result = subprocess.run(
                [sys.executable, "-m", "fiona.cli", "recall", "categories", "--path", str(path)],
                check=True, capture_output=True, text=True,
            )
            data = json.loads(result.stdout)
            self.assertEqual(data["categories"], ["catA", "catB"])

    def test_action_history_filtering_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            # run two different actions
            subprocess.run(
                [sys.executable, "-m", "fiona.cli", "action", "run", "fat.status", "--dry-run", "--trace-path", str(path)],
                check=True, capture_output=True,
            )
            subprocess.run(
                [sys.executable, "-m", "fiona.cli", "action", "run", "host.status", "--dry-run", "--trace-path", str(path)],
                check=True, capture_output=True,
            )

            # history for fat.status only
            result = subprocess.run(
                [sys.executable, "-m", "fiona.cli", "action", "history", "--name", "fat.status", "--trace-path", str(path)],
                check=True, capture_output=True, text=True,
            )
            data = json.loads(result.stdout)
            self.assertEqual(len(data["events"]), 1)
            self.assertEqual(data["events"][0]["action"], "fat.status")


if __name__ == "__main__":
    unittest.main()
