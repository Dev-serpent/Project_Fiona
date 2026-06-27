"""Chemical equilibrium model — thermodynamic equilibrium constants.

Governing equations:

* **Equilibrium constant**:
  :math:`K_{eq} = \\frac{[C]^c [D]^d}{[A]^a [B]^b}`
* **Gibbs free energy**:
  :math:`\\Delta G^\\circ = -RT \\ln K_{eq}`
* **van't Hoff equation**:
  :math:`\\frac{d(\\ln K)}{dT} = \\frac{\\Delta H^\\circ}{R T^2}`

The model relates the equilibrium constant of a chemical reaction to
the standard Gibbs free energy change and its temperature dependence
through the van't Hoff equation.

Assumptions
-----------
* Ideal solution behaviour (activity coefficients ≈ 1).
* Constant pressure.
* Standard state conditions for :math:`\\Delta G^\\circ`.
* No coupled equilibria.

Mathematical form
-----------------
:class:`~SciPhi.interfaces.model.MathematicalForm.ALGEBRAIC` —
the equilibrium condition is a closed-form algebraic relation among
concentrations and thermodynamic parameters.
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


class ChemicalEquilibriumModel(ScientificModel):
    """Chemical equilibrium — mass-action law and thermodynamic driving force.

    Describes the equilibrium position of a reversible reaction
    :math:`aA + bB \\rightleftharpoons cC + dD` in terms of the
    equilibrium constant and standard thermodynamic potentials.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.CHEMISTRY

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.ALGEBRAIC

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="equilibrium_constant",
                expression="K_eq = [C]**c * [D]**d / ([A]**a * [B]**b)",
                description="Mass-action expression for the equilibrium "
                "constant in terms of species concentrations.",
            ),
            Equation(
                name="gibbs_free_energy",
                expression="Delta_G = -R * T * ln(K_eq)",
                description="Standard Gibbs free energy change related "
                "to the equilibrium constant.",
            ),
            Equation(
                name="vant_hoff",
                expression="d(ln K)/dT = Delta_H / (R * T**2)",
                description="Temperature dependence of the equilibrium "
                "constant (van't Hoff equation).",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="equilibrium_constant",
                symbol="K_eq",
                unit="1",
                description="Equilibrium constant (dimensionless for "
                "balanced reactions).",
            ),
            Variable(
                name="gibbs_free_energy",
                symbol="ΔG",
                unit="J mol⁻¹",
                description="Standard Gibbs free energy change of "
                "reaction.",
            ),
            Variable(
                name="temperature",
                symbol="T",
                unit="K",
                description="Absolute temperature.",
            ),
            Variable(
                name="concentration_A",
                symbol="[A]",
                unit="mol L⁻¹",
                description="Equilibrium concentration of reactant A.",
            ),
            Variable(
                name="concentration_B",
                symbol="[B]",
                unit="mol L⁻¹",
                description="Equilibrium concentration of reactant B.",
            ),
            Variable(
                name="concentration_C",
                symbol="[C]",
                unit="mol L⁻¹",
                description="Equilibrium concentration of product C.",
            ),
            Variable(
                name="concentration_D",
                symbol="[D]",
                unit="mol L⁻¹",
                description="Equilibrium concentration of product D.",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="standard_enthalpy_change",
                symbol="ΔH°",
                default_value=0.0,
                unit="J mol⁻¹",
                description="Standard enthalpy change of reaction.",
            ),
            Parameter(
                name="standard_entropy_change",
                symbol="ΔS°",
                default_value=0.0,
                unit="J mol⁻¹ K⁻¹",
                description="Standard entropy change of reaction.",
            ),
            Parameter(
                name="stoichiometric_coefficient_a",
                symbol="a",
                default_value=1.0,
                unit="1",
                description="Stoichiometric coefficient of reactant A.",
            ),
            Parameter(
                name="stoichiometric_coefficient_b",
                symbol="b",
                default_value=1.0,
                unit="1",
                description="Stoichiometric coefficient of reactant B.",
            ),
            Parameter(
                name="stoichiometric_coefficient_c",
                symbol="c",
                default_value=1.0,
                unit="1",
                description="Stoichiometric coefficient of product C.",
            ),
            Parameter(
                name="stoichiometric_coefficient_d",
                symbol="d",
                default_value=1.0,
                unit="1",
                description="Stoichiometric coefficient of product D.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Ideal solution behaviour — all activity "
                "coefficients are unity.",
                impact="Non-ideal solutions (high ionic strength, "
                "concentrated solutes) require activity "
                "corrections.",
            ),
            Assumption(
                statement="Constant pressure — the system is open to "
                "the atmosphere or held at fixed pressure.",
                impact="Pressure-dependent equilibria (gas-phase "
                "reactions at high pressure) are not captured.",
            ),
            Assumption(
                statement="Standard state conditions for thermodynamic "
                "potentials.",
                impact="Non-standard states (e.g. different reference "
                "concentrations) must be converted.",
            ),
            Assumption(
                statement="No coupled equilibria — only one reaction "
                "is considered in isolation.",
                impact="Systems with multiple simultaneous equilibria "
                "require a coupled solver.",
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
                description="Equilibrium constant must be positive.",
                expression="K_eq > 0",
            ),
            Constraint(
                description="Equilibrium concentrations must be "
                "non-negative.",
                expression="[A] >= 0, [B] >= 0, [C] >= 0, [D] >= 0",
            ),
        ]

    @property
    def constants(self) -> list[PhysicalConstant]:
        return [
            PhysicalConstants.gas_constant,
        ]
