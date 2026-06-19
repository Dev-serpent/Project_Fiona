from __future__ import annotations

import logging
import os
import stat
from pathlib import Path


logger = logging.getLogger(__name__)

DEFAULT_CAMCOMS_DIR = Path.home() / ".config" / "fiona" / "camcoms"


def private_key_path(device_id: str) -> Path:
    return DEFAULT_CAMCOMS_DIR / f"{device_id}.private.json"


def public_key_path(device_id: str) -> Path:
    return DEFAULT_CAMCOMS_DIR / f"{device_id}.public.json"


def ensure_camcoms_dir() -> Path:
    DEFAULT_CAMCOMS_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_CAMCOMS_DIR


def ensure_private_permissions(path: Path, *, mode: int = 0o600) -> None:
    """Set restrictive file permissions on a private key file.

    On Unix, this sets the mode to the specified value (default 0o600).
    On Windows, this is a no-op.
    Silently skips if the file doesn't exist.
    Logs a warning if the permissions could not be changed.
    """
    if os.name != "posix":
        return
    if not path.exists():
        return
    try:
        path.chmod(mode)
    except OSError:
        logger.warning("Could not set permissions %o on %s", mode, path)


def ensure_private_directory_permissions(path: Path, *, mode: int = 0o700) -> None:
    """Set restrictive directory permissions.

    Same cross-platform behavior as ensure_private_permissions.
    """
    if os.name != "posix":
        return
    if not path.is_dir():
        return
    try:
        path.chmod(mode)
    except OSError:
        logger.warning("Could not set directory permissions %o on %s", mode, path)


def check_private_permissions(path: Path, *, expected_mode: int = 0o600) -> bool:
    """Check if a file has the expected restrictive permissions.

    Returns True if permissions are correct or on Windows.
    Returns False and logs a warning if permissions are too permissive.
    """
    if os.name != "posix":
        return True
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return True  # File doesn't exist — nothing to check
    current = stat.S_IMODE(st.st_mode)
    extra_bits = current & ~expected_mode
    if extra_bits != 0:
        logger.warning(
            "Permissions on %s are %o, expected %o or tighter (extra bits: %o)",
            path,
            current,
            expected_mode,
            extra_bits,
        )
        return False
    return True
