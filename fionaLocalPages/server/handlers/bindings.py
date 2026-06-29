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
        "enabled": binding.enabled,
        "category": binding.category,
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


# ---------------------------------------------------------------------------
# CRUD: Create / Update / Delete / Toggle
# ---------------------------------------------------------------------------


def _load_config():
    """Load and ensure the bindings config exists, returning config dict."""
    QuikTieper.ensure_config()
    return QuikTieper.load_config()


def _find_app(config: dict, app_name: str) -> dict | None:
    """Find an app config by name (case-insensitive)."""
    app_name_lower = app_name.strip().lower()
    for app in config.get("apps", []):
        if app.get("name", "").strip().lower() == app_name_lower:
            return app
    return None


def _find_shortcut(app: dict, shortcut_name: str) -> dict | None:
    """Find a shortcut by name within an app config."""
    name_lower = shortcut_name.strip().lower()
    for s in app.get("shortcuts", []):
        if s.get("name", "").strip().lower() == name_lower:
            return s
    return None


def _short_binding_name(full_name: str) -> str:
    """Strip the 'appname:' prefix from a full binding name."""
    if ":" in full_name:
        return full_name.split(":", 1)[1]
    return full_name


async def create_binding(request: Request) -> Response:
    """POST /api/v1/bindings/create — create a new binding shortcut.

    Request body
    ------------
    .. code-block:: json

        {
          "app": "app-name",
          "name": "binding-name",
          "keys": ["alt", "x"],
          "command": "command-to-run",
          "instruction": "",
          "category": "General",
          "enabled": true
        }

    Creates the binding as a shortcut in the given app.  If the app
    doesn't exist yet, a new app entry is created.
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    app_name = (body.get("app") or "").strip()
    if not app_name:
        raise ApiError(400, "Field 'app' is required")

    binding_name = (body.get("name") or "").strip()
    if not binding_name:
        raise ApiError(400, "Field 'name' is required")

    keys = body.get("keys", [])
    if not isinstance(keys, list) or len(keys) == 0:
        raise ApiError(400, "Field 'keys' is required (non-empty array)")

    command = body.get("command", "").strip()
    if not command:
        raise ApiError(400, "Field 'command' is required")

    # Load config
    config = _load_config()

    # Find or create app
    app = _find_app(config, app_name)
    if app is None:
        app = {
            "name": app_name,
            "window_match": _infer_window_match(command),
            "launch": {},
            "shortcuts": [],
        }
        config["apps"].append(app)

    # Check for duplicate name
    if _find_shortcut(app, binding_name):
        raise ApiError(409, f"A binding named '{binding_name}' already exists in app '{app_name}'")

    # Build the shortcut entry
    shortcut = {
        "name": binding_name,
        "keys": [k.strip().lower() for k in keys],
        "cmd": command,
        "instruction": (body.get("instruction") or body.get("description") or "").strip(),
        "fiona_cmds": [],
        "cooldown_seconds": 0.8,
        "enabled": body.get("enabled", True),
        "category": body.get("category", ""),
    }
    app.setdefault("shortcuts", []).append(shortcut)

    # Save config
    try:
        QuikTieper.save_config(config)
    except Exception as exc:
        logger.exception("Failed to save config after create")
        raise ApiError(500, f"Failed to save: {exc}") from exc

    return json_response({"ok": True, "data": {"binding": shortcut, "app": app_name}})


def _infer_window_match(command: str) -> str:
    """Infer a window match string from a command."""
    import shlex
    from pathlib import Path
    try:
        parts = shlex.split(command)
        if parts:
            return Path(parts[0]).name.lower()
    except Exception:
        pass
    return ""


async def update_binding(request: Request) -> Response:
    """POST /api/v1/bindings/update — update an existing binding.

    Request body
    ------------
    .. code-block:: json

        {
          "app": "app-name",
          "name": "binding-name",
          "keys": ["alt", "x"],
          "command": "new-command",
          "instruction": "",
          "category": "Editing",
          "enabled": true
        }

    The ``name`` field identifies the binding (in full form like
    ``appname:bindingname`` or short form).  If the binding is a launch
    binding, name should be ``appname:launch``.
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    app_name = (body.get("app") or "").strip()
    if not app_name:
        raise ApiError(400, "Field 'app' is required")

    binding_full_name = (body.get("name") or "").strip()
    if not binding_full_name:
        raise ApiError(400, "Field 'name' is required")

    short_name = _short_binding_name(binding_full_name)

    # Use origName for lookup if provided (allows renaming)
    lookup_name = short_name
    orig_name_raw = body.get("origName")
    if orig_name_raw:
        lookup_name = _short_binding_name(str(orig_name_raw))

    config = _load_config()
    app = _find_app(config, app_name)
    if app is None:
        raise ApiError(404, f"App '{app_name}' not found")

    # Check shortcut bindings
    shortcut = _find_shortcut(app, lookup_name)
    is_launch = lookup_name.lower() == "launch"

    if shortcut is None and not is_launch:
        raise ApiError(404, f"Binding '{binding_full_name}' not found in app '{app_name}'")

    target = app.get("launch", {}) if is_launch else shortcut
    if target is None:
        raise ApiError(404, f"Binding '{binding_full_name}' not found in app '{app_name}'")

    # Update fields
    if "name" in body and not body.get("origName"):
        target["name"] = short_name
    # If name changed from original, update it
    if orig_name_raw and short_name != lookup_name:
        target["name"] = short_name
    if "keys" in body and isinstance(body["keys"], list):
        target["keys"] = [k.strip().lower() for k in body["keys"]]
    if "command" in body:
        target["cmd"] = body["command"].strip()
    if "instruction" in body or "description" in body:
        target["instruction"] = (body.get("instruction") or body.get("description") or "").strip()
    if "enabled" in body:
        target["enabled"] = bool(body["enabled"])
    if "category" in body:
        target["category"] = body.get("category", "")

    # Save
    try:
        QuikTieper.save_config(config)
    except Exception as exc:
        logger.exception("Failed to save config after update")
        raise ApiError(500, f"Failed to save: {exc}") from exc

    return json_response({"ok": True, "data": {"binding": target, "app": app_name}})


