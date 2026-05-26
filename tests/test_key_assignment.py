from __future__ import annotations

import unittest

from QuikTieper.key_assignment import assign_missing_launch_keys


class KeyAssignmentTests(unittest.TestCase):
    def test_assigns_unique_launch_keys_without_changing_existing(self) -> None:
        config = {
            "apps": [
                {"name": "brave", "launch": {"keys": ["alt", "b", "r", "v"], "cmd": "brave"}, "shortcuts": []},
                {"name": "Konsole", "launch": {"keys": [], "cmd": "konsole"}, "shortcuts": []},
                {"name": "Kate", "launch": {"keys": [], "cmd": "kate"}, "shortcuts": []},
            ]
        }

        assigned, changed = assign_missing_launch_keys(config)

        keys = [tuple(app["launch"]["keys"]) for app in assigned["apps"]]
        self.assertEqual(changed, 2)
        self.assertEqual(keys[0], ("alt", "b", "r", "v"))
        self.assertEqual(len({frozenset(key_set) for key_set in keys}), 3)
        self.assertTrue(all(len(key_set) == 4 for key_set in keys))

    def test_generated_keys_use_safe_letters(self) -> None:
        config = {"apps": [{"name": "Super Text App", "launch": {"keys": [], "cmd": "app"}, "shortcuts": []}]}

        assigned, _changed = assign_missing_launch_keys(config)

        self.assertEqual(assigned["apps"][0]["launch"]["keys"][0], "alt")
        self.assertNotIn("s", assigned["apps"][0]["launch"]["keys"])
        self.assertNotIn("t", assigned["apps"][0]["launch"]["keys"])
        self.assertEqual(len(set(assigned["apps"][0]["launch"]["keys"])), 4)

    def test_reassign_repairs_duplicate_key_sets(self) -> None:
        config = {
            "apps": [
                {"name": "brave", "launch": {"keys": ["alt", "b", "r", "v"], "cmd": "brave"}, "shortcuts": []},
                {"name": "Ark", "launch": {"keys": ["alt", "a", "r", "k"], "cmd": "ark"}, "shortcuts": []},
                {"name": "Akregator", "launch": {"keys": ["alt", "a", "k", "r"], "cmd": "akregator"}, "shortcuts": []},
            ]
        }

        assigned, changed = assign_missing_launch_keys(config, reassign=True)

        identities = [frozenset(app["launch"]["keys"]) for app in assigned["apps"]]
        self.assertEqual(changed, 2)
        self.assertEqual(len(set(identities)), 3)
        self.assertEqual(assigned["apps"][0]["launch"]["keys"], ["alt", "b", "r", "v"])


if __name__ == "__main__":
    unittest.main()
