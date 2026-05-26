from __future__ import annotations

from collections.abc import Iterable

from QuikTieper.launcher import Binding


def parse_bindings(apps: Iterable[dict]) -> list[Binding]:
    bindings: list[Binding] = []
    for app in apps:
        app_name = app["name"]
        window_match = app.get("window_match", "")
        launch = app.get("launch", {})
        launch_keys = frozenset(key.lower() for key in launch.get("keys", []))
        if launch_keys:
            bindings.append(
                Binding(
                    name=f"{app_name}:launch",
                    keys=launch_keys,
                    command=launch.get("cmd") or launch.get("command", ""),
                    instruction=launch.get("instruction", ""),
                    fiona_cmds=tuple(launch.get("fiona_cmds", launch.get("quiktieper_cmds", []))),
                    cooldown_seconds=float(launch.get("cooldown_seconds", 0.8)),
                    app_name=app_name,
                    binding_type="launch",
                )
            )
        for shortcut in app.get("shortcuts", []):
            shortcut_keys = frozenset(key.lower() for key in shortcut.get("keys", []))
            if not shortcut_keys:
                continue
            bindings.append(
                Binding(
                    name=f"{app_name}:{shortcut['name']}",
                    keys=shortcut_keys,
                    command=shortcut.get("cmd") or shortcut.get("command", ""),
                    instruction=shortcut.get("instruction", ""),
                    fiona_cmds=tuple(shortcut.get("fiona_cmds", shortcut.get("quiktieper_cmds", []))),
                    cooldown_seconds=float(shortcut.get("cooldown_seconds", 0.8)),
                    app_name=app_name,
                    window_match=window_match,
                    binding_type="shortcut",
                )
            )
    return bindings
