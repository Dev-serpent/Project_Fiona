"""RecallVault API endpoints.

Wraps RecallVault.search_recall(), remember(), and forget().
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.web import Request, Response, json_response

from RecallVault import forget, remember, search_recall

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Handlers ───────────────────────────────────────────────────────────────


async def recall_search(request: Request) -> Response:
    """GET /api/v1/recall/search?q=..."""
    query = request.query.get("q", "")
    try:
        entries = search_recall(query)
        return json_response({
            "ok": True,
            "data": [e.to_dict() for e in entries],
        })
    except Exception as exc:
        logger.exception("Recall search failed")
        raise ApiError(500, str(exc)) from exc


async def recall_remember(request: Request) -> Response:
    """POST /api/v1/recall/remember

    Body: { key, value, category? }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    key: str | None = body.get("key")
    value: str | None = body.get("value")
    if not key or not value:
        raise ApiError(400, "Missing required fields: key and value")

    category = str(body.get("category", "general"))

    try:
        path = remember(key, value, category=category)
        return json_response({
            "ok": True,
            "data": {"path": str(path)},
        })
    except Exception as exc:
        logger.exception("Recall remember failed")
        raise ApiError(500, str(exc)) from exc


async def recall_forget(request: Request) -> Response:
    """DELETE /api/v1/recall/forget/{key}"""
    key = request.match_info.get("key", "")
    if not key:
        raise ApiError(400, "Missing key path parameter")

    try:
        removed = forget(key)
        if not removed:
            raise ApiError(404, f"Key not found: {key}")
        return json_response({
            "ok": True,
            "data": {"key": key, "removed": True},
        })
    except ApiError:
        raise
    except Exception as exc:
        logger.exception("Recall forget failed")
        raise ApiError(500, str(exc)) from exc
