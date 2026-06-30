"""Fiona Actions API endpoints.

Wraps FionaCore.ActionRouter and CmdTrace.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

from aiohttp.web import Request, Response, json_response

from CmdTrace import read_trace, trace_stats
from FionaCore import ActionRouter

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

_router: ActionRouter | None = None

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # server/handlers/ -> project root
_ACTIONS_DIR = _PROJECT_ROOT / "actions"
_ACTIONS_JSON = _ACTIONS_DIR / "actions.json"


def _get_router() -> ActionRouter:
    global _router  # noqa: PLW0603
    if _router is None:
        _router = ActionRouter()
    return _router


def _load_file_actions() -> list[dict[str, Any]]:
    """Load action metadata from ``actions/actions.json``.

    Returns:
        List of action dicts with a ``source`` field set to ``"file"``.
        Returns an empty list if the file is missing or unreadable.
    """
    if not _ACTIONS_JSON.is_file():
        return []
    try:
        with _ACTIONS_JSON.open() as f:
            registry = json.load(f)
        actions = registry.get("actions", [])
        for action in actions:
            action["source"] = "file"
        return actions
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", _ACTIONS_JSON, exc)
        return []


# ── Handlers ───────────────────────────────────────────────────────────────


async def list_actions(_request: Request) -> Response:
    """GET /api/v1/actions — list registered Fiona actions.

    Returns a merged list of core actions (from FionaCore.ActionRouter)
    and file-based actions (from ``actions/actions.json``).
    """
    try:
        router = _get_router()
        core_actions = router.list_actions()
        for action in core_actions:
            action["source"] = "core"

        file_actions = _load_file_actions()

        merged = core_actions + file_actions
        return json_response({"ok": True, "data": merged})
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


async def action_stats_endpoint(request: Request) -> Response:
    """GET /api/v1/actions/stats — calls CmdTrace.trace_stats()."""
    try:
        stats = trace_stats()
        return json_response({"ok": True, "data": stats})
    except Exception as exc:
        logger.exception("Failed to read action stats")
        raise ApiError(500, str(exc)) from exc


# ── Actions JSON Helpers ──────────────────────────────────────────────────


def _read_actions_json() -> dict[str, Any]:
    """Read and return the full ``actions.json`` content.

    Returns a default structure if the file is missing or corrupt.
    """
    if not _ACTIONS_JSON.is_file():
        return {"version": "1", "actions": []}
    try:
        with _ACTIONS_JSON.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"version": "1", "actions": []}


def _write_actions_json(data: dict[str, Any]) -> None:
    """Write *data* to ``actions.json`` atomically (via temp file)."""
    _ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _ACTIONS_JSON.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(_ACTIONS_JSON)


def _find_action_meta(
    actions_list: list[dict[str, Any]], filename: str
) -> int | None:
    """Return the index of the action with *filename*, or ``None``."""
    for i, a in enumerate(actions_list):
        if a.get("filename") == filename:
            return i
    return None


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with Z suffix."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    ) + "Z"


# ── File-based Action CRUD Handlers ───────────────────────────────────────


async def file_get(request: Request) -> Response:
    """GET /api/v1/actions/file/get?filename=xxx

    Returns the file content (``code``) and the action's metadata entry.
    """
    filename = request.query.get("filename", "").strip()
    if not filename:
        raise ApiError(400, "Missing required query parameter: filename")
    if not filename.endswith(".py"):
        filename += ".py"

    safe_name = Path(filename).name
    filepath = _ACTIONS_DIR / safe_name

    if not filepath.is_file():
        raise ApiError(404, f"File '{safe_name}' not found")

    try:
        code = filepath.read_text()
    except OSError as exc:
        raise ApiError(500, f"Failed to read file: {exc}")

    registry = _read_actions_json()
    actions_list = registry.get("actions", [])
    idx = _find_action_meta(actions_list, safe_name)
    meta: dict[str, Any] = dict(actions_list[idx]) if idx is not None else {}

    return json_response({"ok": True, "data": {**meta, "code": code}})


async def file_save(request: Request) -> Response:
    """POST /api/v1/actions/file/save

    Body:
        filename (str):  Name of the .py file (with or without extension).
        code (str):      Python source code.
        description (str, optional):  Human-readable description.
        tags (list[str] | str, optional):  Tags (string is split on commas).
        name (str, optional):  Display name (defaults to stem of filename).

    Creates or updates both the .py file and the ``actions.json`` metadata.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    filename = body.get("filename", "").strip()
    code = body.get("code", "").strip()
    if not filename:
        raise ApiError(400, "Missing required field: filename")
    if not code:
        raise ApiError(400, "Missing required field: code")
    if not filename.endswith(".py"):
        filename += ".py"

    safe_name = Path(filename).name
    if safe_name != filename:
        raise ApiError(400, "Invalid filename")

    filepath = _ACTIONS_DIR / safe_name

    # Write the .py file
    try:
        _ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
        filepath.write_text(code)
    except OSError as exc:
        raise ApiError(500, f"Failed to write file: {exc}") from exc

    # Update actions.json metadata
    registry = _read_actions_json()
    actions_list = registry.setdefault("actions", [])

    name = body.get("name", "").strip() or safe_name.replace(".py", "")
    description = body.get("description", "").strip()
    tags = body.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    now = _now_iso()
    idx = _find_action_meta(actions_list, safe_name)

    if idx is not None:
        actions_list[idx]["name"] = name
        actions_list[idx]["description"] = description
        actions_list[idx]["tags"] = tags
        actions_list[idx]["modified"] = now
        result = actions_list[idx]
    else:
        entry: dict[str, Any] = {
            "name": name,
            "filename": safe_name,
            "description": description,
            "tags": tags,
            "enabled": True,
            "created": now,
            "modified": now,
        }
        actions_list.append(entry)
        result = entry

    _write_actions_json(registry)
    return json_response({"ok": True, "data": result})


