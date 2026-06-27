"""Uncertainty Analyzer — estimates and reports uncertainty in simulation results.

The :class:`UncertaintyAnalyzer` examines a :class:`SimulationResult` in the
context of its :class:`InvestigationPlan` and quantifies the overall confidence
by considering parameter bounds, solver error estimates, model simplifications,
and numerical approximations.
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
class UncertaintySource:
    """A single identified source of uncertainty.

    Attributes:
        name: A short identifier for the uncertainty source
            (e.g. ``"parameter_bounds"``, ``"solver_truncation"``).
        type: The category of uncertainty — one of ``"parametric"``,
            ``"numerical"``, ``"model"``, or ``"measurement"``.
        magnitude: A normalised magnitude in [0, 1] indicating the relative
            contribution to overall uncertainty.
        description: A human-readable description of the uncertainty source.
    """

    name: str
    type: str = "parametric"
    magnitude: float = 0.0
    description: str = ""


@dataclass(frozen=True)
class UncertaintyEstimate:
    """Aggregated uncertainty estimate for a simulation result.

    Attributes:
        overall_confidence: A value in [0, 1] representing the overall
            confidence in the result (1 = highest confidence).
        sources: A list of individual :class:`UncertaintySource` instances
            that contribute to the overall uncertainty.
        recommendations: Actionable recommendations for reducing uncertainty
            in future investigations.
    """

    overall_confidence: float = 1.0
    sources: list[UncertaintySource] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class UncertaintyAnalyzer:
    """Estimates uncertainty in simulation results from multiple sources.

    The analyzer considers:

    - **Parametric uncertainty**: uncertainty propagated from input parameter
      bounds and variability.
    - **Numerical uncertainty**: discretisation error, truncation error, and
      solver convergence tolerance.
    - **Model uncertainty**: simplifications and assumptions made by the model.
    """

    async def analyze(
        self,
        result: SimulationResult,
        plan: InvestigationPlan,
    ) -> UncertaintyEstimate:
        """Estimate uncertainty in a simulation result.

        Args:
            result: The :class:`SimulationResult` to analyse.
            plan: The :class:`InvestigationPlan` describing the problem
                context, assumptions, and constraints.

        Returns:
            An :class:`UncertaintyEstimate` with overall confidence,
            individual uncertainty sources, and recommendations.
        """
        sources: list[UncertaintySource] = []

        # 1. Solver numerical uncertainty.
        sources.append(self._estimate_numerical_uncertainty(result))

        # 2. Parametric uncertainty from plan parameters.
        sources.append(self._estimate_parametric_uncertainty(plan))

        # 3. Model uncertainty from assumptions and simplifications.
        sources.append(self._estimate_model_uncertainty(plan))

        # Compute overall confidence from individual sources.
        overall_confidence = self._compute_overall_confidence(sources, result)

        # Generate recommendations.
        recommendations = self._generate_recommendations(sources, plan, result)

        return UncertaintyEstimate(
            overall_confidence=overall_confidence,
            sources=sources,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # Estimation heuristics
    # ------------------------------------------------------------------

    def _estimate_numerical_uncertainty(
        self, result: SimulationResult,
    ) -> UncertaintySource:
        """Estimate uncertainty from solver numerics."""
        if result.error_estimate is not None:
            magnitude = min(result.error_estimate, 1.0)
            return UncertaintySource(
                name="solver_numerical",
                type="numerical",
                magnitude=magnitude,
                description=(
                    f"Solver reported error estimate of {result.error_estimate:.2e}. "
                    f"Converged in {result.iterations} iterations."
                ),
            )

        # No error estimate available; assign a moderate default.
        if result.converged:
            return UncertaintySource(
                name="solver_numerical",
                type="numerical",
                magnitude=0.05,
                description=(
                    "No explicit error estimate from solver. Default numerical "
                    "uncertainty of 5 % assumed."
                ),
            )

        return UncertaintySource(
            name="solver_numerical",
            type="numerical",
            magnitude=0.5,
            description="Solver did not converge — high numerical uncertainty.",
        )

    def _estimate_parametric_uncertainty(
        self, plan: InvestigationPlan,
    ) -> UncertaintySource:
        """Estimate uncertainty from input parameter ranges."""
        if not plan.parameters:
            return UncertaintySource(
                name="parametric",
                type="parametric",
                magnitude=0.01,
                description="No explicit parameters — parametric uncertainty is negligible.",
            )

        # Stub: in production this would propagate actual parameter ranges
        # through sensitivity analysis or Monte Carlo.
        num_params = len(plan.parameters)
        base_uncertainty = min(0.01 * num_params, 0.3)

        return UncertaintySource(
            name="parametric",
            type="parametric",
            magnitude=base_uncertainty,
            description=(
                f"Estimated parametric uncertainty from {num_params} parameter(s). "
                "Full sensitivity analysis not yet implemented."
            ),
        )

    def _estimate_model_uncertainty(
        self, plan: InvestigationPlan,
    ) -> UncertaintySource:
        """Estimate uncertainty from model assumptions and simplifications."""
        num_assumptions = len(plan.assumptions)
        if num_assumptions == 0:
            return UncertaintySource(
                name="model_simplification",
                type="model",
                magnitude=0.02,
                description="No explicit assumptions declared. Minimal model uncertainty assumed.",
            )

        # Each assumption contributes a small amount.
        magnitude = min(0.02 * num_assumptions, 0.4)
        assumption_descriptions = [a.statement for a in plan.assumptions]

        return UncertaintySource(
            name="model_simplification",
            type="model",
            magnitude=magnitude,
            description=(
                f"Model makes {num_assumptions} assumption(s): "
                f"{'; '.join(assumption_descriptions)}."
            ),
        )

    def _compute_overall_confidence(
        self,
        sources: list[UncertaintySource],
        result: SimulationResult,
    ) -> float:
        """Combine uncertainty sources into an overall confidence score.

        Uses a simple product-of-complements model:
        ``confidence = ∏ (1 - magnitude_i)``
        """
        if not result.converged:
            return 0.1  # Very low confidence when the solver doesn't converge.

        confidence = 1.0
        for source in sources:
            confidence *= 1.0 - source.magnitude

        return max(0.0, min(1.0, confidence))

    def _generate_recommendations(
        self,
        sources: list[UncertaintySource],
        plan: InvestigationPlan,
        result: SimulationResult,
    ) -> list[str]:
        """Generate actionable recommendations to reduce uncertainty."""
        recommendations: list[str] = []

        for source in sources:
            if source.magnitude > 0.1:
                if source.type == "numerical":
                    recommendations.append(
                        "Refine the discretisation or reduce solver tolerance "
                        "to lower numerical uncertainty."
                    )
                elif source.type == "parametric":
                    recommendations.append(
                        "Perform a sensitivity analysis or use tighter parameter "
                        "bounds to reduce parametric uncertainty."
                    )
                elif source.type == "model":
                    recommendations.append(
                        "Review model assumptions and consider a higher-fidelity "
                        "model to reduce structural uncertainty."
                    )

        if not result.converged:
            recommendations.insert(
                0,
                "Investigate solver non-convergence: adjust solver settings, "
                "relax tolerances, or try a different solver method.",
            )

        if not recommendations:
            recommendations.append(
                "Uncertainty is already well-characterised. Continue monitoring."
            )

        return recommendations
