from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_TRACE_PATH = Path.home() / ".config" / "fiona" / "cmdtrace.jsonl"


def append_trace(event: dict[str, Any], path: Path = DEFAULT_TRACE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def read_trace(*, action_name: str | None = None, limit: int = 50, path: Path = DEFAULT_TRACE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        if len(events) >= limit:
            break
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            if action_name and event.get("action") != action_name:
                continue
            events.append(event)
    return list(reversed(events))


def clear_trace(path: Path = DEFAULT_TRACE_PATH) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True
