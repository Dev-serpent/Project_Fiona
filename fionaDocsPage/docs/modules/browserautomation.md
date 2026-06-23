# BrowserAutomation

BrowserAutomation provides Playwright-based browser automation for Fiona. It wraps Playwright with the interface contracts defined in `fiona.interfaces` and exposes a thread-safe state machine, synchronous session wrappers for CLI integration, and a comprehensive error hierarchy.

All Playwright dependencies are imported **lazily** so the package can be imported and inspected without Playwright installed.

## State Machine

The `BrowserManager` uses a thread-safe state machine to track browser lifecycle:

```
STOPPED → STARTING → RUNNING ↔ DEGRADED → ERROR
  ↑                                      │
  └──────────── restart() ───────────────┘
```

### States

| State | Description |
|-------|-------------|
| `STOPPED` | The browser is not running and has not been started. |
| `STARTING` | The browser process is being launched. |
| `RUNNING` | The browser is running and healthy. |
| `DEGRADED` | The browser is running but in a reduced-capability state. |
| `ERROR` | The browser has crashed and auto-restart was attempted but failed. |

Transitions are protected by a `threading.Lock`. Calling an operation from an invalid state raises `RuntimeError`.

### Auto-Restart

After an unexpected crash (`BrowserCrashError`), the manager performs **one** automatic restart attempt. If that launch also fails the state remains `ERROR`. Call `restart()` to retry.

```python
from BrowserAutomation import BrowserManager

manager = BrowserManager()
await manager.start()       # STOPPED → STARTING → RUNNING
await manager.stop()        # RUNNING → STOPPED
await manager.restart()     # STOPPED → STARTING → RUNNING
```

## BrowserConfig

Configuration is a frozen dataclass defined in `fiona.interfaces`:

```python
from fiona.interfaces import BrowserConfig
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `browser_type` | `str` | `"chromium"` | Browser engine (`chromium`, `firefox`, `webkit`). |
| `headless` | `bool` | `False` | Run without a visible UI window. |
| `viewport_width` | `int` | `1280` | Default viewport width in pixels. |
| `viewport_height` | `int` | `720` | Default viewport height in pixels. |
| `data_dir` | `str \| None` | `None` | Persistent profile directory, or `None` for ephemeral. |
| `proxy` | `str \| None` | `None` | Proxy server URL, or `None` for direct connection. |
| `args` | `tuple[str, ...]` | `()` | Additional command-line arguments for the browser process. |

### Default Configuration

```python
from BrowserAutomation._config import default_config, merge_config

config = default_config(headless=True, proxy="http://proxy:8080")

# Merge overrides on top of an existing config
updated = merge_config(config, viewport_width=1920, viewport_height=1080)
```

## IBrowserContext Interface

Each isolated browser context has its own cookies, storage, and authentication — analogous to an incognito window. Contexts created from the same `IBrowserInstance` are fully isolated.

```python
from fiona.interfaces import IBrowserContext, NavigationEvent, NavigationResult
```

### Methods

| Method | Description |
|--------|-------------|
| `navigate(url, *, timeout=30.0, wait_until=NavigationEvent.LOAD)` | Navigate to a URL and return a `NavigationResult`. |
| `click(selector, *, timeout=5.0)` | Click the first element matching a CSS selector. |
| `type_text(selector, text, *, delay=0.01, timeout=5.0)` | Type text into an editable element with per-keystroke delay. |
| `get_text(selector, *, timeout=5.0)` | Retrieve the `textContent` of the first matching element. |
| `screenshot(*, path=None, full_page=False)` | Capture a PNG screenshot (returns raw bytes). |
| `evaluate(js, *, timeout=5.0)` | Execute JavaScript in the page's main frame. |
| `close()` | Close the context and release resources. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_closed` | `bool` | `True` after `close()` has been called. |
| `context_id` | `str` | Stable unique identifier for this context. |

### NavigationEvent

Controls how long `navigate()` waits before considering the navigation complete:

| Value | Description |
|-------|-------------|
| `NavigationEvent.LOAD` | Wait for the full `load` event (all resources fetched). |
| `NavigationEvent.DOM_CONTENT` | Wait only until the DOM is ready (faster, but styles/fonts may be missing). |
| `NavigationEvent.NETWORK_IDLE` | Wait until no network requests have been made for ~500 ms. |

## Session Management

### SessionManager

`SessionManager` provides synchronous wrappers around the async `BrowserManager` for use in CLI handlers and agent commands. It owns a dedicated event loop running in a daemon thread.

```python
from BrowserAutomation._session_manager import SessionManager

session = SessionManager()
session.start()                          # Launches event loop thread + browser
session.navigate("https://example.com")
session.click("button#submit")
session.type_text("#search", "query")
text = session.get_text(".result")
data = session.screenshot(path="/tmp/page.png")
js_result = session.evaluate("document.title")
session.stop()
```

### Module-Level Convenience API

The `__init__.py` exports convenience functions that operate on a module-level default `BrowserManager`:

```python
from BrowserAutomation import (
    browser_status,
    create_context,
    navigate,
    click_element,
    type_text,
    get_text_content,
    capture_screenshot,
    evaluate_script,
    get_browser_manager,
)
```

These are thin wrappers around a shared singleton manager created on first access:

```python
manager = get_browser_manager()
await manager.start()
status = browser_status()   # BrowserManagerState.RUNNING
await navigate("https://example.com")
await click_element("#go")
await type_text("#input", "hello")
await capture_screenshot(path="shot.png")
```

