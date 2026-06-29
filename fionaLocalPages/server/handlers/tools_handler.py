"""REST API handlers for the tool system (fiona/tools).

Provides endpoints to list, execute, and count registered scientific
function tools (unit convert, chem resolve, etc.).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web
from Agent.tool_runtime import ToolRuntime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy runtime singleton (cached at module level)
# ---------------------------------------------------------------------------

_tool_runtime: ToolRuntime | None = None


def _get_runtime() -> ToolRuntime:
    global _tool_runtime  # noqa: PLW0603
    if _tool_runtime is None:
        _tool_runtime = ToolRuntime()
    return _tool_runtime


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_list_tools(request: web.Request) -> web.Response:
    """GET /api/v1/tools

    Returns the list of all registered tools in Ollama-compatible format.
    Query params:
        ?category=physics  (optional, filters by category in description)
    """
    runtime = _get_runtime()
    tools = runtime.get_ollama_tools()

    category = request.query.get("category")
    if category:
        filtered = [
            t for t in tools
            if category.lower() in t["function"]["description"].lower()
        ]
        return web.json_response({
            "tools": filtered,
            "count": len(filtered),
            "total": len(tools),
            "category": category,
        })

    return web.json_response({"tools": tools, "count": len(tools)})


async def handle_execute_tool(request: web.Request) -> web.Response:
    """POST /api/v1/tools/execute

    Body (JSON):
        {"name": "unit_convert", "arguments": {"value": 5, "from_unit": "meter", "to_unit": "foot"}}

    Returns the ToolResult as JSON.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    if not isinstance(body, dict):
        return web.json_response({"error": "Body must be a JSON object"}, status=400)

    name: Any = body.get("name")
    arguments: dict[str, Any] = body.get("arguments", {})

    if not name or not isinstance(name, str):
        return web.json_response({"error": "Missing or invalid 'name' field"}, status=400)

    if not isinstance(arguments, dict):
        return web.json_response({"error": "'arguments' must be a JSON object"}, status=400)

    from fiona.tools.models import ToolCall, ToolContext

    call = ToolCall(id="api", function_name=name, arguments=arguments)
    context = ToolContext(logger=logger)

    runtime = _get_runtime()
    result = await runtime.execute_tool(call, context)

    return web.json_response({
        "success": result.success,
        "content": result.content,
        "error": result.error,
        "metadata": result.metadata,
        "citations": result.citations,
    })


async def handle_tool_count(request: web.Request) -> web.Response:
    """GET /api/v1/tools/count

    Returns the total number of registered tools.
    """
    runtime = _get_runtime()
    tools = runtime.get_ollama_tools()
    return web.json_response({"count": len(tools)})
