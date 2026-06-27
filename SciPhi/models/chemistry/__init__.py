"""Chemistry domain models for SciPhi.

Provides concrete implementations of :class:`ScientificModel` covering
chemical kinetics, equilibrium thermodynamics, and stoichiometry:

* :class:`ChemicalReactionKineticsModel` — rate laws, concentration
  change, Arrhenius equation (ODE initial value)
* :class:`ChemicalEquilibriumModel` — equilibrium constants, Gibbs
  free energy, van't Hoff equation (algebraic)
* :class:`StoichiometryModel` — mole ratios, mass–mole conversion,
  limiting reagent, percent yield (algebraic)
"""

from __future__ import annotations

from SciPhi.models.chemistry.equilibrium import ChemicalEquilibriumModel
from SciPhi.models.chemistry.reactions import ChemicalReactionKineticsModel
from SciPhi.models.chemistry.stoichiometry import StoichiometryModel

__all__ = [
    "ChemicalEquilibriumModel",
    "ChemicalReactionKineticsModel",
    "StoichiometryModel",
]
