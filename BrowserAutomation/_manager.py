"""Browser lifecycle manager with state machine.

State machine::

    STOPPED → STARTING → RUNNING ↔ DEGRADED → ERROR
      ↑                                      │
      └──────────── restart() ───────────────┘

Thread-safety is provided via ``threading.Lock``.
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any

from fiona.interfaces import BrowserConfig, BrowserEvent, EventBus, IBrowserContext

from ._config import default_config, merge_config
from ._errors import (
    BrowserCrashError,
    BrowserError,
    BrowserLaunchError,
    BrowserNotRunning,
    BrowserShutdownError,
)
from ._playwright_provider import PlaywrightBrowserProvider


class BrowserManagerState(Enum):
    """Possible states of a :class:`BrowserManager`."""

    STOPPED = "stopped"
    """The browser is not running and has not been started."""

    STARTING = "starting"
    """The browser process is being launched."""

    RUNNING = "running"
    """The browser is running and healthy."""

    DEGRADED = "degraded"
    """The browser is running but in a reduced-capability state."""

    ERROR = "error"
    """The browser has crashed and auto-restart was attempted but failed."""


# ---------------------------------------------------------------------------
# BrowserManager
# ---------------------------------------------------------------------------

_AUTO_RESTART_ATTEMPTS = 1
"""Number of automatic restart attempts after an unexpected crash."""


class BrowserManager:
    """Manages the lifecycle of a browser instance.

    Provides a thread-safe state machine that tracks browser health,
    supports auto-restart on crash, and publishes lifecycle events
    to an optional :class:`~fiona.interfaces.EventBus`.

    Args:
        config: Browser configuration.  If omitted, defaults are used.
        provider: Browser provider.  If omitted, a new
            :class:`PlaywrightBrowserProvider` is created.
        event_bus: Optional event bus for publishing lifecycle events.
    """

    def __init__(
        self,
        config: BrowserConfig | None = None,
        provider: PlaywrightBrowserProvider | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config = config or default_config()
        self._provider = provider or PlaywrightBrowserProvider()
        self._event_bus = event_bus

        self._lock = threading.Lock()
        self._state = BrowserManagerState.STOPPED
        self._instance: Any = None  # IBrowserInstance
        self._contexts: dict[str, IBrowserContext] = {}
        self._crash_count = 0

    # -- Public API ---------------------------------------------------------

    @property
    def state(self) -> BrowserManagerState:
        """Return the current :class:`BrowserManagerState`."""
        with self._lock:
            return self._state

    @property
    def config(self) -> BrowserConfig:
        """Return the current :class:`BrowserConfig`."""
        return self._config

    def update_config(self, **overrides: object) -> None:
        """Merge *overrides* into the active config (applied on next start)."""
        with self._lock:
            self._config = merge_config(self._config, **overrides)

    # -- Lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        """Start the browser.

        Transitions: ``STOPPED → STARTING → RUNNING``

        Raises:
            BrowserLaunchError: If the browser cannot be launched.
            RuntimeError: If called from an invalid state
                (e.g. already running or starting).
        """
        with self._lock:
            self._assert_state("start", BrowserManagerState.STOPPED)
            self._state = BrowserManagerState.STARTING
            self._crash_count = 0

        try:
            instance = await self._provider.launch(self._config)
            with self._lock:
                self._instance = instance
                self._state = BrowserManagerState.RUNNING
                self._publish_event_locked("BrowserLaunched", context_id="")
        except Exception as exc:
            with self._lock:
                self._state = BrowserManagerState.ERROR
                self._instance = None
            raise BrowserLaunchError(f"Failed to start browser: {exc}") from exc

    async def stop(self) -> None:
        """Stop the browser and close all contexts.

        Transitions: ``{RUNNING, DEGRADED, ERROR} → STOPPED``

        This method is idempotent — calling it while already stopped
        is a no-op.
        """
        contexts: dict[str, IBrowserContext] = {}
        instance: Any = None

        with self._lock:
            if self._state == BrowserManagerState.STOPPED:
                return
            self._state = BrowserManagerState.STOPPED
            contexts = dict(self._contexts)
            self._contexts.clear()
            instance = self._instance
            self._instance = None

        # Close resources outside the lock to avoid deadlocks.
        for ctx in contexts.values():
            try:
                await ctx.close()
            except Exception:
                pass

        if instance is not None:
            try:
                await instance.close()
            except BrowserShutdownError:
                raise
            except Exception as exc:
                raise BrowserShutdownError(f"Failed to stop browser: {exc}") from exc

    async def restart(self) -> None:
        """Restart the browser.

        Transitions: ``{RUNNING, DEGRADED, ERROR} → STARTING → RUNNING``

        This is safe to call when already stopped (acts as ``start()``).
        """
        if self.state == BrowserManagerState.STOPPED:
            await self.start()
            return

        await self.stop()
        await self.start()

    # -- Context management -------------------------------------------------

    async def create_context(self, **kwargs: Any) -> IBrowserContext:
        """Create a new isolated browser context.

        Args:
            **kwargs: Options passed through to the provider.

        Returns:
            A new :class:`IBrowserContext`.

        Raises:
            BrowserNotRunning: The browser is not in a running state.
        """
        with self._lock:
            if self._state not in (BrowserManagerState.RUNNING, BrowserManagerState.DEGRADED):
                raise BrowserNotRunning(
                    f"Cannot create context: browser is {self._state.value}"
                )
            if self._instance is None:
                raise BrowserNotRunning("No browser instance available.")

            instance = self._instance

        try:
            ctx = await instance.create_context(**kwargs)
        except Exception as exc:
            await self._handle_crash(exc)
            raise BrowserError(f"Failed to create context: {exc}") from exc

        with self._lock:
            self._contexts[ctx.context_id] = ctx
            self._publish_event_locked(
                "BrowserContextCreated",
                context_id=ctx.context_id,
            )

        return ctx

    async def close_context(self, context_id: str) -> None:
        """Close a specific browser context.

        Args:
            context_id: The context ID to close.
        """
        ctx: IBrowserContext | None = None
        with self._lock:
            ctx = self._contexts.pop(context_id, None)

        if ctx is not None:
            await ctx.close()

    # -- Convenience wrappers (one-context mode) ----------------------------

    def _require_default_context(self) -> IBrowserContext:
        """Return the first (or only) context or raise."""
        with self._lock:
            if not self._contexts:
                raise BrowserNotRunning("No browser context available. Call create_context() first.")
            return next(iter(self._contexts.values()))

    async def navigate(
        self,
        url: str,
        *,
        timeout: float = 30.0,
        wait_until: str = "load",
    ) -> Any:
        """Navigate the default context to *url*."""
        from fiona.interfaces import NavigationEvent  # noqa: PLC0415

        ctx = self._require_default_context()
        wait = NavigationEvent(wait_until)
        result = await ctx.navigate(url, timeout=timeout, wait_until=wait)

        # Publish NavigationCompleted event
        if result is not None:
            status_code = getattr(result, "status_code", 200)
            final_url = getattr(result, "url", url)
            ctx_id = getattr(ctx, "context_id", "")
            self._publish_event_locked(
                "NavigationCompleted",
                context_id=ctx_id,
                url=final_url,
                status=status_code,
            )

        return result

    async def click_element(self, selector: str, *, timeout: float = 5.0) -> None:
        """Click an element in the default context."""
        ctx = self._require_default_context()
        await ctx.click(selector, timeout=timeout)

    async def type_text(
        self, selector: str, text: str, *, delay: float = 0.01, timeout: float = 5.0
    ) -> None:
        """Type *text* into an element in the default context."""
        ctx = self._require_default_context()
        await ctx.type_text(selector, text, delay=delay, timeout=timeout)

    async def get_text_content(self, selector: str, *, timeout: float = 5.0) -> str:
        """Retrieve text content from an element in the default context."""
        ctx = self._require_default_context()
        return await ctx.get_text(selector, timeout=timeout)

    async def capture_screenshot(
        self, *, path: str | None = None, full_page: bool = False
    ) -> bytes:
        """Capture a screenshot from the default context."""
        ctx = self._require_default_context()
        return await ctx.screenshot(path=path, full_page=full_page)

    async def evaluate_script(self, js: str, *, timeout: float = 5.0) -> Any:
        """Evaluate JavaScript in the default context."""
        ctx = self._require_default_context()
        return await ctx.evaluate(js, timeout=timeout)

    # -- Internal helpers ---------------------------------------------------

    async def _handle_crash(self, exc: Exception) -> None:
        """Handle an unexpected crash with auto-restart logic."""
        should_restart = False
        with self._lock:
            self._crash_count += 1
            self._state = BrowserManagerState.ERROR
            self._publish_event_locked(
                "BrowserCrashed",
                context_id="",
                reason=str(exc),
            )
            should_restart = self._crash_count <= _AUTO_RESTART_ATTEMPTS

        if should_restart:
            try:
                instance = await self._provider.launch(self._config)
                with self._lock:
                    self._instance = instance
                    self._state = BrowserManagerState.RUNNING
                    self._publish_event_locked("BrowserLaunched", context_id="")
            except Exception:
                with self._lock:
                    self._state = BrowserManagerState.ERROR
                    self._instance = None

    def _assert_state(self, operation: str, *expected: BrowserManagerState) -> None:
        """Validate the current state is one of *expected*."""
        if self._state not in expected:
            allowed = ", ".join(s.value for s in expected)
            raise RuntimeError(
                f"Cannot {operation} while state is {self._state.value!r} "
                f"(expected {allowed})"
            )

    def _publish_event_locked(self, event_name: str, **kwargs: Any) -> None:
        """Publish a browser event (caller must hold ``_lock``)."""
        if self._event_bus is None:
            return

        # Map event name to class
        from fiona.interfaces import (  # noqa: PLC0415
            BrowserContextCreated,
            BrowserCrashed,
            BrowserLaunched,
            NavigationCompleted,
        )

        event_map = {
            "BrowserLaunched": BrowserLaunched,
            "BrowserCrashed": BrowserCrashed,
            "BrowserContextCreated": BrowserContextCreated,
            "NavigationCompleted": NavigationCompleted,
        }

        cls = event_map.get(event_name)
        if cls is None:
            return

        event = cls(
            timestamp=time.time(),
            source="BrowserAutomation",
            **kwargs,
        )
        self._event_bus.publish(event)
