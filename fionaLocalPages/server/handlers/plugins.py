"""Plugins API endpoints — list, enable/disable, uninstall, and install plugins.

Uses ``fiona.plugin_system.PluginManager`` for discovery and lifecycle
management.  Falls back gracefully (empty list) when the manager is not
available or no plugins are installed.

Handlers
--------
* ``list_plugins``       —  GET    /api/v1/plugins
* ``enable_plugin``      —  POST   /api/v1/plugins/{id}/enable
* ``disable_plugin``     —  POST   /api/v1/plugins/{id}/disable
* ``uninstall_plugin``   —  DELETE /api/v1/plugins/{id}
* ``install_plugin``     —  POST   /api/v1/plugins/install
* ``check_updates``      —  GET    /api/v1/plugins/updates
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
# PluginManager integration
# ---------------------------------------------------------------------------

try:
    from fiona.plugin_system import PluginManager, PluginError as FionaPluginError

    _HAS_PLUGIN_SYSTEM = True
except ImportError:
    PluginManager = None  # type: ignore[assignment]
    FionaPluginError = Exception  # type: ignore[assignment]
    _HAS_PLUGIN_SYSTEM = False
    logger.warning("fiona.plugin_system not available — plugins API will return empty results")

# ---------------------------------------------------------------------------
# Default search paths
# ---------------------------------------------------------------------------

_DEFAULT_SEARCH_PATHS: list[str] = [
    str(Path.home() / ".config" / "fiona" / "plugins"),
    # Project-level plugin directories
    str(Path(__file__).resolve().parents[3] / "fiona" / "plugins"),
    str(Path(__file__).resolve().parents[3] / "plugins"),
]


def _get_plugin_manager() -> PluginManager | None:
    """Create and return a PluginManager instance, or None if unavailable."""
    if not _HAS_PLUGIN_SYSTEM or PluginManager is None:
        return None
    return PluginManager(search_paths=_DEFAULT_SEARCH_PATHS)


def _read_raw_manifest(plugin_dir: Path) -> dict[str, Any]:
    """Read additional metadata from a plugin directory's ``plugin.json``.

    Returns extra fields beyond ``PluginManifest`` (e.g. category,
    dependencies, config, homepage, fullDescription).
    """
    json_path = plugin_dir / "plugin.json"
    if json_path.is_file():
        try:
            return dict(json.loads(json_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass

    # Try YAML if available
    try:
        import yaml  # type: ignore[import-untyped]  # noqa
    except ImportError:
        yaml = None  # type: ignore[assignment]

    if yaml is not None:
        yaml_path = plugin_dir / "plugin.yaml"
        if yaml_path.is_file():
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (ValueError, OSError):
                pass

    return {}


def _collect_plugins(manager: PluginManager | None) -> list[dict[str, Any]]:
    """Discover plugins and return a list of rich metadata dicts.

    Each dict contains: id, name, version, author, description, status,
    category, dependencies, config, homepage, fullDescription.

    The ``status`` field reflects whether the plugin is currently loaded
    (active) in the manager.
    """
    if manager is None:
        return []

    manifests = manager.discover()
    plugins: list[dict[str, Any]] = []

    for manifest in manifests:
        is_active = manifest.name in manager.active_plugins

        # Try to get richer metadata from the raw manifest file
        extra: dict[str, Any] = {}
        for sp in manager.search_paths:
            base = Path(sp).expanduser().resolve()
            if not base.is_dir():
                continue
            candidate = base / manifest.name
            if candidate.is_dir():
                extra = _read_raw_manifest(candidate)
                break

        plugins.append({
            "id": manifest.name,
            "name": extra.get("name", manifest.name),
            "version": extra.get("version", manifest.version),
            "author": extra.get("author", manifest.author),
            "description": extra.get("description", manifest.description),
            "status": "enabled" if is_active else "disabled",
            "category": extra.get("category", "community"),
            "homepage": extra.get("homepage", ""),
            "dependencies": extra.get("dependencies", []),
            "config": extra.get("config", {}),
            "fullDescription": extra.get(
                "fullDescription",
                extra.get("full_description", manifest.description),
            ),
            "entry_point": manifest.entry_point,
        })

    return plugins


def _find_plugin_dir(manager: PluginManager | None, plugin_id: str) -> Path | None:
    """Find the filesystem directory for a plugin by ID."""
    if manager is None:
        return None
    for sp in manager.search_paths:
        base = Path(sp).expanduser().resolve()
        if not base.is_dir():
            continue
        candidate = base / plugin_id
        if candidate.is_dir():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Simple persistent state for enabled/disabled plugins
# ---------------------------------------------------------------------------

_STATE_FILE = Path.home() / ".config" / "fiona" / "plugin_state.json"


def _load_plugin_state() -> dict[str, bool]:
    """Load enabled/disabled state from disk.

    Returns a dict mapping plugin id → True (enabled) / False (disabled).
    Plugins not in the dict default to enabled.
    """
    if not _STATE_FILE.exists():
        return {}
    try:
        return dict(json.loads(_STATE_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read plugin state file")
        return {}


def _save_plugin_state(state: dict[str, bool]) -> None:
    """Persist enabled/disabled state to disk."""
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        _STATE_FILE.write_text(
            json.dumps(state, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Failed to write plugin state: %s", exc)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def list_plugins(_request: Request) -> Response:
    """GET /api/v1/plugins — return all discovered plugins.

    Response shape
    --------------
    .. code-block:: json

        {
            "ok": true,
            "data": [
                {
                    "id": "voice-input",
                    "name": "Voice Input",
                    "version": "1.2.0",
                    "author": "Fiona Team",
                    "description": "...",
                    "status": "enabled",
                    "category": "core",
                    "homepage": "",
                    "dependencies": ["fiona-core >= 0.1.0"],
                    "config": { ... },
                    "fullDescription": "..."
                }
            ]
        }
    """
    manager = _get_plugin_manager()
    if manager is None:
        return json_response({"ok": True, "data": []})

    try:
        plugins = _collect_plugins(manager)

        # Apply persisted state overrides
        state = _load_plugin_state()
        for plugin in plugins:
            pid = plugin["id"]
            if pid in state:
                plugin["status"] = "enabled" if state[pid] else "disabled"

        return json_response({"ok": True, "data": plugins})
    except Exception as exc:
        logger.exception("Failed to list plugins")
        raise ApiError(500, f"Failed to list plugins: {exc}")


async def enable_plugin(request: Request) -> Response:
    """POST /api/v1/plugins/{id}/enable — enable a plugin.

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "id": "...", "status": "enabled" } }
    """
    plugin_id = request.match_info.get("id", "")
    if not plugin_id:
        raise ApiError(400, "Missing plugin id")

    manager = _get_plugin_manager()
    if manager is None:
        raise ApiError(503, "Plugin system is not available")

    try:
        # Try to load/activate the plugin
        manager.load(plugin_id)
    except FionaPluginError as exc:
        # If loading fails, still mark as enabled in state
        logger.warning("Could not activate plugin %s: %s", plugin_id, exc)

    # Persist enabled state
    state = _load_plugin_state()
    state[plugin_id] = True
    _save_plugin_state(state)

    return json_response({
        "ok": True,
        "data": {"id": plugin_id, "status": "enabled"},
    })


async def disable_plugin(request: Request) -> Response:
    """POST /api/v1/plugins/{id}/disable — disable a plugin.

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "id": "...", "status": "disabled" } }
    """
    plugin_id = request.match_info.get("id", "")
    if not plugin_id:
        raise ApiError(400, "Missing plugin id")

    manager = _get_plugin_manager()
    if manager is None:
        raise ApiError(503, "Plugin system is not available")

    try:
        # Deactivate the plugin
        manager.unload(plugin_id)
    except FionaPluginError as exc:
        logger.warning("Could not deactivate plugin %s: %s", plugin_id, exc)

    # Persist disabled state
    state = _load_plugin_state()
    state[plugin_id] = False
    _save_plugin_state(state)

    return json_response({
        "ok": True,
        "data": {"id": plugin_id, "status": "disabled"},
    })


async def uninstall_plugin(request: Request) -> Response:
    """DELETE /api/v1/plugins/{id} — remove a plugin.

    This removes the plugin directory from the filesystem (if it was
    installed in a user-writable location) and clears its state.

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "id": "...", "removed": true } }
    """
    plugin_id = request.match_info.get("id", "")
    if not plugin_id:
        raise ApiError(400, "Missing plugin id")

    manager = _get_plugin_manager()

    # Unload if active
    if manager is not None:
        try:
            manager.unload(plugin_id)
        except FionaPluginError:
            pass

    # Remove from state
    state = _load_plugin_state()
    state.pop(plugin_id, None)
    _save_plugin_state(state)

    # Try to remove plugin directory
    plugin_dir = _find_plugin_dir(manager, plugin_id)
    removed = False
    if plugin_dir is not None and plugin_dir.exists():
        try:
            import shutil
            shutil.rmtree(plugin_dir)
            removed = True
            logger.info("Removed plugin directory: %s", plugin_dir)
        except OSError as exc:
            logger.error("Failed to remove plugin directory %s: %s", plugin_dir, exc)

    return json_response({
        "ok": True,
        "data": {"id": plugin_id, "removed": removed},
    })


async def install_plugin(request: Request) -> Response:
    """POST /api/v1/plugins/install — install a plugin.

    Accepts a ``path`` (local filesystem path) or ``url`` (remote URL)
    pointing to a plugin package.  This is a placeholder implementation
    that copies/extracts the plugin into the user's plugin directory.

    Request body
    ------------
    .. code-block:: json

        { "path": "/path/to/plugin.zip" }

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": { "id": "...", "name": "...", ... } }
    """
    try:
        body: Any = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    source = body.get("path") or body.get("url")
    if not source or not isinstance(source, str):
        raise ApiError(400, "Missing 'path' or 'url' in request body")

    # Determine the install directory
    install_dir = Path.home() / ".config" / "fiona" / "plugins"
    install_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Installing plugin from %s → %s", source, install_dir)

    # TODO: implement actual plugin extraction/installation
    # For now, detect a local directory and symlink it
    source_path = Path(source).expanduser().resolve()

    plugin_id = ""
    installed = False

    if source_path.is_dir():
        # Source is a directory — copy or symlink
        plugin_id = source_path.name
        target = install_dir / plugin_id
        if not target.exists():
            try:
                # Try symlink first, fallback to copy
                import os
                os.symlink(str(source_path), str(target))
                installed = True
            except (OSError, AttributeError):
                import shutil
                shutil.copytree(source_path, target, dirs_exist_ok=True)
                installed = True
    elif source_path.is_file() and source_path.suffix in (".zip", ".tgz", ".gz"):
        # TODO: extract archive
        logger.warning("Archive installation not yet implemented: %s", source)
        installed = False
    else:
        logger.warning("Unrecognized plugin source: %s", source)
        installed = False

    if not installed:
        raise ApiError(400, f"Could not install plugin from {source}")

    # Discover the newly installed plugin
    manager = _get_plugin_manager()
    if manager is not None:
        manager.discover()

    # Return the plugin metadata
    if manager is not None and plugin_id in manager.manifests:
        manifest = manager.manifests[plugin_id]
        extra = _read_raw_manifest(install_dir / plugin_id)
        return json_response({
            "ok": True,
            "data": {
                "id": plugin_id,
                "name": extra.get("name", manifest.name),
                "version": extra.get("version", manifest.version),
                "author": extra.get("author", manifest.author),
                "description": extra.get("description", manifest.description),
                "status": "enabled",
                "category": extra.get("category", "community"),
                "dependencies": extra.get("dependencies", []),
                "config": extra.get("config", {}),
                "fullDescription": extra.get("fullDescription", manifest.description),
            },
        })

    return json_response({
        "ok": True,
        "data": {"id": plugin_id, "name": plugin_id, "status": "enabled"},
    })


async def check_updates(_request: Request) -> Response:
    """GET /api/v1/plugins/updates — check for newer plugin versions.

    Compares installed plugin versions against a remote registry.
    Currently a placeholder — returns an empty list.

    Response shape
    --------------
    .. code-block:: json

        { "ok": true, "data": [] }
    """
    # TODO: implement actual version comparison against a plugin registry
    return json_response({"ok": True, "data": []})
