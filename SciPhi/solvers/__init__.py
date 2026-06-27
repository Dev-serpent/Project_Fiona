"""SciPhi solvers package.

Provides concrete implementations of the :class:`SciPhi.interfaces.solver.Solver`
ABC across four categories:

* ``deterministic`` -- ODE integrators and algebraic root-finders.
* ``stochastic`` -- Monte Carlo simulation.
* ``symbolic`` -- SymPy-based symbolic computation.
* ``optimization`` -- Minimisation/maximisation algorithms.

Each solver declares its :class:`SciPhi.interfaces.solver.SolverCapabilities`
so that the Solver Selection Engine can match it to a computational problem
without knowing the underlying science.
"""

from __future__ import annotations

from SciPhi.interfaces.solver import Solver
from SciPhi.solvers.deterministic import AlgebraicSolver, ODESolver
from SciPhi.solvers.optimization import Optimizer
from SciPhi.solvers.stochastic import MonteCarloSolver
from SciPhi.solvers.symbolic import SymbolicSolver

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def get_default_solver_registry() -> dict[str, Solver]:
    """Return a dictionary of identifier → solver instance for all built-in solvers.

    The returned mapping is suitable for use by the Solver Selection Engine
    and can be extended by external code with :meth:`dict.update`.

    Returns:
        A dict keyed by solver class name (e.g. ``"ODESolver"``) with
        corresponding solver instances.
    """
    return {
        "ODESolver": ODESolver(),
        "AlgebraicSolver": AlgebraicSolver(),
        "MonteCarloSolver": MonteCarloSolver(),
        "SymbolicSolver": SymbolicSolver(),
        "Optimizer": Optimizer(),
    }


__all__ = [
    "ODESolver",
    "AlgebraicSolver",
    "MonteCarloSolver",
    "SymbolicSolver",
    "Optimizer",
    "get_default_solver_registry",
]
