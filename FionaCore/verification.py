"""Verification-prompt callback system for confirming critical actions.

Provides an abstract :class:`VerificationPrompt` base, two concrete
implementations (:class:`StdoutVerificationPrompt` and
:class:`DesktopVerificationPrompt`), a module-level default, and a
convenience function (:func:`prompt_for_confirmation`) that ties everything
together with :class:`~FionaCore.actions.ActionSpec`.
"""

from __future__ import annotations

import abc
import shutil
import subprocess
import sys
from typing import Any


class VerificationPrompt(abc.ABC):
    """Abstract base for user confirmation prompts before executing risky actions.

    Subclasses must implement :meth:`confirm`, which returns ``True`` to
    proceed or ``False`` to cancel.
    """

    def confirm(self, action_name: str, action_spec_details: dict) -> bool:
        """Ask the user to confirm an action.

        Args:
            action_name: The dotted action identifier (e.g. ``"host.restart"``).
            action_spec_details: Dictionary representation of the ActionSpec.

        Returns:
            True if the action should proceed, False to cancel.
        """
        return True


class StdoutVerificationPrompt(VerificationPrompt):
    """Prompt the user via stdout/stdin.

    Prints action details to the terminal and waits for a yes/no answer.
    """

    def confirm(self, action_name: str, action_spec_details: dict) -> bool:
        print(f"\nAction: {action_name}")
        print(f"  Description: {action_spec_details.get('description', 'N/A')}")
        print(f"  Risk:        {action_spec_details.get('risk', 'N/A')}")
        print(f"  Command:     {' '.join(action_spec_details.get('command', []))}")
        try:
            response = input("Proceed? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Treat EOF/Ctrl+C as "no" so we never hang or proceed unsafely.
            return False
        return response in ("y", "yes")


class DesktopVerificationPrompt(VerificationPrompt):
    """Prompt via desktop notification + Tkinter dialog, with stdout fallback.

    Sends an informational ``notify-send`` notification (fire-and-forget) and
    then shows a Tkinter yes/no dialog for the actual confirmation.  If
    Tkinter is not available, falls back to a terminal prompt.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _notify_desktop(action_name: str, details: dict) -> None:
        """Send an informational desktop notification (best-effort)."""
        if not shutil.which("notify-send"):
            return
        title = f"Fiona: Confirm {action_name}"
        body = (
            f"{details.get('description', 'N/A')} "
            f"({details.get('risk', 'N/A')})"
        )
        subprocess.run(
            ["notify-send", "-u", "critical", title, body],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _prompt_tkinter(action_name: str, details: dict) -> bool | None:
        """Show a Tkinter yes/no dialog.

        Returns:
            ``True`` / ``False`` if the dialog was displayed successfully,
            ``None`` if Tkinter is not available.
        """
        try:
            import tkinter as tk
            from tkinter import messagebox
        except ImportError:
            return None

        root = tk.Tk()
        root.withdraw()          # Hide the main window.
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()

        desc = details.get("description", "N/A")
        risk = details.get("risk", "N/A")
        command = " ".join(details.get("command", []))
        message = (
            f"Action: {action_name}\n"
            f"Description: {desc}\n"
            f"Risk: {risk}\n"
            f"Command: {command}\n\n"
            "Do you want to proceed?"
        )
        result = messagebox.askyesno(
            title="Fiona \u2014 Confirm Critical Action",
            message=message,
            icon=messagebox.WARNING,
        )
        root.destroy()
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def confirm(self, action_name: str, action_spec_details: dict) -> bool:
        # Fire-and-forget desktop notification (best effort).
        self._notify_desktop(action_name, action_spec_details)

        # Try Tkinter dialog first.
        tk_result = self._prompt_tkinter(action_name, action_spec_details)
        if tk_result is not None:
            return tk_result

        # Graceful degradation: terminal prompt.
        print(
            "\n[Tkinter not available \u2014 falling back to terminal prompt]",
        )
        return StdoutVerificationPrompt().confirm(
            action_name, action_spec_details,
        )


#: Module-level default used by
#: :func:`prompt_for_confirmation` and :class:`~FionaCore.actions.ActionRouter`
#: when no explicit prompt is provided.
DEFAULT_VERIFICATION_PROMPT: VerificationPrompt = DesktopVerificationPrompt()


def prompt_for_confirmation(
    action_spec: Any,
    prompt: VerificationPrompt | None = None,
) -> bool:
    """Check whether an action requires confirmation and prompt if so.

    Inspects *action_spec* for a ``requires_confirmation`` flag.  If the flag
    is ``True``, delegates to ``prompt.confirm()``; otherwise returns
    ``True`` immediately.

    Args:
        action_spec: An :class:`~FionaCore.actions.ActionSpec` instance (or
            any dict-like object) that has the field
            ``requires_confirmation`` (``bool``), ``name`` (``str``), and
            optionally the remaining ActionSpec fields.
        prompt: The :class:`VerificationPrompt` to use.  Defaults to
            :data:`DEFAULT_VERIFICATION_PROMPT`.

    Returns:
        ``True`` if the action may proceed (either confirmation is not
        required or the user confirmed), ``False`` if the user cancelled.
    """
    if prompt is None:
        prompt = DEFAULT_VERIFICATION_PROMPT

    # Handle both ActionSpec objects and plain dicts.
    if hasattr(action_spec, "requires_confirmation"):
        requires = action_spec.requires_confirmation
    else:
        requires = bool(action_spec.get("requires_confirmation", False))

    if not requires:
        return True

    # Build a dict of details for the prompt.
    if hasattr(action_spec, "to_dict"):
        details = action_spec.to_dict()
    elif isinstance(action_spec, dict):
        details = dict(action_spec)
    else:
        details = {"name": str(action_spec)}

    name = details.get("name", str(action_spec))
    return prompt.confirm(name, details)
