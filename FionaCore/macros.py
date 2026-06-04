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

    def to_dict(self) -> dict[str, str]:
        return {"action": self.action}


def load_macros(path: Path = DEFAULT_MACROS_PATH) -> dict[str, list[MacroStep]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    macros: dict[str, list[MacroStep]] = {}
    for name, steps in data.items():
        if isinstance(name, str) and isinstance(steps, list):
            macros[name] = [MacroStep(str(step["action"])) for step in steps if isinstance(step, dict) and "action" in step]
    return macros


def save_macro(name: str, steps: list[MacroStep], path: Path = DEFAULT_MACROS_PATH) -> Path:
    macros = load_macros(path)
    macros[name] = steps
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, list[dict[str, str]]] = {
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
