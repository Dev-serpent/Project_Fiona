"""Config API endpoints.

Lists, reads, and updates Fiona configuration files under
``~/.config/fiona/``.
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
# Config path resolution
# ---------------------------------------------------------------------------

FIONA_CONFIG_DIR = Path.home() / ".config" / "fiona"

# Known config files and their descriptions.
KNOWN_CONFIG_FILES: dict[str, str] = {
    "config": "Fiona host service config",
    "identity": "CamComs identity (private key)",
    "identity.pub": "CamComs public key bundle",
    "bindings.json": "QuikTieper application bindings",
    "macros.json": "Fiona macros",
    "recallvault.json": "RecallVault memory store",
    "cmdtrace.jsonl": "Command execution trace log",
    "verification": "Verification prompt template",
}


def _resolve_config(name: str) -> Path:
    """Resolve a config name to an absolute file path under ~/.config/fiona/.

    *name* may be a simple filename (e.g. ``"config"``) or a relative path
    (e.g. ``"subdir/file.json"``).  Directory traversal is blocked.
    """
    # Block path traversal.
    resolved = (FIONA_CONFIG_DIR / name).resolve()
    try:
        resolved.relative_to(FIONA_CONFIG_DIR.resolve())
    except ValueError:
        raise ApiError(403, f"Access denied: config name '{name}' is outside the config directory")
    return resolved


# ── Handlers ───────────────────────────────────────────────────────────────


async def list_configs(_request: Request) -> Response:
    """GET /api/v1/config — list all config files."""
    data: list[dict[str, object]] = []
    if FIONA_CONFIG_DIR.is_dir():
        for child in sorted(FIONA_CONFIG_DIR.iterdir()):
            if child.is_file():
                name = child.name
                data.append({
                    "name": name,
                    "path": str(child),
                    "description": KNOWN_CONFIG_FILES.get(name, "Fiona config file"),
                    "size": child.stat().st_size,
                    "modified": child.stat().st_mtime,
                })
    return json_response({"ok": True, "data": data})


async def read_config(request: Request) -> Response:
    """GET /api/v1/config/{name} — read a specific config file."""
    name = request.match_info.get("name", "")
    if not name:
        raise ApiError(400, "Missing config name")

    target = _resolve_config(name)
    if not target.exists():
        raise ApiError(404, f"Config file not found: {name}")
    if not target.is_file():
        raise ApiError(400, f"Config path is not a file: {name}")

    try:
        raw = target.read_text(encoding="utf-8")
        # Attempt to parse as JSON for structured display.
        try:
            parsed = json.loads(raw)
            content: object = parsed
            content_type = "json"
        except json.JSONDecodeError:
            content = raw
            content_type = "text"

        return json_response({
            "ok": True,
            "data": {
                "name": name,
                "path": str(target),
                "content": content,
                "content_type": content_type,
            },
        })
    except Exception as exc:
        logger.exception("Failed to read config %s", name)
        raise ApiError(500, str(exc)) from exc


async def update_config(request: Request) -> Response:
    """PUT /api/v1/config/{name} — update a config file.

    Body: { content } — full replacement content (JSON object or string).
    """
    name = request.match_info.get("name", "")
    if not name:
        raise ApiError(400, "Missing config name")

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    new_content = body.get("content")
    if new_content is None:
        raise ApiError(400, "Missing required field: content")

    target = _resolve_config(name)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(new_content, (dict, list)):
            target.write_text(
                json.dumps(new_content, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        else:
            target.write_text(str(new_content), encoding="utf-8")
        return json_response({
            "ok": True,
            "data": {"name": name, "path": str(target)},
        })
    except Exception as exc:
        logger.exception("Failed to update config %s", name)
        raise ApiError(500, str(exc)) from exc
