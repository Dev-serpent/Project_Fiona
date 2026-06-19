"""Tests for Macro Engine v2 — waits, conditions, branching, and backwards compat."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from FionaCore import (
    ActionResult,
    ActionRouter,
    MacroStep,
    evaluate_condition,
    execute_step_with_waits,
    load_macros,
    save_macro,
)
from FionaCore.macro_engine import _wait_for_process, _wait_for_window


class MacroStepTests(unittest.TestCase):
    """MacroStep dataclass — extensions and backward compatibility."""

    def test_basic_step_still_works(self) -> None:
        step = MacroStep("host.status")
        self.assertEqual(step.action, "host.status")
        self.assertIsNone(step.wait_type)
        self.assertIsNone(step.wait_value)
        self.assertIsNone(step.condition_type)
        self.assertIsNone(step.condition_value)
        self.assertIsNone(step.fallback_action)

    def test_to_dict_old_format(self) -> None:
        step = MacroStep("host.status")
        self.assertEqual(step.to_dict(), {"action": "host.status"})

    def test_to_dict_skips_none_fields(self) -> None:
        step = MacroStep("host.status", wait_type="sleep", wait_value="2000")
        d = step.to_dict()
        self.assertIn("wait_type", d)
        self.assertIn("wait_value", d)
        self.assertNotIn("condition_type", d)
        self.assertNotIn("condition_value", d)
        self.assertNotIn("fallback_action", d)

    def test_to_dict_full(self) -> None:
        step = MacroStep(
            action="host.restart",
            wait_type="wait_for_window",
            wait_value="Brave",
            condition_type="process_running",
            condition_value="python3",
            fallback_action="host.status",
        )
        expected = {
            "action": "host.restart",
            "wait_type": "wait_for_window",
            "wait_value": "Brave",
            "condition_type": "process_running",
            "condition_value": "python3",
            "fallback_action": "host.status",
        }
        self.assertEqual(step.to_dict(), expected)

    def test_from_dict_old_format(self) -> None:
        step = MacroStep.from_dict({"action": "host.status"})
        self.assertEqual(step.action, "host.status")
        self.assertIsNone(step.wait_type)

    def test_from_dict_full(self) -> None:
        data = {
            "action": "host.restart",
            "wait_type": "sleep",
            "wait_value": "3000",
            "condition_type": "window_active",
            "condition_value": "Terminal",
            "fallback_action": "host.status",
        }
        step = MacroStep.from_dict(data)
        self.assertEqual(step.action, "host.restart")
        self.assertEqual(step.wait_type, "sleep")
        self.assertEqual(step.wait_value, "3000")
        self.assertEqual(step.condition_type, "window_active")
        self.assertEqual(step.condition_value, "Terminal")
        self.assertEqual(step.fallback_action, "host.status")

    def test_from_dict_extra_keys_ignored(self) -> None:
        step = MacroStep.from_dict({"action": "test", "unknown": "value"})
        self.assertEqual(step.action, "test")
        self.assertIsNone(step.wait_type)

    def test_from_dict_empty_action_defaults(self) -> None:
        step = MacroStep.from_dict({})
        self.assertEqual(step.action, "")

    def test_frozen_cannot_be_modified(self) -> None:
        step = MacroStep("test")
        with self.assertRaises(AttributeError):
            step.action = "other"  # type: ignore[misc]

    def test_round_trip_identity(self) -> None:
        original = MacroStep(
            action="a.b",
            wait_type="wait_for_window",
            wait_value="Brave",
            condition_type="process_running",
            condition_value="python3",
            fallback_action="a.c",
        )
        reconstructed = MacroStep.from_dict(original.to_dict())
        self.assertEqual(original, reconstructed)


class MacroStorageTests(unittest.TestCase):
    """load_macros / save_macro with extended fields."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "macros.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_and_load_basic(self) -> None:
        steps = [MacroStep("host.status"), MacroStep("camcoms.paths")]
        save_macro("test", steps, path=self.path)
        loaded = load_macros(self.path)
        self.assertIn("test", loaded)
        self.assertEqual(len(loaded["test"]), 2)
        self.assertEqual(loaded["test"][0].action, "host.status")

    def test_save_and_load_with_waits_and_conditions(self) -> None:
        steps = [
            MacroStep("host.status"),
            MacroStep(
                "host.restart",
                wait_type="sleep",
                wait_value="2000",
                condition_type="process_running",
                condition_value="python3",
                fallback_action="host.status",
            ),
        ]
        save_macro("full", steps, path=self.path)

        # Also verify the file content directly
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(len(raw["full"]), 2)
        self.assertEqual(raw["full"][1]["wait_type"], "sleep")
        self.assertEqual(raw["full"][1]["fallback_action"], "host.status")

        loaded = load_macros(self.path)
        s = loaded["full"][1]
        self.assertEqual(s.wait_type, "sleep")
        self.assertEqual(s.wait_value, "2000")
        self.assertEqual(s.condition_type, "process_running")
        self.assertEqual(s.condition_value, "python3")
        self.assertEqual(s.fallback_action, "host.status")

    def test_old_format_still_loads(self) -> None:
        """Backward compat: macro files with only 'action' fields."""
        old_data = {"startup": [{"action": "host.status"}, {"action": "camcoms.paths"}]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")
        loaded = load_macros(self.path)
        self.assertIn("startup", loaded)
        self.assertEqual(len(loaded["startup"]), 2)
        self.assertEqual(loaded["startup"][0].action, "host.status")
        self.assertIsNone(loaded["startup"][0].wait_type)

    def test_save_preserves_unchanged_macros(self) -> None:
        """Saving one macro should not drop others in the file."""
        save_macro("a", [MacroStep("a1")], path=self.path)
        save_macro("b", [MacroStep("b1")], path=self.path)
        loaded = load_macros(self.path)
        self.assertIn("a", loaded)
        self.assertIn("b", loaded)

    def test_missing_file_returns_empty(self) -> None:
        """load_macros on non-existent path returns empty dict."""
        p = Path(self.tmp.name) / "nonexistent" / "macros.json"
        self.assertEqual(load_macros(p), {})

    def test_invalid_json_raises(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("not json\n", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            load_macros(self.path)


class WaitExecutorTests(unittest.TestCase):
    """execute_step_with_waits — sleep, window, process."""

    def setUp(self) -> None:
        self.router = ActionRouter()

    def test_no_wait_is_noop(self) -> None:
        step = MacroStep("host.status")
        execute_step_with_waits(step, self.router)  # should not raise

    def test_sleep_wait_pauses(self) -> None:
        step = MacroStep("host.status", wait_type="sleep", wait_value="100")
        start = time.monotonic()
        execute_step_with_waits(step, self.router)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.08)

    def test_sleep_invalid_value_does_not_crash(self) -> None:
        step = MacroStep("host.status", wait_type="sleep", wait_value="not-a-number")
        execute_step_with_waits(step, self.router)  # should log warning, not raise

    @patch("FionaCore.macro_engine._wait_for_window", return_value=True)
    def test_wait_for_window_delegates(self, mock_wait: MagicMock) -> None:
        step = MacroStep("host.status", wait_type="wait_for_window", wait_value="Brave")
        execute_step_with_waits(step, self.router)
        mock_wait.assert_called_once_with("Brave", timeout=30)

    @patch("FionaCore.macro_engine._wait_for_process", return_value=True)
    def test_wait_for_process_delegates(self, mock_wait: MagicMock) -> None:
        step = MacroStep("host.status", wait_type="wait_for_process", wait_value="python3")
        execute_step_with_waits(step, self.router)
        mock_wait.assert_called_once_with("python3", timeout=30)

    def test_unknown_wait_type_logs_and_ignores(self) -> None:
        step = MacroStep("host.status", wait_type="unknown_xyz", wait_value="foo")
        execute_step_with_waits(step, self.router)  # should log warning, not raise


class WaitForWindowTests(unittest.TestCase):
    """_wait_for_window — graceful degradation and matching."""

    def test_returns_false_when_seeondesk_unavailable(self) -> None:
        """If SeeOnDesk can't be imported, return False without crashing."""
        with patch.dict("sys.modules", {"SeeOnDesk": None}):
            with patch("builtins.__import__", side_effect=ImportError("no SeeOnDesk")):
                # The import inside _wait_for_window will fail
                result = _wait_for_window("anything", timeout=0.01)
                self.assertFalse(result)

    def test_returns_false_on_timeout(self) -> None:
        """When no window matches, return False after timeout."""
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="other", title="other"),
        ):
            result = _wait_for_window("TargetWindow", timeout=0.1)
            self.assertFalse(result)

    def test_returns_true_when_app_name_matches(self) -> None:
        mock_info = MagicMock()
        mock_info.app_name = "Brave Browser"
        mock_info.title = "Some Page"
        with patch("SeeOnDesk.active_window_info", return_value=mock_info):
            result = _wait_for_window("brave", timeout=1.0)
            self.assertTrue(result)

    def test_returns_true_when_title_matches(self) -> None:
        mock_info = MagicMock()
        mock_info.app_name = "Other"
        mock_info.title = "My Document"
        with patch("SeeOnDesk.active_window_info", return_value=mock_info):
            result = _wait_for_window("document", timeout=1.0)
            self.assertTrue(result)

    def test_case_insensitive_matching(self) -> None:
        mock_info = MagicMock()
        mock_info.app_name = "BRAVE BROWSER"
        mock_info.title = ""
        with patch("SeeOnDesk.active_window_info", return_value=mock_info):
            result = _wait_for_window("brave", timeout=1.0)
            self.assertTrue(result)

    def test_handles_exception_from_seeondesk(self) -> None:
        """If active_window_info raises, keep polling until timeout."""
        call_count = 0

        def flaky_info() -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("temporary glitch")
            info = MagicMock()
            info.app_name = "Found"
            info.title = ""
            return info

        with patch("SeeOnDesk.active_window_info", side_effect=flaky_info):
            result = _wait_for_window("found", timeout=2.0)
            self.assertTrue(result)


