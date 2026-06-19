"""Tests for the workspace watcher (SeeOnDesk/workspace_watcher.py).

Mocks subprocess.run to avoid depending on kdotool/wmctrl being installed.
"""

from __future__ import annotations

import logging
import subprocess
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from SeeOnDesk.workspace_watcher import WorkspaceChange, WorkspaceInfo, WorkspaceWatcher

logging.disable(logging.CRITICAL)


def _mock_kdotool_result(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["kdotool"], returncode=returncode,
        stdout=stdout, stderr="",
    )


def _mock_wmctrl_result(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["wmctrl"], returncode=returncode,
        stdout=stdout, stderr="",
    )


class WorkspaceWatcherListTests(unittest.TestCase):
    """WorkspaceWatcher.list_workspaces() — fallback and edge cases."""

    def setUp(self) -> None:
        self.watcher = WorkspaceWatcher()

    def test_list_workspaces_kdotool_available(self) -> None:
        """When kdotool works, workspaces are returned."""
        with patch.object(
            subprocess, "run",
            side_effect=[
                _mock_kdotool_result("0\n1\n2\n"),
                _mock_kdotool_result("Main"),
                _mock_kdotool_result("Work"),
                _mock_kdotool_result("Chat"),
            ],
        ):
            workspaces = self.watcher.list_workspaces()
        self.assertEqual(len(workspaces), 3)
        self.assertEqual(workspaces[0].id, "0")
        self.assertEqual(workspaces[1].id, "1")
        self.assertEqual(workspaces[2].id, "2")

    def test_list_workspaces_falls_back_to_wmctrl(self) -> None:
        """When kdotool fails, falls back to wmctrl."""
        # First call (kdotool) raises FileNotFoundError, second (wmctrl) returns data
        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if cmd[0] == "kdotool":
                raise FileNotFoundError("kdotool not found")
            if cmd[0] == "wmctrl":
                return _mock_wmctrl_result(
                    "0  *  Main\n"
                    "1  -  Work\n"
                )
            raise ValueError(f"unexpected cmd: {cmd}")

        with patch.object(subprocess, "run", side_effect=side_effect):
            workspaces = self.watcher.list_workspaces()
        self.assertEqual(len(workspaces), 2)
        self.assertTrue(workspaces[0].is_active)
        self.assertFalse(workspaces[1].is_active)
        # The watcher code takes parts[4:] as name — with short lines it uses fallback
        self.assertEqual(workspaces[0].name, "Desktop 0")
        self.assertEqual(workspaces[1].name, "Desktop 1")

    def test_list_workspaces_empty_when_both_missing(self) -> None:
        """When both kdotool and wmctrl are missing, empty list."""
        def side_effect(*args, **kwargs):
            raise FileNotFoundError("not found")

        with patch.object(subprocess, "run", side_effect=side_effect):
            workspaces = self.watcher.list_workspaces()
        self.assertEqual(workspaces, [])

    def test_list_workspaces_handles_timeout(self) -> None:
        """subprocess.TimeoutExpired is handled gracefully."""
        def side_effect(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="kdotool", timeout=5)

        with patch.object(subprocess, "run", side_effect=side_effect):
            workspaces = self.watcher.list_workspaces()
        self.assertEqual(workspaces, [])

    def test_list_workspaces_with_kdotool_fallback_on_failure(self) -> None:
        """When kdotool returns non-zero, falls back to wmctrl."""
        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if cmd[0] == "kdotool":
                return _mock_kdotool_result("", returncode=1)
            if cmd[0] == "wmctrl":
                return _mock_wmctrl_result("0  * DG: 1920x1080  VP: 0,0  WA: ...  Desktop\n")
            raise ValueError(f"unexpected cmd: {cmd}")

        with patch.object(subprocess, "run", side_effect=side_effect):
            workspaces = self.watcher.list_workspaces()
        self.assertEqual(len(workspaces), 1)


class WorkspaceWatcherActiveTests(unittest.TestCase):
    """WorkspaceWatcher.get_active_workspace()."""

    def setUp(self) -> None:
        self.watcher = WorkspaceWatcher()

    def test_get_active_workspace_finds_active(self) -> None:
        with patch.object(
            self.watcher, "list_workspaces",
            return_value=[
                WorkspaceInfo(id="0", name="Main", is_active=False, window_count=0),
                WorkspaceInfo(id="1", name="Work", is_active=True, window_count=0),
            ],
        ):
            active = self.watcher.get_active_workspace()
        self.assertIsNotNone(active)
        self.assertEqual(active.id, "1")
        self.assertEqual(active.name, "Work")

    def test_get_active_workspace_returns_none_when_no_active(self) -> None:
        with patch.object(self.watcher, "list_workspaces", return_value=[]):
            active = self.watcher.get_active_workspace()
        self.assertIsNone(active)

    def test_get_active_workspace_returns_none_when_empty(self) -> None:
        with patch.object(self.watcher, "list_workspaces", return_value=[]):
            result = self.watcher.get_active_workspace()
        self.assertIsNone(result)


