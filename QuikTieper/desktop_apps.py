from __future__ import annotations

import configparser
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DESKTOP_APP_DIRS = (
    Path.home() / ".local" / "share" / "applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
)

DEFAULT_K_PREFIX_ALLOWLIST = frozenset(
    {
        "k3b",
        "kaddressbook",
        "kalarm",
        "kalm",
        "kamoso",
        "kapptemplate",
        "karbon",
        "kasts",
        "kate",
        "kbackup",
        "kcachegrind",
        "kcalc",
        "kcharselect",
        "kcolorchooser",
        "kde connect",
        "kde connect indicator",
        "kde connect sms",
        "kde itinerary",
        "kde marble",
        "kde osm indoor map",
        "kde partition manager",
        "kde system settings",
        "kdebugsettings",
        "kdenlive",
        "kdevelop",
        "kdevelop (pick session)",
        "kdiskfree",
        "keysmith",
        "kfind",
        "kget",
        "kgpg",
        "kgraphviewer",
        "kicad",
        "kicad gerber viewer",
        "kicad image converter",
        "kicad pcb calculator",
        "kicad pcb editor (standalone)",
        "kicad schematic editor (standalone)",
        "kimagemapeditor",
        "kirigami gallery",
        "kitty",
        "kleopatra",
        "kmag",
        "kmail",
        "kmail header theme editor",
        "kmail import wizard",
        "kmix",
        "kmousetool",
        "kmouth",
        "kmplot",
        "kolourpaint",
        "kompare",
        "kongress",
        "konqueror",
        "konsole",
        "kontact",
        "kontrast",
        "konversation",
        "korganizer",
        "krdc",
        "krfb",
        "kruler",
        "ksystemlog",
        "kteatime",
        "ktimer",
        "ktnef",
        "ktorrent",
        "ktrip",
        "kuiviewer",
        "kwalletmanager",
        "kwave sound editor",
        "kwikdisk",
        "kwrite",
    }
)
DEFAULT_CATEGORY_DENYLIST = frozenset(
    {
        "ArcadeGame",
        "BoardGame",
        "DesktopSettings",
        "Education",
        "Game",
        "HardwareSettings",
        "KidsGame",
        "LogicGame",
        "Settings",
        "StrategyGame",
        "X-GNOME-AccountSettings",
        "X-GNOME-ConnectivitySettings",
        "X-GNOME-DevicesSettings",
        "X-GNOME-PersonalizationSettings",
        "X-GNOME-Settings-Panel",
        "X-GNOME-SystemSettings",
    }
)
DEFAULT_NAME_ALLOWLIST = frozenset(
    {
        "Advanced Network Configuration",
        "AppImageLauncher Settings",
        "Bluetooth Adapters",
        "Bluetooth Manager",
        "GNOME System Monitor",
        "KDE Connect",
        "KDE Connect Indicator",
        "KDE Connect SMS",
        "KDE Partition Manager",
        "KDE System Settings",
        "NVIDIA X Server Settings",
        "System Monitor",
        "System Settings",
        "Tweaks",
    }
)
DEFAULT_NAME_DENYLIST = frozenset(
    {
        "About",
        "About iTunes",
        "Access Prompt",
        "Account authentication",
        "Agent Configuration Dialog",
        "Apple Software Update",
        "AutoHotkey Window Spy",
        "Background Services",
        "Bookmarks",
        "Breeze Widget Style",
        "Breeze Window Decoration",
        "CDDB Retrieval",
        "Color Management",
        "Connection Preferences",
        "DAV Groupware",
        "Date & Time",
        "Day-Night Cycle",
        "Default Applications",
        "Desktop Effects",
        "Desktop Session",
        "Device Actions",
        "Digital Camera",
        "Drawing Tablet",
        "Emails",
        "Emoji Choice",
        "Energy",
        "Events and Tasks Reminders",
        "Evolution Data Server OAuth2 Handler",
        "File Associations",
        "File Search",
        "File Sharing",
        "File Type Editor",
        "Font Management",
        "GNOME OAuth2 Handler",
        "Game Controller",
        "General Behavior",
        "Geoclue Demo agent",
        "Global Theme",
        "Google Groupware",
        "Graphics Tablets",
        "Gwenview Importer",
        "Menu Editor",
        "Parental Controls",
        "Rygel Preferences",
        "Uninstall",
    }
)


