from __future__ import annotations

import json
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError

from CamComs.audit import AuditLog
from CamComs.codec import decode_envelope, encode_envelope
from CamComs.encryption import CamComsCryptoError, CamComsIdentity, PublicKeyBundle, decrypt_text, encrypt_message
from CamComs.replay import ReplayGuard
from CamComs.transport import CamComsHttpClient
from CamComs.trust import find_trusted_sender, save_trusted_sender


DEFAULT_PHICONNECT_DIR = Path.home() / ".config" / "fiona" / "phiconnect"
DEFAULT_CHAT_LOG_PATH = DEFAULT_PHICONNECT_DIR / "chat.log"
DEFAULT_TRUSTED_DIR = DEFAULT_PHICONNECT_DIR / "trusted"
DEFAULT_PHICONNECT_PORT = 5000


@dataclass(frozen=True)
class PhiConnectConfig:
    device_id: str = "fiona"
    private_path: Path = DEFAULT_PHICONNECT_DIR / "fiona.private.json"
    public_path: Path = DEFAULT_PHICONNECT_DIR / "fiona.public.json"
    trusted_dir: Path = DEFAULT_TRUSTED_DIR
    chat_log_path: Path = DEFAULT_CHAT_LOG_PATH
    listen_host: str = "0.0.0.0"
    listen_port: int = DEFAULT_PHICONNECT_PORT
    peer_host: str = "127.0.0.1"
    peer_port: int = DEFAULT_PHICONNECT_PORT
    peer_public_path: Path = DEFAULT_PHICONNECT_DIR / "peer.public.json"


class PhiConnectError(ValueError):
    """Raised when a PhiConnect chat message cannot be processed."""


