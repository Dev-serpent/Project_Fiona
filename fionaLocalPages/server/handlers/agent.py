"""Chat/Agent API endpoints.

Wraps Agent.OllamaClient and Agent.AgentOrchestrator.
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.web import Request, Response, json_response

from Agent import (
    AgentOrchestrator,
    OllamaClient,
    command_registry,
    run_agent_goal,
)

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

# Default (or reuse) client so warm models stay loaded.
_client: OllamaClient | None = None


def _get_client() -> OllamaClient:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = OllamaClient()
    return _client


# ── Handlers ───────────────────────────────────────────────────────────────


async def agent_ask(request: Request) -> Response:
    """POST /api/v1/agent/ask

    Body: { prompt, model?, system?, temperature?, max_tokens? }
    """
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    prompt: str | None = body.get("prompt")
    if not prompt:
        raise ApiError(400, "Missing required field: prompt")

    try:
        client = _get_client()
        response_text = client.ask(
            prompt=prompt,
            temperature=body.get("temperature", 0.3),
            max_tokens=body.get("max_tokens", 2048),
        )
        return json_response({
            "ok": True,
            "data": {"response": response_text},
        })
    except Exception as exc:
        logger.exception("Agent ask failed")
        raise ApiError(502, f"Agent request failed: {exc}") from exc


async def agent_goal(request: Request) -> Response:
    """POST /api/v1/agent/goal

    Body: { goal, turns? }
    """
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    goal: str | None = body.get("goal")
    if not goal:
        raise ApiError(400, "Missing required field: goal")

    try:
        result = run_agent_goal(goal=goal)
        return json_response({
            "ok": True,
            "data": {"result": result},
        })
    except Exception as exc:
        logger.exception("Agent goal failed")
        raise ApiError(502, f"Agent goal failed: {exc}") from exc


async def agent_status(_request: Request) -> Response:
    """GET /api/v1/agent/status — calls OllamaClient.health()."""
    try:
        client = _get_client()
        health = client.health()
        return json_response({
            "ok": True,
            "data": {"connected": True, "health": health},
        })
    except Exception as exc:
        logger.warning("Agent health check failed: %s", exc)
        return json_response({
            "ok": True,
            "data": {"connected": False, "error": str(exc)},
        })


async def agent_commands(_request: Request) -> Response:
    """GET /api/v1/agent/commands — calls Agent.command_registry()."""
    try:
        registry = command_registry()
        return json_response({
            "ok": True,
            "data": registry,
        })
    except Exception as exc:
        logger.exception("Failed to get command registry")
        raise ApiError(500, str(exc)) from exc
