"""Fiona local-agent integration layer."""

from Agent.command_registry import CommandSpec, command_registry
from Agent.ollama import DEFAULT_OLLAMA_BASE_URL, OllamaClient, OllamaError
from Agent.orchestrator import AgentOrchestrator, AgentTurn, run_agent_goal

__all__ = [
    "AgentOrchestrator",
    "AgentTurn",
    "CommandSpec",
    "DEFAULT_OLLAMA_BASE_URL",
    "OllamaClient",
    "OllamaError",
    "command_registry",
    "run_agent_goal",
]
