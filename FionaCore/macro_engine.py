"""Extended macro execution engine with waits, conditions, branching, and
variable interpolation."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from string import Template
from typing import Any

from FionaCore.actions import ActionResult, ActionRouter
from FionaCore.macros import MacroStep

logger = logging.getLogger(__name__)

# Maximum allowed GOTO depth to detect circular references.
MAX_GOTO_DEPTH = 10


# ---------------------------------------------------------------------------
# Wait executor
# ---------------------------------------------------------------------------


def execute_step_with_waits(
    step: MacroStep,
    router: ActionRouter,
    context: dict[str, Any] | None = None,
) -> None:
    """Execute any wait operations defined in the step before action execution.

    Supported wait types:
    - ``"sleep"``: Wait for N milliseconds (from *wait_value*).
    - ``"wait_for_window"``: Poll SeeOnDesk ``active_window_info()`` up to
      30 seconds for a matching window title/class.
    - ``"wait_for_process"``: Poll ``/proc`` up to 30 seconds for a matching
      process name.

    When *wait_type* is ``None`` the function returns immediately (no-op).
    """
    if step.wait_type is None or step.wait_value is None:
        return

    if step.wait_type == "sleep":
        try:
            ms = int(step.wait_value)
            time.sleep(ms / 1000.0)
        except ValueError:
            logger.warning("Invalid sleep wait_value '%s' – ignoring", step.wait_value)
        return

    if step.wait_type == "wait_for_window":
        _wait_for_window(step.wait_value, timeout=30)
        return

    if step.wait_type == "wait_for_process":
        _wait_for_process(step.wait_value, timeout=30)
        return

    logger.warning("Unknown wait_type '%s' – ignoring", step.wait_type)


def _wait_for_window(title_substring: str, timeout: float = 30) -> bool:
    """Poll active window info until window title matches or timeout.

    Returns ``True`` if a matching window was found, ``False`` otherwise.
    """
    try:
        from SeeOnDesk import active_window_info
    except ImportError:
        logger.warning(
            "SeeOnDesk is not available – cannot wait_for_window. "
            "Install SeeOnDesk or use a different wait type."
        )
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            info = active_window_info()
            if title_substring.lower() in info.app_name.lower():
                return True
            if title_substring.lower() in info.title.lower():
                return True
        except Exception:
            logger.debug("active_window_info() failed during wait loop", exc_info=True)
        time.sleep(0.5)
    return False


def _wait_for_process(process_name: str, timeout: float = 30) -> bool:
    """Poll ``/proc`` until a process with the given name appears or timeout.

    Returns ``True`` if the process was found, ``False`` otherwise.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for proc in Path("/proc").iterdir():
                if not proc.name.isdigit():
                    continue
                try:
                    comm = (proc / "comm").read_text(encoding="utf-8").strip()
                    if process_name.lower() in comm.lower():
                        return True
                except (OSError, FileNotFoundError):
                    continue
        except Exception:
            logger.debug("/proc iteration failed during wait loop", exc_info=True)
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Condition evaluator
# ---------------------------------------------------------------------------


def evaluate_condition(
    step: MacroStep,
    context: dict[str, Any] | None = None,
) -> bool:
    """Evaluate a condition defined in the step.

    Supported condition types:

    - ``"window_active"``
        Check if a window with a matching title/class is currently active.
    - ``"process_running"``
        Check if a process with a matching name is currently running.
    - ``"action_result"``
        Check if a previously-run action had a specific status.
        Format: ``"action_name:ok"`` or ``"action_name:failed"``.
        Uses ``context["_results"]`` (a list of :class:`ActionResult`).

    Returns ``True`` if the condition is met **or** if no condition is defined
    (i.e. *condition_type* is ``None``).  Unknown condition types also default
    to ``True``.
    """
    context = context or {}

    if step.condition_type is None:
        return True  # No condition = always execute

    if step.condition_type == "window_active":
        return _eval_window_active(step.condition_value or "")

    if step.condition_type == "process_running":
        return _eval_process_running(step.condition_value or "")

    if step.condition_type == "action_result":
        return _eval_action_result(step.condition_value or "", context)

    # Unknown condition types default to True (safe)
    logger.debug("Unknown condition_type '%s' – defaulting to True", step.condition_type)
    return True


def _eval_window_active(target: str) -> bool:
    """Check whether *target* appears in the active window's app_name or title."""
    try:
        from SeeOnDesk import active_window_info
    except ImportError:
        logger.warning(
            "SeeOnDesk is not available – cannot evaluate window_active condition. "
            "Defaulting to False."
        )
        return False

    try:
        info = active_window_info()
        target_lower = target.lower()
        return target_lower in info.app_name.lower() or target_lower in info.title.lower()
    except Exception:
        logger.debug("active_window_info() failed for condition", exc_info=True)
        return False


def _eval_process_running(target: str) -> bool:
    """Check whether *target* appears in any ``/proc/*/comm`` name."""
    target_lower = target.lower()
    try:
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                comm = (proc / "comm").read_text(encoding="utf-8").strip()
                if target_lower in comm.lower():
                    return True
            except (OSError, FileNotFoundError):
                continue
    except Exception:
        logger.debug("/proc iteration failed for condition", exc_info=True)
    return False


