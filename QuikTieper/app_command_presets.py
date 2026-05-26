from __future__ import annotations

import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

from QuikTieper.config import infer_window_match
from QuikTieper.key_assignment import assign_missing_launch_keys


@dataclass(frozen=True)
class AppCommandPreset:
    display_name: str
    aliases: tuple[str, ...]
    commands: tuple[str, ...]


APP_COMMAND_PRESETS = (
    AppCommandPreset("Brave", ("Brave", "brave"), ("brave",)),
    AppCommandPreset("VS Code", ("VS Code", "vs-code", "Visual Studio Code"), ("code",)),
    AppCommandPreset("Terminal", ("Terminal",), ("konsole", "kitty")),
    AppCommandPreset("Files", ("Files", "Dolphin"), ("dolphin",)),
    AppCommandPreset("Accessibility Inspector", ("Accessibility Inspector",), ("accessibilityinspector",)),
    AppCommandPreset("Advanced Network Configuration", ("Advanced Network Configuration",), ("nm-connection-editor",)),
    AppCommandPreset("Akonadi Console", ("Akonadi Console",), ("akonadiconsole",)),
    AppCommandPreset("Akregator", ("Akregator",), ("akregator",)),
    AppCommandPreset("Alligator", ("Alligator",), ("alligator",)),
    AppCommandPreset("Android Studio", ("Android Studio",), ("android-studio",)),
    AppCommandPreset("Angelfish", ("Angelfish",), ("angelfish",)),
    AppCommandPreset("Arduino IDE", ("Arduino IDE", "Arduino IDE (2.3.6)"), ("arduino-ide",)),
    AppCommandPreset("Ark", ("Ark",), ("ark",)),
    AppCommandPreset("Authenticator", ("Authenticator",), ("authenticator",)),
    AppCommandPreset("Bluetooth Manager", ("Bluetooth Manager",), ("blueman-manager",)),
    AppCommandPreset("Boxes", ("Boxes",), ("gnome-boxes",)),
    AppCommandPreset("btop++", ("btop++", "Btop++"), ("btop",)),
    AppCommandPreset("Calculator", ("Calculator", "KCalc"), ("kcalc",)),
    AppCommandPreset("Clocks", ("Clocks",), ("kclock",)),
    AppCommandPreset("CMake GUI", ("CMake GUI", "CMake"), ("cmake-gui",)),
    AppCommandPreset("Console", ("Console",), ("kgx",)),
    AppCommandPreset("Document Viewer", ("Document Viewer", "Okular"), ("okular",)),
    AppCommandPreset("Dragon Player", ("Dragon Player",), ("dragon",)),
    AppCommandPreset("Elisa", ("Elisa",), ("elisa",)),
    AppCommandPreset("Falkon", ("Falkon",), ("falkon",)),
    AppCommandPreset("File Roller", ("File Roller", "Archive Manager"), ("file-roller",)),
    AppCommandPreset("Filelight", ("Filelight",), ("filelight",)),
    AppCommandPreset("gedit", ("gedit", "Text Editor (gedit)"), ("gedit",)),
    AppCommandPreset("GitHub Desktop", ("GitHub Desktop",), ("github-desktop",)),
    AppCommandPreset("GIMP", ("GIMP", "GNU Image Manipulation Program"), ("gimp",)),
    AppCommandPreset("Google Chrome", ("Google Chrome",), ("google-chrome-stable",)),
    AppCommandPreset("Gwenview", ("Gwenview",), ("gwenview",)),
    AppCommandPreset("Help", ("Help",), ("yelp",)),
    AppCommandPreset("Htop", ("Htop",), ("htop",)),
    AppCommandPreset("Image Viewer", ("Image Viewer",), ("gwenview", "loupe")),
    AppCommandPreset("Jupyter Notebook", ("Jupyter Notebook",), ("jupyter-notebook",)),
    AppCommandPreset("JupyterLab", ("JupyterLab",), ("jupyter-lab",)),
    AppCommandPreset("K3b", ("K3b",), ("k3b",)),
    AppCommandPreset("Kate", ("Kate",), ("kate",)),
    AppCommandPreset("KCalc", ("KCalc",), ("kcalc",)),
    AppCommandPreset("KDE Connect", ("KDE Connect",), ("kdeconnect-app",)),
    AppCommandPreset("KDE System Settings", ("KDE System Settings", "System Settings"), ("systemsettings",)),
    AppCommandPreset("Kdenlive", ("Kdenlive",), ("kdenlive",)),
    AppCommandPreset("KDevelop", ("KDevelop",), ("kdevelop",)),
    AppCommandPreset("KiCad", ("KiCad",), ("kicad",)),
    AppCommandPreset("kitty", ("kitty",), ("kitty",)),
    AppCommandPreset("KMail", ("KMail",), ("kmail",)),
    AppCommandPreset("KolourPaint", ("KolourPaint",), ("kolourpaint",)),
    AppCommandPreset("Konqueror", ("Konqueror",), ("konqueror",)),
    AppCommandPreset("Konsole", ("Konsole",), ("konsole",)),
    AppCommandPreset("Kontact", ("Kontact",), ("kontact",)),
    AppCommandPreset("KOrganizer", ("KOrganizer",), ("korganizer",)),
    AppCommandPreset("KRDC", ("KRDC",), ("krdc",)),
    AppCommandPreset("KRuler", ("KRuler",), ("kruler",)),
    AppCommandPreset("KSystemLog", ("KSystemLog",), ("ksystemlog",)),
    AppCommandPreset("KTorrent", ("KTorrent",), ("ktorrent",)),
    AppCommandPreset("KWrite", ("KWrite",), ("kwrite",)),
    AppCommandPreset("LM Studio", ("LM Studio", "LM Studio (0.3.39)"), ("lmstudio",)),
    AppCommandPreset("Maps", ("Maps",), ("plasma-openstreetmap", "gnome-maps")),
    AppCommandPreset("MCreator", ("MCreator",), ("mcreator",)),
    AppCommandPreset("mpv", ("mpv", "mpv Media Player"), ("mpv",)),
    AppCommandPreset("Neovim", ("Neovim", "nvim"), ("nvim",)),
    AppCommandPreset("NVIDIA Settings", ("NVIDIA Settings", "NVIDIA X Server Settings"), ("nvidia-settings",)),
    AppCommandPreset("OBS Studio", ("OBS Studio",), ("obs",)),
    AppCommandPreset("Okular", ("Okular",), ("okular",)),
    AppCommandPreset("Photos / Koko", ("Photos / Koko", "Photos", "Koko"), ("koko",)),
    AppCommandPreset("PyCharm CE", ("PyCharm CE", "PyCharm Community Edition"), ("pycharm-community", "pycharm")),
    AppCommandPreset("Qt Assistant", ("Qt Assistant",), ("assistant6",)),
    AppCommandPreset("Qt Designer", ("Qt Designer", "Qt Widgets Designer"), ("designer6",)),
    AppCommandPreset("Rofi", ("Rofi",), ("rofi",)),
    AppCommandPreset("Screenshot", ("Screenshot",), ("spectacle",)),
    AppCommandPreset("Skanlite", ("Skanlite",), ("skanlite",)),
    AppCommandPreset("Software", ("Software",), ("plasma-discover",)),
    AppCommandPreset("System Monitor", ("System Monitor",), ("plasma-systemmonitor",)),
    AppCommandPreset("Spectacle", ("Spectacle",), ("spectacle",)),
    AppCommandPreset("Text Editor", ("Text Editor",), ("kate", "kwrite")),
    AppCommandPreset("Tweaks", ("Tweaks",), ("systemsettings",)),
    AppCommandPreset("Virtual Machine Manager", ("Virtual Machine Manager",), ("virt-manager",)),
    AppCommandPreset("VLC", ("VLC", "VLC media player"), ("vlc",)),
    AppCommandPreset("Web / Epiphany", ("Web / Epiphany", "Web"), ("epiphany",)),
    AppCommandPreset("Webex", ("Webex",), ("CiscoCollabHost",)),
    AppCommandPreset("Yakuake", ("Yakuake",), ("yakuake",)),
    AppCommandPreset("Yazi", ("Yazi",), ("yazi",)),
    AppCommandPreset("Zellij", ("Zellij",), ("zellij",)),
)


