"""Command system — all CAD operations are executable commands."""

from cad.commands.registry import CommandRegistry, Command, CommandError
from cad.commands.builtins import register_builtin_commands

__all__ = [
    "CommandRegistry",
    "Command",
    "CommandError",
    "register_builtin_commands",
]
