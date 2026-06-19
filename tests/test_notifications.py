"""Tests for FionaCore.notifications — result notification builders."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from FionaCore.actions import ActionResult
from FionaCore.notifications import Notification, build_notification, notify_result


class NotificationDataclassTests(unittest.TestCase):
    def test_default_urgency_normal(self):
        n = Notification(title="T", body="B")
        self.assertEqual(n.urgency, "normal")

    def test_custom_urgency(self):
        n = Notification(title="T", body="B", urgency="critical")
        self.assertEqual(n.urgency, "critical")

    def test_to_dict(self):
        n = Notification(title="Title", body="Body", urgency="low")
        self.assertEqual(n.to_dict(), {"title": "Title", "body": "Body", "urgency": "low"})


class BuildNotificationTests(unittest.TestCase):
    def test_successful_result_includes_ok(self):
        result = ActionResult(ok=True, action="test.action", detail="completed")
        notification = build_notification(result)
        self.assertIn("OK", notification.title)
        self.assertIn("test.action", notification.title)

    def test_failed_result_includes_failed(self):
        result = ActionResult(ok=False, action="test.action", detail="error occurred")
        notification = build_notification(result)
        self.assertIn("FAILED", notification.title)

    def test_ok_result_has_normal_urgency(self):
        result = ActionResult(ok=True, action="test", detail="ok")
        notification = build_notification(result)
        self.assertEqual(notification.urgency, "normal")

    def test_failed_result_has_critical_urgency(self):
        result = ActionResult(ok=False, action="test", detail="fail")
        notification = build_notification(result)
        self.assertEqual(notification.urgency, "critical")

    def test_body_uses_detail_when_present(self):
        result = ActionResult(ok=True, action="test", detail="custom detail")
        notification = build_notification(result)
        self.assertEqual(notification.body, "custom detail")

    def test_body_falls_back_to_stderr(self):
        result = ActionResult(ok=True, action="test", detail="", stderr="error output")
        notification = build_notification(result)
        self.assertEqual(notification.body, "error output")

    def test_body_falls_back_to_stdout(self):
        result = ActionResult(ok=True, action="test", detail="", stderr="", stdout="standard output")
        notification = build_notification(result)
        self.assertEqual(notification.body, "standard output")

    def test_body_uses_no_details_when_all_empty(self):
        result = ActionResult(ok=True, action="test", detail="")
        notification = build_notification(result)
        self.assertEqual(notification.body, "No details.")

    def test_body_truncated_to_240_chars(self):
        long_detail = "x" * 500
        result = ActionResult(ok=True, action="test", detail=long_detail)
        notification = build_notification(result)
        self.assertEqual(len(notification.body), 240)

    def test_stderr_stripped_of_whitespace(self):
        result = ActionResult(ok=True, action="test", detail="", stderr="  error text  \n")
        notification = build_notification(result)
        self.assertEqual(notification.body, "error text")


class NotifyResultTests(unittest.TestCase):
    def test_silent_mode_returns_notification(self):
        result = ActionResult(ok=True, action="test", detail="silent")
        notification = notify_result(result, mode="silent")
        self.assertIsInstance(notification, Notification)
        self.assertEqual(notification.body, "silent")

    def test_silent_mode_does_not_print(self):
        result = ActionResult(ok=True, action="test", detail="no print")
        with patch("builtins.print") as mock_print:
            notify_result(result, mode="silent")
            mock_print.assert_not_called()

    @patch("FionaCore.notifications.shutil.which")
    @patch("FionaCore.notifications.subprocess.run")
    def test_desktop_mode_with_notify_send(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/notify-send"
        mock_run.return_value = subprocess.CompletedProcess(
            ["notify-send"], returncode=0, stdout="", stderr=""
        )
        result = ActionResult(ok=True, action="test", detail="desktop test")
        notify_result(result, mode="desktop")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "notify-send")
        self.assertIn("-u", args)

    @patch("FionaCore.notifications.shutil.which")
    @patch("builtins.print")
    def test_desktop_mode_falls_back_to_stdout(self, mock_print, mock_which):
        mock_which.return_value = None
        result = ActionResult(ok=True, action="test.fallback", detail="printed")
        notify_result(result, mode="desktop")
        mock_print.assert_called_once()
        output = mock_print.call_args[0][0]
        self.assertIn("test.fallback", output)
        self.assertIn("printed", output)

    @patch("builtins.print")
    def test_stdout_mode_prints(self, mock_print):
        result = ActionResult(ok=True, action="test.stdout", detail="printed")
        notify_result(result, mode="stdout")
        mock_print.assert_called_once()

    @patch("builtins.print")
    def test_unknown_mode_returns_notification_silently(self, mock_print):
        """Unknown modes do not print; they silently return the notification."""
        result = ActionResult(ok=True, action="test.unknown", detail="silent")
        notification = notify_result(result, mode="invalid_mode")
        self.assertIsInstance(notification, Notification)
        mock_print.assert_not_called()

    @patch("FionaCore.notifications.speak")
    def test_use_speech_calls_speak(self, mock_speak):
        result = ActionResult(ok=True, action="test.speech", detail="spoken")
        notify_result(result, mode="silent", use_speech=True)
        mock_speak.assert_called_once()

    @patch("FionaCore.notifications.speak")
    def test_use_speech_with_failed_result(self, mock_speak):
        result = ActionResult(ok=False, action="test.fail", detail="failed action")
        notify_result(result, mode="silent", use_speech=True)
        mock_speak.assert_called_once()
        call_text = mock_speak.call_args[0][0]
        self.assertIn("FAILED", call_text)

    @patch("FionaCore.notifications.shutil.which")
    @patch("FionaCore.notifications.subprocess.run")
    def test_desktop_notify_send_uses_critical_for_failure(
        self, mock_run, mock_which
    ):
        mock_which.return_value = "/usr/bin/notify-send"
        mock_run.return_value = subprocess.CompletedProcess(
            ["notify-send"], returncode=0, stdout="", stderr=""
        )
        result = ActionResult(ok=False, action="test", detail="fail")
        notify_result(result, mode="desktop")
        args = mock_run.call_args[0][0]
        self.assertIn("critical", args)


if __name__ == "__main__":
    unittest.main()
