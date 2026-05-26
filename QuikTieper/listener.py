from __future__ import annotations

from pynput import keyboard

from QuikTieper.launcher import AppLauncher, Binding, write_debug_log


SPECIAL_KEYS = {
    keyboard.Key.alt: "alt",
    keyboard.Key.alt_l: "alt",
    keyboard.Key.alt_r: "alt",
    keyboard.Key.ctrl: "ctrl",
    keyboard.Key.ctrl_l: "ctrl",
    keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.shift: "shift",
    keyboard.Key.shift_l: "shift",
    keyboard.Key.shift_r: "shift",
    keyboard.Key.cmd: "cmd",
    keyboard.Key.cmd_l: "cmd",
    keyboard.Key.cmd_r: "cmd",
    keyboard.Key.space: "space",
    keyboard.Key.enter: "enter",
    keyboard.Key.tab: "tab",
    keyboard.Key.esc: "esc",
}


def normalize_key(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    if key in SPECIAL_KEYS:
        return SPECIAL_KEYS[key]
    if isinstance(key, keyboard.KeyCode) and key.char:
        return key.char.lower()
    return None

class ChordListener:
    def __init__(self, bindings: list[Binding]) -> None:
        self.launcher = AppLauncher(bindings)
        self.pressed_keys: set[str] = set()
        self._listener: keyboard.Listener | None = None

    def run(self) -> None:
        self.start()
        if self._listener is not None:
            self._listener.join()

    def start(self) -> None:
        if self._listener is not None:
            return

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is None:
            return

        self._listener.stop()
        self._listener = None
        self.pressed_keys.clear()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        normalized = normalize_key(key)
        if normalized is None:
            return

        self.pressed_keys.add(normalized)
        write_debug_log(f"key press: {normalized}; pressed={sorted(self.pressed_keys)}")
        for binding in self.launcher.trigger_matches(self.pressed_keys):
            self.launcher.launch(binding)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        normalized = normalize_key(key)
        if normalized is not None:
            self.pressed_keys.discard(normalized)
            write_debug_log(f"key release: {normalized}; pressed={sorted(self.pressed_keys)}")
