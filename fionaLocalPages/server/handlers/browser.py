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

        # Create default context so navigation/screenshot functions work.
        try:
            await manager.create_context()
        except Exception as ctx_err:
            logger.warning("Context creation after start: %s", ctx_err)

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
        manager = get_browser_manager()
        state = manager.state

        # Try to get page info from default context
        page_url = ""
        page_title = ""
        try:
            ctx = manager._require_default_context()
            page_url = ctx.page.url if hasattr(ctx, "page") else ""
            page_title = await ctx.page.title() if hasattr(ctx, "page") else ""
        except Exception:
            pass

        return json_response({
            "ok": True,
            "data": {
                "status": state.value,
                "running": state == BrowserManagerState.RUNNING,
                "url": page_url,
                "title": page_title,
            },
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
        result = await navigate(url, timeout=timeout)
        final_url = getattr(result, "url", url)
        status_code = getattr(result, "status_code", None)
        title = getattr(result, "title", None)
        duration_ms = getattr(result, "duration_ms", None)
        return json_response({
            "ok": True,
            "data": {
                "url": final_url,
                "status_code": status_code,
                "title": title,
                "duration_ms": duration_ms,
            },
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
        await click_element(selector, timeout=timeout)
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
        png_bytes = await capture_screenshot(path=save_path, full_page=full_page)
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


async def browser_type(request: Request) -> Response:
    """POST /api/v1/browser/type
    Body: { selector, text, timeout? }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    selector: str | None = body.get("selector")
    text: str | None = body.get("text")
    if not selector or text is None:
        raise ApiError(400, "Missing required fields: selector, text")

    timeout = float(body.get("timeout", 5))
    try:
        from BrowserAutomation import type_text  # noqa: PLC0415

        await type_text(selector, text, timeout=timeout)
        return json_response({"ok": True, "data": {"selector": selector}})
    except Exception as exc:
        logger.exception("Browser type failed")
        raise ApiError(502, f"Type failed: {exc}") from exc


async def browser_get_text(request: Request) -> Response:
    """POST /api/v1/browser/get_text
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
        from BrowserAutomation import get_text_content  # noqa: PLC0415

        text = await get_text_content(selector, timeout=timeout)
        return json_response({"ok": True, "data": {"text": text}})
    except Exception as exc:
        logger.exception("Browser get_text failed")
        raise ApiError(502, f"Get text failed: {exc}") from exc
