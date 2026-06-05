import unittest
import subprocess
import json
import sys
import os
from pathlib import Path

class FionaCliIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.env_dir = Path("tests/testing_env")
        self.env_dir.mkdir(parents=True, exist_ok=True)
        self.python = sys.executable
        self.cli_base = [self.python, "-m", "fiona.cli"]

    def _run_cmd(self, args):
        result = subprocess.run(
            self.cli_base + args,
            capture_output=True,
            text=True,
            check=False
        )
        return result

    def test_api_command_returns_valid_json(self):
        result = self._run_cmd(["api"])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("hostname", data)
            self.assertIn("cpu_usage", data)
            self.assertIn("mouse_x", data)
        except json.JSONDecodeError:
            self.fail("fiona api did not return valid JSON")

    def test_fat_status_json_returns_valid_json(self):
        result = self._run_cmd(["fat", "status", "--json"])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("mem", data)
            self.assertIn("os", data)
        except json.JSONDecodeError:
            self.fail("fiona fat status --json did not return valid JSON")

    def test_action_list_returns_valid_json(self):
        result = self._run_cmd(["action", "list"])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("actions", data)
            self.assertIsInstance(data["actions"], list)
        except json.JSONDecodeError:
            self.fail("fiona action list did not return valid JSON")

    def test_macro_list_returns_valid_json(self):
        result = self._run_cmd(["macro", "list"])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("macros", data)
        except json.JSONDecodeError:
            self.fail("fiona macro list did not return valid JSON")

    def test_recall_list_returns_valid_json(self):
        # Use a temporary recall path in testing_env
        recall_path = self.env_dir / "test_recall.json"
        result = self._run_cmd(["recall", "list", "--path", str(recall_path)])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("entries", data)
        except json.JSONDecodeError:
            self.fail("fiona recall list did not return valid JSON")

    def test_camcoms_paths_returns_paths(self):
        result = self._run_cmd(["camcoms", "paths"])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("camcoms_dir", data)
            self.assertIn("host_private", data)
        except json.JSONDecodeError:
            self.fail("fiona camcoms paths did not return valid JSON")

    def test_seeondesk_status_returns_json(self):
        result = self._run_cmd(["seeondesk", "status"])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("session_type", data)
            self.assertIn("active_window", data)
        except json.JSONDecodeError:
            self.fail("fiona seeondesk status did not return valid JSON")

    def test_agent_status_returns_json(self):
        result = self._run_cmd(["agent", "status"])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("base_url", data)
            # Should have either 'models' (if running) or 'available': False (if not)
            self.assertTrue("models" in data or "available" in data)
        except json.JSONDecodeError:
            self.fail("fiona agent status did not return valid JSON")

    def test_eyecontrol_status_returns_json(self):
        result = self._run_cmd(["eyecontrol", "status"])
        self.assertEqual(result.returncode, 0)
        try:
            data = json.loads(result.stdout)
            self.assertIn("dependencies", data)
            # Check for common dependencies
            deps = data["dependencies"]
            self.assertIn("cv2", deps)
            self.assertIn("numpy", deps)
        except json.JSONDecodeError:
            self.fail("fiona eyecontrol status did not return valid JSON")

if __name__ == "__main__":
    unittest.main()