class WaitForProcessTests(unittest.TestCase):
    """_wait_for_process — /proc scanning."""

    def test_returns_false_when_not_found(self) -> None:
        result = _wait_for_process("__this_process_should_not_exist__", timeout=0.1)
        self.assertFalse(result)

    @patch("pathlib.Path.iterdir")
    def test_returns_true_when_found(self, mock_iterdir: MagicMock) -> None:
        """Simulate a /proc entry with matching comm."""
        proc123 = MagicMock()
        proc123.name = "123"
        comm_file = MagicMock()
        comm_file.read_text.return_value = "python3\n"
        proc123.__truediv__.return_value = comm_file

        mock_iterdir.return_value = [proc123]

        result = _wait_for_process("python3", timeout=1.0)
        self.assertTrue(result)

    @patch("pathlib.Path.iterdir")
    def test_case_insensitive(self, mock_iterdir: MagicMock) -> None:
        proc456 = MagicMock()
        proc456.name = "456"
        comm_file = MagicMock()
        comm_file.read_text.return_value = "Python3\n"
        proc456.__truediv__.return_value = comm_file

        mock_iterdir.return_value = [proc456]

        result = _wait_for_process("python3", timeout=1.0)
        self.assertTrue(result)

    @patch("pathlib.Path.iterdir")
    def test_skips_non_digit_entries(self, mock_iterdir: MagicMock) -> None:
        """Entries like /proc/cpuinfo should be skipped."""
        bad_entry = MagicMock()
        bad_entry.name = "cpuinfo"
        good_entry = MagicMock()
        good_entry.name = "789"
        comm_file = MagicMock()
        comm_file.read_text.return_value = "myproc\n"
        good_entry.__truediv__.return_value = comm_file

        mock_iterdir.return_value = [bad_entry, good_entry]

        result = _wait_for_process("myproc", timeout=1.0)
        self.assertTrue(result)

    @patch("pathlib.Path.iterdir")
    def test_handles_oserror_gracefully(self, mock_iterdir: MagicMock) -> None:
        """If comm file can't be read, skip it."""
        proc = MagicMock()
        proc.name = "999"
        comm_file = MagicMock()
        comm_file.read_text.side_effect = OSError("permission denied")
        proc.__truediv__.return_value = comm_file

        mock_iterdir.return_value = [proc]

        # Should not raise
        result = _wait_for_process("anything", timeout=0.1)
        self.assertFalse(result)


