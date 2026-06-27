"""Tests for the optimisation solver.

Verifies:
1. Capabilities are declared correctly.
2. Solver can optimise a simple known problem (minimise (x-3)^2).
3. Solver handles invalid input gracefully.
4. Solver returns correct result type (SimulationResult).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from SciPhi.interfaces.model import MathematicalForm
from SciPhi.interfaces.solver import (
    ComputationalProblem,
    SimulationResult,
    SolverCapabilities,
)
from SciPhi.solvers.optimization.optimizer import Optimizer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def solver() -> Optimizer:
    return Optimizer()


def _make_opt_problem(
    method: str = "bfgs",
    function: str = "lambda x: (x - 3)**2 + 1",
    gradient: str | None = "lambda x: 2 * (x - 3)",
    x0: float = 0.0,
    tolerance: float = 1e-6,
    constraints: list[str] | None = None,
) -> ComputationalProblem:
    """Create a problem for minimising (x-3)^2 + 1 → minimum at x=3."""
    eq: dict[str, Any] = {
        "name": "objective",
        "function": function,
        "variables": ["x"],
    }
    if gradient is not None:
        eq["gradient"] = gradient

    return ComputationalProblem(
        mathematical_form=MathematicalForm.OPTIMIZATION,
        equations=[eq],
        initial_conditions={"x": x0},
        boundary_conditions={},
        parameter_ranges={},
        tolerance=tolerance,
        discretization={"method": method},
        constraints=constraints or [],
    )


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_capabilities_type(self, solver: Optimizer) -> None:
        caps = solver.capabilities
        assert isinstance(caps, SolverCapabilities)

    def test_capabilities_forms(self, solver: Optimizer) -> None:
        caps = solver.capabilities
        assert MathematicalForm.OPTIMIZATION in caps.forms
        assert len(caps.forms) == 1

    def test_capabilities_methods(self, solver: Optimizer) -> None:
        caps = solver.capabilities
        assert "gradient-descent" in caps.methods
        assert "nelder-mead" in caps.methods
        assert "bfgs" in caps.methods
        assert len(caps.methods) == 3

    def test_info(self, solver: Optimizer) -> None:
        info = solver.info()
        assert info.id == "Optimizer"
        assert MathematicalForm.OPTIMIZATION in info.forms


# ---------------------------------------------------------------------------
# Solve: minimise (x-3)^2 + 1 → minimum at x=3, value=1
# ---------------------------------------------------------------------------


class TestSolve:
    @pytest.mark.parametrize("method", ["gradient-descent", "nelder-mead", "bfgs"])
    def test_minimize_quadratic(self, solver: Optimizer, method: str) -> None:
        problem = _make_opt_problem(method=method, x0=0.0)
        result = solver.solve(problem)

        assert isinstance(result, SimulationResult)
        assert result.solver_method == method

        optimal_x = result.data.get("x", [None])[0]
        assert optimal_x is not None
        assert abs(optimal_x - 3.0) < 0.1, (
            f"method={method}: optimal x={optimal_x}, expected 3.0"
        )

    def test_with_gradient(self, solver: Optimizer) -> None:
        """BFGS with analytical gradient should converge quickly."""
        problem = _make_opt_problem(method="bfgs", tolerance=1e-8)
        result = solver.solve(problem)
        x_opt = result.data["x"][0]
        assert abs(x_opt - 3.0) < 0.01

    def test_with_numerical_gradient(self, solver: Optimizer) -> None:
        """Gradient descent without analytical gradient should still work."""
        problem = _make_opt_problem(method="gradient-descent", gradient=None)
        result = solver.solve(problem)
        x_opt = result.data["x"][0]
        assert abs(x_opt - 3.0) < 0.5  # GD may be slower to converge

    def test_result_structure(self, solver: Optimizer) -> None:
        problem = _make_opt_problem()
        result = solver.solve(problem)

        assert isinstance(result.data, dict)
        assert "x" in result.data
        assert isinstance(result.solver_id, str)
        assert isinstance(result.execution_time, float)
        assert isinstance(result.iterations, int)
        assert isinstance(result.metadata, dict)
        assert "final_objective" in result.metadata

    def test_2d_optimization(self, solver: Optimizer) -> None:
        """Minimise f(x, y) = (x-1)^2 + (y+2)^2 using BFGS (more robust)."""
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.OPTIMIZATION,
            equations=[
                {
                    "name": "objective",
                    "function": "lambda x: (x[0] - 1)**2 + (x[1] + 2)**2",
                    "variables": ["x", "y"],
                }
            ],
            initial_conditions={"x": 0.0, "y": 0.0},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "bfgs"},
            constraints=[],
        )
        result = solver.solve(problem)
        assert result.converged is True
        x_opt = result.data.get("x", [None])[0]
        y_opt = result.data.get("y", [None])[0]
        assert x_opt is not None and y_opt is not None
        assert abs(x_opt - 1.0) < 0.1
        assert abs(y_opt - (-2.0)) < 0.1

    def test_with_constraints(self, solver: Optimizer) -> None:
        """Minimise (x-3)^2 + 1 subject to x >= 2 (i.e., 2 - x <= 0)."""
        problem = _make_opt_problem(
            method="nelder-mead",
            x0=4.0,
            constraints=["2.0 - x[0]"],
        )
        result = solver.solve(problem)
        x_opt = result.data.get("x", [None])[0]
        assert x_opt is not None
        # The unconstrained optimum is x=3, which satisfies x >= 2, so same answer
        assert abs(x_opt - 3.0) < 0.2

    # ------------------------------------------------------------------
    # Invalid input handling
    # ------------------------------------------------------------------

    def test_unsupported_method(self, solver: Optimizer) -> None:
        problem = _make_opt_problem(method="invalid")
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_no_equations(self, solver: Optimizer) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.OPTIMIZATION,
            equations=[],
            initial_conditions={"x": 0.0},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "bfgs"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_missing_function(self, solver: Optimizer) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.OPTIMIZATION,
            equations=[{"name": "bad", "variables": ["x"]}],
            initial_conditions={"x": 0.0},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "bfgs"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)
