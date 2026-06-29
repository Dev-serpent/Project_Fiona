"""CamComs API endpoints.

Wraps the CamComs subsystem for service status, identity, configuration,
audit logs, service lifecycle, trust management, pairing, and key management.
"""

from __future__ import annotations

import json
import logging
import time

from aiohttp.web import Request, Response, json_response

from CamComs import (
    DEFAULT_AUDIT_LOG_PATH,
    DEFAULT_FIONA_CONFIG_PATH,
    DEFAULT_TRUSTED_DIR,
    AuditLog,
    HostService,
    HostServiceConfig,
    PublicKeyBundle,
    get_fingerprint,
    list_trusted_senders,
    load_host_service_config,
    remove_trusted_sender,
    rotate_keys,
    run_user_service_command,
    save_host_service_config,
    save_trusted_sender,
)

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────


def _get_config():
    """Load host service config, returning None if unavailable."""
    try:
        return load_host_service_config(DEFAULT_FIONA_CONFIG_PATH)
    except Exception:
        return None


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


async def camcoms_config_get(_request: Request) -> Response:
    """GET /api/v1/camcoms/config — load CamComs host service configuration."""
    try:
        config = _get_config()
        if config is None:
            return json_response({
                "ok": True,
                "data": {"available": False, "error": "No configuration file found."},
            })
        return json_response({
            "ok": True,
            "data": config.to_dict(),
        })
    except Exception as exc:
        logger.exception("CamComs config get failed")
        return json_response({
            "ok": True,
            "data": {"available": False, "error": str(exc)},
        })


async def camcoms_config_post(request: Request) -> Response:
    """POST /api/v1/camcoms/config — save CamComs configuration.

    Request body (JSON): partial or complete HostServiceConfig fields.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    try:
        # Load existing config to preserve defaults for missing fields
        existing = _get_config()
        current_dict = existing.to_dict() if existing is not None else {}
        current_dict.update(body_data)

        config = HostServiceConfig.from_dict(current_dict)
        save_host_service_config(config, DEFAULT_FIONA_CONFIG_PATH)
        return json_response({
            "ok": True,
            "data": config.to_dict(),
        })
    except Exception as exc:
        logger.exception("CamComs config save failed")
        raise ApiError(500, f"Failed to save config: {exc}")


async def camcoms_logs(request: Request) -> Response:
    """GET /api/v1/camcoms/logs — read audit log entries.

    Query parameters:
        limit (int): max entries to return (default 50).
    """
    try:
        limit_str = request.query.get("limit", "50")
        try:
            limit = max(1, min(int(limit_str), 500))
        except (ValueError, TypeError):
            limit = 50

        log = AuditLog(DEFAULT_AUDIT_LOG_PATH)
        entries = log.read_recent(limit)
        return json_response({
            "ok": True,
            "data": entries,
        })
    except Exception as exc:
        logger.exception("CamComs logs failed")
        return json_response({
            "ok": True,
            "data": [],
            "error": str(exc),
        })


async def camcoms_start(_request: Request) -> Response:
    """POST /api/v1/camcoms/start — start the CamComs host service."""
    try:
        result = run_user_service_command("start")
        return json_response({
            "ok": True,
            "data": {
                "action": "start",
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
        })
    except Exception as exc:
        logger.exception("CamComs start failed")
        raise ApiError(500, f"Failed to start CamComs service: {exc}")


async def camcoms_stop(_request: Request) -> Response:
    """POST /api/v1/camcoms/stop — stop the CamComs host service."""
    try:
        result = run_user_service_command("stop")
        return json_response({
            "ok": True,
            "data": {
                "action": "stop",
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
        })
    except Exception as exc:
        logger.exception("CamComs stop failed")
        raise ApiError(500, f"Failed to stop CamComs service: {exc}")


async def camcoms_restart(_request: Request) -> Response:
    """POST /api/v1/camcoms/restart — restart the CamComs host service."""
    try:
        result = run_user_service_command("restart")
        return json_response({
            "ok": True,
            "data": {
                "action": "restart",
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
        })
    except Exception as exc:
        logger.exception("CamComs restart failed")
        raise ApiError(500, f"Failed to restart CamComs service: {exc}")


async def camcoms_trusted(_request: Request) -> Response:
    """GET /api/v1/camcoms/trusted — list trusted senders."""
    try:
        senders = list_trusted_senders(DEFAULT_TRUSTED_DIR)
        return json_response({
            "ok": True,
            "data": {
                "trusted_dir": str(DEFAULT_TRUSTED_DIR),
                "senders": [s.to_dict() for s in senders],
            },
        })
    except Exception as exc:
        logger.exception("CamComs trusted list failed")
        return json_response({
            "ok": True,
            "data": {"trusted_dir": str(DEFAULT_TRUSTED_DIR), "senders": [], "error": str(exc)},
        })


async def camcoms_trust_add(request: Request) -> Response:
    """POST /api/v1/camcoms/trust/add — add a trusted sender key.

    Request body (JSON):
        public_key (dict): Public key bundle with device_id, encryption_public_key, signing_public_key.
        expires_in_days (int | null): Optional expiry in days.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    public_key_dict = body_data.get("public_key")
    if not public_key_dict or not isinstance(public_key_dict, dict):
        raise ApiError(400, "Missing or invalid required field: public_key")

    try:
        bundle = PublicKeyBundle.from_dict(public_key_dict)
    except Exception as exc:
        raise ApiError(400, f"Invalid public key bundle: {exc}")

    expires_in_days = body_data.get("expires_in_days")
    expires_at = None
    if expires_in_days is not None:
        expires_at = int(time.time()) + int(expires_in_days) * 86400

    try:
        path = save_trusted_sender(bundle, DEFAULT_TRUSTED_DIR, expires_at=expires_at)
        return json_response({
            "ok": True,
            "data": {
                "device_id": bundle.device_id,
                "path": str(path),
                "expires_at": expires_at,
            },
        })
    except Exception as exc:
        logger.exception("CamComs trust add failed")
        raise ApiError(500, f"Failed to add trusted sender: {exc}")


