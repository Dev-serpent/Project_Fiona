"""Discovers available actions from SeeOnDesk for use in the ActionRouter."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from SeeOnDesk.process_tracker import ProcessTracker
from SeeOnDesk.workspace_watcher import WorkspaceWatcher

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredAction:
    name: str
    description: str
    category: str  # "process", "workspace", "window", "system"
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False


def discover_actions(
    tracker: ProcessTracker | None = None,
    watcher: WorkspaceWatcher | None = None,
) -> list[DiscoveredAction]:
    """Discover available actions based on the current system state.
    
    Returns a list of DiscoveredAction objects that can be registered
    with the ActionRouter.
    """
    actions: list[DiscoveredAction] = []
    
    # Process actions
    tracker = tracker or ProcessTracker()
    try:
        processes = tracker.list_processes()
        # Top CPU consumers (simplified: just list process names)
        seen = set()
        for proc in processes:
            if proc.name not in seen and len(seen) < 10:
                seen.add(proc.name)
                actions.append(DiscoveredAction(
                    name=f"process:kill:{proc.name}",
                    description=f"Kill all {proc.name} processes",
                    category="process",
                    requires_confirmation=True,
                ))
                actions.append(DiscoveredAction(
                    name=f"process:info:{proc.name}",
                    description=f"Show info for {proc.name}",
                    category="process",
                ))
    except Exception:
        logger.exception("Failed to discover process actions")
    
    # Workspace actions
    watcher = watcher or WorkspaceWatcher()
    try:
        workspaces = watcher.list_workspaces()
        for ws in workspaces:
            actions.append(DiscoveredAction(
                name=f"workspace:switch:{ws.id}",
                description=f"Switch to workspace '{ws.name}'",
                category="workspace",
                parameters={"workspace_id": ws.id},
            ))
    except Exception:
        logger.exception("Failed to discover workspace actions")
    
    # Window actions
    actions.extend([
        DiscoveredAction(
            name="window:minimize",
            description="Minimize active window",
            category="window",
        ),
        DiscoveredAction(
            name="window:maximize",
            description="Maximize active window",
            category="window",
        ),
        DiscoveredAction(
            name="window:close",
            description="Close active window",
            category="window",
        ),
    ])
    
    return actions