def apply_app_command_presets(config: dict) -> tuple[dict, list[dict[str, str]], int, int]:
    apps = [dict(app) for app in config.get("apps", [])]
    index = {_app_identity(str(app.get("name", ""))): app for app in apps}
    changes: list[dict[str, str]] = []
    added = 0

    for preset in APP_COMMAND_PRESETS:
        matched_apps = _find_existing_apps(index, preset)
        current_command = str(matched_apps[0].get("launch", {}).get("cmd", "")) if matched_apps else ""
        command = _select_command(preset.commands, current_command)
        if not matched_apps:
            app = _new_app_entry(preset.display_name, command)
            apps.append(app)
            index[_app_identity(preset.display_name)] = app
            added += 1
            changes.append({"app": preset.display_name, "old": "", "new": command})
            continue

        for app in matched_apps:
            launch = dict(app.get("launch", {}))
            old_command = str(launch.get("cmd", ""))
            if old_command == command:
                continue
            launch["cmd"] = command
            app["launch"] = launch
            app["window_match"] = infer_window_match(command)
            changes.append({"app": str(app.get("name", preset.display_name)), "old": old_command, "new": command})

    updated, assigned_keys = assign_missing_launch_keys({"apps": apps})
    return updated, changes, added, assigned_keys


def _find_existing_apps(index: dict[str, dict], preset: AppCommandPreset) -> list[dict]:
    apps = []
    seen = set()
    for alias in preset.aliases:
        app = index.get(_app_identity(alias))
        if app is not None and id(app) not in seen:
            apps.append(app)
            seen.add(id(app))
    return apps


def _new_app_entry(name: str, command: str) -> dict:
    return {
        "name": name,
        "window_match": infer_window_match(command),
        "launch": {"name": "launch", "keys": [], "cmd": command},
        "shortcuts": [],
    }


def _select_command(commands: tuple[str, ...], current_command: str) -> str:
    for command in commands:
        if _command_exists(command):
            return command
    if current_command and _command_exists(current_command):
        return current_command
    return commands[0]


def _command_exists(command: str) -> bool:
    try:
        executable = shlex.split(command)[0]
    except (IndexError, ValueError):
        return False
    path = Path(executable).expanduser()
    if path.is_absolute() and path.exists():
        return True
    return shutil.which(executable) is not None


def _app_identity(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())
