from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Binding:
    name: str
    keys: frozenset[str]
    command: str
    cooldown_seconds: float = 0.8


class AppLauncher:
    def __init__(self, bindings: list[Binding]) -> None:
        self.bindings = bindings
        self._last_triggered: dict[str, float] = {}

    def trigger_matches(self, pressed_keys: set[str]) -> list[Binding]:
        matches: list[Binding] = []
        for binding in self.bindings:
            if binding.keys.issubset(pressed_keys) and self._ready(binding):
                matches.append(binding)
        return matches

    def launch(self, binding: Binding) -> None:
        subprocess.Popen(["bash", "-lc", binding.command])
        self._last_triggered[binding.name] = time.monotonic()

    def _ready(self, binding: Binding) -> bool:
        last_seen = self._last_triggered.get(binding.name, 0.0)
        return (time.monotonic() - last_seen) >= binding.cooldown_seconds
