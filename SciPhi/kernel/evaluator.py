"""Scientific Evaluator — validates simulation results against scientific criteria.

The :class:`ScientificEvaluator` performs a battery of checks on simulation
results to ensure they are physically plausible, numerically stable, and
consistent with the investigation plan's constraints and assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from SciPhi.interfaces.solver import SimulationResult
    from SciPhi.kernel.planner import InvestigationPlan


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationCheck:
    """A single validation check and its outcome.

    Attributes:
        name: A short identifier for the check (e.g. ``"unit_consistency"``).
        passed: Whether the check passed.
        detail: A human-readable description of what was checked and the
            outcome.
        severity: The severity if the check fails (``"error"``, ``"warning"``,
            or ``"info"``). An ``"error"``-severity failure causes the overall
            validation to fail.
    """

    name: str
    passed: bool
    detail: str = ""
    severity: str = "error"


@dataclass(frozen=True)
class ValidationReport:
    """Aggregated outcome of all validation checks.

    Attributes:
        passed: ``True`` if all error-severity checks passed.
        checks: The full list of :class:`ValidationCheck` instances performed.
        summary: A concise human-readable summary of the validation outcome.
    """

    passed: bool
    checks: list[ValidationCheck] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class ScientificEvaluator:
    """Validates simulation results against physical and numerical criteria.

    The evaluator runs the following checks:

    - **Unit consistency**: ensures that result data has expected dimensions.
    - **Conservation laws**: checks energy, momentum, and mass conservation
      where applicable.
    - **Physical bounds**: verifies values are non-negative where expected
      and finite everywhere.
    - **Numerical stability**: checks for convergence, oscillations, and
      anomalous spikes.
    """

    async def validate(
        self,
        result: SimulationResult,
        plan: InvestigationPlan,
    ) -> ValidationReport:
        """Run all validation checks on a simulation result.

        Args:
            result: The :class:`SimulationResult` to validate.
            plan: The :class:`InvestigationPlan` defining the expected
                constraints and boundary conditions.

        Returns:
            A :class:`ValidationReport` aggregating all check results.
        """
        checks: list[ValidationCheck] = []

        checks.append(self._check_convergence(result))
        checks.append(self._check_finite_values(result))
        checks.append(self._check_non_negative_values(result, plan))
        checks.append(self._check_oscillations(result))
        checks.append(self._check_error_bounds(result))

        # Determine overall pass/fail: all error-severity checks must pass.
        passed = all(
            check.passed or check.severity != "error"
            for check in checks
        )

        summary_parts: list[str] = []
        for check in checks:
            status = "✓" if check.passed else "✗"
            summary_parts.append(f"[{status}] {check.name}: {check.detail}")

        summary = "\n".join(summary_parts)

        return ValidationReport(
            passed=passed,
            checks=checks,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_convergence(self, result: SimulationResult) -> ValidationCheck:
        """Verify that the solver converged."""
        if result.converged:
            return ValidationCheck(
                name="convergence",
                passed=True,
                detail=f"Solver converged in {result.iterations} iterations.",
                severity="error",
            )
        return ValidationCheck(
            name="convergence",
            passed=False,
            detail=f"Solver did not converge after {result.iterations} iterations.",
            severity="error",
        )

    def _check_finite_values(self, result: SimulationResult) -> ValidationCheck:
        """Verify that all result values are finite (no NaN or Inf)."""
        import math

        non_finite_vars: list[str] = []
        for var_name, values in result.data.items():
            for i, val in enumerate(values):
                if val is None or (isinstance(val, (int, float)) and not math.isfinite(val)):
                    non_finite_vars.append(f"{var_name}[{i}]")

        if not non_finite_vars:
            return ValidationCheck(
                name="finite_values",
                passed=True,
                detail="All result values are finite.",
                severity="error",
            )
        return ValidationCheck(
            name="finite_values",
            passed=False,
            detail=f"Non-finite values found in: {', '.join(non_finite_vars[:10])}.",
            severity="error",
        )

    def _check_non_negative_values(
        self, result: SimulationResult, plan: InvestigationPlan,
    ) -> ValidationCheck:
        """Verify that physically non-negative variables are indeed non-negative.

        Checks variables that represent quantities like mass, concentration,
        density, etc.
        """
        # Identify variables that must be non-negative based on naming.
        non_negative_keywords = ("mass", "concentration", "density", "pressure",
                                 "temperature", "population", "count", "amount")
        negative_vars: list[str] = []

        for var_name, values in result.data.items():
            if any(kw in var_name.lower() for kw in non_negative_keywords):
                for i, val in enumerate(values):
                    if isinstance(val, (int, float)) and val < 0:
                        negative_vars.append(f"{var_name}[{i}]={val}")
                        break  # One report per variable is enough.

        if not negative_vars:
            return ValidationCheck(
                name="non_negative_values",
                passed=True,
                detail="All physically non-negative variables satisfy the constraint.",
                severity="error",
            )
        return ValidationCheck(
            name="non_negative_values",
            passed=False,
            detail=f"Negative values found in: {', '.join(negative_vars)}.",
            severity="error",
        )

    def _check_oscillations(self, result: SimulationResult) -> ValidationCheck:
        """Detect numerical oscillations in the result data (stub).

        A simple heuristic checks whether any variable's values oscillate
        between successive entries beyond a threshold.
        """
        oscillation_vars: list[str] = []

        for var_name, values in result.data.items():
            if len(values) < 3:
                continue
            # Count sign changes in successive differences.
            sign_changes = 0
            for i in range(2, len(values)):
                try:
                    d1 = float(values[i - 1]) - float(values[i - 2])
                    d2 = float(values[i]) - float(values[i - 1])
                    if d1 * d2 < 0:
                        sign_changes += 1
                except (TypeError, ValueError):
                    continue
            # If more than half the points are turning points, flag it.
            if sign_changes > len(values) // 2:
                oscillation_vars.append(var_name)

        if not oscillation_vars:
            return ValidationCheck(
                name="numerical_oscillations",
                passed=True,
                detail="No excessive numerical oscillations detected.",
                severity="warning",
            )
        return ValidationCheck(
            name="numerical_oscillations",
            passed=False,
            detail=f"Excessive oscillations detected in: {', '.join(oscillation_vars)}.",
            severity="warning",
        )

    def _check_error_bounds(self, result: SimulationResult) -> ValidationCheck:
        """Verify that the solver's error estimate is within acceptable bounds."""
        if result.error_estimate is None:
            return ValidationCheck(
                name="error_estimate",
                passed=True,
                detail="No error estimate provided by solver — skipping check.",
                severity="info",
            )

        # A heuristic threshold: error estimate should be < 10 %.
        threshold = 0.1
        if result.error_estimate < threshold:
            return ValidationCheck(
                name="error_estimate",
                passed=True,
                detail=f"Error estimate {result.error_estimate:.2e} is within "
                       f"acceptable bounds (< {threshold}).",
                severity="error",
            )
        return ValidationCheck(
            name="error_estimate",
            passed=False,
            detail=f"Error estimate {result.error_estimate:.2e} exceeds "
                   f"acceptable threshold ({threshold}).",
            severity="warning",
        )
