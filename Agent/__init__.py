"""Fiona local-agent integration layer."""

from Agent.cancellation import CancellationToken, CancelledError
from Agent.chat_handler import AgentChatHandler
from Agent.chat_store import ChatMessage, ChatStore, ChatStoreError, estimate_tokens
from Agent.command_registry import CommandSpec, command_registry
from Agent.ollama import DEFAULT_OLLAMA_BASE_URL, OllamaClient, OllamaError
from Agent.orchestration import (
    Complexity,
    ComplexityAssessor,
    ForemanAgent,
    ForemanConfig,
    PlanValidationError,
    SubAgent,
    SubAgentResult,
    SubGoalSpec,
    TaskPlan,
)
from Agent.orchestrator import AgentOrchestrator, AgentTurn, run_agent_goal
from Agent.permission import (
    AgentPermissionError,
    PermissionEnforcer,
    SafeActionRouter,
)
from Agent.personality import Personality, PersonalityRegistry

__all__ = [
    "AgentChatHandler",
    "AgentOrchestrator",
    "AgentPermissionError",
    "AgentTurn",
    "CancellationToken",
    "CancelledError",
    "ChatMessage",
    "ChatStore",
    "ChatStoreError",
    "CommandSpec",
    "Complexity",
    "ComplexityAssessor",
    "DEFAULT_OLLAMA_BASE_URL",
    "ForemanAgent",
    "ForemanConfig",
    "OllamaClient",
    "OllamaError",
    "PermissionEnforcer",
    "Personality",
    "PersonalityRegistry",
    "PlanValidationError",
    "SafeActionRouter",
    "SubAgent",
    "SubAgentResult",
    "SubGoalSpec",
    "TaskPlan",
    "command_registry",
    "estimate_tokens",
    "run_agent_goal",
]
