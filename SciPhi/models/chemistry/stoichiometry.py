"""Stoichiometry model — mass and mole relationships in reactions.

Governing equations:

* **Mole ratio**:
  :math:`\\frac{n_A}{a} = \\frac{n_B}{b}` (from balanced equation
  :math:`aA + bB \\rightarrow \\cdots`)
* **Mass–mole conversion**:
  :math:`n = \\frac{m}{M}`
* **Limiting reagent**:
  :math:`\\min\\left(\\frac{n_A}{a}, \\frac{n_B}{b}\\right)`
* **Percent yield**:
  :math:`\\frac{\\text{actual}}{\\text{theoretical}} \\times 100\\%`

The model determines the amount relationships between reactants and
products in a balanced chemical reaction, identifies the limiting
reagent, and computes reaction yield.

Assumptions
-----------
* Complete consumption of the limiting reagent.
* No side reactions — all reactant mass goes to the intended products.
* Balanced chemical equation provided externally.

Mathematical form
-----------------
:class:`~SciPhi.interfaces.model.MathematicalForm.ALGEBRAIC` —
all relations are closed-form algebraic ratios.
"""

from __future__ import annotations

from SciPhi.interfaces.model import (
    Assumption,
    Constraint,
    Equation,
    MathematicalForm,
    Parameter,
    ScientificDomain,
    ScientificModel,
    Variable,
)


class StoichiometryModel(ScientificModel):
    """Stoichiometry — mole ratios, mass conversion, and yield calculation.

    Describes the quantitative relationships between reactants and
    products in a balanced chemical reaction :math:`aA + bB \\rightarrow`
    based on the law of conservation of mass.
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
                name="mole_ratio",
                expression="n_A / a = n_B / b",
                description="Mole ratio equivalence from the balanced "
                "equation coefficients.",
            ),
            Equation(
                name="mass_mole_conversion",
                expression="n = m / M",
                description="Conversion between mass and amount of "
                "substance via molar mass.",
            ),
            Equation(
                name="limiting_reagent",
                expression="limiting = min(n_A / a, n_B / b)",
                description="Identification of the limiting reagent "
                "based on smallest mole-to-coefficient ratio.",
            ),
            Equation(
                name="percent_yield",
                expression="yield = (actual / theoretical) * 100",
                description="Percent yield as actual over theoretical "
                "times one hundred.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="amount_A",
                symbol="n_A",
                unit="mol",
                description="Amount of substance of reactant A.",
            ),
            Variable(
                name="amount_B",
                symbol="n_B",
                unit="mol",
                description="Amount of substance of reactant B.",
            ),
            Variable(
                name="mass_A",
                symbol="m_A",
                unit="g",
                description="Mass of reactant A.",
            ),
            Variable(
                name="mass_B",
                symbol="m_B",
                unit="g",
                description="Mass of reactant B.",
            ),
            Variable(
                name="yield_percentage",
                symbol="%",
                unit="1",
                description="Percent yield of the reaction.",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="molar_mass_A",
                symbol="M_A",
                default_value=1.0,
                unit="g mol⁻¹",
                description="Molar mass of reactant A.",
            ),
            Parameter(
                name="molar_mass_B",
                symbol="M_B",
                default_value=1.0,
                unit="g mol⁻¹",
                description="Molar mass of reactant B.",
            ),
            Parameter(
                name="stoichiometric_coefficient_a",
                symbol="a",
                default_value=1.0,
                unit="1",
                description="Stoichiometric coefficient of reactant A "
                "in the balanced equation.",
            ),
            Parameter(
                name="stoichiometric_coefficient_b",
                symbol="b",
                default_value=1.0,
                unit="1",
                description="Stoichiometric coefficient of reactant B "
                "in the balanced equation.",
            ),
            Parameter(
                name="theoretical_yield",
                symbol="Y_theo",
                default_value=100.0,
                unit="g",
                description="Theoretical (maximum) mass of product "
                "expected from complete conversion.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Complete consumption of the limiting reagent.",
                impact="Reversible reactions or incomplete conversion "
                "will produce less product than predicted.",
            ),
            Assumption(
                statement="No side reactions — all reactant mass "
                "converts to the intended products.",
                impact="Real reactions with by-products will have "
                "lower selectivity.",
            ),
            Assumption(
                statement="Balanced chemical equation is provided "
                "externally.",
                impact="Unbalanced or incorrect equations produce "
                "invalid stoichiometric ratios.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Amounts of substance must be non-negative.",
                expression="n_A >= 0, n_B >= 0",
            ),
            Constraint(
                description="Molar masses must be positive.",
                expression="M_A > 0, M_B > 0",
            ),
            Constraint(
                description="Stoichiometric coefficients must be "
                "positive.",
                expression="a > 0, b > 0",
            ),
        ]

    @property
    def constants(self) -> list:
        """No fundamental physical constants are required.

        Stoichiometry uses purely empirical molar masses supplied as
        parameters.
        """
        return []
