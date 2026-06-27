"""Abstract base class for scientific models in the SciPhi framework.

This module defines the foundational types and abstract interface that all
domain-specific scientific models must implement. It establishes the contract
for model metadata, governing equations, variables, parameters, and constraints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ScientificDomain(Enum):
    """Broad scientific or engineering domain a model belongs to."""

    PHYSICS = auto()
    CHEMISTRY = auto()
    BIOLOGY = auto()
    EARTH_SCIENCE = auto()
    ENGINEERING = auto()
    MATHEMATICS = auto()


class MathematicalForm(Enum):
    """The mathematical structure of a model's governing equations."""

    ALGEBRAIC = auto()
    ODE_INITIAL_VALUE = auto()
    ODE_BOUNDARY_VALUE = auto()
    PDE = auto()
    STOCHASTIC = auto()
    OPTIMIZATION = auto()
    SYMBOLIC = auto()
    HYBRID = auto()


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Equation:
    """A single governing equation in symbolic form."""

    name: str
    expression: str
    description: str


@dataclass(frozen=True)
class Variable:
    """A state variable within a scientific model."""

    name: str
    symbol: str
    unit: str
    description: str


@dataclass(frozen=True)
class Parameter:
    """A model parameter with a default numerical value."""

    name: str
    symbol: str
    default_value: float
    unit: str
    description: str


@dataclass(frozen=True)
class Assumption:
    """An assumption made by the model and its impact on validity."""

    statement: str
    impact: str


@dataclass(frozen=True)
class Constraint:
    """A constraint the model must satisfy."""

    description: str
    expression: str


@dataclass(frozen=True)
class PhysicalConstant:
    """A named physical constant with value, unit, and optional uncertainty."""

    name: str
    symbol: str
    value: float
    unit: str
    uncertainty: float | None = None


@dataclass(frozen=True)
class ModelInfo:
    """High-level summary metadata for a scientific model."""

    id: str
    name: str
    domain: ScientificDomain
    description: str
    equation_count: int


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class ScientificModel(ABC):
    """Abstract interface that all scientific models must implement.

    Subclasses provide concrete definitions of the domain, equations,
    variables, parameters, assumptions, constraints, and fundamental
    constants that characterise a specific scientific model.
    """

    @property
    @abstractmethod
    def domain(self) -> ScientificDomain:
        """The scientific domain this model belongs to."""

    @property
    @abstractmethod
    def equations(self) -> list[Equation]:
        """The governing equations defining the model."""

    @property
    @abstractmethod
    def variables(self) -> list[Variable]:
        """State variables the model solves for."""

    @property
    @abstractmethod
    def parameters(self) -> list[Parameter]:
        """Tunable parameters accepted by the model."""

    @property
    @abstractmethod
    def mathematical_form(self) -> MathematicalForm:
        """The mathematical structure of the governing equations."""

    @property
    @abstractmethod
    def assumptions(self) -> list[Assumption]:
        """Assumptions inherent to the model's derivation."""

    @property
    @abstractmethod
    def constraints(self) -> list[Constraint]:
        """Constraints the model or its solution must respect."""

    @property
    @abstractmethod
    def constants(self) -> list[PhysicalConstant]:
        """Fundamental physical constants referenced by the model."""

    # -- Convenience helpers ------------------------------------------------

    def info(self) -> ModelInfo:
        """Return high-level metadata about this model.

        Returns:
            A :class:`ModelInfo` instance populated from the current model
            properties.
        """
        return ModelInfo(
            id=type(self).__name__,
            name=type(self).__name__,
            domain=self.domain,
            description=self.equations[0].description if self.equations else "",
            equation_count=len(self.equations),
        )
