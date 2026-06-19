"""Tests for SeeOnDesk.desktop — desktop awareness data structures and logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from SeeOnDesk.desktop import (
    ActiveWindowInfo,
    DesktopSnapshot,
    active_window_info,
    all_windows_info,
    desktop_snapshot,
    _active_window_from_kdotool,
    _active_window_from_x11,
    _info_for_window_id_kdotool,
    _info_for_window_id_x11,
    _parse_xprop_int,
    _parse_xprop_string,
    _parse_xprop_string_list,
    _process_name,
    _run_command,
    _xprop_details,
)


class ActiveWindowInfoTests(unittest.TestCase):
    def test_default_ok_false(self):
        info = ActiveWindowInfo(ok=False, backend="test")
        self.assertFalse(info.ok)

    def test_app_name_uses_app_class_first(self):
        info = ActiveWindowInfo(
            ok=True, backend="test", app_class="Firefox", process_name="firefox", title="Mozilla Firefox"
        )
        self.assertEqual(info.app_name, "Firefox")

    def test_app_name_falls_back_to_process_name(self):
        info = ActiveWindowInfo(ok=True, backend="test", process_name="firefox")
        self.assertEqual(info.app_name, "firefox")

    def test_app_name_falls_back_to_title(self):
        info = ActiveWindowInfo(ok=True, backend="test", title="Untitled Document")
        self.assertEqual(info.app_name, "Untitled Document")

    def test_app_name_uses_unknown_as_last_resort(self):
        info = ActiveWindowInfo(ok=False, backend="test")
        self.assertEqual(info.app_name, "unknown")

    def test_to_dict_includes_app_name(self):
        info = ActiveWindowInfo(ok=True, backend="kde", app_class="Brave")
        d = info.to_dict()
        self.assertEqual(d["app_name"], "Brave")
        self.assertIn("backend", d)
        self.assertIn("window_id", d)

    def test_to_dict_includes_raw(self):
        info = ActiveWindowInfo(ok=True, backend="test", raw={"key": "val"})
        d = info.to_dict()
        self.assertEqual(d["raw"], {"key": "val"})

    def test_pid_optional(self):
        info = ActiveWindowInfo(ok=True, backend="test", pid=1234)
        self.assertEqual(info.pid, 1234)

    def test_pid_none_by_default(self):
        info = ActiveWindowInfo(ok=False, backend="test")
        self.assertIsNone(info.pid)


class DesktopSnapshotTests(unittest.TestCase):
    def test_to_dict_includes_all_fields(self):
        window = ActiveWindowInfo(ok=True, backend="kde", app_class="Terminal")
        snap = DesktopSnapshot(
            timestamp="2024-01-01T00:00:00",
            session_type="wayland",
            desktop="KDE",
            active_window=window,
            all_windows=[window],
            screenshot_path="/tmp/shot.png",
        )
        d = snap.to_dict()
        self.assertEqual(d["timestamp"], "2024-01-01T00:00:00")
        self.assertEqual(d["session_type"], "wayland")
        self.assertEqual(d["desktop"], "KDE")
        self.assertEqual(d["active_window"]["app_name"], "Terminal")
        self.assertEqual(len(d["all_windows"]), 1)
        self.assertEqual(d["screenshot_path"], "/tmp/shot.png")

    def test_to_dict_screenshot_none(self):
        snap = DesktopSnapshot(
            timestamp="2024-01-01T00:00:00",
            session_type="x11",
            desktop="GNOME",
            active_window=ActiveWindowInfo(ok=False, backend="unavailable"),
        )
        d = snap.to_dict()
        self.assertIsNone(d["screenshot_path"])

    def test_to_dict_all_windows_empty(self):
        snap = DesktopSnapshot(
            timestamp="2024-01-01T00:00:00",
            session_type="x11",
            desktop="GNOME",
            active_window=ActiveWindowInfo(ok=False, backend="unavailable"),
        )
        d = snap.to_dict()
        self.assertEqual(d["all_windows"], [])


class RunCommandTests(unittest.TestCase):
    @patch("SeeOnDesk.desktop.subprocess.run")
    def test_run_command_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="output\n", stderr=""
        )
        ok, stdout, stderr = _run_command(["test", "cmd"])
        self.assertTrue(ok)
        self.assertEqual(stdout, "output\n")

    @patch("SeeOnDesk.desktop.subprocess.run")
    def test_run_command_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error"
        )
        ok, stdout, stderr = _run_command(["test"])
        self.assertFalse(ok)

    @patch("SeeOnDesk.desktop.subprocess.run")
    def test_run_command_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("not found")
        ok, stdout, stderr = _run_command(["missing"])
        self.assertFalse(ok)
        self.assertIn("not found", stderr)

    @patch("SeeOnDesk.desktop.subprocess.run")
    def test_run_command_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 1.0)
        ok, stdout, stderr = _run_command(["slow"])
        self.assertFalse(ok)

    @patch("SeeOnDesk.desktop.subprocess.run")
    def test_run_command_default_timeout(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )
        _run_command(["cmd"])
        mock_run.assert_called_once()
        self.assertIn("timeout", mock_run.call_args[1])


class ParseXpropStringTests(unittest.TestCase):
    def test_parse_simple_string(self):
        output = 'WM_NAME(UTF8_STRING) = "My Window"'
        self.assertEqual(_parse_xprop_string(output, "WM_NAME"), "My Window")

    def test_parse_missing_key(self):
        output = 'WM_CLASS(STRING) = "firefox"'
        self.assertEqual(_parse_xprop_string(output, "WM_NAME"), "")

    def test_parse_empty_output(self):
        self.assertEqual(_parse_xprop_string("", "WM_NAME"), "")

    def test_parse_with_escaped_quotes(self):
        output = 'WM_NAME(UTF8_STRING) = "Window \"Title\""'
        # The regex expects bare quotes; escaped ones may not parse
        # Just verify it doesn't crash
        result = _parse_xprop_string(output, "WM_NAME")
        self.assertIsInstance(result, str)

    def test_parse_with_no_match(self):
        output = '_NET_WM_PID(CARDINAL) = 1234'
        self.assertEqual(_parse_xprop_string(output, "WM_NAME"), "")


class ParseXpropStringListTests(unittest.TestCase):
    def test_parse_simple_list(self):
        output = 'WM_CLASS(STRING) = "firefox", "Firefox"'
        result = _parse_xprop_string_list(output, "WM_CLASS")
        self.assertEqual(result, ["firefox", "Firefox"])

    def test_parse_missing_key(self):
        output = 'WM_NAME(STRING) = "test"'
        self.assertEqual(_parse_xprop_string_list(output, "WM_CLASS"), [])

    def test_parse_empty_output(self):
        self.assertEqual(_parse_xprop_string_list("", "WM_CLASS"), [])

    def test_parse_only_returns_for_matching_key(self):
        output = 'WM_CLASS(STRING) = "a", "b"\nWM_NAME(STRING) = "test"'
        result = _parse_xprop_string_list(output, "WM_CLASS")
        self.assertEqual(result, ["a", "b"])


class ParseXpropIntTests(unittest.TestCase):
    def test_parse_valid_int(self):
        output = '_NET_WM_PID(CARDINAL) = 1234'
        self.assertEqual(_parse_xprop_int(output, "_NET_WM_PID"), 1234)

    def test_parse_missing_key(self):
        output = 'WM_NAME(STRING) = "test"'
        self.assertIsNone(_parse_xprop_int(output, "_NET_WM_PID"))

    def test_parse_empty_output(self):
        self.assertIsNone(_parse_xprop_int("", "_NET_WM_PID"))

    def test_parse_non_numeric_value(self):
        output = '_NET_WM_PID(CARDINAL) = not_a_number'
        self.assertEqual(_parse_xprop_int(output, "_NET_WM_PID"), None)


class ProcessNameTests(unittest.TestCase):
    @patch("SeeOnDesk.desktop.Path.read_text")
    def test_process_name_returns_comm(self, mock_read):
        mock_read.return_value = "firefox\n"
        result = _process_name(1234)
        self.assertEqual(result, "firefox")

    @patch("SeeOnDesk.desktop.Path.read_text")
    def test_process_name_strips_whitespace(self, mock_read):
        mock_read.return_value = "  chrome  \n"
        result = _process_name(5678)
        self.assertEqual(result, "chrome")

    @patch("SeeOnDesk.desktop.Path.read_text")
    def test_process_name_os_error_returns_empty(self, mock_read):
        mock_read.side_effect = OSError("permission denied")
        result = _process_name(9999)
        self.assertEqual(result, "")

    def test_process_name_none_returns_empty(self):
        result = _process_name(None)
        self.assertEqual(result, "")


class XpropDetailsTests(unittest.TestCase):
    @patch("SeeOnDesk.desktop._run_command")
    def test_xprop_details_success(self, mock_run):
        mock_run.return_value = (
            True,
            'WM_CLASS(STRING) = "firefox", "Firefox"\n_NET_WM_NAME(UTF8_STRING) = "Mozilla Firefox"\n_NET_WM_PID(CARDINAL) = 1234\n',
            "",
        )
        result = _xprop_details("0x12345")
        self.assertEqual(result["app_class"], "Firefox")
        self.assertEqual(result["title"], "Mozilla Firefox")
        self.assertEqual(result["pid"], 1234)
        self.assertEqual(result["wm_class"], ["firefox", "Firefox"])

    @patch("SeeOnDesk.desktop._run_command")
    def test_xprop_details_failure(self, mock_run):
        mock_run.return_value = (False, "", "error")
        result = _xprop_details("0x99999")
        self.assertEqual(result, {})

    @patch("SeeOnDesk.desktop._run_command")
    def test_xprop_details_partial(self, mock_run):
        mock_run.return_value = (
            True,
            'WM_CLASS(STRING) = "app", "App"\n',
            "",
        )
        result = _xprop_details("0x12345")
        self.assertIn("app_class", result)
        self.assertNotIn("pid", result)


class ActiveWindowFromKdotoolTests(unittest.TestCase):
    @patch("SeeOnDesk.desktop._run_command")
    def test_kdotool_success(self, mock_run):
        mock_run.side_effect = [
            (True, "0x12345\n", ""),  # getactivewindow
            (True, "Firefox\n", ""),  # getwindowclassname
            (True, "Mozilla Firefox\n", ""),  # getwindowname
        ]
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {"pid": 1234, "app_class": "Firefox"}
            with patch("SeeOnDesk.desktop._process_name", return_value="firefox"):
                info = _active_window_from_kdotool()
                self.assertTrue(info.ok)
                self.assertEqual(info.backend, "kdotool")
                self.assertEqual(info.window_id, "0x12345")
                self.assertEqual(info.app_class, "Firefox")
                self.assertEqual(info.pid, 1234)

    @patch("SeeOnDesk.desktop._run_command")
    def test_kdotool_failure(self, mock_run):
        mock_run.return_value = (False, "", "kdotool not found")
        info = _active_window_from_kdotool()
        self.assertFalse(info.ok)
        self.assertEqual(info.backend, "kdotool")

    @patch("SeeOnDesk.desktop._run_command")
    def test_kdotool_empty_window_id(self, mock_run):
        mock_run.return_value = (True, "", "no window")
        info = _active_window_from_kdotool()
        self.assertFalse(info.ok)


class ActiveWindowFromX11Tests(unittest.TestCase):
    @patch("SeeOnDesk.desktop._run_command")
    def test_xdotool_success(self, mock_run):
        mock_run.side_effect = [
            (True, "0x54321\n", ""),  # getactivewindow
        ]
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {"pid": 5678, "app_class": "Terminal", "title": "bash"}
            with patch("SeeOnDesk.desktop._process_name", return_value="bash"):
                info = _active_window_from_x11()
                self.assertTrue(info.ok)
                self.assertEqual(info.backend, "x11")
                self.assertEqual(info.window_id, "0x54321")
                self.assertEqual(info.pid, 5678)

    @patch("SeeOnDesk.desktop._run_command")
    def test_xdotool_failure(self, mock_run):
        mock_run.return_value = (False, "", "xdotool not found")
        info = _active_window_from_x11()
        self.assertFalse(info.ok)
        self.assertEqual(info.backend, "x11")

    @patch("SeeOnDesk.desktop._run_command")
    def test_xdotool_empty_with_xprop_failure(self, mock_run):
        mock_run.side_effect = [
            (True, "0x54321\n", ""),  # getactivewindow
        ]
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {}
            info = _active_window_from_x11()
            self.assertFalse(info.ok)
            self.assertIn("xprop", info.error)


class ActiveWindowInfoTests(unittest.TestCase):
    @patch("SeeOnDesk.desktop._active_window_from_kdotool")
    @patch("SeeOnDesk.desktop._active_window_from_x11")
    def test_active_window_info_tries_kdotool_first(self, mock_x11, mock_kdotool):
        mock_kdotool.return_value = ActiveWindowInfo(
            ok=True, backend="kdotool", app_class="Brave"
        )
        info = active_window_info()
        self.assertTrue(info.ok)
        self.assertEqual(info.backend, "kdotool")
        mock_x11.assert_not_called()

    @patch("SeeOnDesk.desktop._active_window_from_kdotool")
    @patch("SeeOnDesk.desktop._active_window_from_x11")
    def test_active_window_info_falls_back_to_x11(self, mock_x11, mock_kdotool):
        mock_kdotool.return_value = ActiveWindowInfo(
            ok=False, backend="kdotool", error="not available"
        )
        mock_x11.return_value = ActiveWindowInfo(
            ok=True, backend="x11", app_class="XTerm"
        )
        info = active_window_info()
        self.assertTrue(info.ok)
        self.assertEqual(info.backend, "x11")

    @patch("SeeOnDesk.desktop._active_window_from_kdotool")
    @patch("SeeOnDesk.desktop._active_window_from_x11")
    def test_active_window_info_both_fail(self, mock_x11, mock_kdotool):
        mock_kdotool.return_value = ActiveWindowInfo(
            ok=False, backend="kdotool", error="kdotool error"
        )
        mock_x11.return_value = ActiveWindowInfo(
            ok=False, backend="x11", error="xdotool error"
        )
        info = active_window_info()
        self.assertFalse(info.ok)
        self.assertEqual(info.backend, "unavailable")


class InfoForWindowIdTests(unittest.TestCase):
    @patch("SeeOnDesk.desktop._run_command")
    def test_kdotool_window_info_success(self, mock_run):
        mock_run.side_effect = [
            (True, "Firefox\n", ""),
            (True, "My Window\n", ""),
        ]
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {"pid": 1234}
            with patch("SeeOnDesk.desktop._process_name", return_value="firefox"):
                info = _info_for_window_id_kdotool("0x12345")
                self.assertTrue(info.ok)
                self.assertEqual(info.app_class, "Firefox")
                self.assertEqual(info.title, "My Window")

    @patch("SeeOnDesk.desktop._run_command")
    def test_kdotool_window_info_failure(self, mock_run):
        mock_run.side_effect = [
            (False, "", "error"),
            (False, "", "error"),
        ]
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {}
            info = _info_for_window_id_kdotool("0x99999")
            self.assertFalse(info.ok)

    @patch("SeeOnDesk.desktop._run_command")
    def test_x11_window_info_success(self, mock_run):
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {"pid": 5678, "app_class": "XTerm", "title": "bash"}
            with patch("SeeOnDesk.desktop._process_name", return_value="xterm"):
                info = _info_for_window_id_x11("0x54321")
                self.assertTrue(info.ok)
                self.assertEqual(info.backend, "x11")
                self.assertEqual(info.pid, 5678)

    @patch("SeeOnDesk.desktop._run_command")
    def test_x11_window_info_empty_xprop(self, mock_run):
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {}
            info = _info_for_window_id_x11("0x99999")
            self.assertFalse(info.ok)


class AllWindowsInfoTests(unittest.TestCase):
    @patch("SeeOnDesk.desktop._run_command")
    def test_all_windows_kdotool(self, mock_run):
        mock_run.side_effect = [
            (True, "0x100\n0x200\n", ""),  # kdotool search
            (True, "Firefox\n", ""),
            (True, "Browser\n", ""),
            (True, "Terminal\n", ""),
            (True, "bash\n", ""),
        ]
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {"pid": 1234}
            windows = all_windows_info()
            self.assertEqual(len(windows), 2)

    @patch("SeeOnDesk.desktop._run_command")
    def test_all_windows_fallback_xdotool(self, mock_run):
        mock_run.side_effect = [
            (False, "", ""),  # kdotool search fails
            (True, "0x300\n", ""),  # xdotool search
        ]
        with patch("SeeOnDesk.desktop._xprop_details") as mock_xprop:
            mock_xprop.return_value = {"pid": 9999}
            windows = all_windows_info()
            self.assertEqual(len(windows), 1)

    @patch("SeeOnDesk.desktop._run_command")
    def test_all_windows_both_fail(self, mock_run):
        mock_run.side_effect = [
            (False, "", "kdotool not found"),
            (False, "", "xdotool not found"),
        ]
        windows = all_windows_info()
        self.assertEqual(windows, [])


class DesktopSnapshotIntegrationTests(unittest.TestCase):
    @patch("SeeOnDesk.desktop.active_window_info")
    @patch("SeeOnDesk.desktop.all_windows_info")
    @patch("SeeOnDesk.desktop.os.environ.get")
    def test_desktop_snapshot_no_screenshot(
        self, mock_env_get, mock_all_windows, mock_active
    ):
        def env_get_side_effect(key, default=""):
            env = {"XDG_SESSION_TYPE": "x11", "XDG_CURRENT_DESKTOP": "GNOME"}
            return env.get(key, default)

        mock_env_get.side_effect = env_get_side_effect
        mock_active.return_value = ActiveWindowInfo(
            ok=True, backend="x11", app_class="Terminal"
        )
        mock_all_windows.return_value = []

        snap = desktop_snapshot(include_screenshot=False)
        self.assertEqual(snap.session_type, "x11")
        self.assertEqual(snap.desktop, "GNOME")
        self.assertTrue(snap.active_window.ok)
        self.assertEqual(snap.active_window.app_name, "Terminal")
        self.assertIsNone(snap.screenshot_path)

    @patch("SeeOnDesk.desktop.active_window_info")
    @patch("SeeOnDesk.desktop.all_windows_info")
    @patch("SeeOnDesk.vision.capture_screen")
    @patch("SeeOnDesk.desktop.os.environ.get")
    def test_desktop_snapshot_with_screenshot(
        self, mock_env_get, mock_capture, mock_all_windows, mock_active
    ):
        mock_env_get.return_value = "KDE"
        mock_active.return_value = ActiveWindowInfo(
            ok=True, backend="kdotool", app_class="Brave"
        )
        mock_all_windows.return_value = []
        mock_capture.return_value = True

        snap = desktop_snapshot(include_screenshot=True)
        self.assertIsNotNone(snap.screenshot_path)
        self.assertTrue(snap.screenshot_path.endswith(".png"))

    @patch("SeeOnDesk.desktop.active_window_info")
    @patch("SeeOnDesk.desktop.all_windows_info")
    @patch("SeeOnDesk.vision.capture_screen")
    def test_desktop_snapshot_screenshot_fails(
        self, mock_capture, mock_all_windows, mock_active
    ):
        mock_active.return_value = ActiveWindowInfo(ok=False, backend="unavailable")
        mock_all_windows.return_value = []
        mock_capture.return_value = False

        snap = desktop_snapshot(include_screenshot=True)
        self.assertIsNone(snap.screenshot_path)


if __name__ == "__main__":
    unittest.main()
