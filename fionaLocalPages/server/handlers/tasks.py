"""Task queue API endpoints.

Provides REST endpoints:
  - GET    /api/v1/tasks           → list tasks
  - POST   /api/v1/tasks/create    → create a task
  - POST   /api/v1/tasks/update    → update task status / fields
  - POST   /api/v1/tasks/delete    → delete a task

Tasks are stored in-memory (FIFO, no persistence across restarts).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from aiohttp.web import Request, Response, json_response

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_tasks: list[dict[str, Any]] = []


def _make_task(
    title: str = "",
    description: str = "",
    status: str = "pending",
    priority: str = "medium",
    category: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "category": category,
        "tags": tags or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def list_tasks(request: Request) -> Response:
    """GET /api/v1/tasks — return all tasks."""
    return json_response({"ok": True, "data": _tasks})


async def create_task(request: Request) -> Response:
    """POST /api/v1/tasks/create — create a new task."""
    try:
        body = await request.json()
    except Exception:
        raise ApiError("Invalid JSON body", status=400)

    title = (body.get("title") or "").strip()
    if not title:
        raise ApiError("'title' is required", status=400)

    task = _make_task(
        title=title,
        description=(body.get("description") or "").strip(),
        status=body.get("status", "pending"),
        priority=body.get("priority", "medium"),
        category=(body.get("category") or "").strip(),
        tags=body.get("tags"),
    )
    _tasks.append(task)
    logger.info("Task created: %s (%s)", task["id"], title)
    return json_response({"ok": True, "data": task}, status=201)


async def update_task(request: Request) -> Response:
    """POST /api/v1/tasks/update — update task status / fields."""
    try:
        body = await request.json()
    except Exception:
        raise ApiError("Invalid JSON body", status=400)

    task_id = body.get("id")
    if not task_id:
        raise ApiError("'id' is required", status=400)

    for task in _tasks:
        if task["id"] == task_id:
            for field in ("title", "description", "status", "priority", "category"):
                if field in body:
                    task[field] = body[field]
            if "tags" in body:
                task["tags"] = body["tags"]
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            return json_response({"ok": True, "data": task})

    raise ApiError("Task not found", status=404)


async def delete_task(request: Request) -> Response:
    """POST /api/v1/tasks/delete — delete a task by id."""
    try:
        body = await request.json()
    except Exception:
        raise ApiError("Invalid JSON body", status=400)

    task_id = body.get("id")
    if not task_id:
        raise ApiError("'id' is required", status=400)

    for i, task in enumerate(_tasks):
        if task["id"] == task_id:
            removed = _tasks.pop(i)
            return json_response({"ok": True, "data": removed})

    raise ApiError("Task not found", status=404)
