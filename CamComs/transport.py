from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib import request

from CamComs.codec import decode_envelope, encode_envelope
from CamComs.encryption import CamComsIdentity, PublicKeyBundle, encrypt_message
from CamComs.instructions import instruction_from_text, instruction_to_text, press_instruction


DEFAULT_PORT = 8080
DEFAULT_PATH = "/"
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class CamComsHttpClient:
    host: str
    port: int = DEFAULT_PORT
    path: str = DEFAULT_PATH
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @property
    def url(self) -> str:
        clean_path = self.path if self.path.startswith("/") else f"/{self.path}"
        return f"http://{self.host}:{self.port}{clean_path}"

    def send_encoded(self, encoded_message: str) -> str:
        payload = encoded_message.encode("ascii")
        http_request = request.Request(
            self.url,
            data=payload,
            headers={
                "Content-Type": "text/plain; charset=ascii",
                "Accept": "text/plain",
            },
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            return response.read().decode("ascii").strip()

    def send_envelope(self, envelope: dict[str, Any]) -> dict[str, Any]:
        return decode_envelope(self.send_encoded(encode_envelope(envelope)))


def send_encoded_message(
    encoded_message: str,
    *,
    host: str,
    port: int = DEFAULT_PORT,
    path: str = DEFAULT_PATH,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    client = CamComsHttpClient(host=host, port=port, path=path, timeout_seconds=timeout_seconds)
    return client.send_encoded(encoded_message)


def send_envelope(
    envelope: dict[str, Any],
    *,
    host: str,
    port: int = DEFAULT_PORT,
    path: str = DEFAULT_PATH,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    client = CamComsHttpClient(host=host, port=port, path=path, timeout_seconds=timeout_seconds)
    return client.send_envelope(envelope)


def encrypt_and_send_instruction(
    *,
    sender: CamComsIdentity,
    recipient: PublicKeyBundle,
    host: str,
    instruction_json: str | None = None,
    press_keys: list[str] | None = None,
    port: int = DEFAULT_PORT,
    path: str = DEFAULT_PATH,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    if press_keys:
        instruction_text = instruction_to_text(press_instruction(press_keys))
    elif instruction_json is not None:
        instruction_text = instruction_to_text(instruction_from_text(instruction_json))
    else:
        raise ValueError("either instruction_json or press_keys is required")
    envelope = encrypt_message(instruction_text, sender=sender, recipient=recipient)
    return send_encoded_message(
        encode_envelope(envelope),
        host=host,
        port=port,
        path=path,
        timeout_seconds=timeout_seconds,
    )
