"""Notification system handler — create, list, and dismiss in-memory notifications.

Provides three REST endpoints:
  - GET  /api/v1/notifications      → list notifications
  - POST /api/v1/notifications/create → create a notification
  - POST /api/v1/notifications/dismiss → dismiss one or all notifications

Notifications are stored in a simple in-memory list (FIFO, capped at 200).
When a notification is created, it is optionally broadcast to all connected
WebSocket peers if ``request.app["ws_manager"]`` is available.
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.web import Request, Response, json_response
from FionaCore.notifications import Notification

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_notifications: list[dict[str, str]] = []
_max_notifications = 200


def _add_notification(n: Notification) -> dict[str, str]:
    """Insert a Notification at the front of the list, enforcing the cap."""
    d = n.to_dict()
    _notifications.insert(0, d)
    if len(_notifications) > _max_notifications:
        _notifications.pop()
    return d


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def list_notifications(request: Request) -> Response:
    """GET /api/v1/notifications

    Query parameters:
        limit (int, optional)  — max items to return (default 50, max 200).
        unread_only (bool)     — if true, filter to unread items (default false).

    Returns:
        ``{"ok": true, "data": {"items": [...], "total": N, "unread": N}}``
    """
    try:
        limit = int(request.query.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50

    limit = max(0, min(limit, 200))
    unread_only = request.query.get("unread_only", "").lower() in ("true", "1")

    items = _notifications
    if unread_only:
        items = [n for n in items if n.get("urgency") != "read"]

    total = len(_notifications)
    unread = sum(1 for n in _notifications if n.get("urgency") != "read")
    sliced = items[:limit]

    return json_response({
        "ok": True,
        "data": {
            "items": sliced,
            "total": total,
            "unread": unread,
        },
    })


async def create_notification(request: Request) -> Response:
    """POST /api/v1/notifications/create

    Request body (JSON):
        title    (str, required) — notification title.
        body     (str, required) — notification body text.
        urgency  (str, optional) — one of ``"normal"``, ``"critical"``, ``"low"``
                                   (default ``"normal"``).

    Optionally broadcasts the new notification to all WebSocket peers if
    ``request.app["ws_manager"]`` is present.

    Returns:
        ``{"ok": true, "data": {title, body, urgency}}``
    """
    try:
        body_data: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(status=400, message="Invalid JSON body")

    title = body_data.get("title")
    body_str = body_data.get("body")
    urgency = body_data.get("urgency", "normal")

    # ── Validate required fields ──────────────────────────────────────
    if not title or not isinstance(title, str):
        raise ApiError(status=400, message="'title' is required and must be a string")
    if not body_str or not isinstance(body_str, str):
        raise ApiError(status=400, message="'body' is required and must be a string")
    if urgency not in ("normal", "critical", "low"):
        raise ApiError(
            status=400,
            message=f"Invalid urgency '{urgency}'; must be 'normal', 'critical', or 'low'",
        )

    notification = Notification(title=title, body=body_str, urgency=urgency)
    created = _add_notification(notification)

    # ── Optional WebSocket broadcast ──────────────────────────────────
    ws_manager = request.app.get("ws_manager")
    if ws_manager is not None:
        try:
            await ws_manager.notify("notification", created)
        except Exception:
            logger.warning("Failed to broadcast notification via WebSocket", exc_info=True)

    return json_response({"ok": True, "data": created})


async def dismiss_notifications(request: Request) -> Response:
    """POST /api/v1/notifications/dismiss

    Request body (JSON, one of):
        ``{"index": N}``   — remove the notification at the given index.
        ``{"all": true}``  — remove all notifications.

    Returns:
        ``{"ok": true, "data": {"dismissed": count}}``
    """
    try:
        body_data: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(status=400, message="Invalid JSON body")

    dismissed = 0

    if "all" in body_data and body_data["all"]:
        dismissed = len(_notifications)
        _notifications.clear()
    elif "index" in body_data:
        index = body_data["index"]
        if not isinstance(index, int) or index < 0:
            raise ApiError(status=400, message="'index' must be a non-negative integer")
        if index >= len(_notifications):
            raise ApiError(
                status=404,
                message=f"Notification at index {index} not found (max {len(_notifications) - 1})",
            )
        _notifications.pop(index)
        dismissed = 1
    else:
        raise ApiError(
            status=400,
            message="Request must include either 'index' (int) or 'all' (true)",
        )

    return json_response({"ok": True, "data": {"dismissed": dismissed}})
