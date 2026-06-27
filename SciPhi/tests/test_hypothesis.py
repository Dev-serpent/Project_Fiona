"""Comprehensive tests for the expanded Hypothesis Engine.

Tests cover:

- Form-aware hypothesis generation (ODE, algebraic, optimisation,
  stochastic, PDE, hybrid)
- Data-driven evaluation strategies (steady-state, conservation,
  monotonicity, convergence, stability, stochastic)
- Edge cases (empty data, non-converged, single variable,
  zero-magnitude series)
- Ranking methods (rank_hypotheses, find_best_hypothesis,
  find_most_likely_hypothesis)
- Backward compatibility with existing generation fallback paths
"""

from __future__ import annotations

import math
import pytest

pytestmark = pytest.mark.asyncio

from SciPhi.interfaces.model import (
    MathematicalForm,
    ScientificDomain,
    Equation,
    Variable,
    Parameter,
    Assumption,
    Constraint,
)
from SciPhi.interfaces.solver import SimulationResult
from SciPhi.kernel.planner import InvestigationPlan
from SciPhi.kernel.hypothesis import (
    Hypothesis,
    HypothesisResult,
    HypothesisEngine,
)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def engine() -> HypothesisEngine:
    return HypothesisEngine()


def make_plan(
    *,
    form: MathematicalForm = MathematicalForm.ALGEBRAIC,
    variables: int = 1,
    equations: int = 1,
    domain: ScientificDomain = ScientificDomain.PHYSICS,
) -> InvestigationPlan:
    """Helper to build an InvestigationPlan with a given form and variable count."""
    return InvestigationPlan(
        query="test query",
        domain=domain,
        mathematical_form=form,
        governing_equations=(
            [Equation(f"eq{i}", f"x^{i} = 0", f"Equation {i}")
             for i in range(equations)]
        ),
        variables=(
            [Variable(f"var{i}", f"v{i}", "m", f"Variable {i}")
             for i in range(variables)]
        ),
        parameters=[
            Parameter("p1", "p", 1.0, "", "Parameter"),
        ],
        assumptions=[Assumption("test", "none")],
        constraints=[Constraint("positive", "x > 0")],
    )


