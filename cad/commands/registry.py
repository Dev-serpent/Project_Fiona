"""Command registry — register, discover, and execute commands."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from cad.core.document import Document


class CommandError(Exception):
    """Raised when a command fails to execute."""


class Command(ABC):
    """Base class for all CAD commands.

    A command encapsulates a single operation that can be:
    - Executed via the CLI
    - Called from Python scripts
    - Invoked from the GUI
    - Undone/redone (if undo support is added)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique command name, e.g. 'create_box'."""

    @property
    def aliases(self) -> list[str]:
        return []

    @property
    def description(self) -> str:
        return ""

    @abstractmethod
    def execute(self, doc: Document, **kwargs: Any) -> Any:
        """Execute the command on the given document."""


class CommandRegistry:
    """Central registry of all available commands.

    Commands can be registered, discovered, and executed by name.
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command

    def register_class(self, cls: type[Command]) -> None:
        """Register a command class (instantiate once)."""
        self.register(cls())

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def execute(self, command_name: str, doc: Document, **kwargs: Any) -> Any:
        cmd = self.get(command_name)
        if cmd is None:
            raise CommandError(f"Unknown command: {command_name}")
        try:
            return cmd.execute(doc, **kwargs)
        except Exception as exc:
            raise CommandError(f"Command '{command_name}' failed: {exc}") from exc

    @property
    def commands(self) -> dict[str, Command]:
        return dict(self._commands)

    def list_names(self) -> list[str]:
        return sorted(self._commands.keys())

    def list_by_category(self) -> dict[str, list[Command]]:
        categories: dict[str, list[Command]] = {}
        for cmd in self._commands.values():
            cat = getattr(cmd, "category", "general")
            categories.setdefault(cat, []).append(cmd)
        return categories

    def __repr__(self) -> str:
        return f"CommandRegistry({len(self._commands)} commands)"
