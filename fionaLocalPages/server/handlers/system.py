"""System status and metrics endpoints."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from aiohttp.web import Request, Response, json_response

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────


def _read_int(path: str) -> int:
    try:
        return int(Path(path).read_text().strip())
    except Exception:
        return 0


def _read_line(path: str) -> str:
    try:
        return Path(path).read_text().strip()
    except Exception:
        return "unknown"


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
            "swap_total_gb": round(data.get("swap_total_kb", 0) / (1024 * 1024), 2),
            "swap_used_gb": round(
                (data.get("swap_total_kb", 0) - data.get("swap_free_kb", 0)) / (1024 * 1024), 2
            ),
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
        }
    except Exception:
        return {"error": "unable to read disk info"}


def _network_info() -> dict[str, object]:
    try:
        interfaces: list[dict[str, object]] = []
        for iface in os.listdir("/sys/class/net"):
            if iface == "lo":
                continue
            rx_path = f"/sys/class/net/{iface}/statistics/rx_bytes"
            tx_path = f"/sys/class/net/{iface}/statistics/tx_bytes"
            interfaces.append({
                "name": iface,
                "rx_bytes": _read_int(rx_path),
                "tx_bytes": _read_int(tx_path),
            })
        return {"interfaces": interfaces}
    except Exception:
        return {"error": "unable to read network info"}


def _process_info() -> list[dict[str, object]]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,comm,%cpu,%mem,etime", "--sort=-%cpu", "--no-headers"],
            capture_output=True, text=True, timeout=5.0,
        )
        lines = result.stdout.splitlines()
        procs = []
        for line in lines[:20]:  # top 20
            parts = line.split(maxsplit=4)
            if len(parts) >= 4:
                procs.append({
                    "pid": int(parts[0]) if parts[0].isdigit() else parts[0],
                    "command": parts[1],
                    "cpu": parts[2],
                    "mem": parts[3],
                    "etime": parts[4] if len(parts) > 4 else "",
                })
        return procs
    except Exception:
        return []


def _uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            seconds = float(f.read().split()[0])
        hours, remainder = divmod(int(seconds), 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"
    except Exception:
        return "unknown"


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return "unknown"


def _loadavg() -> list[str]:
    try:
        with open("/proc/loadavg") as f:
            return f.read().split()[:3]
    except Exception:
        return ["0", "0", "0"]


# ── Handlers ───────────────────────────────────────────────────────────────


async def health(_request: Request) -> Response:
    """GET /api/v1/health"""
    return json_response({"ok": True, "version": "0.1.0"})


async def system_status(_request: Request) -> Response:
    """GET /api/v1/system/status — aggregate system info."""
    try:
        data = {
            "hostname": _read_line("/proc/sys/kernel/hostname"),
            "platform": os.uname().sysname,
            "release": os.uname().release,
            "uptime": _uptime(),
            "loadavg": _loadavg(),
            "cpu": {
                "count": _cpu_count(),
                "percent": _cpu_percent(),
                "model": _cpu_model(),
            },
            "memory": _memory_info(),
            "disk": _disk_info(),
            "network": _network_info(),
            "processes": _process_info(),
            "python_version": os.sys.version,
        }
        return json_response({"ok": True, "data": data})
    except Exception as exc:
        logger.exception("Failed to gather system status")
        raise ApiError(status=500, message=str(exc)) from exc


async def system_metrics(_request: Request) -> Response:
    """GET /api/v1/system/metrics — real-time system metrics snapshot."""
    try:
        data = {
            "timestamp": time.time(),
            "cpu_percent": _cpu_percent(),
            "memory": _memory_info(),
            "disk": _disk_info(),
            "loadavg": _loadavg(),
            "uptime": _uptime(),
            "process_count": len(_process_info()),
        }
        return json_response({"ok": True, "data": data})
    except Exception as exc:
        logger.exception("Failed to gather system metrics")
        raise ApiError(status=500, message=str(exc)) from exc
