"""Population dynamics — logistic growth model.

Governing equations:

* **Logistic growth**:
  :math:`\\frac{dN}{dt} = r N \\left(1 - \\frac{N}{K}\\right)`
* **Exponential growth** (limit :math:`N \\ll K`):
  :math:`\\frac{dN}{dt} = r N`
* **Carrying capacity approach**:
  :math:`N(t) = \\frac{K}{1 + \\frac{K - N_0}{N_0} e^{-rt}}`

The logistic growth model describes how a population grows in an
environment with finite resources: initial exponential growth
transitions to saturation as the population approaches the carrying
capacity.

Assumptions
-----------
* Constant environment (carrying capacity and growth rate are fixed).
* No migration (closed population).
* No age or stage structure — all individuals are identical.
* Continuous reproduction (no discrete generational effects).
* Density dependence acts instantaneously.

Mathematical form
-----------------
:class:`~SciPhi.interfaces.model.MathematicalForm.ODE_INITIAL_VALUE` —
the governing equation is a first-order ordinary differential equation
in time.
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


class LogisticGrowthModel(ScientificModel):
    """Logistic population growth with carrying capacity.

    Describes the dynamics of a single population in a resource-limited
    environment.  The growth rate declines linearly with population
    density and reaches zero when :math:`N = K`.
    """

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def domain(self) -> ScientificDomain:
        return ScientificDomain.BIOLOGY

    @property
    def mathematical_form(self) -> MathematicalForm:
        return MathematicalForm.ODE_INITIAL_VALUE

    @property
    def equations(self) -> list[Equation]:
        return [
            Equation(
                name="logistic_growth",
                expression="dN/dt = r * N * (1 - N / K)",
                description="Logistic growth rate: exponential growth "
                "damped by proximity to carrying capacity.",
            ),
            Equation(
                name="exponential_growth",
                expression="dN/dt = r * N",
                description="Exponential growth approximation valid "
                "when the population is far below carrying "
                "capacity (N << K).",
            ),
            Equation(
                name="carrying_capacity_solution",
                expression="N(t) = K / (1 + ((K - N0) / N0) * exp(-r * t))",
                description="Closed-form solution of the logistic "
                "equation.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="population_size",
                symbol="N",
                unit="1",
                description="Population size (number of individuals).",
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
                name="growth_rate",
                symbol="r",
                default_value=0.1,
                unit="s⁻¹",
                description="Intrinsic per-capita growth rate in the "
                "absence of density dependence.",
            ),
            Parameter(
                name="carrying_capacity",
                symbol="K",
                default_value=1000.0,
                unit="1",
                description="Maximum sustainable population size "
                "in the given environment.",
            ),
            Parameter(
                name="initial_population",
                symbol="N₀",
                default_value=10.0,
                unit="1",
                description="Population size at time t = 0.",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Constant environment — carrying capacity "
                "and growth rate are time-invariant.",
                impact="Seasonal or stochastic environments require "
                "time-varying parameters.",
            ),
            Assumption(
                statement="No migration — the population is closed.",
                impact="Immigration or emigration alters the dynamics "
                "and requires additional flux terms.",
            ),
            Assumption(
                statement="No age or stage structure — all individuals "
                "are identical.",
                impact="Stage-structured populations (juveniles vs. "
                "adults) require matrix models.",
            ),
            Assumption(
                statement="Continuous reproduction — no discrete "
                "generational effects.",
                impact="Species with discrete breeding seasons are "
                "better described by difference equations.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Population size must be non-negative.",
                expression="N >= 0",
            ),
            Constraint(
                description="Carrying capacity must be positive.",
                expression="K > 0",
            ),
            Constraint(
                description="Growth rate must be non-negative.",
                expression="r >= 0",
            ),
            Constraint(
                description="Initial population must be non-negative.",
                expression="N0 >= 0",
            ),
        ]

    @property
    def constants(self) -> list:
        """No fundamental physical constants are required.

        The logistic growth model is phenomenological and uses
        empirically determined parameters.
        """
        return []
