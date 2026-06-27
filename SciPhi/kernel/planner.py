"""Scientific Planner — translates free-form queries into structured investigation plans.

The :class:`ScientificPlanner` is responsible for parsing a user's natural-language
(or structured) query and producing a formal :class:`InvestigationPlan` that
captures the domain, governing equations, variables, parameters, assumptions,
constraints, boundary conditions, required accuracy, and mathematical form.

This module also defines the :class:`BoundaryCondition` and :class:`InvestigationPlan`
dataclasses used throughout the kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# Enums used at runtime in class attribute definitions are imported directly.
from SciPhi.interfaces.model import MathematicalForm as _MathematicalForm
from SciPhi.interfaces.model import ScientificDomain as _ScientificDomain

if TYPE_CHECKING:
    from SciPhi.interfaces.model import (
        Assumption,
        Constraint,
        Equation,
        MathematicalForm,
        Parameter,
        ScientificDomain,
        Variable,
    )


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoundaryCondition:
    """A boundary or initial condition applied to a specific variable.

    Attributes:
        variable: The name of the variable the condition applies to.
        type: The mathematical type of boundary condition
            (e.g. ``"dirichlet"``, ``"neumann"``, ``"periodic"``, ``"robin"``).
        value: The numerical value of the condition.
        location: A description of where the condition is applied
            (e.g. ``"x=0"``, ``"t=0"``, ``"surface"``).
    """

    variable: str
    type: str = "dirichlet"
    value: float = 0.0
    location: str = ""


@dataclass(frozen=True)
class InvestigationPlan:
    """A structured plan for a scientific investigation.

    Produced by :class:`ScientificPlanner` from a user query. Captures every
    aspect needed to select a model, compile it, and solve it.
    """

    query: str = ""
    domain: ScientificDomain | None = None
    governing_equations: list[Equation] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    parameters: list[Parameter] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    boundary_conditions: list[BoundaryCondition] = field(default_factory=list)
    required_accuracy: str = "medium"
    mathematical_form: MathematicalForm | None = None


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class ScientificPlanner:
    """Translates a user query into a structured :class:`InvestigationPlan`.

    The planner inspects the query text to determine the scientific domain,
    identify likely governing equations, extract variables and parameters,
    set assumptions and constraints, and classify the mathematical form.

    .. note::

        Keyword-based parsing is a stub. A future version will use NLP/LLM-based
        extraction for richer plan generation.
    """

    # Mapping from keywords to ScientificDomain values.
    _DOMAIN_KEYWORDS: dict[_ScientificDomain, list[str]] = {
        _ScientificDomain.PHYSICS: [
            "physics", "force", "motion", "velocity", "acceleration",
            "energy", "momentum", "thermodynamics", "electromagnetism",
            "quantum", "wave", "field",
        ],
        _ScientificDomain.CHEMISTRY: [
            "chemistry", "reaction", "chemical", "kinetics",
            "diffusion", "concentration", "rate",
        ],
        _ScientificDomain.BIOLOGY: [
            "biology", "population", "growth", "predator", "prey",
            "epidemic", "neural", "gene",
        ],
        _ScientificDomain.EARTH_SCIENCE: [
            "earth", "climate", "weather", "ocean", "atmospheric",
            "geological", "seismic",
        ],
        _ScientificDomain.ENGINEERING: [
            "engineering", "stress", "strain", "structural",
            "control", "circuit", "fluid",
        ],
        _ScientificDomain.MATHEMATICS: [
            "mathematics", "algebraic", "optimization",
            "linear", "polynomial", "matrix",
        ],
    }

    def __init__(self) -> None:
        # Populate form keyword mapping from the enum.
        self._form_keywords: dict[str, _MathematicalForm] = {
            "ode": _MathematicalForm.ODE_INITIAL_VALUE,
            "ordinary differential": _MathematicalForm.ODE_INITIAL_VALUE,
            "initial value": _MathematicalForm.ODE_INITIAL_VALUE,
            "boundary value": _MathematicalForm.ODE_BOUNDARY_VALUE,
            "pde": _MathematicalForm.PDE,
            "partial differential": _MathematicalForm.PDE,
            "algebraic": _MathematicalForm.ALGEBRAIC,
            "stochastic": _MathematicalForm.STOCHASTIC,
            "optimization": _MathematicalForm.OPTIMIZATION,
            "symbolic": _MathematicalForm.SYMBOLIC,
            "hybrid": _MathematicalForm.HYBRID,
        }

    async def create_plan(self, query: str) -> InvestigationPlan:
        """Parse a query and produce an :class:`InvestigationPlan`.

        Args:
            query: A free-form or structured query string describing the
                scientific problem to investigate.

        Returns:
            A fully populated :class:`InvestigationPlan` with the domain,
            mathematical form, and any variables, parameters, assumptions,
            and constraints that could be inferred from the query.

        .. note::

            The current implementation uses simple keyword matching. Variables,
            parameters, and equations are populated as stubs; a future NLP-based
            planner will extract them more accurately.
        """
        query_lower = query.lower()

        domain = self._detect_domain(query_lower)
        math_form = self._detect_form(query_lower)

        # Stub: in production these would be extracted via NLP / symbolic parsing.
        variables: list = []
        parameters: list = []
        assumptions: list = []
        constraints: list = []
        boundary_conditions: list = []
        equations: list = []

        plan = InvestigationPlan(
            query=query,
            domain=domain,
            governing_equations=equations,
            variables=variables,
            parameters=parameters,
            assumptions=assumptions,
            constraints=constraints,
            boundary_conditions=boundary_conditions,
            required_accuracy="medium",
            mathematical_form=math_form,
        )

        return plan

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_domain(self, query_lower: str) -> _ScientificDomain:
        """Return the most likely :class:`ScientificDomain` for *query_lower*."""
        scores: dict[_ScientificDomain, int] = {}
        for domain, keywords in self._DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score:
                scores[domain] = score

        if scores:
            return max(scores, key=scores.__getitem__)  # type: ignore[arg-type]
        return _ScientificDomain.PHYSICS  # conservative default

    def _detect_form(self, query_lower: str) -> _MathematicalForm | None:
        """Return the most likely :class:`MathematicalForm` or ``None``."""
        for keyword, form in self._form_keywords.items():
            if keyword in query_lower:
                return form

        # Generic fallback detection:
        if any(w in query_lower for w in ("change", "rate", "derivative", "over time")):
            return _MathematicalForm.ODE_INITIAL_VALUE
        if any(w in query_lower for w in ("distributed", "spatial", "field")):
            return _MathematicalForm.PDE

        return None
