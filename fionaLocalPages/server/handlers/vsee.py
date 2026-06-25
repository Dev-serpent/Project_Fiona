"""Vsee holography visual scene viewer API endpoints.

Provides handlers that expose the Vsee holography module over HTTP:
  - ``GET /api/v1/vsee/status``  — availability info
  - ``POST /api/v1/vsee/launch`` — launch the holography GUI in a background thread
  - ``GET  /api/v1/vsee/model``  — default hologram model data
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from aiohttp.web import Request, Response, json_response

from fionaLocalPages.server.middleware import ApiError

import Vsee

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def vsee_status(_request: Request) -> Response:
    """GET /api/v1/vsee/status — report whether Vsee is available."""
    try:
        # Check that the core Vsee module and its gui submodule can be loaded.
        has_gui = False
        try:
            import importlib

            importlib.import_module("Vsee.gui")
            has_gui = True
        except Exception:
            has_gui = False

        return json_response({
            "ok": True,
            "data": {
                "available": True,
                "has_gui": has_gui,
            },
        })
    except Exception as exc:
        logger.exception("Vsee status check failed")
        raise ApiError(status=500, message=str(exc)) from exc


async def vsee_launch(request: Request) -> Response:
    """POST /api/v1/vsee/launch — launch the holography GUI in a background thread.

    Body (JSON):
        ``points_path`` (str, optional) — path to a points file.
        ``edges_path``  (str, optional) — path to an edges file.

    The GUI runs in a separate thread so the HTTP response returns immediately.
    The ``Vsee.gui`` module is imported lazily inside the thread to avoid pulling
    in GUI dependencies at server import time.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    points_path: Path | None = None
    edges_path: Path | None = None

    raw_points = body.get("points_path")
    if raw_points is not None:
        if not isinstance(raw_points, str):
            raise ApiError(400, "points_path must be a string or null")
        points_path = Path(raw_points)

    raw_edges = body.get("edges_path")
    if raw_edges is not None:
        if not isinstance(raw_edges, str):
            raise ApiError(400, "edges_path must be a string or null")
        edges_path = Path(raw_edges)

    def _run_gui(p: Path | None, e: Path | None) -> None:
        """Import Vsee.gui lazily and launch the holography window."""
        try:
            from Vsee.gui import launch_holography  # noqa: F811

            launch_holography(points_path=p, edges_path=e)
        except Exception:
            logger.exception("Vsee GUI thread failed")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_gui, points_path, edges_path)

    return json_response({
        "ok": True,
        "data": {
            "launched": True,
            "message": "Vsee launched",
        },
    })


async def vsee_default_model(_request: Request) -> Response:
    """GET /api/v1/vsee/model — return the default hologram model data."""
    try:
        return json_response({
            "ok": True,
            "data": {
                "points_text": Vsee.DEFAULT_POINTS_TEXT,
                "edges_text": Vsee.DEFAULT_EDGES_TEXT,
            },
        })
    except Exception as exc:
        logger.exception("Failed to read default Vsee model")
        raise ApiError(status=500, message=str(exc)) from exc
