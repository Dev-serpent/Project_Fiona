from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from .actions import ActionResult
from .speech import speak


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    urgency: str = "normal"

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "body": self.body, "urgency": self.urgency}


def build_notification(result: ActionResult) -> Notification:
    state = "OK" if result.ok else "FAILED"
    body = result.detail or result.stderr.strip() or result.stdout.strip() or "No details."
    urgency = "normal" if result.ok else "critical"
    return Notification(f"Fiona {state}: {result.action}", body[:240], urgency=urgency)


def _notify_desktop_linux(title: str, body: str, urgency: str) -> bool:
    """Linux desktop notification via ``notify-send``."""
    if not shutil.which("notify-send"):
        return False
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, title, body],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


def _notify_desktop_windows(title: str, body: str, urgency: str) -> bool:
    """Windows toast / balloon notification via ``plyer``."""
    try:
        from plyer import notification  # type: ignore[import-untyped]
        notification.notify(title=title, message=body, timeout=5)
        return True
    except Exception:
        return False


def _notify_desktop(title: str, body: str, urgency: str) -> bool:
    """Dispatch a desktop notification to the current platform."""
    if os.name == "nt":
        return _notify_desktop_windows(title, body, urgency)
    return _notify_desktop_linux(title, body, urgency)


def notify_result(result: ActionResult, *, mode: str = "stdout", use_speech: bool = False) -> Notification:
    notification = build_notification(result)
    if use_speech:
        speak(f"{notification.title}. {notification.body}")
    if mode == "silent":
        return notification
    if mode == "desktop":
        dispatched = _notify_desktop(notification.title, notification.body, notification.urgency)
        if not dispatched:
            print(f"{notification.title}: {notification.body}")
        return notification
    if mode == "stdout":
        print(f"{notification.title}: {notification.body}")
    return notification
