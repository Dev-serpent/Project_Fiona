"""Tests for macro branching runner (run_macro_steps) and variable interpolation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from FionaCore import (
    ActionResult,
    ActionRouter,
    MacroStep,
    load_macros,
    run_macro_steps,
    save_macro,
)
from FionaCore.macro_engine import (
    MAX_GOTO_DEPTH,
    _atomic_write_json,
    _resolve_variables,
)


# ---------------------------------------------------------------------------
# Helper: create a mock router that returns a successful result for any action
# ---------------------------------------------------------------------------


def _mock_router() -> MagicMock:
    """Return a MagicMock ActionRouter whose ``.run()`` always succeeds.

    The returned ActionResult will carry the action name that was passed in.
    ``router.run`` is a ``MagicMock`` so callers can ``reset_mock()`` etc.
    """
    router = MagicMock(spec=ActionRouter)
    router.specs = {}

    def mock_run(name: str, **kwargs: object) -> ActionResult:
        return ActionResult(ok=True, action=name, detail="mocked")

    router.run = MagicMock(side_effect=mock_run)
    return router


# ---------------------------------------------------------------------------
# Atomic write helper
# ---------------------------------------------------------------------------


class AtomicWriteTests(unittest.TestCase):
    def test_atomic_write_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            data = {"key": "value", "num": 42}
            _atomic_write_json(path, data)
            self.assertTrue(path.exists())
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, data)

    def test_atomic_write_sets_private_perms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private.json"
            _atomic_write_json(path, {"a": 1})
            mode = path.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_atomic_write_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overwrite.json"
            path.write_text('{"old": true}', encoding="utf-8")
            _atomic_write_json(path, {"new": True})
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("new", loaded)
            self.assertNotIn("old", loaded)


# ---------------------------------------------------------------------------
# Variable interpolation
# ---------------------------------------------------------------------------


class ResolveVariablesTests(unittest.TestCase):
    """_resolve_variables — interpolation of ${placeholders} in MacroStep fields."""

    def test_no_variables_returns_unchanged(self) -> None:
        step = MacroStep("host.status", wait_type="sleep", wait_value="500")
        resolved = _resolve_variables(step, {})
        self.assertEqual(resolved.action, "host.status")
        self.assertEqual(resolved.wait_value, "500")
        self.assertIsNone(resolved.condition_value)
        self.assertIsNone(resolved.fallback_action)

    def test_basic_substitution(self) -> None:
        step = MacroStep("${action_name}", condition_value="check_${target}")
        ctx = {"_variables": {"action_name": "host.status", "target": "python3"}}
        resolved = _resolve_variables(step, ctx)
        self.assertEqual(resolved.action, "host.status")
        self.assertEqual(resolved.condition_value, "check_python3")

    def test_unknown_variable_leaves_placeholder(self) -> None:
        step = MacroStep("${unknown_var}")
        resolved = _resolve_variables(step, {})
        # safe_substitute leaves ${unknown_var} unchanged
        self.assertEqual(resolved.action, "${unknown_var}")

    def test_step_index_is_available(self) -> None:
        step = MacroStep("step_${step_index}")
        ctx = {"_step_index": 3}
        resolved = _resolve_variables(step, ctx)
        self.assertEqual(resolved.action, "step_3")

    def test_last_result_variables_when_no_results(self) -> None:
        step = MacroStep("action_${last_result}_${last_ok}")
        ctx = {"_results": []}
        resolved = _resolve_variables(step, ctx)
        self.assertEqual(resolved.action, "action__False")

    def test_last_result_variables_with_results(self) -> None:
        results = [ActionResult(ok=True, action="test", detail="works")]
        step = MacroStep("prev=${last_result}_ok=${last_ok}")
        ctx = {"_results": results}
        resolved = _resolve_variables(step, ctx)
        self.assertIn("prev=", resolved.action)
        self.assertIn("ok=True", resolved.action)

    def test_substitution_in_fallback_action(self) -> None:
        step = MacroStep(
            action="primary",
            fallback_action="${fallback_name}",
        )
        ctx = {"_variables": {"fallback_name": "host.status"}}
        resolved = _resolve_variables(step, ctx)
        self.assertEqual(resolved.fallback_action, "host.status")

    def test_substitution_in_wait_value(self) -> None:
        step = MacroStep(
            action="test",
            wait_type="sleep",
            wait_value="${delay_ms}",
        )
        ctx = {"_variables": {"delay_ms": "2000"}}
        resolved = _resolve_variables(step, ctx)
        self.assertEqual(resolved.wait_value, "2000")

    def test_none_fields_remain_none(self) -> None:
        step = MacroStep("test")
        ctx = {"_variables": {"x": "y"}}
        resolved = _resolve_variables(step, ctx)
        self.assertIsNone(resolved.wait_type)
        self.assertIsNone(resolved.wait_value)
        self.assertIsNone(resolved.condition_type)
        self.assertIsNone(resolved.condition_value)
        self.assertIsNone(resolved.fallback_action)

    def test_multiple_substitutions_in_single_field(self) -> None:
        step = MacroStep("${a}_${b}_${c}")
        ctx = {"_variables": {"a": "x", "b": "y", "c": "z"}}
        resolved = _resolve_variables(step, ctx)
        self.assertEqual(resolved.action, "x_y_z")

    def test_empty_variables_dict(self) -> None:
        step = MacroStep("constant_action")
        resolved = _resolve_variables(step, {"_variables": {}})
        self.assertEqual(resolved.action, "constant_action")

    def test_special_chars_in_variable_name(self) -> None:
        step = MacroStep("${var_with_underscore}")
        ctx = {"_variables": {"var_with_underscore": "ok"}}
        resolved = _resolve_variables(step, ctx)
        self.assertEqual(resolved.action, "ok")

    def test_non_string_variable_values(self) -> None:
        """Variables with non-string values are converted to str."""
        step = MacroStep("count=${num}")
        ctx = {"_variables": {"num": 42}}
        resolved = _resolve_variables(step, ctx)
        self.assertEqual(resolved.action, "count=42")


# ---------------------------------------------------------------------------
# run_macro_steps — basic orchestration
# ---------------------------------------------------------------------------


class RunMacroStepsBasicTests(unittest.TestCase):
    """Core orchestration: steps without conditions/waits execute sequentially."""

    def setUp(self) -> None:
        self.router = _mock_router()

    def test_empty_steps_returns_empty_list(self) -> None:
        results = run_macro_steps([], self.router)
        self.assertEqual(results, [])

    def test_single_step_executes(self) -> None:
        results = run_macro_steps(
            [MacroStep("host.status")],
            self.router,
        )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertEqual(results[0].action, "host.status")

    def test_multiple_steps_execute_sequentially(self) -> None:
        results = run_macro_steps(
            [
                MacroStep("host.status"),
                MacroStep("camcoms.paths"),
                MacroStep("camcoms.smoke"),
            ],
            self.router,
        )
        self.assertEqual(len(results), 3)
        self.assertEqual([r.action for r in results], [
            "host.status",
            "camcoms.paths",
            "camcoms.smoke",
        ])
        self.assertTrue(all(r.ok for r in results))

    def test_backward_compat_no_waits_conditions(self) -> None:
        """Old-style steps without waits/conditions must behave identically."""
        old_style = [MacroStep("host.status"), MacroStep("camcoms.paths")]
        results = run_macro_steps(old_style, self.router)
        self.assertEqual(len(results), 2)
        self.assertEqual([r.action for r in results], ["host.status", "camcoms.paths"])
        self.assertTrue(all(r.ok for r in results))

    def test_empty_action_skips_step(self) -> None:
        """A step with an empty action after interpolation is skipped."""
        results = run_macro_steps(
            [MacroStep(""), MacroStep("host.status")],
            self.router,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "host.status")

    def test_passes_action_name_to_router(self) -> None:
        """The router.run() is called with the interpolated action name."""
        self.router.run.reset_mock()
        run_macro_steps(
            [MacroStep("host.status")],
            self.router,
        )
        self.router.run.assert_called_once_with("host.status")


# ---------------------------------------------------------------------------
# run_macro_steps — waits and conditions
# ---------------------------------------------------------------------------


class RunMacroStepsConditionTests(unittest.TestCase):
    """Condition met / not met / fallback behavior."""

    def setUp(self) -> None:
        self.router = _mock_router()

    def test_condition_met_runs_action(self) -> None:
        """When condition is met, action runs normally."""
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Terminal", title="bash"),
        ):
            step = MacroStep(
                action="host.status",
                condition_type="window_active",
                condition_value="Terminal",
            )
            results = run_macro_steps([step], self.router)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].action, "host.status")
            self.assertTrue(results[0].ok)

    def test_condition_not_met_with_fallback_runs_fallback(self) -> None:
        """When condition fails AND fallback exists → fallback runs."""
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Other", title="other"),
        ):
            step = MacroStep(
                action="camcoms.paths",
                condition_type="window_active",
                condition_value="Terminal",
                fallback_action="host.status",
            )
            results = run_macro_steps([step], self.router)
            self.assertEqual(len(results), 1)
            # Fallback ran instead of primary action
            self.assertEqual(results[0].action, "host.status")
            self.assertTrue(results[0].ok)

    def test_condition_not_met_without_fallback_skips(self) -> None:
        """When condition fails and NO fallback → step is skipped."""
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Other", title="other"),
        ):
            step = MacroStep(
                action="camcoms.paths",
                condition_type="window_active",
                condition_value="Terminal",
                # no fallback_action
            )
            results = run_macro_steps([step], self.router)
            self.assertEqual(len(results), 0)

    def test_router_not_called_when_condition_not_met_no_fallback(self) -> None:
        """Router.run is not called when condition fails and no fallback."""
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Other", title="other"),
        ):
            step = MacroStep(
                action="should_not_run",
                condition_type="window_active",
                condition_value="Target",
            )
            self.router.run.reset_mock()
            run_macro_steps([step], self.router)
            self.router.run.assert_not_called()

    def test_mixed_conditions_and_plain_steps(self) -> None:
        """Some steps have conditions, some don't — correct orchestration."""
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Browser", title="web"),
        ):
            steps = [
                MacroStep("host.status"),  # no condition → always runs
                MacroStep(  # condition met → runs
                    action="camcoms.paths",
                    condition_type="window_active",
                    condition_value="Browser",
                ),
                MacroStep(  # condition not met, fallback runs
                    action="camcoms.smoke",
                    condition_type="window_active",
                    condition_value="Terminal",
                    fallback_action="host.status",
                ),
            ]
            results = run_macro_steps(steps, self.router)
            self.assertEqual(len(results), 3)
            self.assertEqual(results[0].action, "host.status")
            self.assertEqual(results[1].action, "camcoms.paths")
            # fallback ran
            self.assertEqual(results[2].action, "host.status")

    def test_action_result_condition(self) -> None:
        """action_result condition checks previous results."""
        steps = [
            MacroStep("camcoms.smoke"),
            MacroStep(
                action="host.restart",
                condition_type="action_result",
                condition_value="camcoms.smoke:ok",
                fallback_action="host.status",
            ),
        ]
        results = run_macro_steps(steps, self.router)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].action, "camcoms.smoke")
        self.assertTrue(results[0].ok)
        # Condition was met (camcoms.smoke returned ok), so host.restart ran
        self.assertEqual(results[1].action, "host.restart")

    def test_action_result_condition_not_met_triggers_fallback(self) -> None:
        """When action_result condition fails, fallback runs."""
        steps = [
            MacroStep("camcoms.smoke"),
            MacroStep(
                action="should_not_run",
                condition_type="action_result",
                condition_value="camcoms.smoke:failed",
                fallback_action="host.status",
            ),
        ]
        results = run_macro_steps(steps, self.router)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].action, "host.status")