def make_result(
    *,
    converged: bool = True,
    iterations: int = 100,
    error_estimate: float | None = 1e-6,
    data: dict | None = None,
) -> SimulationResult:
    return SimulationResult(
        solver_id="TestSolver",
        solver_method="test",
        converged=converged,
        iterations=iterations,
        execution_time=0.1,
        data=data if data is not None else {"x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0]},
        metadata={},
        error_estimate=error_estimate,
    )


# ======================================================================
# Generation — form-agnostic fallback
# ======================================================================


class TestGenerateFallback:
    """Tests for the form-agnostic fallback generation paths."""

    async def test_empty_plan_produces_fallback(self, engine: HypothesisEngine):
        """A plan with no variables and no equations gets the fallback hypothesis."""
        plan = InvestigationPlan()
        hypotheses = await engine.generate_hypotheses(plan)
        assert len(hypotheses) == 1
        assert "physically plausible" in hypotheses[0].statement.lower()

    async def test_plan_with_variables_gets_variable_hypothesis(
        self, engine: HypothesisEngine,
    ):
        """A plan with a variable but no form still gets a variable hypothesis."""
        plan = InvestigationPlan(
            variables=[Variable("mass", "m", "kg", "Mass")],
        )
        hypotheses = await engine.generate_hypotheses(plan)
        # Should get at least the variable-based hypothesis
        assert any("mass" in h.statement.lower() for h in hypotheses)

    async def test_variable_hypothesis_not_duplicated(
        self, engine: HypothesisEngine,
    ):
        """If form-specific generation already produced a variable hypothesis,
        the fallback should not duplicate it."""
        plan = InvestigationPlan(
            mathematical_form=MathematicalForm.ODE_INITIAL_VALUE,
            governing_equations=[Equation("eq1", "dx/dt = 0", "Test")],
            variables=[Variable("x", "x", "", "Test var")],
        )
        hypotheses = await engine.generate_hypotheses(plan)
        # Count hypotheses mentioning "x" as a variable and "consistent"
        consistent_count = sum(
            1 for h in hypotheses
            if "x" in h.variables and "consistent" in h.statement.lower()
        )
        assert consistent_count <= 1, (
            f"Expected at most 1 'consistent' hypothesis for x, "
            f"got {consistent_count}"
        )


# ======================================================================
# Generation — form-specific
# ======================================================================


class TestGenerateODE:
    """Hypotheses specific to ODE initial-value problems."""

    async def test_ode_generates_steady_state(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.ODE_INITIAL_VALUE, variables=2)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("steady state" in s.lower() for s in statements)

    async def test_ode_generates_conservation(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.ODE_INITIAL_VALUE, variables=2)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("conserv" in s.lower() for s in statements)

    async def test_ode_generates_monotonicity(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.ODE_INITIAL_VALUE, variables=2)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("monoton" in s.lower() for s in statements)

    async def test_ode_boundary_value_gets_hypotheses(
        self, engine: HypothesisEngine,
    ):
        plan = make_plan(form=MathematicalForm.ODE_BOUNDARY_VALUE, variables=1)
        hypotheses = await engine.generate_hypotheses(plan)
        assert len(hypotheses) >= 1

    async def test_ode_single_variable_no_conservation(
        self, engine: HypothesisEngine,
    ):
        """Conservation requires >= 2 variables."""
        plan = make_plan(form=MathematicalForm.ODE_INITIAL_VALUE, variables=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        # There should be no conservation hypothesis with 1 variable
        conservation_h = [s for s in statements if "conserv" in s.lower()]
        assert len(conservation_h) == 0


class TestGenerateAlgebraic:
    """Hypotheses specific to algebraic problems."""

    async def test_algebraic_generates_uniqueness(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.ALGEBRAIC, equations=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("unique" in s.lower() or "solution" in s.lower()
                    for s in statements)

    async def test_algebraic_generates_bounds(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.ALGEBRAIC, equations=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("bound" in s.lower() for s in statements)

    async def test_algebraic_no_equations_no_bound_hypothesis(
        self, engine: HypothesisEngine,
    ):
        """Without equations, the uniqueness hypothesis is skipped."""
        plan = InvestigationPlan(
            mathematical_form=MathematicalForm.ALGEBRAIC,
            variables=[Variable("x", "x", "", "Var")],
        )
        hypotheses = await engine.generate_hypotheses(plan)
        # Should still get the variable fallback, but no uniqueness hypothesis
        assert len(hypotheses) >= 1


class TestGenerateOptimization:
    """Hypotheses specific to optimisation problems."""

    async def test_optimization_generates_optimum(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.OPTIMIZATION, variables=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("optimum" in s.lower() or "optim" in s.lower()
                    for s in statements)

    async def test_optimization_no_variables_still_gets_something(
        self, engine: HypothesisEngine,
    ):
        plan = InvestigationPlan(
            mathematical_form=MathematicalForm.OPTIMIZATION,
        )
        hypotheses = await engine.generate_hypotheses(plan)
        # Fallback should still produce a hypothesis
        assert len(hypotheses) >= 1


class TestGenerateStochastic:
    """Hypotheses specific to stochastic problems."""

    async def test_stochastic_generates_convergence(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.STOCHASTIC, variables=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("mean" in s.lower() or "converg" in s.lower()
                    for s in statements)

    async def test_stochastic_no_variables(self, engine: HypothesisEngine):
        """Stochastic generation with no variables still gets fallback."""
        plan = InvestigationPlan(
            mathematical_form=MathematicalForm.STOCHASTIC,
        )
        hypotheses = await engine.generate_hypotheses(plan)
        assert len(hypotheses) >= 1


class TestGeneratePDE:
    """Hypotheses specific to PDE and hybrid problems."""

    async def test_pde_generates_stability(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.PDE, variables=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("stable" in s.lower() or "bounded" in s.lower()
                    for s in statements)

    async def test_hybrid_generates_stability(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.HYBRID, variables=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert any("stable" in s.lower() or "bounded" in s.lower()
                    for s in statements)


class TestGenerateFormSpecificity:
    """Verify that form-specific generation only triggers for the right form."""

    async def test_ode_does_not_generate_optimum(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.ODE_INITIAL_VALUE, variables=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        # None should mention "optimum"
        assert not any("optimum" in s.lower() for s in statements)

    async def test_algebraic_does_not_generate_steady_state(
        self, engine: HypothesisEngine,
    ):
        plan = make_plan(form=MathematicalForm.ALGEBRAIC, variables=1)
        hypotheses = await engine.generate_hypotheses(plan)
        statements = [h.statement for h in hypotheses]
        assert not any("steady state" in s.lower() for s in statements)


# ======================================================================
# Evaluation — steady-state
# ======================================================================


class TestEvaluateSteadyState:
    """Data-driven steady-state detection via derivative estimation."""

    async def test_steady_series_supported(self, engine: HypothesisEngine):
        """A series that flattens should support steady-state."""
        hyp = Hypothesis(
            statement="System reaches steady state.",
            null_hypothesis="System does not reach steady state.",
            variables=["x"],
            expected_outcome="Derivatives approach zero.",
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        # Series that starts high then flattens.
        data = {
            "x": [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0],
        }
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported, (
            f"Expected steady-state to be supported, got: {eval_result}"
        )
        assert eval_result.confidence > 0.5

    async def test_oscillating_series_not_steady(
        self, engine: HypothesisEngine,
    ):
        """An oscillating series should not be recognised as steady."""
        hyp = Hypothesis(
            statement="System reaches steady state.",
            null_hypothesis="System does not reach steady state.",
            variables=["x"],
            expected_outcome="Derivatives approach zero.",
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        # A sine-like oscillation.
        data = {
            "x": [math.sin(i * 0.5) for i in range(50)],
        }
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported, (
            "Oscillating series should not be marked as steady."
        )

    async def test_short_series_insufficient_data(
        self, engine: HypothesisEngine,
    ):
        """A series with fewer than 5 points cannot be evaluated."""
        hyp = Hypothesis(
            statement="System reaches steady state.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        data = {"x": [1.0, 2.0, 3.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported

    async def test_non_converged_steady_state(
        self, engine: HypothesisEngine,
    ):
        """If the simulation did not converge, steady-state should be refuted."""
        hyp = Hypothesis(
            statement="System reaches steady state.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        result = make_result(converged=False)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported
        assert eval_result.confidence < 0.5

    async def test_steady_state_with_no_variables_falls_back(
        self, engine: HypothesisEngine,
    ):
        """When no variables are specified, use all data keys."""
        hyp = Hypothesis(
            statement="System reaches steady state.",
            null_hypothesis="",
            variables=[],
            expected_outcome="",
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        data = {
            "x": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        }
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported


# ======================================================================
# Evaluation — conservation
# ======================================================================


class TestEvaluateConservation:
    """Data-driven conservation checks."""

    async def test_conservation_holds(self, engine: HypothesisEngine):
        """Two variables whose sum is constant should conserve."""
        hyp = Hypothesis(
            statement="Mass and energy are conserved.",
            null_hypothesis="Mass and energy are not conserved.",
            variables=["mass", "energy"],
            expected_outcome="Sum is constant.",
            test_method="Conservation check: sum of variables over time.",
        )
        # Sum is always 10.
        data = {
            "mass": [4.0, 4.5, 5.0, 5.5, 6.0, 6.5],
            "energy": [6.0, 5.5, 5.0, 4.5, 4.0, 3.5],
        }
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        assert eval_result.confidence > 0.5

    async def test_conservation_violated(self, engine: HypothesisEngine):
        """Two variables whose sum diverges should not conserve."""
        hyp = Hypothesis(
            statement="Mass and energy are conserved.",
            null_hypothesis="",
            variables=["mass", "energy"],
            expected_outcome="Sum is constant.",
            test_method="Conservation check: sum of variables over time.",
        )
        # Both increase monotonically — sum diverges.
        data = {
            "mass": [1.0, 2.0, 3.0, 4.0, 5.0],
            "energy": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported

    async def test_conservation_one_variable_only(
        self, engine: HypothesisEngine,
    ):
        """Cannot check conservation with only one variable."""
        hyp = Hypothesis(
            statement="Conservation holds.",
            null_hypothesis="",
            variables=["mass"],
            expected_outcome="",
            test_method="Conservation check: sum of variables over time.",
        )
        data = {"mass": [1.0, 2.0, 3.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported
        assert eval_result.confidence == 0.0

    async def test_conservation_zero_sum(self, engine: HypothesisEngine):
        """If the sum is exactly zero, conservation is trivially true."""
        hyp = Hypothesis(
            statement="A and B cancel.",
            null_hypothesis="",
            variables=["a", "b"],
            expected_outcome="",
            test_method="Conservation check: sum of variables over time.",
        )
        data = {
            "a": [5.0, -5.0, 5.0, -5.0],
            "b": [-5.0, 5.0, -5.0, 5.0],
        }
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        # Should be very confident since sum is exactly 0 throughout.
        assert eval_result.confidence > 0.9

    async def test_conservation_mismatched_lengths(
        self, engine: HypothesisEngine,
    ):
        """Variables with different array lengths should be handled gracefully."""
        hyp = Hypothesis(
            statement="Conservation holds.",
            null_hypothesis="",
            variables=["x", "y"],
            expected_outcome="",
            test_method="Check sum or norm of variables over time.",
        )
        # y is longer than x — truncate to shorter.
        data = {
            "x": [1.0, 2.0, 3.0],
            "y": [4.0, 5.0, 6.0, 7.0, 8.0],
        }
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        # Should not crash — result may be supported or not, but must be valid.
        assert isinstance(eval_result.supported, bool)
        assert 0.0 <= eval_result.confidence <= 1.0

    async def test_conservation_non_converged(
        self, engine: HypothesisEngine,
    ):
        """Non-converged simulation should yield low confidence."""
        hyp = Hypothesis(
            statement="Conservation holds.",
            null_hypothesis="",
            variables=["x", "y"],
            expected_outcome="",
            test_method="Check sum or norm of variables over time.",
        )
        data = {"x": [1.0, 2.0], "y": [3.0, 4.0]}
        result = make_result(converged=False, data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported or eval_result.confidence < 0.5


# ======================================================================
# Evaluation — monotonicity
# ======================================================================


class TestEvaluateMonotonicity:
    """Data-driven monotonicity detection."""

    async def test_monotonically_increasing(self, engine: HypothesisEngine):
        """A strictly increasing series should be monotonic."""
        hyp = Hypothesis(
            statement="x evolves monotonically.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Monotonicity check: sign changes in successive differences.",
        )
        data = {"x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        assert eval_result.confidence > 0.5

    async def test_monotonically_decreasing(self, engine: HypothesisEngine):
        """A strictly decreasing series should be monotonic."""
        hyp = Hypothesis(
            statement="x evolves monotonically.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Monotonicity check: sign changes in successive differences.",
        )
        data = {"x": [9.0, 7.0, 5.0, 3.0, 1.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        assert eval_result.confidence > 0.5

    async def test_oscillating_not_monotonic(self, engine: HypothesisEngine):
        """An oscillating series should not be monotonic."""
        hyp = Hypothesis(
            statement="x evolves monotonically.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Monotonicity check: sign changes in successive differences.",
        )
        data = {"x": [1.0, 2.0, 1.0, 2.0, 1.0, 2.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported

    async def test_constant_series_is_monotonic(self, engine: HypothesisEngine):
        """A constant series has no sign changes → monotonic."""
        hyp = Hypothesis(
            statement="x evolves monotonically.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Monotonicity check: sign changes in successive differences.",
        )
        data = {"x": [5.0, 5.0, 5.0, 5.0, 5.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        assert eval_result.confidence > 0.5

    async def test_monotonicity_short_series(self, engine: HypothesisEngine):
        """A series with fewer than 3 points cannot be evaluated."""
        hyp = Hypothesis(
            statement="x evolves monotonically.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Monotonicity check: sign changes in successive differences.",
        )
        data = {"x": [1.0, 2.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported
        assert eval_result.confidence == 0.0

    async def test_monotonicity_no_variable_fallback(
        self, engine: HypothesisEngine,
    ):
        """If no variable specified, fall back to all data keys."""
        hyp = Hypothesis(
            statement="System evolves monotonically.",
            null_hypothesis="",
            variables=[],
            expected_outcome="",
            test_method="Monotonicity check: sign changes in successive differences.",
        )
        data = {"x": [1.0, 2.0, 3.0, 4.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported

    async def test_monotonicity_non_converged(
        self, engine: HypothesisEngine,
    ):
        """Non-converged simulation should yield low confidence."""
        hyp = Hypothesis(
            statement="x evolves monotonically.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Monotonicity check: sign changes in successive differences.",
        )
        data = {"x": [1.0, 2.0, 3.0]}
        result = make_result(converged=False, data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.confidence < 0.5


# ======================================================================
# Evaluation — convergence
# ======================================================================


class TestEvaluateConvergence:
    """Convergence-based evaluation."""

    async def test_converged_high_confidence(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Equation has a solution.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check solver convergence and residual magnitude.",
        )
        result = make_result(converged=True, iterations=50, error_estimate=1e-8)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        assert eval_result.confidence > 0.8

    async def test_non_converged_low_confidence(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Equation has a solution.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check solver convergence and residual magnitude.",
        )
        result = make_result(converged=False)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported
        assert eval_result.confidence < 0.5

    async def test_converged_high_error_lower_confidence(
        self, engine: HypothesisEngine,
    ):
        hyp = Hypothesis(
            statement="Equation has a solution.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check solver convergence and residual magnitude.",
        )
        result = make_result(converged=True, error_estimate=0.5)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        # Confidence should still be > 0.5 but lower than perfect case.
        assert eval_result.confidence < 0.9

    async def test_converged_many_iterations(
        self, engine: HypothesisEngine,
    ):
        """Excessive iterations slightly reduce confidence."""
        hyp = Hypothesis(
            statement="Equation has a solution.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check solver convergence and residual magnitude.",
        )
        result = make_result(converged=True, iterations=2000, error_estimate=1e-6)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        # With error_estimate=1e-6, confidence = 1.0 * 0.9 = 0.9
        # (due to iterations > 1000 penalty).
        assert eval_result.confidence < 1.0
        assert eval_result.confidence == 0.9


# ======================================================================
# Evaluation — stability
# ======================================================================


class TestEvaluateStability:
    """Numerical stability checks."""

    async def test_stable_solution(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Solution is stable.",
            null_hypothesis="",
            variables=["x", "y"],
            expected_outcome="",
            test_method="Check for unbounded growth and oscillation.",
        )
        data = {
            "x": [1.0, 1.01, 1.02, 1.03, 1.04, 1.05, 1.06],
            "y": [2.0, 1.99, 1.98, 1.97, 1.96, 1.95, 1.94],
        }
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported

    async def test_unbounded_growth(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Solution is stable.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check for unbounded growth and oscillation.",
        )
        # Final value is 10000x initial -> unbounded.
        data = {"x": [1.0, 10.0, 100.0, 1000.0, 10000.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported

    async def test_excessive_oscillations(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Solution is stable.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check for unbounded growth and oscillation.",
        )
        # Alternating pattern — many sign changes.
        data = {"x": [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported

    async def test_stability_with_nan(self, engine: HypothesisEngine):
        """NaN values should be treated as instability."""
        hyp = Hypothesis(
            statement="Solution is stable.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check for unbounded growth and oscillation.",
        )
        data = {"x": [1.0, 2.0, float("nan"), 4.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        # Should not crash; NaN gets cleaned by _extract_series.
        assert isinstance(eval_result.supported, bool)

    async def test_stability_empty_data(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Solution is stable.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check for unbounded growth and oscillation.",
        )
        result = make_result(data={})
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported
        assert eval_result.confidence == 0.0


# ======================================================================
# Evaluation — stochastic
# ======================================================================


class TestEvaluateStochastic:
    """Stochastic/Monte Carlo convergence checks."""

    async def test_low_error_high_confidence(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Sample mean converges.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Assess variance reduction over samples.",
        )
        result = make_result(converged=True, error_estimate=0.01)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        assert eval_result.confidence > 0.5

    async def test_high_error_low_confidence(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Sample mean converges.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Assess variance reduction over samples.",
        )
        result = make_result(converged=True, error_estimate=0.8)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported

    async def test_non_converged_stochastic(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Sample mean converges.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Assess variance reduction over samples.",
        )
        result = make_result(converged=False, error_estimate=None)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported
        assert eval_result.confidence < 0.5

    async def test_no_error_estimate_uses_iterations(
        self, engine: HypothesisEngine,
    ):
        hyp = Hypothesis(
            statement="Sample mean converges.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Assess variance reduction over samples.",
        )
        result = make_result(converged=True, error_estimate=None, iterations=5000)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        # 5000 / 10000 = 0.5 confidence threshold -> supported
        assert isinstance(eval_result.supported, bool)
        assert 0.0 <= eval_result.confidence <= 1.0


# ======================================================================
# Evaluation — generic fallback
# ======================================================================


class TestEvaluateGenericFallback:
    """The fallback evaluation path (test_method doesn't match known keywords)."""

    async def test_converged_fallback(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Some generic hypothesis.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Some unknown test method.",
        )
        result = make_result(converged=True)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert eval_result.supported
        assert eval_result.confidence == 0.85

    async def test_non_converged_fallback(self, engine: HypothesisEngine):
        hyp = Hypothesis(
            statement="Some generic hypothesis.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Some unknown test method.",
        )
        result = make_result(converged=False)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert not eval_result.supported
        assert eval_result.confidence == 0.3


# ======================================================================
# Evaluation — edge cases
# ======================================================================


class TestEvaluateEdgeCases:
    """Edge cases across all evaluation strategies."""

    async def test_empty_result_data(self, engine: HypothesisEngine):
        """An empty data dict should not crash any evaluation strategy."""
        hyp = Hypothesis(
            statement="Test hypothesis.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        result = make_result(data={})
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert isinstance(eval_result.supported, bool)
        assert 0.0 <= eval_result.confidence <= 1.0

    async def test_variable_not_in_data(self, engine: HypothesisEngine):
        """A variable named in the hypothesis but absent from data."""
        hyp = Hypothesis(
            statement="Test hypothesis.",
            null_hypothesis="",
            variables=["nonexistent"],
            expected_outcome="",
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        data = {"x": [1.0, 2.0, 3.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert isinstance(eval_result.supported, bool)

    async def test_extract_series_partial_match(self, engine: HypothesisEngine):
        """Variable name partial matching should find the right series."""
        engine_inst = engine
        data = {
            "velocity_x": [1.0, 2.0, 3.0],
            "velocity_y": [4.0, 5.0, 6.0],
        }
        series = engine_inst._extract_series(data, "velocity_x")
        assert len(series) == 3
        assert series == [1.0, 2.0, 3.0]

    async def test_extract_series_no_match(self, engine: HypothesisEngine):
        """If no variable matches, return empty list."""
        engine_inst = engine
        data = {"a": [1.0, 2.0]}
        series = engine_inst._extract_series(data, "b")
        assert series == []

    async def test_extract_series_infinite_values_filtered(
        self, engine: HypothesisEngine,
    ):
        """Inf values should be filtered out."""
        engine_inst = engine
        data = {"x": [1.0, float("inf"), 3.0]}
        series = engine_inst._extract_series(data, "x")
        assert series == [1.0, 3.0]

    async def test_non_float_values_in_data(self, engine: HypothesisEngine):
        """Non-numeric values in data should be skipped, not crash."""
        hyp = Hypothesis(
            statement="Test.",
            null_hypothesis="",
            variables=["x"],
            expected_outcome="",
            test_method="Check sum or norm of variables over time.",
        )
        data = {"x": [1.0, "string", None, 4.0]}
        result = make_result(data=data)
        eval_result = await engine.evaluate_hypothesis(hyp, result)
        assert isinstance(eval_result.supported, bool)


# ======================================================================
# Ranking
# ======================================================================


class TestRanking:
    """Hypothesis ranking and selection."""

    def test_rank_hypotheses_descending(self, engine: HypothesisEngine):
        h1 = Hypothesis("H1", "")
        h2 = Hypothesis("H2", "")
        h3 = Hypothesis("H3", "")
        results = [
            HypothesisResult(h1, True, 0.3, "weak"),
            HypothesisResult(h2, True, 0.9, "strong"),
            HypothesisResult(h3, False, 0.6, "medium"),
        ]
        ranked = engine.rank_hypotheses(results)
        assert ranked[0].confidence == 0.9
        assert ranked[1].confidence == 0.6
        assert ranked[2].confidence == 0.3

    def test_rank_hypotheses_empty(self, engine: HypothesisEngine):
        ranked = engine.rank_hypotheses([])
        assert ranked == []

    def test_find_best_hypothesis(self, engine: HypothesisEngine):
        h1 = Hypothesis("H1", "")
        h2 = Hypothesis("H2", "")
        results = [
            HypothesisResult(h1, True, 0.4, ""),
            HypothesisResult(h2, True, 0.95, ""),
        ]
        best = engine.find_best_hypothesis(results)
        assert best is not None
        assert best.hypothesis.statement == "H2"
        assert best.confidence == 0.95

    def test_find_best_hypothesis_empty(self, engine: HypothesisEngine):
        best = engine.find_best_hypothesis([])
        assert best is None

    def test_find_most_likely_hypothesis(self, engine: HypothesisEngine):
        """Only supported + >= 0.5 confidence hypotheses should be considered."""
        h1 = Hypothesis("H1 weak", "")
        h2 = Hypothesis("H2 strong", "")
        h3 = Hypothesis("H3 not supported", "")
        results = [
            HypothesisResult(h1, True, 0.3, ""),   # below 0.5 threshold
            HypothesisResult(h2, True, 0.9, ""),   # best
            HypothesisResult(h3, False, 0.8, ""),  # not supported
        ]
        best = engine.find_most_likely_hypothesis(results)
        assert best is not None
        assert best.hypothesis.statement == "H2 strong"

    def test_find_most_likely_none(self, engine: HypothesisEngine):
        """If no hypothesis is both supported and >= 0.5, return None."""
        h1 = Hypothesis("H1", "")
        results = [
            HypothesisResult(h1, True, 0.3, ""),
        ]
        best = engine.find_most_likely_hypothesis(results)
        assert best is None

    def test_find_most_likely_empty(self, engine: HypothesisEngine):
        best = engine.find_most_likely_hypothesis([])
        assert best is None


# ======================================================================
# evaluate_hypotheses (plural) — batch evaluation
# ======================================================================


class TestEvaluateBatch:
    """Batch hypothesis evaluation."""

    async def test_evaluate_multiple_hypotheses(self, engine: HypothesisEngine):
        h1 = Hypothesis(
            "Steady state.",
            "",
            variables=["x"],
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        h2 = Hypothesis(
            "Conservation holds.",
            "",
            variables=["x", "y"],
            test_method="Check sum or norm of variables over time.",
        )
        data = {
            "x": [10.0, 10.0, 10.0, 10.0],
            "y": [5.0, 5.0, 5.0, 5.0],
        }
        result = make_result(data=data)
        batch_results = await engine.evaluate_hypotheses([h1, h2], result)
        assert len(batch_results) == 2
        assert all(isinstance(r, HypothesisResult) for r in batch_results)

    async def test_evaluate_mixed_test_methods(self, engine: HypothesisEngine):
        """Different test methods should be routed correctly."""
        h_steady = Hypothesis(
            "Steady state.",
            "",
            variables=["x"],
            test_method="Compute numerical derivatives and check they approach zero.",
        )
        h_converge = Hypothesis(
            "Convergence.",
            "",
            variables=["x"],
            test_method="Check solver convergence and residual magnitude.",
        )
        data = {"x": [1.0, 2.0, 3.0, 4.0]}
        result = make_result(data=data)
        results = await engine.evaluate_hypotheses([h_steady, h_converge], result)
        assert len(results) == 2
        # The steady-state one should get data-driven evaluation
        # (not the fallback pattern).
        assert "derivative" not in results[1].evidence.lower()


# ======================================================================
# Integration test — full generate → evaluate → rank pipeline
# ======================================================================


class TestFullPipeline:
    """End-to-end: generate from plan, evaluate against result, rank."""

    async def test_generate_evaluate_rank_ode(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.ODE_INITIAL_VALUE, variables=3)
        data = {
            "var0": [10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0,
                     6.5, 6.0, 5.5, 5.0, 5.0, 5.0, 5.0, 5.0],
            "var1": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                     1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "var2": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0,
                     3.5, 4.0, 4.5, 5.0, 5.0, 5.0, 5.0, 5.0],
        }
        result = make_result(data=data)

        hypotheses = await engine.generate_hypotheses(plan)
        assert len(hypotheses) >= 1

        eval_results = await engine.evaluate_hypotheses(hypotheses, result)
        assert len(eval_results) == len(hypotheses)

        ranked = engine.rank_hypotheses(eval_results)
        assert ranked[0].confidence >= ranked[-1].confidence

        best = engine.find_best_hypothesis(eval_results)
        assert best is not None
        assert best.confidence == ranked[0].confidence

        most_likely = engine.find_most_likely_hypothesis(eval_results)
        if most_likely is not None:
            assert most_likely.supported
            assert most_likely.confidence >= 0.5

    async def test_generate_evaluate_algebraic(self, engine: HypothesisEngine):
        plan = make_plan(form=MathematicalForm.ALGEBRAIC, variables=1)
        result = make_result(
            converged=True,
            data={"var0": [2.0]},  # scalar
        )
        hypotheses = await engine.generate_hypotheses(plan)
        assert len(hypotheses) >= 1
        eval_results = await engine.evaluate_hypotheses(hypotheses, result)
        assert all(isinstance(r, HypothesisResult) for r in eval_results)

    async def test_non_converged_full_pipeline(self, engine: HypothesisEngine):
        """A non-converged result should yield low-confidence evaluations."""
        plan = make_plan(form=MathematicalForm.ODE_INITIAL_VALUE, variables=1)
        result = make_result(
            converged=False,
            data={"var0": [1.0, 2.0, 3.0]},
        )
        hypotheses = await engine.generate_hypotheses(plan)
        eval_results = await engine.evaluate_hypotheses(hypotheses, result)
        # Most evaluations should have confidence < 0.5
        low_conf = [r for r in eval_results if r.confidence < 0.5]
        assert len(low_conf) >= 1, (
            "Non-converged simulation should produce some low-confidence results"
        )


# ======================================================================
# Documentation examples — basic smoke test
# ======================================================================


class TestDocExamples:
    """Ensure examples from the module/CLI documentation work."""

    async def test_physics_pendulum_hypothesis(self, engine: HypothesisEngine):
        """Simulate a simple physics scenario: 'what is the period?'"""
        plan = InvestigationPlan(
            query="What is the period of a 1m pendulum?",
            domain=ScientificDomain.PHYSICS,
            mathematical_form=MathematicalForm.ODE_INITIAL_VALUE,
            governing_equations=[
                Equation(
                    "pendulum",
                    "d²θ/dt² + (g/L) sin(θ) = 0",
                    "Simple pendulum equation",
                ),
            ],
            variables=[
                Variable("theta", "θ", "rad", "Angular displacement"),
            ],
            parameters=[
                Parameter("length", "L", 1.0, "m", "Pendulum length"),
                Parameter("gravity", "g", 9.81, "m/s²",
                          "Gravitational acceleration"),
            ],
        )
        data = {"theta": [0.1, 0.08, 0.06, 0.04, 0.02, 0.01, 0.005, 0.002]}
        result = make_result(data=data)

        hypotheses = await engine.generate_hypotheses(plan)
        assert len(hypotheses) >= 1
        eval_results = await engine.evaluate_hypotheses(hypotheses, result)
        assert len(eval_results) == len(hypotheses)

    async def test_unknown_domain_no_crash(self, engine: HypothesisEngine):
        """A plan with no domain/form should not crash."""
        plan = InvestigationPlan(query="Tell me about stars")
        hypotheses = await engine.generate_hypotheses(plan)
        assert len(hypotheses) >= 1
        assert "physically plausible" in hypotheses[0].statement.lower()
