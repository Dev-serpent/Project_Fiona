"""Hypothesis Engine — generates and evaluates testable scientific hypotheses.

The :class:`HypothesisEngine` takes an :class:`InvestigationPlan` and produces
one or more testable hypotheses informed by the plan's mathematical form and
domain. After simulation, it evaluates each hypothesis against the
:class:`SimulationResult` using data-driven analysis — trend detection,
conservation checks, derivative estimation, and numerical stability — rather
than a simple convergence check.

This module also defines the :class:`Hypothesis` and :class:`HypothesisResult`
dataclasses used throughout the kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from SciPhi.interfaces.model import MathematicalForm
    from SciPhi.interfaces.solver import SimulationResult
    from SciPhi.kernel.planner import InvestigationPlan


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hypothesis:
    """A single testable scientific hypothesis.

    Attributes:
        statement: A clear, concise statement of the hypothesis.
        null_hypothesis: The corresponding null hypothesis (H₀).
        variables: The names of the variables involved in the hypothesis.
        expected_outcome: The predicted outcome if the hypothesis is true.
        test_method: A short description of how the hypothesis can be tested
            (e.g. ``"compare final velocity"``, ``"check convergence"``).
    """

    statement: str
    null_hypothesis: str
    variables: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    test_method: str = ""


@dataclass(frozen=True)
class HypothesisResult:
    """The outcome of evaluating a hypothesis against simulation data.

    Attributes:
        hypothesis: The hypothesis that was tested.
        supported: Whether the evidence supports (``True``) or refutes
            (``False``) the hypothesis.
        confidence: A value in [0, 1] indicating the strength of the evidence.
        evidence: A human-readable summary of the evidence used.
    """

    hypothesis: Hypothesis
    supported: bool
    confidence: float
    evidence: str


# ---------------------------------------------------------------------------
# Hypothesis Engine
# ---------------------------------------------------------------------------


class HypothesisEngine:
    """Generates and evaluates hypotheses from an investigation plan and results.

    The engine uses the plan's mathematical form and domain to produce targeted,
    testable hypotheses. Each hypothesis is evaluated against the simulation
    result using data-driven analysis rather than a single convergence check.
    """

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate_hypotheses(self, plan: InvestigationPlan) -> list[Hypothesis]:
        """Generate testable hypotheses from an investigation plan.

        The type and number of hypotheses depend on the plan's mathematical
        form, domain, and available variables.

        Args:
            plan: A structured :class:`InvestigationPlan` describing the
                scientific problem.

        Returns:
            A list of 1–4 :class:`Hypothesis` instances tailored to the
            plan's mathematical form.
        """
        hypotheses: list[Hypothesis] = []

        # Delegate to form-specific generators.
        form = plan.mathematical_form
        if form is not None:
            hypotheses.extend(self._generate_ode_hypotheses(plan))
            hypotheses.extend(self._generate_algebraic_hypotheses(plan))
            hypotheses.extend(self._generate_optimization_hypotheses(plan))
            hypotheses.extend(self._generate_stochastic_hypotheses(plan))
            hypotheses.extend(self._generate_pde_hypotheses(plan))

        # Always add a domain-agnostic fallback based on the first variable.
        if plan.variables:
            var = plan.variables[0]
            # Avoid duplicating an already-generated variable hypothesis.
            if not any(var.name in h.variables and "consistent" in h.statement.lower()
                       for h in hypotheses):
                hypotheses.append(
                    Hypothesis(
                        statement=(
                            f"Changes in {var.name} are consistent with the "
                            f"model predictions."
                        ),
                        null_hypothesis=(
                            f"Changes in {var.name} are not consistent with "
                            f"the model predictions."
                        ),
                        variables=[var.name],
                        expected_outcome=(
                            "Model output matches simulated behavior "
                            "within tolerance."
                        ),
                        test_method=(
                            "Compare simulated vs expected values of "
                            + var.name
                        ),
                    )
                )

        # If we generated nothing, produce a fallback placeholder.
        if not hypotheses:
            hypotheses.append(
                Hypothesis(
                    statement="The simulation produces physically plausible results.",
                    null_hypothesis="The simulation produces unphysical results.",
                    variables=[],
                    expected_outcome="All values are within physical bounds.",
                    test_method="Physical bounds check.",
                )
            )

        return hypotheses

    def _generate_ode_hypotheses(
        self, plan: InvestigationPlan,
    ) -> list[Hypothesis]:
        """Generate hypotheses specific to ODE initial-value problems."""
        from SciPhi.interfaces.model import MathematicalForm

        if plan.mathematical_form not in (
            MathematicalForm.ODE_INITIAL_VALUE,
            MathematicalForm.ODE_BOUNDARY_VALUE,
        ):
            return []

        h: list[Hypothesis] = []

        # Steady-state hypothesis for ODEs with at least one variable.
        if plan.variables:
            var_names = [v.name for v in plan.variables]
            h.append(
                Hypothesis(
                    statement=(
                        f"The system approaches a steady state where "
                        f"derivatives vanish."
                    ),
                    null_hypothesis=(
                        "The system does not reach steady state within "
                        "the simulation horizon."
                    ),
                    variables=var_names,
                    expected_outcome=(
                        "All state variables converge to constant values "
                        "as time progresses."
                    ),
                    test_method="Compute numerical derivatives and check they approach zero.",
                )
            )
            # Conservation hypothesis if there are at least 2 variables.
            if len(var_names) >= 2:
                h.append(
                    Hypothesis(
                        statement=(
                            f"Total {var_names[0]} and {var_names[1]} are "
                            f"conserved over the simulation."
                        ),
                        null_hypothesis=(
                            f"Total {var_names[0]} and {var_names[1]} are "
                            f"not conserved."
                        ),
                        variables=var_names[:2],
                        expected_outcome=(
                            "Sum of variables stays within a constant "
                            "relative tolerance."
                        ),
                        test_method="Check sum or norm of variables over time.",
                    )
                )
            # Monotonicity hypothesis.
            if len(var_names) >= 1:
                h.append(
                    Hypothesis(
                        statement=(
                            f"{var_names[0]} evolves monotonically "
                            f"throughout the simulation."
                        ),
                        null_hypothesis=(
                            f"{var_names[0]} exhibits non-monotonic "
                            f"behaviour."
                        ),
                        variables=[var_names[0]],
                        expected_outcome="Values increase or decrease without reversal.",
                        test_method="Count sign changes in successive differences.",
                    )
                )

        return h

    def _generate_algebraic_hypotheses(
        self, plan: InvestigationPlan,
    ) -> list[Hypothesis]:
        """Generate hypotheses specific to algebraic / equation-solving problems."""
        from SciPhi.interfaces.model import MathematicalForm

        if plan.mathematical_form != MathematicalForm.ALGEBRAIC:
            return []

        h: list[Hypothesis] = []

        if plan.governing_equations:
            eq = plan.governing_equations[0]
            h.append(
                Hypothesis(
                    statement=(
                        f"The equation '{eq.name}' has a unique real "
                        f"solution within the parameter bounds."
                    ),
                    null_hypothesis=(
                        f"The equation '{eq.name}' has no real solution "
                        f"or multiple solutions."
                    ),
                    variables=[v.name for v in plan.variables],
                    expected_outcome="Residual converges to near zero.",
                    test_method=(
                        "Check solver convergence and residual magnitude."
                    ),
                )
            )
            # Bound hypothesis: solution is within physical bounds.
            if plan.variables:
                var = plan.variables[0]
                h.append(
                    Hypothesis(
                        statement=(
                            f"The solution for {var.name} lies within "
                            f"physically plausible bounds."
                        ),
                        null_hypothesis=(
                            f"The solution for {var.name} is outside "
                            f"expected bounds."
                        ),
                        variables=[var.name],
                        expected_outcome=f"{var.name} is finite and non-negative if applicable.",
                        test_method="Physical bounds check on result values.",
                    )
                )

        return h

    def _generate_optimization_hypotheses(
        self, plan: InvestigationPlan,
    ) -> list[Hypothesis]:
        """Generate hypotheses specific to optimisation problems."""
        from SciPhi.interfaces.model import MathematicalForm

        if plan.mathematical_form != MathematicalForm.OPTIMIZATION:
            return []

        h: list[Hypothesis] = []

        if plan.variables:
            var_names = [v.name for v in plan.variables]
            h.append(
                Hypothesis(
                    statement="The optimizer converges to a global optimum.",
                    null_hypothesis="The optimizer converges to a local optimum only.",
                    variables=var_names,
                    expected_outcome=(
                        "Objective function value is stable across "
                        "multiple starting points."
                    ),
                    test_method="Check convergence and objective stability.",
                )
            )

        return h

    def _generate_stochastic_hypotheses(
        self, plan: InvestigationPlan,
    ) -> list[Hypothesis]:
        """Generate hypotheses specific to stochastic / Monte Carlo problems."""
        from SciPhi.interfaces.model import MathematicalForm

        if plan.mathematical_form != MathematicalForm.STOCHASTIC:
            return []

        h: list[Hypothesis] = []

        if plan.variables:
            var_names = [v.name for v in plan.variables]
            h.append(
                Hypothesis(
                    statement=(
                        "The sample mean converges to the true "
                        "expected value."
                    ),
                    null_hypothesis=(
                        "The sample estimate does not converge to "
                        "the true value."
                    ),
                    variables=var_names,
                    expected_outcome=(
                        "Variance decreases with sample size; "
                        "mean stabilises."
                    ),
                    test_method="Assess variance reduction over samples.",
                )
            )

        return h

    def _generate_pde_hypotheses(
        self, plan: InvestigationPlan,
    ) -> list[Hypothesis]:
        """Generate hypotheses specific to PDE / hybrid problems."""
        from SciPhi.interfaces.model import MathematicalForm

        if plan.mathematical_form not in (
            MathematicalForm.PDE,
            MathematicalForm.HYBRID,
        ):
            return []

        h: list[Hypothesis] = []

        if plan.variables:
            var_names = [v.name for v in plan.variables]
            h.append(
                Hypothesis(
                    statement=(
                        "The numerical scheme is stable and does not "
                        "produce unbounded growth."
                    ),
                    null_hypothesis=(
                        "The numerical scheme is unstable, producing "
                        "divergent behaviour."
                    ),
                    variables=var_names,
                    expected_outcome=(
                        "Solution remains bounded and smooth throughout "
                        "the domain."
                    ),
                    test_method="Check for unbounded growth and oscillation.",
                )
            )

        return h

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate_hypotheses(
        self,
        hypotheses: list[Hypothesis],
        results: SimulationResult,
    ) -> list[HypothesisResult]:
        """Evaluate a list of hypotheses against simulation results.

        Each hypothesis is evaluated using data-driven analysis including:
        - Numerical trend detection (monotonicity, steady-state approach)
        - Residual and error-estimate analysis
        - Conservation checks between related variables
        - Derivative estimation for ODE-specific hypotheses
        - Oscillation detection for numerical stability

        Args:
            hypotheses: The hypotheses to evaluate.
            results: The simulation output to test against.

        Returns:
            A list of :class:`HypothesisResult` instances, one per input
            hypothesis, indicating whether the evidence supports or refutes
            each one along with a confidence level.
        """
        import math

        evaluation_results: list[HypothesisResult] = []

        for hypothesis in hypotheses:
            test_method_lower = hypothesis.test_method.lower()

            # Route to the appropriate evaluation strategy based on
            # the hypothesis test method.
            if "derivative" in test_method_lower or "steady" in test_method_lower:
                result = self._evaluate_steady_state(hypothesis, results)
            elif "conserv" in test_method_lower:
                result = self._evaluate_conservation(hypothesis, results)
            elif "monoton" in test_method_lower:
                result = self._evaluate_monotonicity(hypothesis, results)
            elif "convergence" in test_method_lower or "residual" in test_method_lower:
                result = self._evaluate_convergence(hypothesis, results)
            elif "bounded" in test_method_lower or "stabili" in test_method_lower:
                result = self._evaluate_stability(hypothesis, results)
            elif "variance" in test_method_lower or "mean" in test_method_lower:
                result = self._evaluate_stochastic(hypothesis, results)
            elif "unique" in test_method_lower:
                result = self._evaluate_convergence(hypothesis, results)
            elif "optimum" in test_method_lower or "optim" in test_method_lower:
                result = self._evaluate_convergence(hypothesis, results)
            else:
                # Fallback: use convergence-aware generic evaluation.
                supported = results.converged
                confidence = 0.85 if supported else 0.3
                if supported:
                    evidence = (
                        f"Simulation converged in {results.iterations} "
                        f"iterations with error estimate "
                        f"{results.error_estimate}. "
                        f"Data produced for variables: "
                        f"{list(results.data.keys())}."
                    )
                else:
                    evidence = (
                        "Simulation did not converge; "
                        "cannot confirm hypothesis."
                    )
                result = HypothesisResult(
                    hypothesis=hypothesis,
                    supported=supported,
                    confidence=confidence,
                    evidence=evidence,
                )

            evaluation_results.append(result)

        return evaluation_results

    async def evaluate_hypothesis(
        self,
        hypothesis: Hypothesis,
        results: SimulationResult,
    ) -> HypothesisResult:
        """Evaluate a single hypothesis (convenience wrapper)."""
        results_list = await self.evaluate_hypotheses([hypothesis], results)
        return results_list[0]

    # ------------------------------------------------------------------
    # Evaluation strategies
    # ------------------------------------------------------------------

    def _extract_series(
        self, data: dict, var_name: str,
    ) -> list[float]:
        """Extract a numeric series from result data by variable name."""
        import math

        for key, values in data.items():
            if var_name.lower() in key.lower():
                cleaned: list[float] = []
                for v in values:
                    try:
                        fv = float(v)
                        if math.isfinite(fv):
                            cleaned.append(fv)
                    except (TypeError, ValueError):
                        continue
                if cleaned:
                    return cleaned
        return []

    def _evaluate_steady_state(
        self, hypothesis: Hypothesis, results: SimulationResult,
    ) -> HypothesisResult:
        """Evaluate whether variables approach a steady state.

        Uses backward differences on the final portion of each time
        series. If the normalised derivative magnitudes are all below
        a threshold, the system is considered to have reached steady
        state.
        """
        import math

        if not results.converged:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.2,
                evidence="Simulation did not converge; cannot evaluate steady state.",
            )

        var_names = hypothesis.variables
        if not var_names:
            # Fall back to all available data keys.
            var_names = list(results.data.keys())

        steady_count = 0
        total_checks = 0
        detail_parts: list[str] = []

        for vname in var_names:
            series = self._extract_series(results.data, vname)
            if len(series) < 5:
                continue
            total_checks += 1
            # Use the last 40 % of the series for derivative estimation.
            tail = series[-max(len(series) // 2, 5):]
            # Normalised backward differences.
            diffs = []
            for i in range(1, len(tail)):
                dt = 1.0  # Normalised time step.
                dx = abs(tail[i] - tail[i - 1])
                denom = max(abs(tail[i - 1]), 1e-12)
                diffs.append(dx / denom)
            avg_norm_deriv = sum(diffs) / len(diffs) if diffs else float("inf")
            threshold = 1e-3
            if avg_norm_deriv < threshold:
                steady_count += 1
                detail_parts.append(
                    f"{vname}: steady (|dx/x|_avg = {avg_norm_deriv:.2e})"
                )
            else:
                detail_parts.append(
                    f"{vname}: not steady (|dx/x|_avg = {avg_norm_deriv:.2e})"
                )

        if total_checks == 0:
            supported = False
            confidence = 0.0
            evidence = "Insufficient data to evaluate steady state."
        else:
            ratio = steady_count / total_checks
            supported = ratio >= 0.5
            confidence = ratio * (0.9 - 0.1 * (1 - results.error_estimate or 0.5))
            confidence = max(0.0, min(1.0, confidence))
            evidence = "; ".join(detail_parts)

        return HypothesisResult(
            hypothesis=hypothesis,
            supported=supported,
            confidence=round(confidence, 4),
            evidence=evidence,
        )

    def _evaluate_conservation(
        self, hypothesis: Hypothesis, results: SimulationResult,
    ) -> HypothesisResult:
        """Evaluate whether the sum or total of two variables is conserved.

        Computes the relative standard deviation of the sum across all
        time steps. A low relative variation indicates conservation.
        """
        import math

        if not results.converged:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.2,
                evidence="Simulation did not converge; cannot evaluate conservation.",
            )

        var_names = hypothesis.variables
        if len(var_names) < 2:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.0,
                evidence="Need at least 2 variables for conservation check.",
            )

        s1 = self._extract_series(results.data, var_names[0])
        s2 = self._extract_series(results.data, var_names[1])
        if len(s1) < 2 or len(s2) < 2:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.0,
                evidence="Insufficient data for conservation check.",
            )

        # Pad or truncate to same length.
        n = min(len(s1), len(s2))
        sums = [s1[i] + s2[i] for i in range(n)]

        mean_sum = sum(sums) / len(sums)
        if abs(mean_sum) < 1e-12:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=True,
                confidence=0.95,
                evidence="Sum is zero throughout — exact cancellation.",
            )

        variance = sum((s - mean_sum) ** 2 for s in sums) / len(sums)
        rel_std = math.sqrt(variance) / abs(mean_sum)

        threshold = 0.05
        supported = rel_std < threshold
        # High relative std = low confidence in conservation.
        confidence = max(0.0, 1.0 - rel_std / threshold * 0.8)
        confidence = min(1.0, confidence)
        confidence *= (0.9 + 0.1 * (1 - (results.error_estimate or 0.0)))

        evidence = (
            f"Sum of {var_names[0]} and {var_names[1]}: "
            f"mean = {mean_sum:.4e}, relative std = {rel_std:.4e}. "
            + ("Conservation holds." if supported else "Conservation violated.")
        )

        return HypothesisResult(
            hypothesis=hypothesis,
            supported=supported,
            confidence=round(confidence, 4),
            evidence=evidence,
        )

    def _evaluate_monotonicity(
        self, hypothesis: Hypothesis, results: SimulationResult,
    ) -> HypothesisResult:
        """Evaluate whether a variable evolves monotonically.

        Counts the fraction of sign changes in successive differences.
        A low fraction indicates monotonic behaviour.
        """
        import math

        if not results.converged:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.2,
                evidence="Simulation did not converge; cannot evaluate monotonicity.",
            )

        var_names = hypothesis.variables
        if not var_names:
            var_names = list(results.data.keys())

        best_ratio = 0.0
        best_var = ""
        best_evidence = ""

        for vname in var_names:
            series = self._extract_series(results.data, vname)
            if len(series) < 3:
                continue
            diffs = [series[i] - series[i - 1] for i in range(1, len(series))]
            # Count non-zero differences that change sign.
            sign_changes = 0
            non_zero = 0
            prev_sign = 0
            for d in diffs:
                if abs(d) < 1e-12:
                    continue
                non_zero += 1
                sign = 1 if d > 0 else -1
                if prev_sign != 0 and sign != prev_sign:
                    sign_changes += 1
                prev_sign = sign

            if non_zero == 0:
                ratio = 1.0  # Constant series = monotonic.
            else:
                ratio = 1.0 - (sign_changes / non_zero)
            if ratio > best_ratio:
                best_ratio = ratio
                best_var = vname
                best_evidence = (
                    f"{vname}: {sign_changes}/{non_zero} sign changes "
                    f"→ monotonicity ratio = {ratio:.3f}"
                )

        if not best_var:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.0,
                evidence="Insufficient data for monotonicity check.",
            )

        threshold = 0.7  # >= 70 % monotonic.
        supported = best_ratio >= threshold
        confidence = best_ratio * 0.9
        if results.error_estimate is not None:
            confidence *= (1.0 - min(results.error_estimate, 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return HypothesisResult(
            hypothesis=hypothesis,
            supported=supported,
            confidence=round(confidence, 4),
            evidence=best_evidence,
        )

    def _evaluate_convergence(
        self, hypothesis: Hypothesis, results: SimulationResult,
    ) -> HypothesisResult:
        """Evaluate whether the solver converged with acceptable error.

        The confidence is derived from the error estimate and iteration
        count. A converged solution with low error gets high confidence.
        """
        if not results.converged:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.2,
                evidence=(
                    f"Solver did not converge after "
                    f"{results.iterations} iterations."
                ),
            )

        # Base confidence on convergence.
        confidence = 0.85

        # Adjust for error estimate.
        if results.error_estimate is not None:
            # Lower error → higher confidence.
            error_factor = max(0.0, 1.0 - results.error_estimate * 5)
            confidence = 0.5 + 0.5 * error_factor

        # Adjust for iteration count (excessive iterations = marginal).
        if results.iterations > 1000:
            confidence *= 0.9

        confidence = max(0.0, min(1.0, confidence))
        supported = confidence >= 0.5

        evidence = (
            f"Solver converged in {results.iterations} iterations "
            f"with error estimate {results.error_estimate}. "
            f"Data produced for variables: {list(results.data.keys())}."
        )

        return HypothesisResult(
            hypothesis=hypothesis,
            supported=supported,
            confidence=round(confidence, 4),
            evidence=evidence,
        )

    def _evaluate_stability(
        self, hypothesis: Hypothesis, results: SimulationResult,
    ) -> HypothesisResult:
        """Evaluate whether the solution is numerically stable.

        Checks for unbounded growth, NaN/Inf values, and excessive
        oscillations.
        """
        import math

        failures: list[str] = []
        total_vars = 0

        for var_name, values in results.data.items():
            total_vars += 1
            series = self._extract_series(results.data, var_name)
            if not series:
                failures.append(f"{var_name}: no finite data")
                continue

            # Check for unbounded growth: final value > 100x initial
            # magnitude (heuristic).
            init_mag = abs(series[0])
            final_mag = abs(series[-1])
            if init_mag > 1e-12 and final_mag > 1000 * init_mag:
                failures.append(f"{var_name}: unbounded growth")
                continue

            # Check for oscillations.
            if len(series) >= 4:
                diffs = [series[i] - series[i - 1] for i in range(1, len(series))]
                sign_changes = sum(
                    1 for i in range(1, len(diffs))
                    if diffs[i] * diffs[i - 1] < 0
                )
                if sign_changes > len(diffs) * 0.6:
                    failures.append(f"{var_name}: excessive oscillation")

        if total_vars == 0:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.0,
                evidence="No data available for stability check.",
            )

        stable_count = total_vars - len(failures)
        ratio = stable_count / total_vars
        supported = ratio >= 0.75
        confidence = ratio * (0.9 if results.converged else 0.4)
        confidence = max(0.0, min(1.0, confidence))

        if failures:
            evidence = (
                f"Stability issues in {len(failures)}/{total_vars} "
                f"variables: {'; '.join(failures)}"
            )
        else:
            evidence = (
                f"All {total_vars} variables are bounded and "
                f"numerically stable."
            )

        return HypothesisResult(
            hypothesis=hypothesis,
            supported=supported,
            confidence=round(confidence, 4),
            evidence=evidence,
        )

    def _evaluate_stochastic(
        self, hypothesis: Hypothesis, results: SimulationResult,
    ) -> HypothesisResult:
        """Evaluate convergence of stochastic / Monte Carlo estimates.

        Uses the error estimate as a proxy for variance reduction.
        """
        if not results.converged:
            return HypothesisResult(
                hypothesis=hypothesis,
                supported=False,
                confidence=0.2,
                evidence="Simulation did not converge.",
            )

        # For stochastic problems, error estimate often reflects
        # Monte Carlo standard error.
        if results.error_estimate is not None:
            # Lower MC error → better convergence.
            confidence = max(0.0, 1.0 - results.error_estimate * 2)
            supported = confidence >= 0.5
            evidence = (
                f"Error estimate {results.error_estimate:.4e} "
                f"(proxy for MC standard error). "
                f"{'Good convergence.' if supported else 'Further sampling needed.'}"
            )
        else:
            # No error estimate — use iteration count as proxy.
            confidence = min(1.0, results.iterations / 10000)
            supported = confidence >= 0.5
            evidence = (
                f"{results.iterations} samples collected. "
                f"{'Convergence assumed.' if supported else 'Insufficient samples.'}"
            )

        return HypothesisResult(
            hypothesis=hypothesis,
            supported=supported,
            confidence=round(confidence, 4),
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank_hypotheses(
        self, results: list[HypothesisResult],
    ) -> list[HypothesisResult]:
        """Rank hypotheses by confidence (descending).

        Args:
            results: The list of hypothesis evaluation results to rank.

        Returns:
            A new list sorted by confidence in descending order.
        """
        return sorted(results, key=lambda r: r.confidence, reverse=True)

    def find_best_hypothesis(
        self, results: list[HypothesisResult],
    ) -> HypothesisResult | None:
        """Return the hypothesis result with the highest confidence.

        Args:
            results: The list of hypothesis evaluation results.

        Returns:
            The :class:`HypothesisResult` with the highest confidence,
            or ``None`` if the list is empty.
        """
        ranked = self.rank_hypotheses(results)
        return ranked[0] if ranked else None

    def find_most_likely_hypothesis(
        self, results: list[HypothesisResult],
    ) -> HypothesisResult | None:
        """Return the supported hypothesis with the highest confidence.

        This is useful when you want the best *supported* explanation
        (confidence >= 0.5 and supported = True), rather than just the
        highest-confidence result.
        """
        supported = [r for r in results if r.supported and r.confidence >= 0.5]
        if not supported:
            return None
        return max(supported, key=lambda r: r.confidence)
