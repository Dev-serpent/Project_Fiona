"""Tests for the ODE solver.

Verifies:
1. Capabilities are declared correctly.
2. Solver can solve a simple known problem (dx/dt = -x).
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
from SciPhi.solvers.deterministic.ode_solver import ODESolver


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def solver() -> ODESolver:
    return ODESolver()


def _make_ode_problem(
    method: str = "rk4",
    step_size: float = 0.01,
    t_start: float = 0.0,
    t_end: float = 1.0,
    initial_x: float = 1.0,
    tolerance: float = 1e-6,
) -> ComputationalProblem:
    """Create a problem for dx/dt = -x, solution x(t) = x0 * exp(-t)."""
    return ComputationalProblem(
        mathematical_form=MathematicalForm.ODE_INITIAL_VALUE,
        equations=[
            {
                "name": "dx/dt",
                "function": "lambda t, y, **params: -y",
                "variables": ["x"],
                "parameters": {},
            }
        ],
        initial_conditions={"x": initial_x},
        boundary_conditions={},
        parameter_ranges={"t": [t_start, t_end]},
        tolerance=tolerance,
        discretization={
            "method": method,
            "step_size": step_size,
            "t_start": t_start,
            "t_end": t_end,
        },
        constraints=[],
    )


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_capabilities_type(self, solver: ODESolver) -> None:
        caps = solver.capabilities
        assert isinstance(caps, SolverCapabilities)

    def test_capabilities_forms(self, solver: ODESolver) -> None:
        caps = solver.capabilities
        assert MathematicalForm.ODE_INITIAL_VALUE in caps.forms
        assert len(caps.forms) == 1

    def test_capabilities_methods(self, solver: ODESolver) -> None:
        caps = solver.capabilities
        assert "rk4" in caps.methods
        assert "euler" in caps.methods
        assert "dopri5" in caps.methods
        assert len(caps.methods) == 3

    def test_capabilities_name(self, solver: ODESolver) -> None:
        assert solver.capabilities.name == "ODE Solver (IVP)"

    def test_info(self, solver: ODESolver) -> None:
        info = solver.info()
        assert info.id == "ODESolver"
        assert info.name == "ODE Solver (IVP)"
        assert MathematicalForm.ODE_INITIAL_VALUE in info.forms


# ---------------------------------------------------------------------------
# Basic solve: dx/dt = -x, x(0) = 1 → x(t) = exp(-t)
# ---------------------------------------------------------------------------


class TestSolve:
    @pytest.mark.parametrize("method", ["rk4", "euler", "dopri5"])
    def test_simple_decay(self, solver: ODESolver, method: str) -> None:
        problem = _make_ode_problem(method=method, t_end=0.5, step_size=0.001)
        result = solver.solve(problem)

        assert isinstance(result, SimulationResult)
        assert result.converged is True
        assert result.solver_id == "ODESolver"
        assert result.solver_method == method

        # Check that x is close to exp(-t) at the final time
        x_series = result.data.get("x", [])
        t_series = result.data.get("t", [])
        assert len(x_series) > 1
        assert len(t_series) > 1

        # Final value should be close to exp(-0.5)
        x_final = x_series[-1]
        expected = math.exp(-0.5)
        assert abs(x_final - expected) < 0.02, (
            f"method={method}: x_final={x_final}, expected={expected}"
        )

    def test_euler_works(self, solver: ODESolver) -> None:
        """Euler is less accurate but should still be qualitatively correct."""
        problem = _make_ode_problem(method="euler", step_size=0.0005, t_end=0.5)
        result = solver.solve(problem)

        x_final = result.data["x"][-1]
        expected = math.exp(-0.5)
        assert abs(x_final - expected) < 0.02

    def test_result_structure(self, solver: ODESolver) -> None:
        problem = _make_ode_problem()
        result = solver.solve(problem)

        assert isinstance(result.data, dict)
        assert "x" in result.data
        assert "t" in result.data
        assert isinstance(result.execution_time, float)
        assert result.execution_time >= 0
        assert isinstance(result.iterations, int)
        assert result.iterations > 0
        assert isinstance(result.metadata, dict)

    # ------------------------------------------------------------------
    # Invalid input handling
    # ------------------------------------------------------------------

    def test_unsupported_method(self, solver: ODESolver) -> None:
        problem = _make_ode_problem(method="invalid-method")
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_missing_function_key(self, solver: ODESolver) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.ODE_INITIAL_VALUE,
            equations=[{"name": "bad", "variables": ["x"]}],
            initial_conditions={"x": 1.0},
            boundary_conditions={},
            parameter_ranges={"t": [0, 1]},
            tolerance=1e-6,
            discretization={"method": "rk4"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_missing_initial_conditions(self, solver: ODESolver) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.ODE_INITIAL_VALUE,
            equations=[
                {
                    "name": "dx/dt",
                    "function": "lambda t, y, **params: -y",
                    "variables": ["x"],
                    "parameters": {},
                }
            ],
            initial_conditions={},  # empty
            boundary_conditions={},
            parameter_ranges={"t": [0, 1]},
            tolerance=1e-6,
            discretization={"method": "rk4"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_callable_function(self, solver: ODESolver) -> None:
        """Ensure passing a real callable instead of a string works."""
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.ODE_INITIAL_VALUE,
            equations=[
                {
                    "name": "dx/dt",
                    "function": lambda t, y, **params: -y,  # type: ignore[arg-type]
                    "variables": ["x"],
                    "parameters": {},
                }
            ],
            initial_conditions={"x": 1.0},
            boundary_conditions={},
            parameter_ranges={"t": [0, 0.5]},
            tolerance=1e-6,
            discretization={"method": "rk4", "step_size": 0.001},
            constraints=[],
        )
        result = solver.solve(problem)
        assert result.converged is True
        x_final = result.data["x"][-1]
        assert abs(x_final - math.exp(-0.5)) < 0.02
