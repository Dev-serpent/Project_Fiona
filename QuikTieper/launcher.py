from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from wayland_automation import Mouse as WaylandMouse
except ImportError:
    WaylandMouse = None


_LAST_POINTER_TARGET: tuple[int, int] | None = None
_YDOTOOLD_START_ATTEMPTED = False
_WAYLAND_MOUSE: object | None = None
DEBUG_LOG_PATH = Path.home() / ".config" / "fiona" / "debug.log"
FALLBACK_DEBUG_LOG_PATH = Path("/tmp/fiona-debug.log")


@dataclass(frozen=True)
class Binding:
    name: str
    keys: frozenset[str]
    command: str
    instruction: str = ""
    fiona_cmds: tuple[str, ...] = ()
    cooldown_seconds: float = 0.8
    app_name: str | None = None
    window_match: str | None = None
    binding_type: str = "launch"


def write_debug_log(message: str) -> None:
    log_line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
    for path in (DEBUG_LOG_PATH, FALLBACK_DEBUG_LOG_PATH):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(log_line)
            return
        except OSError:
            continue


if WaylandMouse is not None:
    logging.getLogger("wayland_automation.mouse_controller").setLevel(logging.ERROR)


def get_mouse_location() -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    x_match = re.search(r"x:(\d+)", result.stdout)
    y_match = re.search(r"y:(\d+)", result.stdout)
    if x_match is None or y_match is None:
        return None
    return int(x_match.group(1)), int(y_match.group(1))


def run_instruction(instruction: str) -> None:
    global _LAST_POINTER_TARGET
    raw = instruction.strip()
    if not raw:
        return

    if raw.startswith("mouse:"):
        coords = raw.removeprefix("mouse:").split(",")
        if len(coords) != 2:
            return
        x_pos = int(coords[0].strip())
        y_pos = int(coords[1].strip())
        _LAST_POINTER_TARGET = (x_pos, y_pos)
        write_debug_log(f"instruction mouse target set to {x_pos},{y_pos}")
        run_pointer_backends(
            x=x_pos,
            y=y_pos,
            button=None,
            x11_command=["xdotool", "mousemove", str(x_pos), str(y_pos)],
            wayland_command=["ydotool", "mousemove", "--absolute", str(x_pos), str(y_pos)],
        )


def run_fiona_command(command: str) -> None:
    normalized = command.strip().lower()
    write_debug_log(f"running fiona command {normalized}")
    if normalized == "mouse-left-click":
        x_pos = _LAST_POINTER_TARGET[0] if _LAST_POINTER_TARGET is not None else None
        y_pos = _LAST_POINTER_TARGET[1] if _LAST_POINTER_TARGET is not None else None
        run_pointer_backends(
            x=x_pos,
            y=y_pos,
            button="left",
            x11_command=["xdotool", "click", "1"],
            wayland_command=["ydotool", "click", "0xC0"],
        )
    elif normalized == "mouse-right-click":
        x_pos = _LAST_POINTER_TARGET[0] if _LAST_POINTER_TARGET is not None else None
        y_pos = _LAST_POINTER_TARGET[1] if _LAST_POINTER_TARGET is not None else None
        run_pointer_backends(
            x=x_pos,
            y=y_pos,
            button="right",
            x11_command=["xdotool", "click", "3"],
            wayland_command=["ydotool", "click", "0xC1"],
        )


def run_pointer_backends(
    x: int | None,
    y: int | None,
    button: str | None,
    x11_command: list[str],
    wayland_command: list[str],
) -> bool:
    commands_to_try: list[list[str]] = []
    prefer_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    if shutil.which(wayland_command[0]):
        ensure_ydotoold_running()
        commands_to_try.append(wayland_command)
    if shutil.which(x11_command[0]):
        if prefer_wayland:
            commands_to_try.append(x11_command)
        else:
            commands_to_try.insert(0, x11_command)

    for command in commands_to_try:
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True)
        except OSError:
            write_debug_log(f"pointer backend os error for {' '.join(command)}")
            continue
        if result.returncode == 0:
            write_debug_log(f"pointer backend succeeded: {' '.join(command)}")
            return True
        write_debug_log(f"pointer backend failed ({result.returncode}): {' '.join(command)}")

    if WaylandMouse is not None and x is not None and y is not None:
        try:
            get_wayland_mouse().click(x, y, button if button is not None else "nothing")
            write_debug_log(f"wayland_automation handled pointer action x={x} y={y} button={button}")
            return True
        except Exception:
            write_debug_log(f"wayland_automation failed for x={x} y={y} button={button}")
            pass
    return False


