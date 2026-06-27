"""Tests for the Monte Carlo solver.

Verifies:
1. Capabilities are declared correctly.
2. Solver can estimate simple statistical quantities.
3. Solver handles invalid input gracefully.
4. Solver returns correct result type (SimulationResult).
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from SciPhi.interfaces.model import MathematicalForm
from SciPhi.interfaces.solver import (
    ComputationalProblem,
    SimulationResult,
    SolverCapabilities,
)
from SciPhi.solvers.stochastic.monte_carlo import MonteCarloSolver


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def solver() -> MonteCarloSolver:
    return MonteCarloSolver()


def _make_mc_problem(
    method: str = "standard-mc",
    n_samples: int = 5000,
    seed: int = 42,
    func: str = "lambda x: x**2",
    param_ranges: dict[str, list[float]] | None = None,
) -> ComputationalProblem:
    if param_ranges is None:
        param_ranges = {"x": [0.0, 1.0]}

    return ComputationalProblem(
        mathematical_form=MathematicalForm.STOCHASTIC,
        equations=[
            {
                "name": "f",
                "function": func,
                "variables": ["y"],
            }
        ],
        initial_conditions={},
        boundary_conditions={},
        parameter_ranges=param_ranges,
        tolerance=1e-6,
        discretization={
            "method": method,
            "n_samples": n_samples,
            "seed": seed,
        },
        constraints=[],
    )


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_capabilities_type(self, solver: MonteCarloSolver) -> None:
        caps = solver.capabilities
        assert isinstance(caps, SolverCapabilities)

    def test_capabilities_forms(self, solver: MonteCarloSolver) -> None:
        caps = solver.capabilities
        assert MathematicalForm.STOCHASTIC in caps.forms
        assert len(caps.forms) == 1

    def test_capabilities_methods(self, solver: MonteCarloSolver) -> None:
        caps = solver.capabilities
        assert "standard-mc" in caps.methods
        assert "importance-sampling" in caps.methods
        assert len(caps.methods) == 2

    def test_info(self, solver: MonteCarloSolver) -> None:
        info = solver.info()
        assert info.id == "MonteCarloSolver"
        assert MathematicalForm.STOCHASTIC in info.forms


# ---------------------------------------------------------------------------
# Solve: estimate E[x^2] for x ~ U(0,1) = 1/3 ≈ 0.333...
# ---------------------------------------------------------------------------


class TestSolve:
    def test_standard_mc(self, solver: MonteCarloSolver) -> None:
        """E[x^2] for uniform(0,1) = integral_0^1 x^2 dx = 1/3."""
        problem = _make_mc_problem(n_samples=20000, seed=123)
        result = solver.solve(problem)

        assert isinstance(result, SimulationResult)
        assert result.converged is True
        assert result.solver_method == "standard-mc"

        # data contains [mean, std, ci_lower, ci_upper]
        stats = result.data.get("y", [])
        assert len(stats) == 4
        mean_val = stats[0]
        # Should be close to 1/3
        assert abs(mean_val - 1.0 / 3.0) < 0.02, (
            f"MC estimate of E[x^2] = {mean_val}, expected ~0.333"
        )

    def test_importance_sampling(self, solver: MonteCarloSolver) -> None:
        """Importance sampling should also give reasonable results."""
        problem = _make_mc_problem(
            method="importance-sampling", n_samples=20000, seed=42
        )
        result = solver.solve(problem)

        assert result.converged is True
        stats = result.data.get("y", [])
        assert len(stats) == 4
        mean_val = stats[0]
        assert abs(mean_val - 1.0 / 3.0) < 0.05, (
            f"IS estimate of E[x^2] = {mean_val}, expected ~0.333"
        )

    def test_result_structure(self, solver: MonteCarloSolver) -> None:
        problem = _make_mc_problem(n_samples=1000)
        result = solver.solve(problem)

        assert isinstance(result.data, dict)
        assert "y" in result.data
        assert isinstance(result.solver_id, str)
        assert isinstance(result.execution_time, float)
        assert isinstance(result.iterations, int)
        assert result.iterations == 1000
        assert isinstance(result.metadata, dict)
        assert "statistics" in result.metadata

    def test_multiple_parameters(self, solver: MonteCarloSolver) -> None:
        """Function of multiple random variables."""
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.STOCHASTIC,
            equations=[
                {
                    "name": "f",
                    "function": "lambda x, y: x + y",
                    "variables": ["z"],
                }
            ],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={"x": [0.0, 1.0], "y": [0.0, 1.0]},
            tolerance=1e-6,
            discretization={
                "method": "standard-mc",
                "n_samples": 10000,
                "seed": 42,
            },
            constraints=[],
        )
        result = solver.solve(problem)
        assert result.converged is True
        stats = result.data.get("z", [])
        assert len(stats) == 4
        # E[x + y] for x,y ~ U(0,1) = 1.0
        assert abs(stats[0] - 1.0) < 0.05

    def test_callable_function(self, solver: MonteCarloSolver) -> None:
        """Pass a real callable instead of a string."""
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.STOCHASTIC,
            equations=[
                {
                    "name": "f",
                    "function": lambda x: x + 1,  # type: ignore[arg-type]
                    "variables": ["y"],
                }
            ],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={"x": [0.0, 1.0]},
            tolerance=1e-6,
            discretization={
                "method": "standard-mc",
                "n_samples": 5000,
                "seed": 42,
            },
            constraints=[],
        )
        result = solver.solve(problem)
        assert result.converged is True
        stats = result.data.get("y", [])
        assert len(stats) == 4
        # E[x + 1] for x ~ U(0,1) = 1.5
        assert abs(stats[0] - 1.5) < 0.03

    # ------------------------------------------------------------------
    # Invalid input handling
    # ------------------------------------------------------------------

    def test_unsupported_method(self, solver: MonteCarloSolver) -> None:
        problem = _make_mc_problem(method="invalid")
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_no_equations(self, solver: MonteCarloSolver) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.STOCHASTIC,
            equations=[],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={"x": [0, 1]},
            tolerance=1e-6,
            discretization={"method": "standard-mc"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_no_parameter_ranges(self, solver: MonteCarloSolver) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.STOCHASTIC,
            equations=[
                {
                    "name": "f",
                    "function": "lambda x: x",
                    "variables": ["y"],
                }
            ],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "standard-mc", "n_samples": 100},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_error_estimate_present(self, solver: MonteCarloSolver) -> None:
        problem = _make_mc_problem(n_samples=1000)
        result = solver.solve(problem)
        # Monte Carlo should provide an error estimate (std)
        assert result.error_estimate is not None
        assert result.error_estimate >= 0
