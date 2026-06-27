"""Algebraic equation solver.

Provides root-finding for systems of algebraic equations using
Newton-Raphson, bisection, and fixed-point iteration.  The solver
operates purely on callable functions from the problem definition
and has no knowledge of the underlying science.
"""

from __future__ import annotations

import math
import time
from typing import Any, Callable

import numpy as np

from SciPhi.errors import SimulationFailedError
from SciPhi.interfaces.model import MathematicalForm
from SciPhi.interfaces.solver import (
    ComputationalProblem,
    SimulationResult,
    Solver,
    SolverCapabilities,
)

# ---------------------------------------------------------------------------
# Optional scipy integration
# ---------------------------------------------------------------------------

_HAS_SCIPY_OPTIMIZE = False
try:
    import scipy.optimize  # noqa: F401

    _HAS_SCIPY_OPTIMIZE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Pure-Python root-finding implementations
# ---------------------------------------------------------------------------


def _newton_raphson(
    f: Callable[[float], float],
    fprime: Callable[[float], float] | None,
    x0: float,
    tolerance: float,
    max_iter: int = 100,
) -> tuple[float, int]:
    """Newton-Raphson root-finding for a single equation.

    Uses the iteration:
        x_{n+1} = x_n - f(x_n) / f'(x_n)

    If *fprime* is ``None`` the derivative is approximated numerically
    via a central difference.

    Args:
        f: Function whose root is sought.
        fprime: Analytical derivative (optional).
        x0: Initial guess.
        tolerance: Convergence threshold.
        max_iter: Maximum number of iterations.

    Returns:
        Tuple ``(root, iterations)``.

    Raises:
        ValueError: If the method diverges or derivative is zero.
    """
    x = float(x0)
    for iteration in range(max_iter):
        fx = f(x)
        if abs(fx) < tolerance:
            return x, iteration + 1

        if fprime is not None:
            df = fprime(x)
        else:
            # Central difference approximation
            h = max(1e-8, 1e-4 * abs(x))
            df = (f(x + h) - f(x - h)) / (2.0 * h)

        if abs(df) < 1e-14:
            raise ValueError(f"Derivative near zero at x={x}, cannot continue")

        step = fx / df
        x -= step

    raise ValueError(
        f"Newton-Raphson did not converge after {max_iter} iterations (last f(x)={f(x):.6e})"
    )


def _bisection(
    f: Callable[[float], float],
    a: float,
    b: float,
    tolerance: float,
    max_iter: int = 100,
) -> tuple[float, int]:
    """Bisection method for root-finding.

    Requires that *f(a)* and *f(b)* have opposite signs (bracketing).

    Args:
        f: Continuous function whose root is sought.
        a: Left bound.
        b: Right bound.
        tolerance: Convergence threshold.
        max_iter: Maximum number of iterations.

    Returns:
        Tuple ``(root, iterations)``.

    Raises:
        ValueError: If *f(a)* and *f(b)* have the same sign.
    """
    fa = f(a)
    fb = f(b)

    if fa * fb >= 0:
        raise ValueError(
            f"Bisection requires opposite signs at bounds: f({a})={fa}, f({b})={fb}"
        )

    for iteration in range(max_iter):
        c = (a + b) / 2.0
        fc = f(c)

        if abs(fc) < tolerance or (b - a) / 2.0 < tolerance:
            return c, iteration + 1

        if fa * fc < 0:
            b, fb = c, fc
        else:
            a, fa = c, fc

    c = (a + b) / 2.0
    return c, max_iter


def _fixed_point(
    g: Callable[[float], float],
    x0: float,
    tolerance: float,
    max_iter: int = 100,
) -> tuple[float, int]:
    """Fixed-point iteration for root-finding.

    Solves ``x = g(x)`` by iterating ``x_{n+1} = g(x_n)``.

    Args:
        g: Function in the form ``g(x) = x``.
        x0: Initial guess.
        tolerance: Convergence threshold.
        max_iter: Maximum number of iterations.

    Returns:
        Tuple ``(fixed_point, iterations)``.

    Raises:
        ValueError: If the iteration diverges.
    """
    x = float(x0)
    for iteration in range(max_iter):
        x_next = g(x)
        if abs(x_next - x) < tolerance:
            return x_next, iteration + 1
        x = x_next

    raise ValueError(
        f"Fixed-point iteration did not converge after {max_iter} iterations"
    )


