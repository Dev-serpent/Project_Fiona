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

__all__ = [
    "ActiveWindowInfo",
    "DesktopSnapshot",
    "active_window_info",
    "all_windows_info",
    "desktop_snapshot",
    "analyze_screen",
    "capture_screen",
    "capture_window",
]
