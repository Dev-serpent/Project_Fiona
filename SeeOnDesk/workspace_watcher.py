"""Workspace/virtual desktop awareness.

Linux: uses ``kdotool`` or ``wmctrl``.
Windows: single-desktop mock (Windows virtual-desktop tracking requires
complex COM/Shell interfaces, so Fiona reports a single desktop).
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkspaceInfo:
    id: str
    name: str
    is_active: bool
    window_count: int


@dataclass(frozen=True)
class WorkspaceChange:
    old_workspace: WorkspaceInfo | None
    new_workspace: WorkspaceInfo


class WorkspaceWatcher:
    """Poll-based workspace tracker.

    Linux: uses ``kdotool`` if available, falls back to ``wmctrl``.
    Windows: always reports a single desktop (``win32-single``).
    """

    def __init__(self, poll_interval: float = 1.0):
        self._poll_interval = poll_interval
        self._last_id: str | None = None
        self._on_change: list[Callable[[WorkspaceChange], None]] = []
        self._running = False

    def list_workspaces(self) -> list[WorkspaceInfo]:
        """List all workspaces/desktops."""
        # ---- Windows: single-desktop mock ----
        if os.name == "nt":
            return [
                WorkspaceInfo(
                    id="win32-0",
                    name="Default Desktop",
                    is_active=True,
                    window_count=0,
                )
            ]

        # ---- Linux: kdotool ----
        workspaces = []
        try:
            result = subprocess.run(
                ["kdotool", "getdesktops"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                desktop_ids = result.stdout.strip().split()
                for did in desktop_ids:
                    name_result = subprocess.run(
                        ["kdotool", "getdesktopname", did],
                        capture_output=True, text=True, timeout=2
                    )
                    name = name_result.stdout.strip() if name_result.returncode == 0 else f"Desktop {did}"
                    workspaces.append(WorkspaceInfo(
                        id=did, name=name, is_active=False, window_count=0
                    ))
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        # ---- Linux: wmctrl fallback ----
        if not workspaces:
            try:
                result = subprocess.run(
                    ["wmctrl", "-d"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        if not line.strip():
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            wid = parts[0]
                            is_active = "*" in parts[1]
                            name = " ".join(parts[4:]) if len(parts) > 4 else f"Desktop {wid}"
                            workspaces.append(WorkspaceInfo(
                                id=wid, name=name, is_active=is_active, window_count=0
                            ))
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass

        return workspaces
    
    def get_active_workspace(self) -> WorkspaceInfo | None:
        """Get the currently active workspace."""
        for ws in self.list_workspaces():
            if ws.is_active:
                return ws
        return None
    
    def on_change(self, callback: Callable[[WorkspaceChange], None]) -> None:
        self._on_change.append(callback)
    
    def poll(self) -> WorkspaceInfo | None:
        """Poll for workspace changes and invoke callbacks on change."""
        active = self.get_active_workspace()
        if active and active.id != self._last_id:
            change = WorkspaceChange(
                old_workspace=next(
                    (ws for ws in self.list_workspaces() if ws.id == self._last_id),
                    None
                ) if self._last_id else None,
                new_workspace=active,
            )
            for cb in self._on_change:
                try:
                    cb(change)
                except Exception:
                    logger.exception("Workspace change callback error")
            self._last_id = active.id
        elif active:
            self._last_id = active.id
        return active
