from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from unittest.mock import patch

from EyeControl import EyeTrackerConfig, dependency_status
from fiona.cli import main


class EyeControlTests(unittest.TestCase):
    def test_dependency_status_is_safe_without_camera(self) -> None:
        status = dependency_status()

        self.assertIn("ready", status)
        self.assertTrue(status["requires_camera"])
        self.assertIn("cv2", status["dependencies"])
        self.assertIn("mediapipe", status["dependencies"])

    def test_cli_status_prints_dependency_status(self) -> None:
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["fiona", "eyecontrol", "status"]), contextlib.redirect_stdout(stdout):
            main()

        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["requires_camera"])
        self.assertIn("pyautogui", payload["dependencies"])

    def test_cli_run_builds_config_without_starting_real_tracker(self) -> None:
        captured: list[EyeTrackerConfig] = []

        def fake_run(config: EyeTrackerConfig) -> None:
            captured.append(config)

        with (
            patch.object(sys, "argv", ["fiona", "eyecontrol", "run", "--camera-index", "0", "--no-click"]),
            patch("fiona.cli.run_eye_tracker", side_effect=fake_run),
        ):
            main()

        self.assertEqual(captured[0].camera_index, 0)
        self.assertFalse(captured[0].enable_clicks)


if __name__ == "__main__":
    unittest.main()
