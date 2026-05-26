from __future__ import annotations

from pathlib import Path


DEFAULT_CAMCOMS_DIR = Path.home() / ".config" / "fiona" / "camcoms"


def private_key_path(device_id: str) -> Path:
    return DEFAULT_CAMCOMS_DIR / f"{device_id}.private.json"


def public_key_path(device_id: str) -> Path:
    return DEFAULT_CAMCOMS_DIR / f"{device_id}.public.json"


def ensure_camcoms_dir() -> Path:
    DEFAULT_CAMCOMS_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_CAMCOMS_DIR