# ---------------------------------------------------------------------------
# run_macro_steps — wait integration
# ---------------------------------------------------------------------------


class RunMacroStepsWaitTests(unittest.TestCase):
    """Wait operations integrated into the runner."""

    def setUp(self) -> None:
        self.router = _mock_router()

    def test_sleep_wait_is_executed_before_action(self) -> None:
        """A sleep wait delays execution before the action."""
        step = MacroStep("host.status", wait_type="sleep", wait_value="100")
        import time
        start = time.monotonic()
        results = run_macro_steps([step], self.router)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.08)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "host.status")

    @patch("FionaCore.macro_engine._wait_for_window", return_value=True)
    def test_wait_for_window_called(self, mock_wait: MagicMock) -> None:
        step = MacroStep(
            "host.status",
            wait_type="wait_for_window",
            wait_value="Brave",
        )
        run_macro_steps([step], self.router)
        mock_wait.assert_called_once_with("Brave", timeout=30)

    @patch("FionaCore.macro_engine._wait_for_process", return_value=True)
    def test_wait_for_process_called(self, mock_wait: MagicMock) -> None:
        step = MacroStep(
            "host.status",
            wait_type="wait_for_process",
            wait_value="python3",
        )
        run_macro_steps([step], self.router)
        mock_wait.assert_called_once_with("python3", timeout=30)

    def test_waits_with_conditions_compose(self) -> None:
        """Wait THEN condition THEN action — all three orchestrated."""
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Terminal", title=""),
        ):
            step = MacroStep(
                action="host.status",
                wait_type="sleep",
                wait_value="50",
                condition_type="window_active",
                condition_value="Terminal",
            )
            results = run_macro_steps([step], self.router)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].ok)

    def test_sleep_wait_value_from_variable(self) -> None:
        """Wait value can come from variable interpolation."""
        import time
        step = MacroStep(
            action="host.status",
            wait_type="sleep",
            wait_value="${delay}",
        )
        start = time.monotonic()
        results = run_macro_steps(
            [step],
            self.router,
            variables={"delay": "80"},
        )
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.05)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)


