"""Shared Fiona action, permission, notification, voice, and macro primitives."""

from __future__ import annotations

from .actions import ActionResult, ActionRouter, ActionSpec, default_action_specs
from .macros import DEFAULT_MACROS_PATH, MacroStep, load_macros, run_macro, save_macro
from .notifications import Notification, build_notification, notify_result
from .permissions import PermissionProfile, permission_allows
from .voice import VoiceCommand, parse_voice_command

__all__ = [
    "ActionResult",
    "ActionRouter",
    "ActionSpec",
    "DEFAULT_MACROS_PATH",
    "MacroStep",
    "Notification",
    "PermissionProfile",
    "VoiceCommand",
    "build_notification",
    "default_action_specs",
    "load_macros",
    "notify_result",
    "parse_voice_command",
    "permission_allows",
    "run_macro",
    "save_macro",
]
