"""Browser automation API endpoints.

Wraps BrowserAutomation convenience functions.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from aiohttp.web import Request, Response, json_response

from BrowserAutomation import (
    BrowserManagerState,
    browser_status,
    capture_screenshot,
    click_element,
    get_browser_manager,
    navigate,
)

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────


def _state_to_dict(state: BrowserManagerState) -> dict[str, object]:
    return {
        "state": state.value if hasattr(state, "value") else str(state),
        "running": state == BrowserManagerState.RUNNING,
    }


# ── Handlers ───────────────────────────────────────────────────────────────


async def browser_start(_request: Request) -> Response:
    """POST /api/v1/browser/start"""
    try:
        manager = get_browser_manager()
        # BrowserManager.start() may be async.
        if hasattr(manager, "start"):
            result = await manager.start()
        else:
            result = manager.start()
        return json_response({
            "ok": True,
            "data": _state_to_dict(manager.state),
        })
    except Exception as exc:
        logger.exception("Browser start failed")
        raise ApiError(502, f"Browser start failed: {exc}") from exc


async def browser_stop(_request: Request) -> Response:
    """POST /api/v1/browser/stop"""
    try:
        manager = get_browser_manager()
        if hasattr(manager, "stop"):
            result = await manager.stop()
        else:
            result = manager.stop()
        return json_response({
            "ok": True,
            "data": _state_to_dict(manager.state),
        })
    except Exception as exc:
        logger.exception("Browser stop failed")
        raise ApiError(502, f"Browser stop failed: {exc}") from exc


async def browser_status_handler(_request: Request) -> Response:
    """GET /api/v1/browser/status"""
    try:
        state = browser_status()
        return json_response({
            "ok": True,
            "data": _state_to_dict(state),
        })
    except Exception as exc:
        logger.exception("Browser status failed")
        raise ApiError(500, str(exc)) from exc


async def browser_navigate(request: Request) -> Response:
    """POST /api/v1/browser/navigate

    Body: { url, timeout? }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    url: str | None = body.get("url")
    if not url:
        raise ApiError(400, "Missing required field: url")

    timeout = float(body.get("timeout", 30))

    try:
        result = navigate(url, timeout=timeout)
        final_url = getattr(result, "url", url)
        status_code = getattr(result, "status_code", None)
        return json_response({
            "ok": True,
            "data": {"url": final_url, "status_code": status_code},
        })
    except Exception as exc:
        logger.exception("Browser navigate failed")
        raise ApiError(502, f"Navigate failed: {exc}") from exc


async def browser_click(request: Request) -> Response:
    """POST /api/v1/browser/click

    Body: { selector, timeout? }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    selector: str | None = body.get("selector")
    if not selector:
        raise ApiError(400, "Missing required field: selector")

    timeout = float(body.get("timeout", 5))

    try:
        click_element(selector, timeout=timeout)
        return json_response({
            "ok": True,
            "data": {"selector": selector},
        })
    except Exception as exc:
        logger.exception("Browser click failed")
        raise ApiError(502, f"Click failed: {exc}") from exc


async def browser_screenshot(request: Request) -> Response:
    """POST /api/v1/browser/screenshot

    Body: { path?, full_page? }

    Returns the screenshot as a base64-encoded PNG in the JSON response.
    """
    try:
        body: dict[str, Any] = await request.json() if request.can_read_body else {}
    except Exception:
        body = {}

    full_page = bool(body.get("full_page", False))
    save_path: str | None = body.get("path")

    try:
        png_bytes = capture_screenshot(path=save_path, full_page=full_page)
        encoded = base64.b64encode(png_bytes).decode("ascii")
        return json_response({
            "ok": True,
            "data": {
                "screenshot_base64": encoded,
                "size_bytes": len(png_bytes),
                "full_page": full_page,
            },
        })
    except Exception as exc:
        logger.exception("Browser screenshot failed")
        raise ApiError(502, f"Screenshot failed: {exc}") from exc
