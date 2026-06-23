"""Desktop awareness API endpoints.

Wraps SeeOnDesk.active_window_info() and SeeOnDesk.desktop_snapshot().
"""

from __future__ import annotations

import logging

import aiohttp.web
from aiohttp.web import Request, Response, json_response

from SeeOnDesk import active_window_info, desktop_snapshot

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Handlers ───────────────────────────────────────────────────────────────


async def desktop_active(_request: Request) -> Response:
    """GET /api/v1/desktop/active — calls SeeOnDesk.active_window_info()."""
    try:
        info = active_window_info()
        return json_response({
            "ok": True,
            "data": info.to_dict(),
        })
    except Exception as exc:
        logger.exception("Desktop active window failed")
        raise ApiError(500, str(exc)) from exc


async def desktop_snapshot_handler(_request: Request) -> Response:
    """GET /api/v1/desktop/snapshot — calls SeeOnDesk.desktop_snapshot()."""
    try:
        snapshot = desktop_snapshot(include_screenshot=False)
        return json_response({
            "ok": True,
            "data": snapshot.to_dict(),
        })
    except Exception as exc:
        logger.exception("Desktop snapshot failed")
        raise ApiError(500, str(exc)) from exc
