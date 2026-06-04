from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_RECALL_PATH = Path.home() / ".config" / "fiona" / "recallvault.json"


@dataclass(frozen=True)
class RecallEntry:
    key: str
    value: str
    category: str = "general"
    created_at: str = ""

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        data["created_at"] = self.created_at or datetime.now(timezone.utc).isoformat()
        return data


def load_recall(path: Path = DEFAULT_RECALL_PATH) -> list[RecallEntry]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    entries: list[RecallEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value = item.get("value")
        if isinstance(key, str) and isinstance(value, str):
            entries.append(
                RecallEntry(
                    key=key,
                    value=value,
                    category=str(item.get("category", "general")),
                    created_at=str(item.get("created_at", "")),
                )
            )
    return entries


def remember(key: str, value: str, *, category: str = "general", path: Path = DEFAULT_RECALL_PATH) -> Path:
    entries = [entry for entry in load_recall(path) if entry.key != key]
    entries.append(RecallEntry(key=key, value=value, category=category))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([entry.to_dict() for entry in entries], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def search_recall(query: str = "", *, path: Path = DEFAULT_RECALL_PATH) -> list[RecallEntry]:
    entries = load_recall(path)
    normalized = query.casefold().strip()
    if not normalized:
        return entries
    return [
        entry
        for entry in entries
        if normalized in entry.key.casefold()
        or normalized in entry.value.casefold()
        or normalized in entry.category.casefold()
    ]


def forget(key: str, *, path: Path = DEFAULT_RECALL_PATH) -> bool:
    entries = load_recall(path)
    filtered = [entry for entry in entries if entry.key != key]
    if len(filtered) == len(entries):
        return False
    path.write_text(json.dumps([entry.to_dict() for entry in filtered], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def clear_recall(path: Path = DEFAULT_RECALL_PATH) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def list_categories(path: Path = DEFAULT_RECALL_PATH) -> list[str]:
    entries = load_recall(path)
    return sorted(list(set(entry.category for entry in entries)))
