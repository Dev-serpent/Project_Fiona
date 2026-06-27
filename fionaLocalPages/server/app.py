#!/usr/bin/env python3
"""Fiona Local Pages API Server.

Serves the static frontend from ``fionaLocalPages/``, exposes a REST API
at ``/api/v1/``, WebSocket at ``/ws``, and SSE at ``/api/v1/stream``.

Usage:
    python fionaLocalPages/server/app.py [--port 8765] [--host 127.0.0.1]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so all Fiona modules are importable.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Also ensure the server package's parent is importable for relative imports.
_PACKAGE_ROOT = Path(__file__).resolve().parent  # fionaLocalPages/server/
_PACKAGE_PARENT = _PACKAGE_ROOT.parent  # fionaLocalPages/
if str(_PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PARENT))

# ---------------------------------------------------------------------------
# ── Imports ────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

import aiohttp
from aiohttp import web

# Use package-relative imports for internal modules.
# When running as `python app.py` these resolve via sys.path above.
from fionaLocalPages.server.middleware import (
    ApiError,
    cors_middleware,
    error_middleware,
    logging_middleware,
)

from fionaLocalPages.server.ws_server import WebSocketManager

from fionaLocalPages.server.handlers import (
    actions,
    agent,
    agents_crud,
    bindings,
    browser,
    camcoms,
    config,
    desktop,
    files,
    macros,
    notifications_handler as notifications,
    phiconnect,
    quiktieper,
    recall,
    sciretrieval,  # ADD
    settings_handler as settings,
    system,
    terminal,
    vsee,
    voice,
)

# ---------------------------------------------------------------------------
# ── Logging ────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("fiona.server")

# ---------------------------------------------------------------------------
# ── Global state ───────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

ws_manager = WebSocketManager(heartbeat_interval=30.0)

# ---------------------------------------------------------------------------
# ── Application Factory ────────────────────────────────────────────────────
# ---------------------------------------------------------------------------


async def _on_startup(app: web.Application) -> None:
    logger.info("Fiona API server starting — root=%s", _PROJECT_ROOT)


async def _on_shutdown(app: web.Application) -> None:
    logger.info("Shutting down Fiona API server…")
    await ws_manager.stop_periodic_pushes()


def create_app() -> web.Application:
    """Build and return the aiohttp Application."""
    static_path = (_PROJECT_ROOT / "fionaLocalPages").resolve()
    app = web.Application(
        middlewares=[
            logging_middleware,
            cors_middleware,
            error_middleware,
        ]
    )

    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_on_shutdown)

    app["ws_manager"] = ws_manager
    app["project_root"] = _PROJECT_ROOT

    _setup_static_routes(app, static_path)
    _setup_api_routes(app)
    _setup_websocket(app)
    _setup_sse(app)
    _setup_periodic_tasks(app)

    return app


# ---------------------------------------------------------------------------
# ── Route Setup ────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------


def _setup_static_routes(app: web.Application, static_path: Path) -> None:
    """Serve static files and SPA index.html fallback via a unified handler.

    Any GET request path that is not a registered API or WebSocket route
    will be handled here.  If the path maps to an existing file under
    *static_path*, that file is served.  Otherwise ``index.html`` is
    returned (SPA client-side routing).
    """
    logger.info("Serving static files from %s", static_path)
    static_path = static_path.resolve()
    index_path = static_path / "index.html"

    async def _static_or_spa(request: web.Request) -> web.StreamResponse:
        # Exclude API, WS, and /static/ paths — they have their own routes.
        path = request.path
        if path.startswith("/api/") or path.startswith("/ws") or path.startswith("/static/"):
            raise web.HTTPNotFound()

        # Resolve the requested path to an actual file.
        # Strip leading '/' and join with static_path.
        rel = path.lstrip("/")
        if not rel:
            # Root path — serve index.html
            if index_path.exists():
                return web.FileResponse(index_path)
            raise web.HTTPNotFound()

        file_candidate = (static_path / rel).resolve()
        try:
            file_candidate.relative_to(static_path)
        except ValueError:
            # Path traversal attempt
            raise web.HTTPNotFound()

        if file_candidate.is_file():
            return web.FileResponse(file_candidate)

        # File not found — serve index.html for SPA routing
        if index_path.exists():
            return web.FileResponse(index_path)

        raise web.HTTPNotFound()

    # Register root separately (don't go through the tail match).
    async def _serve_index(_request: web.Request) -> web.StreamResponse:
        if index_path.exists():
            return web.FileResponse(index_path)
        raise web.HTTPNotFound()

    app.router.add_get("/", _serve_index, name="index")
    app.router.add_get("/{tail:.*}", _static_or_spa, name="static_or_spa")


def _setup_api_routes(app: web.Application) -> None:
    """Register all REST API routes under /api/v1/."""

    # ── System ─────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/health", system.health)
    app.router.add_get("/api/v1/system/status", system.system_status)
    app.router.add_get("/api/v1/system/metrics", system.system_metrics)

    # ── Agent ──────────────────────────────────────────────────────────
    app.router.add_post("/api/v1/agent/ask", agent.agent_ask)
    app.router.add_post("/api/v1/agent/goal", agent.agent_goal)
    app.router.add_get("/api/v1/agent/status", agent.agent_status)
    app.router.add_get("/api/v1/agent/commands", agent.agent_commands)
    app.router.add_get("/api/v1/agent/models", agents_crud.check_model)

    # ── Agents CRUD ────────────────────────────────────────────────────
    app.router.add_get("/api/v1/agents", agents_crud.list_agents)
    app.router.add_post("/api/v1/agents", agents_crud.create_agent)
    app.router.add_post("/api/v1/agents/{id}/pause", agents_crud.pause_agent)
    app.router.add_post("/api/v1/agents/{id}/resume", agents_crud.resume_agent)
    app.router.add_post("/api/v1/agents/{id}/stop", agents_crud.stop_agent)
    app.router.add_post("/api/v1/agents/{id}/restart", agents_crud.restart_agent)

    # ── Actions ────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/actions", actions.list_actions)
    app.router.add_post("/api/v1/actions/run", actions.run_action)
    app.router.add_get("/api/v1/actions/history", actions.action_history)

    # ── Voice ──────────────────────────────────────────────────────────
    app.router.add_post("/api/v1/voice/parse", voice.voice_parse)
    app.router.add_post("/api/v1/voice/transcribe", voice.voice_transcribe)

    # ── Terminal ───────────────────────────────────────────────────────
    app.router.add_get("/api/v1/terminal/cwd", terminal.terminal_cwd)
    app.router.add_post("/api/v1/terminal/exec", terminal.terminal_exec)
    app.router.add_post("/api/v1/terminal/autocomplete", terminal.terminal_autocomplete)
    app.router.add_get("/api/v1/terminal/status", terminal.terminal_status)

    # ── Files ──────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/files/list", files.file_list)
    app.router.add_get("/api/v1/files/read", files.file_read)
    app.router.add_post("/api/v1/files/write", files.file_write)
    app.router.add_get("/api/v1/files/info", files.file_info)

    # ── Config ─────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/config", config.list_configs)
    app.router.add_get("/api/v1/config/{name}", config.read_config)
    app.router.add_put("/api/v1/config/{name}", config.update_config)

    # ── Browser ────────────────────────────────────────────────────────
    app.router.add_post("/api/v1/browser/start", browser.browser_start)
    app.router.add_post("/api/v1/browser/stop", browser.browser_stop)
    app.router.add_get("/api/v1/browser/status", browser.browser_status_handler)
    app.router.add_post("/api/v1/browser/navigate", browser.browser_navigate)
    app.router.add_post("/api/v1/browser/click", browser.browser_click)
    app.router.add_post("/api/v1/browser/screenshot", browser.browser_screenshot)
    app.router.add_post("/api/v1/browser/type", browser.browser_type)
    app.router.add_post("/api/v1/browser/get_text", browser.browser_get_text)

    # ── Desktop ────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/desktop/active", desktop.desktop_active)
    app.router.add_get("/api/v1/desktop/snapshot", desktop.desktop_snapshot_handler)

    # ── Recall ─────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/recall/search", recall.recall_search)
    app.router.add_post("/api/v1/recall/remember", recall.recall_remember)
    app.router.add_delete("/api/v1/recall/forget/{key}", recall.recall_forget)

    # ── Macros ─────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/macros", macros.list_macros)
    app.router.add_post("/api/v1/macros/run", macros.run_macro_handler)

    # ── CamComs ────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/camcoms/status", camcoms.camcoms_status)
    app.router.add_get("/api/v1/camcoms/identity", camcoms.camcoms_identity)

    # ── PhiConnect ─────────────────────────────────────────────────────
    app.router.add_get("/api/v1/phiconnect/status", phiconnect.phiconnect_status)
    app.router.add_get("/api/v1/phiconnect/identity", phiconnect.phiconnect_identity)
    app.router.add_get("/api/v1/phiconnect/messages", phiconnect.phiconnect_messages)
    app.router.add_post("/api/v1/phiconnect/send", phiconnect.phiconnect_send)
    app.router.add_post("/api/v1/phiconnect/trust", phiconnect.phiconnect_trust_key)

    # ── Vsee ───────────────────────────────────────────────────────────
    app.router.add_get("/api/v1/vsee/status", vsee.vsee_status)
    app.router.add_post("/api/v1/vsee/launch", vsee.vsee_launch)
    app.router.add_get("/api/v1/vsee/model", vsee.vsee_default_model)

    # ── Bindings ───────────────────────────────────────────────────────
    app.router.add_get("/api/v1/bindings", bindings.list_bindings)
    app.router.add_post("/api/v1/bindings/save", bindings.save_bindings)
    app.router.add_get("/api/v1/bindings/apps", bindings.get_apps)

    # ── QuikTieper ─────────────────────────────────────────────────────
    app.router.add_get("/api/v1/quiktieper/status", quiktieper.quiktieper_status)
    app.router.add_get("/api/v1/quiktieper/presets", quiktieper.list_presets)
    app.router.add_get("/api/v1/quiktieper/desktop-apps", quiktieper.list_desktop_apps)
    app.router.add_post("/api/v1/quiktieper/import-apps", quiktieper.import_desktop_apps)
    app.router.add_post("/api/v1/quiktieper/assign-keys", quiktieper.assign_launch_keys)
    app.router.add_post("/api/v1/quiktieper/launcher/start", quiktieper.launcher_start)
    app.router.add_post("/api/v1/quiktieper/launcher/stop", quiktieper.launcher_stop)
    app.router.add_get("/api/v1/quiktieper/launcher/status", quiktieper.launcher_status)

    # ── Notifications ──────────────────────────────────────────────────
    app.router.add_get("/api/v1/notifications", notifications.list_notifications)
    app.router.add_post("/api/v1/notifications/create", notifications.create_notification)
    app.router.add_post("/api/v1/notifications/dismiss", notifications.dismiss_notifications)

    # ── Settings ───────────────────────────────────────────────────────
    app.router.add_get("/api/v1/settings", settings.get_settings)
    app.router.add_put("/api/v1/settings", settings.put_settings)

    # ── SciRetrieval ───────────────────────────────────────────────────
    app.router.add_post("/api/v1/sciretrieval/search", sciretrieval.sciretrieval_search)
    app.router.add_post("/api/v1/sciretrieval/classify", sciretrieval.sciretrieval_classify)
    app.router.add_get("/api/v1/sciretrieval/providers", sciretrieval.sciretrieval_providers)
    app.router.add_post("/api/v1/sciretrieval/getdata", sciretrieval.sciretrieval_getdata)
    app.router.add_post("/api/v1/sciretrieval/cache/clear", sciretrieval.sciretrieval_cache_clear)
    app.router.add_post("/api/v1/sciretrieval/enrich", sciretrieval.sciretrieval_enrich)


def _setup_websocket(app: web.Application) -> None:
    """Register the WebSocket endpoint at /ws."""

    async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=1024 * 1024)
        await ws.prepare(request)

        peer_id = await ws_manager.register(ws)

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await ws_manager.handle_message(peer_id, msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WS error for peer %d: %s", peer_id, ws.exception())
        finally:
            await ws_manager.unregister(peer_id)

        return ws

    app.router.add_get("/ws", websocket_handler)
    ws_manager._handlers["ping"] = _ws_ping


async def _ws_ping(params: dict[str, Any]) -> dict[str, object]:
    """Handle a ``ping`` RPC — returns pong with server timestamp."""
    return {"pong": True, "timestamp": time.time()}


# ---------------------------------------------------------------------------
# ── SSE ────────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------


def _setup_sse(app: web.Application) -> None:
    """Register the SSE endpoint at /api/v1/stream."""

    async def sse_handler(request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await response.prepare(request)
        await response.write(b": connected\n\n")

        try:
            while True:
                await asyncio.sleep(30)
                await response.write(b": heartbeat\n\n")
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        except Exception:
            logger.exception("SSE connection error")

        return response

    app.router.add_get("/api/v1/stream", sse_handler)


# ---------------------------------------------------------------------------
# ── Periodic Background Tasks ──────────────────────────────────────────────
# ---------------------------------------------------------------------------


def _setup_periodic_tasks(app: web.Application) -> None:
    """Start periodic system metrics pushes via WebSocket."""

    async def _collect_metrics() -> dict[str, object]:
        return {
            "timestamp": time.time(),
            "cpu_percent": system._cpu_percent(),
            "memory": system._memory_info(),
            "disk": system._disk_info(),
            "loadavg": system._loadavg(),
            "uptime": system._uptime(),
        }

    async def _start_metrics_push(app: web.Application) -> None:
        await ws_manager.start_periodic_push(
            interval=2.0,
            factory=_collect_metrics,
            event_name="system:metrics",
        )

    app.on_startup.append(_start_metrics_push)


# ---------------------------------------------------------------------------
# ── Main ───────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Fiona Local Pages API Server")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="Port to listen on (default: 8765)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger("fiona.server").setLevel(logging.DEBUG)
        logging.getLogger("aiohttp.access").setLevel(logging.DEBUG)

    app = create_app()
    logger.info("Starting Fiona API server on http://%s:%d", args.host, args.port)
    web.run_app(app, host=args.host, port=args.port, print=lambda *_: None)


if __name__ == "__main__":
    main()
