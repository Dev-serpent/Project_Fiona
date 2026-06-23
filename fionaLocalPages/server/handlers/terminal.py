"""Terminal API endpoints.

Wraps FionaCore.shell_safety.safe_subprocess_run() and
TerminalAssist.terminal_assist_status().
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.web import Request, Response, json_response

from FionaCore.shell_safety import ShellCommandError, safe_subprocess_run
from TerminalAssist import terminal_assist_status

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Handlers ───────────────────────────────────────────────────────────────


async def terminal_exec(request: Request) -> Response:
    """POST /api/v1/terminal/exec

    Body: { command, args?, timeout? }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    command_input: str | list[str] | None = body.get("command")
    if not command_input:
        raise ApiError(400, "Missing required field: command")

    timeout = min(float(body.get("timeout", 30)), 120)

    # Normalize to list[str].
    if isinstance(command_input, str):
        args: list[str] = command_input.split()
    elif isinstance(command_input, list):
        args = [str(a) for a in command_input]
    else:
        raise ApiError(400, "command must be a string or list of strings")

    try:
        completed = safe_subprocess_run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return json_response({
            "ok": True,
            "data": {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "command": args,
            },
        })
    except ShellCommandError as exc:
        raise ApiError(403, str(exc)) from exc
    except Exception as exc:
        logger.exception("Terminal exec failed")
        raise ApiError(500, str(exc)) from exc


async def terminal_status(_request: Request) -> Response:
    """GET /api/v1/terminal/status — calls terminal_assist_status()."""
    try:
        status = terminal_assist_status()
        return json_response({
            "ok": True,
            "data": status,
        })
    except Exception as exc:
        logger.exception("Terminal status failed")
        raise ApiError(500, str(exc)) from exc
