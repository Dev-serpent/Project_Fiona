"""Solver Selection Engine — matches computational problems to capable solvers.

The :class:`SolverSelectionEngine` maintains a registry of available solvers
and selects the most appropriate one for a given :class:`ComputationalProblem`.
Selection is treated as constraint satisfaction: the problem's mathematical
form, required order, and other attributes are matched against each solver's
declared :class:`SolverCapabilities`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from SciPhi.errors import NoSuitableSolverError

if TYPE_CHECKING:
    from SciPhi.interfaces.model import MathematicalForm
    from SciPhi.interfaces.solver import (
        ComputationalProblem,
        Solver,
        SolverCapabilities,
        SolverInfo,
    )


class SolverSelectionEngine:
    """Registry and selector for numerical solvers.

    Solvers are registered with the engine, which then matches them to
    computational problems based on capability declarations.

    Selection ranking (highest score wins):

    1. **Form match** — the solver's forms list includes the problem's form.
    2. **Order** — higher-order methods are preferred when the problem
       requires high accuracy.
    3. **Error estimation** — solvers with error estimation are preferred.
    4. **Parallel support** — solvers supporting parallelism are preferred
       for large problems.
    """

    def __init__(self) -> None:
        self._solvers: dict[str, Solver] = {}

    # ------------------------------------------------------------------
    # Registry management
    # ------------------------------------------------------------------

    def register(self, solver: Solver) -> None:
        """Register a solver with the engine.

        Args:
            solver: An instance of a :class:`Solver` subclass to register.
        """
        caps = solver.capabilities
        self._solvers[caps.name] = solver

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select(self, problem: ComputationalProblem) -> Solver:
        """Select the best solver for a given computational problem.

        Args:
            problem: The computational problem to find a solver for.

        Returns:
            The highest-ranked :class:`Solver` instance capable of handling
            the problem.

        Raises:
            NoSuitableSolverError: If no registered solver can handle the
                problem's mathematical form.
        """
        form = problem.mathematical_form
        candidates: list[tuple[Solver, SolverCapabilities, float]] = []

        for solver in self._solvers.values():
            caps = solver.capabilities
            if form in caps.forms:
                score = self._rank(caps, problem)
                candidates.append((solver, caps, score))

        if not candidates:
            raise NoSuitableSolverError(
                form=str(form),
                message=(
                    f"No registered solver supports mathematical form "
                    f"'{form.name}'. Available forms: "
                    f"{sorted({f.name for s in self._solvers.values() for f in s.capabilities.forms})}"
                ),
            )

        # Sort descending by score, then by name for determinism.
        candidates.sort(key=lambda t: (-t[2], t[1].name))
        best_solver, best_caps, _ = candidates[0]

        # Store selected solver info in problem metadata for traceability.
        problem.mathematical_form = form  # preserve

        return best_solver

    def list_capable(self, form: MathematicalForm) -> list[SolverInfo]:
        """List all solvers that can handle a given mathematical form.

        Args:
            form: The :class:`MathematicalForm` to query.

        Returns:
            A list of :class:`SolverInfo` for solvers supporting *form*.
        """
        capable: list[SolverInfo] = []
        for solver in self._solvers.values():
            caps = solver.capabilities
            if form in caps.forms:
                capable.append(solver.info())
        return capable

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def _rank(self, caps: SolverCapabilities, problem: ComputationalProblem) -> float:
        """Compute a numerical score for a solver's suitability.

        Higher scores indicate a better match. The score is a weighted sum
        of individual criteria.
        """
        score = 10.0  # Base score for being form-compatible.

        # Prefer higher-order methods.
        if caps.order:
            score += max(caps.order) * 2.0

        # Prefer error estimation.
        if caps.error_estimation:
            score += 3.0

        # Prefer parallel support.
        if caps.supports_parallel:
            score += 2.0

        # Bonus if the solver explicitly handles stiff systems when the
        # problem likely requires it (heuristic: tight tolerance).
        if caps.handles_stiff and problem.tolerance < 1e-8:
            score += 1.0

        return score
