from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from CamComs.instructions import validate_instruction
from QuikTieper.launcher import run_fiona_command, run_instruction


DEFAULT_ALLOWED_ACTIONS = frozenset({"press", "click", "move", "launch_binding", "text", "macro"})


class RemoteActionError(ValueError):
    """Raised when a remote instruction is not allowed or cannot run."""


@dataclass(frozen=True)
class RemoteActionResult:
    action: str
    detail: str
    executed: bool


class RemoteActionRunner:
    def __init__(self, *, allowed_actions: set[str] | frozenset[str] = DEFAULT_ALLOWED_ACTIONS, dry_run: bool = False) -> None:
        self.allowed_actions = frozenset(allowed_actions)
        self.dry_run = dry_run

    def run(self, instruction: dict[str, Any]) -> RemoteActionResult:
        validated = validate_instruction(instruction)
        action = validated["type"]
        if action not in self.allowed_actions:
            raise RemoteActionError(f"remote action is not allowed: {action}")

        if action == "press":
            keys = [str(key).strip().lower() for key in validated["keys"]]
            command = "ydotool key " + " ".join(_ydotool_key_sequence(keys))
            return self._run_shell(action, "+".join(keys), command)

        if action == "click":
            button = str(validated["button"])
            if "x" in validated and "y" in validated:
                self._run_pointer_move(validated["x"], validated["y"])
            return self._run_fiona(action, button, f"mouse-{button}-click")

        if action == "move":
            x_pos = int(validated["x"])
            y_pos = int(validated["y"])
            self._run_pointer_move(x_pos, y_pos)
            return RemoteActionResult(action, f"{x_pos},{y_pos}", not self.dry_run)

        if action == "launch_binding":
            name = str(validated["name"]).strip()
            return RemoteActionResult(action, name, False)

        if action == "text":
            value = str(validated["value"])
            return self._run_shell(action, value, f"ydotool type {subprocess.list2cmdline([value])}")

        if action == "macro":
            steps = validated["steps"]
            results = [self.run(step) for step in steps]
            return RemoteActionResult(action, f"{len(results)} step(s)", any(result.executed for result in results))

        raise RemoteActionError(f"unsupported remote action: {action}")

    def _run_pointer_move(self, x_pos: int, y_pos: int) -> None:
        if not self.dry_run:
            run_instruction(f"mouse:{x_pos},{y_pos}")

    def _run_fiona(self, action: str, detail: str, command: str) -> RemoteActionResult:
        if not self.dry_run:
            run_fiona_command(command)
        return RemoteActionResult(action, detail, not self.dry_run)

    def _run_shell(self, action: str, detail: str, command: str) -> RemoteActionResult:
        if not self.dry_run:
            subprocess.Popen(["bash", "-lc", command])
        return RemoteActionResult(action, detail, not self.dry_run)


def _ydotool_key_sequence(keys: list[str]) -> list[str]:
    codes = [_KEY_CODES.get(key) for key in keys]
    if any(code is None for code in codes):
        missing = [key for key, code in zip(keys, codes, strict=False) if code is None]
        raise RemoteActionError(f"unsupported key(s): {', '.join(missing)}")
    down = [f"{code}:1" for code in codes if code is not None]
    up = [f"{code}:0" for code in reversed(codes) if code is not None]
    return [*down, *up]


_KEY_CODES = {
    "a": 30,
    "b": 48,
    "c": 46,
    "d": 32,
    "e": 18,
    "f": 33,
    "g": 34,
    "h": 35,
    "i": 23,
    "j": 36,
    "k": 37,
    "l": 38,
    "m": 50,
    "n": 49,
    "o": 24,
    "p": 25,
    "q": 16,
    "r": 19,
    "s": 31,
    "t": 20,
    "u": 22,
    "v": 47,
    "w": 17,
    "x": 45,
    "y": 21,
    "z": 44,
    "alt": 56,
    "ctrl": 29,
    "shift": 42,
    "space": 57,
    "enter": 28,
    "tab": 15,
    "esc": 1,
}
