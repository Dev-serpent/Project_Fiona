from __future__ import annotations

import threading
import time
from typing import Callable

from FionaCore.notifications import Notification, notify_result
from FionaCore.actions import ActionResult

class SystemWatcher:
    """
    Background thread that monitors system events and triggers callbacks.
    """
    def __init__(self, name: str, interval: float, check_fn: Callable[[], ActionResult | None]) -> None:
        self.name = name
        self.interval = interval
        self.check_fn = check_fn
        self.running = False
        self._thread: threading.Thread | None = None

    def start(self, callback: Callable[[ActionResult], None]) -> None:
        self.running = True
        self._thread = threading.Thread(target=self._run, args=(callback,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False

    def _run(self, callback: Callable[[ActionResult], None]) -> None:
        while self.running:
            result = self.check_fn()
            if result:
                callback(result)
            time.sleep(self.interval)

def check_cpu_load() -> ActionResult | None:
    # Simplified mock for demonstration
    # In a real implementation, this would use psutil or TerminalAssist logic
    return None

def check_build_errors() -> ActionResult | None:
    # Mocks monitoring a log file or CmdTrace for "ERROR"
    return None

class WatcherService:
    def __init__(self) -> None:
        self.watchers = [
            SystemWatcher("cpu", 60.0, check_cpu_load),
            SystemWatcher("build", 5.0, check_build_errors),
        ]

    def start_all(self, callback: Callable[[ActionResult], None]) -> None:
        for w in self.watchers:
            w.start(callback)
