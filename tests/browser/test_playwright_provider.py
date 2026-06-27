"""Mock-based tests for the Playwright provider.

These tests **never** import Playwright at module level — all mocking
happens via monkey-patching ``find_spec`` and ``async_playwright``
at runtime.

.. deprecated::
   The Playwright provider has been replaced by
   :class:`BrowserAutomation._selenium_provider.SeleniumBrowserProvider`.
   These tests are preserved for reference only and are all skipped.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from BrowserAutomation._playwright_provider import PlaywrightBrowserProvider
from BrowserAutomation._errors import (
    BrowserLaunchError,
    BrowserNotRunning,
    BrowserShutdownError,
    ElementNotFound,
    ElementNotInteractable,
    NavigationTimeout,
    ScriptExecutionError,
    SelectorTimeout,
)
from fiona.interfaces import BrowserConfig, NavigationEvent

pytestmark = pytest.mark.skip(reason="Playwright provider is deprecated; replaced by SeleniumBrowserProvider")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def provider() -> PlaywrightBrowserProvider:
    return PlaywrightBrowserProvider()


@pytest.fixture()
def config() -> BrowserConfig:
    return BrowserConfig(
        browser_type="chromium",
        headless=True,
        viewport_width=1280,
        viewport_height=720,
    )


# ---------------------------------------------------------------------------
# Mock helpers (avoid importing playwright at module level)
# ---------------------------------------------------------------------------


def _make_timeout_error(message: str = "Timeout") -> Exception:
    """Create a Playwright-like timeout exception."""
    cls = type("TimeoutError", (Exception,), {})
    return cls(message)


# ---------------------------------------------------------------------------
# Provider basics
# ---------------------------------------------------------------------------


class TestProviderBasics:
    def test_provider_name(self, provider: PlaywrightBrowserProvider) -> None:
        assert provider.name() == "playwright"

    def test_capabilities(self, provider: PlaywrightBrowserProvider) -> None:
        caps = provider.capabilities()
        assert "screenshot" in caps
        assert "js_eval" in caps
        assert "multi_context" in caps
        assert "emulation" in caps

    def test_capabilities_is_copy(self, provider: PlaywrightBrowserProvider) -> None:
        caps = provider.capabilities()
        caps.add("extra")
        assert "extra" not in provider.capabilities()


# ---------------------------------------------------------------------------
# Launch / close lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLaunchLifecycle:
    async def test_launch_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        assert instance is not None
        assert instance.is_closed is False
        assert instance.pid is not None

    @pytest.mark.skip(reason="PlaywrightProvider is deprecated; replaced by SeleniumBrowserProvider")
    async def test_launch_browser_launch_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, launch_should_fail=True)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        with pytest.raises(BrowserLaunchError, match="Failed to launch"):
            await provider.launch(config)

    async def test_close_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        assert instance.is_closed is False
        await instance.close()
        assert instance.is_closed is True

    async def test_idempotent_close(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        await instance.close()
        await instance.close()  # second call should not raise
        assert instance.is_closed is True

    async def test_create_context_after_close_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        await instance.close()
        with pytest.raises(BrowserNotRunning):
            await instance.create_context()


# ---------------------------------------------------------------------------
# create_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestContextCreation:
    async def test_create_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        assert ctx is not None
        assert ctx.is_closed is False
        assert ctx.context_id is not None

    async def test_close_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        assert ctx.is_closed is False
        await ctx.close()
        assert ctx.is_closed is True


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNavigation:
    async def test_navigate_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        result = await ctx.navigate("https://example.com")
        assert result.url == "https://example.com/"
        assert result.status_code == 200
        assert result.title == "Example Domain"

    async def test_navigate_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, navigation_should_timeout=True)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        with pytest.raises(NavigationTimeout):
            await ctx.navigate("https://example.com", timeout=0.1)

    async def test_navigate_with_dom_content_wait(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        result = await ctx.navigate(
            "https://example.com",
            wait_until=NavigationEvent.DOM_CONTENT,
        )
        assert result.status_code == 200


# ---------------------------------------------------------------------------
# Click
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestClick:
    async def test_click_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        await ctx.navigate("https://example.com")
        await ctx.click("a")  # Should not raise

    async def test_click_selector_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, click_should_timeout=True)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        with pytest.raises(SelectorTimeout):
            await ctx.click(".nonexistent", timeout=0.1)

    async def test_click_element_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, click_error_msg="Element is not attached to the DOM")
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        with pytest.raises(ElementNotFound):
            await ctx.click(".missing")

    async def test_click_element_not_interactable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, click_error_msg="element is hidden")
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        with pytest.raises(ElementNotInteractable):
            await ctx.click(".hidden")


# ---------------------------------------------------------------------------
# Type text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTypeText:
    async def test_type_text_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        await ctx.navigate("https://example.com")
        await ctx.type_text("input", "hello world")

    async def test_type_text_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, type_should_timeout=True)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        with pytest.raises(SelectorTimeout):
            await ctx.type_text("input", "hello", timeout=0.1)


# ---------------------------------------------------------------------------
# Get text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetText:
    async def test_get_text_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        await ctx.navigate("https://example.com")
        text = await ctx.get_text("h1")
        assert "Example" in text

    async def test_get_text_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, get_text_should_timeout=True)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        with pytest.raises(SelectorTimeout):
            await ctx.get_text(".nonexistent", timeout=0.1)

    async def test_get_text_element_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, get_text_result=None)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        with pytest.raises(ElementNotFound):
            await ctx.get_text(".nonexistent")


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestScreenshot:
    async def test_screenshot_returns_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        data = await ctx.screenshot()
        assert isinstance(data, bytes)
        assert len(data) > 0

    async def test_screenshot_with_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        dest = str(tmp_path / "test.png")  # type: ignore[operator]
        data = await ctx.screenshot(path=dest)
        assert isinstance(data, bytes)


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEvaluate:
    async def test_evaluate_returns_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        result = await ctx.evaluate("1 + 1")
        assert result == 2

    async def test_evaluate_script_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_mocks(monkeypatch, evaluate_should_fail=True)
        provider = PlaywrightBrowserProvider()
        config = BrowserConfig(browser_type="chromium", headless=True)
        instance = await provider.launch(config)
        ctx = await instance.create_context()
        with pytest.raises(ScriptExecutionError):
            await ctx.evaluate("not valid js {{")


# ---------------------------------------------------------------------------
# Configuration handling
# ---------------------------------------------------------------------------


class TestConfigHandling:
    def test_proxy_config_passed_to_launch(self) -> None:
        config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            proxy="http://proxy:8080",
        )
        args = PlaywrightBrowserProvider._build_launch_args(config)
        assert args["proxy"] == {"server": "http://proxy:8080"}

    def test_extra_args_passed_to_launch(self) -> None:
        config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            args=("--disable-gpu", "--no-sandbox"),
        )
        args = PlaywrightBrowserProvider._build_launch_args(config)
        assert "--disable-gpu" in args["args"]
        assert "--no-sandbox" in args["args"]


# ---------------------------------------------------------------------------
# Mock infrastructure
# ---------------------------------------------------------------------------


def _install_mocks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    launch_should_fail: bool = False,
    navigation_should_timeout: bool = False,
    click_should_timeout: bool = False,
    click_error_msg: str | None = None,
    type_should_timeout: bool = False,
    get_text_should_timeout: bool = False,
    get_text_result: str | None = "Example Domain",
    evaluate_should_fail: bool = False,
) -> None:
    """Monkey-patch ``find_spec`` and the async_playwright entry point."""

    # 1. Make playwright appear installed
    original_find_spec = __import__("importlib.util", fromlist=["find_spec"]).find_spec

    def _mock_find_spec(name: str) -> object:
        if name == "playwright":
            return MagicMock()
        return original_find_spec(name)

    monkeypatch.setattr("importlib.util.find_spec", _mock_find_spec)

    # 2. Inject fake playwright module into sys.modules so that the
    #    lazy import inside PlaywrightBrowserProvider.launch() resolves
    #    to our mock instead of requiring real playwright.
    mock_page = _MockPage(
        navigation_should_timeout=navigation_should_timeout,
        click_should_timeout=click_should_timeout,
        click_error_msg=click_error_msg,
        type_should_timeout=type_should_timeout,
        get_text_should_timeout=get_text_should_timeout,
        get_text_result=get_text_result,
        evaluate_should_fail=evaluate_should_fail,
    )

    mock_browser_type = _MockBrowserType(launch_should_fail=launch_should_fail, page=mock_page)
    mock_pw = _MockPlaywright(mock_browser_type)
    mock_async_pw = _MockAsyncPlaywright(mock_pw)

    # Inject into sys.modules before the provider's launch() imports it.
    _inject_fake_playwright_module(mock_async_pw)

    # Also patch find_spec so that importlib can find "playwright"
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: MagicMock() if name == "playwright" else original_find_spec(name),
    )


class _MockAsyncPlaywright:
    """Replacement for ``playwright.async_api.async_playwright()`` context manager."""

    def __init__(self, mock_pw: _MockPlaywright | None = None) -> None:
        self._mock_pw = mock_pw or _MockPlaywright()

    def __call__(self) -> _MockAsyncPlaywright:
        return self

    async def __aenter__(self) -> _MockPlaywright:
        return self._mock_pw

    async def __aexit__(self, *args: object) -> None:
        pass


class _MockPlaywright:
    """Mimics a Playwright object with browser type attributes."""

    def __init__(self, browser_type: _MockBrowserType | None = None) -> None:
        self._browser_type = browser_type or _MockBrowserType()

    def __getattr__(self, name: str) -> object:
        if name in ("chromium", "firefox", "webkit"):
            return self._browser_type
        msg = f"No mock for {name!r}"
        raise AttributeError(msg)


class _MockBrowserType:
    """Mimics a Playwright browser type (e.g. ``chromium``)."""

    def __init__(
        self,
        launch_should_fail: bool = False,
        page: _MockPage | None = None,
    ) -> None:
        self._launch_should_fail = launch_should_fail
        self._page = page or _MockPage()

    async def launch(self, **kwargs: object) -> _MockBrowser:
        if self._launch_should_fail:
            raise RuntimeError("executable not found")
        return _MockBrowser(page=self._page)


class _MockBrowser:
    """Mimics a Playwright ``Browser`` object."""

    def __init__(self, page: _MockPage | None = None) -> None:
        self._closed = False
        self._page = page or _MockPage()
        self.process = MagicMock()
        self.process.pid = 12345

    async def close(self) -> None:
        self._closed = True

    async def new_context(self, **kwargs: object) -> _MockPWContext:
        return _MockPWContext(page=self._page)


class _MockPWContext:
    """Mimics a Playwright ``BrowserContext`` object."""

    def __init__(self, page: _MockPage | None = None) -> None:
        self._page = page or _MockPage()

    async def new_page(self) -> _MockPage:
        return self._page

    async def close(self) -> None:
        pass


class _MockPage:
    """Mimics a Playwright ``Page`` object with configurable error scenarios."""

    def __init__(
        self,
        navigation_should_timeout: bool = False,
        click_should_timeout: bool = False,
        click_error_msg: str | None = None,
        type_should_timeout: bool = False,
        get_text_should_timeout: bool = False,
        get_text_result: str | None = "Example Domain",
        evaluate_should_fail: bool = False,
    ) -> None:
        self._navigation_should_timeout = navigation_should_timeout
        self._click_should_timeout = click_should_timeout
        self._click_error_msg = click_error_msg
        self._type_should_timeout = type_should_timeout
        self._get_text_should_timeout = get_text_should_timeout
        self._get_text_result = get_text_result
        self._evaluate_should_fail = evaluate_should_fail
        self._closed = False
        self._url = "about:blank"
        self._title_value = ""

    @property
    def url(self) -> str:
        return self._url

    async def title(self) -> str:
        return self._title_value

    async def goto(
        self,
        url: str,
        *,
        wait_until: str = "load",
        timeout: int = 30000,
    ) -> _MockResponse | None:
        if self._navigation_should_timeout:
            raise _make_timeout_error("Navigation timeout")
        self._url = url
        if url == "https://example.com":
            self._url = "https://example.com/"
            self._title_value = "Example Domain"
            return _MockResponse(200, url)
        return _MockResponse(200, url)

    async def click(self, selector: str, *, timeout: int = 5000) -> None:
        if self._click_should_timeout:
            raise _make_timeout_error("waiting for selector")
        if self._click_error_msg:
            msg = self._click_error_msg
            if "attach" in msg.lower():
                raise Exception("Element is not attached to the DOM")
            if "hidden" in msg.lower():
                raise Exception("element is hidden")
            raise Exception(msg)

    async def fill(self, selector: str, value: str) -> None:
        pass

    async def type(self, selector: str, text: str, *, delay: int = 10, timeout: int = 5000) -> None:
        if self._type_should_timeout:
            raise _make_timeout_error("waiting for selector")

    async def wait_for_selector(self, selector: str, *, timeout: int = 5000) -> _MockElement | None:
        if self._get_text_should_timeout:
            raise _make_timeout_error("waiting for selector")
        if self._get_text_result is not None:
            return _MockElement(self._get_text_result)
        return None

    async def screenshot(
        self,
        *,
        path: str | None = None,
        full_page: bool = False,
        type: str = "png",
    ) -> bytes:
        return b"PNG-data-12345"

    async def evaluate(self, js: str, *, timeout: int = 5000) -> object:
        if self._evaluate_should_fail:
            raise Exception("SyntaxError")
        if js == "1 + 1":
            return 2
        return None


class _MockResponse:
    """Mimics a Playwright ``Response`` object."""

    def __init__(self, status: int, url: str) -> None:
        self.status = status
        self.url = url
        self.request = MagicMock()
        self.request.redirected_from = None


class _MockElement:
    """Mimics a Playwright element handle."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def text_content(self) -> str:
        return self._text


# ---------------------------------------------------------------------------
# Fake playwright module injection
# ---------------------------------------------------------------------------


def _inject_fake_playwright_module(mock_async_pw: _MockAsyncPlaywright | None = None) -> None:
    """Inject a fake ``playwright`` package into ``sys.modules``.

    This allows ``from playwright.async_api import async_playwright``
    inside the provider's ``launch()`` method to resolve without
    Playwright being installed.
    """
    import sys  # noqa: PLC0415

    if mock_async_pw is None:
        mock_async_pw = _MockAsyncPlaywright()

    class _FakeAsyncAPI:
        """Fake ``playwright.async_api`` module."""

        @staticmethod
        def async_playwright() -> _MockAsyncPlaywright:
            return mock_async_pw

    class _FakePlaywright:
        """Fake top-level ``playwright`` module."""

        async_api = _FakeAsyncAPI()

    fake_pw = _FakePlaywright()
    sys.modules["playwright"] = fake_pw
    sys.modules["playwright.async_api"] = fake_pw.async_api
