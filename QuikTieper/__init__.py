"""QuikTieper access layer for Fiona."""

from QuikTieper.bindings import parse_bindings
from QuikTieper.config import DEFAULT_CONFIG_PATH, ensure_config, load_config, save_config
from QuikTieper.launcher import AppLauncher, Binding


def __getattr__(name: str) -> object:
    if name in {"ChordListener", "normalize_key"}:
        from QuikTieper.listener import ChordListener, normalize_key

        values = {
            "ChordListener": ChordListener,
            "normalize_key": normalize_key,
        }
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AppLauncher",
    "Binding",
    "ChordListener",
    "DEFAULT_CONFIG_PATH",
    "ensure_config",
    "load_config",
    "normalize_key",
    "parse_bindings",
    "save_config",
]
