from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(frozen=True)
class Personality:
    """Immutable definition of an agent personality.

    Attributes:
        name: Unique identifier for this personality.
        description: Human-readable description of the personality's role.
        system_prompt: The system prompt sent to the LLM for this personality.
        allowed_tools: Optional frozenset of tool names this personality may use.
                       ``None`` means *all* tools are permitted.
        model_override: Optional model name to force when this personality is active.
    """

    name: str
    description: str
    system_prompt: str
    allowed_tools: frozenset[str] | None = None
    model_override: str | None = None

    def permits(self, tool_name: str) -> bool:
        """Check if *tool_name* is in *allowed_tools* (``None`` means all permitted)."""
        return self.allowed_tools is None or tool_name in self.allowed_tools

    def to_dict(self) -> dict[str, Any]:
        """Serialize for display/API."""
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "allowed_tools": list(self.allowed_tools) if self.allowed_tools is not None else None,
            "model_override": self.model_override,
        }


class PersonalityRegistry:
    """Thread-safe singleton registry of built-in and custom personalities."""

    _instance: PersonalityRegistry | None = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> PersonalityRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False  # type: ignore[attr-defined]
                    cls._instance = instance
        return cls._instance  # type: ignore[return-value]

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._personalities: dict[str, Personality] = {}
        self._instance_lock: threading.Lock = threading.Lock()
        self._register_builtins()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> PersonalityRegistry:
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance  # type: ignore[return-value]

    def get(self, name: str) -> Personality:
        """Look up by *name*. Raises ``KeyError`` if not found."""
        with self._instance_lock:
            if name not in self._personalities:
                raise KeyError(f"personality not found: {name}")
            return self._personalities[name]

    def list(self) -> list[Personality]:
        """Return all registered personalities."""
        with self._instance_lock:
            return list(self._personalities.values())

    def register(self, p: Personality) -> None:
        """Add or replace a personality.  *p.name* must be non-empty."""
        if not p.name or not p.name.strip():
            raise ValueError("personality name must be non-empty")
        with self._instance_lock:
            self._personalities[p.name] = p

    # ------------------------------------------------------------------
    # Built-in personalities
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        """Register the 5 built-in personalities."""
        general = Personality(
            name="general",
            description="General-purpose assistant with full tool access",
            system_prompt=_GENERAL_SYSTEM_PROMPT,
            allowed_tools=None,
            model_override=None,
        )
        planner = Personality(
            name="planner",
            description="Strategic planner — reads state, does not execute",
            system_prompt=_PLANNER_SYSTEM_PROMPT,
            allowed_tools=frozenset({
                "seeondesk_list", "seeondesk_active", "fiona_status",
                "recall_search", "recall_remember",
            }),
            model_override="qwen2:1.5b",
        )
        engineer = Personality(
            name="engineer",
            description="Execution specialist — automation & input",
            system_prompt=_ENGINEER_SYSTEM_PROMPT,
            allowed_tools=frozenset({
                "press", "click", "move", "text", "launch_binding", "macro",
                "seeondesk_list", "seeondesk_active", "fiona_status",
            }),
            model_override=None,
        )
        analyst = Personality(
            name="analyst",
            description="Research & memory analyst",
            system_prompt=_ANALYST_SYSTEM_PROMPT,
            allowed_tools=frozenset({
                "dataclient_mine", "recall_remember", "recall_search",
                "seeondesk_analyze", "seeondesk_list", "seeondesk_active",
                "fiona_status",
            }),
            model_override="qwen2:1.5b",
        )
        security = Personality(
            name="security",
            description="Read-only audit personality",
            system_prompt=_SECURITY_SYSTEM_PROMPT,
            allowed_tools=frozenset({
                "seeondesk_list", "seeondesk_active", "fiona_status",
                "recall_search",
            }),
            model_override="qwen2:1.5b",
        )
        for p in (general, planner, engineer, analyst, security):
            self._personalities[p.name] = p


# ======================================================================
# Static system-prompts for the built-in personalities
# ======================================================================

_GENERAL_SYSTEM_PROMPT = """\
You are Fiona, a highly advanced local workstation control system.
You are NOT a general-purpose AI assistant; you are the SYSTEM OPERATOR.

### ABSOLUTE RULES:
1. **NEVER** tell the user to use Task Manager, their mouse, or their keyboard. YOU are the one with control.
2. **NEVER** say "I am an AI language model." You are FIONA.
3. **MANDATORY TOOL USE**: If the user asks a question about the system or asks you to do something, you MUST use a tool to accomplish it.
4. **THINK AND ACT**: Break every request into steps. Check the state with tools if you are unsure.
5. **ONLY JSON**: You must ONLY output the JSON block. No pre-text, no post-text.

OUTPUT FORMAT:
{
  "thought": "Deconstruct the user's request. What is the current state? What tool will move us closer to the goal?",
  "action": "command_name_or_null",
  "input": { "arg": "value" }
}

If the goal is achieved, set "action" to null.
"""

_PLANNER_SYSTEM_PROMPT = """\
You are a strategic planner. Break down complex goals into ordered steps. \
Never execute actions directly — design the plan. Output structured plans as JSON."""

_ENGINEER_SYSTEM_PROMPT = """\
You are a senior engineer. Execute technical tasks precisely. \
Prefer command-line automation over manual steps. Use tools to verify your work."""

_ANALYST_SYSTEM_PROMPT = """\
You are a system analyst. Observe, research, and document. \
Do not modify system state. Gather information and present clear findings."""

_SECURITY_SYSTEM_PROMPT = """\
You are a security engineer. Audit configurations, verify permissions, \
check encryption, and report vulnerabilities. \
Do not make changes — report findings."""
