"""Tests for the symbolic solver.

Verifies:
1. Capabilities are declared correctly.
2. Solver can perform symbolic solve, simplify, and dsolve operations.
3. Solver handles missing sympy gracefully.
4. Solver handles invalid input gracefully.
5. Solver returns correct result type (SimulationResult).
"""

from __future__ import annotations

import pytest

from SciPhi.interfaces.model import MathematicalForm
from SciPhi.interfaces.solver import (
    ComputationalProblem,
    SimulationResult,
    SolverCapabilities,
)
from SciPhi.solvers.symbolic.symbolic_solver import SymbolicSolver

# Check if sympy is available
try:
    import sympy  # noqa: F401

    _HAS_SYMPY = True
except ImportError:
    _HAS_SYMPY = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def solver() -> SymbolicSolver:
    return SymbolicSolver()


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_capabilities_type(self, solver: SymbolicSolver) -> None:
        caps = solver.capabilities
        assert isinstance(caps, SolverCapabilities)

    def test_capabilities_forms(self, solver: SymbolicSolver) -> None:
        caps = solver.capabilities
        assert MathematicalForm.SYMBOLIC in caps.forms
        assert len(caps.forms) == 1

    def test_capabilities_methods(self, solver: SymbolicSolver) -> None:
        caps = solver.capabilities
        assert "sympy-solve" in caps.methods
        assert "sympy-simplify" in caps.methods
        assert "sympy-dsolve" in caps.methods
        assert len(caps.methods) == 3

    def test_info(self, solver: SymbolicSolver) -> None:
        info = solver.info()
        assert info.id == "SymbolicSolver"
        assert MathematicalForm.SYMBOLIC in info.forms


# ---------------------------------------------------------------------------
# Solve operations (only if sympy is installed)
# ---------------------------------------------------------------------------


class TestSolve:
    @pytest.mark.skipif(not _HAS_SYMPY, reason="SymPy is not installed")
    def test_sympy_solve_quadratic(self, solver: SymbolicSolver) -> None:
        """Solve x**2 - 2 = 0."""
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.SYMBOLIC,
            equations=[
                {
                    "expression": "x**2 - 2",
                    "symbols": ["x"],
                    "operation": "solve",
                    "variables": ["solution"],
                }
            ],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "sympy-solve"},
            constraints=[],
        )
        result = solver.solve(problem)

        assert isinstance(result, SimulationResult)
        assert result.converged is True
        assert result.solver_method == "sympy-solve"

        sol_str = result.data.get("solution", [""])[0]
        assert sol_str is not None
        # Should contain sqrt(2) in the solution
        assert "sqrt" in sol_str or "2" in sol_str

    @pytest.mark.skipif(not _HAS_SYMPY, reason="SymPy is not installed")
    def test_sympy_simplify(self, solver: SymbolicSolver) -> None:
        """Simplify (x+1)**2 - (x**2 + 2*x + 1) → 0."""
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.SYMBOLIC,
            equations=[
                {
                    "expression": "(x+1)**2 - (x**2 + 2*x + 1)",
                    "symbols": ["x"],
                    "operation": "simplify",
                    "variables": ["result"],
                }
            ],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "sympy-simplify"},
            constraints=[],
        )
        result = solver.solve(problem)

        assert result.converged is True
        expr_str = result.data.get("result", [""])[0]
        # The simplified form should be "0"
        assert "0" in expr_str

    @pytest.mark.skipif(not _HAS_SYMPY, reason="SymPy is not installed")
    def test_sympy_dsolve(self, solver: SymbolicSolver) -> None:
        """Solve f''(x) + f(x) = 0 symbolically."""
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.SYMBOLIC,
            equations=[
                {
                    "expression": "Derivative(f(x), (x, 2)) + f(x)",
                    "symbols": ["f", "x"],
                    "operation": "dsolve",
                    "variables": ["solution"],
                }
            ],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "sympy-dsolve"},
            constraints=[],
        )
        result = solver.solve(problem)

        assert result.converged is True
        sol_str = result.data.get("solution", [""])[0]
        assert sol_str is not None
        # Should contain sin or cos in the solution
        assert "sin" in sol_str.lower() or "cos" in sol_str.lower()

    @pytest.mark.skipif(not _HAS_SYMPY, reason="SymPy is not installed")
    def test_result_structure(self, solver: SymbolicSolver) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.SYMBOLIC,
            equations=[
                {
                    "expression": "x + 1",
                    "symbols": ["x"],
                    "operation": "simplify",
                    "variables": ["out"],
                }
            ],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "sympy-simplify"},
            constraints=[],
        )
        result = solver.solve(problem)

        assert isinstance(result.data, dict)
        assert "out" in result.data
        assert isinstance(result.solver_id, str)
        assert isinstance(result.execution_time, float)
        assert isinstance(result.iterations, int)
        assert isinstance(result.metadata, dict)
        assert "results" in result.metadata

    # ------------------------------------------------------------------
    # Missing sympy
    # ------------------------------------------------------------------

    def test_no_sympy(self, solver: SymbolicSolver) -> None:
        """If sympy is not installed, should raise a clear error."""
        if _HAS_SYMPY:
            pytest.skip("SymPy is installed, can't test missing case")
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.SYMBOLIC,
            equations=[
                {
                    "expression": "x**2 - 2",
                    "symbols": ["x"],
                    "operation": "solve",
                    "variables": ["x"],
                }
            ],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "sympy-solve"},
            constraints=[],
        )
        with pytest.raises(Exception, match="SymPy is required"):
            solver.solve(problem)

    # ------------------------------------------------------------------
    # Invalid input handling
    # ------------------------------------------------------------------

    def test_unsupported_method(self, solver: SymbolicSolver) -> None:
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.SYMBOLIC,
            equations=[],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "invalid"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_no_equations(self, solver: SymbolicSolver) -> None:
        if not _HAS_SYMPY:
            pytest.skip("SymPy not installed")
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.SYMBOLIC,
            equations=[],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "sympy-solve"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)

    def test_missing_expression(self, solver: SymbolicSolver) -> None:
        if not _HAS_SYMPY:
            pytest.skip("SymPy not installed")
        problem = ComputationalProblem(
            mathematical_form=MathematicalForm.SYMBOLIC,
            equations=[{"operation": "solve", "variables": ["x"]}],
            initial_conditions={},
            boundary_conditions={},
            parameter_ranges={},
            tolerance=1e-6,
            discretization={"method": "sympy-solve"},
            constraints=[],
        )
        with pytest.raises(Exception):
            solver.solve(problem)
