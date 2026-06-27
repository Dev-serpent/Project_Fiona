"""Deterministic solvers for ODE and algebraic problems."""

from __future__ import annotations

from SciPhi.solvers.deterministic.ode_solver import ODESolver
from SciPhi.solvers.deterministic.algebraic_solver import AlgebraicSolver

__all__ = [
    "ODESolver",
    "AlgebraicSolver",
]
