"""SciPhi Kernel — core scientific operating system components.

The kernel package provides the central orchestration and supporting
subsystems for the SciPhi framework. Exposed public classes:

* :class:`OpsimKernel` — the central investigation orchestrator.
* :class:`InvestigationPlan` — a structured plan produced by the planner.
* :class:`InvestigationReport` — the final report from an investigation.
* :class:`Hypothesis` — a single testable scientific hypothesis.
"""

from __future__ import annotations

from SciPhi.kernel.hypothesis import Hypothesis, HypothesisResult
from SciPhi.kernel.opsim import OpsimKernel
from SciPhi.kernel.planner import InvestigationPlan
from SciPhi.kernel.report import InvestigationReport

__all__ = [
    "Hypothesis",
    "HypothesisResult",
    "InvestigationPlan",
    "InvestigationReport",
    "OpsimKernel",
]
