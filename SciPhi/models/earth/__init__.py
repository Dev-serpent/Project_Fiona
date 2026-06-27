"""Earth science domain models for SciPhi.

Provides concrete implementations of :class:`ScientificModel` covering
climate and geophysical processes:

* :class:`EnergyBalanceModel` — zero-dimensional energy balance
  climate model with albedo feedback (ODE initial value / algebraic)
"""

from __future__ import annotations

from SciPhi.models.earth.climate import EnergyBalanceModel

__all__ = [
    "EnergyBalanceModel",
]
