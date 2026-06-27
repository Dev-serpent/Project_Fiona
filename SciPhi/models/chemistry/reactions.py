"""Chemical reaction kinetics model — rate laws and Arrhenius behaviour.

Governing equations:

* **Rate law**: :math:`r = k \\cdot [A]^m \\cdot [B]^n`
* **Concentration change**: :math:`\\frac{d[A]}{dt} = -k \\cdot [A]^m \\cdot [B]^n`
* **Arrhenius equation**: :math:`k = A \\cdot \\exp\\left(-\\frac{E_a}{R T}\\right)`

The model describes elementary reactions in a well-mixed, isothermal
environment.  Concentration changes are first-order in the concentrations
of each reactant raised to their respective reaction orders.

Assumptions
-----------
* Well-mixed (no spatial gradients).
* Constant temperature (basic kinetics — no thermal runaway).
* Elementary reactions (molecularity matches reaction order).
* No side or parallel reactions.

Mathematical form
-----------------
:class:`~SciPhi.interfaces.model.MathematicalForm.ODE_INITIAL_VALUE` —
the governing equation for :math:`[A]` is a first-order ordinary
differential equation in time.
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


class ChemicalReactionKineticsModel(ScientificModel):
    """Chemical reaction kinetics — rate laws and concentration evolution.

    The model captures the time-dependent concentration of reactants
    for an elementary bimolecular reaction :math:`aA + bB \\rightarrow`
    under isothermal conditions.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.CHEMISTRY

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.ODE_INITIAL_VALUE

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="rate_law",
                expression="r = k * [A]**m * [B]**n",
                description="Reaction rate as a function of concentrations "
                "and rate constant.",
            ),
            Equation(
                name="concentration_change_A",
                expression="d[A]/dt = -k * [A]**m * [B]**n",
                description="Time rate of change of reactant A "
                "concentration.",
            ),
            Equation(
                name="concentration_change_B",
                expression="d[B]/dt = -k * [A]**m * [B]**n",
                description="Time rate of change of reactant B "
                "concentration.",
            ),
            Equation(
                name="arrhenius",
                expression="k = A * exp(-Ea / (R * T))",
                description="Arrhenius equation relating the rate constant "
                "to temperature and activation energy.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="concentration_A",
                symbol="[A]",
                unit="mol L⁻¹",
                description="Molar concentration of reactant A.",
            ),
            Variable(
                name="concentration_B",
                symbol="[B]",
                unit="mol L⁻¹",
                description="Molar concentration of reactant B.",
            ),
            Variable(
                name="reaction_rate",
                symbol="r",
                unit="mol L⁻¹ s⁻¹",
                description="Instantaneous reaction rate.",
            ),
            Variable(
                name="time",
                symbol="t",
                unit="s",
                description="Time coordinate.",
            ),
            Variable(
                name="temperature",
                symbol="T",
                unit="K",
                description="Absolute temperature of the reaction mixture.",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="rate_constant",
                symbol="k",
                default_value=1.0,
                unit="L^(m+n-1) mol^(1-m-n) s⁻¹",
                description="Reaction rate constant (temperature "
                "dependent via Arrhenius).",
            ),
            Parameter(
                name="pre_exponential_factor",
                symbol="A",
                default_value=1.0e12,
                unit="L^(m+n-1) mol^(1-m-n) s⁻¹",
                description="Pre-exponential (frequency) factor in the "
                "Arrhenius equation.",
            ),
            Parameter(
                name="activation_energy",
                symbol="Ea",
                default_value=50.0e3,
                unit="J mol⁻¹",
                description="Activation energy of the reaction.",
            ),
            Parameter(
                name="reaction_order_m",
                symbol="m",
                default_value=1.0,
                unit="1",
                description="Reaction order with respect to reactant A.",
            ),
            Parameter(
                name="reaction_order_n",
                symbol="n",
                default_value=1.0,
                unit="1",
                description="Reaction order with respect to reactant B.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Well-mixed system — no spatial concentration "
                "gradients exist.",
                impact="Diffusion-limited or heterogeneous reactions "
                "require spatial modelling.",
            ),
            Assumption(
                statement="Constant temperature — the reaction proceeds "
                "isothermally.",
                impact="Exothermic or endothermic reactions that "
                "significantly change the bath temperature "
                "require coupled energy balance.",
            ),
            Assumption(
                statement="Elementary reaction — the reaction orders "
                "match the molecularity.",
                impact="Complex (multi-step) mechanisms may exhibit "
                "non-integer or concentration-dependent "
                "orders not captured here.",
            ),
            Assumption(
                statement="No side or parallel reactions — all reactant "
                "consumption follows a single pathway.",
                impact="Selectivity and by-product formation are "
                "not described.",
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
                description="Concentrations must be non-negative.",
                expression="[A] >= 0, [B] >= 0",
            ),
            Constraint(
                description="Rate constant must be non-negative.",
                expression="k >= 0",
            ),
            Constraint(
                description="Activation energy must be non-negative.",
                expression="Ea >= 0",
            ),
        ]

    @property
    def constants(self) -> list[PhysicalConstant]:
        return [
            PhysicalConstants.gas_constant,
        ]
