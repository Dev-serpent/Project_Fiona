from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from CamComs import DEFAULT_FIONA_CONFIG_PATH, DEFAULT_TRUSTED_DIR, private_key_path

RESET = "\033[0m"
CYAN = "\033[38;5;51m"
BLUE = "\033[38;5;39m"
GREEN = "\033[38;5;48m"
YELLOW = "\033[38;5;220m"
RED = "\033[38;5;203m"
DIM = "\033[38;5;245m"
BOLD = "\033[1m"
WHITE = "\033[38;5;255m"


@dataclass(frozen=True)
class FatPanel:
    title: str
    rows: tuple[str, ...]


def get_hostname() -> str:
    try:
        return os.uname().nodename
    except Exception:
        return "unknown"


def get_kernel_version() -> str:
    try:
        return os.uname().release
    except Exception:
        return "unknown"


def get_cpu_info() -> dict[str, str]:
    info = {"model": "unknown", "speed": "unknown", "temp": "unknown", "usage": "0%"}
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    info["model"] = line.split(":")[1].strip()
                    break
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "r") as f:
            info["speed"] = f"{int(f.read().strip()) // 1000}MHz"
    except Exception:
        pass
    
    try:
        for path in Path("/sys/class/thermal").glob("thermal_zone*"):
            type_path = path / "type"
            temp_path = path / "temp"
            if type_path.exists() and temp_path.exists():
                if "cpu" in type_path.read_text().lower():
                    info["temp"] = f"{int(temp_path.read_text().strip()) / 1000:.1f}°C"
                    break
    except Exception:
        pass
    return info


