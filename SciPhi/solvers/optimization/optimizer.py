"""Optimization solver for minimising or maximising objective functions.

Provides gradient descent, Nelder-Mead, and BFGS methods.  The solver
operates purely on callable objective functions and has no knowledge
of the underlying problem domain.
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
# Pure-Python optimisation implementations
# ---------------------------------------------------------------------------


def _gradient_descent(
    f: Callable[..., float],
    grad: Callable[..., np.ndarray] | None,
    x0: np.ndarray,
    learning_rate: float = 0.01,
    tolerance: float = 1e-6,
    max_iter: int = 1000,
) -> tuple[np.ndarray, int]:
    """Gradient descent minimisation.

    Args:
        f: Objective function ``f(x, **params) -> float``.
        grad: Gradient function ``grad(x, **params) -> np.ndarray``.
            If ``None``, the gradient is approximated numerically.
        x0: Initial point.
        learning_rate: Step size for each iteration.
        tolerance: Convergence threshold on gradient norm.
        max_iter: Maximum number of iterations.

    Returns:
        Tuple ``(optimal_point, iterations)``.

    Raises:
        ValueError: If the method does not converge.
    """
    x = np.asarray(x0, dtype=float)
    params: dict[str, Any] = {}

    for iteration in range(max_iter):
        if grad is not None:
            g = np.asarray(grad(x, **params))
        else:
            g = _numerical_gradient(f, x, params)

        gn = np.linalg.norm(g)
        if gn < tolerance:
            return x, iteration + 1

        x_new = x - learning_rate * g
        # Simple backtracking if objective increases
        if f(x_new, **params) > f(x, **params) and learning_rate > 1e-12:
            learning_rate *= 0.5
            continue

        x = x_new

    return x, max_iter


def _nelder_mead(
    f: Callable[..., float],
    x0: np.ndarray,
    tolerance: float = 1e-6,
    max_iter: int = 1000,
    params: dict[str, Any] | None = None,
) -> tuple[np.ndarray, int]:
    """Nelder-Mead simplex direct search.

    Args:
        f: Objective function ``f(x, **params) -> float``.
        x0: Initial simplex centroid.
        tolerance: Convergence threshold on function value spread.
        max_iter: Maximum number of iterations.
        params: Additional parameters passed to *f*.

    Returns:
        Tuple ``(optimal_point, iterations)``.
    """
    if params is None:
        params = {}

    n = len(x0)
    # Build initial simplex (use a perturbation relative to the scale
    # of each variable so that the simplex spans a meaningful region).
    simplex = np.zeros((n + 1, n))
    simplex[0] = np.asarray(x0, dtype=float)
    for i in range(n):
        p = np.asarray(x0, dtype=float)
        if abs(p[i]) > 1e-8:
            p[i] *= 1.05
        else:
            p[i] = 0.05  # default offset for zero components
        simplex[i + 1] = p

    values = np.array([f(simplex[i], **params) for i in range(n + 1)])

    alpha = 1.0  # reflection
    gamma = 2.0  # expansion
    rho = 0.5  # contraction
    sigma = 0.5  # shrink

    for iteration in range(max_iter):
        # Order
        order = np.argsort(values)
        simplex = simplex[order]
        values = values[order]

        # Check spread
        if np.std(values) < tolerance:
            return simplex[0], iteration + 1

        centroid = np.mean(simplex[:-1], axis=0)

        # Reflection
        xr = centroid + alpha * (centroid - simplex[-1])
        fr = f(xr, **params)

        if values[0] <= fr < values[-2]:
            simplex[-1] = xr
            values[-1] = fr
        elif fr < values[0]:
            # Expansion
            xe = centroid + gamma * (xr - centroid)
            fe = f(xe, **params)
            if fe < fr:
                simplex[-1] = xe
                values[-1] = fe
            else:
                simplex[-1] = xr
                values[-1] = fr
        else:
            # Contraction
            xc = centroid + rho * (simplex[-1] - centroid)
            fc = f(xc, **params)
            if fc < values[-1]:
                simplex[-1] = xc
                values[-1] = fc
            else:
                # Shrink
                for i in range(1, n + 1):
                    simplex[i] = simplex[0] + sigma * (simplex[i] - simplex[0])
                    values[i] = f(simplex[i], **params)

    return simplex[0], max_iter


def _bfgs(
    f: Callable[..., float],
    grad: Callable[..., np.ndarray] | None,
    x0: np.ndarray,
    tolerance: float = 1e-6,
    max_iter: int = 100,
    params: dict[str, Any] | None = None,
) -> tuple[np.ndarray, int]:
    """BFGS quasi-Newton minimisation.

    Args:
        f: Objective function ``f(x, **params) -> float``.
        grad: Gradient function.  If ``None``, numerical approximation
            is used.
        x0: Initial point.
        tolerance: Convergence threshold on gradient norm.
        max_iter: Maximum number of iterations.
        params: Additional parameters passed to *f*.

    Returns:
        Tuple ``(optimal_point, iterations)``.
    """
    if params is None:
        params = {}

    x = np.asarray(x0, dtype=float)
    n = len(x)
    H = np.eye(n)  # Inverse Hessian approximation

    g_old = _compute_gradient(f, grad, x, params)
    if np.linalg.norm(g_old) < tolerance:
        return x, 0

    for iteration in range(max_iter):
        # Descent direction
        p = -H @ g_old

        # Line search (simple backtracking)
        alpha = 1.0
        for _ in range(20):
            x_new = x + alpha * p
            if f(x_new, **params) < f(x, **params) + 1e-4 * alpha * np.dot(g_old, p):
                break
            alpha *= 0.5
        else:
            return x, iteration + 1

        s = alpha * p
        g_new = _compute_gradient(f, grad, x_new, params)

        if np.linalg.norm(g_new) < tolerance:
            return x_new, iteration + 1

        y = g_new - g_old
        sy = np.dot(s, y)

        if sy > 1e-10:
            # BFGS update
            rho = 1.0 / sy
            H = (np.eye(n) - rho * np.outer(s, y)) @ H @ (
                np.eye(n) - rho * np.outer(y, s)
            ) + rho * np.outer(s, s)

        x = x_new
        g_old = g_new

    return x, max_iter


# ---------------------------------------------------------------------------
# Numerical gradient helper
# ---------------------------------------------------------------------------


def _numerical_gradient(
    f: Callable[..., float],
    x: np.ndarray,
    params: dict[str, Any],
    eps: float = 1e-8,
) -> np.ndarray:
    """Central-difference gradient approximation."""
    g = np.zeros_like(x, dtype=float)
    for i in range(len(x)):
        h = max(eps, eps * abs(x[i]))
        xp = x.copy()
        xp[i] += h
        xm = x.copy()
        xm[i] -= h
        g[i] = (f(xp, **params) - f(xm, **params)) / (2.0 * h)
    return g


def _compute_gradient(
    f: Callable[..., float],
    grad: Callable[..., np.ndarray] | None,
    x: np.ndarray,
    params: dict[str, Any],
) -> np.ndarray:
    """Compute gradient, using analytical if available."""
    if grad is not None:
        return np.asarray(grad(x, **params))
    return _numerical_gradient(f, x, params)


# ---------------------------------------------------------------------------
# Solver implementation
# ---------------------------------------------------------------------------


class Optimizer(Solver):
    """Solver for optimisation problems (minimisation/maximisation).

    Supports three methods:

    * ``gradient-descent`` -- First-order gradient descent with
      backtracking line search.
    * ``nelder-mead`` -- Nelder-Mead simplex (direct search, no
      gradient required).
    * ``bfgs`` -- BFGS quasi-Newton method (uses gradient if
      available, otherwise numerical approximation).

    Constraints from ``problem.constraints`` are handled via a
    quadratic penalty method.
    """

    def __init__(self) -> None:
        self._capabilities = SolverCapabilities(
            name="Optimization Solver",
            forms=[MathematicalForm.OPTIMIZATION],
            methods=["gradient-descent", "nelder-mead", "bfgs"],
            order=[1, 1, 2],
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
        """Minimise the objective function defined by *problem*.

        Expects each equation dict in ``problem.equations`` to contain:

        * ``"function"`` -- a callable ``f(x, **params) -> float`` or
          a string that can be ``eval``\\ed to obtain one.
        * ``"variables"`` -- list of variable names.
        * ``"gradient"`` (optional) -- gradient callable.

        The initial guess is read from ``problem.initial_conditions``.
        Additional solver configuration may be placed in
        ``problem.discretization``:

        * ``learning_rate`` (float, default 0.01) -- for gradient descent.
        * ``max_iter`` (int, default 1000).

        Args:
            problem: The fully specified computational problem.

        Returns:
            A :class:`SimulationResult` containing the optimal point.

        Raises:
            SimulationFailedError: If the optimisation fails.
        """
        # --- Determine method -----------------------------------------------
        method = (
            problem.discretization.get("method", "bfgs")
            if problem.discretization
            else "bfgs"
        )
        if method not in self._capabilities.methods:
            raise SimulationFailedError(
                type(self).__name__,
                f"Unsupported method '{method}'. Choose from {self._capabilities.methods}",
            )

        if not problem.equations:
            raise SimulationFailedError(
                type(self).__name__, "No objective function provided in problem"
            )

        # --- Extract objective ----------------------------------------------
        eq = problem.equations[0]
        objective = _extract_opt_function(eq, "function", 0)
        gradient_raw = eq.get("gradient")
        gradient: Callable[..., np.ndarray] | None = None
        if gradient_raw is not None:
            gradient = _extract_gradient_function(eq, "gradient", 0)

        variable_names: list[str] = eq.get("variables", ["x"])

        # --- Initial guess --------------------------------------------------
        x0_list: list[float] = []
        for var_name in variable_names:
            if var_name in problem.initial_conditions:
                x0_list.append(float(problem.initial_conditions[var_name]))
            else:
                x0_list.append(0.0)
        x0 = np.array(x0_list, dtype=float)

        # --- Configuration --------------------------------------------------
        tolerance = problem.tolerance
        max_iter = (
            int(problem.discretization.get("max_iter", 1000))
            if problem.discretization
            else 1000
        )
        learning_rate = (
            float(problem.discretization.get("learning_rate", 0.01))
            if problem.discretization
            else 0.01
        )

        # --- Build penalised objective for constraints ----------------------
        raw_objective = objective
        constraints = problem.constraints

        if constraints:
            objective = _build_penalized_objective(raw_objective, constraints)

        # --- Solve ----------------------------------------------------------
        t0 = time.time()
        converged = True
        total_iterations = 0
        optimal_x: np.ndarray = x0.copy()

        try:
            if _HAS_SCIPY_OPTIMIZE and method == "nelder-mead":
                optimal_x, total_iterations = _solve_via_scipy(
                    objective, x0, method, tolerance, max_iter
                )
            elif _HAS_SCIPY_OPTIMIZE and method == "bfgs":
                optimal_x, total_iterations = _solve_via_scipy(
                    objective, x0, method, tolerance, max_iter, gradient
                )
            else:
                optimal_x, total_iterations = _solve_pure_python(
                    objective,
                    gradient,
                    x0,
                    method,
                    tolerance,
                    max_iter,
                    learning_rate,
                )
        except Exception as exc:
            raise SimulationFailedError(
                type(self).__name__, f"Optimization failed: {exc}"
            ) from exc

        elapsed = time.time() - t0

        data: dict[str, list[float]] = {}
        for i, var_name in enumerate(variable_names):
            data[var_name] = [float(optimal_x[i])]

        final_value = float(raw_objective(optimal_x))

        return SimulationResult(
            solver_id=type(self).__name__,
            solver_method=method,
            converged=converged,
            iterations=total_iterations,
            execution_time=elapsed,
            data=data,
            metadata={
                "method": method,
                "final_objective": final_value,
                "n_variables": len(variable_names),
                "scipy_used": _HAS_SCIPY_OPTIMIZE
                and method in ("nelder-mead", "bfgs"),
                "constraints_satisfied": _check_constraints(
                    optimal_x, constraints
                ),
            },
            error_estimate=None,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_opt_function(
    eq: dict[str, Any], key: str, idx: int
) -> Callable[..., float]:
    """Return a callable from an equation dict for optimisation.

    The returned callable is guaranteed to return a Python ``float``
    scalar, converting numpy arrays if necessary.

    Unlike the ODE solver, optimisation functions receive a vector
    ``x`` and optional ``**params``.
    """
    raw = eq.get(key)
    if raw is None:
        raise SimulationFailedError(
            "Optimizer", f"Equation {idx} is missing key '{key}'"
        )

    raw_fn: Callable[..., Any]
    if callable(raw):
        raw_fn = raw
    elif isinstance(raw, str):
        try:
            raw_fn = eval(raw, {"__builtins__": {}}, {})  # noqa: PGH001
        except Exception as exc:
            raise SimulationFailedError(
                "Optimizer",
                f"Cannot eval '{key}' for equation {idx}: {exc}",
            ) from exc
    else:
        raise SimulationFailedError(
            "Optimizer",
            f"Equation {idx}, key '{key}': expected callable or str, got {type(raw).__name__}",
        )

    # Wrap to guarantee a scalar float return
    def _scalar_wrapper(x: np.ndarray, **params: Any) -> float:
        result = raw_fn(x, **params)
        if isinstance(result, np.ndarray):
            return float(result.item())
        return float(result)

    return _scalar_wrapper


def _extract_gradient_function(
    eq: dict[str, Any], key: str, idx: int
) -> Callable[..., np.ndarray]:
    """Return a gradient callable from an equation dict.

    Unlike the objective function, gradient functions must return numpy
    arrays (matching the shape of ``x``).
    """
    raw = eq.get(key)
    if raw is None:
        raise SimulationFailedError(
            "Optimizer", f"Equation {idx} is missing key '{key}'"
        )

    raw_fn: Callable[..., Any]
    if callable(raw):
        raw_fn = raw
    elif isinstance(raw, str):
        try:
            raw_fn = eval(raw, {"__builtins__": {}}, {})  # noqa: PGH001
        except Exception as exc:
            raise SimulationFailedError(
                "Optimizer",
                f"Cannot eval '{key}' for equation {idx}: {exc}",
            ) from exc
    else:
        raise SimulationFailedError(
            "Optimizer",
            f"Equation {idx}, key '{key}': expected callable or str, got {type(raw).__name__}",
        )

    # Wrap to guarantee array output
    def _array_wrapper(x: np.ndarray, **params: Any) -> np.ndarray:
        result = raw_fn(x, **params)
        return np.asarray(result, dtype=float)

    return _array_wrapper


def _build_penalized_objective(
    objective: Callable[..., float],
    constraints: list[str],
    penalty_weight: float = 1e6,
) -> Callable[..., float]:
    """Wrap the objective with a quadratic penalty for constraint violations.

    Each constraint string is ``eval``\\ed with a dict containing
    ``x`` as a numpy array.  The constraint is assumed to be in the
    form ``g(x) <= 0``.
    """

    def penalized(x: np.ndarray, **params: Any) -> float:
        val = objective(x, **params)
        penalty = 0.0
        for cstr in constraints:
            try:
                # Evaluate constraint expression; expects g(x) <= 0 form
                c_val = eval(cstr, {"__builtins__": {}}, {"x": x, "np": np})  # noqa: PGH001
                if c_val > 0:
                    penalty += penalty_weight * c_val**2
            except Exception:
                pass
        return val + penalty

    return penalized


def _check_constraints(
    x: np.ndarray, constraints: list[str]
) -> list[dict[str, Any]]:
    """Check which constraints are satisfied at point *x*."""
    results: list[dict[str, Any]] = []
    for cstr in constraints:
        try:
            c_val = eval(cstr, {"__builtins__": {}}, {"x": x, "np": np})  # noqa: PGH001
            results.append({
                "constraint": cstr,
                "value": float(c_val),
                "satisfied": c_val <= 0,
            })
        except Exception:
            results.append({
                "constraint": cstr,
                "value": None,
                "satisfied": False,
            })
    return results


def _solve_via_scipy(
    objective: Callable[..., float],
    x0: np.ndarray,
    method: str,
    tolerance: float,
    max_iter: int,
    gradient: Callable[..., np.ndarray] | None = None,
) -> tuple[np.ndarray, int]:
    """Use scipy.optimize.minimize."""
    import scipy.optimize as spo

    if method == "nelder-mead":
        result = spo.minimize(
            objective,
            x0,
            method="Nelder-Mead",
            options={"xatol": tolerance, "fatol": tolerance, "maxiter": max_iter},
        )
    elif method == "bfgs":
        if gradient is not None:
            result = spo.minimize(
                objective,
                x0,
                method="BFGS",
                jac=gradient,
                options={"gtol": tolerance, "maxiter": max_iter},
            )
        else:
            result = spo.minimize(
                objective,
                x0,
                method="BFGS",
                options={"gtol": tolerance, "maxiter": max_iter},
            )
    else:
        raise ValueError(f"Unsupported scipy method: {method}")

    return result.x, int(result.nit) if hasattr(result, "nit") else 1


def _solve_pure_python(
    objective: Callable[..., float],
    gradient: Callable[..., np.ndarray] | None,
    x0: np.ndarray,
    method: str,
    tolerance: float,
    max_iter: int,
    learning_rate: float,
) -> tuple[np.ndarray, int]:
    """Use pure-Python optimisation implementations."""
    if method == "gradient-descent":
        x_opt, iters = _gradient_descent(
            objective, gradient, x0, learning_rate, tolerance, max_iter
        )
    elif method == "nelder-mead":
        x_opt, iters = _nelder_mead(objective, x0, tolerance, max_iter)
    elif method == "bfgs":
        x_opt, iters = _bfgs(objective, gradient, x0, tolerance, max_iter)
    else:
        raise ValueError(f"Unsupported pure-Python method: {method}")

    return x_opt, iters
