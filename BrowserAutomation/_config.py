"""Browser configuration handling and defaults."""

from __future__ import annotations

from fiona.interfaces import BrowserConfig


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_BROWSER_TYPE = "chromium"
DEFAULT_HEADLESS = False
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 720


def default_config(**overrides: object) -> BrowserConfig:
    """Return a :class:`BrowserConfig` with defaults merged from *overrides*.

    Args:
        **overrides: Any :class:`BrowserConfig` field to override.

    Returns:
        A frozen ``BrowserConfig`` with sensible defaults.
    """
    kwargs: dict[str, object] = {
        "browser_type": DEFAULT_BROWSER_TYPE,
        "headless": DEFAULT_HEADLESS,
        "viewport_width": DEFAULT_VIEWPORT_WIDTH,
        "viewport_height": DEFAULT_VIEWPORT_HEIGHT,
        "data_dir": None,
        "proxy": None,
        "args": (),
    }
    kwargs.update(overrides)
    return BrowserConfig(**kwargs)  # type: ignore[arg-type]


def merge_config(base: BrowserConfig, **overrides: object) -> BrowserConfig:
    """Return a new :class:`BrowserConfig` with *overrides* applied on top of *base*.

    Only fields whose values are not ``None`` in *overrides* are merged.

    Args:
        base: The base configuration to copy.
        **overrides: Override values.

    Returns:
        A new ``BrowserConfig`` with merged values.
    """
    kwargs: dict[str, object] = {
        "browser_type": overrides.get("browser_type", base.browser_type),
        "headless": overrides.get("headless", base.headless),
        "viewport_width": overrides.get("viewport_width", base.viewport_width),
        "viewport_height": overrides.get("viewport_height", base.viewport_height),
        "data_dir": overrides.get("data_dir", base.data_dir),
        "proxy": overrides.get("proxy", base.proxy),
        "args": overrides.get("args", base.args),
    }
    return BrowserConfig(**kwargs)  # type: ignore[arg-type]
