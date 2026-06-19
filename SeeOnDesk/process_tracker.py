"""Process tracking utilities for monitoring foreground and background processes.

Supports Linux (``/proc``) and Windows (``CreateToolhelp32Snapshot`` via ctypes).
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cmdline: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0


class ProcessTracker:
    """Tracks running processes with optional callback on matching.

    On Linux uses ``/proc``; on Windows uses ``CreateToolhelp32Snapshot``
    via ctypes (no psutil dependency).
    """

    def __init__(self):
        self._watchers: dict[str, Callable[[ProcessInfo], None]] = {}

    def list_processes(self) -> list[ProcessInfo]:
        """List all running processes (platform-appropriate backend)."""
        if os.name == "nt":
            return self._list_processes_win32()
        return self._list_processes_linux()

    def _list_processes_linux(self) -> list[ProcessInfo]:
        """List processes from ``/proc`` (Linux)."""
        processes = []
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                pid = int(proc.name)
                comm = (proc / "comm").read_text(encoding="utf-8").strip()
                try:
                    cmdline_bytes = (proc / "cmdline").read_bytes()
                    cmdline = cmdline_bytes.replace(b"\0", b" ").decode("utf-8", errors="replace").strip()
                except OSError:
                    cmdline = comm
                processes.append(ProcessInfo(pid=pid, name=comm, cmdline=cmdline))
            except (OSError, ValueError, FileNotFoundError):
                continue
        return processes

    def _list_processes_win32(self) -> list[ProcessInfo]:
        """List processes via ``CreateToolhelp32Snapshot`` (Windows)."""
        import ctypes  # noqa: PLC0415
        from ctypes import wintypes  # noqa: PLC0415

        TH32CS_SNAPPROCESS = 0x00000002

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        processes: list[ProcessInfo] = []
        kernel32 = ctypes.windll.kernel32
        h_snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if h_snapshot == -1:
            return processes

        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if kernel32.Process32FirstW(h_snapshot, ctypes.byref(pe)):
                while True:
                    pid = pe.th32ProcessID
                    name = pe.szExeFile
                    processes.append(ProcessInfo(pid=pid, name=name, cmdline=name))
                    if not kernel32.Process32NextW(h_snapshot, ctypes.byref(pe)):
                        break
        finally:
            kernel32.CloseHandle(h_snapshot)
        return processes
    
    def find_process(self, name_substring: str) -> list[ProcessInfo]:
        """Find processes whose name or cmdline contains the given substring."""
        target = name_substring.lower()
        return [
            p for p in self.list_processes()
            if target in p.name.lower() or target in p.cmdline.lower()
        ]
    
    def register_watcher(self, name: str, callback: Callable[[ProcessInfo], None]) -> None:
        """Register a callback for when a matching process is found during poll()."""
        self._watchers[name] = callback
    
    def unregister_watcher(self, name: str) -> None:
        self._watchers.pop(name, None)
    
    def poll(self, name_substring: str) -> list[ProcessInfo]:
        """Poll for matching processes and invoke registered watchers."""
        matches = self.find_process(name_substring)
        if matches:
            for watcher in self._watchers.values():
                try:
                    for match in matches:
                        watcher(match)
                except Exception:
                    logger.exception("Watcher error")
        return matches
