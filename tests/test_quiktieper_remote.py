from __future__ import annotations

import unittest

from QuikTieper.remote import RemoteActionError, RemoteActionRunner


class QuikTieperRemoteTests(unittest.TestCase):
    def test_dry_run_press_instruction(self) -> None:
        runner = RemoteActionRunner(dry_run=True)

        result = runner.run({"version": 1, "type": "press", "keys": ["alt", "s"]})

        self.assertEqual(result.action, "press")
        self.assertEqual(result.detail, "alt+s")
        self.assertFalse(result.executed)

    def test_rejects_disallowed_action(self) -> None:
        runner = RemoteActionRunner(allowed_actions={"press"}, dry_run=True)

        with self.assertRaises(RemoteActionError):
            runner.run({"version": 1, "type": "click", "button": "left"})

    def test_dry_run_macro_instruction(self) -> None:
        runner = RemoteActionRunner(dry_run=True)

        result = runner.run(
            {
                "version": 1,
                "type": "macro",
                "steps": [
                    {"version": 1, "type": "press", "keys": ["alt", "s"]},
                    {"version": 1, "type": "text", "value": "ready"},
                ],
            }
        )

        self.assertEqual(result.action, "macro")
        self.assertEqual(result.detail, "2 step(s)")
        self.assertFalse(result.executed)


if __name__ == "__main__":
    unittest.main()