# ---------------------------------------------------------------------------
# run_macro_steps — variable interpolation integration
# ---------------------------------------------------------------------------


class RunMacroStepsVariableTests(unittest.TestCase):
    """Variables passed into the runner are resolved before execution."""

    def setUp(self) -> None:
        self.router = _mock_router()

    def test_variable_substitution_in_action(self) -> None:
        steps = [MacroStep("${action_name}")]
        results = run_macro_steps(
            steps,
            self.router,
            variables={"action_name": "host.status"},
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "host.status")

    def test_variable_substitution_in_condition_value(self) -> None:
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="MyApp", title=""),
        ):
            step = MacroStep(
                action="host.status",
                condition_type="window_active",
                condition_value="${target_window}",
            )
            results = run_macro_steps(
                [step],
                self.router,
                variables={"target_window": "MyApp"},
            )
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].ok)

    def test_variable_substitution_in_fallback(self) -> None:
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Other", title="other"),
        ):
            step = MacroStep(
                action="primary.action",
                condition_type="window_active",
                condition_value="TargetWindow",
                fallback_action="${fallback}",
            )
            results = run_macro_steps(
                [step],
                self.router,
                variables={"fallback": "host.status"},
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].action, "host.status")

    def test_step_index_variable_available(self) -> None:
        steps = [
            MacroStep("step_${step_index}"),
            MacroStep("step_${step_index}"),
        ]
        results = run_macro_steps(steps, self.router)
        self.assertEqual(results[0].action, "step_0")
        self.assertEqual(results[1].action, "step_1")

    def test_variable_not_found_leaves_placeholder(self) -> None:
        """When an undefined variable is not found, the placeholder is left
        unchanged and the action runs with the literal placeholder string."""
        steps = [MacroStep("${undefined_var}")]
        results = run_macro_steps(steps, self.router)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "${undefined_var}")


