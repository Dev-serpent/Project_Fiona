"""Thermodynamics model — ideal gas law, thermodynamic processes, heat transfer.

Provides the governing equations for ideal gases, the first law of
thermodynamics, adiabatic processes, and sensible heat transfer.
"""

from __future__ import annotations

from SciPhi.data.constants import PhysicalConstants
from SciPhi.interfaces.model import (
    Assumption,
    Constraint,
    Equation,
    MathematicalForm,
    Parameter,
    PhysicalConstant,
    ScientificDomain,
    ScientificModel,
    Variable,
)


class ThermodynamicsModel(ScientificModel):
    """Thermodynamics of ideal gases and basic thermal processes.

    Governing equations:

    * :math:`PV = nRT` — ideal gas law.
    * :math:`\\Delta U = Q - W` — first law of thermodynamics.
    * :math:`PV^\\gamma = \\text{constant}` — adiabatic (reversible)
      process relation.
    * :math:`Q = mc\\Delta T` — sensible heat transfer.

    The model is purely algebraic: it relates thermodynamic state variables
    at equilibrium without rate equations.  Transient or non-equilibrium
    processes (e.g. heat diffusion, fluid flow) require additional models.

    Assumptions
    -----------
    * Ideal gas behaviour (negligible intermolecular forces, point
      molecules).
    * Quasistatic (slow) processes so the system remains near equilibrium.
    * Adiabatic process is reversible (isentropic).
    * Constant specific heat capacity (temperature-independent).
    * No phase changes or chemical reactions.

    Mathematical form
    -----------------
    :class:`~SciPhi.interfaces.model.MathematicalForm.ALGEBRAIC` —
    state equations are closed-form algebraic relations among thermodynamic
    variables.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.PHYSICS

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.ALGEBRAIC

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="ideal_gas_law",
                expression="P * V = n * R * T",
                description="Ideal gas law relating pressure, volume, "
                "amount of substance, and absolute temperature.",
            ),
            Equation(
                name="first_law",
                expression="Delta_U = Q - W",
                description="First law of thermodynamics: change in "
                "internal energy equals heat added minus "
                "work done by the system.",
            ),
            Equation(
                name="adiabatic_process",
                expression="P * V**gamma = constant",
                description="Relation between pressure and volume for a "
                "reversible adiabatic (isentropic) process.",
            ),
            Equation(
                name="sensible_heat",
                expression="Q = m * c * Delta_T",
                description="Sensible heat transfer: heat required to "
                "change temperature of a substance.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="pressure",
                symbol="P",
                unit="Pa",
                description="Absolute pressure of the gas.",
            ),
            Variable(
                name="volume",
                symbol="V",
                unit="m³",
                description="Volume occupied by the gas.",
            ),
            Variable(
                name="temperature",
                symbol="T",
                unit="K",
                description="Absolute temperature of the gas.",
            ),
            Variable(
                name="internal_energy",
                symbol="U",
                unit="J",
                description="Internal energy of the system.",
            ),
            Variable(
                name="heat_added",
                symbol="Q",
                unit="J",
                description="Heat transferred into the system.",
            ),
            Variable(
                name="work_done",
                symbol="W",
                unit="J",
                description="Work done by the system on its surroundings.",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="amount_of_substance",
                symbol="n",
                default_value=1.0,
                unit="mol",
                description="Amount of substance (number of moles).",
            ),
            Parameter(
                name="adiabatic_index",
                symbol="γ",
                default_value=1.4,
                unit="1",
                description="Ratio of specific heats (Cp/Cv).  "
                "≈ 5/3 for monatomic, ≈ 7/5 for diatomic "
                "ideal gases.",
            ),
            Parameter(
                name="specific_heat_capacity",
                symbol="c",
                default_value=1005.0,
                unit="J kg⁻¹ K⁻¹",
                description="Specific heat capacity at constant pressure "
                "(default approximates dry air at room "
                "temperature).",
            ),
            Parameter(
                name="mass",
                symbol="m",
                default_value=1.0,
                unit="kg",
                description="Mass of the substance undergoing heat "
                "transfer.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Ideal gas behaviour — intermolecular forces "
                "and molecular volume are neglected.",
                impact="Model is inaccurate at high pressures or low "
                "temperatures where real-gas effects "
                "(van der Waals forces, condensation) "
                "become significant.",
            ),
            Assumption(
                statement="Processes are quasistatic (slow compared to "
                "internal relaxation times).",
                impact="Fast processes (explosions, rapid compression) "
                "may produce irreversible effects not captured "
                "by the equilibrium relations.",
            ),
            Assumption(
                statement="Adiabatic process is reversible (isentropic).",
                impact="Real adiabatic processes with friction, "
                "turbulence, or shock waves are not isentropic.",
            ),
            Assumption(
                statement="Specific heat capacity is constant "
                "(temperature-independent).",
                impact="At large temperature ranges the temperature "
                "dependence of c cannot be ignored.",
            ),
            Assumption(
                statement="No phase changes or chemical reactions occur.",
                impact="Latent heat and reaction enthalpies are "
                "not accounted for.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Absolute temperature must be positive.",
                expression="T > 0",
            ),
            Constraint(
                description="Pressure must be positive.",
                expression="P > 0",
            ),
            Constraint(
                description="Volume must be positive.",
                expression="V > 0",
            ),
            Constraint(
                description="Amount of substance must be positive.",
                expression="n > 0",
            ),
            Constraint(
                description="Adiabatic index must be greater than 1.",
                expression="gamma > 1",
            ),
        ]

    @property
    def constants(self) -> list[PhysicalConstant]:
        return [
            PhysicalConstants.gas_constant,
        ]
