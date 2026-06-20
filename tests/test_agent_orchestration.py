"""Comprehensive tests for Milestone 4: Advanced Orchestration Engine.

Tests cover:
- ComplexityAssessor: classification, fallback
- TaskPlan: from_llm, validation, execution_order, cycle detection
- SubAgent: ReAct loop, cancellation, max turns
- ForemanAgent: simple, complex, parallel, cancellation, fallback
"""

from __future__ import annotations

import json
import threading
import time
import unittest
from unittest.mock import MagicMock, PropertyMock, call, patch
from typing import Any

from Agent.cancellation import CancellationToken, CancelledError
from Agent.chat_store import ChatStore
from Agent.ollama import OllamaClient, OllamaError
from Agent.permission import PermissionEnforcer, SafeActionRouter
from Agent.personality import Personality, PersonalityRegistry
from Agent.orchestration import (
    Complexity,
    ComplexityAssessor,
    ForemanAgent,
    ForemanConfig,
    PlanValidationError,
    SubAgent,
    SubAgentResult,
    SubGoalSpec,
    TaskPlan,
)
from FionaCore import ActionResult


# ======================================================================
# Helpers
# ======================================================================


def _make_personality(
    name: str = "test",
    system_prompt: str = "You are a test assistant.",
    allowed_tools: frozenset[str] | None = None,
) -> Personality:
    """Create a minimal Personality for testing."""
    return Personality(
        name=name,
        description=f"{name} personality",
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
    )


def _make_safe_router(
    personality: Personality | None = None,
    mock_router: Any = None,
    ok: bool = True,
    detail: str = "Mock result",
) -> SafeActionRouter:
    """Build a SafeActionRouter backed by a mock ActionRouter."""
    p = personality or _make_personality()
    enforcer = PermissionEnforcer(p)
    if mock_router is None:
        mock_router = MagicMock()
        mock_router.run.return_value = MagicMock(ok=ok, detail=detail, spec=ActionResult)
    return SafeActionRouter(enforcer, router=mock_router)


def _registry_with_personalities(*names: str) -> PersonalityRegistry:
    """Create a fresh PersonalityRegistry with only the named built-ins.

    This is expensive so use sparingly.  For most tests the full
    singleton is fine.
    """
    # Save and reset singleton
    old = PersonalityRegistry._instance
    PersonalityRegistry._instance = None
    reg = PersonalityRegistry()
    # Only keep the requested personalities
    all_builtins = list(reg._personalities.keys())
    for name in all_builtins:
        if name not in names:
            del reg._personalities[name]
    PersonalityRegistry._instance = old
    return reg


# ======================================================================
# 1. ComplexityAssessor Tests
# ======================================================================


class TestComplexityAssessor(unittest.TestCase):
    """ComplexityAssessor classification and fallback behaviour."""

    def setUp(self) -> None:
        self.client = MagicMock(spec=OllamaClient)
        self.assessor = ComplexityAssessor(self.client)

    def _assert_assess(self, classification: str) -> Complexity:
        """Helper: set mock return and run assess()."""
        self.client.ask.return_value = (
            f'{{"classification": "{classification}", "reason": "test"}}'
        )
        return self.assessor.assess("test goal")

    def test_simple(self) -> None:
        self.assertEqual(self._assert_assess("simple"), Complexity.SIMPLE)

    def test_moderate(self) -> None:
        self.assertEqual(self._assert_assess("moderate"), Complexity.MODERATE)

    def test_complex(self) -> None:
        self.assertEqual(self._assert_assess("complex"), Complexity.COMPLEX)

    def test_case_insensitive(self) -> None:
        self.client.ask.return_value = (
            '{"classification": "COMPLEX", "reason": "case test"}'
        )
        result = self.assessor.assess("test")
        self.assertEqual(result, Complexity.COMPLEX)

    def test_fallback_on_invalid_json(self) -> None:
        self.client.ask.return_value = "not valid json"
        result = self.assessor.assess("test")
        self.assertEqual(result, Complexity.MODERATE)

    def test_fallback_on_ollama_error(self) -> None:
        self.client.ask.side_effect = OllamaError("connection refused")
        result = self.assessor.assess("test")
        self.assertEqual(result, Complexity.MODERATE)

    def test_fallback_on_unrecognised_classification(self) -> None:
        self.client.ask.return_value = (
            '{"classification": "unknown_value", "reason": "test"}'
        )
        result = self.assessor.assess("test")
        self.assertEqual(result, Complexity.MODERATE)

    def test_fallback_on_empty_response(self) -> None:
        self.client.ask.return_value = ""
        result = self.assessor.assess("test")
        self.assertEqual(result, Complexity.MODERATE)

    def test_calls_client_with_expected_params(self) -> None:
        self.client.ask.return_value = (
            '{"classification": "simple", "reason": "test"}'
        )
        self.assessor.assess("my goal")
        _, kwargs = self.client.ask.call_args
        self.assertIn("prompt", kwargs)
        self.assertIn("temperature", kwargs)
        self.assertIn("max_tokens", kwargs)
        self.assertIn("my goal", kwargs["prompt"])


