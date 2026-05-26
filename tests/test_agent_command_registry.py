from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from FionaAgent import command_registry
from QuikTieper.config import save_config


class AgentCommandRegistryTests(unittest.TestCase):
    def test_registry_lists_actions_and_available_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "bindings.json"
            save_config(
                {
                    "apps": [
                        {
                            "name": "terminal",
                            "launch": {"name": "launch", "keys": ["alt", "t", "e", "r"], "cmd": "konsole"},
                            "shortcuts": [],
                        }
                    ]
                },
                config_path,
            )

            registry = command_registry(config_path)

        command_names = {command["name"] for command in registry["commands"]}
        self.assertIn("press", command_names)
        self.assertIn("macro", command_names)
        self.assertEqual(registry["apps"], [{"name": "terminal", "command": "konsole"}])


if __name__ == "__main__":
    unittest.main()
