from __future__ import annotations

from pathlib import Path

from CamComs.encryption import PublicKeyBundle
from CamComs.paths import DEFAULT_CAMCOMS_DIR


DEFAULT_TRUSTED_DIR = DEFAULT_CAMCOMS_DIR / "trusted"


def trusted_public_key_path(device_id: str) -> Path:
    return DEFAULT_TRUSTED_DIR / f"{device_id}.public.json"


def save_trusted_sender(bundle: PublicKeyBundle, trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> Path:
    import json

    trusted_dir.mkdir(parents=True, exist_ok=True)
    path = trusted_dir / f"{bundle.device_id}.public.json"
    path.write_text(json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_trusted_sender(device_id: str, trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> PublicKeyBundle:
    import json

    path = trusted_dir / f"{device_id}.public.json"
    return PublicKeyBundle.from_dict(json.loads(path.read_text(encoding="utf-8")))


def find_trusted_sender(device_id: str, trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> PublicKeyBundle | None:
    try:
        return load_trusted_sender(device_id, trusted_dir)
    except (FileNotFoundError, KeyError, ValueError):
        return None


def list_trusted_senders(trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> list[PublicKeyBundle]:
    bundles: list[PublicKeyBundle] = []
    if not trusted_dir.is_dir():
        return bundles
    for path in sorted(trusted_dir.glob("*.public.json")):
        try:
            bundles.append(load_trusted_sender(path.stem.removesuffix(".public"), trusted_dir))
        except (KeyError, ValueError, FileNotFoundError):
            continue
    return bundles


def remove_trusted_sender(device_id: str, trusted_dir: Path = DEFAULT_TRUSTED_DIR) -> bool:
    path = trusted_dir / f"{device_id}.public.json"
    if not path.exists():
        return False
    path.unlink()
    return True
