"""CamComs API endpoints.

Wraps the CamComs subsystem for service status and identity queries.
"""

from __future__ import annotations

import logging

from aiohttp.web import Request, Response, json_response

from CamComs import (
    DEFAULT_FIONA_CONFIG_PATH,
    HostService,
    get_fingerprint,
    load_host_service_config,
)

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Handlers ───────────────────────────────────────────────────────────────


async def camcoms_status(_request: Request) -> Response:
    """GET /api/v1/camcoms/status — CamComs service status."""
    try:
        config = load_host_service_config(DEFAULT_FIONA_CONFIG_PATH)
        service = HostService(config)
        status_data = service.status()
        return json_response({
            "ok": True,
            "data": status_data,
        })
    except Exception as exc:
        logger.exception("CamComs status failed")
        # If config doesn't exist, return a descriptive but non-fatal response.
        return json_response({
            "ok": True,
            "data": {
                "ready": False,
                "error": str(exc),
                "config_exists": DEFAULT_FIONA_CONFIG_PATH.exists(),
            },
        })


async def camcoms_identity(_request: Request) -> Response:
    """GET /api/v1/camcoms/identity — current identity fingerprint."""
    try:
        fingerprint = get_fingerprint()
        return json_response({
            "ok": True,
            "data": {"fingerprint": fingerprint},
        })
    except Exception as exc:
        logger.exception("CamComs identity failed")
        return json_response({
            "ok": True,
            "data": {"fingerprint": "(unavailable)", "error": str(exc)},
        })
