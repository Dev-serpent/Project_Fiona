from __future__ import annotations

import base64
import json
from typing import Any


def encode_envelope(envelope: dict[str, Any]) -> str:
    """Encode an encrypted envelope into a compact ASCII message."""

    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_envelope(encoded_message: str) -> dict[str, Any]:
    """Decode an ASCII message back into an encrypted envelope."""

    raw = base64.urlsafe_b64decode(encoded_message.encode("ascii"))
    envelope = json.loads(raw.decode("utf-8"))
    if not isinstance(envelope, dict):
        raise ValueError("encoded CamComs message did not contain an envelope object")
    return envelope
