"""Tests for the verification-prompt callback system (FionaCore/verification.py)."""

from __future__ import annotations

import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from FionaCore.actions import ActionSpec
from FionaCore.verification import (
    DEFAULT_VERIFICATION_PROMPT,
    DesktopVerificationPrompt,
    StdoutVerificationPrompt,
    VerificationPrompt,
    prompt_for_confirmation,
)


class VerificationPromptTests(unittest.TestCase):
    """Tests for the abstract base and concrete prompt classes."""

    # ------------------------------------------------------------------
    # VerificationPrompt (abstract)
    # ------------------------------------------------------------------

    def test_abstract_default_returns_true(self) -> None:
        """The default confirm() implementation returns True."""
        prompt = VerificationPrompt()
        self.assertTrue(prompt.confirm("test.action", {"name": "test.action"}))

    # ------------------------------------------------------------------
    # StdoutVerificationPrompt
    # ------------------------------------------------------------------

    def test_stdout_accepts_y(self) -> None:
        prompt = StdoutVerificationPrompt()
        with patch("sys.stdin", io.StringIO("y\n")):
            self.assertTrue(
                prompt.confirm("test.action", {"name": "test.action", "description": "test", "risk": "low", "command": ["echo", "hi"]}),
            )

    def test_stdout_accepts_yes(self) -> None:
        prompt = StdoutVerificationPrompt()
        with patch("sys.stdin", io.StringIO("yes\n")):
            self.assertTrue(
                prompt.confirm("test.action", {"name": "test.action"}),
            )

    def test_stdout_accepts_Y_uppercase(self) -> None:
        prompt = StdoutVerificationPrompt()
        with patch("sys.stdin", io.StringIO("Y\n")):
            self.assertTrue(
                prompt.confirm("test.action", {"name": "test.action"}),
            )

    def test_stdout_rejects_n(self) -> None:
        prompt = StdoutVerificationPrompt()
        with patch("sys.stdin", io.StringIO("n\n")):
            self.assertFalse(
                prompt.confirm("test.action", {"name": "test.action"}),
            )

    def test_stdout_rejects_empty(self) -> None:
        prompt = StdoutVerificationPrompt()
        with patch("sys.stdin", io.StringIO("\n")):
            self.assertFalse(
                prompt.confirm("test.action", {"name": "test.action"}),
            )

    def test_stdout_rejects_arbitrary(self) -> None:
        prompt = StdoutVerificationPrompt()
        with patch("sys.stdin", io.StringIO("maybe\n")):
            self.assertFalse(
                prompt.confirm("test.action", {"name": "test.action"}),
            )

    def test_stdout_handles_eof(self) -> None:
        """EOFError (e.g. /dev/null stdin) is treated as 'no'."""
        prompt = StdoutVerificationPrompt()
        with patch("sys.stdin", io.StringIO("")):  # No input -> raises EOFError
            self.assertFalse(
                prompt.confirm("test.action", {"name": "test.action"}),
            )

    def test_stdout_handles_keyboard_interrupt(self) -> None:
        """Ctrl+C is treated as 'no'."""
        prompt = StdoutVerificationPrompt()

        def _raising_input(_prompt: str = "") -> str:
            raise KeyboardInterrupt()

        with patch("builtins.input", _raising_input):
            self.assertFalse(
                prompt.confirm("test.action", {"name": "test.action"}),
            )

    # ------------------------------------------------------------------
    # DesktopVerificationPrompt
    # ------------------------------------------------------------------

    def test_desktop_fallback_when_tkinter_unavailable(self) -> None:
        """When tkinter is missing, Desktop prompt degrades to stdout."""
        prompt = DesktopVerificationPrompt()
        # Patch both notify-send and tkinter to be unavailable
        with (
            patch("shutil.which", return_value=None),
            patch(
                "FionaCore.verification.DesktopVerificationPrompt._prompt_tkinter",
                return_value=None,
            ),
            patch("sys.stdin", io.StringIO("y\n")),
        ):
            result = prompt.confirm("test.action", {"name": "test.action", "description": "desc", "risk": "high", "command": ["rm", "-rf", "/"]})
            self.assertTrue(result)

    def test_desktop_notify_send_failure_does_not_crash(self) -> None:
        """If notify-send fails (non-zero exit), Tkinter/fallback still works."""
        prompt = DesktopVerificationPrompt()
        mock_failed_run = MagicMock()
        mock_failed_run.returncode = 1
        with (
            patch("shutil.which", return_value="/usr/bin/notify-send"),
            patch("subprocess.run", return_value=mock_failed_run),
            patch(
                "FionaCore.verification.DesktopVerificationPrompt._prompt_tkinter",
                return_value=None,
            ),
            patch("sys.stdin", io.StringIO("n\n")),
        ):
            result = prompt.confirm("test.action", {"name": "test.action"})
            self.assertFalse(result)

    # ------------------------------------------------------------------
    # prompt_for_confirmation (convenience function)
    # ------------------------------------------------------------------

    def test_prompt_returns_true_when_not_required(self) -> None:
        spec = ActionSpec("safe.action", ("echo", "hi"), "Safe action.")
        self.assertTrue(prompt_for_confirmation(spec))

    def test_prompt_returns_true_when_required_and_confirmed(self) -> None:
        spec = ActionSpec(
            "risky.action", ("rm", "-rf", "/"), "Risky action.",
            requires_confirmation=True,
        )
        mock_prompt = VerificationPrompt()
        # Mock confirm to return True
        with patch.object(mock_prompt, "confirm", return_value=True):
            self.assertTrue(prompt_for_confirmation(spec, mock_prompt))

    def test_prompt_returns_false_when_required_and_rejected(self) -> None:
        spec = ActionSpec(
            "risky.action", ("rm", "-rf", "/"), "Risky action.",
            requires_confirmation=True,
        )
        mock_prompt = VerificationPrompt()
        with patch.object(mock_prompt, "confirm", return_value=False):
            self.assertFalse(prompt_for_confirmation(spec, mock_prompt))

    def test_prompt_accepts_dict_like_spec(self) -> None:
        spec = {
            "name": "dict.action",
            "command": ["echo", "hi"],
            "description": "Dict-based spec.",
            "requires_confirmation": True,
        }
        mock_prompt = VerificationPrompt()
        with patch.object(mock_prompt, "confirm", return_value=True):
            self.assertTrue(prompt_for_confirmation(spec, mock_prompt))

    def test_prompt_uses_default_when_none_given(self) -> None:
        """When prompt is None, DEFAULT_VERIFICATION_PROMPT is used."""
        spec = ActionSpec("test.action", ("echo", "hi"), "Test.", requires_confirmation=False)
        self.assertTrue(prompt_for_confirmation(spec, prompt=None))

    def test_default_prompt_is_desktop(self) -> None:
        self.assertIsInstance(
            DEFAULT_VERIFICATION_PROMPT, DesktopVerificationPrompt,
        )


if __name__ == "__main__":
    unittest.main()
