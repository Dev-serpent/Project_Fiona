from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from QuikTieper.config import DEFAULT_CONFIG_PATH, load_config


DEFAULT_ALLOWED_ACTIONS = frozenset({"press", "click", "move", "launch_binding", "text", "macro"})


@dataclass(frozen=True)
class CommandSpec:
    name: str
    category: str
    description: str
    input_schema: dict[str, Any]
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "input_schema": self.input_schema,
            "requires_confirmation": self.requires_confirmation,
        }


DEFAULT_COMMANDS = (
    CommandSpec(
        name="press",
        category="input",
        description="Press a key chord through the local automation backend.",
        input_schema={"version": 1, "type": "press", "keys": ["alt", "s"]},
    ),
    CommandSpec(
        name="click",
        category="pointer",
        description="Click a mouse button, optionally after moving to screen coordinates.",
        input_schema={"version": 1, "type": "click", "button": "left", "x": 100, "y": 100},
    ),
    CommandSpec(
        name="move",
        category="pointer",
        description="Move the pointer to absolute screen coordinates.",
        input_schema={"version": 1, "type": "move", "x": 100, "y": 100},
    ),
    CommandSpec(
        name="text",
        category="input",
        description="Type text through the local automation backend.",
        input_schema={"version": 1, "type": "text", "value": "hello"},
        requires_confirmation=True,
    ),
    CommandSpec(
        name="launch_binding",
        category="app",
        description="Request an app launch by configured Fiona binding name.",
        input_schema={"version": 1, "type": "launch_binding", "name": "terminal"},
    ),
    CommandSpec(
        name="macro",
        category="automation",
        description="Run a sequence of validated Fiona action steps.",
        input_schema={
            "version": 1,
            "type": "macro",
            "steps": [{"version": 1, "type": "press", "keys": ["alt", "s"]}],
        },
        requires_confirmation=True,
    ),
)


def command_registry(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    commands = [spec.to_dict() for spec in DEFAULT_COMMANDS if spec.name in DEFAULT_ALLOWED_ACTIONS]
    return {
        "commands": commands,
        "apps": _available_apps(config_path),
    }


def _available_apps(config_path: Path) -> list[dict[str, str]]:
    if not config_path.exists():
        return []
    try:
        config = load_config(config_path)
    except Exception:
        return []
    apps = []
    for app in config.get("apps", []):
        launch = app.get("launch", {})
        apps.append(
            {
                "name": str(app.get("name", "")),
                "command": str(launch.get("cmd", "")),
            }
        )
    return apps
