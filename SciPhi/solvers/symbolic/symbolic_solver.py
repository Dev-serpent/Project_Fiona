"""Symbolic solver using SymPy.

Provides exact (symbolic) solutions for algebraic equations, expression
simplification, and symbolic ODE solving.  The solver has no knowledge
of the underlying science -- it operates purely on symbolic expression
strings.
"""

from __future__ import annotations

import time
import traceback
from typing import Any

from SciPhi.errors import SimulationFailedError
from SciPhi.interfaces.model import MathematicalForm
from SciPhi.interfaces.solver import (
    ComputationalProblem,
    SimulationResult,
    Solver,
    SolverCapabilities,
)

# ---------------------------------------------------------------------------
# Optional sympy integration
# ---------------------------------------------------------------------------

_HAS_SYMPY = False
try:
    import sympy  # noqa: F401

    _HAS_SYMPY = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Solver implementation
# ---------------------------------------------------------------------------


class SymbolicSolver(Solver):
    """Solver for symbolic mathematical problems using SymPy.

    Supports three operations:

    * ``sympy-solve`` -- Solve algebraic equations symbolically.
    * ``sympy-simplify`` -- Simplify symbolic expressions.
    * ``sympy-dsolve`` -- Solve ordinary differential equations
      symbolically.

    Requires SymPy to be installed.  If SymPy is not available the
    solver will raise :class:`SimulationFailedError` with a clear
    message.
    """

    def __init__(self) -> None:
        self._capabilities = SolverCapabilities(
            name="Symbolic Solver (SymPy)",
            forms=[MathematicalForm.SYMBOLIC],
            methods=["sympy-solve", "sympy-simplify", "sympy-dsolve"],
            order=[0],
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
        """Perform symbolic computation on the given problem.

        Expects each equation dict in ``problem.equations`` to contain:

        * ``"expression"`` -- a string containing a SymPy-compatible
          expression or equation.
        * ``"symbols"`` -- list of symbol name strings (optional; if
          omitted symbols are inferred).
        * ``"operation"`` (or ``"type"``) -- one of ``"solve"``,
          ``"simplify"``, ``"dsolve"``.

        If the operation is not specified per-equation, the method is
        taken from ``problem.discretization["method"]`` or falls back
        to ``"sympy-solve"``.

        Args:
            problem: The fully specified computational problem.

        Returns:
            A :class:`SimulationResult` containing the symbolic results
            as string representations.

        Raises:
            SimulationFailedError: If SymPy is not installed or the
                computation fails.
        """
        if not _HAS_SYMPY:
            raise SimulationFailedError(
                type(self).__name__,
                "SymPy is required for symbolic operations. "
                "Install it with: pip install sympy",
            )

        import sympy  # noqa: W0406

        # --- Determine method -----------------------------------------------
        fallback_method = "sympy-solve"
        if problem.discretization and "method" in problem.discretization:
            fallback_method = problem.discretization["method"]

        method = fallback_method
        if method not in self._capabilities.methods:
            raise SimulationFailedError(
                type(self).__name__,
                f"Unsupported method '{method}'. Choose from {self._capabilities.methods}",
            )

        if not problem.equations:
            raise SimulationFailedError(
                type(self).__name__, "No equations provided in problem"
            )

        # --- Process each equation ------------------------------------------
        t0 = time.time()
        data: dict[str, list[Any]] = {}
        all_results: list[dict[str, Any]] = []
        converged = True

        try:
            for idx, eq in enumerate(problem.equations):
                expr_str = eq.get("expression", "")
                if not expr_str:
                    raise SimulationFailedError(
                        type(self).__name__,
                        f"Equation {idx} is missing key 'expression'",
                    )

                # Determine per-equation operation, fallback to global method
                op = eq.get("operation") or eq.get("type") or method
                op = op.replace("sympy-", "")  # normalize

                # Extract symbols
                symbol_names: list[str] = eq.get("symbols", [])
                symbols = [sympy.Symbol(name) for name in symbol_names]

                result_expr: Any = None
                result_str: str = ""

                if op == "solve":
                    result_expr = _do_solve(sympy, expr_str, symbols)
                    result_str = str(result_expr)

                elif op == "simplify":
                    result_expr = _do_simplify(sympy, expr_str)
                    result_str = str(result_expr)

                elif op == "dsolve":
                    result_expr = _do_dsolve(sympy, expr_str, symbols)
                    result_str = str(result_expr)

                else:
                    raise SimulationFailedError(
                        type(self).__name__,
                        f"Unknown symbolic operation '{op}' for equation {idx}",
                    )

                var_name = eq.get("variables", [f"eq{idx}"])[0]
                data[var_name] = [result_str]

                all_results.append(
                    {
                        "equation": expr_str,
                        "operation": op,
                        "result": result_str,
                        "symbols": symbol_names,
                    }
                )

        except Exception as exc:
            converged = False
            if isinstance(exc, SimulationFailedError):
                raise
            raise SimulationFailedError(
                type(self).__name__, f"Symbolic computation failed: {exc}"
            ) from exc
        finally:
            elapsed = time.time() - t0

        return SimulationResult(
            solver_id=type(self).__name__,
            solver_method=method,
            converged=converged,
            iterations=len(problem.equations),
            execution_time=elapsed,
            data=data,
            metadata={
                "method": method,
                "n_equations": len(problem.equations),
                "results": all_results,
                "sympy_version": getattr(sympy, "__version__", "unknown"),
            },
            error_estimate=None,
        )


# ---------------------------------------------------------------------------
# Symbolic operation helpers
# ---------------------------------------------------------------------------


def _do_solve(
    sympy_module: Any, expr_str: str, symbols: list[Any]
) -> Any:
    """Solve an algebraic equation symbolically.

    If the expression contains ``"=="`` it is treated as an equation;
    otherwise the solver solves ``expr = 0``.

    Args:
        sympy_module: The imported ``sympy`` module.
        expr_str: Expression string.
        symbols: List of SymPy Symbol objects.  If empty, all free
            symbols in the expression are used.

    Returns:
        SymPy result (list of solutions or a single solution).
    """
    expr = sympy_module.parse_expr(expr_str)

    # Check if the expression is already an Equality
    if isinstance(expr, sympy_module.Equality):
        # Re-arrange to expr = 0 form
        eq_to_solve = expr.lhs - expr.rhs
    else:
        eq_to_solve = expr

    if not symbols:
        symbols = list(eq_to_solve.free_symbols)

    if not symbols:
        return eq_to_solve

    return sympy_module.solve(eq_to_solve, *symbols, dict=True)


def _do_simplify(sympy_module: Any, expr_str: str) -> Any:
    """Simplify a symbolic expression.

    Args:
        sympy_module: The imported ``sympy`` module.
        expr_str: Expression string.

    Returns:
        Simplified SymPy expression.
    """
    expr = sympy_module.parse_expr(expr_str)
    return sympy_module.simplify(expr)


def _do_dsolve(
    sympy_module: Any, expr_str: str, symbols: list[Any]
) -> Any:
    """Solve an ODE symbolically.

    The expression should represent a differential equation, e.g.
    ``"f(x).diff(x, 2) + f(x)"``.  An equality with ``Eq`` or ``==``
    is also accepted.

    Args:
        sympy_module: The imported ``sympy`` module.
        expr_str: Expression string.
        symbols: List of SymPy Symbol objects.  The first symbol is
            treated as the function, the second (if present) as the
            independent variable.

    Returns:
        SymPy solution (typically a list of ``Equality`` objects).
    """
    expr = sympy_module.parse_expr(expr_str)

    if isinstance(expr, sympy_module.Equality):
        ode = expr.lhs - expr.rhs
    else:
        ode = expr

    # Infer function and independent variable
    if symbols:
        func = symbols[0]
        # If a Symbol was provided where a Function is needed, convert
        if isinstance(func, sympy_module.Symbol):
            # Try to find functions in the expression
            funcs = [s for s in ode.free_symbols if not isinstance(s, sympy_module.Symbol)]
            funcs_atoms = ode.atoms(sympy_module.Function)
            if funcs_atoms:
                func = list(funcs_atoms)[0]
            else:
                # Create a function from the symbol
                var = sympy_module.Symbol("x")
                if len(symbols) > 1:
                    var = symbols[1]
                func = sympy_module.Function(func.name)(var)
        x = sympy_module.Symbol("x")
        if len(symbols) > 1:
            x = symbols[1]
    else:
        # Try to auto-detect
        funcs_atoms = list(ode.atoms(sympy_module.Function))
        if funcs_atoms:
            func = funcs_atoms[0]
        else:
            raise SimulationFailedError(
                "SymbolicSolver",
                "Cannot detect function in ODE expression. "
                "Provide symbols=['f', 'x'] in the equation dict.",
            )
        x = sympy_module.Symbol("x")

    return sympy_module.dsolve(ode, ics=None)