def get_per_core_usage() -> list[float]:
    usages = []
    try:
        with open("/proc/stat", "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("cpu") and line[3].isdigit():
                    parts = [int(p) for p in line.split()[1:]]
                    idle = parts[3]
                    total = sum(parts)
                    usages.append(round(100 * (1 - idle/total), 1))
    except Exception:
        pass
    return usages


def get_swap_info() -> str:
    try:
        with open("/proc/meminfo", "r") as f:
            total, free = 0, 0
            for line in f:
                if line.startswith("SwapTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("SwapFree:"):
                    free = int(line.split()[1])
            if total > 0:
                used = total - free
                return f"{used // 1024}MB / {total // 1024}MB ({100 * used / total:.1f}%)"
    except Exception:
        pass
    return "0MB / 0MB (0%)"


def get_disk_activity() -> str:
    try:
        with open("/proc/diskstats", "r") as f:
            for line in f:
                if " sda " in line or " nvme0n1 " in line:
                    parts = line.split()
                    reads = int(parts[5]) // 2
                    writes = int(parts[9]) // 2
                    return f"R: {reads//1024}MB W: {writes//1024}MB"
    except Exception:
        pass
    return "unknown"


def get_network_details() -> dict[str, str]:
    info = {"ip": "127.0.0.1", "interface": "unknown", "signal": "n/a", "rx": "0", "tx": "0"}
    try:
        output = subprocess.check_output(["ip", "-4", "-o", "addr", "show"], text=True)
        for line in output.splitlines():
            if " scope global " in line:
                parts = line.split()
                info["interface"] = parts[1]
                info["ip"] = parts[3].split("/")[0]
                break
        
        if info["interface"] != "unknown":
            with open(f"/sys/class/net/{info['interface']}/statistics/rx_bytes", "r") as f:
                info["rx"] = f"{int(f.read().strip()) // (1024**2)}MB"
            with open(f"/sys/class/net/{info['interface']}/statistics/tx_bytes", "r") as f:
                info["tx"] = f"{int(f.read().strip()) // (1024**2)}MB"
            
        if info["interface"].startswith("w"):
            with open("/proc/net/wireless", "r") as f:
                lines = f.readlines()
                for line in lines:
                    if info["interface"] in line:
                        info["signal"] = line.split()[2].strip(".") + "%"
    except Exception:
        pass
    return info


def get_gpu_info() -> str:
    try:
        if shutil.which("nvidia-smi"):
            out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"], text=True)
            return out.strip().replace(",", " |") + "°C"
    except Exception:
        pass
    return "none detected"


def get_top_processes() -> list[str]:
    try:
        out = subprocess.check_output(["ps", "-eo", "comm,%cpu,%mem", "--sort=-%cpu"], text=True)
        return out.strip().splitlines()[1:4]
    except Exception:
        return []


def get_failed_services() -> list[str]:
    try:
        out = subprocess.check_output(["systemctl", "--user", "list-units", "--state=failed", "--no-legend"], text=True)
        failed = [line.split()[0] for line in out.splitlines()]
        return failed[:3]
    except Exception:
        return []


def get_power_info() -> str:
    try:
        for path in Path("/sys/class/power_supply").glob("BAT*"):
            capacity = (path / "capacity").read_text().strip()
            status = (path / "status").read_text().strip()
            return f"{capacity}% ({status})"
    except Exception:
        pass
    return "AC Power"


def get_security_info() -> dict[str, str]:
    info = {"firewall": "unknown", "updates": "0"}
    try:
        if shutil.which("ufw"):
            status = subprocess.check_output(["sudo", "ufw", "status"], text=True).splitlines()[0]
            info["firewall"] = status.split(":")[1].strip()
        if shutil.which("checkupdates"):
            out = subprocess.check_output(["checkupdates"], text=True)
            info["updates"] = str(len(out.splitlines()))
    except Exception:
        pass
    return info


def get_cpu_load() -> str:
    try:
        with open("/proc/loadavg", "r") as f:
            load = f.read().split()[:3]
            return " / ".join(load)
    except Exception:
        return "unknown"


def get_mem_info() -> str:
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
            t, a = 0, 0
            for line in lines:
                if line.startswith("MemTotal:"): t = int(line.split()[1])
                elif line.startswith("MemAvailable:"): a = int(line.split()[1])
            if t > 0:
                u = t - a
                p = (u / t) * 100
                return f"{u // 1024}MB / {t // 1024}MB ({p:.1f}%)"
    except Exception:
        pass
    return "unknown"


def get_uptime() -> str:
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    except Exception:
        return "unknown"


def get_disk_usage() -> str:
    try:
        usage = shutil.disk_usage("/")
        u = usage.used // (1024**3)
        t = usage.total // (1024**3)
        p = (usage.used / usage.total) * 100
        return f"{u}GB / {t}GB ({p:.1f}%)"
    except Exception:
        return "unknown"


def get_os_info() -> str:
    try:
        with open("/etc/os-release", "r") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=")[1].strip().strip('"')
    except Exception:
        pass
    return os.uname().sysname


def terminal_assist_status() -> dict[str, object]:
    zellij_path = shutil.which("zellij")
    python_executable = sys.executable
    checks = {
        "host_config": DEFAULT_FIONA_CONFIG_PATH.exists(),
        "host_private_key": private_key_path("host").exists(),
        "trusted_senders": DEFAULT_TRUSTED_DIR.exists(),
        "zellij": bool(zellij_path),
    }
    
    cpu_info = get_cpu_info()
    net_info = get_network_details()
    sec_info = get_security_info()
    
    cpu_usage_raw = 0.0
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
            parts = [int(p) for p in line.split()[1:]]
            idle = parts[3]
            total = sum(parts)
            cpu_usage_raw = 100 * (1 - idle/total)
    except Exception: pass

    mem_raw = 0.0
    try:
        with open("/proc/meminfo", "r") as f:
            t, a = 0, 0
            for line in f:
                if line.startswith("MemTotal:"): t = int(line.split()[1])
                elif line.startswith("MemAvailable:"): a = int(line.split()[1])
            if t > 0: mem_raw = 100 * (t - a) / t
    except Exception: pass

    disk_raw = 0.0
    try:
        du = shutil.disk_usage("/")
        disk_raw = 100 * du.used / du.total
    except Exception: pass

    return {
        "ready": all(checks.values()),
        "hostname": get_hostname(),
        "kernel": get_kernel_version(),
        "zellij_path": zellij_path,
        "python": python_executable,
        "checks": checks,
        "cpu_load": get_cpu_load(),
        "cpu_usage": f"{cpu_usage_raw:.1f}%",
        "cpu_usage_raw": cpu_usage_raw,
        "cpu_model": cpu_info["model"],
        "cpu_speed": cpu_info["speed"],
        "cpu_temp": cpu_info["temp"],
        "cpu_cores": get_per_core_usage(),
        "mem": get_mem_info(),
        "mem_raw": mem_raw,
        "swap": get_swap_info(),
        "disk": get_disk_usage(),
        "disk_raw": disk_raw,
        "disk_io": get_disk_activity(),
        "uptime": get_uptime(),
        "os": get_os_info(),
        "user": os.getlogin(),
        "network": net_info,
        "gpu": get_gpu_info(),
        "processes": get_top_processes(),
        "failed_services": get_failed_services(),
        "power": get_power_info(),
        "security": sec_info,
        "commands": [
            "fiona fat status",
            "fiona fat layout --print",
            "fiona fat run",
        ],
    }


def _gauge(percent: float, width: int, color: bool = True) -> str:
    if percent < 0: percent = 0
    if percent > 100: percent = 100
    filled = int((percent / 100) * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    if not color:
        return f"[{bar}] {percent:>5.1f}%"
    ansi = GREEN
    if percent > 85: ansi = RED
    elif percent > 60: ansi = YELLOW
    return f"[{ansi}{bar}{RESET}] {ansi}{percent:>5.1f}%{RESET}"


def _get_icon(category: str) -> str:
    icons = {
        "system": "󰍹 ", "cpu": " ", "mem": " ", "disk": "󰋊 ",
        "net": "󰖩 ", "power": "󰚥 ", "sec": "󰒃 ", "core": "󰅟 ", "proc": "󰑖 ",
    }
    return icons.get(category, "• ")


def build_dashboard(*, color: bool = True, width: int = 96, height: int = 24) -> str:
    status = terminal_assist_status()
    checks = status["checks"]
    net = status["network"]
    sec = status["security"]
    
    title_text = f" fAT Dashboard │ {status['hostname']} │ {status['os']} "
    rendered = [_paint(title_text.center(width, "━"), CYAN + BOLD, color)]
    
    sys_line = (
        f" CPU: {status['cpu_usage']} "
        f"│ MEM: {status['mem'].split(' / ')[0]} "
        f"│ DISK: {status['disk'].split(' / ')[0]} "
        f"│ NET: {net['ip']} "
    )
    rendered.append(_paint("┏" + "━" * (width - 2) + "┓", BLUE, color))
    rendered.append("┃ " + _paint(sys_line.ljust(width - 4), GREEN, color) + " ┃")
    rendered.append(_paint("┣" + "━" * (width - 2) + "┫", BLUE, color))
    
    gauge_w = (width - 12) // 3
    gauges = (
        f"CPU {_gauge(status['cpu_usage_raw'], gauge_w, color)} "
        f"MEM {_gauge(status['mem_raw'], gauge_w, color)} "
        f"DSK {_gauge(status['disk_raw'], gauge_w, color)}"
    )
    rendered.append("┃ " + gauges.ljust(_visible_pad(width - 4, gauges)) + " ┃")
    rendered.append(_paint("┣" + "━" * (width - 2) + "┫", BLUE, color))

    two_col = width >= 110
    col_w = (width - 6) // 2 if two_col else width - 4
    
    panel_groups = [
        FatPanel(_get_icon("system") + "SYSTEM & HARDWARE", (
            f"Kernel:      {status['kernel']}",
            f"Architecture: {os.uname().machine}",
            f"CPU Model:   {status['cpu_model']}",
            f"CPU Speed:   {status['cpu_speed']} @ {status['cpu_temp']}",
            f"GPU:         {status['gpu']}",
            f"Uptime:      {status['uptime']}",
        )),
        FatPanel(_get_icon("mem") + "MEMORY & STORAGE", (
            f"RAM:         {status['mem']}",
            f"Swap:        {status['swap']}",
            f"Disk Usage:  {status['disk']}",
            f"Disk I/O:    {status['disk_io']}",
        )),
        FatPanel(_get_icon("net") + "NETWORK & POWER", (
            f"Interface:   {net['interface']} ({net['signal']})",
            f"Traffic:     RX: {net['rx']} / TX: {net['tx']}",
            f"Power:       {status['power']}",
        )),
        FatPanel(_get_icon("proc") + "PROCESSES & SECURITY", (
            f"Top CPU:     {', '.join(status['processes']) if status['processes'] else 'none'}",
            f"Firewall:    {sec['firewall']}",
            f"Updates:     {sec['updates']} available",
            f"Failed Serv: {', '.join(status['failed_services']) if status['failed_services'] else 'none'}",
        )),
        FatPanel(_get_icon("core") + "CORE COMPONENTS", (
            _check_row("Config File", bool(checks["host_config"])),
            _check_row("Private Key", bool(checks["host_private_key"])),
            _check_row("Trust Store", bool(checks["trusted_senders"])),
            _check_row("Zellij Link", bool(checks["zellij"])),
        )),
    ]

    if two_col:
        for i in range(0, len(panel_groups), 2):
            p1 = panel_groups[i]
            p2 = panel_groups[i+1] if i+1 < len(panel_groups) else None
            h1 = _paint(f" {p1.title} ".ljust(col_w, "─"), WHITE + BOLD, color)
            h2 = _paint(f" {p2.title} ".ljust(col_w, "─"), WHITE + BOLD, color) if p2 else " " * col_w
            rendered.append(f"┃ {h1} │ {h2} ┃")
            max_r = max(len(p1.rows), len(p2.rows) if p2 else 0)
            for r in range(max_r):
                r1 = p1.rows[r] if r < len(p1.rows) else ""
                r2 = (p2.rows[r] if r < len(p2.rows) else "") if p2 else ""
                rendered.append(f"┃ {_row_content(r1, col_w, color)} │ {_row_content(r2, col_w, color)} ┃")
            if i + 2 < len(panel_groups): rendered.append("┃ " + " " * (width - 4) + " ┃")
    else:
        for p in panel_groups:
            rendered.append("┃ " + _paint(f" {p.title} ".ljust(width - 4, "─"), WHITE + BOLD, color) + " ┃")
            for r in p.rows: rendered.append(_row(r, inner_width=width - 4, color=color))
            rendered.append("┃ " + " " * (width - 4) + " ┃")

    while len(rendered) < height - 1:
        rendered.append("┃ " + " " * (width - 4) + " ┃")

    rendered.append(_paint("┗" + "━" * (width - 2) + "┛", BLUE, color))
    return "\n".join(rendered)


def _row_content(text: str, inner_width: int, color: bool) -> str:
    colored = _color_status(text, color)
    visible_text = _strip_known_ansi(colored)
    padding = max(0, inner_width - len(visible_text))
    return colored + (" " * padding)


def build_zellij_layout(*, python_executable: str | None = None, working_directory: Path | None = None) -> str:
    python_executable = python_executable or sys.executable
    working_directory = working_directory or Path.cwd()
    cwd = _kdl_string(str(working_directory))
    py = _kdl_string(python_executable)
    return "\n".join([
        "layout {", "    pane size=1 borderless=true {", '        plugin location="tab-bar"', "    }",
        f"    cwd {cwd}", '    pane split_direction="vertical" {', '        pane split_direction="horizontal" {',
        f"            pane command={py} name=\"fAT\" {{ args \"-m\" \"fiona.cli\" \"fat\" \"status\" }}",
        f"            pane command={py} name=\"Host\" {{ args \"-m\" \"fiona.cli\" \"host\" \"status\" }}",
        "        }", '        pane split_direction="horizontal" {',
        f"            pane command={py} name=\"CamComs\" {{ args \"-m\" \"fiona.cli\" \"camcoms\" \"paths\" }}",
        f"            pane command={py} name=\"SeeOnDesk\" {{ args \"-m\" \"fiona.cli\" \"seeondesk\" \"status\" }}",
        "        }", "    }", "    pane size=1 borderless=true {", '        plugin location="status-bar"', "    }", "}", ""
    ])


def write_zellij_layout(path: Path, *, python_executable: str | None = None, working_directory: Path | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_zellij_layout(python_executable=python_executable, working_directory=working_directory), encoding="utf-8")
    return path


def run_zellij(layout_path: Path) -> int:
    zellij = shutil.which("zellij")
    if not zellij: raise RuntimeError("zellij is not installed or is not on PATH")
    return subprocess.call([zellij, "--layout", str(layout_path)])


def _check_row(label: str, ok: bool) -> str:
    return f"{label}: {'ok' if ok else 'missing'}"


def _row(text: str, *, inner_width: int, color: bool) -> str:
    colored = _color_status(text, color)
    visible_text = _strip_known_ansi(colored)
    padding = max(0, inner_width - len(visible_text))
    return f"┃ {colored}{' ' * padding} ┃"


def _color_status(text: str, color: bool) -> str:
    if not color: return text
    if text.endswith(": ok"): return text[:-2] + GREEN + "ok" + RESET
    if text.endswith(": missing"): return text[:-7] + RED + "missing" + RESET
    if text.endswith("partial"): return text[:-7] + YELLOW + "partial" + RESET
    return _paint(text, DIM, color)


def _paint(text: str, ansi: str, color: bool) -> str:
    return f"{ansi}{text}{RESET}" if color else text


def _visible_pad(width: int, text: str) -> int:
    return width + len(text) - len(_strip_known_ansi(text))


def _strip_known_ansi(text: str) -> str:
    for code in (RESET, CYAN, BLUE, GREEN, YELLOW, RED, DIM, BOLD):
        text = text.replace(code, "")
    return text


def _kdl_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
