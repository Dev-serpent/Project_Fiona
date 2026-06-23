"""Macro API endpoints.

Wraps FionaCore.load_macros() and FionaCore.run_macro().
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.web import Request, Response, json_response

from FionaCore import load_macros, run_macro

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Handlers ───────────────────────────────────────────────────────────────


async def list_macros(_request: Request) -> Response:
    """GET /api/v1/macros — list all macros with their steps."""
    try:
        macros = load_macros()
        data: dict[str, list[dict[str, str]]] = {
            name: [step.to_dict() for step in steps]
            for name, steps in macros.items()
        }
        return json_response({
            "ok": True,
            "data": data,
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