async def delete_binding(request: Request) -> Response:
    """DELETE /api/v1/bindings/delete — delete a binding.

    Request body
    ------------
    .. code-block:: json

        { "app": "app-name", "name": "binding-name" }

    The binding is removed from the app's shortcuts.  If it's a launch
    binding (name ends with ``:launch``), the launch entry is cleared.
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    app_name = (body.get("app") or "").strip()
    if not app_name:
        raise ApiError(400, "Field 'app' is required")

    binding_full_name = (body.get("name") or "").strip()
    if not binding_full_name:
        raise ApiError(400, "Field 'name' is required")

    short_name = _short_binding_name(binding_full_name)

    config = _load_config()
    app = _find_app(config, app_name)
    if app is None:
        raise ApiError(404, f"App '{app_name}' not found")

    is_launch = short_name.lower() == "launch"

    if is_launch:
        app["launch"] = {}
    else:
        shortcuts = app.get("shortcuts", [])
        new_shortcuts = [s for s in shortcuts if s.get("name", "").strip().lower() != short_name.lower()]
        if len(new_shortcuts) == len(shortcuts):
            raise ApiError(404, f"Binding '{binding_full_name}' not found in app '{app_name}'")
        app["shortcuts"] = new_shortcuts

    try:
        QuikTieper.save_config(config)
    except Exception as exc:
        logger.exception("Failed to save config after delete")
        raise ApiError(500, f"Failed to save: {exc}") from exc

    return json_response({"ok": True, "data": {"deleted": True, "app": app_name}})


async def toggle_binding(request: Request) -> Response:
    """POST /api/v1/bindings/toggle — toggle a binding's enabled state.

    Request body
    ------------
    .. code-block:: json

        { "app": "app-name", "name": "binding-name", "enabled": true }

    Persists the new enabled state immediately.
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    app_name = (body.get("app") or "").strip()
    if not app_name:
        raise ApiError(400, "Field 'app' is required")

    binding_full_name = (body.get("name") or "").strip()
    if not binding_full_name:
        raise ApiError(400, "Field 'name' is required")

    short_name = _short_binding_name(binding_full_name)
    enabled = bool(body.get("enabled", True))

    config = _load_config()
    app = _find_app(config, app_name)
    if app is None:
        raise ApiError(404, f"App '{app_name}' not found")

    is_launch = short_name.lower() == "launch"

    if is_launch:
        launch = app.get("launch", {})
        if not launch.get("keys"):
            raise ApiError(404, f"Launch binding not found in app '{app_name}'")
        launch["enabled"] = enabled
    else:
        shortcut = _find_shortcut(app, short_name)
        if shortcut is None:
            raise ApiError(404, f"Binding '{binding_full_name}' not found in app '{app_name}'")
        shortcut["enabled"] = enabled

    try:
        QuikTieper.save_config(config)
    except Exception as exc:
        logger.exception("Failed to save config after toggle")
        raise ApiError(500, f"Failed to save: {exc}") from exc

    return json_response({"ok": True, "data": {"enabled": enabled, "app": app_name}})


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------


