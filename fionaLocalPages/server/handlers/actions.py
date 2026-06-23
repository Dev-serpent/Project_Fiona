"""Fiona Actions API endpoints.

Wraps FionaCore.ActionRouter and CmdTrace.
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.web import Request, Response, json_response

from CmdTrace import read_trace
from FionaCore import ActionRouter

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

_router: ActionRouter | None = None


def _get_router() -> ActionRouter:
    global _router  # noqa: PLW0603
    if _router is None:
        _router = ActionRouter()
    return _router


# ── Handlers ───────────────────────────────────────────────────────────────


async def list_actions(_request: Request) -> Response:
    """GET /api/v1/actions — list registered Fiona actions."""
    try:
        router = _get_router()
        actions = router.list_actions()
        return json_response({"ok": True, "data": actions})
    except Exception as exc:
        logger.exception("Failed to list actions")
        raise ApiError(500, str(exc)) from exc


async def run_action(request: Request) -> Response:
    """POST /api/v1/actions/run

    Body: { name, source?, profile?, dry_run? }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    name: str | None = body.get("name")
    if not name:
        raise ApiError(400, "Missing required field: name")

    try:
        router = _get_router()
        result = router.run(
            name=name,
            source=body.get("source", "web"),
            permission_profile=body.get("profile", "local"),
            dry_run=bool(body.get("dry_run", False)),
        )
        return json_response({
            "ok": True,
            "data": result.to_dict(),
        })
    except ValueError as exc:
        raise ApiError(404, str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to run action")
        raise ApiError(500, str(exc)) from exc


async def action_history(request: Request) -> Response:
    """GET /api/v1/actions/history — calls CmdTrace.read_trace()."""
    try:
        limit_str = request.query.get("limit", "50")
        limit = max(1, min(int(limit_str), 500))
    except (ValueError, TypeError):
        limit = 50

    try:
        events = read_trace(limit=limit)
        return json_response({"ok": True, "data": events})
    except Exception as exc:
        logger.exception("Failed to read action history")
        raise ApiError(500, str(exc)) from exc