class WorkspaceWatcherPollTests(unittest.TestCase):
    """WorkspaceWatcher.poll() — detects changes and invokes callbacks."""

    def setUp(self) -> None:
        self.watcher = WorkspaceWatcher()
        self.callback = unittest.mock.MagicMock()
        self.watcher.on_change(self.callback)

    def test_poll_invokes_callback_on_change(self) -> None:
        """When active workspace changes, callbacks are invoked."""
        with patch.object(
            self.watcher, "get_active_workspace",
            return_value=WorkspaceInfo(id="1", name="Work", is_active=True, window_count=0),
        ):
            self.watcher.poll()
        self.callback.assert_called_once()
        change = self.callback.call_args[0][0]
        self.assertIsInstance(change, WorkspaceChange)
        self.assertIsNone(change.old_workspace)
        self.assertEqual(change.new_workspace.id, "1")

    def test_poll_detects_second_change(self) -> None:
        """Multiple changes fire multiple callbacks."""
        with patch.object(
            self.watcher, "get_active_workspace",
            return_value=WorkspaceInfo(id="1", name="Work", is_active=True, window_count=0),
        ):
            self.watcher.poll()
        self.assertEqual(self.callback.call_count, 1)

        with patch.object(
            self.watcher, "get_active_workspace",
            return_value=WorkspaceInfo(id="2", name="Chat", is_active=True, window_count=0),
        ):
            self.watcher.poll()
        self.assertEqual(self.callback.call_count, 2)

    def test_poll_does_not_invoke_on_same_workspace(self) -> None:
        """When workspace hasn't changed, no callback."""
        active = WorkspaceInfo(id="1", name="Work", is_active=True, window_count=0)
        with patch.object(self.watcher, "get_active_workspace", return_value=active):
            self.watcher.poll()
        self.callback.reset_mock()
        with patch.object(self.watcher, "get_active_workspace", return_value=active):
            self.watcher.poll()
        self.callback.assert_not_called()

    def test_poll_returns_active_workspace(self) -> None:
        with patch.object(
            self.watcher, "get_active_workspace",
            return_value=WorkspaceInfo(id="1", name="Work", is_active=True, window_count=0),
        ):
            result = self.watcher.poll()
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "1")

    def test_poll_no_active_returns_none(self) -> None:
        with patch.object(self.watcher, "get_active_workspace", return_value=None):
            result = self.watcher.poll()
        self.assertIsNone(result)

    def test_poll_no_active_does_not_invoke_callback(self) -> None:
        with patch.object(self.watcher, "get_active_workspace", return_value=None):
            self.watcher.poll()
        self.callback.assert_not_called()

    def test_callback_exception_does_not_crash_poll(self) -> None:
        """If a callback raises, poll() catches and continues."""
        failing_cb = unittest.mock.MagicMock(side_effect=ValueError("cb failed"))
        self.watcher.on_change(failing_cb)
        with patch.object(
            self.watcher, "get_active_workspace",
            return_value=WorkspaceInfo(id="1", name="Work", is_active=True, window_count=0),
        ):
            # Should not raise
            result = self.watcher.poll()
        self.assertIsNotNone(result)


class WorkspaceInfoDataclassTests(unittest.TestCase):
    """WorkspaceInfo and WorkspaceChange dataclass behaviors."""

    def test_workspace_info_frozen(self) -> None:
        ws = WorkspaceInfo(id="1", name="Main", is_active=True, window_count=3)
        with self.assertRaises(AttributeError):
            ws.id = "2"  # type: ignore[misc]

    def test_workspace_change_old_can_be_none(self) -> None:
        change = WorkspaceChange(
            old_workspace=None,
            new_workspace=WorkspaceInfo(id="1", name="Main", is_active=True, window_count=0),
        )
        self.assertIsNone(change.old_workspace)
        self.assertEqual(change.new_workspace.id, "1")


if __name__ == "__main__":
    unittest.main()
