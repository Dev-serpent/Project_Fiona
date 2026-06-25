"""QuikTieper API endpoints — bindings, presets, desktop apps, launcher.

Provides REST access to the full QuikTieper subsystem beyond the basic
key-bindings CRUD already served by :mod:`~handlers.bindings`.

Handlers
--------
* ``quiktieper_status``        —  GET    /api/v1/quiktieper/status
* ``list_presets``              —  GET    /api/v1/quiktieper/presets
* ``list_desktop_apps``         —  GET    /api/v1/quiktieper/desktop-apps
* ``import_desktop_apps``       —  POST   /api/v1/quiktieper/import-apps
* ``assign_launch_keys``        —  POST   /api/v1/quiktieper/assign-keys
* ``launcher_start``            —  POST   /api/v1/quiktieper/launcher/start
* ``launcher_stop``             —  POST   /api/v1/quiktieper/launcher/stop
* ``launcher_status``           —  GET    /api/v1/quiktieper/launcher/status
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from aiohttp.web import Request, Response, json_response

import QuikTieper
from QuikTieper.app_command_presets import APP_COMMAND_PRESETS
from QuikTieper.desktop_apps import DesktopApp, discover_desktop_apps, merge_desktop_apps
from QuikTieper.key_assignment import assign_missing_launch_keys
from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process launcher state
# ---------------------------------------------------------------------------
# Holds a reference to an AppLauncher once started via the API.
_launcher: QuikTieper.AppLauncher | None = None


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def quiktieper_status(request: Request) -> Response:
    """GET /api/v1/quiktieper/status — return aggregated QuikTieper status.

    Response shape
    --------------
    .. code-block:: json

        {
          "ok": true,
          "data": {
            "config_path": "…",
            "bindings_count": 5,
            "launcher_running": false,
            "presets_count": 42,
            "has_pystray": true
          }
        }
    """
    config_path = str(QuikTieper.DEFAULT_CONFIG_PATH)
    bindings_count = 0
    try:
        QuikTieper.ensure_config()
        config = QuikTieper.load_config()
        apps = config.get("apps", [])
        bindings_count = sum(len(app.get("shortcuts", [])) for app in apps)
    except Exception as exc:
        logger.warning("Failed to load bindings config for status: %s", exc)

    # Check pystray availability
    try:
        import pystray  # noqa: F401
        has_pystray = True
    except ImportError:
        has_pystray = False

    return json_response({
        "ok": True,
        "data": {
            "config_path": config_path,
            "bindings_count": bindings_count,
            "launcher_running": _launcher is not None,
            "presets_count": len(APP_COMMAND_PRESETS),
            "has_pystray": has_pystray,
        },
    })


async def list_presets(request: Request) -> Response:
    """GET /api/v1/quiktieper/presets — return app command presets.

    Returns the built-in list of :class:`AppCommandPreset` objects
    from ``QuikTieper.app_command_presets``.

    Response shape
    --------------
    .. code-block:: json

        {
          "ok": true,
          "data": {
            "presets": [
              { "display_name": "Brave", "aliases": ["Brave","brave"], "commands": ["brave"] },
              …
            ]
          }
        }
    """
    presets = []
    for preset in APP_COMMAND_PRESETS:
        presets.append({
            "display_name": preset.display_name,
            "aliases": list(preset.aliases),
            "commands": list(preset.commands),
        })

    return json_response({"ok": True, "data": {"presets": presets}})


async def list_desktop_apps(request: Request) -> Response:
    """GET /api/v1/quiktieper/desktop-apps — scan and list installed .desktop apps.

    Scans the standard ``*.desktop`` file locations and returns a list of
    discovered applications.

    Response shape
    --------------
    .. code-block:: json

        {
          "ok": true,
          "data": {
            "apps": [
              {
                "name": "Firefox",
                "command": "firefox %u",
                "desktop_id": "firefox",
                "window_match": "firefox",
                "categories": ["Network","WebBrowser"]
              },
              …
            ]
          }
        }
    """
    try:
        apps = discover_desktop_apps()
    except Exception as exc:
        logger.exception("Failed to discover desktop apps")
        raise ApiError(500, f"Desktop app discovery failed: {exc}") from exc

    return json_response({
        "ok": True,
        "data": {
            "apps": [
                {
                    "name": app.name,
                    "command": app.command,
                    "desktop_id": app.desktop_id,
                    "window_match": app.window_match,
                    "categories": list(app.categories),
                }
                for app in apps
            ],
        },
    })


async def import_desktop_apps(request: Request) -> Response:
    """POST /api/v1/quiktieper/import-apps — merge desktop apps into bindings.

    Scans installed ``.desktop`` files and adds any that are not already
    present in the current bindings configuration.  The updated config is
    saved, and the number of newly added apps is returned.

    Response shape
    --------------
    .. code-block:: json

        {
          "ok": true,
          "data": { "added": 5, "path": "…" }
        }
    """
    try:
        QuikTieper.ensure_config()
        config = QuikTieper.load_config()
        apps = discover_desktop_apps()
        merged, added = merge_desktop_apps(config, apps)
        result_path = QuikTieper.save_config(merged)
    except Exception as exc:
        logger.exception("Failed to import desktop apps")
        raise ApiError(500, f"Failed to import desktop apps: {exc}") from exc

    return json_response({
        "ok": True,
        "data": {
            "added": added,
            "path": str(result_path),
        },
    })


async def assign_launch_keys(request: Request) -> Response:
    """POST /api/v1/quiktieper/assign-keys — assign launch keys to unbound apps.

    Iterates over the bindings config and assigns a unique launch key chord
    to any app that is missing launch keys.  The updated config is saved.

    Response shape
    --------------
    .. code-block:: json

        {
          "ok": true,
          "data": { "assigned": 3, "path": "…" }
        }
    """
    try:
        QuikTieper.ensure_config()
        config = QuikTieper.load_config()
        assigned_count = assign_missing_launch_keys(config)
        result_path = QuikTieper.save_config(config)
    except Exception as exc:
        logger.exception("Failed to assign launch keys")
        raise ApiError(500, f"Failed to assign launch keys: {exc}") from exc

    return json_response({
        "ok": True,
        "data": {
            "assigned": assigned_count,
            "path": str(result_path),
        },
    })


async def launcher_start(request: Request) -> Response:
    """POST /api/v1/quiktieper/launcher/start — start the AppLauncher.

    Parses the current bindings config, creates an ``AppLauncher`` instance,
    and holds it in-process.  If a launcher is already running this is a
    no-op (returns 200).

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "running": true } }
    """
    global _launcher

    if _launcher is not None:
        return json_response({"ok": True, "data": {"running": True}})

    try:
        QuikTieper.ensure_config()
        config = QuikTieper.load_config()
        raw_apps = config.get("apps", [])
        bindings = QuikTieper.parse_bindings(raw_apps)
        _launcher = QuikTieper.AppLauncher(bindings)
    except Exception as exc:
        logger.exception("Failed to start launcher")
        raise ApiError(500, f"Failed to start launcher: {exc}") from exc

    logger.info("QuikTieper AppLauncher started with %d bindings", len(bindings))
    return json_response({"ok": True, "data": {"running": True}})


async def launcher_stop(request: Request) -> Response:
    """POST /api/v1/quiktieper/launcher/stop — stop the AppLauncher.

    Clears the in-process launcher reference.  If no launcher is running
    this is a no-op.

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "running": false } }
    """
    global _launcher

    if _launcher is None:
        return json_response({"ok": True, "data": {"running": False}})

    _launcher = None
    logger.info("QuikTieper AppLauncher stopped")
    return json_response({"ok": True, "data": {"running": False}})


async def launcher_status(request: Request) -> Response:
    """GET /api/v1/quiktieper/launcher/status — check if launcher is running.

    Response shape
    --------------
    .. code-block:: json

        {
          "ok": true,
          "data": {
            "running": true,
            "bindings_count": 12
          }
        }
    """
    bindings_count = 0
    if _launcher is not None:
        bindings_count = len(_launcher.bindings)

    return json_response({
        "ok": True,
        "data": {
            "running": _launcher is not None,
            "bindings_count": bindings_count,
        },
    })
