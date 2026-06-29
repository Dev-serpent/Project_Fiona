"""HTTP middleware: error handling, CORS, request logging for the Fiona API server."""

from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Awaitable, Callable

from aiohttp.web import (
    HTTPException,
    Request,
    Response,
    StreamResponse,
    middleware,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------

CORS_HEADERS: dict[str, str] = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
    "Access-Control-Allow-Headers": (
        "Content-Type, Authorization, X-Requested-With, Accept, Origin"
    ),
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Max-Age": "86400",
}


@middleware
async def cors_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """Set CORS headers on every response and handle preflight OPTIONS."""
    if request.method == "OPTIONS":
        return Response(status=204, headers=CORS_HEADERS)

    try:
        response = await handler(request)
    except HTTPException as exc:
        for key, value in CORS_HEADERS.items():
            exc.headers[key] = value
        raise

    for key, value in CORS_HEADERS.items():
        response.headers[key] = value
    return response


# ---------------------------------------------------------------------------
# Error handling middleware
# ---------------------------------------------------------------------------


class ApiError(Exception):
    """Structured API error that maps to a JSON error response.

    Attributes:
        status: HTTP status code.
        message: Human-readable error description.
        details: Optional extra context (e.g. validation errors).
    """

    def __init__(
        self,
        status: int = 400,
        message: str = "Bad Request",
        details: object = None,
    ) -> None:
        self.status = status
        self.message = message
        self.details = details
        super().__init__(message)


@middleware
async def error_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """Catch exceptions and return structured JSON error responses."""
    try:
        return await handler(request)
    except ApiError as exc:
        body: dict[str, object] = {"ok": False, "error": {"message": exc.message}}
        if exc.details is not None:
            body["error"]["details"] = exc.details  # type: ignore[attr-defined]
        return Response(
            status=exc.status,
            text=json.dumps(body),
            content_type="application/json",
        )
    except HTTPException as exc:
        # Let redirect responses (3xx) propagate as actual HTTP redirects
        if 300 <= exc.status <= 399:
            raise
        body = {
            "ok": False,
            "error": {
                "message": exc.reason or str(exc.status),
                "status": exc.status,
            },
        }
        return Response(
            status=exc.status,
            text=json.dumps(body),
            content_type="application/json",
        )
    except Exception:
        logger.exception("Unhandled server error")
        return Response(
            status=500,
            text=json.dumps({
                "ok": False,
                "error": {"message": "Internal server error"},
            }),
            content_type="application/json",
        )


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


@middleware
async def logging_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """Log every request with duration."""
    start = time.perf_counter()
    try:
        response = await handler(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "%s %s → %s (%dms)",
            request.method,
            request.path,
            response.status,
            duration_ms,
        )
        return response
    except HTTPException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "%s %s → %s (%dms)",
            request.method,
            request.path,
            exc.status,
            duration_ms,
        )
        raise
