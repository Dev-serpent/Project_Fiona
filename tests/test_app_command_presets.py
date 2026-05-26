from __future__ import annotations

import unittest
from unittest.mock import patch

from QuikTieper.app_command_presets import apply_app_command_presets


class AppCommandPresetsTests(unittest.TestCase):
    def test_updates_existing_aliases_and_adds_missing_apps(self) -> None:
        config = {
            "apps": [
                {
                    "name": "terminal",
                    "window_match": "gnome-terminal",
                    "launch": {"name": "launch", "keys": ["alt", "t", "e", "r"], "cmd": "gnome-terminal"},
                    "shortcuts": [],
                },
                {
                    "name": "GNU Image Manipulation Program",
                    "window_match": "gimp-3.2",
                    "launch": {"name": "launch", "keys": ["alt", "g", "i", "m"], "cmd": "gimp-3.2"},
                    "shortcuts": [],
                },
            ]
        }

        with patch("QuikTieper.app_command_presets.shutil.which", return_value="/usr/bin/app"):
            updated, changes, added, assigned_keys = apply_app_command_presets(config)

        apps = {app["name"]: app for app in updated["apps"]}
        self.assertEqual(apps["terminal"]["launch"]["cmd"], "konsole")
        self.assertEqual(apps["GNU Image Manipulation Program"]["launch"]["cmd"], "gimp")
        self.assertIn("Jupyter Notebook", apps)
        self.assertGreaterEqual(added, 1)
        self.assertGreaterEqual(assigned_keys, added)
        self.assertTrue(any(change["app"] == "terminal" for change in changes))

    def test_preserves_existing_full_path_when_preferred_command_is_missing(self) -> None:
        config = {
            "apps": [
                {
                    "name": "LM Studio (0.3.39)",
                    "window_match": "lmstudio",
                    "launch": {
                        "name": "launch",
                        "keys": ["alt", "l", "m", "s"],
                        "cmd": "/tmp/lm-studio.AppImage --no-sandbox",
                    },
                    "shortcuts": [],
                }
            ]
        }

        def fake_which(executable: str) -> str | None:
            return None

        with patch("QuikTieper.app_command_presets.shutil.which", side_effect=fake_which), patch(
            "QuikTieper.app_command_presets.Path.exists", return_value=True
        ):
            updated, _changes, _added, _assigned_keys = apply_app_command_presets(config)

        apps = {app["name"]: app for app in updated["apps"]}
        self.assertEqual(apps["LM Studio (0.3.39)"]["launch"]["cmd"], "/tmp/lm-studio.AppImage --no-sandbox")


if __name__ == "__main__":
    unittest.main()