class ConditionEvaluatorTests(unittest.TestCase):
    """evaluate_condition — all condition types."""

    def test_no_condition_returns_true(self) -> None:
        step = MacroStep("host.status")
        self.assertTrue(evaluate_condition(step))

    def test_unknown_condition_type_returns_true(self) -> None:
        step = MacroStep("test", condition_type="unknown_type", condition_value="foo")
        self.assertTrue(evaluate_condition(step))

    # -- window_active -----------------------------------------------------

    def test_window_active_returns_false_when_not_matching(self) -> None:
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="other", title="other"),
        ):
            step = MacroStep("test", condition_type="window_active", condition_value="Brave")
            self.assertFalse(evaluate_condition(step))

    def test_window_active_returns_true_when_matching_app_name(self) -> None:
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="Brave Browser", title=""),
        ):
            step = MacroStep("test", condition_type="window_active", condition_value="brave")
            self.assertTrue(evaluate_condition(step))

    def test_window_active_returns_true_when_matching_title(self) -> None:
        with patch(
            "SeeOnDesk.active_window_info",
            return_value=MagicMock(app_name="", title="My Terminal"),
        ):
            step = MacroStep("test", condition_type="window_active", condition_value="terminal")
            self.assertTrue(evaluate_condition(step))

    def test_window_active_graceful_if_seeondesk_unavailable(self) -> None:
        """If SeeOnDesk import fails, return False without crashing."""
        with patch.dict("sys.modules", {"SeeOnDesk": None}):
            with patch("builtins.__import__", side_effect=ImportError("no SeeOnDesk")):
                step = MacroStep("test", condition_type="window_active", condition_value="anything")
                result = evaluate_condition(step)
                self.assertFalse(result)

    def test_window_active_handles_exception_gracefully(self) -> None:
        def failing() -> None:
            raise RuntimeError("backend failure")

        with patch("SeeOnDesk.active_window_info", side_effect=failing):
            step = MacroStep("test", condition_type="window_active", condition_value="anything")
            self.assertFalse(evaluate_condition(step))

    # -- process_running ---------------------------------------------------

    def test_process_running_returns_false_when_not_found(self) -> None:
        step = MacroStep("test", condition_type="process_running", condition_value="__nonexistent__")
        self.assertFalse(evaluate_condition(step))

    @patch("pathlib.Path.iterdir")
    def test_process_running_returns_true_when_found(self, mock_iterdir: MagicMock) -> None:
        proc = MagicMock()
        proc.name = "123"
        comm_file = MagicMock()
        comm_file.read_text.return_value = "sshd\n"
        proc.__truediv__.return_value = comm_file

        mock_iterdir.return_value = [proc]

        step = MacroStep("test", condition_type="process_running", condition_value="sshd")
        self.assertTrue(evaluate_condition(step))

    @patch("pathlib.Path.iterdir")
    def test_process_running_case_insensitive(self, mock_iterdir: MagicMock) -> None:
        proc = MagicMock()
        proc.name = "456"
        comm_file = MagicMock()
        comm_file.read_text.return_value = "SSHD\n"
        proc.__truediv__.return_value = comm_file

        mock_iterdir.return_value = [proc]

        step = MacroStep("test", condition_type="process_running", condition_value="sshd")
        self.assertTrue(evaluate_condition(step))

    # -- action_result -----------------------------------------------------

    def test_action_result_checks_last_matching_action(self) -> None:
        results = [
            ActionResult(ok=True, action="host.status", detail="ok"),
            ActionResult(ok=False, action="host.restart", detail="failed"),
        ]
        ctx = {"_results": results}

        ok_step = MacroStep("next", condition_type="action_result", condition_value="host.status:ok")
        self.assertTrue(evaluate_condition(ok_step, context=ctx))

        fail_step = MacroStep("next", condition_type="action_result", condition_value="host.restart:failed")
        self.assertTrue(evaluate_condition(fail_step, context=ctx))

    def test_action_result_mismatch_returns_false(self) -> None:
        results = [
            ActionResult(ok=True, action="host.status", detail="ok"),
        ]
        ctx = {"_results": results}

        step = MacroStep("next", condition_type="action_result", condition_value="host.status:failed")
        self.assertFalse(evaluate_condition(step, context=ctx))

    def test_action_result_action_not_found_returns_false(self) -> None:
        results = [
            ActionResult(ok=True, action="host.status", detail="ok"),
        ]
        ctx = {"_results": results}

        step = MacroStep("next", condition_type="action_result", condition_value="other.action:ok")
        self.assertFalse(evaluate_condition(step, context=ctx))

    def test_action_result_empty_results_returns_false(self) -> None:
        ctx: dict = {}
        step = MacroStep("next", condition_type="action_result", condition_value="anything:ok")
        self.assertFalse(evaluate_condition(step, context=ctx))

    def test_action_result_malformed_value_defaults_true(self) -> None:
        """Malformed condition_value (not in format 'a:b') returns True."""
        step = MacroStep("next", condition_type="action_result", condition_value="no-colon")
        self.assertTrue(evaluate_condition(step, context={}))

    def test_action_result_uses_most_recent_result_of_action(self) -> None:
        results = [
            ActionResult(ok=True, action="host.status", detail="first"),
            ActionResult(ok=False, action="host.status", detail="second"),
        ]
        ctx = {"_results": results}

        # Most recent (second) is failed, so expect fail
        step = MacroStep("next", condition_type="action_result", condition_value="host.status:ok")
        self.assertFalse(evaluate_condition(step, context=ctx))

        step2 = MacroStep("next", condition_type="action_result", condition_value="host.status:failed")
        self.assertTrue(evaluate_condition(step2, context=ctx))