# ---------------------------------------------------------------------------
# Solver implementation
# ---------------------------------------------------------------------------


class AlgebraicSolver(Solver):
    """Solver for algebraic equations (root-finding).

    Supports three methods:

    * ``newton-raphson`` -- Newton-Raphson iteration (requires derivative
      or uses numerical approximation).
    * ``bisection`` -- Bracketed bisection (requires bounds).
    * ``fixed-point`` -- Fixed-point iteration (function must be in the
      form ``x = g(x)``).
    """

    def __init__(self) -> None:
        self._capabilities = SolverCapabilities(
            name="Algebraic Equation Solver",
            forms=[MathematicalForm.ALGEBRAIC],
            methods=["newton-raphson", "bisection", "fixed-point"],
            order=[1, 1, 1],
            supports_parallel=False,
            handles_stiff=None,
            error_estimation=False,
        )

    # ------------------------------------------------------------------
    # Solver ABC
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> SolverCapabilities:
        return self._capabilities

    def solve(self, problem: ComputationalProblem) -> SimulationResult:
        """Solve the algebraic system defined by *problem*.

        Expects each equation dict in ``problem.equations`` to contain:

        * ``"function"`` -- a callable ``f(x, **params)`` or a string
          that can be ``eval``\\ed to obtain one.
        * ``"variables"`` -- list of variable names (one per equation).
        * ``"derivative"`` (optional) -- derivative callable (Newton-Raphson).
        * ``"bounds"`` (optional) -- ``[a, b]`` interval (bisection).

        Initial guesses are read from ``problem.initial_conditions``.

        Args:
            problem: The fully specified computational problem.

        Returns:
            A :class:`SimulationResult` containing the solution values.

        Raises:
            SimulationFailedError: If root-finding fails or the problem
                definition is invalid.
        """
        method = (
            problem.discretization.get("method", "newton-raphson")
            if problem.discretization
            else "newton-raphson"
        )
        if method not in self._capabilities.methods:
            raise SimulationFailedError(
                type(self).__name__,
                f"Unsupported method '{method}'. Choose from {self._capabilities.methods}",
            )

        # --- Extract equations & initial guesses ----------------------------
        if not problem.equations:
            raise SimulationFailedError(
                type(self).__name__, "No equations provided in problem"
            )

        t0 = time.time()
        data: dict[str, list[float]] = {}
        converged = True
        total_iterations = 0

        try:
            if _HAS_SCIPY_OPTIMIZE and method in (
                "newton-raphson",
                "bisection",
            ):
                data, total_iterations = _solve_via_scipy(problem, method)
            else:
                data, total_iterations = _solve_pure_python(problem, method)
        except (ValueError, SimulationFailedError):
            converged = False
        except Exception as exc:
            raise SimulationFailedError(
                type(self).__name__, f"Algebraic solve failed: {exc}"
            ) from exc

        elapsed = time.time() - t0

        return SimulationResult(
            solver_id=type(self).__name__,
            solver_method=method,
            converged=converged,
            iterations=total_iterations,
            execution_time=elapsed,
            data=data,
            metadata={
                "method": method,
                "n_equations": len(problem.equations),
                "scipy_used": _HAS_SCIPY_OPTIMIZE
                and method in ("newton-raphson", "bisection"),
            },
            error_estimate=None,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_function(
    eq: dict[str, Any], key: str, idx: int
) -> Callable[..., float]:
    """Return a callable from an equation dict (see :func:`_extract_callable`)."""
    raw = eq.get(key)
    if raw is None:
        raise SimulationFailedError(
            "AlgebraicSolver", f"Equation {idx} is missing key '{key}'"
        )
    if callable(raw):
        return raw
    if isinstance(raw, str):
        try:
            return eval(raw, {"__builtins__": {}}, {})  # noqa: PGH001
        except Exception as exc:
            raise SimulationFailedError(
                "AlgebraicSolver",
                f"Cannot eval '{key}' for equation {idx}: {exc}",
            ) from exc
    raise SimulationFailedError(
        "AlgebraicSolver",
        f"Equation {idx}, key '{key}': expected callable or str, got {type(raw).__name__}",
    )


def _solve_via_scipy(
    problem: ComputationalProblem, method: str
) -> tuple[dict[str, list[float]], int]:
    """Use scipy.optimize for root-finding."""
    import scipy.optimize as spo

    data: dict[str, list[float]] = {}
    total_iterations = 0

    for idx, eq in enumerate(problem.equations):
        f = _extract_function(eq, "function", idx)
        variables = eq.get("variables", [f"x{idx}"])
        var_name = variables[0] if variables else f"x{idx}"

        # Initial guess from problem.initial_conditions
        x0 = float(problem.initial_conditions.get(var_name, 0.0))

        if method == "newton-raphson":
            fprime = eq.get("derivative")
            if fprime is not None:
                fprime_c = _extract_function(eq, "derivative", idx)
                sol = spo.newton(f, x0, fprime=fprime_c, tol=problem.tolerance, maxiter=100)
            else:
                sol = spo.newton(f, x0, tol=problem.tolerance, maxiter=100)
            data[var_name] = [float(sol)]
            total_iterations += 1  # scipy.newton doesn't expose iteration count easily

        elif method == "bisection":
            bounds = eq.get("bounds", [0.0, 1.0])
            if len(bounds) != 2:
                raise SimulationFailedError(
                    "AlgebraicSolver",
                    f"Bisection requires [a, b] bounds for equation {idx}, got {bounds}",
                )
            a, b = float(bounds[0]), float(bounds[1])
            # Check sign change
            fa, fb = f(a), f(b)
            if fa * fb >= 0:
                # Try to find a bracket automatically
                sol = spo.root_scalar(
                    f, bracket=None, method="bisect", x0=a, x1=b
                )
            else:
                sol = spo.root_scalar(f, bracket=[a, b], method="bisect")
            data[var_name] = [float(sol.root)]
            total_iterations += int(getattr(sol, "iterations", 1))

    return data, total_iterations


def _solve_pure_python(
    problem: ComputationalProblem, method: str
) -> tuple[dict[str, list[float]], int]:
    """Use pure-Python root-finding implementations."""
    data: dict[str, list[float]] = {}
    total_iterations = 0

    for idx, eq in enumerate(problem.equations):
        f = _extract_function(eq, "function", idx)
        variables = eq.get("variables", [f"x{idx}"])
        var_name = variables[0] if variables else f"x{idx}"

        x0 = float(problem.initial_conditions.get(var_name, 0.0))

        if method == "newton-raphson":
            fprime = eq.get("derivative")
            fprime_c = None
            if fprime is not None:
                fprime_c = _extract_function(eq, "derivative", idx)
            try:
                root, iters = _newton_raphson(
                    f, fprime_c, x0, problem.tolerance
                )
                data[var_name] = [root]
                total_iterations += iters
            except ValueError as exc:
                raise SimulationFailedError(
                    type(self).__name__, str(exc)
                ) from exc

        elif method == "bisection":
            bounds = eq.get("bounds", [0.0, 1.0])
            if len(bounds) != 2:
                raise SimulationFailedError(
                    "AlgebraicSolver",
                    f"Bisection requires [a, b] bounds for equation {idx}, got {bounds}",
                )
            try:
                root, iters = _bisection(
                    f, float(bounds[0]), float(bounds[1]), problem.tolerance
                )
                data[var_name] = [root]
                total_iterations += iters
            except ValueError as exc:
                raise SimulationFailedError(
                    type(self).__name__, str(exc)
                ) from exc

        elif method == "fixed-point":
            try:
                root, iters = _fixed_point(f, x0, problem.tolerance)
                data[var_name] = [root]
                total_iterations += iters
            except ValueError as exc:
                raise SimulationFailedError(
                    type(self).__name__, str(exc)
                ) from exc

    return data, total_iterations