# ---------------------------------------------------------------------------
# GOTO branching
# ---------------------------------------------------------------------------

# The GOTO handler inside run_macro_steps does a lazy import:
#   from FionaCore.macros import load_macros as _load_macros
# So we must mock FionaCore.macros.load_macros for GOTO tests.


class GotoTests(unittest.TestCase):
    """GOTO support in run_macro_steps — jumping to another macro."""

    def setUp(self) -> None:
        self.router = _mock_router()

    @patch("FionaCore.macros.load_macros")
    def test_goto_branches_to_target_macro(self, mock_load: MagicMock) -> None:
        """When action is GOTO:other, execution continues in target macro."""
        target_steps = [MacroStep("host.status"), MacroStep("camcoms.paths")]
        mock_load.return_value = {"other": target_steps}

        steps = [MacroStep("GOTO:other")]
        results = run_macro_steps(steps, self.router)
        # GOTO step itself (action ran) + 2 target steps
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0].action.startswith("GOTO:"))
        self.assertEqual(results[1].action, "host.status")
        self.assertEqual(results[2].action, "camcoms.paths")

    @patch("FionaCore.macros.load_macros")
    def test_goto_nonexistent_logs_warning_and_continues(self, mock_load: MagicMock) -> None:
        """GOTO to a macro that doesn't exist logs a warning and continues."""
        mock_load.return_value = {}

        steps = [
            MacroStep("GOTO:does_not_exist"),
            MacroStep("host.status"),
        ]
        results = run_macro_steps(steps, self.router)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].action, "host.status")

    @patch("FionaCore.macros.load_macros")
    def test_circular_goto_is_detected_and_stopped(self, mock_load: MagicMock) -> None:
        """Circular GOTO triggers depth limit and stops."""
        loop_steps = [MacroStep("GOTO:loop")]
        mock_load.return_value = {"loop": loop_steps}

        steps = [MacroStep("GOTO:loop")]
        results = run_macro_steps(steps, self.router)
        # Should have the initial GOTO + up to MAX_GOTO_DEPTH iterations
        self.assertLessEqual(len(results), MAX_GOTO_DEPTH + 1)
        # All actions should start with GOTO:
        for r in results:
            self.assertTrue(r.action.startswith("GOTO:"))

    @patch("FionaCore.macros.load_macros")
    def test_goto_empty_target_skipped(self, mock_load: MagicMock) -> None:
        """GOTO: with no macro name is skipped."""
        steps = [
            MacroStep("GOTO:"),
            MacroStep("host.status"),
        ]
        results = run_macro_steps(steps, self.router)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].action, "host.status")

    @patch("FionaCore.macros.load_macros")
    def test_goto_with_variable_interpolation(self, mock_load: MagicMock) -> None:
        """GOTO target can come from variable interpolation."""
        target_steps = [MacroStep("host.status")]
        mock_load.return_value = {"target_macro": target_steps}

        steps = [MacroStep("GOTO:${macro_name}")]
        results = run_macro_steps(
            steps,
            self.router,
            variables={"macro_name": "target_macro"},
        )
        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0].action, "GOTO:target_macro")
        self.assertEqual(results[1].action, "host.status")

    @patch("FionaCore.macros.load_macros")
    def test_goto_after_regular_steps(self, mock_load: MagicMock) -> None:
        """Regular steps execute before GOTO is triggered."""
        target_steps = [MacroStep("camcoms.paths")]
        mock_load.return_value = {"target": target_steps}

        steps = [
            MacroStep("host.status"),
            MacroStep("GOTO:target"),
        ]
        results = run_macro_steps(steps, self.router)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].action, "host.status")
        self.assertTrue(results[1].action.startswith("GOTO:"))
        self.assertEqual(results[2].action, "camcoms.paths")


