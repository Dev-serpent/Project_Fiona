"""UnitConverter tool — converts between physical units.

Uses the ``pint`` library if available for full unit-system support;
otherwise falls back to a hardcoded table of common conversions.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fiona.tools.interfaces import ITool
from fiona.tools.models import ToolCategory, ToolContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional pint import
# ---------------------------------------------------------------------------
try:
    import pint

    HAS_PINT = True
    _ureg = pint.UnitRegistry()
except ImportError:
    HAS_PINT = False
    _ureg = None

# ---------------------------------------------------------------------------
# Hardcoded fallback conversion table (SI base + common derived units)
# ---------------------------------------------------------------------------
# Each entry: factor (to SI) and dimensionality string for mismatch detection.
_FALLBACK_TABLE: dict[str, tuple[float, str]] = {
    # Length
    "meter": (1.0, "length"),
    "metre": (1.0, "length"),
    "m": (1.0, "length"),
    "kilometer": (1000.0, "length"),
    "km": (1000.0, "length"),
    "centimeter": (0.01, "length"),
    "cm": (0.01, "length"),
    "millimeter": (0.001, "length"),
    "mm": (0.001, "length"),
    "inch": (0.0254, "length"),
    "in": (0.0254, "length"),
    "inches": (0.0254, "length"),
    "foot": (0.3048, "length"),
    "feet": (0.3048, "length"),
    "ft": (0.3048, "length"),
    "yard": (0.9144, "length"),
    "yd": (0.9144, "length"),
    "mile": (1609.344, "length"),
    "mi": (1609.344, "length"),
    # Mass
    "kilogram": (1.0, "mass"),
    "kg": (1.0, "mass"),
    "gram": (0.001, "mass"),
    "g": (0.001, "mass"),
    "milligram": (1e-6, "mass"),
    "mg": (1e-6, "mass"),
    "pound": (0.45359237, "mass"),
    "lb": (0.45359237, "mass"),
    "lbs": (0.45359237, "mass"),
    "ounce": (0.028349523125, "mass"),
    "oz": (0.028349523125, "mass"),
    "ton": (907.18474, "mass"),
    # Time
    "second": (1.0, "time"),
    "s": (1.0, "time"),
    "sec": (1.0, "time"),
    "minute": (60.0, "time"),
    "min": (60.0, "time"),
    "hour": (3600.0, "time"),
    "h": (3600.0, "time"),
    "hr": (3600.0, "time"),
    "day": (86400.0, "time"),
    "d": (86400.0, "time"),
    # Temperature (special conversion, not linear factor)
    "celsius": (1.0, "temperature"),
    "c": (1.0, "temperature"),
    "fahrenheit": (1.0, "temperature"),
    "f": (1.0, "temperature"),
    "kelvin": (1.0, "temperature"),
    "k": (1.0, "temperature"),
    # Volume
    "liter": (0.001, "volume"),
    "litre": (0.001, "volume"),
    "l": (0.001, "volume"),
    "milliliter": (1e-6, "volume"),
    "ml": (1e-6, "volume"),
    "gallon": (0.003785411784, "volume"),
    "gal": (0.003785411784, "volume"),
    "quart": (0.000946352946, "volume"),
    "qt": (0.000946352946, "volume"),
    # Energy
    "joule": (1.0, "energy"),
    "j": (1.0, "energy"),
    "kilojoule": (1000.0, "energy"),
    "kj": (1000.0, "energy"),
    "calorie": (4.184, "energy"),
    "cal": (4.184, "energy"),
    "kilocalorie": (4184.0, "energy"),
    "kcal": (4184.0, "energy"),
    "electronvolt": (1.602176634e-19, "energy"),
    "ev": (1.602176634e-19, "energy"),
    # Power
    "watt": (1.0, "power"),
    "w": (1.0, "power"),
    "kilowatt": (1000.0, "power"),
    "kw": (1000.0, "power"),
    "horsepower": (745.69987158227022, "power"),
    "hp": (745.69987158227022, "power"),
    # Pressure
    "pascal": (1.0, "pressure"),
    "pa": (1.0, "pressure"),
    "kilopascal": (1000.0, "pressure"),
    "kpa": (1000.0, "pressure"),
    "bar": (100000.0, "pressure"),
    "atm": (101325.0, "pressure"),
    "atmosphere": (101325.0, "pressure"),
    "psi": (6894.757293178, "pressure"),
    "torr": (133.32236842105263, "pressure"),
}

_TEMP_UNITS = {"celsius", "c", "fahrenheit", "f", "kelvin", "k"}


def _lookup_unit(unit: str) -> tuple[float, str] | None:
    """Look up a unit in the fallback table (case-insensitive)."""
    key = unit.strip().lower()
    # Direct match
    if key in _FALLBACK_TABLE:
        return _FALLBACK_TABLE[key]
    # Try plural -> singular (remove trailing 's')
    if key.endswith("s") and key[:-1] in _FALLBACK_TABLE:
        return _FALLBACK_TABLE[key[:-1]]
    return None


def _convert_fallback(
    value: float, from_unit: str, to_unit: str
) -> tuple[float, str]:
    """Convert using the hardcoded fallback table.

    Returns:
        ``(converted_value, result_unit)``.

    Raises:
        ValueError: If units are unknown or dimensions don't match.
    """
    from_info = _lookup_unit(from_unit)
    to_info = _lookup_unit(to_unit)

    if from_info is None:
        raise ValueError(f"Unknown unit: {from_unit!r}")
    if to_info is None:
        raise ValueError(f"Unknown unit: {to_unit!r}")

    from_factor, from_dim = from_info
    to_factor, to_dim = to_info

    if from_dim != to_dim:
        raise ValueError(
            f"Cannot convert {from_dim!r} ({from_unit}) to {to_dim!r} ({to_unit})"
        )

    # Handle temperature separately
    if from_dim == "temperature":
        result = _convert_temperature(value, from_unit, to_unit)
    else:
        result = value * from_factor / to_factor

    return result, to_unit


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Convert between Celsius, Fahrenheit, and Kelvin."""
    # Normalise unit names
    f_lower = from_unit.strip().lower()
    t_lower = to_unit.strip().lower()

    # Map to standard names
    unit_map = {
        "celsius": "c", "c": "c",
        "fahrenheit": "f", "f": "f",
        "kelvin": "k", "k": "k",
    }
    f_std = unit_map.get(f_lower, f_lower)
    t_std = unit_map.get(t_lower, t_lower)

    # Convert from -> Kelvin
    if f_std == "c":
        kelvin = value + 273.15
    elif f_std == "f":
        kelvin = (value - 32.0) * 5.0 / 9.0 + 273.15
    elif f_std == "k":
        kelvin = value
    else:
        raise ValueError(f"Unsupported temperature unit: {from_unit!r}")

    # Convert Kelvin -> to
    if t_std == "c":
        return kelvin - 273.15
    elif t_std == "f":
        return (kelvin - 273.15) * 9.0 / 5.0 + 32.0
    elif t_std == "k":
        return kelvin
    else:
        raise ValueError(f"Unsupported temperature unit: {to_unit!r}")


