"""SIR epidemic model — compartmental epidemiology.

Governing equations:

* **Susceptible**:
  :math:`\\frac{dS}{dt} = -\\beta \\frac{S I}{N}`
* **Infected**:
  :math:`\\frac{dI}{dt} = \\beta \\frac{S I}{N} - \\gamma I`
* **Recovered**:
  :math:`\\frac{dR}{dt} = \\gamma I`
* **Basic reproduction number**:
  :math:`R_0 = \\frac{\\beta}{\\gamma}`

The SIR model partitions a population into three compartments:
susceptible (S), infected (I), and recovered (R).  Transmission occurs
through mass-action mixing, and recovery confers permanent immunity.

Assumptions
-----------
* Closed population (no births, deaths, or migration).
* No vaccination or intervention.
* Homogeneous mixing — every individual has equal contact probability.
* Permanent immunity after recovery (no waning).
* Constant transmission and recovery rates.

Mathematical form
-----------------
:class:`~SciPhi.interfaces.model.MathematicalForm.ODE_INITIAL_VALUE` —
the compartment dynamics are governed by a system of three coupled
first-order ordinary differential equations.
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


class SIRModel(ScientificModel):
    """Susceptible–Infected–Recovered compartmental epidemic model.

    Describes the spread of an infectious disease through a well-mixed
    population with permanent immunity.  The model is the foundation
    of classical mathematical epidemiology.
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
                name="susceptible_rate",
                expression="dS/dt = -beta * S * I / N",
                description="Rate of change of the susceptible "
                "compartment due to new infections.",
            ),
            Equation(
                name="infected_rate",
                expression="dI/dt = beta * S * I / N - gamma * I",
                description="Rate of change of the infected compartment: "
                "new infections minus recoveries.",
            ),
            Equation(
                name="recovered_rate",
                expression="dR/dt = gamma * I",
                description="Rate of change of the recovered "
                "compartment due to recovery.",
            ),
            Equation(
                name="basic_reproduction_number",
                expression="R0 = beta / gamma",
                description="Basic reproduction number: average number "
                "of secondary infections from a single "
                "infectious individual in a fully "
                "susceptible population.",
            ),
        ]

    @property
    def variables(self) -> list[Variable]:
        return [
            Variable(
                name="susceptible",
                symbol="S",
                unit="1",
                description="Number of susceptible individuals.",
            ),
            Variable(
                name="infected",
                symbol="I",
                unit="1",
                description="Number of infected (and infectious) "
                "individuals.",
            ),
            Variable(
                name="recovered",
                symbol="R",
                unit="1",
                description="Number of recovered (immune) individuals.",
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
                name="transmission_rate",
                symbol="β",
                default_value=0.3,
                unit="s⁻¹",
                description="Per-capita transmission rate (contact rate "
                "times transmission probability).",
            ),
            Parameter(
                name="recovery_rate",
                symbol="γ",
                default_value=0.1,
                unit="s⁻¹",
                description="Per-capita recovery rate (inverse of the "
                "mean infectious period).",
            ),
            Parameter(
                name="total_population",
                symbol="N",
                default_value=1000.0,
                unit="1",
                description="Total population size (S + I + R = N, "
                "assumed constant).",
            ),
        ]

    @property
    def assumptions(self) -> list[Assumption]:
        return [
            Assumption(
                statement="Closed population — no births, deaths, or "
                "migration.",
                impact="Demographic processes or disease-induced "
                "mortality are not captured.",
            ),
            Assumption(
                statement="No vaccination or intervention.",
                impact="Control measures (masks, social distancing, "
                "vaccination) alter transmission dynamics.",
            ),
            Assumption(
                statement="Homogeneous mixing — every individual has "
                "equal contact probability.",
                impact="Age-structured, spatial, or network contact "
                "patterns are neglected.",
            ),
            Assumption(
                statement="Permanent immunity after recovery — no "
                "waning or reinfection.",
                impact="Diseases with temporary immunity or multiple "
                "strains require extended compartment "
                "models (e.g. SIRS).",
            ),
            Assumption(
                statement="Constant transmission and recovery rates.",
                impact="Time-varying behaviour (seasonality, behaviour "
                "change, treatment) is not represented.",
            ),
        ]

    @property
    def constraints(self) -> list[Constraint]:
        return [
            Constraint(
                description="Compartment sizes must be non-negative.",
                expression="S >= 0, I >= 0, R >= 0",
            ),
            Constraint(
                description="Total population is conserved.",
                expression="S + I + R = N",
            ),
            Constraint(
                description="Transmission and recovery rates must be "
                "non-negative.",
                expression="beta >= 0, gamma >= 0",
            ),
            Constraint(
                description="Total population must be positive.",
                expression="N > 0",
            ),
        ]

    @property
    def constants(self) -> list:
        """No fundamental physical constants are required.

        The SIR model is phenomenological and uses empirically
        determined epidemiological parameters.
        """
        return []
