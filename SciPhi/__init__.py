"""SciPhi — A scientific computing framework for model definition and simulation.

SciPhi provides abstract interfaces for defining scientific models and connecting
them to numerical solvers, along with foundational data utilities for physical
constants and unit conversions.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Expose key types at the package root for convenient access.

from SciPhi.kernel.opsim import OpsimKernel
from SciPhi.kernel.report import InvestigationReport
from SciPhi.kernel.hypothesis import Hypothesis, HypothesisResult
from SciPhi.kernel.evaluator import ValidationReport, ValidationCheck
from SciPhi.kernel.uncertainty import UncertaintyEstimate, UncertaintySource
from SciPhi.kernel.provenance import ProvenanceEntry
from SciPhi.data.constants import PhysicalConstants
from SciPhi.data.units import UnitConverter
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
    # Kernel
    "OpsimKernel",
    "InvestigationReport",
    "Hypothesis",
    "HypothesisResult",
    "ValidationReport",
    "ValidationCheck",
    "UncertaintyEstimate",
    "UncertaintySource",
    "ProvenanceEntry",
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
    # Data utilities
    "PhysicalConstants",
    "UnitConverter",
]
