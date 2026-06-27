"""ODE initial-value problem solver.

Provides numerical integration for systems of ordinary differential
equations using explicit Runge-Kutta methods.  The solver declares
no domain knowledge -- it operates on callable right-hand side
functions supplied inside the :class:`ComputationalProblem` equation
dicts.
"""

from __future__ import annotations

import math
import time
import types
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

_HAS_SCIPY = False
try:
    import scipy.integrate  # noqa: F401

    _HAS_SCIPY = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Pure-Python integrators (used when scipy is unavailable or for small
# problems where the overhead of scipy is undesirable).
# ---------------------------------------------------------------------------


def _euler_step(
    f: Callable[..., float | np.ndarray],
    t: float,
    y: np.ndarray,
    h: float,
    params: dict[str, float],
) -> np.ndarray:
    """Forward Euler step.

    Args:
        f: Right-hand side function ``f(t, y, **params)``.
        t: Current time.
        y: Current state vector.
        h: Step size.
        params: Additional parameters passed to *f*.

    Returns:
        State vector at ``t + h``.
    """
    return y + h * np.asarray(f(t, y, **params))


def _rk4_step(
    f: Callable[..., float | np.ndarray],
    t: float,
    y: np.ndarray,
    h: float,
    params: dict[str, float],
) -> np.ndarray:
    """Classical fourth-order Runge-Kutta step (RK4).

    Args:
        f: Right-hand side function ``f(t, y, **params)``.
        t: Current time.
        y: Current state vector.
        h: Step size.
        params: Additional parameters passed to *f*.

    Returns:
        State vector at ``t + h``.
    """
    y = np.asarray(y)
    k1 = np.asarray(f(t, y, **params))
    k2 = np.asarray(f(t + 0.5 * h, y + 0.5 * h * k1, **params))
    k3 = np.asarray(f(t + 0.5 * h, y + 0.5 * h * k2, **params))
    k4 = np.asarray(f(t + h, y + h * k3, **params))
    return y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def _dopri5_step(
    f: Callable[..., float | np.ndarray],
    t: float,
    y: np.ndarray,
    h: float,
    params: dict[str, float],
) -> tuple[np.ndarray, np.ndarray, float]:
    """Single step of the Dormand-Prince 5(4) method.

    Uses the DOPRI5 tableau with embedded fourth-order estimate for
    error control.

    Args:
        f: Right-hand side function ``f(t, y, **params)``.
        t: Current time.
        y: Current state vector.
        h: Step size.
        params: Additional parameters passed to *f*.

    Returns:
        Tuple ``(y_new, y_err, h_new)`` where *y_new* is the fifth-order
        solution, *y_err* is the error estimate, and *h_new* is the
        suggested next step size.
    """
    y = np.asarray(y, dtype=float)

    # DOPRI5 coefficients (Dormand & Prince 1980)
    c2 = 1.0 / 5.0
    c3 = 3.0 / 10.0
    c4 = 4.0 / 5.0
    c5 = 8.0 / 9.0
    c6 = 1.0

    a21 = 1.0 / 5.0
    a31 = 3.0 / 40.0
    a32 = 9.0 / 40.0
    a41 = 44.0 / 45.0
    a42 = -56.0 / 15.0
    a43 = 32.0 / 9.0
    a51 = 19372.0 / 6561.0
    a52 = -25360.0 / 2187.0
    a53 = 64448.0 / 6561.0
    a54 = -212.0 / 729.0
    a61 = 9017.0 / 3168.0
    a62 = -355.0 / 33.0
    a63 = 46732.0 / 5247.0
    a64 = 49.0 / 176.0
    a65 = -5103.0 / 18656.0

    # Fourth-order weights (for error estimate)
    e1 = 71.0 / 57600.0
    e2 = -71.0 / 16695.0
    e3 = 71.0 / 1920.0
    e4 = -17253.0 / 339200.0
    e5 = 22.0 / 525.0
    e6 = -1.0 / 40.0

    k1 = np.asarray(f(t, y, **params))
    k2 = np.asarray(f(t + c2 * h, y + h * (a21 * k1), **params))
    k3 = np.asarray(f(t + c3 * h, y + h * (a31 * k1 + a32 * k2), **params))
    k4 = np.asarray(f(t + c4 * h, y + h * (a41 * k1 + a42 * k2 + a43 * k3), **params))
    k5 = np.asarray(
        f(t + c5 * h, y + h * (a51 * k1 + a52 * k2 + a53 * k3 + a54 * k4), **params)
    )
    k6 = np.asarray(
        f(
            t + c6 * h,
            y + h * (a61 * k1 + a62 * k2 + a63 * k3 + a64 * k4 + a65 * k5),
            **params,
        )
    )

    # Fifth-order solution
    y_new = y + h * (
        35.0 / 384.0 * k1
        + 0.0 * k2
        + 500.0 / 1113.0 * k3
        + 125.0 / 192.0 * k4
        + -2187.0 / 6784.0 * k5
        + 11.0 / 84.0 * k6
    )

    # Error estimate (difference between 4th and 5th order)
    y_err = h * (e1 * k1 + e2 * k2 + e3 * k3 + e4 * k4 + e5 * k5 + e6 * k6)

    # Error norm
    err_norm = np.linalg.norm(y_err) / max(1.0e-10, np.linalg.norm(y_new))
    if err_norm == 0.0:
        h_new = 2.0 * h
    else:
        h_new = h * min(2.0, max(0.1, 0.9 * (1.0 / err_norm) ** 0.2))

    return y_new, y_err, h_new


# ---------------------------------------------------------------------------
# Solver implementation
# ---------------------------------------------------------------------------


class ODESolver(Solver):
    """Solver for systems of ordinary differential equations (IVP).

    Supports three integration methods:

    * ``euler``  -- Forward Euler (first-order, explicit).
    * ``rk4``    -- Classical Runge-Kutta (fourth-order, explicit).
    * ``dopri5`` -- Dormand-Prince 5(4) with adaptive step-size control
      (uses ``scipy.integrate.solve_ivp`` when available, otherwise a
      pure-Python implementation).
    """

    def __init__(self) -> None:
        self._capabilities = SolverCapabilities(
            name="ODE Solver (IVP)",
            forms=[MathematicalForm.ODE_INITIAL_VALUE],
            methods=["rk4", "euler", "dopri5"],
            order=[1, 4, 5],
            supports_parallel=False,
            handles_stiff=False,
            error_estimation=True,
        )

    # ------------------------------------------------------------------
    # Solver ABC
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> SolverCapabilities:
        return self._capabilities

    def solve(self, problem: ComputationalProblem) -> SimulationResult:
        """Integrate the ODE system defined by *problem*.

        Expects each equation dict in ``problem.equations`` to contain:

        * ``"function"`` -- a callable ``f(t, y, **params)`` or a string
          that can be ``eval``\\ed to obtain one.
        * ``"variables"`` -- list of variable names (length must match the
          output dimension of *function*).

        The independent variable range is read from
        ``problem.parameter_ranges`` using the key ``"t"`` or from
        ``problem.discretization`` (keys ``"t_start"``, ``"t_end"``).

        Args:
            problem: The fully specified computational problem.

        Returns:
            A :class:`SimulationResult` containing the time-series data.

        Raises:
            SimulationFailedError: If the integration fails or the problem
                definition is invalid.
        """
        method = problem.discretization.get("method", "rk4") if problem.discretization else "rk4"  # type: ignore[union-attr]
        if method not in self._capabilities.methods:
            raise SimulationFailedError(
                type(self).__name__,
                f"Unsupported method '{method}'. Choose from {self._capabilities.methods}",
            )

        # --- Extract RHS functions ------------------------------------------
        rhs_functions: list[Callable[..., float | np.ndarray]] = []
        variable_names: list[str] = []
        all_params: dict[str, float] = {}

        for eq_idx, eq in enumerate(problem.equations):
            fn = _extract_callable(eq, "function", eq_idx)
            rhs_functions.append(fn)
            vars_list = eq.get("variables", [])
            variable_names.extend(vars_list)
            params = eq.get("parameters", {})
            all_params.update(params)

        # --- Determine time span and step size -------------------------------
        t_span = _extract_t_span(problem)
        t_start, t_end = t_span

        step_size = 0.01  # default
        if problem.discretization:
            step_size = problem.discretization.get("step_size", 0.01)

        # --- Initial conditions ---------------------------------------------
        y0_list: list[float] = []
        for var_name in variable_names:
            if var_name in problem.initial_conditions:
                y0_list.append(float(problem.initial_conditions[var_name]))
            else:
                # Try matching by equation variable order
                pass

        if not y0_list and variable_names:
            raise SimulationFailedError(
                type(self).__name__,
                f"No initial conditions provided for variables {variable_names}. "
                f"Got keys: {list(problem.initial_conditions.keys())}",
            )

        y0 = np.array(y0_list, dtype=float)

        # --- Combine RHS into a single function for vector systems ----------
        if len(rhs_functions) == 1:
            rhs = rhs_functions[0]
        else:

            def rhs(t: float, y: np.ndarray, **params: Any) -> np.ndarray:
                return np.array([f(t, y, **params) for f in rhs_functions])

        # --- Solve ----------------------------------------------------------
        t0 = time.time()
        result_data: dict[str, list[float]] = {}

        try:
            if method == "dopri5" and _HAS_SCIPY:
                result_data = _solve_via_scipy(rhs, t_span, y0, all_params, problem.tolerance)
            elif method in ("rk4", "euler", "dopri5"):
                result_data = _solve_pure_python(
                    rhs, method, t_span, y0, all_params, step_size, problem.tolerance
                )
            else:
                raise SimulationFailedError(
                    type(self).__name__, f"Unknown method '{method}'"
                )
        except Exception as exc:
            raise SimulationFailedError(
                type(self).__name__, f"Integration failed: {exc}"
            ) from exc

        elapsed = time.time() - t0

        # Build variable -> time-series mapping.
        # Internal solver functions store results as "y0", "y1", ...
        # Map these back to the declared variable names.
        data: dict[str, list[float]] = {}
        for idx, var_name in enumerate(variable_names):
            key = f"y{idx}"
            series = result_data.get(key, [])
            data[var_name] = list(np.asarray(series))

        # Also store the independent variable
        if "t" in result_data:
            data["t"] = list(np.asarray(result_data["t"]))

        return SimulationResult(
            solver_id=type(self).__name__,
            solver_method=method,
            converged=True,
            iterations=len(data.get(variable_names[0], [])),
            execution_time=elapsed,
            data=data,
            metadata={
                "t_span": list(t_span),
                "step_size": step_size,
                "n_variables": len(variable_names),
                "scipy_used": _HAS_SCIPY and method == "dopri5",
            },
            error_estimate=None,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_callable(
    eq: dict[str, Any], key: str, idx: int
) -> Callable[..., float | np.ndarray]:
    """Return a callable from an equation dict.

    If the value under *key* is already a callable it is returned as-is.
    If it is a string it is ``eval``\\ed to produce a lambda.

    Raises:
        SimulationFailedError: If no callable can be produced.
    """
    raw = eq.get(key)
    if raw is None:
        raise SimulationFailedError(
            "ODESolver", f"Equation {idx} is missing key '{key}'"
        )
    if callable(raw):
        return raw
    if isinstance(raw, str):
        try:
            return eval(raw, {"__builtins__": {}}, {})  # noqa: PGH001
        except Exception as exc:
            raise SimulationFailedError(
                "ODESolver",
                f"Cannot eval function string for equation {idx}: {exc}",
            ) from exc
    raise SimulationFailedError(
        "ODESolver",
        f"Equation {idx}, key '{key}': expected callable or str, got {type(raw).__name__}",
    )


def _extract_t_span(problem: ComputationalProblem) -> tuple[float, float]:
    """Extract the time integration interval from a problem definition.

    Checks, in order:
    1. ``problem.discretization`` keys ``"t_start"`` / ``"t_end"``
    2. ``problem.parameter_ranges["t"]``
    3. Default ``(0.0, 1.0)``
    """
    if problem.discretization:
        t_start = problem.discretization.get("t_start")
        t_end = problem.discretization.get("t_end")
        if t_start is not None and t_end is not None:
            return (float(t_start), float(t_end))

    t_range = problem.parameter_ranges.get("t")
    if t_range is not None:
        try:
            lo, hi = t_range[0], t_range[1]
            return (float(lo), float(hi))
        except (IndexError, TypeError):
            pass

    return (0.0, 1.0)


def _solve_via_scipy(
    rhs: Callable[..., float | np.ndarray],
    t_span: tuple[float, float],
    y0: np.ndarray,
    params: dict[str, float],
    tolerance: float,
) -> dict[str, list[float]]:
    """Integrate using ``scipy.integrate.solve_ivp``."""
    import scipy.integrate  # noqa: W0406

    def rhs_wrapper(t: float, y: np.ndarray) -> np.ndarray:
        return np.asarray(rhs(t, y, **params))

    sol = scipy.integrate.solve_ivp(
        rhs_wrapper,
        t_span,
        y0,
        method="DOP853" if _HAS_SCIPY else "RK45",
        rtol=tolerance,
        atol=tolerance * 1e-3,
        dense_output=True,
    )

    result: dict[str, list[float]] = {}
    if sol.t is not None:
        result["t"] = list(sol.t)
    for i in range(len(y0)):
        result[f"y{i}"] = list(sol.y[i]) if sol.y is not None else []
    return result


def _solve_pure_python(
    rhs: Callable[..., float | np.ndarray],
    method: str,
    t_span: tuple[float, float],
    y0: np.ndarray,
    params: dict[str, float],
    step_size: float,
    tolerance: float,
) -> dict[str, list[float]]:
    """Integrate using a pure-Python implementation."""
    t0, t_end = t_span
    n_steps = max(1, math.ceil((t_end - t0) / step_size))
    h = (t_end - t0) / n_steps

    step_fn: Callable[..., np.ndarray]
    if method == "euler":
        step_fn = _euler_step
    elif method == "rk4":
        step_fn = _rk4_step
    elif method == "dopri5":
        step_fn = _dopri5_step  # type: ignore[assignment]
    else:
        raise ValueError(f"Unsupported pure-Python method: {method}")

    t = t0
    y = y0.copy()
    t_series: list[float] = [t]
    y_series: list[list[float]] = [y.tolist()]

    if method == "dopri5":
        # Adaptive stepping: allow up to 10x the fixed-step count for
        # rejected steps.
        max_iter = max(100, n_steps * 10)
        for _ in range(max_iter):
            y_new, y_err, h_new = _dopri5_step(rhs, t, y, h, params)
            err_norm = np.linalg.norm(y_err)
            if err_norm > tolerance and h > 1e-14:
                h *= 0.5
                continue
            y = y_new
            t += h
            t = min(t, t_end)
            t_series.append(t)
            y_series.append(y.tolist())
            if abs(t - t_end) < 1e-14:
                break
            h = min(h_new, t_end - t)
            if h < 1e-14:
                break
    else:
        # Fixed-step methods (euler, rk4)
        for _ in range(n_steps):
            y = step_fn(rhs, t, y, h, params)
            t += h
            t = min(t, t_end)
            t_series.append(t)
            y_series.append(y.tolist())
            if abs(t - t_end) < 1e-14:
                break
            if t + h > t_end:
                h = t_end - t

    result: dict[str, list[float]] = {"t": t_series}
    for i in range(len(y0)):
        result[f"y{i}"] = [y_vals[i] for y_vals in y_series]
    return result
