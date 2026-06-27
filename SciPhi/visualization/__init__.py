"""Visualization module for SciPhi simulation results.

Provides convenience functions for plotting :class:`SimulationResult` objects
and :class:`InvestigationReport` summaries using ``matplotlib`` (optional
dependency — all functions degrade gracefully when the library is not
installed).
"""

from __future__ import annotations

from SciPhi.visualization.plots import plot_comparison, plot_report, plot_result

__all__ = [
    "plot_result",
    "plot_report",
    "plot_comparison",
]
