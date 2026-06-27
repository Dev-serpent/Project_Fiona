"""Selenium WebDriver provider for browser automation.

Implements :class:`IBrowserProvider`, :class:`IBrowserInstance`, and
:class:`IBrowserContext` using Selenium WebDriver with Chrome.

Design notes:

* The Playwright-downloaded Chrome binary is used as the browser
  executable, avoiding the need to install Chrome separately.
* ``webdriver-manager`` automatically handles ChromeDriver discovery
  so users never need to manage driver binaries.
* Each :class:`SeleniumBrowserContext` wraps a single ``webdriver``
  instance (equivalent to one browser window).
* The :class:`SeleniumBrowserInstance` tracks the alive WebDriver
  and provides factory methods for new contexts.
* All Selenium imports are lazy so the package can be imported
  without Selenium installed.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
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
    ElementNotFound,
    ElementNotInteractable,
    NavigationTimeout,
    ScriptExecutionError,
    SelectorTimeout,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chrome binary resolution (prefer system Chrome, then Playwright fallback)
# ---------------------------------------------------------------------------

_SYSTEM_CHROME_CANDIDATES = (
    "google-chrome-stable",
    "google-chrome",
    "chromium-browser",
    "chromium",
)
"""Ordered list of system Chrome executable names to search on ``PATH``."""

_PLAYWRIGHT_CHROME_PATH = os.path.expanduser(
    "~/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
)
"""Fallback path to the Chrome binary downloaded by Playwright.

Used when no system Chrome is found on ``PATH``.
"""


def _resolve_chrome_binary() -> str | None:
    """Return the path to a usable Chrome binary, or ``None``.

    Resolution order:
      1. ``FIONA_CHROME_BINARY`` environment variable.
      2. First system Chrome found on ``PATH``.
      3. Playwright-downloaded Chrome.
    """
    env_path = os.environ.get("FIONA_CHROME_BINARY")
    if env_path:
        if os.path.isfile(env_path):
            return env_path
        logger.warning("FIONA_CHROME_BINARY set but not found: %s", env_path)

    import shutil  # noqa: PLC0415

    for name in _SYSTEM_CHROME_CANDIDATES:
        resolved = shutil.which(name)
        if resolved:
            return resolved

    if os.path.isfile(_PLAYWRIGHT_CHROME_PATH):
        logger.info(
            "No system Chrome found; falling back to Playwright-downloaded "
            "Chrome at %s. This version may not match the ChromeDriver version "
            "managed by webdriver-manager; set FIONA_CHROME_BINARY or install "
            "Chrome via your system package manager.",
            _PLAYWRIGHT_CHROME_PATH,
        )
        return _PLAYWRIGHT_CHROME_PATH

    return None


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

SELENIUM_CAPABILITIES: frozenset[str] = frozenset({
    "screenshot",
    "js_eval",
    "click",
    "type_text",
    "get_text",
    "navigate",
    "multi_window",
})


# ---------------------------------------------------------------------------
# Selenium import helper
# ---------------------------------------------------------------------------


def _check_selenium_installed() -> None:
    """Raise ``RuntimeError`` if Selenium is not available."""
    import sys  # noqa: PLC0415

    if "selenium" in sys.modules:
        return

    from importlib.util import find_spec  # noqa: PLC0415

    if find_spec("selenium") is None:
        msg = (
            "Selenium is not installed.\n\n"
            "  pip install selenium webdriver-manager\n\n"
            "On Arch Linux you can also use:\n"
            "  sudo pacman -S python-selenium"
        )
        raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# Browser Instance
# ---------------------------------------------------------------------------


class SeleniumBrowserInstance(IBrowserInstance):
    """A running Selenium-controlled browser.

    Wraps a ``webdriver.Chrome`` instance.  Since Selenium's model maps
    one driver to one browser window, the driver itself IS the first
    context.
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        self._closed = False

    async def create_context(self, **kwargs: Any) -> IBrowserContext:
        """Create a new browser context (opens a new tab/window).

        In Selenium, a "context" is a new window/tab.  The original
        driver is used; this method opens a new tab via JavaScript and
        switches to it.
        """
        if self._closed:
            raise BrowserNotRunning("Browser instance is closed.")

        # Execute JS to open a new window (more reliable than tabs)
        self._driver.execute_script("window.open('');")
        window_handles = self._driver.window_handles
        if len(window_handles) > 1:
            self._driver.switch_to.window(window_handles[-1])

        return SeleniumBrowserContext(self._driver)

    async def close(self) -> None:
        """Kill the browser process."""
        if self._closed:
            return
        self._closed = True
        try:
            self._driver.quit()
        except Exception as exc:
            raise BrowserError(f"Failed to close browser: {exc}") from exc

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def pid(self) -> int | None:
        try:
            return self._driver.service.process.pid if self._driver.service.process else None
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Browser Context (single window/tab)
# ---------------------------------------------------------------------------


