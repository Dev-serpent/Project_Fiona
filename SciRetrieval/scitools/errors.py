"""Specialised error hierarchy for scitool failures.

All exceptions derive from ``SciToolError`` so callers can catch
a single base type at the top level if desired.
"""


class SciToolError(Exception):
    """Base error for all scitool failures."""


class ToolNotFoundError(SciToolError):
    """The requested tool is not registered in the registry."""


class ToolExecutionError(SciToolError):
    """The tool's ``run()`` method raised an unexpected error."""


class MissingDependencyError(SciToolError):
    """An optional Python dependency required by this tool is not installed."""


class InvalidInputError(SciToolError):
    """The input arguments did not satisfy the tool's schema or validation rules."""
