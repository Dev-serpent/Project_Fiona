"""Biology domain models for SciPhi.

Provides concrete implementations of :class:`ScientificModel` covering
population dynamics and epidemiology:

* :class:`LogisticGrowthModel` — logistic population growth with
  carrying capacity (ODE initial value)
* :class:`SIRModel` — compartmental susceptible–infected–recovered
  epidemic model (ODE initial value)
"""

from __future__ import annotations

from SciPhi.models.biology.epidemiology import SIRModel
from SciPhi.models.biology.population import LogisticGrowthModel

__all__ = [
    "LogisticGrowthModel",
    "SIRModel",
]
