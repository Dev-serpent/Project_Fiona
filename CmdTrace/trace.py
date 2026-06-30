from __future__ import annotations

import collections.abc
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TRACE_PATH = Path.home() / ".config" / "fiona" / "cmdtrace.jsonl"


# ── existing public functions (unchanged) ──────────────────────────────


def append_trace(event: dict[str, Any], path: Path = DEFAULT_TRACE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def read_trace(
    *,
    action_name: str | None = None,
    limit: int = 50,
    path: Path = DEFAULT_TRACE_PATH,
) -> list[dict[str, Any]]:
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


# ── internal helpers ──────────────────────────────────────────────────


def _read_all_events(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Return (events_in_chronological_order, skipped_lines)."""
    if not path.exists():
        return [], 0
    events: list[dict[str, Any]] = []
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            skipped += 1
    return events, skipped


def _get_event_timestamp(event: dict[str, Any]) -> float | None:
    """Return Unix timestamp from event's ``time`` or ``timestamp`` field, or *None*."""
    raw = event.get("time") or event.get("timestamp")
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            return float(raw)
        # Try ISO-8601 parsing
        dt = datetime.fromisoformat(str(raw))
        # Assume naive datetimes are UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError, OSError):
        return None


def _get_event_time_str(event: dict[str, Any]) -> str | None:
    """Return the original ISO string from ``time`` or ``timestamp``."""
    raw = event.get("time") or event.get("timestamp")
    if raw is None:
        return None
    return str(raw)


def _search_recursive(obj: Any, query: str) -> bool:
    """Case-insensitive substring search across all string values in *obj*."""
    q = query.lower()
    stack: list[Any] = [obj]
    while stack:
        val = stack.pop()
        if isinstance(val, str):
            if q in val.lower():
                return True
        elif isinstance(val, dict):
            stack.extend(val.values())
        elif isinstance(val, (list, tuple)):
            stack.extend(val)
    return False


def _human_size(size: int) -> str:
    """Return a human-readable file size string (e.g. \"2.4 KB\")."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.1f} TB"


def _discover_keys(events: list[dict[str, Any]]) -> list[str]:
    """Return every top-level key that appears across *events*, sorted."""
    keys: set[str] = set()
    for ev in events:
        keys.update(ev.keys())
    return sorted(keys)


# ── new public functions ──────────────────────────────────────────────


def trace_stats(path: Path = DEFAULT_TRACE_PATH) -> dict[str, Any]:
    """Analyze the entire trace file and return summary statistics."""
    if not path.exists():
        return {
            "total_events": 0,
            "skipped_lines": 0,
            "per_action": {},
            "success_count": 0,
            "failure_count": 0,
            "unknown_status_count": 0,
            "first_event_time": None,
            "last_event_time": None,
            "time_span_seconds": None,
            "total_duration": 0.0,
            "avg_duration": None,
            "max_duration": None,
            "file_size_bytes": 0,
            "file_size_human": "0 B",
        }

    events, skipped = _read_all_events(path)

    total = len(events)
    per_action: dict[str, int] = {}
    success_count = 0
    failure_count = 0
    unknown_status_count = 0
    first_ts: float | None = None
    last_ts: float | None = None
    first_time_str: str | None = None
    last_time_str: str | None = None
    total_duration = 0.0
    durations: list[float] = []

    for ev in events:
        # Per-action counts
        action = ev.get("action")
        if action is not None:
            action_str = str(action)
            per_action[action_str] = per_action.get(action_str, 0) + 1

        # Status
        ok_val = ev.get("ok")
        if ok_val is True:
            success_count += 1
        elif ok_val is False:
            failure_count += 1
        else:
            unknown_status_count += 1

        # Timestamps
        ts = _get_event_timestamp(ev)
        ts_str = _get_event_time_str(ev)
        if ts is not None:
            if first_ts is None or ts < first_ts:
                first_ts = ts
                first_time_str = ts_str
            if last_ts is None or ts > last_ts:
                last_ts = ts
                last_time_str = ts_str

        # Duration
        dur = ev.get("duration", 0)
        if isinstance(dur, (int, float)) and dur > 0:
            durations.append(float(dur))
            total_duration += float(dur)

    # Sort per_action by count descending
    sorted_actions = dict(
        sorted(per_action.items(), key=lambda x: x[1], reverse=True)
    )

    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = 0

    time_span: float | None = None
    if first_ts is not None and last_ts is not None and last_ts >= first_ts:
        time_span = last_ts - first_ts

    max_dur = max(durations) if durations else None
    avg_dur = (total_duration / len(durations)) if durations else None

    return {
        "total_events": total,
        "skipped_lines": skipped,
        "per_action": sorted_actions,
        "success_count": success_count,
        "failure_count": failure_count,
        "unknown_status_count": unknown_status_count,
        "first_event_time": first_time_str,
        "last_event_time": last_time_str,
        "time_span_seconds": time_span,
        "total_duration": total_duration,
        "avg_duration": avg_dur,
        "max_duration": max_dur,
        "file_size_bytes": file_size,
        "file_size_human": _human_size(file_size),
    }


def trace_search(
    *,
    query: str = "",
    action_name: str | None = None,
    status: bool | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    regex: str | None = None,
    limit: int = 100,
    path: Path = DEFAULT_TRACE_PATH,
) -> list[dict[str, Any]]:
    """Advanced search over trace events. Returns results in chronological order (oldest first).

    Parameters
    ----------
    query : str
        Case-insensitive substring search across all string values in each event.
    action_name : str or None
        Exact match on ``event["action"]``.
    status : bool or None
        *True* → only events with ``ok=True``; *False* → only ``ok=False``; *None* → no filter.
    start_time : str or None
        ISO timestamp lower bound (inclusive) on ``time`` / ``timestamp`` field.
    end_time : str or None
        ISO timestamp upper bound (inclusive).
    regex : str or None
        Python regex pattern matched against ``json.dumps(event)``.
    limit : int
        Maximum number of results (default 100).
    path : Path
        Path to trace file.
    """
    if not path.exists():
        return []

    events, _skipped = _read_all_events(path)
    results: list[dict[str, Any]] = []

    # Pre-compile regex once
    pattern = re.compile(regex) if regex else None

    # Pre-parse timestamp bounds
    start_ts: float | None = None
    end_ts: float | None = None
    try:
        if start_time:
            dt = datetime.fromisoformat(start_time)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            start_ts = dt.timestamp()
    except (ValueError, TypeError):
        pass
    try:
        if end_time:
            dt = datetime.fromisoformat(end_time)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            end_ts = dt.timestamp()
    except (ValueError, TypeError):
        pass

    for event in events:
        if len(results) >= limit:
            break

        # Action filter
        if action_name and event.get("action") != action_name:
            continue

        # Status filter
        if status is not None:
            if event.get("ok") is not status:
                continue

        # Time range filter
        if start_ts is not None or end_ts is not None:
            ev_ts = _get_event_timestamp(event)
            if ev_ts is not None:
                if start_ts is not None and ev_ts < start_ts:
                    continue
                if end_ts is not None and ev_ts > end_ts:
                    continue
            else:
                # No timestamp available — skip if any time filter is active
                continue

        # Regex filter (against JSON serialization)
        if pattern is not None:
            serialized = json.dumps(event, sort_keys=True)
            if not pattern.search(serialized):
                continue

        # Query substring filter (recursive)
        if query:
            if not _search_recursive(event, query):
                continue

        results.append(event)

    return results


def trace_export(
    path: Path = DEFAULT_TRACE_PATH,
    output: Path | None = None,
    fmt: str = "json",
) -> Path:
    """Export the trace to a JSON array or CSV file.

    Parameters
    ----------
    path : Path
        Source trace file.
    output : Path or None
        Destination path. If *None*, a name like ``cmdtrace-export-{timestamp}.{fmt}``
        is auto-generated in the same directory as *path*.
    fmt : str
        ``"json"`` (default) or ``"csv"``.
    """
    events, _skipped = _read_all_events(path)

    # Auto-generate output path if not provided
    if output is None:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        output = path.parent / f"cmdtrace-export-{ts}.{fmt}"

    if fmt == "csv":
        fieldnames = _discover_keys(events)
        with output.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(events)
    else:
        # Default: JSON pretty-printed array
        with output.open("w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, sort_keys=True, ensure_ascii=False)

    return output


def trace_compact(
    *,
    max_size_mb: float = 10.0,
    max_age_days: float = 30.0,
    keep_last: int = 10000,
    path: Path = DEFAULT_TRACE_PATH,
) -> dict[str, Any]:
    """Compact/rotate the trace file by size and age thresholds.

    Returns a dict describing what was done.
    """
    if not path.exists():
        return {
            "original_size_bytes": 0,
            "new_size_bytes": 0,
            "original_entries": 0,
            "new_entries": 0,
            "trimmed_by_size": 0,
            "trimmed_by_age": 0,
        }

    try:
        original_size = path.stat().st_size
    except OSError:
        original_size = 0

    events, _skipped = _read_all_events(path)
    original_entries = len(events)

    if original_entries == 0:
        return {
            "original_size_bytes": original_size,
            "new_size_bytes": original_size,
            "original_entries": 0,
            "new_entries": 0,
            "trimmed_by_size": 0,
            "trimmed_by_age": 0,
        }

    now = time.time()
    age_cutoff = now - max_age_days * 86400

    # Determine which events to keep.
    # 1. Age-based removal.
    kept: list[dict[str, Any]] = []
    trimmed_by_age = 0
    for ev in events:
        ev_ts = _get_event_timestamp(ev)
        if ev_ts is not None and ev_ts < age_cutoff:
            trimmed_by_age += 1
        else:
            kept.append(ev)

    # 2. Size-based removal (only if the file on disk exceeds the limit).
    trimmed_by_size = 0
    if original_size > max_size_mb * 1024 * 1024 and len(kept) > keep_last:
        trimmed_by_size = len(kept) - keep_last
        kept = kept[-keep_last:]

    new_entries = len(kept)
    needs_rewrite = (trimmed_by_age > 0) or (trimmed_by_size > 0)

    if needs_rewrite:
        # Rewrite the file with only kept entries
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                for ev in kept:
                    f.write(
                        json.dumps(ev, sort_keys=True, separators=(",", ":")) + "\n"
                    )
            new_size = path.stat().st_size
        except OSError:
            new_size = original_size
    else:
        new_size = original_size

    return {
        "original_size_bytes": original_size,
        "new_size_bytes": new_size,
        "original_entries": original_entries,
        "new_entries": new_entries,
        "trimmed_by_size": trimmed_by_size,
        "trimmed_by_age": trimmed_by_age,
    }


class _TraceTailIterator(collections.abc.Iterator[dict[str, Any]]):
    """Iterator that yields new trace events as they are written.

    The file position is captured eagerly at construction time, so events
    written *between* iterator creation and the first ``next()`` call are
    detected correctly.
    """

    def __init__(self, path: Path, interval: float) -> None:
        self._path = path
        self._interval = interval
        self._closed = False
        try:
            self._pos: int = path.stat().st_size if path.exists() else 0
        except OSError:
            self._pos = 0

    def __next__(self) -> dict[str, Any]:
        if self._closed:
            raise StopIteration
        while True:
            try:
                if not self._path.exists():
                    time.sleep(self._interval)
                    continue

                current_size = self._path.stat().st_size
                if current_size < self._pos:
                    # File was truncated — restart from beginning
                    self._pos = 0

                if current_size > self._pos:
                    with self._path.open("r", encoding="utf-8") as f:
                        f.seek(self._pos)
                        while True:
                            line = f.readline()
                            if not line:
                                break
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                event = json.loads(line)
                                if isinstance(event, dict):
                                    self._pos = f.tell()
                                    return event
                            except json.JSONDecodeError:
                                continue
                        self._pos = f.tell()

                time.sleep(self._interval)
            except OSError:
                time.sleep(self._interval)


    def close(self) -> None:
        """Stop the iterator on the next ``__next__`` call."""
        self._closed = True

    def __iter__(self) -> collections.abc.Iterator[dict[str, Any]]:
        return self


def trace_tail(
    path: Path = DEFAULT_TRACE_PATH, interval: float = 1.0
) -> collections.abc.Iterator[dict[str, Any]]:
    """Return an iterator that yields new trace events as they are written.

    The file position is captured eagerly so events written between the call
    to ``trace_tail()`` and the first ``next()`` call are detected.

    Parameters
    ----------
    path : Path
        Path to the trace file.
    interval : float
        Seconds between polls for file growth.
    """
    return _TraceTailIterator(path, interval)
