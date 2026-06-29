from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .actions import ActionResult, ActionRouter

DEFAULT_MACROS_PATH = Path.home() / ".config" / "fiona" / "macros.json"

# Reserved key used to store per-macro metadata (shortcuts, etc.)
_METADATA_KEY = "_fiona_meta"


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


def _parse_steps(value: Any) -> list[MacroStep]:
    """Parse steps from either a list (old format) or a dict with 'steps' key (new format)."""
    if isinstance(value, list):
        return [
            MacroStep.from_dict(step)
            for step in value
            if isinstance(step, dict) and "action" in step
        ]
    if isinstance(value, dict) and "steps" in value:
        return [
            MacroStep.from_dict(step)
            for step in value["steps"]
            if isinstance(step, dict) and "action" in step
        ]
    return []


def _parse_shortcut(value: Any) -> str:
    """Extract shortcut string from a macro entry (new format dict)."""
    if isinstance(value, dict) and isinstance(value.get("shortcut"), str):
        return value["shortcut"]
    return ""


def load_macros(path: Path = DEFAULT_MACROS_PATH) -> dict[str, list[MacroStep]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    macros: dict[str, list[MacroStep]] = {}
    for name, value in data.items():
        if name == _METADATA_KEY or not isinstance(name, str):
            continue
        steps = _parse_steps(value)
        if steps:
            macros[name] = steps
    return macros


def load_macros_with_meta(
    path: Path = DEFAULT_MACROS_PATH,
) -> tuple[dict[str, list[MacroStep]], dict[str, dict[str, Any]]]:
    """Load macros and their metadata (shortcuts, etc.).

    Returns ``(macros, metadata)`` where *metadata* maps macro name to a dict
    (currently only ``"shortcut"`` may be present).
    """
    if not path.exists():
        return {}, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}, {}
    macros: dict[str, list[MacroStep]] = {}
    metadata: dict[str, dict[str, Any]] = {}

    # Also read any persisted metadata block
    persisted_meta = data.get(_METADATA_KEY, {})
    if isinstance(persisted_meta, dict):
        metadata.update(persisted_meta)

    for name, value in data.items():
        if name == _METADATA_KEY or not isinstance(name, str):
            continue
        steps = _parse_steps(value)
        if steps:
            macros[name] = steps
        # If entry is a dict with shortcut, merge into metadata
        shortcut = _parse_shortcut(value)
        if shortcut:
            meta_entry = metadata.get(name, {})
            meta_entry["shortcut"] = shortcut
            metadata[name] = meta_entry

    return macros, metadata


def _save_payload(
    macros: dict[str, list[MacroStep]],
    metadata: dict[str, dict[str, Any]] | None = None,
    path: Path = DEFAULT_MACROS_PATH,
) -> Path:
    """Write macros (and optional metadata) to the JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    for macro_name, macro_steps in sorted(macros.items()):
        steps_dicts = [step.to_dict() for step in macro_steps]
        entry_meta = (metadata or {}).get(macro_name, {})
        shortcut = entry_meta.get("shortcut", "")
        if shortcut:
            payload[macro_name] = {"steps": steps_dicts, "shortcut": shortcut}
        else:
            payload[macro_name] = steps_dicts

    # Persist metadata block for entries that don't have their own object format
    if metadata:
        filtered_meta = {
            k: v for k, v in metadata.items()
            if k not in macros or not v.get("shortcut")
        }
        if filtered_meta:
            payload[_METADATA_KEY] = filtered_meta

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def save_macro(
    name: str,
    steps: list[MacroStep],
    shortcut: str = "",
    path: Path = DEFAULT_MACROS_PATH,
) -> Path:
    macros, metadata = load_macros_with_meta(path)
    macros[name] = steps
    if shortcut:
        meta = metadata.get(name, {})
        meta["shortcut"] = shortcut
        metadata[name] = meta
    elif name in metadata:
        # Remove shortcut if empty string
        meta = metadata[name]
        meta.pop("shortcut", None)
        if not meta:
            metadata.pop(name, None)
    return _save_payload(macros, metadata, path)


def delete_macro(name: str, path: Path = DEFAULT_MACROS_PATH) -> Path:
    macros, metadata = load_macros_with_meta(path)
    macros.pop(name, None)
    metadata.pop(name, None)
    return _save_payload(macros, metadata, path)


def export_macros_raw(path: Path = DEFAULT_MACROS_PATH) -> dict[str, Any]:
    """Return the raw JSON-decoded contents of the macros file (for export)."""
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def import_macros_raw(data: dict[str, Any], path: Path = DEFAULT_MACROS_PATH) -> Path:
    """Write a raw dict to the macros file (for import).  Overwrites entirely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
