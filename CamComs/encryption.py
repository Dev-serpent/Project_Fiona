from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import constant_time, hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat


ENVELOPE_VERSION = 1
ENVELOPE_KIND = "camcoms.encrypted"
KEY_INFO = b"fiona.camcoms.v1"
PRIVATE_KEY_INFO = b"fiona.camcoms.private.v1"
PRIVATE_KEY_KDF_ITERATIONS = 390000


class CamComsCryptoError(ValueError):
    """Raised when a CamComs encrypted message cannot be trusted or decoded."""


@dataclass(frozen=True)
class PublicKeyBundle:
    device_id: str
    encryption_public_key: X25519PublicKey
    signing_public_key: Ed25519PublicKey

    def to_dict(self) -> dict[str, str]:
        return {
            "device_id": self.device_id,
            "encryption_public_key": _b64e(
                self.encryption_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
            ),
            "signing_public_key": _b64e(self.signing_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)),
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> PublicKeyBundle:
        return cls(
            device_id=data["device_id"],
            encryption_public_key=X25519PublicKey.from_public_bytes(_b64d(data["encryption_public_key"])),
            signing_public_key=Ed25519PublicKey.from_public_bytes(_b64d(data["signing_public_key"])),
        )


@dataclass(frozen=True)
class CamComsIdentity:
    device_id: str
    encryption_private_key: X25519PrivateKey
    signing_private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls, device_id: str | None = None) -> CamComsIdentity:
        return cls(
            device_id=device_id or str(uuid.uuid4()),
            encryption_private_key=X25519PrivateKey.generate(),
            signing_private_key=Ed25519PrivateKey.generate(),
        )

    @property
    def public_bundle(self) -> PublicKeyBundle:
        return PublicKeyBundle(
            device_id=self.device_id,
            encryption_public_key=self.encryption_private_key.public_key(),
            signing_public_key=self.signing_private_key.public_key(),
        )

    def to_private_dict(self, passphrase: str | None = None) -> dict[str, Any]:
        private_data = {
            "device_id": self.device_id,
            "encryption_private_key": _b64e(
                self.encryption_private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            ),
            "signing_private_key": _b64e(
                self.signing_private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            ),
        }
        if passphrase is None:
            return private_data

        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = _derive_private_key(passphrase, salt)
        payload = json.dumps(private_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {
            "format": "camcoms.private.encrypted.v1",
            "kdf": "PBKDF2HMAC-SHA256",
            "iterations": PRIVATE_KEY_KDF_ITERATIONS,
            "salt": _b64e(salt),
            "nonce": _b64e(nonce),
            "ciphertext": _b64e(AESGCM(key).encrypt(nonce, payload, PRIVATE_KEY_INFO)),
        }

    @classmethod
    def from_private_dict(cls, data: dict[str, Any], passphrase: str | None = None) -> CamComsIdentity:
        if data.get("format") == "camcoms.private.encrypted.v1":
            if passphrase is None:
                raise CamComsCryptoError("passphrase is required for encrypted private keys")
            salt = _b64d(str(data["salt"]))
            nonce = _b64d(str(data["nonce"]))
            ciphertext = _b64d(str(data["ciphertext"]))
            key = _derive_private_key(passphrase, salt)
            try:
                raw = AESGCM(key).decrypt(nonce, ciphertext, PRIVATE_KEY_INFO)
            except Exception as exc:
                raise CamComsCryptoError("private key decryption failed") from exc
            data = json.loads(raw.decode("utf-8"))

        return cls(
            device_id=data["device_id"],
            encryption_private_key=X25519PrivateKey.from_private_bytes(_b64d(data["encryption_private_key"])),
            signing_private_key=Ed25519PrivateKey.from_private_bytes(_b64d(data["signing_private_key"])),
        )


def encrypt_message(
    plaintext: str | bytes,
    *,
    sender: CamComsIdentity,
    recipient: PublicKeyBundle,
    message_type: str = "instruction",
) -> dict[str, Any]:
    raw_plaintext = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    ephemeral_private_key = X25519PrivateKey.generate()
    ephemeral_public_key = ephemeral_private_key.public_key()
    salt = os.urandom(16)
    nonce = os.urandom(12)
    shared_secret = ephemeral_private_key.exchange(recipient.encryption_public_key)
    aes_key = _derive_message_key(shared_secret, salt)

    envelope: dict[str, Any] = {
        "version": ENVELOPE_VERSION,
        "kind": ENVELOPE_KIND,
        "message_id": str(uuid.uuid4()),
        "message_type": message_type,
        "created_at": int(time.time()),
        "sender": sender.device_id,
        "recipient": recipient.device_id,
        "sender_signing_public_key": _b64e(
            sender.signing_private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ),
        "ephemeral_public_key": _b64e(ephemeral_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)),
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
    }
    aad = _canonical_bytes(envelope)
    envelope["ciphertext"] = _b64e(AESGCM(aes_key).encrypt(nonce, raw_plaintext, aad))
    envelope["signature"] = _b64e(sender.signing_private_key.sign(_canonical_bytes(envelope)))
    return envelope


