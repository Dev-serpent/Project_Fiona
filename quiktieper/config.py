from __future__ import annotations

import json
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "quiktieper" / "bindings.json"

DEFAULT_CONFIG = {
    "bindings": [
        {
            "name": "brave",
            "keys": ["alt", "b", "r", "v"],
            "cmd": "brave-browser",
        },
        {
            "name": "vs-code",
            "keys": ["alt", "v", "s", "c"],
            "cmd": "code",
        },
        {
            "name": "terminal",
            "keys": ["alt", "t", "e", "r"],
            "cmd": "gnome-terminal",
        },
    ]
}


def ensure_config(path: Path = DEFAULT_CONFIG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    return path


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    config_path = ensure_config(path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for binding in config.get("bindings", []):
        if "cmd" not in binding and "command" in binding:
            binding["cmd"] = binding["command"]
    return config


def save_config(config: dict, path: Path = DEFAULT_CONFIG_PATH) -> Path:
    config_path = ensure_config(path)
    normalized = json.loads(json.dumps(config))
    for binding in normalized.get("bindings", []):
        if "cmd" not in binding and "command" in binding:
            binding["cmd"] = binding["command"]
        binding.pop("command", None)
    config_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return config_path
