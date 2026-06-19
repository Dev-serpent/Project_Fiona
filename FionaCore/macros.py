from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .actions import ActionResult, ActionRouter

DEFAULT_MACROS_PATH = Path.home() / ".config" / "fiona" / "macros.json"


@dataclass(frozen=True)
class MacroStep:
    action: str
    # Wait support
    wait_type: str | None = None  # "sleep", "wait_for_window", "wait_for_process", None
    wait_value: str | None = None  # e.g. "2000" (ms), "Brave", "python3"
    # Condition support
    condition_type: str | None = None  # "window_active", "process_running", "action_result", None
    condition_value: str | None = None  # e.g. "Brave", "python3", "host.status:ok"
    # Branching
    fallback_action: str | None = None  # Run this if condition is False

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"action": self.action}
        if self.wait_type is not None:
            d["wait_type"] = self.wait_type
            d["wait_value"] = self.wait_value
        if self.condition_type is not None:
            d["condition_type"] = self.condition_type
            d["condition_value"] = self.condition_value
        if self.fallback_action is not None:
            d["fallback_action"] = self.fallback_action
        return d

    @classmethod
    def from_dict(cls, data: dict) -> MacroStep:
        return cls(
            action=str(data.get("action", "")),
            wait_type=data.get("wait_type"),
            wait_value=data.get("wait_value"),
            condition_type=data.get("condition_type"),
            condition_value=data.get("condition_value"),
            fallback_action=data.get("fallback_action"),
        )


def load_macros(path: Path = DEFAULT_MACROS_PATH) -> dict[str, list[MacroStep]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    macros: dict[str, list[MacroStep]] = {}
    for name, steps in data.items():
        if isinstance(name, str) and isinstance(steps, list):
            macros[name] = [MacroStep.from_dict(step) for step in steps if isinstance(step, dict) and "action" in step]
    return macros


def save_macro(name: str, steps: list[MacroStep], path: Path = DEFAULT_MACROS_PATH) -> Path:
    macros = load_macros(path)
    macros[name] = steps
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, list[dict[str, Any]]] = {
        macro_name: [step.to_dict() for step in macro_steps] for macro_name, macro_steps in sorted(macros.items())
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_macro(
    name: str,
    *,
    router: ActionRouter | None = None,
    path: Path = DEFAULT_MACROS_PATH,
    dry_run: bool = False,
    source: str = "macro",
) -> list[ActionResult]:
    router = router or ActionRouter()
    macros = load_macros(path)
    if name not in macros:
        raise ValueError(f"unknown macro: {name}")
    return [router.run(step.action, source=source, dry_run=dry_run) for step in macros[name]]
