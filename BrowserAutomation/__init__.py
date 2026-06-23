"""Browser automation subsystem for Fiona.

Wraps Playwright with the interface contracts defined in
:mod:`fiona.interfaces`.  All Playwright dependencies are imported
lazily so the package can be imported without Playwright installed.
"""

from __future__ import annotations

from typing import Any

from ._errors import (
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
from ._manager import BrowserManager, BrowserManagerState

# ---------------------------------------------------------------------------
# Default instance (module-level convenience)
# ---------------------------------------------------------------------------

_default_manager: BrowserManager | None = None


def _ensure_manager() -> BrowserManager:
    """Return (or create) the module-level default :class:`BrowserManager`."""
    global _default_manager  # noqa: PLW0603
    if _default_manager is None:
        _default_manager = BrowserManager()
    return _default_manager


def get_browser_manager() -> BrowserManager:
    """Return the module-level default :class:`BrowserManager`.

    Creates one on first call.  Use this for CLI and integration access.
    """
    return _ensure_manager()


# ---------------------------------------------------------------------------
# Convenience functions that use the default BrowserManager
# ---------------------------------------------------------------------------


def browser_status() -> BrowserManagerState:
    """Return the current state of the default :class:`BrowserManager`.

    See :meth:`BrowserManager.state`.
    """
    return _ensure_manager().state


def create_context(**kwargs: Any) -> Any:
    """Create a context from the default manager.

    Equivalent to ``BrowserManager.create_context(**kwargs)``.
    """
    return _ensure_manager().create_context(**kwargs)


def navigate(url: str, *, timeout: float = 30.0, wait_until: str = "load") -> Any:
    """Navigate the default context to *url*.

    Equivalent to calling ``navigate`` on the default manager's context.
    """
    return _ensure_manager().navigate(url, timeout=timeout, wait_until=wait_until)


def click_element(selector: str, *, timeout: float = 5.0) -> None:
    """Click an element in the default context."""
    _ensure_manager().click_element(selector, timeout=timeout)


def type_text(selector: str, text: str, *, delay: float = 0.01, timeout: float = 5.0) -> None:
    """Type *text* into an element in the default context."""
    _ensure_manager().type_text(selector, text, delay=delay, timeout=timeout)


def get_text_content(selector: str, *, timeout: float = 5.0) -> str:
    """Retrieve text content from an element in the default context."""
    return _ensure_manager().get_text_content(selector, timeout=timeout)


def capture_screenshot(*, path: str | None = None, full_page: bool = False) -> bytes:
    """Capture a screenshot from the default context."""
    return _ensure_manager().capture_screenshot(path=path, full_page=full_page)


def evaluate_script(js: str, *, timeout: float = 5.0) -> Any:
    """Evaluate JavaScript in the default context."""
    return _ensure_manager().evaluate_script(js, timeout=timeout)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Manager
    "BrowserManager",
    "BrowserManagerState",
    "get_browser_manager",
    # Convenience
    "browser_status",
    "create_context",
    "navigate",
    "click_element",
    "type_text",
    "get_text_content",
    "capture_screenshot",
    "evaluate_script",
    # Errors
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