def ensure_identity(config: PhiConnectConfig) -> CamComsIdentity:
    if config.private_path.exists() and config.public_path.exists():
        return CamComsIdentity.from_private_dict(json.loads(config.private_path.read_text(encoding="utf-8")))
    identity = CamComsIdentity.generate(config.device_id)
    config.private_path.parent.mkdir(parents=True, exist_ok=True)
    config.private_path.write_text(json.dumps(identity.to_private_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    config.public_path.write_text(json.dumps(identity.public_bundle.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return identity


def trust_public_key(path: Path, trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> Path:
    bundle = PublicKeyBundle.from_dict(json.loads(path.read_text(encoding="utf-8")))
    return save_trusted_sender(bundle, trusted_dir)


def read_recent_messages(path: Path = DEFAULT_CHAT_LOG_PATH, *, seconds: int = 180) -> list[dict[str, Any]]:
    return AuditLog(path).read_since(seconds=seconds)


def send_chat_message(
    body: str,
    *,
    config: PhiConnectConfig,
    host: str | None = None,
    port: int | None = None,
) -> dict[str, Any]:
    identity = ensure_identity(config)
    if not config.peer_public_path.exists():
        raise PhiConnectError(f"peer public key not found at {config.peer_public_path}; set a peer public key before sending")
    recipient = PublicKeyBundle.from_dict(json.loads(config.peer_public_path.read_text(encoding="utf-8")))
    plaintext = _chat_payload(body, sender=identity.device_id, recipient=recipient.device_id)
    envelope = encrypt_message(
        json.dumps(plaintext, sort_keys=True, separators=(",", ":")),
        sender=identity,
        recipient=recipient,
        message_type="chat",
    )
    encoded = encode_envelope(envelope)
    target_host = host or config.peer_host
    target_port = port or config.peer_port
    try:
        response_text = CamComsHttpClient(host=target_host, port=target_port).send_encoded(encoded)
    except (OSError, URLError) as exc:
        AuditLog(config.chat_log_path).record(
            {
                "direction": "outbound",
                "ok": False,
                "sender": identity.device_id,
                "recipient": recipient.device_id,
                "message_id": envelope["message_id"],
                "body": body,
                "peer": f"{target_host}:{target_port}",
                "error": str(exc),
            }
        )
        raise PhiConnectError(f"could not send to {target_host}:{target_port}; is the PhiConnect receiver running there? {exc}") from exc
    event = {
        "direction": "outbound",
        "ok": True,
        "sender": identity.device_id,
        "recipient": recipient.device_id,
        "message_id": envelope["message_id"],
        "body": body,
        "peer": f"{target_host}:{target_port}",
        "response": response_text,
    }
    AuditLog(config.chat_log_path).record(event)
    return event


class PhiConnectMessageProcessor:
    def __init__(
        self,
        *,
        identity: CamComsIdentity,
        trusted_dir: Path = DEFAULT_TRUSTED_DIR,
        replay_guard: ReplayGuard | None = None,
        chat_log: AuditLog | None = None,
        on_message: Any | None = None,
    ) -> None:
        self.identity = identity
        self.trusted_dir = trusted_dir
        self.replay_guard = replay_guard or ReplayGuard(DEFAULT_PHICONNECT_DIR / "seen_messages.json")
        self.chat_log = chat_log or AuditLog(DEFAULT_CHAT_LOG_PATH)
        self.on_message = on_message

    def process_encoded(self, encoded_message: str) -> dict[str, Any]:
        envelope: dict[str, Any] = {}
        try:
            envelope = decode_envelope(encoded_message.strip())
            if envelope.get("message_type") != "chat":
                raise PhiConnectError("message_type must be chat")
            trusted_sender = find_trusted_sender(str(envelope.get("sender", "")), self.trusted_dir)
            if trusted_sender is None:
                raise PhiConnectError("sender is not trusted")
            self.replay_guard.check_and_record(envelope)
            plaintext = decrypt_text(envelope, recipient=self.identity, expected_sender=trusted_sender)
            message = _validate_chat_payload(json.loads(plaintext))
            event = {
                "direction": "inbound",
                "ok": True,
                "sender": envelope["sender"],
                "recipient": envelope["recipient"],
                "message_id": envelope["message_id"],
                "body": message["body"],
            }
            self.chat_log.record(event)
            if self.on_message:
                try:
                    self.on_message(event)
                except Exception:
                    pass
            return {"ok": True, "message_id": envelope["message_id"], "sender": envelope["sender"]}
        except (CamComsCryptoError, PhiConnectError, ValueError, json.JSONDecodeError) as exc:
            event = {
                "direction": "inbound",
                "ok": False,
                "sender": envelope.get("sender"),
                "recipient": envelope.get("recipient"),
                "message_id": envelope.get("message_id"),
                "error": str(exc),
            }
            self.chat_log.record(event)
            raise


def build_phiconnect_server(config: PhiConnectConfig, on_message: Any | None = None) -> ThreadingHTTPServer:
    identity = ensure_identity(config)
    processor = PhiConnectMessageProcessor(
        identity=identity,
        trusted_dir=config.trusted_dir,
        replay_guard=ReplayGuard(config.chat_log_path.parent / "seen_messages.json"),
        chat_log=AuditLog(config.chat_log_path),
        on_message=on_message,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length).decode("ascii")
            try:
                response = processor.process_encoded(payload)
                status = 200
            except (CamComsCryptoError, PhiConnectError, ValueError, json.JSONDecodeError) as exc:
                response = {"ok": False, "error": str(exc)}
                status = 400
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response, sort_keys=True).encode("utf-8"))

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return ThreadingHTTPServer((config.listen_host, config.listen_port), Handler)


def run_phiconnect_receiver(config: PhiConnectConfig, on_message: Any | None = None) -> None:
    build_phiconnect_server(config, on_message=on_message).serve_forever()


def _chat_payload(body: str, *, sender: str, recipient: str) -> dict[str, Any]:
    payload = {
        "version": 1,
        "type": "chat",
        "created_at": int(time.time()),
        "sender": sender,
        "recipient": recipient,
        "body": body,
    }
    return _validate_chat_payload(payload)


def _validate_chat_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("version") != 1:
        raise PhiConnectError("chat version must be 1")
    if payload.get("type") != "chat":
        raise PhiConnectError("chat type must be chat")
    if not isinstance(payload.get("body"), str) or not payload["body"].strip():
        raise PhiConnectError("chat body must be a non-empty string")
    return payload
