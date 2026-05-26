from __future__ import annotations

import unittest
from unittest.mock import patch

from SeeOnDesk.desktop import active_window_info, desktop_snapshot


class SeeOnDeskTests(unittest.TestCase):
    def test_active_window_uses_kdotool_when_available(self) -> None:
        def fake_run(args: list[str], timeout_seconds: float = 1.0) -> tuple[bool, str, str]:
            if args[:2] == ["kdotool", "getactivewindow"]:
                return True, "123\n", ""
            if args[:2] == ["kdotool", "getwindowclassname"]:
                return True, "konsole\n", ""
            if args[:2] == ["kdotool", "getwindowname"]:
                return True, "Terminal\n", ""
            if args[:2] == ["xprop", "-id"]:
                return True, "_NET_WM_PID(CARDINAL) = 4242\n", ""
            return False, "", "unexpected"

        with patch("SeeOnDesk.desktop._run_command", side_effect=fake_run), patch(
            "SeeOnDesk.desktop._process_name", return_value="konsole"
        ):
            info = active_window_info()

        self.assertTrue(info.ok)
        self.assertEqual(info.backend, "kdotool")
        self.assertEqual(info.window_id, "123")
        self.assertEqual(info.app_name, "konsole")
        self.assertEqual(info.title, "Terminal")
        self.assertEqual(info.pid, 4242)
        self.assertEqual(info.process_name, "konsole")

    def test_active_window_falls_back_to_x11_metadata(self) -> None:
        xprop = "\n".join(
            [
                'WM_CLASS(STRING) = "Navigator", "firefox"',
                '_NET_WM_NAME(UTF8_STRING) = "Docs - Browser"',
                "_NET_WM_PID(CARDINAL) = 777",
            ]
        )

        def fake_run(args: list[str], timeout_seconds: float = 1.0) -> tuple[bool, str, str]:
            if args[:2] == ["kdotool", "getactivewindow"]:
                return False, "", "missing"
            if args[:2] == ["xdotool", "getactivewindow"]:
                return True, "456\n", ""
            if args[:2] == ["xprop", "-id"]:
                return True, xprop, ""
            return False, "", "unexpected"

        with patch("SeeOnDesk.desktop._run_command", side_effect=fake_run), patch(
            "SeeOnDesk.desktop._process_name", return_value="firefox"
        ):
            info = active_window_info()

        self.assertTrue(info.ok)
        self.assertEqual(info.backend, "x11")
        self.assertEqual(info.window_id, "456")
        self.assertEqual(info.app_class, "firefox")
        self.assertEqual(info.title, "Docs - Browser")
        self.assertEqual(info.pid, 777)

    def test_active_window_reports_unavailable_without_backend(self) -> None:
        with patch("SeeOnDesk.desktop._run_command", return_value=(False, "", "not installed")):
            info = active_window_info()

        self.assertFalse(info.ok)
        self.assertEqual(info.backend, "unavailable")
        self.assertIn("not installed", info.error)

    def test_desktop_snapshot_is_serializable(self) -> None:
        with patch("SeeOnDesk.desktop.active_window_info") as active:
            active.return_value.to_dict.return_value = {"ok": False, "app_name": "unknown"}
            snapshot = desktop_snapshot().to_dict()

        self.assertIn("timestamp", snapshot)
        self.assertIn("session_type", snapshot)
        self.assertEqual(snapshot["active_window"]["app_name"], "unknown")


if __name__ == "__main__":
    unittest.main()