# ---------------------------------------------------------------------------
# Full integration
# ---------------------------------------------------------------------------


class FullIntegrationTests(unittest.TestCase):
    """End-to-end scenario combining all features."""

    def setUp(self) -> None:
        self.router = _mock_router()

    def test_complex_macro_with_all_features(self) -> None:
        """A complex macro that uses variables, waits, conditions, and fallbacks."""
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Browser", title="web"),
        ):
            steps = [
                # Step 0: Simple wait then action
                MacroStep(
                    "host.status",
                    wait_type="sleep",
                    wait_value="20",
                ),
                # Step 1: Condition met → action runs
                MacroStep(
                    "camcoms.paths",
                    condition_type="window_active",
                    condition_value="Browser",
                ),
                # Step 2: Condition not met → fallback runs
                MacroStep(
                    "camcoms.smoke",
                    condition_type="window_active",
                    condition_value="Terminal",
                    fallback_action="host.status",
                ),
            ]
            results = run_macro_steps(steps, self.router)
            self.assertEqual(len(results), 3)
            self.assertEqual(results[0].action, "host.status")
            self.assertEqual(results[1].action, "camcoms.paths")
            # Fallback ran
            self.assertEqual(results[2].action, "host.status")
            self.assertTrue(all(r.ok for r in results))

    def test_variables_persist_across_steps(self) -> None:
        """Variables dict remains available for all steps."""
        steps = [
            MacroStep("${first_action}"),
            MacroStep("${second_action}"),
        ]
        results = run_macro_steps(
            steps,
            self.router,
            variables={
                "first_action": "host.status",
                "second_action": "camcoms.paths",
            },
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].action, "host.status")
        self.assertEqual(results[1].action, "camcoms.paths")


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

# _handle_list_macros() calls load_macros() imported from FionaCore at module
# level in cli.py.  _handle_run_macro() calls load_macros() from FionaCore
# at module level, and run_macro_steps internally imports from
# FionaCore.macros.  We mock the relevant paths.


