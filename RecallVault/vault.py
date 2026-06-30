from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RECALL_PATH = Path.home() / ".config" / "fiona" / "recallvault.json"


@dataclass(frozen=True)
class RecallEntry:
    key: str
    value: str
    category: str = "general"
    created_at: str = ""
    ttl_seconds: int | None = None
    tags: list[str] | None = None
    accessed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at or datetime.now(timezone.utc).isoformat()
        data["accessed_at"] = self.accessed_at or datetime.now(timezone.utc).isoformat()
        # Omit None values for backward compatibility with older files
        if data["ttl_seconds"] is None:
            del data["ttl_seconds"]
        if data["tags"] is None:
            del data["tags"]
        return data


def _is_expired(entry: RecallEntry) -> bool:
    """Return True if the entry has exceeded its TTL."""
    if entry.ttl_seconds is None:
        return False
    if not entry.created_at:
        return False
    try:
        created = datetime.fromisoformat(entry.created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - created).total_seconds()
        return elapsed >= entry.ttl_seconds
    except (ValueError, TypeError):
        return False


def _human_size(size_bytes: int) -> str:
    """Convert byte count to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ("KB", "MB", "GB"):
        size_bytes /= 1024
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
    size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def load_recall(path: Path = DEFAULT_RECALL_PATH) -> list[RecallEntry]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    entries: list[RecallEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value = item.get("value")
        if isinstance(key, str) and isinstance(value, str):
            # Parse tags
            tags = item.get("tags")
            if tags is not None and isinstance(tags, list):
                tags = [str(t) for t in tags if isinstance(t, (str, int, float))]
            else:
                tags = None
            # Parse ttl_seconds
            ttl = item.get("ttl_seconds")
            if ttl is not None:
                try:
                    ttl = int(ttl)
                except (ValueError, TypeError):
                    ttl = None
            entries.append(
                RecallEntry(
                    key=key,
                    value=value,
                    category=str(item.get("category", "general")),
                    created_at=str(item.get("created_at", "")),
                    ttl_seconds=ttl,
                    tags=tags if tags else None,
                    accessed_at=str(item.get("accessed_at", "")),
                )
            )
    # Filter out expired entries
    active = [e for e in entries if not _is_expired(e)]
    # Silently rewrite if expired entries were purged
    if len(active) < len(entries):
        path.write_text(
            json.dumps([entry.to_dict() for entry in active], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return active


def remember(
    key: str,
    value: str,
    *,
    category: str = "general",
    ttl_seconds: int | None = None,
    tags: list[str] | None = None,
    path: Path = DEFAULT_RECALL_PATH,
) -> Path:
    entries = [entry for entry in load_recall(path) if entry.key != key]
    entries.append(
        RecallEntry(
            key=key,
            value=value,
            category=category,
            ttl_seconds=ttl_seconds,
            tags=tags,
            accessed_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([entry.to_dict() for entry in entries], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def search_recall(query: str = "", *, path: Path = DEFAULT_RECALL_PATH) -> list[RecallEntry]:
    entries = load_recall(path)
    normalized = query.casefold().strip()
    if not normalized:
        return entries

    now = datetime.now(timezone.utc).isoformat()
    matched: list[RecallEntry] = []
    updated_entries: list[RecallEntry] = []
    needs_update = False

    for entry in entries:
        is_match = (
            normalized in entry.key.casefold()
            or normalized in entry.value.casefold()
            or normalized in entry.category.casefold()
            or (
                entry.tags
                and any(normalized in tag.casefold() for tag in entry.tags)
            )
        )
        if is_match:
            if entry.accessed_at != now:
                entry = RecallEntry(
                    key=entry.key,
                    value=entry.value,
                    category=entry.category,
                    created_at=entry.created_at,
                    ttl_seconds=entry.ttl_seconds,
                    tags=entry.tags,
                    accessed_at=now,
                )
                needs_update = True
            matched.append(entry)
        updated_entries.append(entry)

    if needs_update:
        path.write_text(
            json.dumps([e.to_dict() for e in updated_entries], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return matched


def forget(key: str, *, path: Path = DEFAULT_RECALL_PATH) -> bool:
    entries = load_recall(path)
    filtered = [entry for entry in entries if entry.key != key]
    if len(filtered) == len(entries):
        return False
    path.write_text(
        json.dumps([entry.to_dict() for entry in filtered], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return True


def clear_recall(path: Path = DEFAULT_RECALL_PATH) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def list_categories(path: Path = DEFAULT_RECALL_PATH) -> list[str]:
    entries = load_recall(path)
    return sorted({entry.category for entry in entries})


def recall_stats(path: Path = DEFAULT_RECALL_PATH) -> dict[str, Any]:
    """Return statistics about the recall vault contents."""
    entries = load_recall(path)
    total = len(entries)

    per_category: dict[str, int] = {}
    per_tag: dict[str, int] = {}
    oldest: tuple[str, str] | None = None
    newest: tuple[str, str] | None = None
    expired_count = 0
    tagged_count = 0

    for entry in entries:
        cat = entry.category
        per_category[cat] = per_category.get(cat, 0) + 1

        if entry.tags:
            tagged_count += 1
            for tag in entry.tags:
                per_tag[tag] = per_tag.get(tag, 0) + 1

        if _is_expired(entry):
            expired_count += 1

        if entry.created_at:
            if oldest is None or entry.created_at < oldest[1]:
                oldest = (entry.key, entry.created_at)
            if newest is None or entry.created_at > newest[1]:
                newest = (entry.key, entry.created_at)

    untagged = total - tagged_count

    try:
        total_bytes = path.stat().st_size if path.exists() else 0
    except OSError:
        total_bytes = 0

    return {
        "total_entries": total,
        "per_category": dict(sorted(per_category.items())),
        "per_tag": dict(sorted(per_tag.items())),
        "total_storage_bytes": total_bytes,
        "total_storage_human": _human_size(total_bytes),
        "oldest_entry": {"key": oldest[0], "created_at": oldest[1]} if oldest else None,
        "newest_entry": {"key": newest[0], "created_at": newest[1]} if newest else None,
        "expired_entries": expired_count,
        "tagged_entries": tagged_count,
        "untagged_entries": untagged,
        "categories": sorted({entry.category for entry in entries}),
    }


def export_recall(
    path: Path = DEFAULT_RECALL_PATH,
    output: Path | None = None,
    fmt: str = "json",
) -> Path:
    """Export all recall entries to a JSON or CSV file.

    Args:
        path: Source vault file path.
        output: Destination path. If None, auto-generate in the same directory.
        fmt: Output format — ``"json"`` (default) or ``"csv"``.

    Returns:
        The path of the created export file.
    """
    entries = load_recall(path)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    if output is None:
        output = path.parent / f"recallvault-export-{timestamp}.{fmt}"

    output.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        output.write_text(
            json.dumps([entry.to_dict() for entry in entries], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    elif fmt == "csv":
        import csv

        with output.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["key", "value", "category", "tags", "created_at", "ttl_seconds"])
            for entry in entries:
                tags_str = ",".join(entry.tags) if entry.tags else ""
                ttl_str = str(entry.ttl_seconds) if entry.ttl_seconds is not None else ""
                writer.writerow([entry.key, entry.value, entry.category, tags_str, entry.created_at, ttl_str])
    else:
        raise ValueError(f"Unsupported export format: {fmt!r}, expected 'json' or 'csv'")

    return output


def import_recall(
    input: Path,  # noqa: A002 — shadowing built-in input per API spec
    path: Path = DEFAULT_RECALL_PATH,
    fmt: str | None = None,
) -> int:
    """Import entries from a JSON or CSV file into the recall vault.

    Merges with existing entries — same key overwrites.

    Args:
        path: Target vault file path.
        input: Source file to import from.
        fmt: Format of the source file. If None, auto-detect from extension.

    Returns:
        Number of entries imported.
    """
    if fmt is None:
        ext = input.suffix.lower()
        if ext == ".json":
            fmt = "json"
        elif ext == ".csv":
            fmt = "csv"
        else:
            raise ValueError(
                f"Could not auto-detect format from extension {ext!r}; "
                "please specify fmt='json' or fmt='csv'"
            )

    existing = load_recall(path)
    existing_keys = {e.key for e in existing}
    imported: list[RecallEntry] = []

    if fmt == "json":
        try:
            data = json.loads(input.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Failed to read JSON file: {e}") from e

        if not isinstance(data, list):
            raise ValueError("JSON file must contain a list of objects")

        for item in data:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            value = item.get("value")
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            # Parse tags
            tags = item.get("tags")
            if tags is not None and isinstance(tags, list):
                tags = [str(t) for t in tags if isinstance(t, (str, int, float))]
            else:
                tags = None
            # Parse ttl
            ttl = item.get("ttl_seconds")
            if ttl is not None:
                try:
                    ttl = int(ttl)
                except (ValueError, TypeError):
                    ttl = None
            imported.append(
                RecallEntry(
                    key=key,
                    value=value,
                    category=str(item.get("category", "general")),
                    created_at=str(item.get("created_at", "")),
                    ttl_seconds=ttl,
                    tags=tags if tags else None,
                    accessed_at=str(item.get("accessed_at", "")),
                )
            )
    elif fmt == "csv":
        import csv

        try:
            with input.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row.get("key") or "").strip()
                    value = (row.get("value") or "").strip()
                    if not key or not value:
                        continue
                    category = (row.get("category") or "general").strip()
                    created_at = (row.get("created_at") or "").strip()
                    # Parse tags from comma-separated string
                    tags_str = (row.get("tags") or "").strip()
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else None
                    # Parse ttl
                    ttl_str = (row.get("ttl_seconds") or "").strip()
                    ttl = int(ttl_str) if ttl_str else None
                    imported.append(
                        RecallEntry(
                            key=key,
                            value=value,
                            category=category,
                            created_at=created_at,
                            ttl_seconds=ttl,
                            tags=tags if tags else None,
                            accessed_at="",
                        )
                    )
        except OSError as e:
            raise ValueError(f"Failed to read CSV file: {e}") from e
    else:
        raise ValueError(f"Unsupported import format: {fmt!r}, expected 'json' or 'csv'")

    if not imported:
        return 0

    # Merge: keep existing entries whose keys aren't being overwritten
    imported_keys = {e.key for e in imported}
    result = [e for e in existing if e.key not in imported_keys]
    result.extend(imported)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([entry.to_dict() for entry in result], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return len(imported)


def backup_recall(path: Path = DEFAULT_RECALL_PATH) -> Path:
    """Create a timestamped backup of the recall vault file.

    If the vault file does not exist, an empty backup (``[]``) is created.
    """
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_path = path.parent / f"recallvault-{timestamp}.json"
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        backup_path.write_bytes(path.read_bytes())
    else:
        backup_path.write_text("[]\n", encoding="utf-8")

    return backup_path
