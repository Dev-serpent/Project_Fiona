from __future__ import annotations

import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ActiveWindowInfo:
    """Best-effort identity of the currently focused desktop window."""

    ok: bool
    backend: str
    window_id: str = ""
    app_class: str = ""
    title: str = ""
    pid: int | None = None
    process_name: str = ""
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def app_name(self) -> str:
        return self.app_class or self.process_name or self.title or "unknown"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["app_name"] = self.app_name
        return data


@dataclass(frozen=True)
class DesktopSnapshot:
    """Single desktop-awareness sample for Fiona."""

    timestamp: str
    session_type: str
    desktop: str
    active_window: ActiveWindowInfo

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "session_type": self.session_type,
            "desktop": self.desktop,
            "active_window": self.active_window.to_dict(),
        }


def desktop_snapshot() -> DesktopSnapshot:
    return DesktopSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        session_type=os.environ.get("XDG_SESSION_TYPE", ""),
        desktop=os.environ.get("XDG_CURRENT_DESKTOP", ""),
        active_window=active_window_info(),
    )


def active_window_info() -> ActiveWindowInfo:
    kdotool_info = _active_window_from_kdotool()
    if kdotool_info.ok:
        return kdotool_info
    x11_info = _active_window_from_x11()
    if x11_info.ok:
        return x11_info
    return ActiveWindowInfo(
        ok=False,
        backend="unavailable",
        error=kdotool_info.error or x11_info.error or "No supported desktop awareness backend found.",
        raw={"kdotool": kdotool_info.to_dict(), "x11": x11_info.to_dict()},
    )


def _active_window_from_kdotool() -> ActiveWindowInfo:
    ok, window_id, error = _run_command(["kdotool", "getactivewindow"])
    if not ok or not window_id.strip():
        return ActiveWindowInfo(ok=False, backend="kdotool", error=error or "kdotool did not return an active window")

    window_id = window_id.strip().splitlines()[0]
    class_ok, app_class, class_error = _run_command(["kdotool", "getwindowclassname", window_id])
    title_ok, title, _title_error = _run_command(["kdotool", "getwindowname", window_id])
    xprop = _xprop_details(window_id)
    pid = xprop.get("pid")
    return ActiveWindowInfo(
        ok=class_ok or bool(xprop),
        backend="kdotool",
        window_id=window_id,
        app_class=(app_class.strip().splitlines()[0] if class_ok and app_class.strip() else xprop.get("app_class", "")),
        title=(title.strip().splitlines()[0] if title_ok and title.strip() else xprop.get("title", "")),
        pid=pid,
        process_name=_process_name(pid),
        error="" if class_ok or xprop else class_error,
        raw={"xprop": xprop},
    )


def _active_window_from_x11() -> ActiveWindowInfo:
    ok, window_id, error = _run_command(["xdotool", "getactivewindow"])
    if not ok or not window_id.strip():
        return ActiveWindowInfo(ok=False, backend="x11", error=error or "xdotool did not return an active window")
    window_id = window_id.strip().splitlines()[0]
    xprop = _xprop_details(window_id)
    if not xprop:
        return ActiveWindowInfo(ok=False, backend="x11", window_id=window_id, error="xprop did not return window metadata")
    pid = xprop.get("pid")
    return ActiveWindowInfo(
        ok=True,
        backend="x11",
        window_id=window_id,
        app_class=xprop.get("app_class", ""),
        title=xprop.get("title", ""),
        pid=pid,
        process_name=_process_name(pid),
        raw={"xprop": xprop},
    )


def _xprop_details(window_id: str) -> dict[str, Any]:
    ok, output, _error = _run_command(["xprop", "-id", window_id, "WM_CLASS", "_NET_WM_NAME", "WM_NAME", "_NET_WM_PID"])
    if not ok:
        return {}
    details: dict[str, Any] = {}
    wm_class = _parse_xprop_string_list(output, "WM_CLASS")
    if wm_class:
        details["app_class"] = wm_class[-1]
        details["wm_class"] = wm_class
    title = _parse_xprop_string(output, "_NET_WM_NAME") or _parse_xprop_string(output, "WM_NAME")
    if title:
        details["title"] = title
    pid = _parse_xprop_int(output, "_NET_WM_PID")
    if pid is not None:
        details["pid"] = pid
    return details


def _run_command(args: list[str], timeout_seconds: float = 1.0) -> tuple[bool, str, str]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return False, "", str(exc)
    return completed.returncode == 0, completed.stdout, completed.stderr.strip()


def _parse_xprop_string(output: str, key: str) -> str:
    pattern = rf"^{re.escape(key)}\([^)]*\) = \"(.*)\"$"
    for line in output.splitlines():
        match = re.match(pattern, line.strip())
        if match:
            return match.group(1)
    return ""


def _parse_xprop_string_list(output: str, key: str) -> list[str]:
    for line in output.splitlines():
        if not line.strip().startswith(f"{key}("):
            continue
        return re.findall(r'"([^"]*)"', line)
    return []


def _parse_xprop_int(output: str, key: str) -> int | None:
    pattern = rf"^{re.escape(key)}\([^)]*\) = (\d+)$"
    for line in output.splitlines():
        match = re.match(pattern, line.strip())
        if match:
            return int(match.group(1))
    return None


def _process_name(pid: int | None) -> str:
    if pid is None:
        return ""
    proc_comm = Path("/proc") / str(pid) / "comm"
    try:
        return proc_comm.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
