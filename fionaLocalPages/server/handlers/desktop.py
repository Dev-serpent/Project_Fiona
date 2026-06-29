"""Desktop awareness API endpoints.

Wraps SeeOnDesk modules for active window, snapshot, processes,
workspaces, applications, and system resources.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import aiohttp.web
from aiohttp.web import Request, Response, json_response

from SeeOnDesk import active_window_info, desktop_snapshot
from SeeOnDesk.process_tracker import ProcessTracker
from SeeOnDesk.workspace_watcher import WorkspaceWatcher

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────


def _cpu_count() -> int:
    try:
        return os.cpu_count() or 0
    except Exception:
        return 0


def _cpu_percent() -> float:
    """Read CPU usage from /proc/stat (short delta for real-time percent)."""
    try:
        def _sample() -> tuple[int, int]:
            with open("/proc/stat") as f:
                parts = [int(v) for v in f.readline().split()[1:]]
            return sum(parts), parts[3]

        t1, i1 = _sample()
        time.sleep(0.1)
        t2, i2 = _sample()
        delta_total = t2 - t1
        delta_idle = i2 - i1
        if delta_total == 0:
            return 0.0
        return round(100.0 * (1.0 - delta_idle / delta_total), 1)
    except Exception:
        return 0.0


def _memory_info() -> dict[str, object]:
    try:
        with open("/proc/meminfo") as f:
            data: dict[str, int] = {}
            for line in f:
                if line.startswith("MemTotal:"):
                    data["total_kb"] = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    data["available_kb"] = int(line.split()[1])
                elif line.startswith("MemFree:"):
                    data["free_kb"] = int(line.split()[1])
                elif line.startswith("SwapTotal:"):
                    data["swap_total_kb"] = int(line.split()[1])
                elif line.startswith("SwapFree:"):
                    data["swap_free_kb"] = int(line.split()[1])
                if len(data) >= 5:
                    break

        total = data.get("total_kb", 0)
        available = data.get("available_kb", 0)
        used = total - available if total > 0 else 0
        return {
            "total_gb": round(total / (1024 * 1024), 2),
            "used_gb": round(used / (1024 * 1024), 2),
            "available_gb": round(available / (1024 * 1024), 2),
            "percent_used": round(100.0 * used / total, 1) if total > 0 else 0.0,
            "total": total,
            "used": used,
            "available": available,
        }
    except Exception:
        return {"error": "unable to read memory info"}


def _disk_info() -> dict[str, object]:
    try:
        usage = shutil.disk_usage("/")
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round(100.0 * usage.used / usage.total, 1),
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
        }
    except Exception:
        return {"error": "unable to read disk info"}


def _loadavg() -> list[str]:
    try:
        with open("/proc/loadavg") as f:
            return f.read().split()[:3]
    except Exception:
        return ["0", "0", "0"]


def _read_proc_status(pid: int) -> dict[str, object]:
    """Read memory and state from /proc/[pid]/status."""
    result: dict[str, object] = {}
    try:
        status_path = Path(f"/proc/{pid}/status")
        if status_path.exists():
            for line in status_path.read_text().splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    result["vm_rss_kb"] = int(parts[1]) if len(parts) > 1 else 0
                elif line.startswith("State:"):
                    result["state"] = line.split(":", 1)[1].strip()
    except (OSError, ValueError):
        pass
    return result


def _read_proc_stat(pid: int) -> dict[str, object] | None:
    """Read CPU time from /proc/[pid]/stat."""
    try:
        stat_path = Path(f"/proc/{pid}/stat")
        if not stat_path.exists():
            return None
        data = stat_path.read_text()
        # Find the closing ')' of the comm field
        paren_end = data.rfind(")")
        if paren_end == -1:
            return None
        fields = data[paren_end + 2:].split()
        if len(fields) < 19:
            return None
        return {
            "state": fields[0],
            "utime": int(fields[11]),
            "stime": int(fields[12]),
        }
    except (OSError, ValueError, IndexError):
        return None


def _process_cpu_percent(proc_stat: dict[str, object] | None, uptime_seconds: float) -> float:
    """Compute rough lifetime CPU% for a process."""
    if not proc_stat:
        return 0.0
    try:
        clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    except (AttributeError, KeyError, ValueError):
        clk_tck = 100  # Common default
    total_jiffies = proc_stat.get("utime", 0) + proc_stat.get("stime", 0)
    uptime_jiffies = uptime_seconds * clk_tck
    if uptime_jiffies <= 0:
        return 0.0
    return round(100.0 * total_jiffies / uptime_jiffies, 1)


def _parse_desktop_file(path: Path) -> dict[str, str] | None:
    """Minimal .desktop file parser — returns dict with name/exec/icon/etc."""
    app: dict[str, str] = {}
    in_desktop_entry = False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("[Desktop Entry]"):
                in_desktop_entry = True
            elif line.startswith("[") and in_desktop_entry:
                break
            elif in_desktop_entry and "=" in line:
                key, value = line.split("=", 1)
                app[key.strip()] = value.strip()
    except Exception:
        return None

    if app.get("NoDisplay") == "true":
        return None
    if app.get("Type") != "Application":
        return None
    return {
        "name": app.get("Name", ""),
        "exec": app.get("Exec", ""),
        "icon": app.get("Icon", ""),
        "categories": app.get("Categories", ""),
        "comment": app.get("Comment", ""),
        "terminal": app.get("Terminal", "false"),
    }


def _list_desktop_apps() -> list[dict[str, str]]:
    """List installed applications from .desktop files."""
    apps: list[dict[str, str]] = []
    search_paths = [
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path.home() / ".local/share/applications",
    ]
    seen_names: set[str] = set()
    for search_path in search_paths:
        if not search_path.is_dir():
            continue
        for f in sorted(search_path.glob("*.desktop")):
            try:
                entry = _parse_desktop_file(f)
                if entry and entry["name"] and entry["name"] not in seen_names:
                    seen_names.add(entry["name"])
                    apps.append(entry)
            except Exception:
                continue
    return sorted(apps, key=lambda a: a["name"].lower())


# ── Uptime ──────────────────────────────────────────────────────────────────


def _uptime_seconds() -> float:
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0.0


# ── Handlers ───────────────────────────────────────────────────────────────


async def desktop_active(_request: Request) -> Response:
    """GET /api/v1/desktop/active — calls SeeOnDesk.active_window_info()."""
    try:
        info = active_window_info()
        return json_response({
            "ok": True,
            "data": info.to_dict(),
        })
    except Exception as exc:
        logger.exception("Desktop active window failed")
        raise ApiError(500, str(exc)) from exc


async def desktop_snapshot_handler(_request: Request) -> Response:
    """GET /api/v1/desktop/snapshot — calls SeeOnDesk.desktop_snapshot()."""
    try:
        snapshot = desktop_snapshot(include_screenshot=False)
        return json_response({
            "ok": True,
            "data": snapshot.to_dict(),
        })
    except Exception as exc:
        logger.exception("Desktop snapshot failed")
        raise ApiError(500, str(exc)) from exc


async def desktop_processes(_request: Request) -> Response:
    """GET /api/v1/desktop/processes — list running processes with resource usage.

    Uses SeeOnDesk ProcessTracker for the base process list and enriches
    with CPU/memory data from /proc.
    """
    try:
        tracker = ProcessTracker()
        procs = tracker.list_processes()
        uptime = _uptime_seconds()

        # Get total memory for percentage calculation
        total_mem_kb = 0
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_mem_kb = int(line.split()[1])
                        break
        except Exception:
            pass

        result = []
        for p in procs:
            status_data = _read_proc_status(p.pid)
            stat_data = _read_proc_stat(p.pid)
            cpu = _process_cpu_percent(stat_data, uptime)
            rss_kb = status_data.get("vm_rss_kb", 0) or 0
            mem_percent = round(100.0 * rss_kb / total_mem_kb, 1) if total_mem_kb > 0 else 0.0
            status = status_data.get("state", "") or ""

            result.append({
                "pid": p.pid,
                "name": p.name,
                "cpu_percent": cpu,
                "memory_percent": mem_percent,
                "memory_rss": rss_kb,
                "status": status,
            })

        return json_response({"ok": True, "data": result})
    except Exception as exc:
        logger.exception("Desktop processes failed")
        raise ApiError(500, str(exc)) from exc


async def desktop_applications(_request: Request) -> Response:
    """GET /api/v1/desktop/applications — list installed applications.

    Reads .desktop files from standard system locations.
    """
    try:
        apps = _list_desktop_apps()
        return json_response({"ok": True, "data": apps})
    except Exception as exc:
        logger.exception("Desktop applications failed")
        raise ApiError(500, str(exc)) from exc


async def desktop_workspaces(_request: Request) -> Response:
    """GET /api/v1/desktop/workspaces — list virtual desktops/workspaces.

    Uses SeeOnDesk WorkspaceWatcher.
    """
    try:
        watcher = WorkspaceWatcher()
        workspaces = watcher.list_workspaces()
        return json_response({
            "ok": True,
            "data": [
                {
                    "id": ws.id,
                    "name": ws.name,
                    "is_active": ws.is_active,
                    "window_count": ws.window_count,
                }
                for ws in workspaces
            ],
        })
    except Exception as exc:
        logger.exception("Desktop workspaces failed")
        raise ApiError(500, str(exc)) from exc


async def desktop_system_resources(_request: Request) -> Response:
    """GET /api/v1/desktop/system-resources — CPU, memory, disk usage."""
    try:
        return json_response({
            "ok": True,
            "data": {
                "cpu": {
                    "percent": _cpu_percent(),
                    "count": _cpu_count(),
                    "loadavg": _loadavg(),
                },
                "memory": _memory_info(),
                "disk": _disk_info(),
            },
        })
    except Exception as exc:
        logger.exception("Desktop system resources failed")
        raise ApiError(500, str(exc)) from exc


async def desktop_launch(request: Request) -> Response:
    """POST /api/v1/desktop/launch — launch an application via its exec command.

    Body: { "exec": "<command>" }
    """
    try:
        body = await request.json()
        exec_cmd = body.get("exec", "")
        if not exec_cmd:
            raise ApiError(400, "Missing 'exec' field in request body")

        # Strip desktop file placeholders like %U, %f, etc.
        sanitized = re.sub(r"%[UfFdDnNickvm]", "", exec_cmd).strip()

        subprocess.Popen(
            ["sh", "-c", sanitized],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return json_response({"ok": True, "message": f"Launched: {sanitized}"})
    except ApiError:
        raise
    except Exception as exc:
        logger.exception("Desktop launch failed")
        raise ApiError(500, str(exc)) from exc
