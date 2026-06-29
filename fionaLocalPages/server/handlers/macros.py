"""Macro API endpoints.

Wraps FionaCore.load_macros(), run_macro(), save_macro(), delete_macro(),
export_macros_raw(), and import_macros_raw().
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any

from aiohttp.web import Request, Response, json_response

from FionaCore import load_macros, run_macro
from FionaCore.macros import (
    DEFAULT_MACROS_PATH,
    MacroStep,
    delete_macro,
    export_macros_raw,
    import_macros_raw,
    load_macros_with_meta,
    save_macro,
)

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────


def _step_to_dict(step: MacroStep) -> dict[str, str]:
    return step.to_dict()


# ── Handlers ───────────────────────────────────────────────────────────────


async def list_macros(_request: Request) -> Response:
    """GET /api/v1/macros — list all macros with their steps and shortcuts."""
    try:
        macros, metadata = load_macros_with_meta()
        data: dict[str, list[dict[str, str]]] = {
            name: [_step_to_dict(step) for step in steps]
            for name, steps in macros.items()
        }
        shortcuts: dict[str, str] = {
            name: meta.get("shortcut", "")
            for name, meta in metadata.items()
            if meta.get("shortcut")
        }
        return json_response({
            "ok": True,
            "data": data,
            "shortcuts": shortcuts,
        })
    except Exception as exc:
        logger.exception("Failed to list macros")
        raise ApiError(500, str(exc)) from exc


async def run_macro_handler(request: Request) -> Response:
    """POST /api/v1/macros/run

    Body: { name, dry_run? }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    name: str | None = body.get("name")
    if not name:
        raise ApiError(400, "Missing required field: name")

    dry_run = bool(body.get("dry_run", False))

    try:
        results = run_macro(name=name, dry_run=dry_run)
        return json_response({
            "ok": True,
            "data": [r.to_dict() for r in results],
        })
    except ValueError as exc:
        raise ApiError(404, str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to run macro")
        raise ApiError(500, str(exc)) from exc


async def save_macro_handler(request: Request) -> Response:
    """POST /api/v1/macros/save — create or update a macro.

    Body:
    ```json
    {
      "name": "MyMacro",
      "steps": [{ "action": "echo hello", ... }],
      "shortcut": "Ctrl+Shift+K"
    }
    ```
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    name: str | None = body.get("name")
    if not name:
        raise ApiError(400, "Missing required field: name")

    raw_steps: list[dict[str, Any]] = body.get("steps", [])
    if not isinstance(raw_steps, list):
        raise ApiError(400, "'steps' must be a list")

    shortcut: str = body.get("shortcut", "")

    steps = [MacroStep.from_dict(s) for s in raw_steps if isinstance(s, dict)]

    try:
        save_macro(name=name, steps=steps, shortcut=shortcut)
        return json_response({
            "ok": True,
            "data": {"name": name, "step_count": len(steps)},
        })
    except Exception as exc:
        logger.exception("Failed to save macro")
        raise ApiError(500, str(exc)) from exc


async def delete_macro_handler(request: Request) -> Response:
    """DELETE /api/v1/macros/delete — delete a macro.

    Query param or body: { name }
    """
    # Try body first, then query param
    name: str | None = None
    try:
        body: dict[str, Any] = await request.json()
        name = body.get("name")
    except Exception:
        name = request.query.get("name")

    if not name:
        raise ApiError(400, "Missing required field: name")

    try:
        delete_macro(name=name)
        return json_response({
            "ok": True,
            "data": {"name": name, "deleted": True},
        })
    except Exception as exc:
        logger.exception("Failed to delete macro")
        raise ApiError(500, str(exc)) from exc


async def export_macros_handler(_request: Request) -> Response:
    """GET /api/v1/macros/export — export all macros as a JSON download."""
    try:
        raw = export_macros_raw()
        body = _json.dumps(raw, indent=2)
        return Response(
            body=body,
            status=200,
            headers={
                "Content-Type": "application/json",
                "Content-Disposition": 'attachment; filename="fiona-macros.json"',
            },
        )
    except Exception as exc:
        logger.exception("Failed to export macros")
        raise ApiError(500, str(exc)) from exc


async def import_macros_handler(request: Request) -> Response:
    """POST /api/v1/macros/import — import macros from a JSON body.

    The body should be the full macros file format (a dict mapping macro names
    to either a list of steps or a dict with "steps" and "shortcut" keys).

    Completely replaces the current macros file.
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body — expected a JSON object")

    if not isinstance(body, dict):
        raise ApiError(400, "Request body must be a JSON object")

    # Validate that it looks like a macros file
    macro_count = 0
    for key, value in body.items():
        if key.startswith("_"):
            continue  # metadata keys
        if isinstance(value, list):
            macro_count += 1
        elif isinstance(value, dict) and "steps" in value:
            macro_count += 1

    if macro_count == 0:
        raise ApiError(400, "No valid macros found in import data")

    try:
        import_macros_raw(body)
        return json_response({
            "ok": True,
            "data": {"count": macro_count, "imported": True},
        })
    except Exception as exc:
        logger.exception("Failed to import macros")
        raise ApiError(500, str(exc)) from exc
