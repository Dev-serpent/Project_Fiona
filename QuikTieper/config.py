from __future__ import annotations

import json
import shlex
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "fiona" / "bindings.json"

DEFAULT_CONFIG = {
    "apps": [
        {
            "name": "brave",
            "window_match": "brave-browser",
            "launch": {
                "name": "launch",
                "keys": ["alt", "b", "r", "v"],
                "cmd": "brave-browser",
            },
            "shortcuts": [
                {
                    "name": "search",
                    "keys": ["alt", "s"],
                    "cmd": "ydotool key 29:1 38:1 38:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "new-tab",
                    "keys": ["alt", "t"],
                    "cmd": "ydotool key 29:1 20:1 20:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "close-tab",
                    "keys": ["alt", "w"],
                    "cmd": "ydotool key 29:1 17:1 17:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "find",
                    "keys": ["alt", "f"],
                    "cmd": "ydotool key 29:1 33:1 33:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "history",
                    "keys": ["alt", "h"],
                    "cmd": "ydotool key 29:1 35:1 35:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "previous-tab",
                    "keys": ["alt", "q"],
                    "cmd": "ydotool key 29:1 42:1 15:1 15:0 42:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "next-tab",
                    "keys": ["alt", "e"],
                    "cmd": "ydotool key 29:1 15:1 15:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "reload",
                    "keys": ["alt", "r"],
                    "cmd": "ydotool key 29:1 19:1 19:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                }
            ],
        },
        {
            "name": "vs-code",
            "window_match": "code",
            "launch": {
                "name": "launch",
                "keys": ["alt", "v", "s", "c"],
                "cmd": "code",
            },
            "shortcuts": [
                {
                    "name": "search",
                    "keys": ["alt", "s"],
                    "cmd": "ydotool key 29:1 42:1 33:1 33:0 42:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "new-file",
                    "keys": ["alt", "t"],
                    "cmd": "ydotool key 29:1 49:1 49:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "close-editor",
                    "keys": ["alt", "w"],
                    "cmd": "ydotool key 29:1 17:1 17:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "find",
                    "keys": ["alt", "f"],
                    "cmd": "ydotool key 29:1 33:1 33:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "explorer",
                    "keys": ["alt", "e"],
                    "cmd": "ydotool key 29:1 42:1 18:1 18:0 42:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                },
                {
                    "name": "command-palette",
                    "keys": ["alt", "p"],
                    "cmd": "ydotool key 29:1 42:1 25:1 25:0 42:0 29:0",
                    "instruction": "",
                    "fiona_cmds": [],
                }
            ],
        },
        {
            "name": "terminal",
            "window_match": "gnome-terminal",
            "launch": {
                "name": "launch",
                "keys": ["alt", "t", "e", "r"],
                "cmd": "gnome-terminal",
            },
            "shortcuts": [],
        },
        {
            "name": "files",
            "window_match": "dolphin",
            "launch": {
                "name": "launch",
                "keys": ["alt", "f", "i", "l"],
                "cmd": "dolphin",
            },
            "shortcuts": [],
        },
    ]
}


def ensure_config(path: Path = DEFAULT_CONFIG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    return path


def infer_window_match(command: str) -> str:
    parts = shlex.split(command)
    if not parts:
        return ""
    return Path(parts[0]).name.lower()


def normalize_binding(binding: dict, default_name: str) -> dict:
    fiona_cmds = binding.get("fiona_cmds", binding.get("quiktieper_cmds", []))
    if isinstance(fiona_cmds, str):
        fiona_cmds = [item.strip() for item in fiona_cmds.split(",") if item.strip()]
    return {
        "name": binding.get("name", default_name),
        "keys": [key.lower() for key in binding.get("keys", [])],
        "cmd": binding.get("cmd") or binding.get("command", ""),
        "instruction": binding.get("instruction", "").strip(),
        "fiona_cmds": fiona_cmds,
        "cooldown_seconds": float(binding.get("cooldown_seconds", 0.8)),
    }


def normalize_config(config: dict) -> dict:
    if "apps" not in config and "bindings" in config:
        apps: list[dict] = []
        for binding in config.get("bindings", []):
            normalized_launch = normalize_binding(binding, "launch")
            apps.append(
                {
                    "name": binding.get("name", "app"),
                    "window_match": infer_window_match(normalized_launch["cmd"]),
                    "launch": normalized_launch,
                    "shortcuts": [],
                }
            )
        config = {"apps": apps}

    apps: list[dict] = []
    for app in config.get("apps", []):
        name = app.get("name", "app")
        launch = normalize_binding(app.get("launch", {}), "launch")
        shortcuts = [
            normalize_binding(shortcut, shortcut.get("name", "shortcut"))
            for shortcut in app.get("shortcuts", [])
        ]
        window_match = app.get("window_match", "").strip().lower() or infer_window_match(launch["cmd"])
        apps.append(
            {
                "name": name,
                "window_match": window_match,
                "launch": launch,
                "shortcuts": shortcuts,
            }
        )

    return {"apps": apps}


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    config_path = ensure_config(path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return normalize_config(config)


def save_config(config: dict, path: Path = DEFAULT_CONFIG_PATH) -> Path:
    config_path = ensure_config(path)
    normalized = normalize_config(config)
    config_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return config_path