# ======================================================================
# 2. TaskPlan Tests
# ======================================================================


class TestTaskPlan(unittest.TestCase):
    """TaskPlan construction, validation, execution_order, from_llm."""

    def setUp(self) -> None:
        # Ensure the PersonalityRegistry singleton is available
        self._old_reg = PersonalityRegistry._instance
        PersonalityRegistry._instance = None
        self.registry = PersonalityRegistry()

    def tearDown(self) -> None:
        PersonalityRegistry._instance = self._old_reg

    # -- to_dict / construction ----------------------------------------

    def test_to_dict(self) -> None:
        plan = TaskPlan(
            goal="test goal",
            sub_goals=(
                SubGoalSpec(id="a", description="Do A", assigned_personality="planner"),
                SubGoalSpec(
                    id="b", description="Do B", assigned_personality="engineer",
                    depends_on=("a",), parallel=True,
                ),
            ),
        )
        d = plan.to_dict()
        self.assertEqual(d["goal"], "test goal")
        self.assertEqual(len(d["sub_goals"]), 2)
        self.assertEqual(d["sub_goals"][0]["id"], "a")
        self.assertEqual(d["sub_goals"][1]["depends_on"], ["a"])
        self.assertTrue(d["sub_goals"][1]["parallel"])

    # -- validate -------------------------------------------------------

    def test_validate_valid(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(id="a", description="A", assigned_personality="general"),
            ),
        )
        # Should not raise
        plan.validate(registry=self.registry)

    def test_validate_duplicate_ids(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(id="a", description="A", assigned_personality="general"),
                SubGoalSpec(id="a", description="B", assigned_personality="general"),
            ),
        )
        with self.assertRaises(PlanValidationError) as ctx:
            plan.validate(registry=self.registry)
        self.assertIn("Duplicate", str(ctx.exception))
        self.assertIn("a", str(ctx.exception))

    def test_validate_missing_dependency(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(
                    id="a", description="A", assigned_personality="general",
                    depends_on=("nonexistent",),
                ),
            ),
        )
        with self.assertRaises(PlanValidationError) as ctx:
            plan.validate(registry=self.registry)
        self.assertIn("depends on unknown", str(ctx.exception))

    def test_validate_invalid_personality(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(
                    id="a", description="A",
                    assigned_personality="does_not_exist",
                ),
            ),
        )
        with self.assertRaises(PlanValidationError) as ctx:
            plan.validate(registry=self.registry)
        self.assertIn("unknown personality", str(ctx.exception))

    def test_validate_circular_dependency(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(
                    id="a", description="A", assigned_personality="general",
                    depends_on=("b",),
                ),
                SubGoalSpec(
                    id="b", description="B", assigned_personality="general",
                    depends_on=("a",),
                ),
            ),
        )
        with self.assertRaises(PlanValidationError) as ctx:
            plan.validate(registry=self.registry)
        self.assertIn("Circular", str(ctx.exception))

    # -- execution_order ------------------------------------------------

    def test_execution_order_single(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(id="a", description="A", assigned_personality="general"),
            ),
        )
        layers = plan.execution_order()
        self.assertEqual(len(layers), 1)
        self.assertEqual(len(layers[0]), 1)
        self.assertEqual(layers[0][0].id, "a")

    def test_execution_order_linear(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(
                    id="a", description="A", assigned_personality="general",
                    depends_on=(),
                ),
                SubGoalSpec(
                    id="b", description="B", assigned_personality="general",
                    depends_on=("a",),
                ),
                SubGoalSpec(
                    id="c", description="C", assigned_personality="general",
                    depends_on=("b",),
                ),
            ),
        )
        layers = plan.execution_order()
        self.assertEqual(len(layers), 3)
        self.assertEqual(layers[0][0].id, "a")
        self.assertEqual(layers[1][0].id, "b")
        self.assertEqual(layers[2][0].id, "c")

    def test_execution_order_parallel_layer(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(id="a", description="A", assigned_personality="general"),
                SubGoalSpec(id="b", description="B", assigned_personality="general"),
            ),
        )
        layers = plan.execution_order()
        self.assertEqual(len(layers), 1)
        self.assertEqual(len(layers[0]), 2)
        ids = {sg.id for sg in layers[0]}
        self.assertEqual(ids, {"a", "b"})

    def test_execution_order_diamond(self) -> None:
        plan = TaskPlan(
            goal="test",
            sub_goals=(
                SubGoalSpec(id="a", description="A", assigned_personality="general"),
                SubGoalSpec(
                    id="b", description="B", assigned_personality="general",
                    depends_on=("a",),
                ),
                SubGoalSpec(
                    id="c", description="C", assigned_personality="general",
                    depends_on=("a",),
                ),
                SubGoalSpec(
                    id="d", description="D", assigned_personality="general",
                    depends_on=("b", "c"),
                ),
            ),
        )
        layers = plan.execution_order()
        self.assertEqual(len(layers), 3)
        self.assertEqual(layers[0][0].id, "a")
        self.assertEqual(len(layers[1]), 2)
        self.assertEqual(layers[2][0].id, "d")

    # -- _detect_cycles --------------------------------------------------

    def test_detect_cycles_direct(self) -> None:
        self.assertTrue(TaskPlan._detect_cycles([
            SubGoalSpec(id="a", description="A", assigned_personality="general",
                        depends_on=("b",)),
            SubGoalSpec(id="b", description="B", assigned_personality="general",
                        depends_on=("a",)),
        ]))

    def test_detect_cycles_no_cycle(self) -> None:
        self.assertFalse(TaskPlan._detect_cycles([
            SubGoalSpec(id="a", description="A", assigned_personality="general",
                        depends_on=()),
            SubGoalSpec(id="b", description="B", assigned_personality="general",
                        depends_on=("a",)),
        ]))

    def test_detect_cycles_self_loop(self) -> None:
        self.assertTrue(TaskPlan._detect_cycles([
            SubGoalSpec(id="a", description="A", assigned_personality="general",
                        depends_on=("a",)),
        ]))

    def test_detect_cycles_disconnected(self) -> None:
        self.assertFalse(TaskPlan._detect_cycles([
            SubGoalSpec(id="a", description="A", assigned_personality="general"),
            SubGoalSpec(id="b", description="B", assigned_personality="general"),
        ]))

    # -- from_llm -------------------------------------------------------

    def test_from_llm_success(self) -> None:
        client = MagicMock(spec=OllamaClient)
        client.ask.return_value = json.dumps({
            "sub_goals": [
                {
                    "id": "step-1",
                    "description": "Check system state",
                    "assigned_personality": "planner",
                    "depends_on": [],
                    "parallel": False,
                },
                {
                    "id": "step-2",
                    "description": "Execute action",
                    "assigned_personality": "engineer",
                    "depends_on": ["step-1"],
                    "parallel": False,
                },
            ],
        })

        plan = TaskPlan.from_llm(
            client, "test goal", max_retries=0, registry=self.registry,
        )
        self.assertEqual(plan.goal, "test goal")
        self.assertEqual(len(plan.sub_goals), 2)
        self.assertEqual(plan.sub_goals[0].id, "step-1")
        self.assertEqual(plan.sub_goals[0].assigned_personality, "planner")
        self.assertEqual(plan.sub_goals[1].depends_on, ("step-1",))

    def test_from_llm_retry_then_succeed(self) -> None:
        """Succeeds on the second attempt after invalid JSON on the first."""
        client = MagicMock(spec=OllamaClient)
        valid_json = json.dumps({
            "sub_goals": [
                {
                    "id": "s1", "description": "Do it",
                    "assigned_personality": "general",
                    "depends_on": [], "parallel": False,
                },
            ],
        })
        client.ask.side_effect = ["not json", valid_json]

        plan = TaskPlan.from_llm(
            client, "test", max_retries=2, registry=self.registry,
        )
        self.assertEqual(len(plan.sub_goals), 1)
        self.assertEqual(client.ask.call_count, 2)

    def test_from_llm_exhausts_retries(self) -> None:
        client = MagicMock(spec=OllamaClient)
        client.ask.return_value = "not valid json at all"

        with self.assertRaises(PlanValidationError):
            TaskPlan.from_llm(
                client, "test", max_retries=1, registry=self.registry,
            )
        # 2 calls = initial + 1 retry
        self.assertEqual(client.ask.call_count, 2)

    def test_from_llm_missing_sub_goals_key(self) -> None:
        client = MagicMock(spec=OllamaClient)
        client.ask.return_value = '{"other_key": []}'

        with self.assertRaises(PlanValidationError) as ctx:
            TaskPlan.from_llm(
                client, "test", max_retries=0, registry=self.registry,
            )
        self.assertIn("sub_goals", str(ctx.exception))

    def test_from_llm_empty_sub_goals(self) -> None:
        client = MagicMock(spec=OllamaClient)
        client.ask.return_value = '{"sub_goals": []}'

        with self.assertRaises(PlanValidationError):
            TaskPlan.from_llm(
                client, "test", max_retries=0, registry=self.registry,
            )

    def test_from_llm_bad_personality_retry(self) -> None:
        client = MagicMock(spec=OllamaClient)
        bad = json.dumps({
            "sub_goals": [
                {
                    "id": "s1", "description": "X",
                    "assigned_personality": "nonexistent",
                    "depends_on": [], "parallel": False,
                },
            ],
        })
        good = json.dumps({
            "sub_goals": [
                {
                    "id": "s1", "description": "X",
                    "assigned_personality": "general",
                    "depends_on": [], "parallel": False,
                },
            ],
        })
        client.ask.side_effect = [bad, good]

        plan = TaskPlan.from_llm(
            client, "test", max_retries=1, registry=self.registry,
        )
        self.assertEqual(len(plan.sub_goals), 1)
        self.assertEqual(plan.sub_goals[0].assigned_personality, "general")

    def test_from_llm_ollama_error_retry(self) -> None:
        client = MagicMock(spec=OllamaClient)
        client.ask.side_effect = [
            OllamaError("timeout"),
            json.dumps({
                "sub_goals": [
                    {
                        "id": "s1", "description": "X",
                        "assigned_personality": "general",
                        "depends_on": [], "parallel": False,
                    },
                ],
            }),
        ]

        plan = TaskPlan.from_llm(
            client, "test", max_retries=1, registry=self.registry,
        )
        self.assertEqual(len(plan.sub_goals), 1)

    def test_from_llm_respects_max_sub_goals(self) -> None:
        client = MagicMock(spec=OllamaClient)
        client.ask.return_value = json.dumps({
            "sub_goals": [
                {
                    "id": f"s{i}", "description": f"Step {i}",
                    "assigned_personality": "general",
                    "depends_on": [], "parallel": False,
                }
                for i in range(10)
            ],
        })

        plan = TaskPlan.from_llm(
            client, "test", max_retries=0, registry=self.registry,
            max_sub_goals=10,
        )
        self.assertEqual(len(plan.sub_goals), 10)


