from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from CamComs.encryption import PublicKeyBundle
from CamComs.paths import DEFAULT_CAMCOMS_DIR, ensure_private_directory_permissions, ensure_private_permissions


DEFAULT_TRUSTED_DIR = DEFAULT_CAMCOMS_DIR / "trusted"


@dataclass(frozen=True)
class TrustedSender:
    """A trusted sender entry with optional expiry."""

    bundle: PublicKeyBundle
    added_at: int  # Unix timestamp
    expires_at: int | None = None  # Unix timestamp, None = no expiry

    def to_dict(self) -> dict:
        result: dict = {
            "version": 2,
            "added_at": self.added_at,
            "expires_at": self.expires_at,
            "bundle": self.bundle.to_dict(),
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> TrustedSender:
        # Detect and support old format (raw PublicKeyBundle dict without "version" key)
        if "version" not in data:
            return cls(
                bundle=PublicKeyBundle.from_dict(data),
                added_at=0,
                expires_at=None,
            )
        return cls(
            bundle=PublicKeyBundle.from_dict(data["bundle"]),
            added_at=data["added_at"],
            expires_at=data.get("expires_at"),
        )


def is_trust_expired(trusted: TrustedSender) -> bool:
    """Check if a trusted sender entry has expired."""
    if trusted.expires_at is None:
        return False
    return time.time() > trusted.expires_at


def prune_expired(trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> list[str]:
    """Remove all expired trusted sender entries. Returns list of removed device IDs."""
    removed: list[str] = []
    for trusted in list_trusted_senders(trusted_dir):
        if is_trust_expired(trusted):
            remove_trusted_sender(trusted.bundle.device_id, trusted_dir)
            removed.append(trusted.bundle.device_id)
    return removed


def trusted_public_key_path(device_id: str) -> Path:
    return DEFAULT_TRUSTED_DIR / f"{device_id}.public.json"


def save_trusted_sender(
    bundle: PublicKeyBundle,
    trusted_dir: Path = DEFAULT_TRUSTED_DIR,
    expires_at: int | None = None,
) -> Path:
    import json

    trust_entry = TrustedSender(
        bundle=bundle,
        added_at=int(time.time()),
        expires_at=expires_at,
    )
    trusted_dir.mkdir(parents=True, exist_ok=True)
    path = trusted_dir / f"{bundle.device_id}.public.json"
    path.write_text(json.dumps(trust_entry.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ensure_private_permissions(path)
    ensure_private_directory_permissions(trusted_dir)
    return path


def load_trusted_sender(device_id: str, trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> TrustedSender:
    import json

    path = trusted_dir / f"{device_id}.public.json"
    return TrustedSender.from_dict(json.loads(path.read_text(encoding="utf-8")))


def find_trusted_sender(device_id: str, trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> TrustedSender | None:
    try:
        return load_trusted_sender(device_id, trusted_dir)
    except (FileNotFoundError, KeyError, ValueError):
        return None


def list_trusted_senders(trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> list[TrustedSender]:
    entries: list[TrustedSender] = []
    if not trusted_dir.is_dir():
        return entries
    for path in sorted(trusted_dir.glob("*.public.json")):
        try:
            entries.append(load_trusted_sender(path.stem.removesuffix(".public"), trusted_dir))
        except (KeyError, ValueError, FileNotFoundError):
            continue
    return entries


def remove_trusted_sender(device_id: str, trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> bool:
    path = trusted_dir / f"{device_id}.public.json"
    if not path.exists():
        return False
    path.unlink()
    return True
