"""Fiona local-agent integration layer."""

from FionaAgent.command_registry import CommandSpec, command_registry
from FionaAgent.lmstudio import DEFAULT_LM_STUDIO_BASE_URL, LMStudioClient, LMStudioError

__all__ = [
    "CommandSpec",
    "DEFAULT_LM_STUDIO_BASE_URL",
    "LMStudioClient",
    "LMStudioError",
    "command_registry",
]
