"""Quantum mechanics model — particle in a box, quantum harmonic oscillator.

Provides the energy eigenvalues and wavefunctions for two fundamental
1D quantum systems: the infinite potential well and the quantum harmonic
oscillator.
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


class QuantumModel(ScientificModel):
    """Non-relativistic quantum mechanics in 1D — bound states.

    Governing equations:

    **Particle in a 1D infinite potential well (box):**

    * :math:`E_n = \\frac{n^2 h^2}{8 m L^2}` — energy eigenvalues.
    * :math:`\\psi_n(x) = \\sqrt{\\frac{2}{L}} \\sin\\left(\\frac{n \\pi x}{L}\\right)`
      — stationary-state wavefunctions on :math:`x \\in [0, L]`.

    **Quantum harmonic oscillator:**

    * :math:`E_n = \\hbar \\omega \\left(n + \\frac{1}{2}\\right)`
      — equally-spaced energy levels.

    The time-independent Schrödinger equation (TISE) is the underlying PDE;
    the energy-level expressions are its closed-form algebraic solutions for
    the two potentials.  The model's primary mathematical form is therefore
    :class:`~SciPhi.interfaces.model.MathematicalForm.PDE`.

    Assumptions
    -----------
    * Non-relativistic kinematics (Schrödinger, not Dirac, equation).
    * 1D geometry — motion is confined to a single spatial dimension.
    * Infinite potential well walls (no tunnelling out of the well).
    * Harmonic potential is purely quadratic (no anharmonic corrections).
    * Spin-independent Hamiltonian (spin degrees of freedom ignored).

    Constants
    ---------
    * :math:`h` — Planck constant.
    * :math:`\\hbar = h / (2\\pi)` — reduced Planck constant.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.PHYSICS

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.PDE

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="particle_in_a_box_energy",
                expression="E_n = n**2 * h**2 / (8 * m * L**2)",
                description="Energy eigenvalues for a particle in a 1D "
                "infinite potential well of length L.",
            ),
            Equation(
                name="particle_in_a_box_wavefunction",
                expression="psi_n(x) = sqrt(2/L) * sin(n * pi * x / L)",
                description="Normalised stationary-state wavefunctions "
                "for the 1D infinite well "
                "(x in [0, L]).",
            ),
            Equation(
                name="quantum_harmonic_oscillator_energy",
                expression="E_n = hbar * omega * (n + 1/2)",
                description="Energy eigenvalues for the 1D quantum "
                "harmonic oscillator.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="energy",
                symbol="E",
                unit="J",
                description="Energy eigenvalue of the quantum state.",
            ),
            Variable(
                name="wavefunction",
                symbol="ψ",
                unit="m⁻¹/²",
                description="Spatial wavefunction (probability amplitude).",
            ),
            Variable(
                name="position",
                symbol="x",
                unit="m",
                description="Spatial coordinate (1D).",
            ),
        ]

    @property
    def parameters(self) -> list[Parameter]:
        return [
            Parameter(
                name="quantum_number",
                symbol="n",
                default_value=1.0,
                unit="1",
                description="Principal quantum number (positive integer).",
            ),
            Parameter(
                name="box_length",
                symbol="L",
                default_value=1e-9,
                unit="m",
                description="Length of the 1D infinite potential well "
                "(~ nanometer scale for typical "
                "nanostructures).",
            ),
            Parameter(
                name="oscillator_frequency",
                symbol="ω",
                default_value=1.0e14,
                unit="rad s⁻¹",
                description="Angular frequency of the quantum harmonic "
                "oscillator potential.",
            ),
            Parameter(
                name="mass",
                symbol="m",
                default_value=9.1093837015e-31,
                unit="kg",
                description="Particle mass (defaults to electron mass).",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Non-relativistic kinematics — the Schrödinger "
                "equation is used instead of the Dirac equation.",
                impact="Model is invalid when particle kinetic energies "
                "approach or exceed the rest mass energy "
                "(≈ 511 keV for electrons).",
            ),
            Assumption(
                statement="1D geometry — motion is confined to a single "
                "spatial dimension.",
                impact="Degeneracies and coupling present in 2D/3D "
                "systems are not captured.",
            ),
            Assumption(
                statement="Infinite potential well walls — no tunnelling "
                "out of the well.",
                impact="Finite barriers allow tunnelling (leakage of "
                "the wavefunction into classically forbidden "
                "regions).",
            ),
            Assumption(
                statement="Harmonic potential is purely quadratic "
                "(no anharmonic corrections).",
                impact="Real molecular potentials (e.g. Morse potential) "
                "deviate from harmonicity at high "
                "excitation levels.",
            ),
            Assumption(
                statement="Spin-independent Hamiltonian — spin degrees "
                "of freedom are ignored.",
                impact="Spin-orbit coupling, Zeeman splitting, and "
                "Pauli exclusion are not included.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Quantum number must be a positive integer.",
                expression="n in {1, 2, 3, ...}",
            ),
            Constraint(
                description="Box length must be positive.",
                expression="L > 0",
            ),
            Constraint(
                description="Mass must be positive.",
                expression="m > 0",
            ),
            Constraint(
                description="Oscillator frequency must be non-negative.",
                expression="omega >= 0",
            ),
            Constraint(
                description="Position is bounded within the well "
                "(0 <= x <= L for particle in a box).",
                expression="0 <= x <= L",
            ),
        ]

    @property
    def constants(self) -> list[PhysicalConstant]:
        return [
            PhysicalConstants.planck_constant,
            PhysicalConstants.reduced_planck_constant,
        ]
