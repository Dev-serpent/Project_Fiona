"""File system API endpoints with path allow-listing.

Only paths under the project root (or explicit allow-list) are accessible
to prevent directory traversal and accidental system file access.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from aiohttp.web import Request, Response, json_response

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path allow-list configuration
# ---------------------------------------------------------------------------

# Project root — all file operations are restricted to this tree.
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # fionaLocalPages/server/handlers/ -> Fiona/

# Additional allowed directories (resolved to absolute).
ALLOWED_PATHS: list[Path] = [
    PROJECT_ROOT,
    PROJECT_ROOT / "fionaLocalPages",
]

# Config directory for Fiona (for config endpoints that may access ~/.config/fiona/)
FIONA_CONFIG_DIR = Path.home() / ".config" / "fiona"


def _resolve_path(user_path: str) -> Path:
    """Resolve and validate a user-supplied path against the allow-list.

    Returns the resolved absolute path.

    Raises:
        ApiError (403) if the path is outside the allowed tree.
    """
    # Reject absolute paths that are explicitly outside the project.
    resolved = Path(user_path).expanduser().resolve()

    allowed = [p.resolve() for p in ALLOWED_PATHS]

    # Allow ~/.config/fiona/ for config operations
    if FIONA_CONFIG_DIR.exists():
        allowed.append(FIONA_CONFIG_DIR.resolve())

    for base in allowed:
        try:
            resolved.relative_to(base)
            return resolved
        except ValueError:
            continue

    raise ApiError(
        403,
        f"Access denied: path '{user_path}' is outside the allowed directory tree",
    )


# ── Handlers ───────────────────────────────────────────────────────────────


async def file_list(request: Request) -> Response:
    """GET /api/v1/files/list?path=..."""
    raw_path = request.query.get("path", ".")
    try:
        target = _resolve_path(raw_path)
    except ApiError:
        # Fall back to project root if the path is denied.
        target = PROJECT_ROOT

    if not target.exists():
        raise ApiError(404, f"Path does not exist: {raw_path}")
    if not target.is_dir():
        raise ApiError(400, f"Path is not a directory: {raw_path}")

    try:
        entries: list[dict[str, object]] = []
        for child in sorted(target.iterdir()):
            try:
                stat = child.stat()
                entries.append({
                    "name": child.name,
                    "path": str(child.relative_to(PROJECT_ROOT)) if child.is_relative_to(PROJECT_ROOT) else str(child),
                    "type": "directory" if child.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
            except OSError:
                continue
        return json_response({"ok": True, "data": entries})
    except Exception as exc:
        logger.exception("File list failed")
        raise ApiError(500, str(exc)) from exc


async def file_read(request: Request) -> Response:
    """GET /api/v1/files/read?path=..."""
    raw_path = request.query.get("path", "")
    if not raw_path:
        raise ApiError(400, "Missing query parameter: path")

    target = _resolve_path(raw_path)

    if not target.exists():
        raise ApiError(404, f"File does not exist: {raw_path}")
    if not target.is_file():
        raise ApiError(400, f"Path is not a file: {raw_path}")

    # Reject binary files for safety.
    _check_text_file(target)

    try:
        content = target.read_text(encoding="utf-8")
        return json_response({
            "ok": True,
            "data": {"path": str(target), "content": content},
        })
    except Exception as exc:
        logger.exception("File read failed")
        raise ApiError(500, str(exc)) from exc


async def file_write(request: Request) -> Response:
    """POST /api/v1/files/write

    Body: { path, content }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    raw_path: str | None = body.get("path")
    content: str | None = body.get("content")

    if not raw_path:
        raise ApiError(400, "Missing required field: path")
    if content is None:
        raise ApiError(400, "Missing required field: content")

    target = _resolve_path(raw_path)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return json_response({
            "ok": True,
            "data": {"path": str(target)},
        })
    except Exception as exc:
        logger.exception("File write failed")
        raise ApiError(500, str(exc)) from exc


async def file_info(request: Request) -> Response:
    """GET /api/v1/files/info?path=..."""
    raw_path = request.query.get("path", "")
    if not raw_path:
        raise ApiError(400, "Missing query parameter: path")

    target = _resolve_path(raw_path)

    if not target.exists():
        raise ApiError(404, f"Path does not exist: {raw_path}")

    try:
        stat = target.stat()
        return json_response({
            "ok": True,
            "data": {
                "path": str(target),
                "type": "directory" if target.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "permissions": oct(stat.st_mode & 0o777),
                "owner": stat.st_uid,
            },
        })
    except Exception as exc:
        logger.exception("File info failed")
        raise ApiError(500, str(exc)) from exc


# ── File Rename Handler ─────────────────────────────────────────────────────


async def file_rename(request: Request) -> Response:
    """POST /api/v1/files/rename

    Body: { path: str, newName: str }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    raw_path: str | None = body.get("path")
    new_name: str | None = body.get("newName")

    if not raw_path:
        raise ApiError(400, "Missing required field: path")
    if not new_name:
        raise ApiError(400, "Missing required field: newName")
    if "/" in new_name or new_name in (".", ".."):
        raise ApiError(400, "Invalid name: must be a single file or directory name")

    target = _resolve_path(raw_path)

    if not target.exists():
        raise ApiError(404, f"Path does not exist: {raw_path}")

    new_path = target.parent / new_name
    if new_path.exists():
        raise ApiError(409, f"A file or directory named '{new_name}' already exists")

    try:
        target.rename(new_path)
        stat = new_path.stat()
        return json_response({
            "ok": True,
            "data": {
                "name": new_path.name,
                "path": str(new_path),
                "type": "directory" if new_path.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
            },
        })
    except PermissionError:
        raise ApiError(403, f"Permission denied: {raw_path}")
    except OSError as exc:
        logger.exception("File rename failed")
        raise ApiError(500, str(exc))


# ── File Delete Handler ─────────────────────────────────────────────────────


async def file_delete(request: Request) -> Response:
    """DELETE /api/v1/files/delete

    Body: { path: str }
    """
    # Support both JSON body and query parameters for flexibility.
    raw_path: str | None = None
    content_type = request.content_type or ""

    if "json" in content_type:
        try:
            body: dict[str, Any] = await request.json()
            raw_path = body.get("path")
        except Exception:
            raise ApiError(400, "Invalid JSON body")
    else:
        raw_path = request.query.get("path")

    if not raw_path:
        raise ApiError(400, "Missing required field: path")

    target = _resolve_path(raw_path)

    if not target.exists():
        raise ApiError(404, f"Path does not exist: {raw_path}")

    try:
        if target.is_dir():
            contents = list(target.iterdir())
            if contents:
                raise ApiError(
                    400,
                    f"Directory is not empty ({len(contents)} items). "
                    "Refusing to delete non-empty directory for safety.",
                )
            target.rmdir()
        else:
            target.unlink()

        return json_response({
            "ok": True,
            "data": {"path": raw_path, "deleted": True},
        })
    except ApiError:
        raise
    except PermissionError:
        raise ApiError(403, f"Permission denied: {raw_path}")
    except OSError as exc:
        logger.exception("File delete failed")
        raise ApiError(500, str(exc))


# ── Helpers ────────────────────────────────────────────────────────────────


def _check_text_file(path: Path) -> None:
    """Quick binary detection: reject files containing null bytes."""
    try:
        head = path.read_bytes(8192)
        if b"\x00" in head:
            raise ApiError(400, f"Cannot read binary file: {path.name}")
    except ApiError:
        raise
    except Exception:
        pass  # let the caller handle the actual read failure