class CliMacroFlagsTests(unittest.TestCase):
    """Test that --run-macro and --list-macros CLI flags work.

    Notes
    -----
    ``fiona/__init__.py`` imports ``TerminalAssist`` which requires ``pynput``.
    That package is not installed in the test environment, so we pre-seed
    ``sys.modules`` with a fake ``pynput`` before importing ``fiona.cli``.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import sys as _sys
        cls._module_patches = [
            patch.dict(_sys.modules, {
                # TerminalAssist needs pynput
                "pynput": MagicMock(),
                "pynput.mouse": MagicMock(),
                "pynput.keyboard": MagicMock(),
                # Vsee needs pandas / numpy
                "pandas": MagicMock(),
                "numpy": MagicMock(),
            }),
        ]
        for p in cls._module_patches:
            p.start()

    @classmethod
    def tearDownClass(cls) -> None:
        for p in cls._module_patches:
            p.stop()

    def test_list_macros_flag(self) -> None:
        """--list-macros loads macros and prints them."""
        from fiona.cli import _handle_list_macros

        import io
        import sys
        with patch("fiona.cli.load_macros") as mock_load:
            mock_load.return_value = {
                "alpha": [MacroStep("a1"), MacroStep("a2")],
                "beta": [MacroStep("b1")],
            }
            captured = io.StringIO()
            with patch.object(sys, "stdout", captured):
                _handle_list_macros()

        output = captured.getvalue()
        self.assertIn("alpha", output)
        self.assertIn("beta", output)
        self.assertIn("2 step(s)", output)
        self.assertIn("1 step(s)", output)
        self.assertIn("Total macros: 2", output)

    def test_run_macro_flag_runs_and_reports(self) -> None:
        """--run-macro loads, runs, and prints summary."""
        from fiona.cli import _handle_run_macro

        import io
        import sys
        with patch("fiona.cli.load_macros") as mock_cli_load:
            mock_cli_load.return_value = {
                "test": [
                    MacroStep("host.status"),
                    MacroStep("camcoms.paths"),
                ],
            }
            with patch("fiona.cli.run_macro_steps") as mock_runner:
                mock_runner.return_value = [
                    ActionResult(ok=True, action="host.status", detail="ok"),
                    ActionResult(ok=True, action="camcoms.paths", detail="ok"),
                ]
                captured = io.StringIO()
                with patch.object(sys, "stdout", captured):
                    _handle_run_macro("test")

        output = captured.getvalue()
        self.assertIn("[0]", output)
        self.assertIn("[1]", output)
        self.assertIn("OK", output)
        self.assertIn("Macro 'test' executed 2 steps", output)
        self.assertIn("2 succeeded, 0 failed", output)

    def test_run_macro_unknown_exits(self) -> None:
        """Running an unknown macro raises SystemExit."""
        from fiona.cli import _handle_run_macro

        with patch("fiona.cli.load_macros") as mock_load:
            mock_load.return_value = {}
            with self.assertRaises(SystemExit) as ctx:
                _handle_run_macro("nonexistent")
        self.assertIn("unknown macro", str(ctx.exception))

    def test_list_macros_empty(self) -> None:
        """--list-macros with no macros prints appropriate message."""
        from fiona.cli import _handle_list_macros

        import io
        import sys
        with patch("fiona.cli.load_macros") as mock_load:
            mock_load.return_value = {}
            captured = io.StringIO()
            with patch.object(sys, "stdout", captured):
                _handle_list_macros()

        output = captured.getvalue()
        self.assertIn("No macros found", output)


# ---------------------------------------------------------------------------
# Context _results tracking
# ---------------------------------------------------------------------------


class ContextResultsTrackingTests(unittest.TestCase):
    """Results are tracked correctly in the context."""

    def setUp(self) -> None:
        self.router = _mock_router()

    def test_results_appended_in_order(self) -> None:
        steps = [
            MacroStep("host.status"),
            MacroStep("camcoms.paths"),
        ]
        results = run_macro_steps(steps, self.router)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].action, "host.status")
        self.assertEqual(results[1].action, "camcoms.paths")

    def test_fallback_result_appended(self) -> None:
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Other", title="other"),
        ):
            step = MacroStep(
                action="primary",
                condition_type="window_active",
                condition_value="Target",
                fallback_action="host.status",
            )
            results = run_macro_steps([step], self.router)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].action, "host.status")

    def test_skipped_step_not_in_results(self) -> None:
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Other", title="other"),
        ):
            step = MacroStep(
                action="should_not_run",
                condition_type="window_active",
                condition_value="Target",
                # no fallback
            )
            results = run_macro_steps([step], self.router)
            self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
