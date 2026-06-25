"""Agents CRUD API endpoints.

Provides an in-memory agent lifecycle store with pause/resume/stop/restart
controls, plus model-availability detection via Ollama.

Data is ***not*** persisted — stored in a module-level dict.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from aiohttp.web import Request, Response, json_response

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory agent store
# ---------------------------------------------------------------------------

_agent_store: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def list_agents(_request: Request) -> Response:
    """GET /api/v1/agents — list all agents plus available Ollama models."""
    from Agent import OllamaClient

    client = OllamaClient()
    models: list[str] = []
    try:
        health_data = client.health()
        # health() calls GET /api/tags which returns {"models": [...]}
        models = [m.get("name", "") for m in health_data.get("models", [])]
    except Exception:
        logger.debug("Could not reach Ollama for model list", exc_info=True)

    agents = list(_agent_store.values())
    return json_response({
        "ok": True,
        "data": agents,
        "meta": {"available_models": models},
    })


async def create_agent(request: Request) -> Response:
    """POST /api/v1/agents — create a new agent entry."""
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    name = body.get("name", "New Agent")
    model = body.get("model", "qwen3:8b")
    system_prompt = body.get("system_prompt", "")

    agent_id = uuid.uuid4().hex[:8]
    agent = {
        "id": agent_id,
        "name": name,
        "model": model,
        "system_prompt": system_prompt,
        "status": "idle",
        "created_at": time.time(),
        "current_action": "",
        "tokens_used": 0,
        "elapsed_ms": 0,
        "progress": None,
    }
    _agent_store[agent_id] = agent
    logger.info("Agent created: %s (%s)", agent_id, name)
    return json_response({"ok": True, "data": agent}, status=201)


async def pause_agent(request: Request) -> Response:
    """POST /api/v1/agents/{id}/pause — pause an agent."""
    agent_id = request.match_info.get("id")
    if agent_id not in _agent_store:
        raise ApiError(404, f"Agent {agent_id} not found")
    _agent_store[agent_id]["status"] = "paused"
    return json_response({"ok": True, "data": _agent_store[agent_id]})


async def resume_agent(request: Request) -> Response:
    """POST /api/v1/agents/{id}/resume — resume a paused agent."""
    agent_id = request.match_info.get("id")
    if agent_id not in _agent_store:
        raise ApiError(404, f"Agent {agent_id} not found")
    _agent_store[agent_id]["status"] = "idle"
    return json_response({"ok": True, "data": _agent_store[agent_id]})


async def stop_agent(request: Request) -> Response:
    """POST /api/v1/agents/{id}/stop — stop an agent."""
    agent_id = request.match_info.get("id")
    if agent_id not in _agent_store:
        raise ApiError(404, f"Agent {agent_id} not found")
    _agent_store[agent_id]["status"] = "stopped"
    return json_response({"ok": True, "data": _agent_store[agent_id]})


async def restart_agent(request: Request) -> Response:
    """POST /api/v1/agents/{id}/restart — restart/cycle an agent."""
    agent_id = request.match_info.get("id")
    if agent_id not in _agent_store:
        raise ApiError(404, f"Agent {agent_id} not found")
    _agent_store[agent_id].update({
        "status": "idle",
        "current_action": "",
        "tokens_used": 0,
        "elapsed_ms": 0,
        "progress": None,
    })
    return json_response({"ok": True, "data": _agent_store[agent_id]})


async def check_model(request: Request) -> Response:
    """GET /api/v1/agent/models — list available Ollama models.

    Returns whether ``qwen3:8b`` (the default model) is available.
    """
    from Agent import OllamaClient

    client = OllamaClient()
    try:
        health_data = client.health()
        models = [m.get("name", "") for m in health_data.get("models", [])]
        qwen_available = any("qwen3:8b" in m for m in models)
        return json_response({
            "ok": True,
            "data": {
                "models": models,
                "qwen3_8b_available": qwen_available,
            },
        })
    except Exception as exc:
        logger.warning("Ollama model check failed: %s", exc)
        return json_response({
            "ok": True,
            "data": {
                "models": [],
                "qwen3_8b_available": False,
                "error": str(exc),
            },
        })