def _eval_action_result(value: str, context: dict[str, Any]) -> bool:
    """Check a previous action result from ``context["_results"]``.

    *value* format: ``"action_name:ok"`` or ``"action_name:failed"``.
    """
    parts = value.split(":")
    if len(parts) != 2:
        logger.debug("Malformed action_result value '%s' – defaulting to True", value)
        return True

    action_name, expected_status = parts
    previous_results = context.get("_results", [])
    for result in reversed(previous_results):
        if isinstance(result, ActionResult) and result.action == action_name:
            if expected_status == "ok" and result.ok:
                return True
            if expected_status == "failed" and not result.ok:
                return True
            return False  # Found the action but status doesn't match
    return False  # Action not found in results


# ---------------------------------------------------------------------------
# Atomic file write helper
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically using a temp file and rename (Unix-safe)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.chmod(0o600)  # private
    tmp.rename(path)  # atomic on Unix


# ---------------------------------------------------------------------------
# Variable interpolation
# ---------------------------------------------------------------------------


def _resolve_variables(step: MacroStep, context: dict[str, Any]) -> MacroStep:
    """Perform variable interpolation on all string fields of a MacroStep.

    Variables are referenced as ``${variable_name}`` in strings.

    Available variables:
    - ``context['_variables']`` items
    - ``last_result`` — string representation of the most recent ActionResult
    - ``last_ok`` — ``"True"`` / ``"False"`` of most recent result
    - ``step_index`` — current step index

    If a variable is not found, the placeholder is left unchanged.
    """
    variables = dict(context.get("_variables", {}))

    # Add convenience variables
    variables["step_index"] = context.get("_step_index", 0)

    last_results = context.get("_results", [])
    if last_results:
        last = last_results[-1]
        variables["last_result"] = str(last)
        variables["last_ok"] = str(last.ok) if last else "False"
    else:
        variables["last_result"] = ""
        variables["last_ok"] = "False"

    # Build a substitution dict — only string-compatible values
    sub_map: dict[str, str] = {k: str(v) for k, v in variables.items()}

    def _sub(s: str | None) -> str | None:
        if s is None:
            return None
        try:
            return Template(s).safe_substitute(sub_map)
        except Exception:
            return s

    return MacroStep(
        action=_sub(step.action) or "",
        wait_type=step.wait_type,
        wait_value=_sub(step.wait_value),
        condition_type=step.condition_type,
        condition_value=_sub(step.condition_value),
        fallback_action=_sub(step.fallback_action),
    )


# ---------------------------------------------------------------------------
# Full macro orchestration runner
# ---------------------------------------------------------------------------


def run_macro_steps(
    steps: list[MacroStep],
    router: ActionRouter,
    variables: dict[str, Any] | None = None,
) -> list[ActionResult]:
    """Execute a list of MacroSteps with full orchestration:

    variables → wait → condition check → action (or fallback).

    For each step:
    1. Perform variable interpolation on all string fields.
    2. Execute any wait operations.
    3. Evaluate the condition.
    4. If condition passes: run the action via ``router.run()``.
    5. If condition fails and *fallback_action* is set: run fallback action.
    6. If condition fails and no fallback: skip the step.
    7. Store ActionResult in ``context['_results']``.
    8. If step action is ``"GOTO:<macro_name>"``, load that macro's steps
       and continue execution there (depth-limited to **MAX_GOTO_DEPTH**).

    Returns a list of :class:`ActionResult` for all executed actions.
    """
    context: dict[str, Any] = {
        "_results": [],
        "_variables": dict(variables or {}),
        "_step_index": 0,
        "_goto_depth": 0,
    }
    results: list[ActionResult] = []
    index = 0

    while index < len(steps):
        step = steps[index]
        context["_step_index"] = index

        # 1. Variable interpolation
        resolved = _resolve_variables(step, context)

        # 2. Wait
        execute_step_with_waits(resolved, router, context)

        # 3. Condition
        condition_met = evaluate_condition(resolved, context)

        if condition_met:
            # 4. Execute action
            if not resolved.action:
                logger.warning("Empty action at step %d – skipping", index)
                index += 1
                continue

            result = router.run(resolved.action)
            context["_results"].append(result)
            results.append(result)

            # 8. GOTO support
            if resolved.action.startswith("GOTO:"):
                macro_name = resolved.action[len("GOTO:"):]
                if not macro_name:
                    logger.warning("Empty GOTO target at step %d", index)
                    index += 1
                    continue

                # Track GOTO depth to detect circular references
                goto_depth = context.get("_goto_depth", 0) + 1
                if goto_depth > MAX_GOTO_DEPTH:
                    logger.warning(
                        "GOTO depth exceeded (%d > %d) for '%s' – stopping",
                        goto_depth, MAX_GOTO_DEPTH, macro_name,
                    )
                    context["_goto_depth"] = goto_depth
                    index += 1
                    continue

                context["_goto_depth"] = goto_depth

                # Lazy import to avoid circular dependency at module level
                from FionaCore.macros import load_macros as _load_macros

                macros = _load_macros()
                if macro_name in macros:
                    logger.info("GOTO '%s' → branching to %d steps", macro_name, len(macros[macro_name]))
                    steps = macros[macro_name]
                    index = 0
                    continue  # don't increment index
                else:
                    logger.warning("GOTO macro '%s' not found", macro_name)
                    index += 1
                    continue
        else:
            # 5. / 6. Fallback or skip
            fallback = resolved.fallback_action
            if fallback:
                result = router.run(fallback)
                context["_results"].append(result)
                results.append(result)
            else:
                logger.info("Condition not met for step %d, skipping", index)

        index += 1

    # Update convenience variables with last result
    if results:
        context["_variables"]["last_result"] = results[-1]
        context["_variables"]["last_ok"] = results[-1].ok if results[-1] else None

    return results
