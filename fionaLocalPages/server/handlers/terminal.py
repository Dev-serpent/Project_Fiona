"""Terminal API endpoints — shell execution, built-in commands, autocomplete.

All terminal logic lives server-side.  The frontend is a thin client that
sends user input to ``POST /api/v1/terminal/exec`` and displays whatever
``stdout`` / ``stderr`` the backend returns.

The backend tracks the current working directory (``_cwd``) across
commands so that ``cd`` works correctly — each subprocess runs in the
tracked directory.
"""

from __future__ import annotations

import logging
import os
import shlex
from typing import Any

from aiohttp.web import Request, Response, json_response

from FionaCore.shell_safety import ShellCommandError, safe_subprocess_run
from TerminalAssist import terminal_assist_status

from fionaLocalPages.server.middleware import ApiError


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persistent session state (single-user; all tabs share the same cwd)
# ---------------------------------------------------------------------------
_cwd: str = os.path.expanduser("~")

# ---------------------------------------------------------------------------
# Categorized command reference (server-side)
# ---------------------------------------------------------------------------

COMMAND_REFERENCE: dict[str, list[dict[str, str]]] = {
    "File Navigation": [
        {"cmd": "pwd", "desc": "Show current directory"},
        {"cmd": "ls", "desc": "List files"},
        {"cmd": "ls -la", "desc": "Detailed listing including hidden files"},
        {"cmd": "cd <dir>", "desc": "Change directory"},
        {"cmd": "cd ..", "desc": "Go up one directory"},
        {"cmd": "cd ~", "desc": "Go to home directory"},
    ],
    "File Operations": [
        {"cmd": "touch <file>", "desc": "Create empty file"},
        {"cmd": "mkdir <dir>", "desc": "Create directory"},
        {"cmd": "cp <src> <dest>", "desc": "Copy file"},
        {"cmd": "cp -r <dir1> <dir2>", "desc": "Copy directory"},
        {"cmd": "mv <old> <new>", "desc": "Move/rename"},
        {"cmd": "rm <file>", "desc": "Delete file"},
        {"cmd": "rm -r <dir>", "desc": "Delete directory"},
    ],
    "Viewing Files": [
        {"cmd": "cat <file>", "desc": "Display file"},
        {"cmd": "less <file>", "desc": "Scroll through file"},
        {"cmd": "head <file>", "desc": "First 10 lines"},
        {"cmd": "tail <file>", "desc": "Last 10 lines"},
        {"cmd": "tail -f <log>", "desc": "Follow log updates"},
    ],
    "Searching": [
        {"cmd": 'find . -name "<pattern>"', "desc": "Find files"},
        {"cmd": 'grep "<text>" <file>', "desc": "Search text"},
        {"cmd": 'grep -r "<text>" .', "desc": "Recursive search"},
        {"cmd": "which <cmd>", "desc": "Locate executable"},
    ],
    "System Information": [
        {"cmd": "uname -a", "desc": "System information"},
        {"cmd": "hostname", "desc": "Hostname"},
        {"cmd": "whoami", "desc": "Current user"},
        {"cmd": "uptime", "desc": "System uptime"},
        {"cmd": "df -h", "desc": "Disk usage"},
        {"cmd": "free -h", "desc": "Memory usage"},
    ],
    "Processes": [
        {"cmd": "ps aux", "desc": "List processes"},
        {"cmd": "top", "desc": "Interactive process viewer"},
        {"cmd": "htop", "desc": "Better process viewer (if installed)"},
        {"cmd": "kill <PID>", "desc": "Kill process"},
        {"cmd": "kill -9 <PID>", "desc": "Force kill"},
    ],
    "Networking": [
        {"cmd": "ping <host>", "desc": "Ping host"},
        {"cmd": "ip addr", "desc": "Show IP addresses"},
        {"cmd": "ss -tulpn", "desc": "Listening ports"},
        {"cmd": "curl <url>", "desc": "HTTP request"},
        {"cmd": "wget <url>", "desc": "Download file"},
    ],
    "Permissions": [
        {"cmd": "chmod +x <script>", "desc": "Make executable"},
        {"cmd": "chmod 755 <file>", "desc": "Set permissions"},
        {"cmd": "chown <user>:<group> <file>", "desc": "Change owner"},
    ],
    "Archives": [
        {"cmd": "tar -czf <archive>.tar.gz <folder>/", "desc": "Create tar.gz"},
        {"cmd": "tar -xzf <archive>.tar.gz", "desc": "Extract tar.gz"},
        {"cmd": "zip -r <archive>.zip <folder>/", "desc": "Create zip"},
        {"cmd": "unzip <archive>.zip", "desc": "Extract zip"},
    ],
    "Package Management (Debian/Kali)": [
        {"cmd": "sudo apt update", "desc": "Update package index"},
        {"cmd": "sudo apt upgrade", "desc": "Upgrade packages"},
        {"cmd": "sudo apt install <pkg>", "desc": "Install package"},
        {"cmd": "sudo apt remove <pkg>", "desc": "Remove package"},
    ],
    "Package Management (Arch)": [
        {"cmd": "sudo pacman -Syu", "desc": "Full system update"},
        {"cmd": "sudo pacman -S <pkg>", "desc": "Install package"},
        {"cmd": "sudo pacman -R <pkg>", "desc": "Remove package"},
    ],
    "Shell Utilities": [
        {"cmd": "help", "desc": "Show this command reference"},
        {"cmd": "?", "desc": "Shortcut for help"},
        {"cmd": "clear", "desc": "Clear terminal"},
        {"cmd": "history", "desc": "Command history"},
        {"cmd": "man <cmd>", "desc": "Manual page"},
        {"cmd": "<cmd> --help", "desc": "Quick help"},
        {"cmd": 'echo "<text>"', "desc": "Print text"},
    ],
    "Pipes & Redirection": [
        {"cmd": "<cmd> > <file>", "desc": "Redirect output (overwrite)"},
        {"cmd": "<cmd> >> <file>", "desc": "Append output"},
        {"cmd": "<cmd> < <file>", "desc": "Input from file"},
        {"cmd": "<cmd1> | <cmd2>", "desc": "Pipe output"},
    ],
    "Fiona CLI": [
        {"cmd": "fiona --help", "desc": "Fiona CLI help"},
        {"cmd": "fiona status", "desc": "Fiona system status"},
        {"cmd": "fiona shell <cmd>", "desc": "Run shell command"},
        {"cmd": 'fiona agent ask "..."', "desc": "Ask the agent"},
        {"cmd": 'fiona agent goal "..."', "desc": "Set agent goal"},
        {"cmd": "fiona listen", "desc": "Start voice listener"},
        {"cmd": "fiona macro list", "desc": "List macros"},
        {"cmd": "fiona macro run <name>", "desc": "Run macro"},
        {"cmd": "fiona bind", "desc": "Show QuikTieper bindings"},
        {"cmd": "fiona camcoms status", "desc": "CamComs connection status"},
        {"cmd": 'fiona voice parse "..."', "desc": "Parse voice command"},
        {"cmd": 'fiona recall search "..."', "desc": "Search recall vault"},
        {"cmd": "fiona desktop snapshot", "desc": "Desktop snapshot"},
        {"cmd": "fiona browser start", "desc": "Start browser automation"},
        {"cmd": "fiona quiktieper init", "desc": "Initialize QuikTieper config"},
        {"cmd": "fiona quiktieper import-apps", "desc": "Import desktop apps"},
        {"cmd": "fiona quiktieper assign-keys", "desc": "Assign launch keys"},
        {"cmd": "fiona quiktieper list", "desc": "List QuikTieper bindings"},
        {"cmd": "fiona dashboard", "desc": "TerminalAssist dashboard"},
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_help_text() -> str:
    """Return the full command reference as a plain-text string."""
    lines: list[str] = [
        "",
        "== Fiona Terminal -- Command Reference ==",
        "",
    ]
    for category, entries in COMMAND_REFERENCE.items():
        lines.append(f"  {category}:")
        for entry in entries:
            padded = (entry["cmd"] + " " * 50)[:42]
            lines.append(f"    {padded} {entry['desc']}")
        lines.append("")
    lines.append("Tip: Type any command above -- it runs on the Fiona host.")
    lines.append("     Use Up/Down for history, Tab for autocomplete, Ctrl+L to clear.")
    return "\n".join(lines)


def _autocomplete_tokens() -> list[str]:
    """Return every unique first-token across all command reference entries."""
    tokens: set[str] = set()
    for entries in COMMAND_REFERENCE.values():
        for entry in entries:
            first = entry["cmd"].split(None, 1)[0] if entry["cmd"] else ""
            if first:
                tokens.add(first)
    return sorted(tokens)


def _find_autocomplete_matches(partial: str) -> list[str]:
    """Return up to 10 autocomplete suggestions for *partial*."""
    if not partial:
        return []
    lower = partial.lower()
    tokens = _autocomplete_tokens()
    exact = [t for t in tokens if t.startswith(lower)]
    fuzzy = [t for t in tokens if t != lower and lower in t and not t.startswith(lower)]
    return (exact + fuzzy)[:10]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def terminal_cwd(_request: Request) -> Response:
    """GET /api/v1/terminal/cwd — return the current working directory."""
    return json_response({
        "ok": True,
        "data": {"cwd": _cwd},
    })


def _resolve_cd(dest: str) -> str | None:
    """Resolve a ``cd`` destination relative to ``_cwd``.

    Returns the resolved absolute path, or ``None`` if the path does not
    exist or is not a directory.
    """
    global _cwd
    dest = dest.strip()
    if not dest or dest == "~":
        resolved = os.path.expanduser("~")
    elif dest.startswith("~"):
        resolved = os.path.expanduser(dest)
    elif dest.startswith("/"):
        resolved = dest
    else:
        resolved = os.path.normpath(os.path.join(_cwd, dest))
    if os.path.isdir(resolved):
        _cwd = resolved
        return _cwd
    return None


async def terminal_exec(request: Request) -> Response:
    """POST /api/v1/terminal/exec

    Body
    ----
    .. code-block:: json

        { "command": "string", "timeout": 30 }

    Built-in commands
    -----------------
    ``help`` / ``?``
        Returns the full categorized command reference as ``stdout``.
    ``clear``
        Clears the terminal (returns ``"action": "clear"``).
    ``cd <path>``
        Changes the server-side current working directory (``_cwd``).
        Returns the new ``cwd`` in the response so the frontend can
        update its prompt.

    Everything else is forwarded to :func:`safe_subprocess_run` with
    ``cwd=_cwd`` so that the working directory persists across commands.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    command_input: str | list[str] | None = body.get("command")
    if not command_input:
        raise ApiError(400, "Missing required field: command")

    # Normalise to a stripped string.
    raw = command_input.strip() if isinstance(command_input, str) else " ".join(command_input).strip()
    raw_lower = raw.lower()

    # ── Built-in: help ────────────────────────────────────────────────
    if raw_lower in ("help", "?"):
        return json_response({
            "ok": True,
            "data": {
                "returncode": 0,
                "stdout": _build_help_text(),
                "stderr": "",
                "command": raw,
                "cwd": _cwd,
            },
        })

    # ── Built-in: clear ───────────────────────────────────────────────
    if raw_lower in ("clear", "cls"):
        return json_response({
            "ok": True,
            "data": {
                "action": "clear",
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "command": raw,
                "cwd": _cwd,
            },
        })

    # ── Built-in: cd (server-side directory tracking) ─────────────────
    if raw_lower.startswith("cd "):
        dest = raw[3:].strip()
        if not dest or dest == "~":
            _resolve_cd("~")
            return json_response({
                "ok": True,
                "data": {
                    "returncode": 0,
                    "stdout": "",
                    "stderr": "",
                    "command": raw,
                    "cwd": _cwd,
                },
            })
        elif dest == "-":
            # cd - is not tracked; just no-op
            return json_response({
                "ok": True,
                "data": {
                    "returncode": 0,
                    "stdout": _cwd,
                    "stderr": "",
                    "command": raw,
                    "cwd": _cwd,
                },
            })
        else:
            resolved = _resolve_cd(dest)
            if resolved is None:
                # Directory does not exist — let the shell try so the
                # user gets the proper error message.
                try:
                    args = shlex.split(raw)
                except ValueError:
                    args = raw.split()
                completed = safe_subprocess_run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=_cwd,
                )
                return json_response({
                    "ok": True,
                    "data": {
                        "returncode": completed.returncode,
                        "stdout": completed.stdout or "",
                        "stderr": completed.stderr or "",
                        "command": raw,
                        "cwd": _cwd,
                    },
                })
            return json_response({
                "ok": True,
                "data": {
                    "returncode": 0,
                    "stdout": "",
                    "stderr": "",
                    "command": raw,
                    "cwd": _cwd,
                },
            })

    # ── Built-in: pwd (return tracked directory) ──────────────────────
    if raw_lower == "pwd":
        return json_response({
            "ok": True,
            "data": {
                "returncode": 0,
                "stdout": _cwd + "\n",
                "stderr": "",
                "command": raw,
                "cwd": _cwd,
            },
        })

    # ── Shell execution ───────────────────────────────────────────────
    timeout = min(float(body.get("timeout", 30)), 120)

    # Split into args for safe_subprocess_run.
    try:
        args: list[str] = shlex.split(raw)
    except ValueError:
        args = raw.split()

    try:
        completed = safe_subprocess_run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=_cwd,
        )
        return json_response({
            "ok": True,
            "data": {
                "returncode": completed.returncode,
                "stdout": completed.stdout or "",
                "stderr": completed.stderr or "",
                "command": raw,
                "cwd": _cwd,
            },
        })
    except ShellCommandError as exc:
        raise ApiError(403, str(exc)) from exc
    except Exception as exc:
        logger.exception("Terminal exec failed")
        raise ApiError(500, str(exc)) from exc


async def terminal_autocomplete(request: Request) -> Response:
    """POST /api/v1/terminal/autocomplete

    Body
    ----
    .. code-block:: json

        { "partial": "p" }

    Returns matching command base-names.
    """
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    partial = (body.get("partial") or "").strip()
    matches = _find_autocomplete_matches(partial)

    return json_response({
        "ok": True,
        "data": {
            "partial": partial,
            "matches": matches,
        },
    })


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