async def export_bindings(request: Request) -> Response:
    """GET /api/v1/bindings/export — download the full config as JSON.

    Returns the raw bindings.json file as a downloadable attachment.
    """
    try:
        QuikTieper.ensure_config()
        config = QuikTieper.load_config()
    except Exception as exc:
        logger.exception("Failed to load config for export")
        raise ApiError(500, f"Failed to load config: {exc}") from exc

    import json as _json
    body = _json.dumps(config, indent=2)
    return Response(
        body=body,
        status=200,
        headers={
            "Content-Type": "application/json",
            "Content-Disposition": 'attachment; filename="fiona-bindings.json"',
        },
    )


async def import_bindings(request: Request) -> Response:
    """POST /api/v1/bindings/import — import bindings from JSON body.

    Request body
    ------------
    The full apps config structure:

    .. code-block:: json

        { "apps": [ { "name": "...", "launch": {...}, "shortcuts": [...] } ] }

    Replaces the current config entirely with the imported data.
    Returns a count of imported bindings.
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body — expected a JSON object")

    if not isinstance(body, dict):
        raise ApiError(400, "Request body must be a JSON object")

    # Normalize to ensure it's well-formed
    try:
        normalized = QuikTieper.normalize_config(body)
    except Exception as exc:
        logger.exception("Failed to normalize imported config")
        raise ApiError(400, f"Invalid config format: {exc}") from exc

    # Count bindings
    count = 0
    for app in normalized.get("apps", []):
        if app.get("launch", {}).get("keys"):
            count += 1
        count += len(app.get("shortcuts", []))

    try:
        QuikTieper.save_config(normalized)
    except Exception as exc:
        logger.exception("Failed to save imported config")
        raise ApiError(500, f"Failed to save imported config: {exc}") from exc

    return json_response({
        "ok": True,
        "data": {"count": count, "saved": True},
    })


# ---------------------------------------------------------------------------
# Conflict Detection
# ---------------------------------------------------------------------------


async def check_conflicts(request: Request) -> Response:
    """POST /api/v1/bindings/check-conflicts — check for key combo conflicts.

    Request body
    ------------
    .. code-block:: json

        {
          "keys": ["alt", "x"],
          "exclude": { "app": "app-name", "name": "binding-name" }
        }

    ``exclude`` is optional — if provided, bindings matching the exclusion
    are not considered conflicting (useful when editing an existing binding).

    Response
    --------
    Returns a list of bindings that use the same key combination.

    .. code-block:: json

        {
          "ok": true,
          "data": { "conflicts": [ { "app": "...", "name": "...", ... } ] }
        }
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    query_keys_raw = body.get("keys", [])
    if not isinstance(query_keys_raw, list) or len(query_keys_raw) == 0:
        raise ApiError(400, "Field 'keys' is required (non-empty array)")

    # Normalise the query keys to lower case sorted set
    query_keys = frozenset(k.strip().lower() for k in query_keys_raw)

    # Optional exclusion — which binding to exclude from conflict results
    exclude_app = ""
    exclude_name = ""
    if "exclude" in body and isinstance(body["exclude"], dict):
        exclude_app = (body["exclude"].get("app") or "").strip().lower()
        exclude_name = (body["exclude"].get("name") or "").strip().lower()
        exclude_name = _short_binding_name(exclude_name).lower()

    config = _load_config()
    conflicts = []

    for app in config.get("apps", []):
        app_name = app.get("name", "")
        app_name_lower = app_name.strip().lower()

        # Check launch binding
        launch = app.get("launch", {})
        launch_keys_raw = launch.get("keys", [])
        if launch_keys_raw:
            launch_keys = frozenset(k.lower() for k in launch_keys_raw)
            if launch_keys == query_keys:
                if not (exclude_app == app_name_lower and exclude_name == "launch"):
                    conflicts.append({
                        "app": app_name,
                        "name": f"{app_name}:launch",
                        "keys": sorted(launch_keys),
                        "command": launch.get("cmd", ""),
                        "binding_type": "launch",
                    })

        # Check shortcuts
        for shortcut in app.get("shortcuts", []):
            shortcut_keys_raw = shortcut.get("keys", [])
            if not shortcut_keys_raw:
                continue
            shortcut_keys = frozenset(k.lower() for k in shortcut_keys_raw)
            if shortcut_keys == query_keys:
                short_name = shortcut.get("name", "")
                if not (exclude_app == app_name_lower and exclude_name == short_name.strip().lower()):
                    conflicts.append({
                        "app": app_name,
                        "name": f"{app_name}:{short_name}",
                        "keys": sorted(shortcut_keys),
                        "command": shortcut.get("cmd", ""),
                        "binding_type": "shortcut",
                    })

    return json_response({"ok": True, "data": {"conflicts": conflicts}})
