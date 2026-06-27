"""SciPhi interfaces package.

Exposes the abstract base classes that define the SciPhi framework contract
for scientific models and solvers.
"""

from SciPhi.interfaces.model import (
    Assumption,
    Constraint,
    Equation,
    MathematicalForm,
    ModelInfo,
    Parameter,
    PhysicalConstant,
    ScientificDomain,
    ScientificModel,
    Variable,
)
from SciPhi.interfaces.solver import (
    ComputationalProblem,
    SimulationResult,
    Solver,
    SolverCapabilities,
    SolverInfo,
)

__all__ = [
    # Model layer
    "ScientificDomain",
    "MathematicalForm",
    "Equation",
    "Variable",
    "Parameter",
    "Assumption",
    "Constraint",
    "PhysicalConstant",
    "ModelInfo",
    "ScientificModel",
    # Solver layer
    "SolverCapabilities",
    "SolverInfo",
    "ComputationalProblem",
    "SimulationResult",
    "Solver",
]
