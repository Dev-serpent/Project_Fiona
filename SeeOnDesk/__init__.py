"""Desktop awareness helpers for Fiona."""

from __future__ import annotations

from .desktop import (
    ActiveWindowInfo,
    DesktopSnapshot,
    active_window_info,
    all_windows_info,
    desktop_snapshot,
)
from .vision import analyze_screen, capture_screen, capture_window
from .process_tracker import ProcessTracker, ProcessInfo
from .workspace_watcher import WorkspaceWatcher, WorkspaceInfo, WorkspaceChange
from .action_discovery import discover_actions, DiscoveredAction

__all__ = [
    "ActiveWindowInfo",
    "DesktopSnapshot",
    "active_window_info",
    "all_windows_info",
    "desktop_snapshot",
    "analyze_screen",
    "capture_screen",
    "capture_window",
    "ProcessTracker",
    "ProcessInfo",
    "WorkspaceWatcher",
    "WorkspaceInfo",
    "WorkspaceChange",
    "discover_actions",
    "DiscoveredAction",
]