@dataclass(frozen=True)
class DesktopApp:
    name: str
    command: str
    desktop_id: str
    window_match: str
    categories: tuple[str, ...] = ()

    def to_config_app(self) -> dict:
        return {
            "name": self.name,
            "window_match": self.window_match,
            "launch": {
                "name": "launch",
                "keys": [],
                "cmd": self.command,
                "instruction": "",
                "fiona_cmds": [],
                "cooldown_seconds": 0.8,
            },
            "shortcuts": [],
        }


def discover_desktop_apps(
    app_dirs: Iterable[Path] = DESKTOP_APP_DIRS,
    *,
    skip_unapproved_k_apps: bool = True,
    k_prefix_allowlist: frozenset[str] = DEFAULT_K_PREFIX_ALLOWLIST,
    skip_low_value_apps: bool = True,
) -> list[DesktopApp]:
    apps: dict[str, DesktopApp] = {}
    for app_dir in app_dirs:
        if not app_dir.is_dir():
            continue
        for desktop_file in sorted(app_dir.rglob("*.desktop")):
            app = desktop_app_from_file(desktop_file)
            if app is None:
                continue
            if skip_unapproved_k_apps and _is_unapproved_k_app(app, k_prefix_allowlist):
                continue
            if skip_low_value_apps and _is_low_value_app(app):
                continue
            apps.setdefault(app.name.lower(), app)
    return sorted(apps.values(), key=lambda app: app.name.lower())


def desktop_app_from_file(path: Path) -> DesktopApp | None:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error:
        return None
    if not parser.has_section("Desktop Entry"):
        return None

    entry = parser["Desktop Entry"]
    if entry.get("Type", "Application") != "Application":
        return None
    if _truthy(entry.get("NoDisplay", "false")) or _truthy(entry.get("Hidden", "false")):
        return None

    name = entry.get("Name", "").strip()
    exec_line = entry.get("Exec", "").strip()
    if not name or not exec_line:
        return None

    command = clean_desktop_exec(exec_line)
    if not command:
        return None

    window_match = entry.get("StartupWMClass", "").strip().lower() or _command_basename(command)
    return DesktopApp(
        name=_clean_name(name),
        command=command,
        desktop_id=path.stem,
        window_match=window_match,
        categories=tuple(category for category in entry.get("Categories", "").split(";") if category),
    )


def merge_desktop_apps(config: dict, desktop_apps: Iterable[DesktopApp]) -> tuple[dict, int]:
    merged = {"apps": list(config.get("apps", []))}
    existing_names = {str(app.get("name", "")).strip().lower() for app in merged["apps"]}
    added = 0
    for app in desktop_apps:
        if app.name.lower() in existing_names:
            continue
        merged["apps"].append(app.to_config_app())
        existing_names.add(app.name.lower())
        added += 1
    return merged, added


def clean_desktop_exec(exec_line: str) -> str:
    cleaned = re.sub(r"\s+%[fFuUdDnNickvm]", "", exec_line).strip()
    cleaned = re.sub(r"%[fFuUdDnNickvm]", "", cleaned).strip()
    try:
        parts = shlex.split(cleaned)
    except ValueError:
        return cleaned
    return shlex.join(parts)


def _command_basename(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    if not parts:
        return ""
    return Path(parts[0]).name.lower()


def _clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _is_unapproved_k_app(app: DesktopApp, allowlist: frozenset[str]) -> bool:
    normalized = app.name.strip().lower()
    if not normalized.startswith("k"):
        return False
    return normalized not in allowlist


def _is_low_value_app(app: DesktopApp) -> bool:
    if app.name in DEFAULT_NAME_ALLOWLIST:
        return False
    if app.name in DEFAULT_NAME_DENYLIST:
        return True
    if app.name.startswith("About "):
        return True
    if app.name.endswith(" Demo") or " Demo " in app.name:
        return True
    if "Uninstall" in app.name:
        return True
    if set(app.categories).intersection(DEFAULT_CATEGORY_DENYLIST):
        return True
    return False
