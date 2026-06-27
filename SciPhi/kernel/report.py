"""Report Generator — compiles all investigation phases into a structured report.

The :class:`ReportGenerator` takes the outputs of every investigation phase
(plan, result, validation, uncertainty, provenance, hypothesis evaluation)
and assembles them into a single :class:`InvestigationReport` that can be
returned to the user or agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from SciPhi.interfaces.solver import SimulationResult
    from SciPhi.kernel.evaluator import ValidationReport
    from SciPhi.kernel.hypothesis import HypothesisResult
    from SciPhi.kernel.planner import InvestigationPlan
    from SciPhi.kernel.provenance import ProvenanceEntry
    from SciPhi.kernel.uncertainty import UncertaintyEstimate


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvestigationReport:
    """The final output of a SciPhi investigation.

    Contains all information produced during the investigation pipeline,
    from the original query through to validation and provenance.

    Attributes:
        query: The original user query.
        executive_summary: A concise summary of findings.
        methodology: A dictionary describing the methodology used (model,
            solver, equations, etc.).
        results: A dictionary summarising the simulation or analytical
            results.
        validation: The :class:`ValidationReport` from the evaluator.
        uncertainty: The :class:`UncertaintyEstimate` from uncertainty
            analysis, or ``None``.
        hypothesis_evaluation: Results of hypothesis testing, or ``None``.
        limitations: A list of identified limitations.
        provenance_id: The ID of the provenance record for traceability.
        traceability: The full :class:`ProvenanceEntry` for this
            investigation.
        timestamp: An ISO-8601 formatted timestamp string.
    """

    query: str
    executive_summary: str
    methodology: dict
    results: dict
    validation: ValidationReport
    uncertainty: UncertaintyEstimate | None = None
    hypothesis_evaluation: list[HypothesisResult] | None = None
    limitations: list[str] = field(default_factory=list)
    provenance_id: str = ""
    traceability: ProvenanceEntry | None = None
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Compiles the outputs of all investigation phases into a final report.

    The generator assembles structured data from each phase into a single
    :class:`InvestigationReport` dataclass. It also produces a human-readable
    executive summary.
    """

    async def compile(
        self,
        plan: InvestigationPlan,
        result: SimulationResult | None,
        validation: ValidationReport,
        uncertainty: UncertaintyEstimate | None,
        provenance: ProvenanceEntry,
        hypotheses: list[HypothesisResult] | None = None,
    ) -> InvestigationReport:
        """Compile all investigation phases into a structured report.

        Args:
            plan: The :class:`InvestigationPlan` produced by the planner.
            result: The :class:`SimulationResult` from the solver, or
                ``None`` if simulation was skipped.
            validation: The :class:`ValidationReport` from the evaluator.
            uncertainty: The :class:`UncertaintyEstimate` from uncertainty
                analysis, or ``None``.
            provenance: The :class:`ProvenanceEntry` recorded for this
                investigation.
            hypotheses: Optional list of :class:`HypothesisResult` from
                hypothesis evaluation.

        Returns:
            A fully populated :class:`InvestigationReport`.
        """
        methodology = self._build_methodology(plan, provenance, result is not None)
        results = self._build_results(result)
        limitations = self._identify_limitations(validation, uncertainty)
        executive_summary = self._build_executive_summary(
            plan, result, validation, uncertainty, hypotheses,
        )

        return InvestigationReport(
            query=plan.query or (plan.governing_equations[0].name if plan.governing_equations else ""),
            executive_summary=executive_summary,
            methodology=methodology,
            results=results,
            validation=validation,
            uncertainty=uncertainty,
            hypothesis_evaluation=hypotheses,
            limitations=limitations,
            provenance_id=provenance.record_id,
            traceability=provenance,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_methodology(
        self,
        plan: InvestigationPlan,
        provenance: ProvenanceEntry,
        has_result: bool,
    ) -> dict:
        """Build the methodology section of the report."""
        methodology: dict = {
            "domain": plan.domain.name,
            "mathematical_form": (
                plan.mathematical_form.name if plan.mathematical_form else "unknown"
            ),
            "governing_equations": [
                {"name": eq.name, "expression": eq.expression}
                for eq in plan.governing_equations
            ],
            "assumptions": [a.statement for a in plan.assumptions],
            "constraints": [c.description for c in plan.constraints],
            "boundary_conditions": [
                {"variable": bc.variable, "type": bc.type, "value": bc.value}
                for bc in plan.boundary_conditions
            ],
            "required_accuracy": plan.required_accuracy,
        }

        if has_result and provenance.solver_id:
            methodology["solver"] = {
                "id": provenance.solver_id,
                "config": provenance.solver_config,
            }

        if provenance.model_id:
            methodology["model"] = {
                "id": provenance.model_id,
                "version": provenance.model_version,
            }

        return methodology

    def _build_results(self, result: SimulationResult | None) -> dict:
        """Build the results section of the report."""
        if result is None:
            return {"status": "analytical", "detail": "Simulation was not required."}

        results: dict = {
            "status": "converged" if result.converged else "diverged",
            "solver_id": result.solver_id,
            "solver_method": result.solver_method,
            "iterations": result.iterations,
            "execution_time_seconds": result.execution_time,
            "error_estimate": result.error_estimate,
        }

        # Summarise each variable's data range.
        data_summary: dict[str, dict] = {}
        for var_name, values in result.data.items():
            numeric_values = [v for v in values if isinstance(v, (int, float))]
            if numeric_values:
                data_summary[var_name] = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "mean": sum(numeric_values) / len(numeric_values),
                    "count": len(numeric_values),
                }
            else:
                data_summary[var_name] = {"count": len(values), "type": "non-numeric"}

        results["data_summary"] = data_summary
        results["metadata"] = result.metadata

        return results

    def _identify_limitations(
        self,
        validation: ValidationReport,
        uncertainty: UncertaintyEstimate | None,
    ) -> list[str]:
        """Identify limitations from validation and uncertainty results."""
        limitations: list[str] = []

        if not validation.passed:
            limitations.append(
                f"Validation did not pass: {validation.summary[:200]}"
            )

        if uncertainty is not None:
            if uncertainty.overall_confidence < 0.5:
                limitations.append(
                    f"Overall confidence is low ({uncertainty.overall_confidence:.1%}). "
                    "Results should be interpreted with caution."
                )
            limitations.extend(uncertainty.recommendations)

        if not limitations:
            limitations.append("No significant limitations identified.")

        return limitations

    def _build_executive_summary(
        self,
        plan: InvestigationPlan,
        result: SimulationResult | None,
        validation: ValidationReport,
        uncertainty: UncertaintyEstimate | None,
        hypotheses: list[HypothesisResult] | None,
    ) -> str:
        """Generate a concise human-readable executive summary."""
        parts: list[str] = []

        # Domain and problem.
        domain_name = plan.domain.name.replace("_", " ").title()
        form_name = (
            plan.mathematical_form.name.replace("_", " ").title()
            if plan.mathematical_form
            else "Unknown"
        )
        parts.append(
            f"Investigation in {domain_name} with {form_name} governing equations."
        )

        # Result status.
        if result is None:
            parts.append("An analytical solution was used — no numerical simulation was required.")
        elif result.converged:
            parts.append(
                f"Simulation converged in {result.iterations} iterations "
                f"({result.execution_time:.3f} s)."
            )
        else:
            parts.append(
                "Simulation did not converge. Results may be unreliable."
            )

        # Validation.
        if validation.passed:
            parts.append("All validation checks passed.")
        else:
            failed = [c.name for c in validation.checks if not c.passed]
            parts.append(f"Validation issues: {', '.join(failed)}.")

        # Uncertainty.
        if uncertainty is not None:
            parts.append(
                f"Overall confidence: {uncertainty.overall_confidence:.0%}."
            )

        # Hypothesis evaluation.
        if hypotheses:
            supported = sum(1 for h in hypotheses if h.supported)
            parts.append(
                f"Hypothesis evaluation: {supported}/{len(hypotheses)} "
                f"hypotheses supported by the evidence."
            )

        return " ".join(parts)