def get_wayland_mouse() -> object:
    global _WAYLAND_MOUSE
    if _WAYLAND_MOUSE is None:
        if WaylandMouse is None:
            raise RuntimeError("wayland-automation is not installed")
        _WAYLAND_MOUSE = WaylandMouse()
        write_debug_log("initialized cached wayland_automation mouse client")
    return _WAYLAND_MOUSE


def ydotool_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime_dir) / ".ydotool_socket"


def ensure_ydotoold_running() -> None:
    global _YDOTOOLD_START_ATTEMPTED
    socket_path = ydotool_socket_path()
    if socket_path.exists():
        return
    if _YDOTOOLD_START_ATTEMPTED:
        return

    _YDOTOOLD_START_ATTEMPTED = True
    startup_commands: list[list[str]] = []
    if shutil.which("pkexec"):
        startup_commands.append(["pkexec", "ydotoold"])
    if shutil.which("sudo"):
        startup_commands.append(["sudo", "-n", "ydotoold"])
    startup_commands.append(["ydotoold"])

    for command in startup_commands:
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            write_debug_log(f"attempted to start ydotoold with: {' '.join(command)}")
        except OSError:
            write_debug_log(f"failed to spawn ydotoold starter: {' '.join(command)}")
            continue

        for _ in range(10):
            if socket_path.exists():
                write_debug_log(f"ydotoold socket available at {socket_path}")
                return
            time.sleep(0.1)

    write_debug_log("ydotoold socket did not appear after startup attempts")


def should_prefer_kdotool() -> bool:
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "").lower()
    return "kde" in desktop or "plasma" in desktop


def get_active_window_classes_kdotool() -> set[str]:
    if shutil.which("kdotool") is None:
        return set()

    try:
        active_window = subprocess.run(
            ["kdotool", "getactivewindow"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return set()

    window_id = active_window.stdout.strip()
    if not window_id:
        return set()

    try:
        class_result = subprocess.run(
            ["kdotool", "getwindowclassname", window_id],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return set()

    values = {line.strip().lower() for line in class_result.stdout.splitlines() if line.strip()}
    if values:
        write_debug_log(f"kdotool active classes={sorted(values)}")
    return values


def get_active_window_classes_xprop() -> set[str]:
    if shutil.which("xprop") is None:
        return set()

    try:
        active_window = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return set()

    match = re.search(r"window id # (0x[0-9a-fA-F]+)", active_window.stdout)
    if match is None:
        return set()

    window_id = match.group(1)
    try:
        window_props = subprocess.run(
            ["xprop", "-id", window_id, "WM_CLASS"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return set()

    values = {value.lower() for value in re.findall(r'"([^"]+)"', window_props.stdout)}
    if values:
        write_debug_log(f"xprop active classes={sorted(values)}")
    return values


def get_active_window_classes() -> set[str]:
    if should_prefer_kdotool():
        values = get_active_window_classes_kdotool()
        if values:
            return values
        write_debug_log("kdotool active-window lookup returned no classes; falling back to xprop")

    return get_active_window_classes_xprop()


class AppLauncher:
    def __init__(self, bindings: list[Binding]) -> None:
        self.bindings = bindings
        self._last_triggered: dict[str, float] = {}

    def trigger_matches(self, pressed_keys: set[str]) -> list[Binding]:
        matches: list[Binding] = []
        active_classes: set[str] | None = None
        for binding in self.bindings:
            if not binding.keys.issubset(pressed_keys) or not self._ready(binding):
                continue
            if binding.window_match:
                if active_classes is None:
                    active_classes = get_active_window_classes()
                expected = binding.window_match.lower()
                if not any(expected in value for value in active_classes):
                    write_debug_log(
                        f"binding {binding.name} skipped; active classes={sorted(active_classes)} expected={expected}"
                    )
                    continue
            write_debug_log(f"binding matched: {binding.name} keys={sorted(binding.keys)}")
            matches.append(binding)
        return matches

    def launch(self, binding: Binding) -> None:
        write_debug_log(
            f"launching {binding.name} cmd={binding.command!r} instruction={binding.instruction!r} "
            f"fiona_cmds={list(binding.fiona_cmds)!r}"
        )
        if binding.instruction:
            run_instruction(binding.instruction)
        for internal_command in binding.fiona_cmds:
            run_fiona_command(internal_command)
        if binding.command.strip():
            subprocess.Popen(["bash", "-lc", binding.command])
            write_debug_log(f"spawned shell command for {binding.name}: {binding.command}")
        self._last_triggered[binding.name] = time.monotonic()

    def _ready(self, binding: Binding) -> bool:
        last_seen = self._last_triggered.get(binding.name, 0.0)
        return (time.monotonic() - last_seen) >= binding.cooldown_seconds