def decrypt_message(
    envelope: dict[str, Any],
    *,
    recipient: CamComsIdentity,
    expected_sender: PublicKeyBundle | None = None,
) -> bytes:
    _validate_envelope_shape(envelope)
    if envelope["recipient"] != recipient.device_id:
        raise CamComsCryptoError("message was not encrypted for this recipient")

    sender_signing_key = Ed25519PublicKey.from_public_bytes(_b64d(envelope["sender_signing_public_key"]))
    if expected_sender is not None:
        if envelope["sender"] != expected_sender.device_id:
            raise CamComsCryptoError("message sender does not match the expected sender")
        expected_key = expected_sender.signing_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        envelope_key = sender_signing_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        if not constant_time.bytes_eq(expected_key, envelope_key):
            raise CamComsCryptoError("message signing key does not match the expected sender")

    signature = _b64d(envelope["signature"])
    signed_payload = dict(envelope)
    del signed_payload["signature"]
    try:
        sender_signing_key.verify(signature, _canonical_bytes(signed_payload))
    except InvalidSignature as exc:
        raise CamComsCryptoError("message signature is invalid") from exc

    ephemeral_public_key = X25519PublicKey.from_public_bytes(_b64d(envelope["ephemeral_public_key"]))
    shared_secret = recipient.encryption_private_key.exchange(ephemeral_public_key)
    aes_key = _derive_message_key(shared_secret, _b64d(envelope["salt"]))
    aad_payload = dict(signed_payload)
    ciphertext = _b64d(aad_payload.pop("ciphertext"))

    try:
        return AESGCM(aes_key).decrypt(_b64d(envelope["nonce"]), ciphertext, _canonical_bytes(aad_payload))
    except Exception as exc:
        raise CamComsCryptoError("message decryption failed") from exc


def decrypt_text(
    envelope: dict[str, Any],
    *,
    recipient: CamComsIdentity,
    expected_sender: PublicKeyBundle | None = None,
) -> str:
    return decrypt_message(envelope, recipient=recipient, expected_sender=expected_sender).decode("utf-8")


def _derive_message_key(shared_secret: bytes, salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=KEY_INFO,
    ).derive(shared_secret)


def _derive_private_key(passphrase: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PRIVATE_KEY_KDF_ITERATIONS,
    ).derive(passphrase.encode("utf-8"))


def _validate_envelope_shape(envelope: dict[str, Any]) -> None:
    required = {
        "version",
        "kind",
        "message_id",
        "message_type",
        "created_at",
        "sender",
        "recipient",
        "sender_signing_public_key",
        "ephemeral_public_key",
        "salt",
        "nonce",
        "ciphertext",
        "signature",
    }
    missing = required.difference(envelope)
    if missing:
        raise CamComsCryptoError(f"encrypted message is missing fields: {', '.join(sorted(missing))}")
    if envelope["version"] != ENVELOPE_VERSION or envelope["kind"] != ENVELOPE_KIND:
        raise CamComsCryptoError("encrypted message uses an unsupported envelope version")


def _canonical_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _b64d(encoded: str) -> bytes:
    return base64.urlsafe_b64decode(encoded.encode("ascii"))
