"""Dynamics model — Newton's second law, harmonic oscillator, damped oscillations.

Provides the governing equations for classical point-mass dynamics and linear
oscillatory systems including the damped harmonic oscillator.
"""

from __future__ import annotations

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


class DynamicsModel(ScientificModel):
    """Classical dynamics of a particle and the (damped) harmonic oscillator.

    Governing equations:

    * :math:`F = m a` — Newton's second law of motion.
    * :math:`\\ddot{x} + 2 \\zeta \\omega_0 \\dot{x} + \\omega_0^2 x = 0`
      — damped harmonic oscillator (second-order ODE).
    * :math:`\\omega_0 = \\sqrt{k / m}` — natural angular frequency.

    The model is formulated as an initial-value ODE in time, making it
    suitable for time-domain simulation of oscillatory mechanical systems.

    Assumptions
    -----------
    * Linear elastic regime (Hooke's law holds).
    * No external forcing (free oscillation — homogeneous equation).
    * Viscous (linear) damping model.
    * Point-mass representation.

    Mathematical form
    -----------------
    :class:`~SciPhi.interfaces.model.MathematicalForm.ODE_INITIAL_VALUE` —
    the governing equation is a second-order ordinary differential equation
    that requires initial conditions for position and velocity.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.PHYSICS

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.ODE_INITIAL_VALUE

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="newtons_second_law",
                expression="F = m * a",
                description="Newton's second law: net force equals mass "
                "times acceleration.",
            ),
            Equation(
                name="damped_harmonic_oscillator",
                expression="d2x/dt2 + 2*zeta*omega0*dx/dt + omega0**2*x = 0",
                description="Second-order linear ODE for a damped harmonic "
                "oscillator with no external forcing.",
            ),
            Equation(
                name="natural_frequency",
                expression="omega0 = sqrt(k / m)",
                description="Natural angular frequency of the "
                "undamped system.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="position",
                symbol="x",
                unit="m",
                description="Displacement from equilibrium.",
            ),
            Variable(
                name="velocity",
                symbol="v",
                unit="m s⁻¹",
                description="Instantaneous velocity (dx/dt).",
            ),
            Variable(
                name="time",
                symbol="t",
                unit="s",
                description="Independent time variable.",
            ),
            Variable(
                name="acceleration",
                symbol="a",
                unit="m s⁻²",
                description="Instantaneous acceleration (d²x/dt²).",
            ),
            Variable(
                name="force",
                symbol="F",
                unit="N",
                description="Net applied force.",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="mass",
                symbol="m",
                default_value=1.0,
                unit="kg",
                description="Mass of the oscillating object.",
            ),
            Parameter(
                name="spring_constant",
                symbol="k",
                default_value=10.0,
                unit="N m⁻¹",
                description="Spring (restoring force) constant.",
            ),
            Parameter(
                name="damping_ratio",
                symbol="ζ",
                default_value=0.1,
                unit="1",
                description="Dimensionless damping ratio.  ζ < 1 → "
                "underdamped, ζ = 1 → critically damped, "
                "ζ > 1 → overdamped.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Linear elastic regime — restoring force is "
                "proportional to displacement (Hooke's law).",
                impact="Model is invalid for large amplitudes where "
                "material non-linearities or geometric "
                "non-linearities become significant.",
            ),
            Assumption(
                statement="No external forcing — the oscillator is free "
                "(homogeneous ODE).",
                impact="Driven oscillations or systems with external "
                "excitation require an inhomogeneous term.",
            ),
            Assumption(
                statement="Damping is viscous (linear, proportional "
                "to velocity).",
                impact="Coulomb (dry friction) or quadratic drag damping "
                "are not captured.",
            ),
            Assumption(
                statement="Point-mass idealisation — no rotational or "
                "flexural degrees of freedom.",
                impact="Extended bodies or multi-degree-of-freedom systems "
                "require a generalised-coordinate formulation.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Mass must be positive.",
                expression="m > 0",
            ),
            Constraint(
                description="Spring constant must be positive.",
                expression="k > 0",
            ),
            Constraint(
                description="Damping ratio must be non-negative.",
                expression="zeta >= 0",
            ),
            Constraint(
                description="Natural frequency is real and non-negative.",
                expression="omega0 >= 0",
            ),
        ]

    @property
    def constants(self) -> list[PhysicalConstant]:
        # No fundamental constants are required beyond the user-provided
        # parameters m, k, ζ.
        return []
