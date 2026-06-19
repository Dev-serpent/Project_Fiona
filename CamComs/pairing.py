"""ESP32 pairing protocol for CamComs secure device linking."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from CamComs.encryption import PublicKeyBundle
from CamComs.trust import DEFAULT_TRUSTED_DIR, save_trusted_sender

logger = logging.getLogger(__name__)

PAIRING_REQUEST_TIMEOUT = 120  # seconds before a pending request expires
DEFAULT_PAIRING_PORT = 8090


@dataclass(frozen=True)
class PairingRequest:
    """A pending device pairing request."""

    request_id: str
    device_id: str
    public_bundle: PublicKeyBundle
    received_at: float  # time.monotonic()
    fingerprint: str  # Short visual fingerprint for user verification

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "device_id": self.device_id,
            "public_key": self.public_bundle.to_dict(),
            "fingerprint": self.fingerprint,
        }


def compute_fingerprint(bundle: PublicKeyBundle, length: int = 16) -> str:
    """Compute a short visual fingerprint from the public key bundle.

    Uses the first `length` characters of the base64-encoded encryption public key.
    This is shown to the user to verify the device identity out-of-band.
    """
    return bundle.to_dict()["encryption_public_key"][:length]


class PairingManager:
    """Manages incoming pairing requests and user approval flow."""

    def __init__(self, trusted_dir: Path = DEFAULT_TRUSTED_DIR):
        self.trusted_dir = trusted_dir
        self._pending_requests: dict[str, PairingRequest] = {}

    def submit_request(self, bundle: PublicKeyBundle) -> PairingRequest:
        """Submit a pairing request from a device.

        Returns a PairingRequest that the user must approve.
        Raises ValueError if the device is already trusted.
        """
        # Check if already trusted
        from CamComs.trust import find_trusted_sender

        existing = find_trusted_sender(bundle.device_id, self.trusted_dir)
        if existing is not None:
            raise ValueError(f"Device {bundle.device_id} is already trusted")

        # Prune stale pending requests
        self._prune_stale()

        request = PairingRequest(
            request_id=str(uuid.uuid4()),
            device_id=bundle.device_id,
            public_bundle=bundle,
            received_at=time.monotonic(),
            fingerprint=compute_fingerprint(bundle),
        )
        self._pending_requests[request.request_id] = request
        return request

    def approve_request(
        self, request_id: str, *, expires_in_days: int | None = None
    ) -> bool:
        """Approve a pending pairing request.

        Copies the device's public key to the trust store.
        Returns True if approved, False if request not found or expired.
        """
        request = self._pending_requests.pop(request_id, None)
        if request is None:
            return False

        expires_at = None
        if expires_in_days is not None:
            expires_at = int(time.time()) + expires_in_days * 86400

        save_trusted_sender(
            request.public_bundle,
            self.trusted_dir,
            expires_at=expires_at,
        )
        logger.info(
            "Paired device %s (fingerprint: %s)",
            request.device_id,
            request.fingerprint,
        )
        return True

    def deny_request(self, request_id: str) -> bool:
        """Deny and remove a pending pairing request."""
        return self._pending_requests.pop(request_id, None) is not None

    def get_pending_requests(self) -> list[PairingRequest]:
        """Get list of non-expired pending requests."""
        self._prune_stale()
        return list(self._pending_requests.values())

    def _prune_stale(self) -> None:
        now = time.monotonic()
        stale = [
            rid
            for rid, req in self._pending_requests.items()
            if (now - req.received_at) > PAIRING_REQUEST_TIMEOUT
        ]
        for rid in stale:
            self._pending_requests.pop(rid, None)


def handle_pairing_request_post(
    body: bytes,
    pairing_manager: PairingManager,
) -> dict:
    """Handle an HTTP POST body containing a pairing request.

    Expected body: JSON with {"device_id": "...", "encryption_public_key": "...", "signing_public_key": "..."}
    Returns response dict with ok status and request_id or error.
    """
    try:
        data = json.loads(body.decode("utf-8"))
        bundle = PublicKeyBundle.from_dict(data)
        request = pairing_manager.submit_request(bundle)
        return {
            "ok": True,
            "request_id": request.request_id,
            "fingerprint": request.fingerprint,
        }
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}


# ── Threaded HTTP server for pairing requests ──────────────────────────


class _PairingRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler that accepts POST /pair requests."""

    # The pairing manager is injected via class attribute so the handler can
    # access it without changing the BaseHTTPRequestHandler constructor.
    pairing_manager: PairingManager | None = None

    def do_POST(self) -> None:
        if self.path not in ("/pair", "/pairing", "/"):
            self._send_json({"ok": False, "error": "Not found"}, status=404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        if self.pairing_manager is None:
            self._send_json(
                {"ok": False, "error": "Pairing manager not configured"},
                status=500,
            )
            return

        response = handle_pairing_request_post(body, self.pairing_manager)
        status = 200 if response.get("ok") else 400
        self._send_json(response, status=status)

    def do_GET(self) -> None:
        self._send_json({"ok": True, "service": "fiona-pairing"}, status=200)

    def _send_json(self, payload: dict, *, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload, sort_keys=True).encode("utf-8"))

    def log_message(self, _format: str, *_args: object) -> None:
        return


class PairingHttpServer:
    """Simple threaded HTTP server that listens for ESP32 pairing requests.

    Call ``start()`` to begin listening in a background daemon thread.
    Call ``stop()`` to shut down the server gracefully.
    """

    def __init__(
        self,
        pairing_manager: PairingManager,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PAIRING_PORT,
    ):
        self.host = host
        self.port = port
        self.pairing_manager = pairing_manager
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start the HTTP server in a background daemon thread."""
        if self._server is not None:
            logger.warning("Pairing HTTP server is already running")
            return

        _PairingRequestHandler.pairing_manager = self.pairing_manager

        self._server = ThreadingHTTPServer(
            (self.host, self.port), _PairingRequestHandler
        )
        self._thread = Thread(
            target=self._server.serve_forever,
            name="pairing-http-server",
            daemon=True,
        )
        self._thread.start()
        logger.info("Pairing HTTP server started on %s:%s", self.host, self.port)

    def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server is None:
            return
        self._server.shutdown()
        self._server = None
        self._thread = None
        _PairingRequestHandler.pairing_manager = None
        logger.info("Pairing HTTP server stopped")

    @property
    def is_running(self) -> bool:
        return self._server is not None
