"""Per-session synchronous wrapper around the async browser automation API.

Each :class:`SessionManager` owns a dedicated event loop, enabling
synchronous callers (CLI handlers, agent commands) to use the
async browser interfaces without managing asyncio themselves.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from ._errors import BrowserError, BrowserNotRunning
from ._manager import BrowserManager, BrowserManagerState


class SessionManager:
    """Synchronous wrapper for browser automation in CLI/agent sessions.

    Creates and manages a single :class:`BrowserManager` with its own
    event loop, running in a dedicated thread.

    Args:
        config: Configuration passed to :class:`BrowserManager`.
            If omitted, defaults are used.
    """

    def __init__(self, config: Any = None) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._manager: BrowserManager | None = None
        self._config = config
        self._ready = threading.Event()

    # -- Lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Start the session (launches the event loop thread and browser).

        Blocks until the browser is running.

        Raises:
            RuntimeError: If the session is already started.
            BrowserLaunchError: If the browser cannot be launched.
        """
        if self._loop is not None:
            raise RuntimeError("SessionManager is already started")

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=_run_loop,
            args=(self._loop,),
            daemon=True,
            name="browser-session",
        )
        self._thread.start()

        # Create the manager in the event loop thread
        future = asyncio.run_coroutine_threadsafe(
            self._async_init(), self._loop
        )
        self._manager = future.result(timeout=30)

        # Start the browser
        self._call_async(self._manager.start)

        # Create a default context so navigation/screenshot work immediately
        try:
            self._call_async(self._manager.create_context)
        except Exception:
            pass

    def stop(self) -> None:
        """Stop the session gracefully.

        Closes the browser, stops the event loop, and joins the thread.
        Idempotent.
        """
        if self._manager is None:
            return

        try:
            self._call_async(self._manager.stop)
        except Exception:
            pass

        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop = None

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)
            self._thread = None

        self._manager = None

    # -- Properties ---------------------------------------------------------

    @property
    def state(self) -> BrowserManagerState:
        """Current :class:`BrowserManagerState` of the underlying manager."""
        if self._manager is None:
            return BrowserManagerState.STOPPED
        return self._manager.state

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the browser is in a healthy running state."""
        return self.state == BrowserManagerState.RUNNING

    # -- Context management -------------------------------------------------

    def create_context(self, **kwargs: Any) -> Any:
        """Create a new browser context (synchronous wrapper)."""
        if self._manager is None:
            raise BrowserNotRunning("Session not started. Call start() first.")
        return self._call_async(self._manager.create_context, **kwargs)

    # -- Action wrappers ----------------------------------------------------

    def navigate(self, url: str, *, timeout: float = 30.0, wait_until: str = "load") -> Any:
        """Navigate to *url* (synchronous wrapper)."""
        if self._manager is None:
            raise BrowserNotRunning("Session not started. Call start() first.")
        return self._call_async(self._manager.navigate, url, timeout=timeout, wait_until=wait_until)

    def click(self, selector: str, *, timeout: float = 5.0) -> None:
        """Click an element (synchronous wrapper)."""
        if self._manager is None:
            raise BrowserNotRunning("Session not started. Call start() first.")
        return self._call_async(self._manager.click_element, selector, timeout=timeout)

    def type_text(self, selector: str, text: str, *, delay: float = 0.01, timeout: float = 5.0) -> None:
        """Type text into an element (synchronous wrapper)."""
        if self._manager is None:
            raise BrowserNotRunning("Session not started. Call start() first.")
        return self._call_async(
            self._manager.type_text, selector, text, delay=delay, timeout=timeout
        )

    def get_text(self, selector: str, *, timeout: float = 5.0) -> str:
        """Get text content from an element (synchronous wrapper)."""
        if self._manager is None:
            raise BrowserNotRunning("Session not started. Call start() first.")
        return self._call_async(self._manager.get_text_content, selector, timeout=timeout)

    def screenshot(self, *, path: str | None = None, full_page: bool = False) -> bytes:
        """Capture a screenshot (synchronous wrapper)."""
        if self._manager is None:
            raise BrowserNotRunning("Session not started. Call start() first.")
        return self._call_async(self._manager.capture_screenshot, path=path, full_page=full_page)

    def evaluate(self, js: str, *, timeout: float = 5.0) -> Any:
        """Evaluate JavaScript (synchronous wrapper)."""
        if self._manager is None:
            raise BrowserNotRunning("Session not started. Call start() first.")
        return self._call_async(self._manager.evaluate_script, js, timeout=timeout)

    # -- Internals ----------------------------------------------------------

    async def _async_init(self) -> BrowserManager:
        """Create the manager in the event-loop thread, defaults used."""
        from ._config import default_config  # noqa: PLC0415

        from ._playwright_provider import PlaywrightBrowserProvider  # noqa: PLC0415

        config = self._config if self._config is not None else default_config()
        provider = PlaywrightBrowserProvider()
        return BrowserManager(config=config, provider=provider)

    def _call_async(self, coro_factory: Any, *args: Any, **kwargs: Any) -> Any:
        """Schedule a coroutine on the event loop and wait for the result."""
        if self._loop is None:
            raise BrowserNotRunning("Session event loop is not running.")
        if not self._loop.is_running():
            raise BrowserNotRunning("Session event loop has stopped.")
        future = asyncio.run_coroutine_threadsafe(
            coro_factory(*args, **kwargs), self._loop
        )
        return future.result(timeout=60)


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Run the event loop forever (daemon thread target)."""
    asyncio.set_event_loop(loop)
    loop.run_forever()
