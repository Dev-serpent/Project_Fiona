"""Basic circuit analysis — Ohm's law, Kirchhoff's laws, RC/RL circuits.

Governing equations:

* **Ohm's law**: :math:`V = I R`
* **Kirchhoff's voltage law**: :math:`\\sum V = 0`
* **Kirchhoff's current law**: :math:`\\sum I = 0`
* **RC charging**: :math:`V_C(t) = V_0 \\left(1 - e^{-t/(RC)}\\right)`
* **RL charging**: :math:`I(t) = \\frac{V_0}{R} \\left(1 - e^{-t R / L}\\right)`

The model covers the steady-state (algebraic) and transient (ODE)
behaviour of passive linear circuits.

Assumptions
-----------
* Lumped element model (dimensions ≪ wavelength).
* Ideal components (no parasitics, no saturation).
* Linear region (constant R, C, L).
* Zero initial stored energy for transients.

Mathematical form
-----------------
:class:`~SciPhi.interfaces.model.MathematicalForm.HYBRID` —
Ohm's law and Kirchhoff's laws are algebraic; the RC and RL charging
equations are solutions to first-order ODEs with initial values.
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


class CircuitModel(ScientificModel):
    """Linear circuit analysis — Ohm's law, Kirchhoff's laws, RC/RL
    transients.

    Provides the fundamental relationships for analysing passive
    linear circuits in both steady-state (DC) and transient regimes.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.ENGINEERING

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.HYBRID

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="ohms_law",
                expression="V = I * R",
                description="Ohm's law: voltage across a resistor "
                "equals current times resistance.",
            ),
            Equation(
                name="kirchhoff_voltage_law",
                expression="sum(V) = 0",
                description="Kirchhoff's voltage law: the sum of "
                "voltage drops around any closed loop "
                "is zero.",
            ),
            Equation(
                name="kirchhoff_current_law",
                expression="sum(I) = 0",
                description="Kirchhoff's current law: the sum of "
                "currents entering any node is zero.",
            ),
            Equation(
                name="rc_charging",
                expression="V_C(t) = V_0 * (1 - exp(-t / (R * C)))",
                description="Voltage across a charging capacitor "
                "in an RC circuit.",
            ),
            Equation(
                name="rl_charging",
                expression="I(t) = V_0 / R * (1 - exp(-t * R / L))",
                description="Current through an RL circuit "
                "approaching steady state.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="voltage",
                symbol="V",
                unit="V",
                description="Voltage (potential difference).",
            ),
            Variable(
                name="current",
                symbol="I",
                unit="A",
                description="Electric current.",
            ),
            Variable(
                name="charge",
                symbol="q",
                unit="C",
                description="Electric charge.",
            ),
            Variable(
                name="time",
                symbol="t",
                unit="s",
                description="Time coordinate.",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="resistance",
                symbol="R",
                default_value=1000.0,
                unit="Ω",
                description="Electrical resistance.",
            ),
            Parameter(
                name="capacitance",
                symbol="C",
                default_value=1.0e-6,
                unit="F",
                description="Capacitance (default: 1 µF).",
            ),
            Parameter(
                name="inductance",
                symbol="L",
                default_value=1.0e-3,
                unit="H",
                description="Inductance (default: 1 mH).",
            ),
            Parameter(
                name="source_voltage",
                symbol="V₀",
                default_value=5.0,
                unit="V",
                description="Source (applied) voltage.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Lumped element model — component dimensions "
                "are much smaller than the signal "
                "wavelength.",
                impact="At high frequencies (RF/microwave) "
                "distributed effects and transmission "
                "line theory are required.",
            ),
            Assumption(
                statement="Ideal components — no parasitic resistance, "
                "capacitance, or inductance.",
                impact="Real components have parasitic elements "
                "(ESR, ESL) that affect high-frequency "
                "or precision behaviour.",
            ),
            Assumption(
                statement="Linear region — R, C, and L are constant "
                "and independent of voltage or current.",
                impact="Nonlinear effects (diode breakdown, "
                "capacitor saturation, inductor core "
                "saturation) are not captured.",
            ),
            Assumption(
                statement="Zero initial stored energy for transient "
                "solutions.",
                impact="Non-zero initial conditions require the "
                "full complementary solution.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Resistance must be non-negative.",
                expression="R >= 0",
            ),
            Constraint(
                description="Capacitance must be non-negative.",
                expression="C >= 0",
            ),
            Constraint(
                description="Inductance must be non-negative.",
                expression="L >= 0",
            ),
        ]

    @property
    def constants(self) -> list:
        """No fundamental physical constants are required.

        Circuit analysis uses only component parameters supplied by
        the user.
        """
        return []
