"""PhiConnect API endpoints.

Wraps the PhiConnect secure messaging subsystem for identity queries,
message retrieval, sending, public-key trust management, contact/peer
management, and configuration.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time as time_module
from pathlib import Path
from typing import Any

from aiohttp.web import Request, Response, json_response

import PhiConnect
from CamComs.encryption import PublicKeyBundle
from CamComs.trust import list_trusted_senders, remove_trusted_sender, save_trusted_sender

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────

WEB_CONFIG_PATH = PhiConnect.DEFAULT_PHICONNECT_DIR / "web_config.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "listen_port": PhiConnect.DEFAULT_PHICONNECT_PORT,
    "listen_host": "0.0.0.0",
    "peer_host": "127.0.0.1",
    "peer_port": PhiConnect.DEFAULT_PHICONNECT_PORT,
    "auto_start": False,
    "log_level": "INFO",
}


# ── Helpers ──────────────────────────────────────────────────────────────


def _compute_fingerprint(public_bundle_dict: dict[str, str]) -> str:
    """Compute a SHA-256 fingerprint from a public key bundle dict."""
    canonical = json.dumps(public_bundle_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_identity_dict(identity: Any) -> dict[str, Any]:
    """Build a serializable dict from a CamComsIdentity, including
    a computed SHA-256 fingerprint derived from the public bundle."""
    bundle_dict = identity.public_bundle.to_dict()
    return {
        "device_id": identity.device_id,
        "public_bundle": bundle_dict,
        "fingerprint": _compute_fingerprint(bundle_dict),
    }


def _load_web_config() -> dict[str, Any]:
    """Load persistent web config or return defaults."""
    try:
        if WEB_CONFIG_PATH.exists():
            stored = json.loads(WEB_CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **stored}
    except Exception:
        logger.warning("Failed to load web config, using defaults")
    return dict(DEFAULT_CONFIG)


def _save_web_config(config: dict[str, Any]) -> None:
    """Save web config to disk."""
    WEB_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULT_CONFIG, **config}
    WEB_CONFIG_PATH.write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _trusted_dir() -> Path:
    """Return the current trusted directory from the default config."""
    return PhiConnect.PhiConnectConfig().trusted_dir


def _fingerprint_truncated(fp: str) -> str:
    """Return a short display form of a hex fingerprint."""
    if not fp or fp == "(unavailable)":
        return ""
    if len(fp) <= 16:
        return fp
    return fp[:16] + "..."


# ── Existing Handlers (preserved and enhanced) ────────────────────────────


async def phiconnect_status(_request: Request) -> Response:
    """GET /api/v1/phiconnect/status — PhiConnect subsystem health.

    Returns:
        JSON with ``ready``, ``port``, ``config_dir``,
        ``identity_exists``, and ``trusted_peers`` fields.
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

        trusted_count = 0
        try:
            trusted_count = len(list_trusted_senders(_trusted_dir()))
        except Exception:
            pass

        return json_response({
            "ok": True,
            "data": {
                "ready": config_dir_exists and identity_exists,
                "port": PhiConnect.DEFAULT_PHICONNECT_PORT,
                "config_dir": str(config_dir),
                "identity_exists": identity_exists,
                "trusted_peers": trusted_count,
            },
        })
    except Exception as exc:
        logger.exception("PhiConnect status failed")
        raise ApiError(500, str(exc)) from exc


async def phiconnect_identity(_request: Request) -> Response:
    """GET /api/v1/phiconnect/identity — current PhiConnect identity.

    Returns the device identity (device ID, public key bundle, and
    fingerprint) on success.  If the identity cannot be loaded, returns
    a placeholder with ``fingerprint`` set to ``"(unavailable)"``.
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
        search (str):   optional text to filter message bodies.
        sender (str):   optional sender device ID to filter by.

    Returns a list of message dicts parsed from the chat log.
    """
    try:
        seconds_str = request.query.get("seconds", "180")
        try:
            seconds = int(seconds_str)
        except (ValueError, TypeError):
            seconds = 180

        messages = PhiConnect.read_recent_messages(seconds=seconds)

        # Apply optional filters
        search_text = request.query.get("search", "").strip().lower()
        sender_filter = request.query.get("sender", "").strip()

        if search_text:
            messages = [
                m for m in messages
                if search_text in (m.get("body") or "").lower()
            ]
        if sender_filter:
            messages = [
                m for m in messages
                if m.get("sender") == sender_filter
            ]

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


# ── Trust Key (extended: also accept key_json) ───────────────────────────


