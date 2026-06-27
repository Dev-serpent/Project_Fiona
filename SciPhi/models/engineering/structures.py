"""Basic structural analysis — beam bending, stress–strain relationships.

Governing equations:

* **Hooke's law**:
  :math:`\\sigma = E \\varepsilon`
* **Beam bending (flexure formula)**:
  :math:`\\sigma = \\frac{M y}{I}`
* **Euler buckling**:
  :math:`P_{cr} = \\frac{\\pi^2 E I}{(K L)^2}`
* **Cantilever deflection (end load)**:
  :math:`\\delta = \\frac{P L^3}{3 E I}`

The model captures the linear-elastic response of structural elements
under axial, bending, and buckling loads.

Assumptions
-----------
* Linear elastic material behaviour (Hookean).
* Small deflections (linearised geometry).
* Isotropic, homogeneous material.
* Prismatic beams (constant cross-section).
* No shear deformation (Euler–Bernoulli beam theory).

Mathematical form
-----------------
:class:`~SciPhi.interfaces.model.MathematicalForm.ALGEBRAIC` —
all relations are closed-form algebraic equations among stress,
strain, geometry, and material properties.
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


class StructuralModel(ScientificModel):
    """Linear-elastic structural analysis — stress, strain, and deflection.

    Provides the fundamental algebraic relationships for analysing
    beams and columns under static loading within the linear-elastic
    regime.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.ENGINEERING

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.ALGEBRAIC

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="hookes_law",
                expression="sigma = E * epsilon",
                description="Hooke's law: linear relation between "
                "axial stress and strain.",
            ),
            Equation(
                name="beam_bending",
                expression="sigma = M * y / I",
                description="Flexure formula: bending stress at a "
                "distance y from the neutral axis.",
            ),
            Equation(
                name="euler_buckling",
                expression="P_cr = pi**2 * E * I / (K * L)**2",
                description="Euler critical buckling load for a slender "
                "column.",
            ),
            Equation(
                name="cantilever_deflection",
                expression="delta = P * L**3 / (3 * E * I)",
                description="End deflection of a cantilever beam under "
                "a point load at the free end.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="axial_stress",
                symbol="σ",
                unit="Pa",
                description="Normal stress in the material.",
            ),
            Variable(
                name="strain",
                symbol="ε",
                unit="1",
                description="Normal strain (dimensionless "
                "deformation).",
            ),
            Variable(
                name="deflection",
                symbol="δ",
                unit="m",
                description="Transverse deflection at the point "
                "of interest.",
            ),
            Variable(
                name="bending_moment",
                symbol="M",
                unit="N m",
                description="Internal bending moment at the section "
                "of interest.",
            ),
            Variable(
                name="critical_buckling_load",
                symbol="P_cr",
                unit="N",
                description="Critical axial load at which buckling "
                "occurs.",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="youngs_modulus",
                symbol="E",
                default_value=200.0e9,
                unit="Pa",
                description="Young's modulus of elasticity "
                "(default: structural steel).",
            ),
            Parameter(
                name="area_moment_inertia",
                symbol="I",
                default_value=1.0e-6,
                unit="m⁴",
                description="Second moment of area about the neutral "
                "axis.",
            ),
            Parameter(
                name="length",
                symbol="L",
                default_value=1.0,
                unit="m",
                description="Length of the beam or column.",
            ),
            Parameter(
                name="applied_load",
                symbol="P",
                default_value=1000.0,
                unit="N",
                description="Applied transverse or axial load.",
            ),
            Parameter(
                name="distance_from_neutral_axis",
                symbol="y",
                default_value=0.05,
                unit="m",
                description="Distance from the neutral axis to the "
                "point where stress is evaluated.",
            ),
            Parameter(
                name="column_effective_length_factor",
                symbol="K",
                default_value=1.0,
                unit="1",
                description="Effective length factor for buckling "
                "(1.0 = pinned-pinned, 0.5 = fixed-fixed, "
                "2.0 = cantilever).",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Linear elastic material — stress is "
                "proportional to strain (Hookean).",
                impact="Yielding, plasticity, and material "
                "nonlinearity are not captured.",
            ),
            Assumption(
                statement="Small deflections — geometry is assumed "
                "unchanged under load.",
                impact="Large-deformation effects (geometric "
                "nonlinearity, P-delta) are neglected.",
            ),
            Assumption(
                statement="Isotropic, homogeneous material.",
                impact="Anisotropic materials (composites, wood "
                "grain) or inhomogeneous sections require "
                "generalised constitutive models.",
            ),
            Assumption(
                statement="Prismatic beam — constant cross-section "
                "along the length.",
                impact="Tapered or non-uniform sections require "
                "integration along the beam axis.",
            ),
            Assumption(
                statement="No shear deformation — Euler–Bernoulli "
                "beam theory.",
                impact="Short, deep beams require Timoshenko "
                "theory to account for shear deflection.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Young's modulus must be positive.",
                expression="E > 0",
            ),
            Constraint(
                description="Area moment of inertia must be positive.",
                expression="I > 0",
            ),
            Constraint(
                description="Length must be positive.",
                expression="L > 0",
            ),
            Constraint(
                description="Effective length factor must be positive.",
                expression="K > 0",
            ),
        ]

    @property
    def constants(self) -> list:
        """No fundamental physical constants are required.

        Structural analysis uses only material and geometric parameters.
        """
        return []
