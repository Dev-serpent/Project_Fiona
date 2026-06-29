"""SciToolRegistry — collects and exposes all built-in scitools.

This internal registry feeds into the broader :class:`IToolRegistry`
implementation but does not depend on it directly.
"""

from __future__ import annotations

from fiona.tools.interfaces import ITool
from fiona.tools.models import ToolCategory, ToolSpec


class SciToolRegistry:
    """Internal registry that collects all scitools.

    Tools are registered by name and can be looked up individually or
    listed by category.  The :meth:`create_default` classmethod provides
    a convenient way to register all built-in tools with graceful
    fallback when optional dependencies are missing.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ITool] = {}

    def register(self, tool: ITool) -> None:
        """Register a tool under its ``spec.name``.

        Args:
            tool: The tool instance to register.

        Raises:
            ValueError: A tool with the same name is already registered.
        """
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"A tool named {name!r} is already registered")
        self._tools[name] = tool

    def get(self, name: str) -> ITool | None:
        """Look up a tool by name.

        Returns:
            The registered :class:`ITool`, or *None* if not found.
        """
        return self._tools.get(name)

    def list_specs(self) -> list[ToolSpec]:
        """Return specs for all registered tools."""
        return [t.spec for t in self._tools.values()]

    def list_by_category(self, category: ToolCategory) -> list[ToolSpec]:
        """Return specs for tools matching the given category.

        Args:
            category: The :class:`ToolCategory` to filter by.

        Returns:
            List of matching :class:`ToolSpec` objects.
        """
        return [
            t.spec for t in self._tools.values() if t.spec.category == category
        ]

    @classmethod
    def create_default(cls) -> SciToolRegistry:
        """Register all built-in scitools with graceful optional-dependency fallback.

        If a required dependency is missing (e.g. ``pint``, ``aiohttp``,
        ``sympy``, ``biopython``), the corresponding tool is silently
        skipped.
        """
        registry = cls()

        # Unit converter — requires pint (pure-Python fallback available)
        try:
            from SciRetrieval.scitools.unit_converter import UnitConverter

            registry.register(UnitConverter())
        except ImportError:
            pass

        # Chemical resolver — requires aiohttp
        try:
            from SciRetrieval.scitools.chem_resolver import ChemResolver

            registry.register(ChemResolver())
        except ImportError:
            pass

        # Sequence formatter — biopython optional (pure-Python fallback)
        try:
            from SciRetrieval.scitools.seq_formatter import SeqFormatter

            registry.register(SeqFormatter())
        except ImportError:
            pass

        # LaTeX converter — sympy optional (regex fallback)
        try:
            from SciRetrieval.scitools.latex_converter import LatexConverter

            registry.register(LatexConverter())
        except ImportError:
            pass

        # Physical constants — no external deps needed
        from SciRetrieval.scitools.constants import PhysicalConstantTool

        registry.register(PhysicalConstantTool())

        return registry