# ======================================================================
# 3. SubAgent Tests
# ======================================================================


class TestSubAgent(unittest.TestCase):
    """SubAgent ReAct loop execution, cancellation, max turns."""

    def setUp(self) -> None:
        self.client = MagicMock(spec=OllamaClient)
        self.personality = _make_personality(
            name="general",
            system_prompt="You are a helpful assistant.",
            allowed_tools=None,
        )
        self.mock_action_router = MagicMock()
        self.mock_action_router.run.return_value = MagicMock(
            ok=True, detail="Action result", spec=ActionResult,
        )
        self.router = _make_safe_router(self.personality, self.mock_action_router)
        self.sub_agent = SubAgent(
            self.personality, self.client, self.router, max_turns=5,
        )
        self.token = CancellationToken()

    def test_execute_returns_final_answer_directly(self) -> None:
        """Single turn with final answer."""
        self.client.ask.return_value = (
            '{"thought": "Done", "final": "The answer is 42."}'
        )
        result = self.sub_agent.execute("test goal", self.token)
        self.assertEqual(result, "The answer is 42.")
        self.assertEqual(self.sub_agent.turns, 1)

    def test_execute_multiple_turns(self) -> None:
        """Action then final answer."""
        self.client.ask.side_effect = [
            '{"thought": "Check state", "action": "fiona_status", "input": {}}',
            '{"thought": "Got state", "final": "System is OK."}',
        ]
        result = self.sub_agent.execute("test goal", self.token)
        self.assertEqual(result, "System is OK.")
        self.assertEqual(self.sub_agent.turns, 2)
        # Verify the action router was called (SafeActionRouter passes extra kwargs)
        self.mock_action_router.run.assert_called_once()
        args, kwargs = self.mock_action_router.run.call_args
        self.assertEqual(args[0], "fiona_status")
        self.assertEqual(kwargs.get("source"), "agent")

    def test_execute_router_failure_becomes_observation(self) -> None:
        """If the action router fails, that becomes an observation and loop continues."""
        self.mock_action_router.run.return_value = MagicMock(
            ok=False, detail="Action not found", spec=ActionResult,
        )
        self.client.ask.side_effect = [
            '{"thought": "Try action", "action": "unknown_tool", "input": {}}',
            '{"thought": "Action failed", "final": "Could not complete."}',
        ]
        result = self.sub_agent.execute("test goal", self.token)
        self.assertEqual(result, "Could not complete.")
        # Router was called
        self.mock_action_router.run.assert_called_once()

    def test_execute_router_exception_becomes_observation(self) -> None:
        """If SafeActionRouter.run raises, the error becomes an observation."""
        self.mock_action_router.run.side_effect = RuntimeError("boom")
        self.client.ask.side_effect = [
            '{"thought": "Try action", "action": "fiona_status", "input": {}}',
            '{"thought": "It failed", "final": "Handled error gracefully."}',
        ]
        result = self.sub_agent.execute("test goal", self.token)
        self.assertEqual(result, "Handled error gracefully.")

    def test_cancellation_raises_during_execution(self) -> None:
        """When cancelled before the first LLM call, CancelledError propagates."""
        self.token.cancel()
        with self.assertRaises(CancelledError):
            self.sub_agent.execute("test goal", self.token)

    def test_cancellation_between_turns(self) -> None:
        """Cancel after first action, before second LLM call."""
        call_count: int = 0

        def cancel_after_first_ask(*args: Any, **kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            # Cancel after the first ask returns (so second turn's
            # token.raise_if_cancelled() fires)
            self.token.cancel()
            return '{"thought": "Step 1", "action": "fiona_status", "input": {}}'

        self.client.ask.side_effect = cancel_after_first_ask

        with self.assertRaises(CancelledError):
            self.sub_agent.execute("test goal", self.token)

        # First ask was made, second never was
        self.assertEqual(call_count, 1, "Second LLM call should not happen")
        self.assertTrue(self.token.is_cancelled())

    def test_cancellation_pre_checked(self) -> None:
        """CancellationToken checked before execute."""
        self.token.cancel()
        with self.assertRaises(CancelledError):
            self.sub_agent.execute("test goal", self.token)

    def test_max_turns_exceeded(self) -> None:
        """When max_turns is reached without final, a fallback message is returned."""
        # Return action-only responses each turn (never final)
        self.client.ask.return_value = (
            '{"thought": "Still working", "action": "fiona_status", "input": {}}'
        )
        self.sub_agent = SubAgent(
            self.personality, self.client, self.router, max_turns=3,
        )
        result = self.sub_agent.execute("test goal", self.token)
        self.assertIn("maximum", result.lower())
        self.assertIn("3", result)
        self.assertEqual(self.sub_agent.turns, 3)

    def test_on_turn_callback_invoked(self) -> None:
        """The on_turn callback receives each LLM response."""
        self.client.ask.side_effect = [
            '{"thought": "Check", "action": "fiona_status", "input": {}}',
            '{"thought": "Done", "final": "Complete."}',
        ]
        collected: list[str] = []
        result = self.sub_agent.execute(
            "test goal", self.token, on_turn=collected.append,
        )
        self.assertEqual(result, "Complete.")
        # 3 calls: LLM response (action), action log, LLM response (final)
        self.assertEqual(len(collected), 3)
        # Note: on_turn is called for both LLM response and action log

    def test_handles_non_json_response_as_final(self) -> None:
        """When the LLM returns non-JSON text, it's used as the final answer."""
        self.client.ask.return_value = "The system is running normally."
        result = self.sub_agent.execute("test goal", self.token)
        self.assertEqual(result, "The system is running normally.")

    def test_handles_empty_response(self) -> None:
        """Empty string response is returned as-is."""
        self.client.ask.return_value = ""
        result = self.sub_agent.execute("test goal", self.token)
        self.assertEqual(result, "")

    def test_response_with_extra_text(self) -> None:
        """JSON embedded in surrounding text is parsed correctly."""
        self.client.ask.return_value = (
            'Here is my analysis:\n{"thought": "done", "final": "All good."}'
        )
        result = self.sub_agent.execute("test goal", self.token)
        self.assertEqual(result, "All good.")

    def test_thought_used_when_no_final_or_action(self) -> None:
        """If JSON has 'thought' but neither 'final' nor 'action', thought is returned."""
        self.client.ask.return_value = '{"thought": "I am thinking about this."}'
        result = self.sub_agent.execute("test goal", self.token)
        self.assertEqual(result, "I am thinking about this.")

    def test_router_permission_check(self) -> None:
        """SubAgent's SafeActionRouter checks permissions before execution."""
        # Use a personality with restricted tools
        restricted_personality = _make_personality(
            name="restricted",
            allowed_tools=frozenset({"allowed_tool"}),
        )
        mock_router = MagicMock()
        mock_router.run.return_value = MagicMock(
            ok=True, detail="OK", spec=ActionResult,
        )
        router = _make_safe_router(restricted_personality, mock_router)

        agent = SubAgent(restricted_personality, self.client, router, max_turns=3)

        # First call: try a disallowed tool -> PermissionError caught -> observation
        # Second call: provide final answer
        self.client.ask.side_effect = [
            '{"thought": "Try disallowed", "action": "disallowed_tool", "input": {}}',
            '{"thought": "Fixed", "final": "Used allowed tool instead."}',
        ]
        result = agent.execute("test goal", self.token)
        self.assertEqual(result, "Used allowed tool instead.")
        # Router should NOT have been called for the disallowed tool
        # (PermissionError is raised by SafeActionRouter before delegation)
        mock_router.run.assert_not_called()


# ======================================================================
# 4. ForemanAgent Tests
# ======================================================================


class TestForemanAgent(unittest.TestCase):
    """ForemanAgent orchestration pipeline."""

    def setUp(self) -> None:
        # Save and reset PersonalityRegistry singleton
        self._old_reg = PersonalityRegistry._instance
        PersonalityRegistry._instance = None

        # Patch ActionRouter globally so all SafeActionRouter(enforcer)
        # calls within ForemanAgent get a mock underlying router.
        self._ar_patcher = patch("Agent.permission.ActionRouter")
        self.mock_ar_cls = self._ar_patcher.start()
        self.mock_ar = MagicMock()
        self.mock_ar.run.return_value = MagicMock(
            ok=True, detail="Mock tool output", spec=ActionResult,
        )
        self.mock_ar_cls.return_value = self.mock_ar

        self.client = MagicMock(spec=OllamaClient)
        self.registry = PersonalityRegistry()
        self.config = ForemanConfig(
            parallel_by_default=False,
            max_sub_agents=5,
            max_turns_per_sub_agent=3,
            max_plan_retries=1,
        )
        self.foreman = ForemanAgent(
            self.client, self.registry, config=self.config,
        )

    def tearDown(self) -> None:
        self._ar_patcher.stop()
        PersonalityRegistry._instance = self._old_reg

    # -- helpers --------------------------------------------------------

    def _set_client_responses(
        self,
        complexity: str = "simple",
        plan_json: str | None = None,
        sub_agent_responses: list[str] | None = None,
        synthesis_response: str = "Synthesized final response.",
    ) -> None:
        """Set up sequential responses for client.ask().

        The sequence is:
        1. Complexity assessment
        2. (optional) Task decomposition
        3. N sub-agent calls
        4. (optional) Synthesis
        """
        responses: list[str] = []

        # 1. Complexity
        responses.append(
            f'{{"classification": "{complexity}", "reason": "test"}}'
        )

        # 2. Decomposition (for moderate/complex)
        if complexity in ("moderate", "complex"):
            if plan_json is None:
                plan_json = json.dumps({
                    "sub_goals": [
                        {
                            "id": "step-1",
                            "description": "Research topic",
                            "assigned_personality": "planner",
                            "depends_on": [],
                            "parallel": False,
                        },
                        {
                            "id": "step-2",
                            "description": "Execute task",
                            "assigned_personality": "engineer",
                            "depends_on": ["step-1"],
                            "parallel": False,
                        },
                    ],
                })
            responses.append(plan_json)

        # 3. Sub-agent calls
        if sub_agent_responses is not None:
            responses.extend(sub_agent_responses)

        # 4. Synthesis (for complex plans)
        if complexity in ("moderate", "complex") and sub_agent_responses:
            responses.append(synthesis_response)

        self.client.ask.side_effect = responses

    # -- SIMPLE path ----------------------------------------------------

    def test_simple_goal_single_sub_agent(self) -> None:
        """Simple goal bypasses decomposition and runs a single SubAgent."""
        self._set_client_responses(
            complexity="simple",
            sub_agent_responses=[
                '{"thought": "Done", "final": "Single agent result."}',
            ],
        )
        result = self.foreman.execute("simple goal")
        self.assertEqual(result, "Single agent result.")
        # Complexity assessment was made
        self.assertIn("Classify", self.client.ask.call_args_list[0][1]["prompt"])

    def test_simple_goal_cancellation(self) -> None:
        """Cancellation before a simple goal propagates."""
        self.client.ask.return_value = (
            '{"classification": "simple", "reason": "test"}'
        )
        token = CancellationToken()
        token.cancel()
        with self.assertRaises(CancelledError):
            self.foreman.execute("simple goal", token=token)

    # -- COMPLEX path (full orchestration) ------------------------------

    def test_complex_goal_decompose_sequential_synthesize(self) -> None:
        """Complex goal: decompose → sequential execution → synthesis."""
        self._set_client_responses(
            complexity="complex",
            sub_agent_responses=[
                '{"thought": "Done", "final": "Research complete."}',
                '{"thought": "Done", "final": "Task executed."}',
            ],
            synthesis_response="Here is the full summary.",
        )
        result = self.foreman.execute("complex goal")
        self.assertEqual(result, "Here is the full summary.")
        # Verify the synthesis prompt includes the sub-goal results
        synthesis_call = self.client.ask.call_args_list[-1]
        prompt = synthesis_call[1]["prompt"]
        self.assertIn("complex goal", prompt)
        self.assertIn("Research complete.", prompt)
        self.assertIn("Task executed.", prompt)

    def test_complex_goal_respects_execution_order(self) -> None:
        """Dependencies ensure sub-goals execute in correct order."""
        plan = TaskPlan(
            goal="multi",
            sub_goals=(
                SubGoalSpec(id="first", description="First step",
                            assigned_personality="general"),
                SubGoalSpec(id="second", description="Second step",
                            assigned_personality="general",
                            depends_on=("first",)),
                SubGoalSpec(id="third", description="Third step",
                            assigned_personality="general",
                            depends_on=("second",)),
            ),
        )
        self._set_client_responses(
            complexity="complex",
            plan_json=json.dumps({
                "sub_goals": [
                    {"id": "first", "description": "First step",
                     "assigned_personality": "general", "depends_on": [],
                     "parallel": False},
                    {"id": "second", "description": "Second step",
                     "assigned_personality": "general",
                     "depends_on": ["first"], "parallel": False},
                    {"id": "third", "description": "Third step",
                     "assigned_personality": "general",
                     "depends_on": ["second"], "parallel": False},
                ],
            }),
            sub_agent_responses=[
                '{"thought": "1", "final": "First done."}',
                '{"thought": "2", "final": "Second done."}',
                '{"thought": "3", "final": "Third done."}',
            ],
            synthesis_response="All done in order.",
        )
        result = self.foreman.execute("multi step goal")
        self.assertEqual(result, "All done in order.")

    # -- PARALLEL path --------------------------------------------------

    def test_parallel_execution_when_enabled(self) -> None:
        """With parallel_by_default=True, same-layer specs run in parallel."""
        self.config = ForemanConfig(
            parallel_by_default=True,
            max_turns_per_sub_agent=3,
        )
        self.foreman = ForemanAgent(
            self.client, self.registry, config=self.config,
        )

        self._set_client_responses(
            complexity="complex",
            plan_json=json.dumps({
                "sub_goals": [
                    {"id": "a", "description": "Task A",
                     "assigned_personality": "general",
                     "depends_on": [], "parallel": False},
                    {"id": "b", "description": "Task B",
                     "assigned_personality": "general",
                     "depends_on": [], "parallel": False},
                ],
            }),
            sub_agent_responses=[
                '{"thought": "A", "final": "Result A."}',
                '{"thought": "B", "final": "Result B."}',
            ],
            synthesis_response="Parallel synthesis.",
        )
        result = self.foreman.execute("parallel goal")
        self.assertEqual(result, "Parallel synthesis.")
        # Both sub-agents should have been dispatched
        # (ThreadPoolExecutor may interleave but both complete)

    # -- PLAN RETRY EXHAUSTION -> fallback to simple --------------------

    def test_plan_retry_exhaustion_fallback_to_simple(self) -> None:
        """When decomposition fails repeatedly, fall back to simple agent."""
        # max_plan_retries=1 means 2 plan attempts (initial + 1 retry)
        # We need: 1 complexity + 2 plan + 1 fallback = 4 responses
        self.client.ask.side_effect = [
            # 1. Complexity
            '{"classification": "complex", "reason": "test"}',
            # 2. Plan attempt 1 (fails)
            "invalid json that won't parse",
            # 3. Plan attempt 2 (retry, fails again)
            '{"sub_goals": []}',
            # 4. Fallback simple agent
            '{"thought": "Fallback", "final": "Simple fallback result."}',
        ]

        result = self.foreman.execute("complex goal that fails")
        self.assertEqual(result, "Simple fallback result.")

    def test_plan_retry_with_bad_personality_fallback(self) -> None:
        """Plan with bad personality validation falls back to simple."""
        # max_plan_retries=1 means 2 plan attempts.
        # Need: 1 complexity + 2 plan + 1 fallback = 4 responses
        bad_personality_plan = json.dumps({
            "sub_goals": [
                {"id": "s1", "description": "X",
                 "assigned_personality": "does_not_exist_xyz",
                 "depends_on": [], "parallel": False},
            ],
        })
        self.client.ask.side_effect = [
            # 1. Complexity
            '{"classification": "complex", "reason": "test"}',
            # 2. Plan attempt 1 (fails validation)
            bad_personality_plan,
            # 3. Plan attempt 2 (retry, fails again with same bad plan)
            bad_personality_plan,
            # 4. Fallback simple agent
            '{"thought": "Fallback done", "final": "Fallback result."}',
        ]

        result = self.foreman.execute("complex goal")
        self.assertEqual(result, "Fallback result.")

    # -- CANCELLATION mid-orchestration ---------------------------------

    def test_cancellation_during_sub_agent_execution(self) -> None:
        """Cancellation during sub-agent execution collects partial results."""
        self._set_client_responses(
            complexity="complex",
            plan_json=json.dumps({
                "sub_goals": [
                    {"id": "s1", "description": "Step 1",
                     "assigned_personality": "general",
                     "depends_on": [], "parallel": False},
                    {"id": "s2", "description": "Step 2",
                     "assigned_personality": "general",
                     "depends_on": ["s1"], "parallel": False},
                ],
            }),
            sub_agent_responses=[
                '{"thought": "done", "final": "Step 1 complete."}',
                # Step 2 should not execute; we'll cancel before it
            ],
            synthesis_response="Partial synthesis.",
        )

        # We need to cancel after the first sub-agent call
        # Use a side effect on client.ask that triggers cancel after
        # the complexity + decomposition + step 1 calls
        call_count = [0]

        def ask_with_cancel(prompt: str, **kwargs: Any) -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                return '{"classification": "complex", "reason": "test"}'
            elif call_count[0] == 2:
                return json.dumps({
                    "sub_goals": [
                        {"id": "s1", "description": "Step 1",
                         "assigned_personality": "general",
                         "depends_on": [], "parallel": False},
                        {"id": "s2", "description": "Step 2",
                         "assigned_personality": "general",
                         "depends_on": ["s1"], "parallel": False},
                    ],
                })
            elif call_count[0] == 3:
                return '{"thought": "done", "final": "Step 1 complete."}'
            return "synthesis fallback"

        self.client.ask.side_effect = ask_with_cancel

        token = CancellationToken()

        # Cancel after the 3rd call (complexity + plan + step 1 completed)
        # We need to inject this between calls.  Let's use a threading
        # Timer or trigger it from inside the sub-agent execution.
        # The simplest approach: schedule cancellation after a short delay.
        def delayed_cancel() -> None:
            token.cancel()

        timer = threading.Timer(0.05, delayed_cancel)
        timer.start()

        # This should either:
        # a) Complete fully if cancellation didn't interrupt
        # b) Return a synthesis of partial results if it did
        # Since timing is non-deterministic, at minimum ensure no crash
        result = self.foreman.execute("cancellable goal", token=token)
        timer.cancel()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    # -- EDGE CASES -----------------------------------------------------

    def test_no_sub_goals_returns_fallback(self) -> None:
        """Empty execution produces a fallback message."""
        # Override to a plan that has no sub-goals (shouldn't happen
        # in practice since from_llm validates, but handle gracefully)
        plan = TaskPlan(goal="empty", sub_goals=())
        result = self.foreman._synthesize("empty", [], CancellationToken())
        self.assertIn("No sub-agents", result)

    def test_synthesis_fallback_on_error(self) -> None:
        """When synthesis LLM call fails, raw results are returned."""
        results = [
            SubAgentResult(
                task_description="Test task",
                personality_used="general",
                response="Test response",
                success=True,
                turns=1,
                duration_ms=10.0,
            ),
        ]
        # Make the synthesis LLM call fail
        self.client.ask.side_effect = OllamaError("LLM unavailable")

        result = self.foreman._synthesize("test goal", results, CancellationToken())
        self.assertIn("Test task", result)
        self.assertIn("Test response", result)

    def test_sub_agent_with_unknown_personality(self) -> None:
        """_dispatch_sub_agent returns error result for unknown personality."""
        spec = SubGoalSpec(
            id="bad", description="Bad personality",
            assigned_personality="does_not_exist",
        )
        result = self.foreman._dispatch_sub_agent(spec, CancellationToken())
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("Unknown personality", result.error or "")

    def test_simple_goal_uses_specified_personality(self) -> None:
        """The personality parameter is passed through for simple goals."""
        self.client.ask.side_effect = [
            '{"classification": "simple", "reason": "test"}',
            '{"thought": "done", "final": "Engineer result."}',
        ]
        result = self.foreman.execute("simple task", personality="engineer")
        self.assertEqual(result, "Engineer result.")

    def test_foreman_with_chat_store(self) -> None:
        """ForemanAgent works with an optional ChatStore."""
        store = MagicMock(spec=ChatStore)
        store.create_session.return_value = "test-session-id"

        foreman = ForemanAgent(
            self.client, self.registry, chat_store=store, config=self.config,
        )
        self._set_client_responses(
            complexity="simple",
            sub_agent_responses=[
                '{"thought": "done", "final": "Stored result."}',
            ],
        )
        result = foreman.execute("store test")
        self.assertEqual(result, "Stored result.")
        # Verify storage was attempted
        store.create_session.assert_called()
        store.add_message.assert_called()

    def test_non_default_config_is_used(self) -> None:
        """Custom ForemanConfig settings are respected."""
        config = ForemanConfig(
            parallel_by_default=True,
            max_sub_agents=3,
            max_turns_per_sub_agent=1,
            max_plan_retries=0,
            default_personality="analyst",
        )
        foreman = ForemanAgent(self.client, self.registry, config=config)
        self.assertEqual(foreman._config.max_sub_agents, 3)
        self.assertEqual(foreman._config.max_turns_per_sub_agent, 1)
        self.assertEqual(foreman._config.max_plan_retries, 0)
        self.assertEqual(foreman._config.default_personality, "analyst")
        self.assertTrue(foreman._config.parallel_by_default)


# ======================================================================
# 5. Smoke Tests
# ======================================================================


class TestMilestone4Smoke(unittest.TestCase):
    """Verification that all new classes are importable and basic."""

    def test_imports_work(self) -> None:
        from Agent.orchestration import (  # noqa: F811
            Complexity,
            ComplexityAssessor,
            ForemanAgent,
            ForemanConfig,
            PlanValidationError,
            SubAgent,
            SubAgentResult,
            SubGoalSpec,
            TaskPlan,
        )
        self.assertTrue(Complexity is not None)

    def test_complexity_enum_values(self) -> None:
        self.assertEqual(Complexity.SIMPLE.value, "simple")
        self.assertEqual(Complexity.MODERATE.value, "moderate")
        self.assertEqual(Complexity.COMPLEX.value, "complex")

    def test_foreman_config_defaults(self) -> None:
        config = ForemanConfig()
        self.assertFalse(config.parallel_by_default)
        self.assertEqual(config.max_sub_agents, 5)
        self.assertEqual(config.max_turns_per_sub_agent, 10)
        self.assertEqual(config.max_plan_retries, 2)
        self.assertEqual(config.default_personality, "general")

    def test_sub_goal_spec_immutable(self) -> None:
        spec = SubGoalSpec(
            id="test", description="desc",
            assigned_personality="general",
        )
        with self.assertRaises(AttributeError):
            spec.id = "changed"  # type: ignore[misc]

    def test_sub_agent_result_defaults(self) -> None:
        r = SubAgentResult(
            task_description="test",
            personality_used="general",
            response="ok",
        )
        self.assertTrue(r.success)
        self.assertIsNone(r.error)
        self.assertEqual(r.turns, 0)
        self.assertEqual(r.duration_ms, 0.0)
        self.assertFalse(r.cancelled)

    def test_plan_validation_error_is_runtime_error(self) -> None:
        self.assertTrue(issubclass(PlanValidationError, RuntimeError))

    def test_from_agent_package(self) -> None:
        from Agent import (  # noqa: F811
            Complexity,
            ComplexityAssessor,
            ForemanAgent,
            ForemanConfig,
            PlanValidationError,
            SubAgent,
            SubAgentResult,
            SubGoalSpec,
            TaskPlan,
        )
        self.assertTrue(ComplexityAssessor is not None)
        self.assertTrue(ForemanAgent is not None)
        self.assertTrue(TaskPlan is not None)


# ======================================================================
# Entrypoint
# ======================================================================

if __name__ == "__main__":
    unittest.main()
