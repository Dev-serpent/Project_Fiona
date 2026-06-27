"""Tests for the algebraic (root-finding) solver.

Verifies:
1. Capabilities are declared correctly.
2. Solver can solve a simple known problem (find sqrt(2) via x^2 - 2 = 0).
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
from SciPhi.solvers.deterministic.algebraic_solver import AlgebraicSolver


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def solver() -> AlgebraicSolver:
    return AlgebraicSolver()


def _make_root_problem(
    method: str = "newton-raphson",
    function: str = "lambda x: x**2 - 2",
    derivative: str | None = "lambda x: 2*x",
    x0: float = 1.0,
    bounds: list[float] | None = None,
    tolerance: float = 1e-6,
) -> ComputationalProblem:
    """Create a problem for finding sqrt(2) via f(x) = x^2 - 2 = 0."""
    eq: dict[str, Any] = {
        "name": "f",
        "function": function,
        "variables": ["x"],
    }
    if derivative is not None:
        eq["derivative"] = derivative
    if bounds is not None:
        eq["bounds"] = bounds

    return ComputationalProblem(
        mathematical_form=MathematicalForm.ALGEBRAIC,
        equations=[eq],
        initial_conditions={"x": x0},
        boundary_conditions={},
        parameter_ranges={},
        tolerance=tolerance,
        discretization={"method": method},
        constraints=[],
    )


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_capabilities_type(self, solver: AlgebraicSolver) -> None:
        caps = solver.capabilities
        assert isinstance(caps, SolverCapabilities)

    def test_capabilities_forms(self, solver: AlgebraicSolver) -> None:
        caps = solver.capabilities
        assert MathematicalForm.ALGEBRAIC in caps.forms
        assert len(caps.forms) == 1

    def test_capabilities_methods(self, solver: AlgebraicSolver) -> None:
        caps = solver.capabilities
        assert "newton-raphson" in caps.methods
        assert "bisection" in caps.methods
        assert "fixed-point" in caps.methods
        assert len(caps.methods) == 3

    def test_info(self, solver: AlgebraicSolver) -> None:
        info = solver.info()
        assert info.id == "AlgebraicSolver"
        assert MathematicalForm.ALGEBRAIC in info.forms


# ---------------------------------------------------------------------------
# Solve: find sqrt(2) ≈ 1.4142
# ---------------------------------------------------------------------------


class TestSolve:
    @pytest.mark.parametrize("method", ["newton-raphson", "bisection"])
    def test_sqrt2(self, solver: AlgebraicSolver, method: str) -> None:
        if method == "newton-raphson":
            problem = _make_root_problem(method=method)
        else:
            problem = _make_root_problem(
                method=method,
                derivative=None,
                bounds=[0.0, 3.0],
            )

        result = solver.solve(problem)

        assert isinstance(result, SimulationResult)
        assert result.solver_method == method

        root = result.data.get("x", [None])[0]
        assert root is not None
        assert abs(root - math.sqrt(2)) < 1e-4, (
            f"method={method}: root={root}, expected sqrt(2)={math.sqrt(2)}"
        )

    def test_fixed_point(self, solver: AlgebraicSolver) -> None:
        """Solve x = sqrt(2)/x + x/2 via fixed-point... actually use x = cos(x) via callable."""
        # Use a callable directly so we don't need math in the eval namespace
        import math as _math

        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.ALGEBRAIC,
            equations=[
                {
                    "name": "g",
                    "function": lambda x: _math.cos(x),  # type: ignore[arg-type]
                    "variables": ["x"],
                }
            ],
            initial_conditions={"x": 0.5},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "fixed-point"},
            constraints=[],
        )
        result = solver.solve(problem)
        assert result.converged is True
        root = result.data.get("x", [None])[0]
        assert root is not None
        # cos(x) = x has solution around 0.739
        assert abs(root - 0.739) < 0.01

    def test_result_structure(self, solver: AlgebraicSolver) -> None:
        problem = _make_root_problem()
        result = solver.solve(problem)

        assert isinstance(result.data, dict)
        assert "x" in result.data
        assert isinstance(result.solver_id, str)
        assert isinstance(result.execution_time, float)
        assert isinstance(result.iterations, int)
        assert isinstance(result.metadata, dict)

    def test_newton_raphson_without_derivative(self, solver: AlgebraicSolver) -> None:
        """Newton-Raphson should work via numerical differentiation."""
        problem = _make_root_problem(derivative=None)
        result = solver.solve(problem)
        root = result.data["x"][0]
        assert abs(root - math.sqrt(2)) < 1e-4

    # ------------------------------------------------------------------
    # Invalid input handling
    # ------------------------------------------------------------------

    def test_unsupported_method(self, solver: AlgebraicSolver) -> None:
        problem = _make_root_problem(method="invalid")
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_bisection_no_bounds(self, solver: AlgebraicSolver) -> None:
        problem = _make_root_problem(
            method="bisection",
            derivative=None,
            bounds=None,
        )
        # Should fail because bisection needs bounds
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_missing_function(self, solver: AlgebraicSolver) -> None:
        """Missing 'function' key should return a non-converged result."""
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.ALGEBRAIC,
            equations=[{"name": "bad", "variables": ["x"]}],
            initial_conditions={"x": 1.0},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "newton-raphson"},
            constraints=[],
        )
        result = solver.solve(problem)
        assert result.converged is False

    def test_no_equations(self, solver: AlgebraicSolver) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.ALGEBRAIC,
            equations=[],
            initial_conditions={"x": 1.0},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "newton-raphson"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)
