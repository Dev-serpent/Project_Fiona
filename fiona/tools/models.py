"""Canonical data models for the Fiona tool system.

All tool-related data types live here as the single source of truth.
No other module should define its own ToolResult, ToolSpec, etc.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolCategory(str, Enum):
    """High-level category for grouping tools by scientific domain or purpose."""

    RETRIEVAL = "retrieval"
    ANALYSIS = "analysis"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"
    PHYSICS = "physics"
    FORMATTING = "formatting"
    BROWSER = "browser"
    FILESYSTEM = "filesystem"
    AUTOMATION = "automation"
    SIMULATION = "simulation"
    SYSTEM = "system"


@dataclass(frozen=True)
class ToolSpec:
    """Immutable specification describing a tool's identity, schema, and metadata."""

    name: str
    """Unique tool name used for invocation (e.g. ``'unit_convert'``)."""

    description: str
    """Human-readable description of what the tool does."""

    input_schema: dict[str, Any]
    """JSON Schema describing the expected input parameters."""

    category: ToolCategory = ToolCategory.ANALYSIS
    """Domain or purpose category for grouping."""

    requires_confirmation: bool = False
    """If True, the calling agent should ask the user before executing."""


@dataclass(frozen=True)
class ToolCall:
    """An invocation request for a named tool with specific arguments."""

    id: str
    """Unique identifier for this call (e.g. a UUID or request ID)."""

    function_name: str
    """Name of the tool to invoke (matches ``ToolSpec.name``)."""

    arguments: dict[str, Any]
    """Keyword arguments to pass to the tool's ``run()`` method."""


@dataclass(frozen=True)
class ToolResult:
    """Standardised result returned by every tool execution.

    Attributes:
        success: Whether the tool completed without errors.
        content: Primary output text / representation of the result.
        metadata: Optional structured metadata about the result.
        citations: List of citation strings or DOIs for provenance.
        artifacts: List of artifact dicts (e.g. file paths, structured data).
        error: If *success* is False, a human-readable error description.
    """

    success: bool
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class ToolContext:
    """Contextual information passed to every tool invocation.

    Attributes:
        logger: A logger instance the tool may use for diagnostic output.
        config: Optional configuration dictionary for the tool.
        cache: Optional cache manager reference (structural typing).
        cancellation_token: Optional threading.Event that, when set,
            signals the tool should abort as soon as possible.
        user_metadata: Optional user-specific metadata (e.g. preferences).
    """

    logger: logging.Logger
    config: dict[str, Any] | None = None
    cache: Any | None = None
    cancellation_token: threading.Event | None = None
    user_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolLimits:
    """Execution constraints that the tool executor should enforce."""

    max_rounds: int = 10
    """Maximum number of tool-call rounds in a single agent loop."""

    max_tool_calls_per_round: int = 8
    """Maximum number of parallel tool invocations per round."""

    max_execution_time_seconds: float = 30.0
    """Hard timeout per tool execution."""

    max_token_budget: int = 8192
    """Maximum token budget for tool input/output (approximate)."""
