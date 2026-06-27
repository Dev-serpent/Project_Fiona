"""Electromagnetism model — Coulomb's law, Ohm's law, RC circuits.

Provides electrostatic and basic circuit equations including the transient
behaviour of an RC charging circuit.
"""

from __future__ import annotations

import math

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


class ElectromagnetismModel(ScientificModel):
    """Electrostatic and basic circuit dynamics.

    Governing equations:

    * :math:`F = k \\frac{q_1 q_2}{r^2}` — Coulomb's law for the
      electrostatic force between two point charges.
    * :math:`V = I R` — Ohm's law.
    * :math:`V_C(t) = V_0 \\left(1 - e^{-t/(RC)}\\right)` — capacitor
      voltage during RC charging.
    * :math:`I(t) = \\frac{V_0}{R} e^{-t/(RC)}` — current during RC
      charging.

    The model combines time-independent electrostatic relations with a
    first-order linear ODE (RC circuit).  The mathematical form is therefore
    :class:`~SciPhi.interfaces.model.MathematicalForm.HYBRID`.

    Assumptions
    -----------
    * Lumped-element model (all components ideal, no parasitic effects).
    * Linear, isotropic, homogeneous materials.
    * Point charges for Coulomb interactions.
    * Ideal voltage source (zero internal resistance).

    Constants
    ---------
    * :math:`k = 1/(4\\pi\\varepsilon_0)` — Coulomb's constant, derived
      from :data:`PhysicalConstants.vacuum_permittivity`.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.PHYSICS

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.HYBRID

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="coulombs_law",
                expression="F = k * q1 * q2 / r**2",
                description="Electrostatic force between two point "
                "charges separated by distance r.",
            ),
            Equation(
                name="ohms_law",
                expression="V = I * R",
                description="Voltage across a resistor is proportional "
                "to the current through it.",
            ),
            Equation(
                name="rc_charging_voltage",
                expression="V_C(t) = V0 * (1 - exp(-t / (R * C)))",
                description="Capacitor voltage as a function of time "
                "during RC charging from a constant "
                "voltage source.",
            ),
            Equation(
                name="rc_charging_current",
                expression="I(t) = (V0 / R) * exp(-t / (R * C))",
                description="Current as a function of time during RC "
                "charging.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="charge",
                symbol="q",
                unit="C",
                description="Electric charge (point charge magnitude).",
            ),
            Variable(
                name="voltage",
                symbol="V",
                unit="V",
                description="Electric potential difference.",
            ),
            Variable(
                name="current",
                symbol="I",
                unit="A",
                description="Electric current.",
            ),
            Variable(
                name="time",
                symbol="t",
                unit="s",
                description="Independent time variable.",
            ),
            Variable(
                name="electric_field",
                symbol="E",
                unit="V m⁻¹",
                description="Electric field magnitude.",
            ),
            Variable(
                name="capacitor_voltage",
                symbol="V_C",
                unit="V",
                description="Voltage across the capacitor (time-dependent).",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="capacitance",
                symbol="C",
                default_value=1e-6,
                unit="F",
                description="Capacitance of the capacitor.",
            ),
            Parameter(
                name="resistance",
                symbol="R",
                default_value=1e3,
                unit="Ω",
                description="Resistance of the resistor.",
            ),
            Parameter(
                name="source_voltage",
                symbol="V₀",
                default_value=5.0,
                unit="V",
                description="Constant voltage of the DC source.",
            ),
            Parameter(
                name="distance",
                symbol="r",
                default_value=1.0,
                unit="m",
                description="Separation distance between point charges.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Lumped-element model — all components are "
                "ideal and parasitic effects (lead inductance, "
                "dielectric leakage) are ignored.",
                impact="Model is inaccurate at high frequencies where "
                "distributed effects become important.",
            ),
            Assumption(
                statement="Linear, isotropic, homogeneous materials.",
                impact="Non-linear permittivity, permeability, or "
                "anisotropic media are not handled.",
            ),
            Assumption(
                statement="Point charges for Coulomb interactions.",
                impact="Finite-size charge distributions require "
                "integration over the charge density.",
            ),
            Assumption(
                statement="Ideal voltage source with zero internal "
                "resistance.",
                impact="Real sources have finite output impedance "
                "that affects transient behaviour.",
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
                description="Capacitance must be positive.",
                expression="C > 0",
            ),
            Constraint(
                description="Distance between charges must be positive.",
                expression="r > 0",
            ),
            Constraint(
                description="Time constant RC must be positive.",
                expression="R * C > 0",
            ),
        ]

    @property
    def constants(self) -> list[PhysicalConstant]:
        # Coulomb constant k = 1 / (4 * pi * epsilon_0)
        eps0 = PhysicalConstants.vacuum_permittivity
        k_value = 1.0 / (4.0 * math.pi * eps0.value)
        coulomb_constant = PhysicalConstant(
            name="Coulomb constant",
            symbol="k",
            value=k_value,
            unit="N m² C⁻²",
            uncertainty=None,
        )
        return [
            coulomb_constant,
            PhysicalConstants.vacuum_permittivity,
        ]
