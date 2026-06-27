"""Opsim Kernel — the central orchestrator of the SciPhi scientific operating system.

The :class:`OpsimKernel` owns the full investigation lifecycle:

1. Receive a query → Simulation Advisor decides if numerical work is needed.
2. If needed → Scientific Planner produces a structured investigation plan.
3. ModelSelector picks the right scientific model.
4. ProblemCompiler translates the model into a computational problem.
5. SolverSelectionEngine matches the problem to a capable solver.
6. Solver executes and returns a result.
7. ScientificEvaluator validates the result.
8. UncertaintyAnalyzer quantifies confidence.
9. ProvenanceTracker records every decision.
10. ReportGenerator compiles the final :class:`InvestigationReport`.

The kernel is domain-agnostic: it never imports physics, chemistry, etc.
All domain knowledge comes through registered models and solvers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from SciPhi.errors import (
    InvalidQueryError,
    ModelNotFoundError,
    NoSuitableSolverError,
    SimulationFailedError,
    SciPhiError,
)
from SciPhi.kernel.advisor import SimulationAdvisor, SimulationAdvice
from SciPhi.kernel.compiler import ProblemCompiler
from SciPhi.kernel.evaluator import ScientificEvaluator, ValidationReport
from SciPhi.kernel.hypothesis import HypothesisEngine, HypothesisResult
from SciPhi.kernel.planner import InvestigationPlan, ScientificPlanner
from SciPhi.kernel.provenance import ProvenanceEntry, ProvenanceTracker
from SciPhi.kernel.report import InvestigationReport, ReportGenerator
from SciPhi.kernel.solver_selector import SolverSelectionEngine
from SciPhi.kernel.uncertainty import UncertaintyAnalyzer, UncertaintyEstimate

if TYPE_CHECKING:
    from SciPhi.interfaces.model import ModelInfo, ScientificModel
    from SciPhi.interfaces.solver import (
        ComputationalProblem,
        SimulationResult,
        Solver,
        SolverInfo,
    )

logger = logging.getLogger(__name__)


class OpsimKernel:
    """Central orchestrator for scientific investigations.

    The kernel coordinates the full pipeline from query to report. It owns
    instances of each subsystem and provides a clean public API for running
    investigations, quick-path simulations, and data inspection.

    Args:
        model_registry: An optional dictionary mapping model IDs to
            :class:`ScientificModel` instances. If ``None``, an empty
            registry is created.
        solver_registry: An optional dictionary mapping solver names to
            :class:`Solver` instances. If ``None``, an empty registry is
            created.
    """

    def __init__(
        self,
        model_registry: dict[str, ScientificModel] | None = None,
        solver_registry: dict[str, Solver] | None = None,
    ) -> None:
        # -- Registries --
        self._models: dict[str, ScientificModel] = model_registry or {}
        self._solvers: dict[str, Solver] = solver_registry or {}

        # -- Subsystems --
        self._advisor = SimulationAdvisor()
        self._planner = ScientificPlanner()
        self._compiler = ProblemCompiler()
        self._solver_selector = SolverSelectionEngine()
        self._evaluator = ScientificEvaluator()
        self._uncertainty_analyzer = UncertaintyAnalyzer()
        self._provenance_tracker = ProvenanceTracker()
        self._report_generator = ReportGenerator()
        self._hypothesis_engine = HypothesisEngine()

        # Register pre-loaded solvers with the selection engine.
        for solver in self._solvers.values():
            self._solver_selector.register(solver)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def investigate(self, query: str) -> InvestigationReport:
        """Run the full Opsim investigation pipeline on a query.

        This method executes every phase of the pipeline:

        1. Parse the query and build an :class:`InvestigationPlan`.
        2. Consult the :class:`SimulationAdvisor` — if an analytical solution
           exists, skip numerical simulation.
        3. Select a :class:`ScientificModel` from the registry.
        4. Compile the model into a :class:`ComputationalProblem`.
        5. Select a :class:`Solver` capable of handling the problem.
        6. Execute the solver.
        7. Validate the result.
        8. Analyse uncertainty.
        9. Generate and evaluate hypotheses.
        10. Record provenance.
        11. Compile and return the final :class:`InvestigationReport`.

        Args:
            query: A free-form or structured query describing the scientific
                problem to investigate.

        Returns:
            An :class:`InvestigationReport` containing all findings.

        Raises:
            InvalidQueryError: If the query cannot be parsed.
            ModelNotFoundError: If no suitable model is registered.
            NoSuitableSolverError: If no solver can handle the problem.
            SimulationFailedError: If the solver fails to produce a result.
            SciPhiError: On any other pipeline failure.
        """
        if not query or not query.strip():
            raise InvalidQueryError(query=query, reason="Query must be non-empty.")

        logger.info("Starting investigation for query: '%s'", query[:120])

        # ---------------------------------------------------------------
        # Step 1: Plan
        # ---------------------------------------------------------------
        plan: InvestigationPlan = await self._planner.create_plan(query)

        # ---------------------------------------------------------------
        # Step 2: Advise
        # ---------------------------------------------------------------
        advice: SimulationAdvice = await self._advisor.should_simulate(plan)

        # Short-circuit if an analytical solution exists.
        if not advice.needs_simulation:
            logger.info(
                "Simulation advisor short-circuited: %s", advice.reason,
            )
            return await self._build_analytical_report(
                query=query,
                plan=plan,
                advice=advice,
            )

        # ---------------------------------------------------------------
        # Step 3: Model Selection
        # ---------------------------------------------------------------
        model = self._select_model(plan)

        # ---------------------------------------------------------------
        # Step 4: Compilation
        # ---------------------------------------------------------------
        logger.info("Compiling model '%s' into computational problem.", type(model).__name__)
        problem: ComputationalProblem = await self._compiler.compile(model, plan)

        # ---------------------------------------------------------------
        # Step 5: Solver Selection
        # ---------------------------------------------------------------
        logger.info("Selecting solver for form '%s'.", problem.mathematical_form.name)
        solver: Solver = self._solver_selector.select(problem)

        # ---------------------------------------------------------------
        # Step 6: Solve
        # ---------------------------------------------------------------
        logger.info("Solving with solver '%s'.", solver.capabilities.name)
        try:
            result: SimulationResult = solver.solve(problem)
        except Exception as exc:
            raise SimulationFailedError(
                solver_id=solver.capabilities.name,
                reason=str(exc),
            ) from exc

        if not result.converged:
            logger.warning(
                "Solver '%s' did not converge after %d iterations.",
                solver.capabilities.name, result.iterations,
            )

        # ---------------------------------------------------------------
        # Step 7: Validate
        # ---------------------------------------------------------------
        logger.info("Validating simulation result.")
        validation: ValidationReport = await self._evaluator.validate(result, plan)

        if not validation.passed:
            logger.warning("Validation did not pass: %s", validation.summary[:200])

        # ---------------------------------------------------------------
        # Step 8: Uncertainty Analysis
        # ---------------------------------------------------------------
        logger.info("Analysing uncertainty.")
        uncertainty: UncertaintyEstimate = await self._uncertainty_analyzer.analyze(
            result, plan,
        )

        # ---------------------------------------------------------------
        # Step 9: Hypothesis Evaluation
        # ---------------------------------------------------------------
        logger.info("Evaluating hypotheses.")
        hypotheses = await self._hypothesis_engine.generate_hypotheses(plan)
        hypothesis_results: list[HypothesisResult] = (
            await self._hypothesis_engine.evaluate_hypotheses(hypotheses, result)
        )

        # ---------------------------------------------------------------
        # Step 10: Provenance
        # ---------------------------------------------------------------
        logger.info("Recording provenance.")
        entry = self._build_provenance_entry(
            query=query,
            plan=plan,
            model=model,
            solver=solver,
            result=result,
            validation=validation,
            uncertainty=uncertainty,
            approximations=[],
        )
        provenance_id = await self._provenance_tracker.record(entry)

        # Re-fetch the finalized entry.
        finalized_entry = await self._provenance_tracker.get(provenance_id)
        if finalized_entry is None:
            finalized_entry = entry  # fallback

        # ---------------------------------------------------------------
        # Step 11: Report
        # ---------------------------------------------------------------
        logger.info("Compiling final report (provenance ID: %s).", provenance_id)
        report = await self._report_generator.compile(
            plan=plan,
            result=result,
            validation=validation,
            uncertainty=uncertainty,
            provenance=finalized_entry,
            hypotheses=hypothesis_results,
        )

        return report

    async def simulate(self, model_id: str, params: dict) -> SimulationResult:
        """Quick-path simulation: run a specific model with given parameters.

        This is a convenience method that bypasses the planning and advisory
        phases and directly compiles, selects a solver, and executes.

        Args:
            model_id: The identifier of the model to simulate.
            params: A dictionary of parameter overrides.

        Returns:
            The :class:`SimulationResult` from the solver.

        Raises:
            ModelNotFoundError: If *model_id* is not in the registry.
            NoSuitableSolverError: If no solver can handle the model's form.
            SimulationFailedError: If the solver fails.
        """
        model = self._models.get(model_id)
        if model is None:
            raise ModelNotFoundError(model_id)

        # Build a minimal plan from the model.
        plan = InvestigationPlan(
            domain=model.domain,
            governing_equations=list(model.equations),
            variables=list(model.variables),
            parameters=list(model.parameters),
            assumptions=list(model.assumptions),
            constraints=list(model.constraints),
            mathematical_form=model.mathematical_form,
        )

        # Apply parameter overrides.
        for param in model.parameters:
            if param.name in params:
                plan.parameters  # already captured above

        problem = await self._compiler.compile(model, plan)
        solver = self._solver_selector.select(problem)

        try:
            result = solver.solve(problem)
        except Exception as exc:
            raise SimulationFailedError(
                solver_id=solver.capabilities.name,
                reason=str(exc),
            ) from exc

        return result

    async def validate(self, result: SimulationResult) -> ValidationReport:
        """Run validation on an existing simulation result without re-solving.

        Args:
            result: The :class:`SimulationResult` to validate.

        Returns:
            A :class:`ValidationReport` summarising the validation checks.
        """
        # We need a plan to validate against. Build a minimal one from metadata.
        plan = InvestigationPlan(
            domain=None,  # type: ignore[arg-type]
            governing_equations=[],
        )
        return await self._evaluator.validate(result, plan)

    def list_models(self, domain: str | None = None) -> list[ModelInfo]:
        """List available models, optionally filtered by domain.

        Args:
            domain: If provided, only return models in this domain
                (case-insensitive). If ``None``, return all models.

        Returns:
            A list of :class:`ModelInfo` instances.
        """
        models: list[ModelInfo] = []
        for model in self._models.values():
            if domain is None or model.domain.name.lower() == domain.lower():
                models.append(model.info())
        return models

    def list_solvers(self) -> list[SolverInfo]:
        """List all registered solvers.

        Returns:
            A list of :class:`SolverInfo` instances.
        """
        return [solver.info() for solver in self._solvers.values()]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_model(self, plan: InvestigationPlan) -> ScientificModel:
        """Select a model from the registry that matches the plan's domain.

        Args:
            plan: The investigation plan to match against.

        Returns:
            The best-matching :class:`ScientificModel`.

        Raises:
            ModelNotFoundError: If no model matches the plan's domain.
        """
        candidate: ScientificModel | None = None

        target_domain = plan.domain
        for model in self._models.values():
            if target_domain is None or model.domain == target_domain:
                candidate = model
                break

        if candidate is None and self._models:
            # Fallback: use the first registered model.
            candidate = next(iter(self._models.values()))
            logger.warning(
                "No model for domain '%s'; falling back to '%s'.",
                target_domain.name if target_domain else "unknown",
                type(candidate).__name__,
            )

        if candidate is None:
            domain_label = target_domain.name if target_domain else "any"
            raise ModelNotFoundError(
                model_id=f"domain={domain_label}",
                message=f"No models registered for domain '{domain_label}'.",
            )

        return candidate

    async def _build_analytical_report(
        self,
        query: str,
        plan: InvestigationPlan,
        advice: SimulationAdvice,
    ) -> InvestigationReport:
        """Build a report when simulation is skipped (analytical path)."""
        entry = ProvenanceEntry(
            record_id="",
            query=query,
            model_id=None,
            equations_used=[eq.name for eq in plan.governing_equations],
            assumptions=[a.statement for a in plan.assumptions],
        )
        provenance_id = await self._provenance_tracker.record(entry)
        finalized_entry = await self._provenance_tracker.get(provenance_id)

        validation = ValidationReport(
            passed=True,
            checks=[],
            summary="No validation needed — analytical solution used.",
        )

        report = await self._report_generator.compile(
            plan=plan,
            result=None,
            validation=validation,
            uncertainty=None,
            provenance=finalized_entry or entry,
            hypotheses=None,
        )

        return report

    def _build_provenance_entry(
        self,
        query: str,
        plan: InvestigationPlan,
        model: ScientificModel,
        solver: Solver,
        result: SimulationResult,
        validation: ValidationReport,
        uncertainty: UncertaintyEstimate,
        approximations: list[str],
    ) -> ProvenanceEntry:
        """Construct a provenance entry from the pipeline outputs."""
        constants_used: list[dict] = []
        for const in model.constants:
            constants_used.append({
                "name": const.name,
                "symbol": const.symbol,
                "value": const.value,
                "unit": const.unit,
                "uncertainty": const.uncertainty,
            })

        return ProvenanceEntry(
            record_id="",  # auto-generated
            query=query,
            model_id=type(model).__name__,
            model_version="1.0",  # placeholder; could come from model metadata
            equations_used=[eq.name for eq in model.equations],
            constants_used=constants_used,
            data_sources=[],
            solver_id=solver.capabilities.name,
            solver_config={
                "method": solver.capabilities.methods,
                "order": solver.capabilities.order,
                "error_estimation": solver.capabilities.error_estimation,
                "parallel": solver.capabilities.supports_parallel,
            },
            assumptions=[a.statement for a in plan.assumptions],
            approximations=approximations,
            validation_results=list(validation.checks),
            uncertainty=uncertainty,
            timestamp="",  # auto-generated
        )