## Error Hierarchy

All browser errors are defined in `fiona.interfaces` and re-exported from `BrowserAutomation`.

```
BrowserError
├── BrowserLaunchError          — Browser process could not be started
├── BrowserNotRunning           — Operation requires a running browser
├── BrowserShutdownError        — Failed to shut down the browser cleanly
├── BrowserTimeout              — Base timeout error
│   ├── NavigationTimeout       — Page navigation exceeded timeout
│   └── SelectorTimeout         — Waiting for a DOM selector timed out
├── ElementNotFound             — DOM element does not exist on the page
├── ElementNotInteractable      — Element found but cannot be interacted with
├── ScriptExecutionError        — JavaScript evaluation failed
└── BrowserCrashError           — Browser process terminated unexpectedly
```

```python
from BrowserAutomation import (
    BrowserError,
    BrowserLaunchError,
    BrowserNotRunning,
    BrowserShutdownError,
    BrowserTimeout,
    NavigationTimeout,
    SelectorTimeout,
    ElementNotFound,
    ElementNotInteractable,
    ScriptExecutionError,
    BrowserCrashError,
)

try:
    await manager.start()
except BrowserLaunchError as exc:
    print(f"Failed to launch: {exc}")
```

## PlaywrightProvider

`PlaywrightBrowserProvider` is the concrete implementation of `IBrowserProvider`. It translates `BrowserConfig` into Playwright launch arguments and maps Playwright exceptions into the Fiona error hierarchy.

### Lazy Imports

Playwright is imported **inside methods**, not at module level:

```python
async def launch(self, config: BrowserConfig) -> IBrowserInstance:
    _check_playwright_installed()

    from playwright.async_api import async_playwright  # lazy import

    pw = await async_playwright().__aenter__()
    browser = await getattr(pw, config.browser_type).launch(**args)
    return PlaywrightBrowserInstance(browser=browser)
```

If Playwright is not installed, a helpful `RuntimeError` is raised:

```
RuntimeError: Playwright is not installed. Install it with:
  pip install playwright
  playwright install chromium
```

### Capabilities

The provider advertises these capabilities:

```python
PLAYWRIGHT_CAPABILITIES = frozenset({
    "screenshot",
    "pdf",
    "network_intercept",
    "js_eval",
    "multi_context",
    "emulation",
})
```

### Launch Argument Mapping

`BrowserConfig` fields are mapped to Playwright `launch()` kwargs as follows:

| BrowserConfig Field | Playwright kwarg |
|---------------------|------------------|
| `headless` | `headless` |
| `proxy` | `proxy={"server": config.proxy}` |
| `args` | `args=list(config.args)` |

## CLI Commands

Browser automation is accessible via the `fiona browser` command (aliased as `fiona br`).

```bash
fiona browser start          # Start the browser engine
fiona browser stop           # Stop the browser engine
fiona browser status         # Show browser status as JSON
fiona browser navigate <url> # Navigate to a URL
fiona browser click <sel>    # Click a CSS selector
fiona browser type <sel> txt # Type text into an element
fiona browser screenshot     # Capture a screenshot
```

### Command Details

#### `fiona browser start`

```
fiona browser start
```

Starts the browser. Shows an error if already running.

#### `fiona browser stop`

```
fiona browser stop
```

Stops the browser gracefully. Idempotent.

#### `fiona browser status`

```
fiona browser status
```

Outputs structured JSON:

```json
{
  "state": "running",
  "config": {
    "headless": false,
    "slow_mo": null,
    "viewport_width": 1280,
    "viewport_height": 720
  }
}
```

#### `fiona browser navigate`

```
fiona browser navigate <url> [--timeout 30.0]
```

Arguments:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `url` | positional | — | URL to navigate to. |
| `--timeout` | `float` | `30.0` | Navigation timeout in seconds. |

Outputs structured JSON with the navigation result:

```json
{
  "url": "https://example.com/",
  "status_code": 200,
  "title": "Example Domain",
  "duration_ms": 1234.56
}
```

#### `fiona browser click`

```
fiona browser click <selector> [--timeout 5.0]
```

Arguments:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `selector` | positional | — | CSS selector to click. |
| `--timeout` | `float` | `5.0` | Timeout in seconds. |

#### `fiona browser type`

```
fiona browser type <selector> <text> [--delay 0.01] [--timeout 5.0]
```

Arguments:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `selector` | positional | — | CSS selector for the target element. |
| `text` | positional | — | Text to type. |
| `--delay` | `float` | `0.01` | Delay between keystrokes (seconds). |
| `--timeout` | `float` | `5.0` | Timeout in seconds. |

#### `fiona browser screenshot`

```
fiona browser screenshot [--output path] [--full-page]
```

Arguments:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--output` | `Path` | stdout | Output file path. If omitted, raw PNG bytes are written to stdout. |
| `--full-page` | flag | `False` | Capture the full scrollable page, not just the viewport. |

### Alias

The entire `browser` command group is aliased as `br`:

```bash
fiona br start
fiona br status
fiona br navigate https://example.com
```

## Dependencies

Playwright is an **optional** dependency of Fiona. Install it with:

```bash
pip install fiona[browser]
# or directly:
pip install "playwright>=1.45.0"
playwright install chromium
```

The minimum required version is `playwright>=1.45.0`, declared under the `[browser]` optional-dependencies group in `pyproject.toml`.
