"""QuikTieper key bindings API endpoints.

Provides CRUD access to the QuikTieper bindings configuration file at
``~/.config/fiona/bindings.json``.

Handlers
--------
* ``list_bindings``  —  GET  /api/v1/bindings
* ``save_bindings``  —  POST /api/v1/bindings/save
* ``get_apps``       —  GET  /api/v1/bindings/apps
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from aiohttp.web import Request, Response, json_response

import QuikTieper
from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _binding_to_dict(binding: QuikTieper.Binding) -> dict[str, Any]:
    """Convert a frozen ``Binding`` dataclass to a JSON-safe plain dict.

    ``dataclasses.asdict`` is not used directly because it may produce
    unexpected container types (e.g. tuples, frozensets) that are not
    natively JSON-serialisable.
    """
    return {
        "name": binding.name,
        "keys": sorted(binding.keys),
        "command": binding.command,
        "instruction": binding.instruction,
        "fiona_cmds": list(binding.fiona_cmds),
        "cooldown_seconds": binding.cooldown_seconds,
        "app_name": binding.app_name,
        "window_match": binding.window_match,
        "binding_type": binding.binding_type,
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def list_bindings(request: Request) -> Response:
    """GET /api/v1/bindings — return the full bindings configuration.

    Query parameters
    ----------------
    ``parsed`` (optional)
        If ``"true"`` (case-insensitive), also returns the fully parsed
        list of ``Binding`` objects (converted to dicts) under the
        ``"apps"`` key.

    Response shape
    --------------
    .. code-block:: json

        {
          "ok": true,
          "data": {
            "config": { … },
            "apps": [ … ]   // only when ?parsed=true
          }
        }
    """
    # Ensure the config file exists before attempting to load it.
    try:
        QuikTieper.ensure_config()
    except Exception as exc:
        logger.exception("Failed to ensure bindings config file")
        raise ApiError(500, f"Failed to initialise bindings config: {exc}") from exc

    # Load the config dict (handles JSON decode + normalisation internally).
    try:
        config = QuikTieper.load_config()
    except Exception as exc:
        logger.exception("Failed to load bindings config")
        raise ApiError(500, f"Failed to load bindings config: {exc}") from exc

    data: dict[str, object] = {"config": config}

    # Optionally include fully parsed Binding objects.
    parsed_param = request.query.get("parsed", "").strip().lower()
    if parsed_param == "true":
        try:
            raw_apps = config.get("apps", [])
            parsed_bindings = QuikTieper.parse_bindings(raw_apps)
            data["apps"] = [_binding_to_dict(b) for b in parsed_bindings]
        except Exception as exc:
            logger.exception("Failed to parse bindings")
            raise ApiError(500, f"Failed to parse bindings: {exc}") from exc

    return json_response({"ok": True, "data": data})


async def save_bindings(request: Request) -> Response:
    """POST /api/v1/bindings/save — persist a full bindings configuration.

    Request body
    ------------
    A JSON object with at least an ``"apps"`` key:

    .. code-block:: json

        { "apps": [ … ], "version": 1 }

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "path": "…", "saved": true } }
    """
    # Parse and validate the request body.
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    if not isinstance(body, dict):
        raise ApiError(400, "Request body must be a JSON object")

    # Persist via QuikTieper (normalises config internally).
    try:
        result_path = QuikTieper.save_config(body)
    except Exception as exc:
        logger.exception("Failed to save bindings config")
        raise ApiError(500, f"Failed to save bindings config: {exc}") from exc

    return json_response({
        "ok": True,
        "data": {
            "path": str(result_path),
            "saved": True,
        },
    })


async def get_apps(request: Request) -> Response:
    """GET /api/v1/bindings/apps — return just the list of app configs.

    This is a convenience endpoint so the frontend can show a grouped
    view without fetching the entire config (which may contain metadata
    fields).

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "apps": [ … ] } }
    """
    try:
        QuikTieper.ensure_config()
    except Exception as exc:
        logger.exception("Failed to ensure bindings config file")
        raise ApiError(500, f"Failed to initialise bindings config: {exc}") from exc

    try:
        config = QuikTieper.load_config()
    except Exception as exc:
        logger.exception("Failed to load bindings config")
        raise ApiError(500, f"Failed to load bindings config: {exc}") from exc

    apps = config.get("apps", [])
    return json_response({"ok": True, "data": {"apps": apps}})
