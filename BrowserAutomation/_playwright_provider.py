"""Playwright implementation of the browser automation interfaces.

All Playwright imports are **lazy** (imported inside methods, not at
module level) so the package can be imported and inspected without
Playwright installed.  This mirrors the pattern used by
:mod:`EyeControl`.
"""

from __future__ import annotations

import time
import uuid
from importlib.util import find_spec
from typing import Any

from fiona.interfaces import (
    BrowserConfig,
    IBrowserContext,
    IBrowserInstance,
    IBrowserProvider,
    NavigationEvent,
    NavigationResult,
)

from ._errors import (
    BrowserCrashError,
    BrowserError,
    BrowserLaunchError,
    BrowserNotRunning,
    BrowserShutdownError,
    ElementNotFound,
    ElementNotInteractable,
    NavigationTimeout,
    ScriptExecutionError,
    SelectorTimeout,
)

# ---------------------------------------------------------------------------
# Capability constants
# ---------------------------------------------------------------------------

PLAYWRIGHT_CAPABILITIES: frozenset[str] = frozenset({
    "screenshot",
    "pdf",
    "network_intercept",
    "js_eval",
    "multi_context",
    "emulation",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_playwright_installed() -> None:
    """Raise ``RuntimeError`` if Playwright is not available."""
    import sys  # noqa: PLC0415

    # Check sys.modules first (handles injected fake modules in tests)
    if "playwright" in sys.modules:
        return

    if find_spec("playwright") is None:
        msg = (
            "Playwright is not installed. Install it with:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )
        raise RuntimeError(msg)


_NEXT_CONTEXT_ID: int = 0


def _new_context_id() -> str:
    """Return a unique context identifier."""
    global _NEXT_CONTEXT_ID  # noqa: PLW0603
    _NEXT_CONTEXT_ID += 1
    # Use a short readable ID for debugging, prefixed with a UUID
    return f"{uuid.uuid4().hex[:8]}-{_NEXT_CONTEXT_ID}"


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

_WAIT_UNTIL_MAP: dict[NavigationEvent, str] = {
    NavigationEvent.LOAD: "load",
    NavigationEvent.DOM_CONTENT: "domcontentloaded",
    NavigationEvent.NETWORK_IDLE: "networkidle",
}


def _to_playwright_wait(wait_until: NavigationEvent) -> str:
    """Convert a :class:`NavigationEvent` to the Playwright string constant."""
    return _WAIT_UNTIL_MAP[wait_until]


# ---------------------------------------------------------------------------
# IBrowserContext implementation
# ---------------------------------------------------------------------------


class PlaywrightBrowserContext(IBrowserContext):
    """An isolated browser context backed by Playwright.

    Wraps a ``playwright.async_api.BrowserContext`` (or, if created
    without an explicit context, manages a single page directly).
    """

    def __init__(self, context: Any, page: Any) -> None:
        self._ctx = context
        self._page = page
        self._closed = False
        self._id = _new_context_id()

    # -- IBrowserContext ----------------------------------------------------

    async def navigate(
        self,
        url: str,
        *,
        timeout: float = 30.0,
        wait_until: NavigationEvent = NavigationEvent.LOAD,
    ) -> NavigationResult:
        self._require_open()
        pw_wait = _to_playwright_wait(wait_until)
        pw_timeout = int(timeout * 1000)  # Playwright uses ms

        try:
            response = await self._page.goto(url, wait_until=pw_wait, timeout=pw_timeout)
        except Exception as exc:
            raise _map_navigation_error(exc, timeout) from exc

        status_code: int = response.status if response is not None else 0
        redirect_chain: tuple[str, ...] = _extract_redirect_chain(response)
        title: str = await self._page.title()

        return NavigationResult(
            url=self._page.url,
            status_code=status_code,
            title=title,
            duration_ms=0.0,  # Playwright doesn't expose this directly
            redirect_chain=redirect_chain,
        )

    async def click(self, selector: str, *, timeout: float = 5.0) -> None:
        self._require_open()
        pw_timeout = int(timeout * 1000)
        try:
            await self._page.click(selector, timeout=pw_timeout)
        except Exception as exc:
            raise _map_click_error(exc, selector, timeout) from exc

    async def type_text(
        self,
        selector: str,
        text: str,
        *,
        delay: float = 0.01,
        timeout: float = 5.0,
    ) -> None:
        self._require_open()
        pw_timeout = int(timeout * 1000)
        pw_delay = int(delay * 1000)
        try:
            await self._page.fill(selector, "")
            await self._page.type(selector, text, delay=pw_delay, timeout=pw_timeout)
        except Exception as exc:
            raise _map_type_error(exc, selector, timeout) from exc

    async def get_text(self, selector: str, *, timeout: float = 5.0) -> str:
        self._require_open()
        pw_timeout = int(timeout * 1000)
        try:
            element = await self._page.wait_for_selector(selector, timeout=pw_timeout)
            if element is None:
                raise ElementNotFound(f"No element found for selector: {selector!r}")
            text = await element.text_content()
            return (text or "").strip()
        except ElementNotFound:
            raise
        except Exception as exc:
            raise _map_get_text_error(exc, selector, timeout) from exc

    async def screenshot(
        self,
        *,
        path: str | None = None,
        full_page: bool = False,
    ) -> bytes:
        self._require_open()
        try:
            data = await self._page.screenshot(path=path, full_page=full_page, type="png")
            return data
        except Exception as exc:
            raise BrowserError(f"Screenshot failed: {exc}") from exc

    async def evaluate(self, js: str, *, timeout: float = 5.0) -> Any:
        self._require_open()
        pw_timeout = int(timeout * 1000)
        try:
            return await self._page.evaluate(js, timeout=pw_timeout)
        except Exception as exc:
            raise ScriptExecutionError(f"JavaScript evaluation failed: {exc}") from exc

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._ctx.close()
        except Exception:
            pass  # idempotent — swallow errors on close

    # -- Properties ---------------------------------------------------------

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def context_id(self) -> str:
        return self._id

    # -- Internals ----------------------------------------------------------

    def _require_open(self) -> None:
        if self._closed:
            raise BrowserNotRunning("This browser context has been closed.")

    @property
    def page(self) -> Any:
        """Expose the underlying Playwright page for advanced use."""
        return self._page


# ---------------------------------------------------------------------------
# IBrowserInstance implementation
# ---------------------------------------------------------------------------


class PlaywrightBrowserInstance(IBrowserInstance):
    """A running Playwright browser process.

    Wraps a ``playwright.async_api.Browser`` instance.
    """

    def __init__(self, browser: Any, process: Any | None = None) -> None:
        self._browser = browser
        self._process = process
        self._closed = False

    # -- IBrowserInstance ---------------------------------------------------

    async def create_context(self, **kwargs: Any) -> IBrowserContext:
        self._require_open()
        try:
            pw_context = await self._browser.new_context(**kwargs)
        except Exception as exc:
            raise BrowserLaunchError(f"Failed to create browser context: {exc}") from exc

        page = await pw_context.new_page()
        return PlaywrightBrowserContext(context=pw_context, page=page)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._browser.close()
        except Exception as exc:
            raise BrowserShutdownError(f"Failed to close browser: {exc}") from exc

    # -- Properties ---------------------------------------------------------

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def pid(self) -> int | None:
        if self._browser is None:
            return None
        try:
            proc = self._browser.process
            return proc.pid if proc else None
        except Exception:
            return None

    # -- Internals ----------------------------------------------------------

    def _require_open(self) -> None:
        if self._closed:
            raise BrowserNotRunning("This browser instance has been closed.")

    @property
    def browser(self) -> Any:
        """Expose the underlying Playwright browser for advanced use."""
        return self._browser


# ---------------------------------------------------------------------------
# IBrowserProvider implementation
# ---------------------------------------------------------------------------


class PlaywrightBrowserProvider(IBrowserProvider):
    """Playwright-based browser automation provider.

    Supports Chromium, Firefox, and WebKit.  Playwright is imported
    lazily so that importing this module does not require Playwright.
    """

    # -- IBrowserProvider ---------------------------------------------------

    async def launch(self, config: BrowserConfig) -> IBrowserInstance:
        _check_playwright_installed()

        # Lazy import inside the method
        from playwright.async_api import async_playwright  # type: ignore[import-untyped]  # noqa: PLC0415

        pw_args = self._build_launch_args(config)
        try:
            pw = await async_playwright().__aenter__()
            browser_type = getattr(pw, config.browser_type)
            browser = await browser_type.launch(**pw_args)
        except Exception as exc:
            raise BrowserLaunchError(
                f"Failed to launch {config.browser_type} browser: {exc}"
            ) from exc

        return PlaywrightBrowserInstance(browser=browser)

    def name(self) -> str:
        return "playwright"

    def capabilities(self) -> set[str]:
        return set(PLAYWRIGHT_CAPABILITIES)

    # -- Internals ----------------------------------------------------------

    @staticmethod
    def _build_launch_args(config: BrowserConfig) -> dict[str, Any]:
        """Translate :class:`BrowserConfig` into Playwright ``launch()`` kwargs."""
        args: dict[str, Any] = {
            "headless": config.headless,
        }

        if config.proxy:
            args["proxy"] = {"server": config.proxy}

        if config.args:
            args["args"] = list(config.args)

        return args


# ---------------------------------------------------------------------------
# Error mapping helpers
# ---------------------------------------------------------------------------


def _map_navigation_error(exc: Exception, timeout: float) -> Exception:
    """Map a Playwright navigation exception to our error hierarchy."""
    exc_name = type(exc).__name__
    exc_str = str(exc).lower()

    if "timeout" in exc_str or exc_name == "TimeoutError":
        return NavigationTimeout(f"Navigation timed out after {timeout}s: {exc}")
    if "crash" in exc_str or "closed" in exc_str:
        return BrowserCrashError(f"Browser crash during navigation: {exc}")

    return BrowserError(f"Navigation failed: {exc}")


def _map_click_error(exc: Exception, selector: str, timeout: float) -> Exception:
    """Map a Playwright click exception to our error hierarchy."""
    exc_name = type(exc).__name__
    exc_str = str(exc).lower()

    if "timeout" in exc_str or exc_name == "TimeoutError":
        return SelectorTimeout(
            f"Timed out after {timeout}s waiting for selector {selector!r}: {exc}"
        )
    if "detached" in exc_str or "not found" in exc_str or "not attached" in exc_str or "attach" in exc_str:
        return ElementNotFound(f"Element {selector!r} not found: {exc}")
    if "intercept" in exc_str or "hidden" in exc_str or "disabled" in exc_str:
        return ElementNotInteractable(f"Element {selector!r} is not interactable: {exc}")
    if "crash" in exc_str or "closed" in exc_str:
        return BrowserCrashError(f"Browser crash during click: {exc}")

    return BrowserError(f"Click on {selector!r} failed: {exc}")


def _map_type_error(exc: Exception, selector: str, timeout: float) -> Exception:
    """Map a Playwright type-text exception to our error hierarchy."""
    exc_name = type(exc).__name__
    exc_str = str(exc).lower()

    if "timeout" in exc_str or exc_name == "TimeoutError":
        return SelectorTimeout(
            f"Timed out after {timeout}s waiting for selector {selector!r}: {exc}"
        )
    if "not editable" in exc_str or "not an input" in exc_str:
        return ElementNotInteractable(f"Element {selector!r} is not editable: {exc}")
    if "crash" in exc_str or "closed" in exc_str:
        return BrowserCrashError(f"Browser crash during type_text: {exc}")

    return BrowserError(f"Type text into {selector!r} failed: {exc}")


def _map_get_text_error(exc: Exception, selector: str, timeout: float) -> Exception:
    """Map a Playwright get-text exception to our error hierarchy."""
    exc_name = type(exc).__name__
    exc_str = str(exc).lower()

    if "timeout" in exc_str or exc_name == "TimeoutError":
        return SelectorTimeout(
            f"Timed out after {timeout}s waiting for selector {selector!r}: {exc}"
        )
    if "crash" in exc_str or "closed" in exc_str:
        return BrowserCrashError(f"Browser crash during get_text: {exc}")

    return BrowserError(f"Get text from {selector!r} failed: {exc}")


def _extract_redirect_chain(response: Any) -> tuple[str, ...]:
    """Extract the redirect URL chain from a Playwright response object."""
    urls: list[str] = []
    current = response
    while current is not None:
        urls.insert(0, current.url)
        current = current.request.redirected_from  # type: ignore[union-attr]
    return tuple(urls)
