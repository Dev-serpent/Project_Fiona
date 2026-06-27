"""Engineering domain models for SciPhi.

Provides concrete implementations of :class:`ScientificModel` covering
structural analysis and circuit theory:

* :class:`CircuitModel` — Ohm's law, Kirchhoff's laws, RC/RL
  transient response (hybrid ODE / algebraic)
* :class:`StructuralModel` — Hooke's law, beam bending, Euler
  buckling, cantilever deflection (algebraic)
"""

from __future__ import annotations

from SciPhi.models.engineering.circuits import CircuitModel
from SciPhi.models.engineering.structures import StructuralModel

__all__ = [
    "CircuitModel",
    "StructuralModel",
]