async def phiconnect_trust_key(request: Request) -> Response:
    """POST /api/v1/phiconnect/trust — trust a peer public key.

    Request body (JSON):
        path (str):          Filesystem path to the public key file.
        trusted_dir (str):   Optional trusted directory override.

    OR::

        key_json (str):      Raw JSON of the public key bundle to trust.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    trusted_dir_str: str | None = body_data.get("trusted_dir")

    try:
        path_str: str | None = body_data.get("path")
        key_json_str: str | None = body_data.get("key_json")

        if path_str:
            path = Path(path_str)
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
        elif key_json_str:
            bundle = PublicKeyBundle.from_dict(json.loads(key_json_str))
            result_path = save_trusted_sender(
                bundle, _trusted_dir(),
            )
            return json_response({
                "ok": True,
                "data": {
                    "path": str(result_path),
                    "device_id": bundle.device_id,
                },
            })
        else:
            raise ApiError(400, "Missing required field: path or key_json")
    except Exception as exc:
        logger.exception("PhiConnect trust key failed")
        raise ApiError(500, str(exc)) from exc


# ── Peers / Contacts ─────────────────────────────────────────────────────


async def phiconnect_peers_list(_request: Request) -> Response:
    """GET /api/v1/phiconnect/peers — list known peers/contacts.

    Returns trusted senders with fingerprint, added_at, and last_seen
    (derived from chat log).
    """
    try:
        td = _trusted_dir()
        senders = list_trusted_senders(td)

        # Gather last-seen timestamps from chat log (30-day lookback)
        last_seen_map: dict[str, int] = {}
        try:
            messages = PhiConnect.read_recent_messages(seconds=86400 * 30)
            for msg in messages:
                sender = msg.get("sender", "")
                ts = msg.get("timestamp", 0)
                if sender and ts:
                    if sender not in last_seen_map or ts > last_seen_map[sender]:
                        last_seen_map[sender] = int(ts)
        except Exception:
            pass

        now = time_module.time()
        peers = []
        for sender in senders:
            bundle_dict = sender.bundle.to_dict()
            fingerprint = _compute_fingerprint(bundle_dict)
            device_id = sender.bundle.device_id
            peers.append({
                "device_id": device_id,
                "fingerprint": fingerprint,
                "truncated_fingerprint": _fingerprint_truncated(fingerprint),
                "added_at": sender.added_at,
                "expires_at": sender.expires_at,
                "last_seen": last_seen_map.get(device_id),
                "trust_status": "trusted",
                "is_expired": (
                    sender.expires_at is not None and
                    sender.expires_at < now
                ) if sender.expires_at else False,
            })

        return json_response({"ok": True, "data": peers})
    except Exception as exc:
        logger.exception("PhiConnect peers list failed")
        raise ApiError(500, str(exc)) from exc


async def phiconnect_peers_add(request: Request) -> Response:
    """POST /api/v1/phiconnect/peers/add — add a peer by trusting
    their public key.

    Request body (JSON)::
        device_id (str):            Peer device ID.
        public_bundle (dict):       The peer's public key bundle dict.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    public_bundle_data = body_data.get("public_bundle")
    if not public_bundle_data:
        raise ApiError(400, "Missing required field: public_bundle")

    try:
        bundle = PublicKeyBundle.from_dict(public_bundle_data)
    except Exception as exc:
        raise ApiError(400, f"Invalid public bundle: {exc}")

    try:
        result_path = save_trusted_sender(bundle, _trusted_dir())
        return json_response({
            "ok": True,
            "data": {
                "device_id": bundle.device_id,
                "path": str(result_path),
                "fingerprint": _compute_fingerprint(public_bundle_data),
            },
        })
    except Exception as exc:
        logger.exception("PhiConnect peer add failed")
        raise ApiError(500, str(exc)) from exc


async def phiconnect_peers_remove(request: Request) -> Response:
    """DELETE /api/v1/phiconnect/peers/remove — remove a peer/contact.

    Query parameters::
        device_id (str): The device ID of the peer to remove.
    """
    device_id = request.query.get("device_id")
    if not device_id:
        raise ApiError(400, "Missing required query parameter: device_id")

    try:
        removed = remove_trusted_sender(device_id, _trusted_dir())
        return json_response({
            "ok": True,
            "data": {"removed": removed, "device_id": device_id},
        })
    except Exception as exc:
        logger.exception("PhiConnect peer remove failed")
        raise ApiError(500, str(exc)) from exc


# ── Trust Management ──────────────────────────────────────────────────────


