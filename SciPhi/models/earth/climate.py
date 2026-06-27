"""Simple energy balance climate model — zero-dimensional.

Governing equations:

* **Energy balance**:
  :math:`C \\frac{dT}{dt} = \\frac{(1 - \\alpha) S}{4} - \\varepsilon \\sigma T^4`
* **Albedo feedback** (simplified linear):
  :math:`\\alpha(T) = \\alpha_0 + \\gamma (T - T_0)`

The model treats the Earth as a single uniform layer with heat capacity
:math:`C`, solar forcing :math:`S`, and outgoing longwave radiation
governed by the Stefan–Boltzmann law.  A simplified linear albedo
feedback couples the surface temperature back to the planetary albedo.

Assumptions
-----------
* Zero-dimensional (single global-average temperature).
* Gray atmosphere (single effective emissivity).
* No ocean circulation or heat transport.
* Linear albedo feedback (valid only near the reference temperature).
* No seasonal or diurnal cycle.

Mathematical form
-----------------
:class:`~SciPhi.interfaces.model.MathematicalForm.HYBRID` —
the energy balance is a first-order ODE in time (:math:`dT/dt`), while
the albedo parametrisation is an instantaneous algebraic relation.
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


class EnergyBalanceModel(ScientificModel):
    """Zero-dimensional energy balance climate model.

    Describes the time evolution of the Earth's global-average surface
    temperature under radiative forcing with a simplified linear albedo
    feedback.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.EARTH_SCIENCE

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.HYBRID

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="energy_balance",
                expression="C * dT/dt = (1 - alpha) * S / 4 - epsilon "
                "* sigma * T**4",
                description="Energy balance: net incoming shortwave "
                "radiation minus outgoing longwave "
                "radiation equals heat storage rate.",
            ),
            Equation(
                name="albedo_feedback",
                expression="alpha(T) = alpha_0 + gamma * (T - T_0)",
                description="Linearised temperature dependence of "
                "planetary albedo.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="surface_temperature",
                symbol="T",
                unit="K",
                description="Global average surface temperature.",
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
                name="solar_constant",
                symbol="S",
                default_value=1361.0,
                unit="W m⁻²",
                description="Total solar irradiance at Earth's mean "
                "orbital distance.",
            ),
            Parameter(
                name="albedo",
                symbol="α₀",
                default_value=0.3,
                unit="1",
                description="Reference planetary albedo (fraction of "
                "incident solar radiation reflected).",
            ),
            Parameter(
                name="emissivity",
                symbol="ε",
                default_value=0.62,
                unit="1",
                description="Effective planetary emissivity (gray "
                "atmosphere approximation).",
            ),
            Parameter(
                name="heat_capacity",
                symbol="C",
                default_value=5.0e7,
                unit="J m⁻² K⁻¹",
                description="Effective heat capacity of the Earth "
                "system per unit area (≈ 10 m mixed "
                "layer ocean).",
            ),
            Parameter(
                name="albedo_feedback_coefficient",
                symbol="γ",
                default_value=0.01,
                unit="K⁻¹",
                description="Linear albedo feedback strength "
                "(change in albedo per Kelvin).",
            ),
            Parameter(
                name="reference_temperature",
                symbol="T₀",
                default_value=288.0,
                unit="K",
                description="Reference temperature about which "
                "albedo is linearised.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Zero-dimensional — a single global-average "
                "temperature represents the entire planet.",
                impact="Regional climate patterns, latitudinal "
                "temperature gradients, and circulation "
                "are not resolved.",
            ),
            Assumption(
                statement="Gray atmosphere — a single effective "
                "emissivity approximates radiative transfer.",
                impact="Spectrally resolved radiative effects "
                "(greenhouse gas bands, clouds) "
                "are lumped into one parameter.",
            ),
            Assumption(
                statement="No ocean circulation or lateral heat "
                "transport.",
                impact="Ocean heat uptake and poleward transport "
                "significantly affect transient climate "
                "response.",
            ),
            Assumption(
                statement="Linear albedo feedback — valid only near "
                "the reference temperature.",
                impact="Strong nonlinearities (ice–albedo "
                "tipping points at high temperatures) "
                "are not captured.",
            ),
            Assumption(
                statement="No seasonal or diurnal cycle.",
                impact="Orbital forcing and daily temperature "
                "variations are averaged out.",
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
                description="Albedo must be in the physical range "
                "[0, 1].",
                expression="0 <= alpha <= 1",
            ),
            Constraint(
                description="Emissivity must be in the range (0, 1].",
                expression="0 < epsilon <= 1",
            ),
            Constraint(
                description="Heat capacity must be positive.",
                expression="C > 0",
            ),
        ]

    @property
    def constants(self) -> list[PhysicalConstant]:
        return [
            PhysicalConstants.stefan_boltzmann_constant,
        ]