async def file_delete(request: Request) -> Response:
    """POST /api/v1/actions/file/delete

    Body: { filename: str }

    Removes the .py file and its metadata entry from ``actions.json``.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    filename = body.get("filename", "").strip()
    if not filename:
        raise ApiError(400, "Missing required field: filename")
    if not filename.endswith(".py"):
        filename += ".py"

    safe_name = Path(filename).name
    filepath = _ACTIONS_DIR / safe_name

    try:
        if filepath.is_file():
            filepath.unlink()
    except OSError as exc:
        raise ApiError(500, f"Failed to delete file: {exc}") from exc

    registry = _read_actions_json()
    actions_list = registry.get("actions", [])
    idx = _find_action_meta(actions_list, safe_name)
    if idx is not None:
        del actions_list[idx]
    _write_actions_json(registry)

    return json_response({"ok": True})


async def file_toggle(request: Request) -> Response:
    """POST /api/v1/actions/file/toggle

    Body: { filename: str }

    Toggles the ``enabled`` boolean in ``actions.json``.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    filename = body.get("filename", "").strip()
    if not filename:
        raise ApiError(400, "Missing required field: filename")
    if not filename.endswith(".py"):
        filename += ".py"

    safe_name = Path(filename).name

    registry = _read_actions_json()
    actions_list = registry.get("actions", [])
    idx = _find_action_meta(actions_list, safe_name)
    if idx is None:
        raise ApiError(404, f"Action '{safe_name}' not found in metadata")

    actions_list[idx]["enabled"] = not actions_list[idx].get("enabled", True)
    actions_list[idx]["modified"] = _now_iso()
    _write_actions_json(registry)

    return json_response({"ok": True, "data": actions_list[idx]})


async def file_duplicate(request: Request) -> Response:
    """POST /api/v1/actions/file/duplicate

    Body:
        filename (str):  Source file name.
        new_name (str):  Target file name (without ``_copy`` suffix — caller
                         provides the desired name).

    Copies the .py file and creates a fresh metadata entry.
    Returns the new action metadata.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    filename = body.get("filename", "").strip()
    new_name = body.get("new_name", "").strip()
    if not filename:
        raise ApiError(400, "Missing required field: filename")
    if not new_name:
        raise ApiError(400, "Missing required field: new_name")

    if not filename.endswith(".py"):
        filename += ".py"
    if not new_name.endswith(".py"):
        new_name += ".py"

    safe_name = Path(filename).name
    safe_new = Path(new_name).name
    src_path = _ACTIONS_DIR / safe_name
    dst_path = _ACTIONS_DIR / safe_new

    if not src_path.is_file():
        raise ApiError(404, f"Source file '{safe_name}' not found")
    if dst_path.is_file():
        raise ApiError(409, f"File '{safe_new}' already exists")

    try:
        dst_path.write_text(src_path.read_text())
    except OSError as exc:
        raise ApiError(500, f"Failed to duplicate file: {exc}") from exc

    registry = _read_actions_json()
    actions_list = registry.get("actions", [])
    idx = _find_action_meta(actions_list, safe_name)
    now = _now_iso()

    if idx is not None:
        new_entry: dict[str, Any] = dict(actions_list[idx])
        new_entry["name"] = safe_new.replace(".py", "")
        new_entry["filename"] = safe_new
        new_entry["enabled"] = True
        new_entry["created"] = now
        new_entry["modified"] = now
    else:
        new_entry = {
            "name": safe_new.replace(".py", ""),
            "filename": safe_new,
            "description": "",
            "tags": [],
            "enabled": True,
            "created": now,
            "modified": now,
        }

    actions_list.append(new_entry)
    _write_actions_json(registry)

    return json_response({"ok": True, "data": new_entry})