def _convert_pint(value: float, from_unit: str, to_unit: str) -> tuple[float, str]:
    """Convert using pint (requires ``pint`` installed)."""
    q = value * _ureg.parse_expression(from_unit)
    result = q.to(to_unit)
    return float(result.magnitude), str(result.units)


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


class UnitConverter(ITool):
    """Converts a numeric value between physical units.

    Uses ``pint`` for full unit-system support when available; otherwise
    falls back to a hardcoded table of common conversions.
    """

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="unit_convert",
            description=(
                "Convert a numeric value from one physical unit to another. "
                "Supports length, mass, time, temperature, volume, energy, "
                "power, and pressure units."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "The numeric value to convert.",
                    },
                    "from_unit": {
                        "type": "string",
                        "description": "The source unit (e.g. 'meter', 'kg', 'celsius').",
                    },
                    "to_unit": {
                        "type": "string",
                        "description": "The target unit (e.g. 'foot', 'lb', 'fahrenheit').",
                    },
                },
                "required": ["value", "from_unit", "to_unit"],
            },
            category=ToolCategory.PHYSICS,
        )

    async def run(
        self, context: ToolContext, **kwargs: object
    ) -> ToolResult:
        """Execute the unit conversion.

        Args:
            context: Execution context with logger.
            **kwargs: Must contain ``value`` (float), ``from_unit`` (str),
                ``to_unit`` (str).

        Returns:
            :class:`ToolResult` with the converted value as content.
        """
        try:
            value = kwargs.get("value")
            if value is None:
                return ToolResult(
                    success=False,
                    content="",
                    error="Missing required argument: 'value'",
                )
            value = float(value)  # type: ignore[arg-type]

            from_unit = kwargs.get("from_unit")
            to_unit = kwargs.get("to_unit")
            if not from_unit or not to_unit:
                missing = []
                if not from_unit:
                    missing.append("from_unit")
                if not to_unit:
                    missing.append("to_unit")
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Missing required arguments: {', '.join(missing)}",
                )
            from_str = str(from_unit)
            to_str = str(to_unit)

            if HAS_PINT:
                result_value, result_unit = _convert_pint(
                    value, from_str, to_str
                )
            else:
                result_value, result_unit = _convert_fallback(
                    value, from_str, to_str
                )

            # Format nicely
            if result_value == int(result_value):
                formatted = f"{int(result_value)} {result_unit}"
            else:
                formatted = f"{result_value:.6g} {result_unit}"

            context.logger.info(
                "unit_convert: %g %s -> %s %s",
                value, from_str, result_value, result_unit,
            )
            return ToolResult(success=True, content=formatted)

        except ValueError as exc:
            context.logger.warning("unit_convert failed: %s", exc)
            return ToolResult(success=False, content="", error=str(exc))
        except Exception as exc:
            context.logger.error("unit_convert error: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=f"Unexpected conversion error: {exc}",
            )
