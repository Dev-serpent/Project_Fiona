"""Abstract interfaces for the Fiona tool system.

These ABCs define the contracts that all tools, registries, and
executors must satisfy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from fiona.tools.models import ToolCall, ToolContext, ToolResult, ToolSpec


class ITool(ABC):
    """A single executable tool with a well-defined spec and run method."""

    @property
    @abstractmethod
    def spec(self) -> ToolSpec:
        """Return the tool's immutable specification."""
        ...

    @abstractmethod
    async def run(self, context: ToolContext, **kwargs: object) -> ToolResult:
        """Execute the tool with the given context and arguments.

        Args:
            context: Execution context (logger, config, cancellation token, etc.).
            **kwargs: Tool-specific keyword arguments matching the input schema.

        Returns:
            A :class:`ToolResult` indicating success or failure.
        """
        ...


class IToolRegistry(ABC):
    """Registry that maps tool names to their ITool implementations."""

    @abstractmethod
    def register(self, tool: ITool, source: str = "internal") -> None:
        """Register a tool under its ``spec.name``.

        Args:
            tool: The tool instance to register.
            source: Origin identifier (e.g. ``"internal"``, ``"mcp"``).

        Raises:
            ValueError: A tool with the same name is already registered.
        """
        ...

    @abstractmethod
    def get(self, name: str) -> ITool | None:
        """Look up a tool by name.

        Returns:
            The registered tool, or *None* if not found.
        """
        ...

    @abstractmethod
    def list(self) -> list[ToolSpec]:
        """Return specs for all registered tools."""
        ...

    @abstractmethod
    def list_by_category(self, category: str) -> list[ToolSpec]:
        """Return specs for tools matching the given category string."""
        ...


class IToolExecutor(ABC):
    """Executes tool calls against the tool registry."""

    @abstractmethod
    async def execute(
        self, call: ToolCall, context: ToolContext
    ) -> ToolResult:
        """Execute a single tool call.

        Args:
            call: The tool call specifying which tool and arguments.
            context: Execution context.

        Returns:
            The :class:`ToolResult` produced by the tool.
        """
        ...
