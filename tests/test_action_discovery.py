"""Tests for action discovery (SeeOnDesk/action_discovery.py).

Tests discover_actions() returns categorized actions, handles empty system
state, includes window actions, and handles errors gracefully.
"""

from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch

from SeeOnDesk.action_discovery import DiscoveredAction, discover_actions
from SeeOnDesk.process_tracker import ProcessInfo
from SeeOnDesk.workspace_watcher import WorkspaceInfo

logging.disable(logging.CRITICAL)


class DiscoverActionsTests(unittest.TestCase):
    """discover_actions() — returns categorized actions from system state."""

    def setUp(self) -> None:
        self.mock_tracker = MagicMock()
        self.mock_watcher = MagicMock()

    def test_returns_categorized_actions(self) -> None:
        """Returns actions with expected categories."""
        self.mock_tracker.list_processes.return_value = [
            ProcessInfo(pid=100, name="bash", cmdline="/usr/bin/bash"),
            ProcessInfo(pid=200, name="python3", cmdline="/usr/bin/python3 script.py"),
        ]
        self.mock_watcher.list_workspaces.return_value = [
            WorkspaceInfo(id="0", name="Main", is_active=True, window_count=0),
            WorkspaceInfo(id="1", name="Work", is_active=False, window_count=0),
        ]
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        categories = {a.category for a in actions}
        self.assertIn("process", categories)
        self.assertIn("workspace", categories)
        self.assertIn("window", categories)
        self.assertGreater(len(actions), 0)

    def test_includes_process_actions(self) -> None:
        self.mock_tracker.list_processes.return_value = [
            ProcessInfo(pid=100, name="firefox", cmdline="/usr/bin/firefox"),
        ]
        self.mock_watcher.list_workspaces.return_value = []
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        process_actions = [a for a in actions if a.category == "process"]
        self.assertGreater(len(process_actions), 0)
        names = {a.name for a in process_actions}
        self.assertIn("process:kill:firefox", names)
        self.assertIn("process:info:firefox", names)

    def test_process_kill_requires_confirmation(self) -> None:
        self.mock_tracker.list_processes.return_value = [
            ProcessInfo(pid=100, name="bash", cmdline="/usr/bin/bash"),
        ]
        self.mock_watcher.list_workspaces.return_value = []
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        kill_actions = [a for a in actions if a.name.startswith("process:kill:")]
        for ka in kill_actions:
            self.assertTrue(ka.requires_confirmation)

    def test_includes_workspace_actions(self) -> None:
        self.mock_tracker.list_processes.return_value = []
        self.mock_watcher.list_workspaces.return_value = [
            WorkspaceInfo(id="0", name="Desktop 1", is_active=True, window_count=0),
        ]
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        ws_actions = [a for a in actions if a.category == "workspace"]
        self.assertGreater(len(ws_actions), 0)
        self.assertIn("workspace:switch:0", {a.name for a in ws_actions})

    def test_includes_window_actions(self) -> None:
        self.mock_tracker.list_processes.return_value = []
        self.mock_watcher.list_workspaces.return_value = []
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        window_actions = [a for a in actions if a.category == "window"]
        window_names = {a.name for a in window_actions}
        self.assertIn("window:minimize", window_names)
        self.assertIn("window:maximize", window_names)
        self.assertIn("window:close", window_names)

    def test_handles_empty_system_state(self) -> None:
        """Empty processes and workspaces still returns window actions."""
        self.mock_tracker.list_processes.return_value = []
        self.mock_watcher.list_workspaces.return_value = []
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        self.assertGreater(len(actions), 0)
        # Only window actions should remain
        for a in actions:
            self.assertEqual(a.category, "window")

    def test_handles_tracker_error_gracefully(self) -> None:
        """If tracker.list_processes() raises, workspace+window actions remain."""
        self.mock_tracker.list_processes.side_effect = OSError("permission denied")
        self.mock_watcher.list_workspaces.return_value = []
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        # Window actions should still be there
        self.assertGreater(len(actions), 0)
        for a in actions:
            self.assertEqual(a.category, "window")

    def test_handles_watcher_error_gracefully(self) -> None:
        """If watcher.list_workspaces() raises, process+window actions remain."""
        self.mock_tracker.list_processes.return_value = [
            ProcessInfo(pid=100, name="bash", cmdline="/usr/bin/bash"),
        ]
        self.mock_watcher.list_workspaces.side_effect = OSError("wmctrl not found")
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        categories = {a.category for a in actions}
        self.assertIn("process", categories)
        self.assertIn("window", categories)

    def test_limits_process_actions_to_10_unique(self) -> None:
        """Only top 10 unique process names generate actions."""
        processes = [
            ProcessInfo(pid=i, name=f"proc{i}", cmdline=f"/bin/proc{i}")
            for i in range(20)
        ]
        self.mock_tracker.list_processes.return_value = processes
        self.mock_watcher.list_workspaces.return_value = []
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        process_kill_actions = [a for a in actions if a.name.startswith("process:kill:")]
        self.assertLessEqual(len(process_kill_actions), 10)

    def test_discovered_action_has_parameters_for_workspace(self) -> None:
        """Workspace actions include workspace_id in parameters."""
        self.mock_tracker.list_processes.return_value = []
        self.mock_watcher.list_workspaces.return_value = [
            WorkspaceInfo(id="0", name="Main", is_active=True, window_count=0),
        ]
        actions = discover_actions(tracker=self.mock_tracker, watcher=self.mock_watcher)
        ws_switch = [a for a in actions if a.name == "workspace:switch:0"]
        self.assertEqual(len(ws_switch), 1)
        self.assertEqual(ws_switch[0].parameters.get("workspace_id"), "0")

    def test_default_constructor_uses_default_tracker_and_watcher(self) -> None:
        """Calling discover_actions() without args creates defaults."""
        with patch("SeeOnDesk.action_discovery.ProcessTracker") as mock_pt:
            with patch("SeeOnDesk.action_discovery.WorkspaceWatcher") as mock_ww:
                mock_pt.return_value.list_processes.return_value = []
                mock_ww.return_value.list_workspaces.return_value = []
                actions = discover_actions()
                self.assertIsNotNone(actions)
                self.assertIsInstance(actions, list)


class DiscoveredActionDataclassTests(unittest.TestCase):
    """DiscoveredAction dataclass properties."""

    def test_default_requires_confirmation_false(self) -> None:
        action = DiscoveredAction(name="test", description="test", category="system")
        self.assertFalse(action.requires_confirmation)

    def test_default_parameters_is_empty_dict(self) -> None:
        action = DiscoveredAction(name="test", description="test", category="system")
        self.assertEqual(action.parameters, {})

    def test_frozen_cannot_be_modified(self) -> None:
        action = DiscoveredAction(name="test", description="test", category="system")
        with self.assertRaises(AttributeError):
            action.name = "new"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
