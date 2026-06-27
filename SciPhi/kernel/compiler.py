"""Problem Compiler — translates a scientific model into a computational problem.

The :class:`ProblemCompiler` is the critical translation layer between
the scientific description (a :class:`ScientificModel`) and the computational
description (a :class:`ComputationalProblem`). It introduces no new science —
it purely translates symbolic equations into a computable form, applies
discretisation strategies based on the mathematical form, and attaches
initial/boundary conditions from the investigation plan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from SciPhi.errors import CompilationError

if TYPE_CHECKING:
    from SciPhi.interfaces.model import (
        MathematicalForm,
        ScientificModel,
    )
    from SciPhi.interfaces.solver import ComputationalProblem
    from SciPhi.kernel.planner import InvestigationPlan


class ProblemCompiler:
    """Translates a :class:`ScientificModel` into a :class:`ComputationalProblem`.

    The compiler:

    - Converts symbolic governing equations into a dictionary-based
      representation suitable for solvers.
    - Selects a discretisation strategy based on the mathematical form
      and required accuracy.
    - Applies initial and boundary conditions from the investigation plan.
    - Sets solver tolerances from the plan's accuracy requirement.
    """

    # Mapping from accuracy level string to numerical tolerance.
    _ACCURACY_TOLERANCES: dict[str, float] = {
        "low": 1e-3,
        "medium": 1e-6,
        "high": 1e-9,
        "very high": 1e-12,
    }

    async def compile(
        self,
        model: ScientificModel,
        plan: InvestigationPlan,
    ) -> ComputationalProblem:
        """Compile a scientific model and plan into a computational problem.

        Args:
            model: The :class:`ScientificModel` selected for the investigation.
            plan: The :class:`InvestigationPlan` containing boundary
                conditions, accuracy requirements, and constraints.

        Returns:
            A fully populated :class:`ComputationalProblem` ready to be
            dispatched to a solver.

        Raises:
            CompilationError: If the model cannot be compiled (e.g. missing
                equations, incompatible mathematical forms).
        """
        # Validate the model and plan are compatible.
        self._validate_compatibility(model, plan)

        # Convert symbolic equations to a dictionary-based form.
        equations_dict = self._convert_equations(model)

        # Convert boundary conditions from the plan to the solver's dict format.
        boundary_conditions = self._convert_boundary_conditions(plan)

        # Determine tolerance from the required accuracy.
        tolerance = self._resolve_tolerance(plan.required_accuracy)

        # Build parameter ranges from model parameters.
        parameter_ranges = self._build_parameter_ranges(model)

        # Initial conditions: currently a stub — in the future these could be
        # extracted from the plan's boundary_conditions where location == "initial".
        initial_conditions: dict[str, float] = {}

        # Determine the discretisation strategy based on mathematical form.
        discretization = self._select_discretization(model.mathematical_form, tolerance)

        # Prepare the computational problem.
        from SciPhi.interfaces.solver import ComputationalProblem

        problem = ComputationalProblem(
            mathematical_form=model.mathematical_form,
            equations=equations_dict,
            initial_conditions=initial_conditions,
            boundary_conditions=boundary_conditions,
            parameter_ranges=parameter_ranges,
            tolerance=tolerance,
            discretization=discretization,
            constraints=[c.description for c in plan.constraints],
        )

        # Store the model identity in metadata for traceability.
        problem.mathematical_form = model.mathematical_form  # already set

        return problem

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_compatibility(
        self, model: ScientificModel, plan: InvestigationPlan,
    ) -> None:
        """Raise :exc:`CompilationError` if the model and plan are incompatible.

        If the plan specifies a mathematical form that differs from the
        model's declared form, the model is treated as authoritative — a
        warning is logged and the model's form is used.
        """
        import logging
        logger = logging.getLogger(__name__)

        if plan.mathematical_form is not None:
            if model.mathematical_form != plan.mathematical_form:
                logger.warning(
                    "Plan heuristic detected form '%s' but model '%s' declares '%s'. "
                    "Using model's declaration.",
                    plan.mathematical_form.name,
                    type(model).__name__,
                    model.mathematical_form.name,
                )

        if not model.equations:
            raise CompilationError(
                model_id=type(model).__name__,
                reason="Model has no governing equations defined.",
            )

    def _convert_equations(self, model: ScientificModel) -> list[dict]:
        """Convert symbolic :class:`Equation` objects to solver-friendly dicts."""
        equations: list[dict] = []
        for eq in model.equations:
            equations.append({
                "name": eq.name,
                "expression": eq.expression,
                "description": eq.description,
            })
        return equations

    def _convert_boundary_conditions(
        self, plan: InvestigationPlan,
    ) -> dict[str, dict]:
        """Convert plan boundary conditions to solver dict format."""
        bc_dict: dict[str, dict] = {}
        for bc in plan.boundary_conditions:
            bc_dict[bc.variable] = {
                "type": bc.type,
                "value": bc.value,
                "location": bc.location,
            }
        return bc_dict

    def _resolve_tolerance(self, accuracy: str) -> float:
        """Map an accuracy level string to a numerical tolerance."""
        return self._ACCURACY_TOLERANCES.get(accuracy.lower(), 1e-6)

    def _build_parameter_ranges(
        self, model: ScientificModel,
    ) -> dict[str, dict]:
        """Build default parameter ranges from model parameters."""
        ranges: dict[str, dict] = {}
        for param in model.parameters:
            # Default range: ±50 % around the default value
            default = param.default_value
            ranges[param.name] = {
                "default": default,
                "min": default * 0.5 if default != 0 else -1.0,
                "max": default * 1.5 if default != 0 else 1.0,
                "unit": param.unit,
            }
        return ranges

    def _select_discretization(
        self, form: MathematicalForm, tolerance: float,
    ) -> dict | None:
        """Choose a default discretisation strategy based on mathematical form.

        Args:
            form: The mathematical form of the governing equations.
            tolerance: The required solution tolerance.

        Returns:
            A dictionary describing the discretisation strategy, or ``None``
            if the form does not require discretisation (e.g. algebraic).
        """
        from SciPhi.interfaces.model import MathematicalForm as MF

        if form in (MF.ALGEBRAIC, MF.SYMBOLIC):
            return None  # No discretisation needed.

        if form == MF.ODE_INITIAL_VALUE:
            return {
                "method": "finite_difference",
                "scheme": "rk4",
                "step_size": tolerance ** 0.25,
            }

        if form == MF.ODE_BOUNDARY_VALUE:
            return {
                "method": "shooting",
                "scheme": "rk4",
                "tolerance": tolerance,
            }

        if form == MF.PDE:
            return {
                "method": "finite_difference",
                "scheme": "central_difference",
                "grid_points": 100,
                "tolerance": tolerance,
            }

        if form == MF.STOCHASTIC:
            return {
                "method": "monte_carlo",
                "samples": 10_000,
                "tolerance": tolerance,
            }

        if form == MF.OPTIMIZATION:
            return {
                "method": "gradient_descent",
                "learning_rate": 0.01,
                "max_iterations": 1000,
                "tolerance": tolerance,
            }

        # Default fallback.
        return {
            "method": "unknown",
            "tolerance": tolerance,
        }
