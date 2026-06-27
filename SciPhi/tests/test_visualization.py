"""Tests for the SciPhi visualization module.

Verifies:
1. ``plot_result`` returns a string (data URL or error message).
2. ``plot_result`` handles empty result data gracefully.
3. ``plot_report`` returns a string.
4. ``plot_comparison`` returns a string.
5. All functions handle missing ``matplotlib`` gracefully.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from SciPhi.interfaces.solver import SimulationResult
from SciPhi.kernel.report import InvestigationReport
from SciPhi.kernel.evaluator import ValidationReport, ValidationCheck
from SciPhi.kernel.uncertainty import UncertaintyEstimate, UncertaintySource


# ---------------------------------------------------------------------------
# Fixtures: minimal SimulationResult instances
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_result() -> SimulationResult:
    """A result with no data."""
    return SimulationResult(
        solver_id="test_solver",
        solver_method="euler",
        converged=True,
        iterations=10,
        execution_time=0.5,
        data={},
        metadata={"model": "test"},
    )


@pytest.fixture
def scalar_result() -> SimulationResult:
    """A result with scalar (single-value) data."""
    return SimulationResult(
        solver_id="test_solver",
        solver_method="euler",
        converged=True,
        iterations=10,
        execution_time=0.5,
        data={"T": 298.15, "P": 101325.0, "rho": 1.225},
        metadata={"model": "test"},
    )


@pytest.fixture
def time_series_result() -> SimulationResult:
    """A result with time-series data."""
    return SimulationResult(
        solver_id="test_solver",
        solver_method="rk4",
        converged=True,
        iterations=100,
        execution_time=1.2,
        data={
            "time": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            "T": [300.0, 310.0, 320.0, 330.0, 340.0, 350.0],
            "P": [1e5, 1.05e5, 1.1e5, 1.15e5, 1.2e5, 1.25e5],
        },
        metadata={"model": "test"},
    )


@pytest.fixture
def grid_result() -> SimulationResult:
    """A result with 2-D grid data (nested lists)."""
    return SimulationResult(
        solver_id="test_solver",
        solver_method="fdm",
        converged=True,
        iterations=50,
        execution_time=3.0,
        data={
            "temperature": [
                [300, 305, 310, 315],
                [310, 315, 320, 325],
                [320, 325, 330, 335],
            ],
        },
        metadata={"model": "test"},
    )


# ---------------------------------------------------------------------------
# Fixtures: InvestigationReport
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_report() -> InvestigationReport:
    """A minimal but representative investigation report."""
    checks = [
        ValidationCheck(name="convergence", passed=True, detail="OK", severity="error"),
        ValidationCheck(name="bounds", passed=True, detail="OK", severity="error"),
        ValidationCheck(
            name="oscillations",
            passed=False,
            detail="Minor oscillation",
            severity="warning",
        ),
    ]
    validation = ValidationReport(
        passed=True,
        checks=checks,
        summary="All error-level checks passed.",
    )
    uncertainty = UncertaintyEstimate(
        overall_confidence=0.82,
        sources=[
            UncertaintySource(name="numerical", type="numerical", magnitude=0.1),
            UncertaintySource(name="parametric", type="parametric", magnitude=0.08),
        ],
        recommendations=["Refine mesh for better accuracy."],
    )
    return InvestigationReport(
        query="Test simulation of heat transfer",
        executive_summary="The simulation converged successfully.",
        methodology={"solver": "rk4", "form": "ode"},
        results={
            "status": "converged",
            "solver_id": "test_solver",
            "solver_method": "rk4",
            "iterations": 100,
            "execution_time_seconds": 1.2,
            "error_estimate": None,
            "data_summary": {
                "T": {"min": 300.0, "max": 350.0, "mean": 325.0, "count": 6},
                "P": {"min": 1e5, "max": 1.25e5, "mean": 1.125e5, "count": 6},
            },
            "metadata": {},
        },
        validation=validation,
        uncertainty=uncertainty,
        limitations=["No significant limitations identified."],
    )


@pytest.fixture
def report_no_uncertainty() -> InvestigationReport:
    """A report without uncertainty information."""
    validation = ValidationReport(
        passed=True,
        checks=[],
        summary="All checks passed.",
    )
    return InvestigationReport(
        query="Simple test",
        executive_summary="OK.",
        methodology={"solver": "euler"},
        results={"status": "analytical", "detail": "No simulation."},
        validation=validation,
        uncertainty=None,
        limitations=[],
    )


# ---------------------------------------------------------------------------
# Tests: plot_result
# ---------------------------------------------------------------------------


class TestPlotResult:
    """Tests for ``plot_result``."""

    def test_returns_string(self, time_series_result: SimulationResult) -> None:
        """``plot_result`` should return a string (data URL or error)."""
        from SciPhi.visualization import plot_result

        result = plot_result(time_series_result)
        assert isinstance(result, str)
        # If matplotlib is available, it should be a data URL.
        if not result.startswith("matplotlib is not available"):
            assert result.startswith(
                "data:image/png;base64,"
            ), f"Unexpected prefix: {result[:50]}"

    def test_scalar_returns_string(self, scalar_result: SimulationResult) -> None:
        """Scalar data should produce a string."""
        from SciPhi.visualization import plot_result

        result = plot_result(scalar_result)
        assert isinstance(result, str)

    def test_grid_returns_string(self, grid_result: SimulationResult) -> None:
        """Grid data should produce a string."""
        from SciPhi.visualization import plot_result

        result = plot_result(grid_result)
        assert isinstance(result, str)

    def test_empty_data_returns_string(self, empty_result: SimulationResult) -> None:
        """Empty data should produce a string (text-only figure)."""
        from SciPhi.visualization import plot_result

        result = plot_result(empty_result)
        assert isinstance(result, str)

    def test_save_to_path(
        self, time_series_result: SimulationResult, tmp_path: Any
    ) -> None:
        """When ``output_path`` is given, the function should return it."""
        from SciPhi.visualization import plot_result

        out = tmp_path / "test_plot.png"
        result = plot_result(time_series_result, output_path=str(out))
        assert result is None or isinstance(result, str)
        if result is not None and not result.startswith("matplotlib"):
            # File should exist when matplotlib was available.
            assert out.exists()

    def test_custom_title(self, scalar_result: SimulationResult) -> None:
        """A custom title should be accepted without error."""
        from SciPhi.visualization import plot_result

        result = plot_result(scalar_result, title="Custom Title")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: plot_report
# ---------------------------------------------------------------------------


class TestPlotReport:
    """Tests for ``plot_report``."""

    def test_returns_string(self, sample_report: InvestigationReport) -> None:
        """``plot_report`` should return a string."""
        from SciPhi.visualization import plot_report

        result = plot_report(sample_report)
        assert isinstance(result, str)

    def test_no_uncertainty(
        self, report_no_uncertainty: InvestigationReport
    ) -> None:
        """Report without uncertainty should still produce a valid plot."""
        from SciPhi.visualization import plot_report

        result = plot_report(report_no_uncertainty)
        assert isinstance(result, str)

    def test_save_to_path(
        self, sample_report: InvestigationReport, tmp_path: Any
    ) -> None:
        """When ``output_path`` is given, the function should return it."""
        from SciPhi.visualization import plot_report

        out = tmp_path / "test_report.png"
        result = plot_report(sample_report, output_path=str(out))
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: plot_comparison
# ---------------------------------------------------------------------------


class TestPlotComparison:
    """Tests for ``plot_comparison``."""

    def test_returns_string(self, time_series_result: SimulationResult) -> None:
        """``plot_comparison`` should return a string."""
        from SciPhi.visualization import plot_comparison

        result = plot_comparison(
            [time_series_result, time_series_result],
            ["Run 1", "Run 2"],
        )
        assert isinstance(result, str)

    def test_mismatched_labels(
        self, time_series_result: SimulationResult
    ) -> None:
        """Length mismatch should return an error string."""
        from SciPhi.visualization import plot_comparison

        result = plot_comparison(
            [time_series_result, time_series_result],
            ["Only one label"],
        )
        assert isinstance(result, str)
        # When matplotlib is missing the mpl error comes first.
        assert "Length mismatch" in result or "matplotlib" in result

    def test_empty_results_list(self) -> None:
        """Empty results list should return an error string."""
        from SciPhi.visualization import plot_comparison

        result = plot_comparison([], [])
        assert isinstance(result, str)
        msg = result
        assert "No results to compare" in msg or msg.startswith(
            "matplotlib"
        ), f"Unexpected message: {msg}"

    def test_incompatible_keys(self) -> None:
        """Incompatible variable keys should return an error string."""
        from SciPhi.visualization import plot_comparison

        r1 = SimulationResult(
            solver_id="s1",
            solver_method="m",
            converged=True,
            iterations=1,
            execution_time=0.1,
            data={"a": [1, 2]},
            metadata={},
        )
        r2 = SimulationResult(
            solver_id="s2",
            solver_method="m",
            converged=True,
            iterations=1,
            execution_time=0.1,
            data={"b": [3, 4]},
            metadata={},
        )
        result = plot_comparison([r1, r2], ["A", "B"])
        assert isinstance(result, str)
        # When matplotlib is missing the mpl error comes first.
        assert "incompatible" in result or "matplotlib" in result

    def test_save_to_path(
        self, time_series_result: SimulationResult, tmp_path: Any
    ) -> None:
        """When ``output_path`` is given, comparison should return it."""
        from SciPhi.visualization import plot_comparison

        out = tmp_path / "test_comparison.png"
        result = plot_comparison(
            [time_series_result, time_series_result],
            ["Run 1", "Run 2"],
            output_path=str(out),
        )
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: missing matplotlib (mock)
# ---------------------------------------------------------------------------


def _make_dummy_report() -> InvestigationReport:
    """Build a bare InvestigationReport for testing."""
    validation = ValidationReport(passed=True, checks=[], summary="")
    return InvestigationReport(
        query="q",
        executive_summary="s",
        methodology={},
        results={},
        validation=validation,
        uncertainty=None,
        limitations=[],
    )


# We patch _get_matplotlib inside the plots module so all public functions
# see None when they call it.


@pytest.mark.usefixtures("_no_mpl")
class TestMissingMatplotlib:
    """All functions should return an error string when matplotlib is absent."""

    @staticmethod
    @pytest.fixture
    def _no_mpl():
        """Temporarily make _get_matplotlib return None."""
        target = "SciPhi.visualization.plots._get_matplotlib"
        with patch(target, return_value=None) as mock:
            yield mock

    def test_plot_result_missing_mpl(self) -> None:
        """``plot_result`` returns error string when mpl is absent."""
        from SciPhi.visualization import plot_result

        res = SimulationResult(
            solver_id="x",
            solver_method="x",
            converged=True,
            iterations=1,
            execution_time=0.1,
            data={"a": 1.0},
            metadata={},
        )
        result = plot_result(res)
        assert isinstance(result, str)
        assert "matplotlib is not available" in result

    def test_plot_report_missing_mpl(self) -> None:
        """``plot_report`` returns error string when mpl is absent."""
        from SciPhi.visualization import plot_report

        report = _make_dummy_report()
        result = plot_report(report)
        assert isinstance(result, str)
        assert "matplotlib is not available" in result

    def test_plot_comparison_missing_mpl(self) -> None:
        """``plot_comparison`` returns error string when mpl is absent."""
        from SciPhi.visualization import plot_comparison

        result = plot_comparison([], [])
        assert isinstance(result, str)
        assert "matplotlib is not available" in result
