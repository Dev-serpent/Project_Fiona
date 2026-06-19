"""Key rotation and identity management for CamComs."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from CamComs.encryption import CamComsIdentity
from CamComs.pairing import compute_fingerprint
from CamComs.paths import ensure_private_permissions


DEFAULT_IDENTITY_PATH = Path.home() / ".config" / "fiona" / "identity.json"
DEFAULT_PUBKEY_PATH = Path.home() / ".config" / "fiona" / "identity.pub"


def rotate_keys(
    identity_path: Path = DEFAULT_IDENTITY_PATH,
    pubkey_path: Path = DEFAULT_PUBKEY_PATH,
    device_id: str = "host",
) -> tuple[str, str]:
    """Rotate keys for the host identity.

    Loads the existing identity from *identity_path* (if any), generates a
    new key pair, saves the new private key atomically (temp file + rename),
    and exports the new public key bundle to *pubkey_path*.

    Returns (*old_fingerprint*, *new_fingerprint*).
    """
    old_fingerprint: str
    if identity_path.exists():
        data = json.loads(identity_path.read_text(encoding="utf-8"))
        old_identity = CamComsIdentity.from_private_dict(data)
        old_fingerprint = compute_fingerprint(old_identity.public_bundle)
    else:
        old_fingerprint = "(none)"

    new_identity = CamComsIdentity.generate(device_id)
    new_fingerprint = compute_fingerprint(new_identity.public_bundle)

    # ── Save private key atomically ─────────────────────────────────────
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        dir=identity_path.parent,
        delete=False,
        suffix=".tmp",
        prefix="identity_",
    )
    try:
        json.dump(new_identity.to_private_dict(), tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp.close()
        Path(tmp.name).rename(identity_path)
        ensure_private_permissions(identity_path)
    finally:
        leftover = Path(tmp.name)
        if leftover.exists():
            leftover.unlink()

    # ── Export public key bundle atomically ─────────────────────────────
    pubkey_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_pub = tempfile.NamedTemporaryFile(
        mode="w",
        dir=pubkey_path.parent,
        delete=False,
        suffix=".tmp",
        prefix="identity_pub_",
    )
    try:
        json.dump(new_identity.public_bundle.to_dict(), tmp_pub, indent=2, sort_keys=True)
        tmp_pub.write("\n")
        tmp_pub.close()
        Path(tmp_pub.name).rename(pubkey_path)
        ensure_private_permissions(pubkey_path)
    finally:
        leftover_pub = Path(tmp_pub.name)
        if leftover_pub.exists():
            leftover_pub.unlink()

    return old_fingerprint, new_fingerprint


def load_identity(
    identity_path: Path = DEFAULT_IDENTITY_PATH,
) -> CamComsIdentity | None:
    """Load the local identity from *identity_path*.

    Returns ``None`` if the file does not exist or cannot be parsed.
    """
    if not identity_path.exists():
        return None
    try:
        data = json.loads(identity_path.read_text(encoding="utf-8"))
        return CamComsIdentity.from_private_dict(data)
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def get_fingerprint(
    identity: CamComsIdentity | None = None,
    identity_path: Path = DEFAULT_IDENTITY_PATH,
) -> str:
    """Return the fingerprint for a given identity (or load from disk).

    Falls back to *identity_path* if *identity* is ``None``.
    Returns ``"(no identity)"`` if no identity is available.
    """
    if identity is None:
        identity = load_identity(identity_path)
    if identity is None:
        return "(no identity)"
    return compute_fingerprint(identity.public_bundle)
