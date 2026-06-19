"""Shared Fiona action, permission, notification, voice, and macro primitives."""

from __future__ import annotations

from .acl import (
    DEFAULT_ACL_RULES,
    SENDER_SCOPE_ORDER,
    SenderACLRule,
    resolve_sender_profile,
    resolve_sender_scope,
)
from .actions import ActionResult, ActionRouter, ActionSpec, default_action_specs
from .macro_engine import evaluate_condition, execute_step_with_waits, run_macro_steps
from .macros import DEFAULT_MACROS_PATH, MacroStep, load_macros, run_macro, save_macro
from .notifications import Notification, build_notification, notify_result
from .permissions import PermissionProfile, permission_allows
from .shell_safety import (
    DESTRUCTIVE_PATTERNS,
    ShellCommandError,
    check_command_safety,
    is_command_safe,
    safe_os_system,
    safe_popen_shell,
    safe_subprocess_run,
)
from .speech import speak
from .verification import (
    DEFAULT_VERIFICATION_PROMPT,
    DesktopVerificationPrompt,
    StdoutVerificationPrompt,
    VerificationPrompt,
    prompt_for_confirmation,
)
from .voice import VoiceCommand, parse_voice_command
from .voice_engine import WhisperEngine, quick_transcribe

__all__ = [
    "ActionResult",
    "ActionRouter",
    "ActionSpec",
    "DEFAULT_ACL_RULES",
    "DEFAULT_MACROS_PATH",
    "DEFAULT_VERIFICATION_PROMPT",
    "DESTRUCTIVE_PATTERNS",
    "DesktopVerificationPrompt",
    "MacroStep",
    "Notification",
    "PermissionProfile",
    "SENDER_SCOPE_ORDER",
    "SenderACLRule",
    "ShellCommandError",
    "StdoutVerificationPrompt",
    "VerificationPrompt",
    "VoiceCommand",
    "WhisperEngine",
    "build_notification",
    "check_command_safety",
    "default_action_specs",
    "evaluate_condition",
    "execute_step_with_waits",
    "is_command_safe",
    "load_macros",
    "notify_result",
    "parse_voice_command",
    "permission_allows",
    "prompt_for_confirmation",
    "quick_transcribe",
    "resolve_sender_profile",
    "resolve_sender_scope",
    "run_macro",
    "run_macro_steps",
    "safe_os_system",
    "safe_popen_shell",
    "safe_subprocess_run",
    "save_macro",
    "speak",
]
