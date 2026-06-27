"""Simulation Advisor — decides whether numerical simulation is necessary.

Before any computation begins, the :class:`SimulationAdvisor` checks whether
an analytical or closed-form solution exists, whether dimensional-analysis
shortcuts or conservation laws suffice, or whether the query matches a known
reference problem. If so, it advises the kernel to short-circuit and return
the known result instead of dispatching a solver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from SciPhi.kernel.planner import InvestigationPlan


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SimulationAdvice:
    """Advice from the :class:`SimulationAdvisor` on whether to simulate.

    Attributes:
        needs_simulation: ``True`` if numerical simulation is required;
            ``False`` if an analytical or known result can be returned instead.
        reason: A human-readable justification for the advice.
        alternative_approach: If *needs_simulation* is ``False``, a description
            of the alternative (e.g. closed-form formula, reference value).
        confidence: A value in [0, 1] indicating how certain the advisor is
            about its recommendation.
    """

    needs_simulation: bool = True
    reason: str = "No analytical shortcut identified."
    alternative_approach: str | None = None
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Advisor
# ---------------------------------------------------------------------------

# Cache of known reference problems (query → known answer description).
_KNOWN_REFERENCE_PROBLEMS: dict[str, str] = {
    "free fall": "s = ½gt²",
    "simple pendulum": "T = 2π√(L/g)",
    "ideal gas law": "PV = nRT",
    "hooke's law": "F = -kx",
    "coulomb's law": "F = kq₁q₂/r²",
    "newton's second law": "F = ma",
    "kinematic equation": "v² = u² + 2as",
}


class SimulationAdvisor:
    """Advises the kernel on whether numerical simulation is needed.

    The advisor checks multiple heuristics in order:

    1. **Known reference problems** — does the query match a problem with a
       well-known closed-form answer?
    2. **Dimensional analysis sufficiency** — can the answer be derived from
       dimensional reasoning alone?
    3. **Conservation law shortcuts** — do conservation principles directly
       give the answer?
    4. **Analytical form detection** — does the mathematical form admit a
       closed-form solution?

    If any heuristic produces a confident match, the advisor recommends
    skipping numerical simulation.
    """

    async def should_simulate(self, plan: InvestigationPlan) -> SimulationAdvice:
        """Determine whether numerical simulation is required for *plan*.

        Args:
            plan: A structured :class:`InvestigationPlan` describing the
                scientific problem.

        Returns:
            A :class:`SimulationAdvice` instance indicating whether to
            simulate and, if not, what alternative approach to use.
        """
        # 1. Check known reference problems.
        advice = self._check_reference_problems(plan)
        if advice is not None:
            return advice

        # 2. Check dimensional analysis sufficiency (stub).
        advice = self._check_dimensional_analysis(plan)
        if advice is not None:
            return advice

        # 3. Check conservation law shortcuts (stub).
        advice = self._check_conservation_laws(plan)
        if advice is not None:
            return advice

        # 4. Check if the mathematical form admits closed-form solution (stub).
        advice = self._check_analytical_form(plan)
        if advice is not None:
            return advice

        # Default: simulation required.
        return SimulationAdvice(
            needs_simulation=True,
            reason="No analytical shortcut or known result matched this investigation plan.",
            alternative_approach=None,
            confidence=0.9,
        )

    # ------------------------------------------------------------------
    # Internal heuristic checks
    # ------------------------------------------------------------------

    def _check_reference_problems(
        self, plan: InvestigationPlan,
    ) -> SimulationAdvice | None:
        """Return advice if the plan matches a known reference problem."""
        # Build a set of tokens from the plan — include the original query
        # text (if available), equation names, variable names, and boundary
        # condition locations.
        query_tokens: set[str] = set()

        if plan.query:
            for token in plan.query.lower().split():
                # Strip common punctuation for cleaner matching.
                cleaned = token.strip(",.!?;:'\"()[]{}")
                if cleaned:
                    query_tokens.add(cleaned)

        for eq in plan.governing_equations:
            query_tokens.add(eq.name.lower())
        for var in plan.variables:
            query_tokens.add(var.name.lower())
        for bc in plan.boundary_conditions:
            query_tokens.add(bc.variable.lower())

        for key, formula in _KNOWN_REFERENCE_PROBLEMS.items():
            key_tokens = set(key.split())
            if key_tokens & query_tokens:
                return SimulationAdvice(
                    needs_simulation=False,
                    reason=f"Query matches known reference problem '{key}' "
                           f"with closed-form solution: {formula}.",
                    alternative_approach=f"Use closed-form solution: {formula}",
                    confidence=0.95,
                )

        return None

    def _check_dimensional_analysis(
        self, plan: InvestigationPlan,
    ) -> SimulationAdvice | None:
        """Check whether dimensional analysis alone suffices (stub)."""
        # Future: use Buckingham Pi theorem to determine if dimensional
        # analysis can reduce the problem to a dimensionless form with
        # a known relationship.
        return None

    def _check_conservation_laws(
        self, plan: InvestigationPlan,
    ) -> SimulationAdvice | None:
        """Check whether conservation laws give a direct answer (stub)."""
        # Future: check if the plan's constraints include conservation laws
        # that directly determine the answer.
        return None

    def _check_analytical_form(
        self, plan: InvestigationPlan,
    ) -> SimulationAdvice | None:
        """Check whether the mathematical form admits a closed-form solution (stub)."""
        # Future: use symbolic algebra to determine if the equations have a
        # known closed-form solution.
        return None
