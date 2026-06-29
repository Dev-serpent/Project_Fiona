"""Fiona tool system — canonical types for tool integration.

This package is the single source of truth for all tool-related
abstract interfaces and data models.  No other module should define
its own ``ToolResult``, ``ToolSpec``, etc.
"""

from fiona.tools.interfaces import ITool, IToolExecutor, IToolRegistry
from fiona.tools.models import (
    ToolCall,
    ToolCategory,
    ToolContext,
    ToolLimits,
    ToolResult,
    ToolSpec,
)

__all__ = [
    # Interfaces
    "ITool",
    "IToolRegistry",
    "IToolExecutor",
    # Models
    "ToolSpec",
    "ToolResult",
    "ToolContext",
    "ToolLimits",
    "ToolCall",
    "ToolCategory",
]
