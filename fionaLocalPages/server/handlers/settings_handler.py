"""Settings API endpoints — reads/writes ``settings.txt``.

Settings are stored as a JSON file at ``~/.config/fiona/settings.txt``.
The frontend calls these endpoints to persist settings server-side
(in addition to its own localStorage backup).

Handlers
--------
* ``get_settings``   —  GET  /api/v1/settings
* ``put_settings``   —  PUT  /api/v1/settings
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aiohttp.web import Request, Response, json_response

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------

SETTINGS_PATH = Path.home() / ".config" / "fiona" / "settings.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_settings_file() -> None:
    """Create the settings file with an empty JSON object if it does not exist."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        try:
            SETTINGS_PATH.write_text("{}", encoding="utf-8")
            logger.info("Created empty settings file at %s", SETTINGS_PATH)
        except OSError as exc:
            logger.error("Failed to create settings file: %s", exc)


def _load_settings() -> dict[str, Any]:
    """Load settings from the JSON file.  Returns ``{}`` on any error."""
    _ensure_settings_file()
    try:
        raw = SETTINGS_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        return dict(json.loads(raw))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read settings file, returning empty: %s", exc)
        return {}


def _save_settings(settings: dict[str, Any]) -> None:
    """Write *settings* as pretty-printed JSON to the file."""
    _ensure_settings_file()
    try:
        SETTINGS_PATH.write_text(
            json.dumps(settings, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Failed to write settings file: %s", exc)
        raise ApiError(500, f"Failed to save settings: {exc}") from exc


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def get_settings(_request: Request) -> Response:
    """GET /api/v1/settings — return the full settings object.

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { … } }
    """
    settings = _load_settings()
    return json_response({"ok": True, "data": settings})


async def put_settings(request: Request) -> Response:
    """PUT /api/v1/settings — persist the full settings object.

    Request body should be a JSON object (the complete settings tree).
    It is written verbatim to ``settings.txt``.

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "path": "…", "saved": true } }
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    if not isinstance(body, dict):
        raise ApiError(400, "Request body must be a JSON object")

    _save_settings(body)

    return json_response({
        "ok": True,
        "data": {
            "path": str(SETTINGS_PATH),
            "saved": True,
        },
    })
