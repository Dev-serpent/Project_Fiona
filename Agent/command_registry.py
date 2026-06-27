from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from QuikTieper.config import DEFAULT_CONFIG_PATH, load_config


DEFAULT_ALLOWED_ACTIONS = frozenset({
    "press", "click", "move", "launch_binding", "text", "macro",
    "seeondesk_list", "seeondesk_active", "seeondesk_analyze",
    "dataclient_mine", "recall_remember", "recall_search",
    "fiona_status",
    "browser_status", "browser_navigate", "browser_click",
    "browser_type", "browser_screenshot",
    "sciretrieval_query",
})


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
        description="Press a key chord (e.g. ['ctrl', 'c']) through the local automation backend.",
        input_schema={"keys": ["alt", "s"]},
    ),
    CommandSpec(
        name="click",
        category="pointer",
        description="Click a mouse button (left, right, middle), optionally at coordinates.",
        input_schema={"button": "left", "x": 100, "y": 100},
    ),
    CommandSpec(
        name="move",
        category="pointer",
        description="Move the pointer to absolute screen coordinates.",
        input_schema={"x": 100, "y": 100},
    ),
    CommandSpec(
        name="text",
        category="input",
        description="Type a string of text through the local automation backend.",
        input_schema={"value": "hello"},
        requires_confirmation=True,
    ),
    CommandSpec(
        name="launch_binding",
        category="app",
        description="Launch an application by its Fiona binding name.",
        input_schema={"name": "terminal"},
    ),
    CommandSpec(
        name="macro",
        category="automation",
        description="Run a sequence of Fiona action steps.",
        input_schema={
            "steps": [{"type": "press", "keys": ["alt", "s"]}],
        },
        requires_confirmation=True,
    ),
    CommandSpec(
        name="seeondesk_list",
        category="awareness",
        description="List all currently open windows and their titles.",
        input_schema={},
    ),
    CommandSpec(
        name="seeondesk_active",
        category="awareness",
        description="Get detailed information about the currently focused window.",
        input_schema={},
    ),
    CommandSpec(
        name="seeondesk_analyze",
        category="vision",
        description="Capture the screen and use vision AI to describe it. Use this to 'see' what is happening.",
        input_schema={"prompt": "What is visible on the screen?"},
    ),
    CommandSpec(
        name="dataclient_mine",
        category="research",
        description="Search the web for a topic and save summarized results to a CSV.",
        input_schema={"topic": "current weather", "out": "research.csv", "max_links": 3},
    ),
    CommandSpec(
        name="recall_remember",
        category="memory",
        description="Persistently remember a fact, snippet, or note.",
        input_schema={"key": "my_favorite_color", "value": "blue", "category": "personal"},
    ),
    CommandSpec(
        name="recall_search",
        category="memory",
        description="Search persistent memories by keyword or query.",
        input_schema={"query": "favorite"},
    ),
    CommandSpec(
        name="fiona_status",
        category="system",
        description="Get an overview of Fiona's subsystem statuses.",
        input_schema={},
    ),
    # Browser automation
    CommandSpec(
        name="browser_status",
        category="browser",
        description="Show the current state of the browser automation engine.",
        input_schema={},
    ),
    CommandSpec(
        name="browser_navigate",
        category="browser",
        description="Navigate the browser to a given URL.",
        input_schema={"url": "https://example.com"},
    ),
    CommandSpec(
        name="browser_click",
        category="browser",
        description="Click an element on the page by CSS selector.",
        input_schema={"selector": "#submit-button"},
    ),
    CommandSpec(
        name="browser_type",
        category="browser",
        description="Type text into an input element by CSS selector.",
        input_schema={"selector": "#search-box", "text": "hello world"},
    ),
    CommandSpec(
        name="browser_screenshot",
        category="browser",
        description="Capture a screenshot of the current browser page.",
        input_schema={},
    ),
    # Scientific retrieval
    CommandSpec(
        name="sciretrieval_query",
        category="research",
        description="Query scientific databases (NCBI, PubChem, NIST) for chemical, biological, or physical data.",
        input_schema={
            "query": "The scientific question to research (e.g., 'What is the molecular weight of Aspirin?')"
        },
    ),
)


def command_registry(
    config_path: Path = DEFAULT_CONFIG_PATH,
    enforcer: Any | None = None,  # Agent.permission.PermissionEnforcer | None
) -> dict[str, Any]:
    """Return available commands and apps.

    If *enforcer* is provided (a :class:`Agent.permission.PermissionEnforcer`),
    only commands the active personality is allowed to use are returned.
    When *enforcer* is ``None`` (the default) behaviour is identical to the
    original implementation.
    """
    commands = []
    for spec in DEFAULT_COMMANDS:
        if spec.name not in DEFAULT_ALLOWED_ACTIONS:
            continue
        if enforcer is not None and not enforcer.check_tool(spec.name):
            continue
        commands.append(spec.to_dict())
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