class MacroEngineIntegrationTests(unittest.TestCase):
    """Integration: full macro engine v2 flow (waits + conditions + branching)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.macro_path = Path(self.tmp.name) / "macros.json"
        self.router = ActionRouter()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_macro_with_waits_can_be_saved_and_loaded_and_run(self) -> None:
        """Full round-trip: define macro with wait, save, load, and run steps."""
        steps = [
            MacroStep("host.status", wait_type="sleep", wait_value="50"),
            MacroStep("camcoms.paths"),
        ]
        save_macro("integration", steps, path=self.macro_path)

        # Executing each step through execute_step_with_waits + router.run
        from FionaCore.macros import run_macro

        results = run_macro("integration", router=self.router, path=self.macro_path, dry_run=True)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.ok for r in results))

    def test_condition_and_fallback_in_context(self) -> None:
        """Simulate branching logic with evaluate_condition + fallback selection."""
        step = MacroStep(
            action="host.restart",
            condition_type="process_running",
            condition_value="python3",
            fallback_action="host.status",
        )

        # We patch _eval_process_running to return False so the condition is
        # not met and the fallback action is selected.
        with patch("FionaCore.macro_engine._eval_process_running", return_value=False):
            condition_met = evaluate_condition(step)
        chosen_action = step.action if condition_met else step.fallback_action
        self.assertEqual(chosen_action, step.fallback_action)

        # Run the chosen action
        result = self.router.run(chosen_action, dry_run=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.action, "host.status")


if __name__ == "__main__":
    unittest.main()
