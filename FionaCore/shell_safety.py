"""Shell command safety validator — bans destructive commands.

This module provides a centralized blocklist-based safety layer for all
shell execution paths in Fiona. Every invocation of os.system(),
subprocess.Popen with shell=True, or subprocess.run with shell=True
MUST pass through this validator first.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from typing import Literal

# ---------------------------------------------------------------------------
# Blocklist — patterns that are NEVER allowed in any shell command.
# Each entry is a compiled regex that matches a destructive command pattern.
# ---------------------------------------------------------------------------

DESTRUCTIVE_PATTERNS: list[re.Pattern[str]] = [
    # rm -rf / or rm -rf /*  — root filesystem deletion
    re.compile(r'\brm\b.*\s+/\s*$', re.IGNORECASE),
    re.compile(r'\brm\b.*\s+/\*\s*$', re.IGNORECASE),
    # rm --no-preserve-root (dangerous even on subdirs)
    re.compile(r'\brm\b.*--no-preserve-root', re.IGNORECASE),
    # Chmod dangerous paths
    re.compile(r'\bchmod\s+(-r\s+)?(777|a=rwx|a\+x)\s+/', re.IGNORECASE),
    # Chown dangerous
    re.compile(r'\bchown\s+-r\s+[^:]+:[^ ]+\s+/', re.IGNORECASE),
    # mkfs / mkfs.* — formatting block devices
    re.compile(r'\bmkfs\b', re.IGNORECASE),
    re.compile(r'\bmkswap\b', re.IGNORECASE),
    # dd — dangerous block-level writes
    re.compile(r'\bdd\s+if=/dev/zero', re.IGNORECASE),
    re.compile(r'\bdd\s+of=/dev/sd', re.IGNORECASE),
    re.compile(r'\bdd\s+of=/dev/nvme', re.IGNORECASE),
    re.compile(r'\bdd\s+of=/dev/mmc', re.IGNORECASE),
    # Direct disk/partition writes via cat/echo redirect
    re.compile(r'\bcat\s+.+>\s*/dev/sd', re.IGNORECASE),
    re.compile(r'\bcat\s+.+>\s*/dev/nvme', re.IGNORECASE),
    re.compile(r'\becho\s+.+>\s*/dev/sd', re.IGNORECASE),
    re.compile(r'\becho\s+.+>\s*/dev/nvme', re.IGNORECASE),
    # > /dev/sd* (write to disk)
    re.compile(r'>\s*/dev/sd[a-z]'),
    re.compile(r'>\s*/dev/nvme\d'),
    # Wipe/erase commands
    re.compile(r'\bwipefs\b', re.IGNORECASE),
    re.compile(r'\bshred\s+', re.IGNORECASE),
    re.compile(r'\bbb\s*\(?dd|/dev/random\)?\s+of=', re.IGNORECASE),
    # fdisk / parted destructive operations
    re.compile(r'\bfdisk\s+/dev/sd', re.IGNORECASE),
    re.compile(r'\bparted\s+/dev/sd', re.IGNORECASE),
    # Poweroff / reboot with dangerous flags (force)
    re.compile(r'\bpoweroff\s+-f', re.IGNORECASE),
    re.compile(r'\breboot\s+-f', re.IGNORECASE),
    # Password/credential exposure
    re.compile(r'\bchmod\s+644\s+/etc/shadow', re.IGNORECASE),
    re.compile(r'\bchmod\s+644\s+/etc/gshadow', re.IGNORECASE),
    re.compile(r'\bchmod\s+644\s+/etc/passwd', re.IGNORECASE),
    # curl/wget pipe to bash (arbitrary remote execution)
    re.compile(r'\bcurl\s+-[a-z]*s[a-z]*[a-z]*\s+https?://.*\|?\s*(bash|sh)\b', re.IGNORECASE),
    re.compile(r'\bwget\s+-[a-z]*q[a-z]*[a-z]*\s+https?://.*\|?\s*(bash|sh)\b', re.IGNORECASE),
    # Direct bash/sh -c with curl/wget pipe
    re.compile(r'\b(bash|sh)\s+-c\s+["\'].*(curl|wget).*\||\|.*(bash|sh)\b', re.IGNORECASE),
]

# Common safe system commands for reference (not a blocklist, just informational)
DOCUMENTED_SAFE_COMMANDS: tuple[str, ...] = (
    "loginctl lock-session",
    "qdbus-qt5 org.kde.ksmserver /KSMServer logout",
    "gnome-screensaver-command -l",
    "gnome-session-quit",
    "systemctl suspend",
    "systemctl reboot",
    "systemctl poweroff",
    "systemctl --user",
    "journalctl",
)


class ShellCommandError(ValueError):
    """Raised when a shell command is rejected by the safety validator."""


def check_command_safety(command: str | list[str]) -> None:
    """Validate a shell command string against the destructive patterns blocklist.

    Args:
        command: Either a raw shell string (e.g. "rm -rf /tmp") or a list of args.

    Raises:
        ShellCommandError: If the command matches a destructive pattern.

    Returns:
        None — the command is safe to execute.
    """
    if isinstance(command, list):
        command_str = " ".join(shlex.quote(str(arg)) for arg in command)
    else:
        command_str = str(command)

    command_lower = command_str.lower()

    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(command_lower):
            raise ShellCommandError(
                f"Command blocked by safety validator: {command_str!r} "
                f"matches destructive pattern: {pattern.pattern}"
            )


def safe_os_system(command: str) -> int:
    """Safe wrapper around os.system() that blocks destructive commands.

    Args:
        command: Shell command string to execute.

    Returns:
        The exit code from os.system().

    Raises:
        ShellCommandError: If the command matches a destructive pattern.
    """
    check_command_safety(command)
    return os.system(command)


def safe_subprocess_run(
    args: list[str],
    *,
    check_safety: bool = True,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """Safe wrapper around subprocess.run() that blocks destructive commands.

    Args:
        args: Command arguments list.
        check_safety: If True, validate command before executing.
        **kwargs: Additional arguments passed to subprocess.run().

    Returns:
        subprocess.CompletedProcess instance.
    """
    if check_safety:
        check_command_safety(args)
    return subprocess.run(args, **kwargs)


def safe_popen_shell(command: str) -> subprocess.Popen[str]:
    """Safe wrapper around subprocess.Popen with bash -lc for shell commands.

    Args:
        command: Shell command string to execute.

    Returns:
        subprocess.Popen instance.

    Raises:
        ShellCommandError: If the command matches a destructive pattern.
    """
    check_command_safety(command)
    return subprocess.Popen(["bash", "-lc", command])


def is_command_safe(command: str | list[str]) -> bool:
    """Non-raising check — returns True if the command is safe to execute.

    Args:
        command: Either a raw shell string or a list of args.

    Returns:
        True if the command does not match any destructive pattern.
    """
    try:
        check_command_safety(command)
        return True
    except ShellCommandError:
        return False
