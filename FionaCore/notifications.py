from __future__ import annotations

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


def notify_result(result: ActionResult, *, mode: str = "stdout", use_speech: bool = False) -> Notification:
    notification = build_notification(result)
    if use_speech:
        speak(f"{notification.title}. {notification.body}")
    if mode == "silent":
        return notification
    if mode == "desktop" and shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "-u", notification.urgency, notification.title, notification.body],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return notification
    if mode in {"stdout", "desktop"}:
        print(f"{notification.title}: {notification.body}")
    return notification