class SeleniumBrowserContext(IBrowserContext):
    """A browser window/tab controlled via Selenium WebDriver.

    Every operation uses the shared WebDriver and switches to this
    context's window handle before acting.
    """

    def __init__(self, driver: Any, window_handle: str | None = None) -> None:
        self._driver = driver
        self._handle = window_handle or driver.current_window_handle
        self._id = uuid.uuid4().hex[:12]
        self._closed = False

    def _switch(self) -> None:
        """Switch the WebDriver to this context's window handle."""
        if self._closed:
            raise BrowserNotRunning("Context is closed.")
        try:
            if self._driver.current_window_handle != self._handle:
                self._driver.switch_to.window(self._handle)
        except Exception as exc:
            raise BrowserCrashError(f"Window handle {self._handle} lost: {exc}") from exc

    def _check_alive(self) -> None:
        """Ensure the underlying driver is still responsive."""
        if self._closed:
            raise BrowserNotRunning("Context is closed.")
        try:
            # Ping the driver
            _ = self._driver.title
        except Exception as exc:
            raise BrowserCrashError(f"Browser crashed: {exc}") from exc

    # -- IBrowserContext --------------------------------------------------

    async def navigate(
        self,
        url: str,
        *,
        timeout: float = 30.0,
        wait_until: NavigationEvent = NavigationEvent.LOAD,
    ) -> NavigationResult:
        self._check_alive()
        self._switch()

        start = time.monotonic()
        try:
            self._driver.get(url)
        except Exception as exc:
            raise NavigationTimeout(
                f"Navigation timed out after {timeout}s: {exc}"
            ) from exc

        duration_ms = (time.monotonic() - start) * 1000

        # Wait strategy based on NavigationEvent
        try:
            if wait_until == NavigationEvent.LOAD:
                self._wait_for_page_load(timeout)
            elif wait_until == NavigationEvent.DOM_CONTENT:
                self._wait_for_dom_ready(timeout)
            elif wait_until == NavigationEvent.NETWORK_IDLE:
                self._wait_for_network_idle(timeout)
        except Exception as exc:
            if "timeout" in str(exc).lower():
                raise NavigationTimeout(
                    f"Page did not reach '{wait_until.value}' within {timeout}s"
                ) from exc
            raise BrowserError(f"Navigation wait failed: {exc}") from exc

        return NavigationResult(
            url=self._driver.current_url,
            status_code=self._get_status_code(),
            title=self._driver.title,
            duration_ms=duration_ms,
            redirect_chain=(),
        )

    def _wait_for_page_load(self, timeout: float) -> None:
        """Wait for ``document.readyState === 'complete'``."""
        import selenium.webdriver.support.expected_conditions as EC  # noqa: PLC0415
        from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415

        WebDriverWait(self._driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    def _wait_for_dom_ready(self, timeout: float) -> None:
        """Wait for ``document.readyState !== 'loading'``."""
        import selenium.webdriver.support.expected_conditions as EC  # noqa: PLC0415
        from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415

        WebDriverWait(self._driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") != "loading"
        )

    def _wait_for_network_idle(self, timeout: float) -> None:
        """Wait for network idle via JS performance API (best-effort)."""
        import selenium.webdriver.support.expected_conditions as EC  # noqa: PLC0415
        from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415

        WebDriverWait(self._driver, timeout).until(
            lambda d: d.execute_script(
                "return window.performance.getEntriesByType('resource').length > 0"
                "? false : true"
            )
        )

    def _get_status_code(self) -> int:
        """Try to extract the HTTP status code from DevTools.

        Falls back to 200 if unavailable.
        """
        try:
            logs = self._driver.get_log("performance")
            for entry in logs:
                import json  # noqa: PLC0415
                try:
                    msg = json.loads(entry["message"])
                    params = msg.get("message", {}).get("params", {})
                    response = params.get("response", {})
                    if response.get("url") == self._driver.current_url:
                        return response.get("status", 200)
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        except Exception:
            pass
        return 200

    async def click(self, selector: str, *, timeout: float = 5.0) -> None:
        """Click the first element matching a CSS selector."""
        self._check_alive()
        self._switch()

        from selenium.webdriver.common.by import By  # noqa: PLC0415
        from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415
        from selenium.webdriver.support import expected_conditions as EC  # noqa: PLC0415
        from selenium.common.exceptions import (
            TimeoutException,
            ElementClickInterceptedException,
            ElementNotInteractableException,
        )  # noqa: PLC0415

        try:
            element = WebDriverWait(self._driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.click()
        except TimeoutException as exc:
            raise SelectorTimeout(
                f"Element '{selector}' did not become clickable within {timeout}s"
            ) from exc
        except ElementClickInterceptedException as exc:
            raise ElementNotInteractable(
                f"Element '{selector}' was intercepted: {exc}"
            ) from exc
        except ElementNotInteractableException as exc:
            raise ElementNotInteractable(
                f"Element '{selector}' is not interactable: {exc}"
            ) from exc

    async def type_text(
        self,
        selector: str,
        text: str,
        *,
        delay: float = 0.01,
        timeout: float = 5.0,
    ) -> None:
        """Type text into an editable element."""
        self._check_alive()
        self._switch()

        from selenium.webdriver.common.by import By  # noqa: PLC0415
        from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415
        from selenium.webdriver.support import expected_conditions as EC  # noqa: PLC0415
        from selenium.common.exceptions import TimeoutException  # noqa: PLC0415

        try:
            element = WebDriverWait(self._driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.clear()
            if delay > 0:
                element.send_keys(text)  # Selenium handles typing natively
            else:
                element.send_keys(text)
        except TimeoutException as exc:
            raise SelectorTimeout(
                f"Element '{selector}' did not appear within {timeout}s"
            ) from exc

    async def get_text(self, selector: str, *, timeout: float = 5.0) -> str:
        """Retrieve the ``textContent`` of the first matching element."""
        self._check_alive()
        self._switch()

        from selenium.webdriver.common.by import By  # noqa: PLC0415
        from selenium.webdriver.support.ui import WebDriverWait  # noqa: PLC0415
        from selenium.webdriver.support import expected_conditions as EC  # noqa: PLC0415
        from selenium.common.exceptions import TimeoutException  # noqa: PLC0415

        try:
            element = WebDriverWait(self._driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element.text
        except TimeoutException as exc:
            raise SelectorTimeout(
                f"Element '{selector}' not found within {timeout}s"
            ) from exc

    async def screenshot(
        self,
        *,
        path: str | None = None,
        full_page: bool = False,
    ) -> bytes:
        """Capture a screenshot of the current page."""
        self._check_alive()
        self._switch()

        if full_page:
            # Compute full page dimensions via JS and set window size
            try:
                total_width = self._driver.execute_script(
                    "return Math.max(document.body.scrollWidth, "
                    "document.documentElement.scrollWidth);"
                )
                total_height = self._driver.execute_script(
                    "return Math.max(document.body.scrollHeight, "
                    "document.documentElement.scrollHeight);"
                )
                self._driver.set_window_size(total_width, total_height)
            except Exception:
                pass  # Fall back to viewport screenshot

        png_bytes = self._driver.get_screenshot_as_png()

        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "wb") as f:
                f.write(png_bytes)

        # Restore viewport to original size after full-page capture
        if full_page:
            try:
                self._driver.set_window_size(1280, 720)
            except Exception:
                pass

        return png_bytes

    async def evaluate(self, js: str, *, timeout: float = 5.0) -> Any:
        """Execute JavaScript in the page's main frame context."""
        self._check_alive()
        self._switch()

        try:
            return self._driver.execute_script(js)
        except Exception as exc:
            raise ScriptExecutionError(
                f"JavaScript execution failed: {exc}"
            ) from exc

    async def close(self) -> None:
        """Close this context (tab/window)."""
        if self._closed:
            return
        self._closed = True
        try:
            # Switch to this handle and close the window
            if self._handle in self._driver.window_handles:
                self._driver.switch_to.window(self._handle)
                self._driver.close()
                # Switch to the last remaining window
                if self._driver.window_handles:
                    self._driver.switch_to.window(self._driver.window_handles[-1])
        except Exception:
            pass  # Window may already be closed

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def context_id(self) -> str:
        return self._id


# ---------------------------------------------------------------------------
# Browser Provider
# ---------------------------------------------------------------------------


class SeleniumBrowserProvider(IBrowserProvider):
    """Selenium-based browser automation provider.

    Uses Chrome/Chromium via Selenium WebDriver.  The binary path
    resolution follows :func:`_resolve_chrome_binary` — prefer system
    Chrome, then Playwright-downloaded Chrome as fallback.  Override
    via the ``FIONA_CHROME_BINARY`` environment variable.
    """

    async def launch(self, config: BrowserConfig) -> IBrowserInstance:
        _check_selenium_installed()

        # Lazy imports
        from selenium import webdriver  # noqa: PLC0415
        from selenium.webdriver.chrome.options import Options  # noqa: PLC0415
        from selenium.webdriver.chrome.service import Service  # noqa: PLC0415
        from webdriver_manager.chrome import ChromeDriverManager  # noqa: PLC0415

        chrome_opts = Options()

        # ── Binary location ────────────────────────────────────────────
        chrome_binary = _resolve_chrome_binary()
        if chrome_binary:
            chrome_opts.binary_location = chrome_binary

        # ── Headless mode ──────────────────────────────────────────────
        if config.headless:
            chrome_opts.add_argument("--headless=new")

        # ── Viewport ───────────────────────────────────────────────────
        chrome_opts.add_argument(f"--window-size={config.viewport_width},{config.viewport_height}")

        # ── Additional arguments ───────────────────────────────────────
        chrome_opts.add_argument("--no-sandbox")
        chrome_opts.add_argument("--disable-dev-shm-usage")
        chrome_opts.add_argument("--disable-gpu")
        chrome_opts.add_argument("--disable-extensions")
        chrome_opts.add_argument("--disable-background-networking")
        chrome_opts.add_argument("--disable-sync")
        chrome_opts.add_argument("--disable-default-apps")
        chrome_opts.add_argument("--mute-audio")
        chrome_opts.add_argument("--remote-debugging-port=0")

        # Performance logging for status code detection
        chrome_opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        # Apply any user-provided args
        for arg in config.args:
            if arg not in chrome_opts.arguments:
                chrome_opts.add_argument(arg)

        # ── Proxy ──────────────────────────────────────────────────────
        if config.proxy:
            chrome_opts.add_argument(f"--proxy-server={config.proxy}")

        # ── User data dir ──────────────────────────────────────────────
        if config.data_dir:
            chrome_opts.add_argument(f"--user-data-dir={config.data_dir}")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_opts)
        except Exception as exc:
            raise BrowserLaunchError(
                f"Failed to launch Chrome with Selenium: {exc}"
            ) from exc

        return SeleniumBrowserInstance(driver)

    def name(self) -> str:
        return "selenium"

    def capabilities(self) -> set[str]:
        return set(SELENIUM_CAPABILITIES)
