"""PhiConnect API endpoints.

Wraps the PhiConnect secure messaging subsystem for identity queries,
message retrieval, sending, and public-key trust management.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aiohttp.web import Request, Response, json_response

import PhiConnect

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_identity_dict(identity: Any) -> dict[str, Any]:
    """Build a serializable dict from a CamComsIdentity.

    The identity object does not expose a direct ``to_dict()``, so we
    assemble the representation from its public attributes.
    """
    return {
        "device_id": identity.device_id,
        "public_bundle": identity.public_bundle.to_dict(),
    }


# ── Handlers ─────────────────────────────────────────────────────────────


async def phiconnect_status(_request: Request) -> Response:
    """GET /api/v1/phiconnect/status — PhiConnect subsystem health.

    Returns:
        JSON with ``ready`` (bool), ``port``, ``config_dir``, and
        ``identity_exists`` fields.
    """
    try:
        config_dir = PhiConnect.DEFAULT_PHICONNECT_DIR
        config_dir_exists = config_dir.exists()

        identity_exists = False
        try:
            PhiConnect.ensure_identity(PhiConnect.PhiConnectConfig())
            identity_exists = True
        except Exception:
            pass

        return json_response({
            "ok": True,
            "data": {
                "ready": config_dir_exists and identity_exists,
                "port": PhiConnect.DEFAULT_PHICONNECT_PORT,
                "config_dir": str(config_dir),
                "identity_exists": identity_exists,
            },
        })
    except Exception as exc:
        logger.exception("PhiConnect status failed")
        raise ApiError(500, str(exc)) from exc


async def phiconnect_identity(_request: Request) -> Response:
    """GET /api/v1/phiconnect/identity — current PhiConnect identity.

    Returns the device identity (device ID and public key bundle) on
    success.  If the identity cannot be loaded, returns a placeholder
    with ``fingerprint`` set to ``"(unavailable)"``.
    """
    try:
        identity = PhiConnect.ensure_identity(PhiConnect.PhiConnectConfig())
        return json_response({
            "ok": True,
            "data": _build_identity_dict(identity),
        })
    except Exception as exc:
        logger.exception("PhiConnect identity failed")
        return json_response({
            "ok": True,
            "data": {
                "fingerprint": "(unavailable)",
                "error": str(exc),
            },
        })


async def phiconnect_messages(request: Request) -> Response:
    """GET /api/v1/phiconnect/messages — recent chat messages.

    Query parameters:
        seconds (int): lookback window in seconds (default 180).

    Returns a list of message dicts parsed from the chat log.
    """
    try:
        seconds_str = request.query.get("seconds", "180")
        try:
            seconds = int(seconds_str)
        except (ValueError, TypeError):
            seconds = 180

        messages = PhiConnect.read_recent_messages(seconds=seconds)
        return json_response({
            "ok": True,
            "data": messages,
        })
    except Exception as exc:
        logger.exception("PhiConnect read messages failed")
        raise ApiError(500, str(exc)) from exc


async def phiconnect_send(request: Request) -> Response:
    """POST /api/v1/phiconnect/send — send a chat message.

    Request body (JSON):
        body (str):        Message text (required).
        host (str | null): Optional target hostname.
        port (int | null): Optional target port.

    Returns the result dict from ``send_chat_message``.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    message_body: str | None = body_data.get("body")
    if not message_body or not isinstance(message_body, str):
        raise ApiError(400, "Missing or invalid required field: body")

    host: str | None = body_data.get("host")
    port_raw: object = body_data.get("port")
    port: int | None = None
    if port_raw is not None:
        try:
            port = int(str(port_raw))
        except (ValueError, TypeError):
            raise ApiError(400, "port must be an integer if provided")

    try:
        config = PhiConnect.PhiConnectConfig()
        result = PhiConnect.send_chat_message(
            message_body,
            config=config,
            host=host,
            port=port,
        )
        return json_response({
            "ok": True,
            "data": result,
        })
    except Exception as exc:
        logger.exception("PhiConnect send failed")
        raise ApiError(502, f"PhiConnect send failed: {exc}") from exc


async def phiconnect_trust_key(request: Request) -> Response:
    """POST /api/v1/phiconnect/trust — trust a peer public key.

    Request body (JSON):
        path (str):        Filesystem path to the public key file (required).
        trusted_dir (str | null): Optional trusted directory override.

    Copies the key into the trusted directory and returns the destination
    path on success.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    path_str: str | None = body_data.get("path")
    if not path_str:
        raise ApiError(400, "Missing required field: path")

    path = Path(path_str)

    trusted_dir_str: str | None = body_data.get("trusted_dir")

    try:
        if trusted_dir_str is not None:
            result_path = PhiConnect.trust_public_key(
                path, trusted_dir=Path(trusted_dir_str),
            )
        else:
            result_path = PhiConnect.trust_public_key(path)
        return json_response({
            "ok": True,
            "data": {"path": str(result_path)},
        })
    except Exception as exc:
        logger.exception("PhiConnect trust key failed")
        raise ApiError(500, str(exc)) from exc