async def phiconnect_trust_list(_request: Request) -> Response:
    """GET /api/v1/phiconnect/trust/list — list trusted keys with details.

    Returns full key bundle metadata for trust verification purposes.
    """
    try:
        td = _trusted_dir()
        senders = list_trusted_senders(td)
        now = time_module.time()

        trusted = []
        for sender in senders:
            bundle_dict = sender.bundle.to_dict()
            trusted.append({
                "device_id": sender.bundle.device_id,
                "fingerprint": _compute_fingerprint(bundle_dict),
                "truncated_fingerprint": _fingerprint_truncated(
                    _compute_fingerprint(bundle_dict),
                ),
                "public_bundle": bundle_dict,
                "added_at": sender.added_at,
                "expires_at": sender.expires_at,
                "is_expired": (
                    sender.expires_at is not None and
                    sender.expires_at < now
                ) if sender.expires_at else False,
            })

        return json_response({"ok": True, "data": trusted})
    except Exception as exc:
        logger.exception("PhiConnect trust list failed")
        raise ApiError(500, str(exc)) from exc


async def phiconnect_trust_revoke(request: Request) -> Response:
    """POST /api/v1/phiconnect/trust/revoke — revoke trust for a device.

    Request body (JSON)::
        device_id (str): Device ID to revoke trust for.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    device_id = body_data.get("device_id")
    if not device_id:
        raise ApiError(400, "Missing required field: device_id")

    try:
        removed = remove_trusted_sender(device_id, _trusted_dir())
        return json_response({
            "ok": True,
            "data": {"removed": removed, "device_id": device_id},
        })
    except Exception as exc:
        logger.exception("PhiConnect trust revoke failed")
        raise ApiError(500, str(exc)) from exc


# ── Configuration ─────────────────────────────────────────────────────────


async def phiconnect_get_config(_request: Request) -> Response:
    """GET /api/v1/phiconnect/config — get current PhiConnect configuration."""
    try:
        web_config = _load_web_config()

        identity_info: dict[str, Any] = {}
        try:
            identity = PhiConnect.ensure_identity(PhiConnect.PhiConnectConfig())
            identity_info = _build_identity_dict(identity)
        except Exception:
            pass

        return json_response({
            "ok": True,
            "data": {
                "config": web_config,
                "identity": identity_info,
            },
        })
    except Exception as exc:
        logger.exception("PhiConnect get config failed")
        raise ApiError(500, str(exc)) from exc


async def phiconnect_save_config(request: Request) -> Response:
    """POST /api/v1/phiconnect/config — save PhiConnect configuration.

    Request body (JSON)::
        Fields to update. Valid keys: listen_port, listen_host,
        peer_host, peer_port, auto_start, log_level.
    """
    try:
        body_data = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    valid_keys = {
        "listen_port", "listen_host",
        "peer_host", "peer_port",
        "auto_start", "log_level",
    }
    updates = {k: v for k, v in body_data.items() if k in valid_keys}

    # Validate ports
    for key in ("listen_port", "peer_port"):
        val = updates.get(key)
        if val is not None:
            try:
                port = int(val)
                if port < 1 or port > 65535:
                    raise ApiError(400, f"{key} must be between 1 and 65535")
                updates[key] = port
            except (ValueError, TypeError):
                raise ApiError(400, f"{key} must be an integer")

    try:
        current = _load_web_config()
        current.update(updates)
        _save_web_config(current)

        # Apply log level if it changed
        log_level = current.get("log_level", "INFO")
        logging.getLogger("PhiConnect").setLevel(
            getattr(logging, log_level.upper(), logging.INFO),
        )

        return json_response({
            "ok": True,
            "data": {"config": current, "updated": list(updates.keys())},
        })
    except Exception as exc:
        logger.exception("PhiConnect save config failed")
        raise ApiError(500, str(exc)) from exc


async def phiconnect_regenerate_keys(request: Request) -> Response:
    """POST /api/v1/phiconnect/keys/regenerate — regenerate identity keys.

    WARNING: This invalidates existing trust relationships and makes
    previously encrypted messages undecryptable.
    """
    try:
        config = PhiConnect.PhiConnectConfig()
        if config.private_path.exists():
            config.private_path.unlink()
        if config.public_path.exists():
            config.public_path.unlink()

        identity = PhiConnect.ensure_identity(config)
        return json_response({
            "ok": True,
            "data": _build_identity_dict(identity),
        })
    except Exception as exc:
        logger.exception("PhiConnect regenerate keys failed")
        raise ApiError(500, str(exc)) from exc
