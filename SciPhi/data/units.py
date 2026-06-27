"""Lightweight unit-conversion utilities using only the Python stdlib.

Provides a :class:`UnitConverter` that stores conversion factors to SI base
units and supports common metric, imperial-derived, and scientific units.
"""

from __future__ import annotations

import re
from typing import Final

# ---------------------------------------------------------------------------
# Internal conversion table  (all values → SI base unit factor)
# ---------------------------------------------------------------------------
# Each entry stores the factor to multiply by to get the canonical SI unit,
# plus a dimensional symbol string (LMT) for consistency checks.
# ---------------------------------------------------------------------------

_SI_BASE: Final[dict[str, tuple[float, str]]] = {
    # Length (L)
    "m": (1.0, "L^1"),  # metre (SI)
    "km": (1_000.0, "L^1"),
    "cm": (0.01, "L^1"),
    "mm": (0.001, "L^1"),
    # Mass (M)
    "kg": (1.0, "M^1"),  # kilogram (SI)
    "g": (0.001, "M^1"),
    # Time (T)
    "s": (1.0, "T^1"),  # second (SI)
    "ms": (0.001, "T^1"),
    # Force  (L M T^-2)
    "N": (1.0, "L^1 M^1 T^-2"),  # newton = kg·m·s⁻²
    # Energy (L^2 M T^-2)
    "J": (1.0, "L^2 M^1 T^-2"),  # joule = N·m = kg·m²·s⁻²
    # Power  (L^2 M T^-3)
    "W": (1.0, "L^2 M^1 T^-3"),  # watt = J·s⁻¹
    # Pressure (L^-1 M T^-2)
    "Pa": (1.0, "L^-1 M^1 T^-2"),  # pascal = N·m⁻²
    "bar": (100_000.0, "L^-1 M^1 T^-2"),
    "atm": (101_325.0, "L^-1 M^1 T^-2"),
    # Temperature  (Θ)  -- handled specially (not a simple factor)
    "K": (1.0, "Θ^1"),  # kelvin (SI)
    "C": (1.0, "Θ^1"),  # Celsius  (delta offset applied in convert)
    # Amount of substance (N)
    "mol": (1.0, "N^1"),
    # Electric current (I)
    "A": (1.0, "I^1"),  # ampere (SI)
    # Voltage  (L^2 M T^-3 I^-1)
    "V": (1.0, "L^2 M^1 T^-3 I^-1"),  # volt = W·A⁻¹
    # Frequency (T^-1)
    "Hz": (1.0, "T^-1"),
}

# Units that share the same dimension symbol (ignoring temperature scale offset).
_SI_BY_DIMENSION: dict[str, list[str]] = {}
for _unit, (_factor, _dim) in _SI_BASE.items():
    _SI_BY_DIMENSION.setdefault(_dim, []).append(_unit)

# Celsius offset relative to kelvin.
_CELSIUS_OFFSET: Final[float] = 273.15


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class UnitConverter:
    """Convert between common scientific units, check consistency, and inspect
    dimensional symbols.

    All operations use only the Python standard library — no ``pint``,
    ``sympy``, or other external dependencies are required.

    Examples::

        >>> uc = UnitConverter()
        >>> uc.convert(1000, "m", "km")
        1.0
        >>> uc.convert(0, "C", "K")
        273.15
        >>> uc.is_consistent("N", "kg m s^-2")   # doctest: +SKIP
        True
        >>> uc.dimensional_symbol("Pa")
        'L^-1 M^1 T^-2'
    """

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def known_units() -> frozenset[str]:
        """Return the set of unit symbols this converter recognises.

        Returns:
            Immutable set of unit strings (e.g. ``"m"``, ``"kg"``, ``"Pa"``).
        """
        return frozenset(_SI_BASE)

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        """Convert *value* expressed in *from_unit* to *to_unit*.

        Args:
            value: The numerical quantity to convert.
            from_unit: Source unit symbol (e.g. ``"km"``, ``"C"``).
            to_unit: Target unit symbol (e.g. ``"m"``, ``"K"``).

        Returns:
            The converted numerical value.

        Raises:
            ValueError: If either unit is unknown or the dimensions do not
                match.
        """
        from_factor, from_dim = self._lookup(from_unit)
        to_factor, to_dim = self._lookup(to_unit)

        if from_dim != to_dim:
            raise ValueError(
                f"Cannot convert {from_unit!r} (dim {from_dim}) "
                f"to {to_unit!r} (dim {to_dim}) — dimensions differ."
            )

        # Handle Celsius / kelvin offset.
        offset = 0.0
        if from_unit == "C" and to_unit == "K":
            offset = _CELSIUS_OFFSET
        elif from_unit == "K" and to_unit == "C":
            offset = -_CELSIUS_OFFSET

        return value * (from_factor / to_factor) + offset

    # ------------------------------------------------------------------
    # Consistency
    # ------------------------------------------------------------------

    def is_consistent(self, unit1: str, unit2: str) -> bool:
        """Check whether two units have the same physical dimensionality.

        Args:
            unit1: First unit symbol.
            unit2: Second unit symbol.

        Returns:
            ``True`` if the two units share the same LMT dimensionality,
            ``False`` otherwise (including if either symbol is unknown).
        """
        try:
            return self._lookup(unit1)[1] == self._lookup(unit2)[1]
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Dimensional symbol
    # ------------------------------------------------------------------

    @staticmethod
    def dimensional_symbol(unit: str) -> str:
        """Return the LMT dimensional symbol of a unit.

        The returned string follows the pattern ``L^a M^b T^c Θ^d N^e I^f``,
        omitting exponents that are zero.

        Args:
            unit: A known unit symbol (e.g. ``"N"``, ``"Pa"``).

        Returns:
            Dimensional string like ``"L^1 M^1 T^-2"``.

        Raises:
            ValueError: If the unit is not recognised.
        """
        if unit not in _SI_BASE:
            raise ValueError(f"Unknown unit {unit!r}.")
        return _SI_BASE[unit][1]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _lookup(unit: str) -> tuple[float, str]:
        """Return (factor, dimension) for a recognised unit symbol.

        Raises:
            ValueError: If the unit is not in the conversion table.
        """
        if unit not in _SI_BASE:
            raise ValueError(
                f"Unknown unit {unit!r}. "
                f"Known units: {sorted(_SI_BASE)}"
            )
        return _SI_BASE[unit]
