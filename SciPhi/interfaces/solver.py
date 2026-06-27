"""Abstract base class for numerical solvers in the SciPhi framework.

This module defines the interface that all numerical solvers must implement,
along with the data structures used to describe a computational problem and
its result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from SciPhi.interfaces.model import MathematicalForm


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SolverCapabilities:
    """Describes what a solver implementation can handle."""

    name: str
    forms: list[MathematicalForm]
    methods: list[str]
    order: list[int]
    supports_parallel: bool = False
    handles_stiff: bool | None = None
    error_estimation: bool = False


@dataclass(frozen=True)
class SolverInfo:
    """High-level descriptive metadata about a solver."""

    id: str
    name: str
    methods: list[str]
    forms: list[MathematicalForm]


@dataclass
class ComputationalProblem:
    """A fully specified problem ready to be handed to a solver.

    This dataclass bundles the mathematical form, discretisation settings,
    parsed equations, initial/boundary conditions, parameter ranges,
    tolerances, and constraints into a single object that a solver can
    process.
    """

    mathematical_form: MathematicalForm
    equations: list[dict]
    initial_conditions: dict
    boundary_conditions: dict
    parameter_ranges: dict
    tolerance: float = 1e-6
    discretization: dict | None = None
    constraints: list[str] = field(default_factory=list)


@dataclass
class SimulationResult:
    """The outcome of a single solver invocation.

    Stores convergence status, performance metrics, and the computed
    solution data (normally as time-series or final values per variable).
    """

    solver_id: str
    solver_method: str
    converged: bool
    iterations: int
    execution_time: float
    data: dict  # variable_name -> list[float]
    metadata: dict
    error_estimate: float | None = None


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class Solver(ABC):
    """Abstract interface that all numerical solvers must implement.

    Subclasses provide concrete algorithms for solving computational
    problems described by a :class:`ComputationalProblem` and produce
    a :class:`SimulationResult`.
    """

    @property
    @abstractmethod
    def capabilities(self) -> SolverCapabilities:
        """The capabilities advertised by this solver implementation."""

    @abstractmethod
    def solve(self, problem: ComputationalProblem) -> SimulationResult:
        """Execute the solver on a given computational problem.

        Args:
            problem: The fully specified problem to solve.

        Returns:
            A :class:`SimulationResult` containing the solution data and
            execution metadata.
        """

    # -- Convenience helpers ------------------------------------------------

    def info(self) -> SolverInfo:
        """Return high-level descriptive metadata about this solver.

        Returns:
            A :class:`SolverInfo` instance populated from the current
            :attr:`capabilities`.
        """
        caps = self.capabilities
        return SolverInfo(
            id=type(self).__name__,
            name=caps.name,
            methods=caps.methods,
            forms=caps.forms,
        )
