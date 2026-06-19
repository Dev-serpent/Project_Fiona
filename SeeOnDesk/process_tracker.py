"""Process tracking utilities for monitoring foreground and background processes."""

from __future__ import annotations

import logging
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
    
    Uses /proc for lightweight polling (no psutil dependency).
    """
    
    def __init__(self):
        self._watchers: dict[str, Callable[[ProcessInfo], None]] = {}
    
    def list_processes(self) -> list[ProcessInfo]:
        """List all running processes from /proc."""
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
