"""Fiona local-agent integration layer."""

from Agent.command_registry import CommandSpec, command_registry
from Agent.lmstudio import DEFAULT_LM_STUDIO_BASE_URL, LMStudioClient, LMStudioError

__all__ = [
    "CommandSpec",
    "DEFAULT_LM_STUDIO_BASE_URL",
    "LMStudioClient",
    "LMStudioError",
    "command_registry",
]
