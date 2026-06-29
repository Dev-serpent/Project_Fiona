"""PhysicalConstantTool — looks up physical constants by name, symbol, or keyword.

No external dependencies required — uses a hardcoded table of ~30
commonly used physical constants.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fiona.tools.interfaces import ITool
from fiona.tools.models import ToolCategory, ToolContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded physical constants table
# ---------------------------------------------------------------------------
# Each entry: (name, symbol, value, unit)
_PHYSICAL_CONSTANTS: list[tuple[str, str, str, str]] = [
    ("speed of light in vacuum", "c", "299792458", "m·s⁻¹"),
    ("Planck constant", "h", "6.62607015e-34", "J·Hz⁻¹"),
    ("reduced Planck constant", "ħ", "1.054571817e-34", "J·s"),
    ("gravitational constant", "G", "6.67430e-11", "m³·kg⁻¹·s⁻²"),
    ("elementary charge", "e", "1.602176634e-19", "C"),
    ("electron mass", "mₑ", "9.1093837015e-31", "kg"),
    ("proton mass", "mₚ", "1.67262192369e-27", "kg"),
    ("neutron mass", "mₙ", "1.67492749804e-27", "kg"),
    ("Avogadro constant", "N_A", "6.02214076e23", "mol⁻¹"),
    ("Boltzmann constant", "k_B", "1.380649e-23", "J·K⁻¹"),
    ("molar gas constant", "R", "8.314462618", "J·mol⁻¹·K⁻¹"),
    ("Stefan-Boltzmann constant", "σ", "5.670374419e-8", "W·m⁻²·K⁻⁴"),
    ("fine-structure constant", "α", "7.2973525693e-3", ""),
    ("Rydberg constant", "R_∞", "10973731.568160", "m⁻¹"),
    ("Bohr radius", "a₀", "5.29177210903e-11", "m"),
    ("Bohr magneton", "μ_B", "9.2740100783e-24", "J·T⁻¹"),
    ("nuclear magneton", "μ_N", "5.0507837461e-27", "J·T⁻¹"),
    ("electron volt", "eV", "1.602176634e-19", "J"),
    ("atomic mass unit", "u", "1.66053906660e-27", "kg"),
    ("Faraday constant", "F", "96485.33212", "C·mol⁻¹"),
    ("vacuum permittivity", "ε₀", "8.8541878128e-12", "F·m⁻¹"),
    ("vacuum permeability", "μ₀", "1.25663706212e-6", "N·A⁻²"),
    ("characteristic impedance of vacuum", "Z₀", "376.730313668", "Ω"),
    ("Coulomb constant", "k_e", "8.9875517923e9", "N·m²·C⁻²"),
    ("standard acceleration of gravity", "g", "9.80665", "m·s⁻²"),
    ("standard atmosphere", "atm", "101325", "Pa"),
    ("molar volume of ideal gas (STP)", "V_m", "22.41396954e-3", "m³·mol⁻¹"),
    ("Wien displacement constant", "b", "2.897771955e-3", "m·K"),
    ("Hubble constant (approximate)", "H₀", "2.2e-18", "s⁻¹"),
    ("speed of sound in air (20°C)", "v_sound", "343", "m·s⁻¹"),
    ("electron radius (classical)", "r_e", "2.8179403227e-15", "m"),
    ("Compton wavelength of electron", "λ_C", "2.42631023867e-12", "m"),
]

# Build search index: name, symbol, and keywords
_CONSTANT_INDEX: list[dict[str, Any]] = []
for name, symbol, value, unit in _PHYSICAL_CONSTANTS:
    keywords = set(re.split(r"[\s,]+", name.lower()))
    keywords.add(symbol.lower())
    if symbol and symbol.endswith("₀"):
        keywords.add(symbol.rstrip("₀"))  # allow "epsilon" to match "ε₀"
    _CONSTANT_INDEX.append({
        "name": name,
        "symbol": symbol,
        "value": value,
        "unit": unit,
        "keywords": keywords,
    })


def _search_constants(query: str) -> list[dict[str, Any]]:
    """Search the constants table by name, symbol, or keyword.

    Returns:
        List of matching entries, ordered by relevance (exact match first).
    """
    q = query.strip().lower()

    # Exact match on name or symbol
    exact: list[dict[str, Any]] = []
    # Partial / keyword match
    partial: list[dict[str, Any]] = []

    for entry in _CONSTANT_INDEX:
        name_lower = entry["name"].lower()
        symbol_lower = entry["symbol"].lower()

        if name_lower == q or symbol_lower == q:
            exact.append(entry)
        elif q in name_lower or q in symbol_lower:
            partial.append(entry)
        elif any(q in kw for kw in entry["keywords"]):
            partial.append(entry)

    return exact + partial


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


class PhysicalConstantTool(ITool):
    """Looks up physical constants by name, symbol, or keyword.

    Uses a hardcoded table of ~30 commonly used constants with no
    external dependencies.
    """

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="physical_constant",
            description=(
                "Look up a physical constant by name, symbol, or keyword. "
                "Returns the value, unit, and description.  Supports ~30 "
                "commonly used constants including c, h, G, N_A, k_B, etc."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Name, symbol, or keyword to search for "
                            "(e.g. 'speed of light', 'c', 'Planck')."
                        ),
                    },
                },
                "required": ["query"],
            },
            category=ToolCategory.PHYSICS,
        )

    async def run(
        self, context: ToolContext, **kwargs: object
    ) -> ToolResult:
        """Execute the constant lookup.

        Args:
            context: Execution context with logger.
            **kwargs: Must contain ``query`` (str).

        Returns:
            :class:`ToolResult` with matching constant(s).
        """
        query = kwargs.get("query")
        if not query:
            return ToolResult(
                success=False,
                content="",
                error="Missing required argument: 'query'",
            )

        query_str = str(query).strip()
        if not query_str:
            return ToolResult(
                success=False,
                content="",
                error="Query is empty",
            )

        matches = _search_constants(query_str)

        if not matches:
            return ToolResult(
                success=False,
                content="",
                error=f"No constant found matching {query_str!r}",
            )

        # Format results
        lines: list[str] = []
        for i, entry in enumerate(matches, 1):
            unit_str = f" [{entry['unit']}]" if entry["unit"] else ""
            lines.append(
                f"{i}. {entry['symbol']} — {entry['name']}"
            )
            lines.append(f"   = {entry['value']}{unit_str}")
            lines.append("")

        result = "\n".join(lines).strip()
        context.logger.info(
            "physical_constant: found %d match(es) for %r",
            len(matches),
            query_str,
        )
        return ToolResult(
            success=True,
            content=result,
            metadata={"match_count": len(matches), "query": query_str},
        )