async def camcoms_trust_remove(request: Request) -> Response:
    """POST /api/v1/camcoms/trust/remove — remove a trusted sender.

    Request body (JSON):
        device_id (str): Device ID to remove from trusted senders.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    device_id = body_data.get("device_id")
    if not device_id or not isinstance(device_id, str):
        raise ApiError(400, "Missing or invalid required field: device_id")

    try:
        removed = remove_trusted_sender(device_id, DEFAULT_TRUSTED_DIR)
        return json_response({
            "ok": True,
            "data": {"device_id": device_id, "removed": removed},
        })
    except Exception as exc:
        logger.exception("CamComs trust remove failed")
        raise ApiError(500, f"Failed to remove trusted sender: {exc}")


async def camcoms_pairing_status(_request: Request) -> Response:
    """GET /api/v1/camcoms/pairing/status — get pairing status."""
    try:
        senders = list_trusted_senders(DEFAULT_TRUSTED_DIR)
        return json_response({
            "ok": True,
            "data": {
                "trusted_dir": str(DEFAULT_TRUSTED_DIR),
                "trusted_dir_exists": DEFAULT_TRUSTED_DIR.is_dir(),
                "paired_device_count": len(senders),
                "paired_devices": [s.bundle.device_id for s in senders],
            },
        })
    except Exception as exc:
        logger.exception("CamComs pairing status failed")
        return json_response({
            "ok": True,
            "data": {
                "trusted_dir": str(DEFAULT_TRUSTED_DIR),
                "trusted_dir_exists": DEFAULT_TRUSTED_DIR.is_dir(),
                "paired_device_count": 0,
                "paired_devices": [],
                "error": str(exc),
            },
        })


async def camcoms_keygen(request: Request) -> Response:
    """POST /api/v1/camcoms/keygen — generate new identity keys.

    Request body (JSON):
        device_id (str | null): Optional device ID (default "host").
        confirmed (bool): Must be true to proceed (destructive operation).

    Returns old and new fingerprints.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    if not body_data.get("confirmed"):
        raise ApiError(400, "Key generation requires confirmation (confirmed: true)")

    device_id = body_data.get("device_id", "host")
    if not isinstance(device_id, str):
        raise ApiError(400, "device_id must be a string")

    try:
        old_fp, new_fp = rotate_keys(device_id=device_id)
        return json_response({
            "ok": True,
            "data": {
                "old_fingerprint": old_fp,
                "new_fingerprint": new_fp,
                "device_id": device_id,
            },
        })
    except Exception as exc:
        logger.exception("CamComs keygen failed")
        raise ApiError(500, f"Failed to generate new identity keys: {exc}")
