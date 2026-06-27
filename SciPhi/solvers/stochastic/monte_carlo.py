"""Monte Carlo simulation solver.

Performs statistical sampling over parameter ranges to estimate
expected values, variances, and confidence intervals for quantities
defined by the computational problem.  The solver has no knowledge
of the underlying stochastic process -- it simply evaluates a
callable over sampled points.
"""

from __future__ import annotations

import math
import random
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
# Sampling strategies
# ---------------------------------------------------------------------------


def _standard_mc(
    func: Callable[..., float],
    param_ranges: dict[str, tuple[float, float]],
    n_samples: int,
    seed: int | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Standard Monte Carlo sampling with uniform distributions.

    Args:
        func: Function ``f(**params) -> float`` to evaluate.
        param_ranges: Mapping of parameter name to ``(min, max)``.
        n_samples: Number of samples to draw.
        seed: Random seed for reproducibility.

    Returns:
        Tuple ``(samples, param_arrays)`` where *samples* is a 1-D array
        of function evaluations and *param_arrays* maps each parameter name
        to its sampled values.
    """
    if seed is not None:
        np.random.seed(seed)

    param_names = list(param_ranges.keys())
    param_arrays: dict[str, np.ndarray] = {}

    # Generate uniform samples for each parameter
    for name in param_names:
        lo, hi = param_ranges[name]
        param_arrays[name] = np.random.uniform(lo, hi, size=n_samples)

    # Evaluate the function
    samples = np.array([
        func(**{name: param_arrays[name][i] for name in param_names})
        for i in range(n_samples)
    ])

    return samples, param_arrays


def _importance_sampling(
    func: Callable[..., float],
    param_ranges: dict[str, tuple[float, float]],
    n_samples: int,
    importance_params: dict[str, dict[str, float]] | None = None,
    seed: int | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray], np.ndarray]:
    """Monte Carlo with importance sampling.

    Uses a Gaussian importance distribution centered within each parameter
    range.  Each sample is weighted by the ratio of the target uniform
    density to the proposal density.

    Args:
        func: Function ``f(**params) -> float`` to evaluate.
        param_ranges: Mapping of parameter name to ``(min, max)``.
        n_samples: Number of samples to draw.
        importance_params: Per-parameter importance distribution config
            (e.g. ``{"mu": mean, "sigma": std}``).  If ``None``, defaults
            to the midpoint of the range with sigma = 20% of the width.
        seed: Random seed for reproducibility.

    Returns:
        Tuple ``(raw_samples, param_arrays, weights)`` where *raw_samples*
        are the raw function evaluations, and *weights* are the importance
        sampling weights (not normalised).
    """
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    param_names = list(param_ranges.keys())
    param_arrays: dict[str, np.ndarray] = {}
    weights = np.ones(n_samples)

    for name in param_names:
        lo, hi = param_ranges[name]
        width = hi - lo

        if importance_params and name in importance_params:
            mu = importance_params[name].get("mu", (lo + hi) / 2.0)
            sigma = importance_params[name].get("sigma", width * 0.2)
        else:
            mu = (lo + hi) / 2.0
            sigma = width * 0.2

        # Sample from Gaussian, clip to range
        raw = np.random.normal(loc=mu, scale=sigma, size=n_samples)
        raw = np.clip(raw, lo, hi)
        param_arrays[name] = raw

        # Importance weight: p_target / p_proposal
        # Target: uniform over [lo, hi]
        p_target = 1.0 / width
        # Proposal: truncated Gaussian (approximate, ignoring normalization)
        p_proposal = (
            (1.0 / (sigma * math.sqrt(2.0 * math.pi)))
            * np.exp(-0.5 * ((raw - mu) / sigma) ** 2)
        )
        weights *= p_target / np.maximum(p_proposal, 1e-30)

    # Evaluate function
    raw_samples = np.array([
        func(**{name: param_arrays[name][i] for name in param_names})
        for i in range(n_samples)
    ])

    return raw_samples, param_arrays, weights


# ---------------------------------------------------------------------------
# Solver implementation
# ---------------------------------------------------------------------------


class MonteCarloSolver(Solver):
    """Monte Carlo solver for stochastic computational problems.

    Evaluates a function over randomly sampled parameter values and
    computes statistical summaries (mean, standard deviation, confidence
    intervals).

    Supports two sampling methods:

    * ``standard-mc`` -- uniform random sampling.
    * ``importance-sampling`` -- Gaussian proposal distribution with
      importance weighting.
    """

    def __init__(self) -> None:
        self._capabilities = SolverCapabilities(
            name="Monte Carlo Solver",
            forms=[MathematicalForm.STOCHASTIC],
            methods=["standard-mc", "importance-sampling"],
            order=[0],
            supports_parallel=False,
            handles_stiff=None,
            error_estimation=True,
        )

    # ------------------------------------------------------------------
    # Solver ABC
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> SolverCapabilities:
        return self._capabilities

    def solve(self, problem: ComputationalProblem) -> SimulationResult:
        """Run a Monte Carlo simulation.

        Expects each equation dict in ``problem.equations`` to contain:

        * ``"function"`` -- a callable ``f(**params) -> float`` or a
          string that can be ``eval``\\ed to obtain one.
        * ``"variables"`` -- list of output variable names.

        Parameter ranges are read from ``problem.parameter_ranges``
        (mapping of name to ``[min, max]``).

        Configuration may be provided via ``problem.discretization``:

        * ``n_samples`` (int, default 10 000)
        * ``seed`` (int, optional)
        * ``confidence_level`` (float, default 0.95)

        Args:
            problem: The fully specified computational problem.

        Returns:
            A :class:`SimulationResult` containing statistical summaries.

        Raises:
            SimulationFailedError: If the simulation fails or the
                problem definition is invalid.
        """
        # --- Extract configuration ------------------------------------------
        n_samples = 10000
        seed: int | None = None
        confidence_level = 0.95

        if problem.discretization:
            n_samples = int(problem.discretization.get("n_samples", n_samples))
            seed = problem.discretization.get("seed")
            confidence_level = float(
                problem.discretization.get("confidence_level", confidence_level)
            )

        method = (
            problem.discretization.get("method", "standard-mc")
            if problem.discretization
            else "standard-mc"
        )
        if method not in self._capabilities.methods:
            raise SimulationFailedError(
                type(self).__name__,
                f"Unsupported method '{method}'. Choose from {self._capabilities.methods}",
            )

        # --- Extract functions & parameter ranges ---------------------------
        if not problem.equations:
            raise SimulationFailedError(
                type(self).__name__, "No equations provided in problem"
            )

        param_ranges: dict[str, tuple[float, float]] = {}
        for name, val in problem.parameter_ranges.items():
            if hasattr(val, "__iter__") and not isinstance(val, str):
                vals = list(val)
                if len(vals) >= 2:
                    param_ranges[name] = (float(vals[0]), float(vals[1]))
                else:
                    param_ranges[name] = (float(vals[0]), float(vals[0]))
            else:
                param_ranges[name] = (float(val), float(val))

        if not param_ranges:
            raise SimulationFailedError(
                type(self).__name__,
                "No parameter ranges defined. Monte Carlo requires at least "
                "one parameter with a [min, max] range.",
            )

        t0 = time.time()
        data: dict[str, list[float]] = {}
        variable_names: list[str] = []
        all_stats: dict[str, dict[str, float]] = {}

        try:
            for idx, eq in enumerate(problem.equations):
                func = _extract_mc_function(eq, "function", idx)
                vars_list = eq.get("variables", [f"y{idx}"])
                variable_names.extend(vars_list)

                if method == "standard-mc":
                    samples, _ = _standard_mc(func, param_ranges, n_samples, seed)
                    # For standard MC, statistics are simple
                    mean_val = float(np.mean(samples))
                    std_val = float(np.std(samples, ddof=1)) if len(samples) > 1 else 0.0
                elif method == "importance-sampling":
                    imp_params = (
                        problem.discretization.get("importance_params")
                        if problem.discretization
                        else None
                    )
                    raw_samples, _, weights = _importance_sampling(
                        func, param_ranges, n_samples, imp_params, seed
                    )
                    # Weighted statistics for importance sampling
                    w_sum = np.sum(weights)
                    if w_sum > 0:
                        mean_val = float(np.sum(raw_samples * weights) / w_sum)
                        # Weighted standard deviation (unbiased)
                        variance = float(
                            np.sum(weights * (raw_samples - mean_val) ** 2) / w_sum
                        ) if len(raw_samples) > 1 else 0.0
                        std_val = math.sqrt(variance) if variance >= 0 else 0.0
                    else:
                        mean_val = 0.0
                        std_val = 0.0
                    samples = raw_samples  # keep raw samples for ci computation
                n = len(samples)
                z = _z_score(confidence_level)
                ci_half = z * std_val / math.sqrt(n) if n > 1 else 0.0

                var_name = vars_list[0]
                data[var_name] = samples.tolist()
                all_stats[var_name] = {
                    "mean": mean_val,
                    "std": std_val,
                    "ci_lower": mean_val - ci_half,
                    "ci_upper": mean_val + ci_half,
                    "ci_level": confidence_level,
                    "n_samples": n,
                }

        except Exception as exc:
            raise SimulationFailedError(
                type(self).__name__, f"Monte Carlo simulation failed: {exc}"
            ) from exc

        elapsed = time.time() - t0

        # For the simulation result data, store the summary statistics
        # (not all individual samples - that could be massive).
        result_data: dict[str, list[float]] = {}
        for var_name, stats in all_stats.items():
            result_data[var_name] = [
                stats["mean"],
                stats["std"],
                stats["ci_lower"],
                stats["ci_upper"],
            ]

        return SimulationResult(
            solver_id=type(self).__name__,
            solver_method=method,
            converged=True,
            iterations=n_samples,
            execution_time=elapsed,
            data=result_data,
            metadata={
                "n_samples": n_samples,
                "method": method,
                "seed": seed,
                "statistics": all_stats,
                "param_ranges": {k: list(v) for k, v in param_ranges.items()},
            },
            error_estimate=float(np.mean([s["std"] for s in all_stats.values()]))
            if all_stats
            else None,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_mc_function(
    eq: dict[str, Any], key: str, idx: int
) -> Callable[..., float]:
    """Return a callable from an equation dict for Monte Carlo evaluation.

    Unlike the ODE solver, Monte Carlo functions receive keyword arguments
    only (parameter name -> sampled value).
    """
    raw = eq.get(key)
    if raw is None:
        raise SimulationFailedError(
            "MonteCarloSolver", f"Equation {idx} is missing key '{key}'"
        )
    if callable(raw):
        return raw
    if isinstance(raw, str):
        try:
            # Allow **kwargs style functions
            return eval(raw, {"__builtins__": {}}, {})  # noqa: PGH001
        except Exception as exc:
            raise SimulationFailedError(
                "MonteCarloSolver",
                f"Cannot eval function string for equation {idx}: {exc}",
            ) from exc
    raise SimulationFailedError(
        "MonteCarloSolver",
        f"Equation {idx}, key '{key}': expected callable or str, got {type(raw).__name__}",
    )


def _z_score(confidence_level: float) -> float:
    """Approximate z-score for a given confidence level (two-tailed).

    Uses a simple approximation for the normal quantile function.
    """
    # Standard approximations for common confidence levels
    if confidence_level >= 0.995:
        return 2.807
    if confidence_level >= 0.99:
        return 2.576
    if confidence_level >= 0.975:
        return 2.241
    if confidence_level >= 0.95:
        return 1.960
    if confidence_level >= 0.90:
        return 1.645
    if confidence_level >= 0.80:
        return 1.282
    # Fallback: rough approximation
    alpha = 1.0 - confidence_level
    return math.sqrt(2.0) * math.erfinv(1.0 - alpha)
