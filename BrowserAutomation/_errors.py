"""Re-export all browser-related error types from :mod:`fiona.interfaces`.

This allows :mod:`BrowserAutomation` to be self-contained without
forcing consumers to import directly from ``fiona.interfaces``.
"""

from __future__ import annotations

from fiona.interfaces import (
    BrowserCrashError,
    BrowserError,
    BrowserLaunchError,
    BrowserNotRunning,
    BrowserShutdownError,
    BrowserTimeout,
    ElementNotFound,
    ElementNotInteractable,
    NavigationTimeout,
    ScriptExecutionError,
    SelectorTimeout,
)

__all__ = [
    "BrowserCrashError",
    "BrowserError",
    "BrowserLaunchError",
    "BrowserNotRunning",
    "BrowserShutdownError",
    "BrowserTimeout",
    "ElementNotFound",
    "ElementNotInteractable",
    "NavigationTimeout",
    "ScriptExecutionError",
    "SelectorTimeout",
]
