"""Kinematics model — 1D and 2D projectile motion under constant gravity.

Provides equations for uniformly-accelerated motion (constant acceleration)
suitable for projectile trajectory calculations near the Earth's surface.
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


class KinematicsModel(ScientificModel):
    """Kinematics of a point mass under constant gravitational acceleration.

    Encapsulates the standard SUVAT equations for 1D and 2D motion:

    * :math:`v = v_0 + a t`
    * :math:`x = x_0 + v_0 t + \\frac{1}{2} a t^2`
    * :math:`v^2 = v_0^2 + 2 a (x - x_0)`

    The model treats the **x**-axis as horizontal and the **y**-axis as
    vertical (positive upward).  Gravitational acceleration acts along the
    negative **y** direction by default.

    Assumptions
    -----------
    * No air resistance or drag forces.
    * Constant gravitational acceleration (near Earth's surface).
    * Flat, non-rotating reference frame (inertial over short distances).
    * Point-mass projectile (no extended-body effects).

    Mathematical form
    -----------------
    :class:`~SciPhi.interfaces.model.MathematicalForm.ALGEBRAIC` —
    the equations are closed-form algebraic expressions with no derivatives
    or integrals that require numerical integration.
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
                name="velocity_after_time",
                expression="v = v0 + a * t",
                description="Velocity as a function of initial velocity, "
                "constant acceleration, and time.",
            ),
            Equation(
                name="displacement_after_time",
                expression="x = x0 + v0 * t + 0.5 * a * t**2",
                description="Position as a function of initial position, "
                "initial velocity, constant acceleration, and time.",
            ),
            Equation(
                name="velocity_displacement_relation",
                expression="v**2 = v0**2 + 2 * a * (x - x0)",
                description="Velocity–displacement relation independent "
                "of time.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="x_position",
                symbol="x",
                unit="m",
                description="Horizontal position of the projectile.",
            ),
            Variable(
                name="y_position",
                symbol="y",
                unit="m",
                description="Vertical position of the projectile.",
            ),
            Variable(
                name="x_velocity",
                symbol="v_x",
                unit="m s⁻¹",
                description="Horizontal velocity component.",
            ),
            Variable(
                name="y_velocity",
                symbol="v_y",
                unit="m s⁻¹",
                description="Vertical velocity component.",
            ),
            Variable(
                name="time",
                symbol="t",
                unit="s",
                description="Elapsed time since launch.",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="gravitational_acceleration",
                symbol="g",
                default_value=PhysicalConstants.standard_gravity.value,
                unit="m s⁻²",
                description="Constant gravitational acceleration "
                "(positive downward).",
            ),
            Parameter(
                name="initial_angle",
                symbol="θ",
                default_value=45.0,
                unit="deg",
                description="Launch angle measured from the horizontal.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="No air resistance or drag forces act on the "
                "projectile.",
                impact="Model is accurate only for dense, slow-moving "
                "objects over short distances.  Trajectories in "
                "air deviate significantly at high speeds.",
            ),
            Assumption(
                statement="Gravitational acceleration is constant "
                "(near-Earth surface).",
                impact="Model breaks down for large altitude changes "
                "(> 1 km) where g varies appreciably.",
            ),
            Assumption(
                statement="Reference frame is inertial (flat, "
                "non-rotating Earth).",
                impact="Coriolis and centrifugal effects are neglected.  "
                "Long-range or long-duration flights require a "
                "rotating-frame treatment.",
            ),
            Assumption(
                statement="Projectile is treated as a point mass.",
                impact="Rotational dynamics, aerodynamic lift, and "
                "finite-size effects are ignored.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Time must be non-negative.",
                expression="t >= 0",
            ),
            Constraint(
                description="Mass is positive (implied; mass cancels out "
                "in kinematics).",
                expression="m > 0",
            ),
        ]

    @property
    def constants(self) -> list[PhysicalConstant]:
        return [
            PhysicalConstants.standard_gravity,
        ]
