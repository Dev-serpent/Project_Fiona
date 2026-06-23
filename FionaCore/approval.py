"""Human-in-the-loop approval system for agent plans."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class PlanStatus(Enum):
    PENDING = "pending"        # Awaiting human approval
    APPROVED = "approved"      # Human approved, ready to execute
    DENIED = "denied"          # Human denied
    EXECUTING = "executing"    # Currently being executed by agent
    COMPLETED = "completed"    # All steps done
    FAILED = "failed"          # Execution failed
    CANCELLED = "cancelled"    # Human cancelled during execution


@dataclass(frozen=True)
class PlannedStep:
    """A single step in an agent plan."""
    step_number: int
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    risk: str = "low"          # low / medium / high
    requires_approval: bool = False


@dataclass
class AgentPlan:
    """A complete plan submitted by the agent for human approval."""
    plan_id: str
    goal: str
    steps: list[PlannedStep]
    status: PlanStatus = PlanStatus.PENDING
    agent_id: str = "default"
    created_at: float = field(default_factory=time.time)
    decided_at: float | None = None
    decision_reason: str = ""
    result_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": [{
                "step_number": s.step_number,
                "action": s.action,
                "params": s.params,
                "reasoning": s.reasoning,
                "risk": s.risk,
                "requires_approval": s.requires_approval,
            } for s in self.steps],
            "status": self.status.value,
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "decision_reason": self.decision_reason,
            "result_summary": self.result_summary,
        }


class ApprovalManager:
    """Manages the human-in-the-loop approval queue.

    Thread-safe. Agent threads submit plans and block on wait_for_approval().
    Server threads call approve/deny in response to human action.
    Callers can subscribe to status changes via on_change callback.

    If *event_bus* is provided, plan lifecycle events are published
    (``"plan_updated"``, ``"plan_approved"``, ``"plan_denied"``, etc.).
    """

    def __init__(self, event_bus: Any | None = None):
        self._lock = threading.Lock()
        self._plans: dict[str, AgentPlan] = {}
        self._events: dict[str, threading.Event] = {}  # plan_id → event
        self._on_change_callbacks: list[Callable[[str], None]] = []
        self._event_bus = event_bus

    def on_change(self, callback: Callable[[str], None]) -> None:
        """Register callback invoked when any plan status changes.
        Callback receives plan_id."""
        with self._lock:
            self._on_change_callbacks.append(callback)

    def submit_plan(self, goal: str, steps: list[PlannedStep],
                    agent_id: str = "default") -> str:
        """Submit a plan for human approval. Returns plan_id.
        The plan starts in PENDING status."""
        plan_id = uuid.uuid4().hex[:12]
        plan = AgentPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            agent_id=agent_id,
        )
        with self._lock:
            self._plans[plan_id] = plan
            self._events[plan_id] = threading.Event()
            self._notify_change(plan_id)
        return plan_id

    def get_plan(self, plan_id: str) -> dict | None:
        """Get plan as dict, or None if not found."""
        with self._lock:
            plan = self._plans.get(plan_id)
            return plan.to_dict() if plan else None

    def get_pending_plans(self) -> list[dict]:
        """Get all plans still awaiting human decision."""
        with self._lock:
            return [
                p.to_dict() for p in self._plans.values()
                if p.status == PlanStatus.PENDING
            ]

    def get_all_plans(self) -> list[dict]:
        """Get all plans (for history view), newest first."""
        with self._lock:
            plans = list(self._plans.values())
            plans.sort(key=lambda p: p.created_at, reverse=True)
            return [p.to_dict() for p in plans]

    def approve_plan(self, plan_id: str) -> bool:
        """Approve a pending plan. Returns True if successful."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan or plan.status != PlanStatus.PENDING:
                return False
            plan.status = PlanStatus.APPROVED
            plan.decided_at = time.time()
            self._events[plan_id].set()
            self._notify_change(plan_id)
        return True

    def deny_plan(self, plan_id: str, reason: str = "") -> bool:
        """Deny a pending plan. Returns True if successful."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan or plan.status != PlanStatus.PENDING:
                return False
            plan.status = PlanStatus.DENIED
            plan.decided_at = time.time()
            plan.decision_reason = reason
            self._events[plan_id].set()
            self._notify_change(plan_id)
        return True

    def mark_executing(self, plan_id: str) -> bool:
        """Mark plan as being executed."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan or plan.status != PlanStatus.APPROVED:
                return False
            plan.status = PlanStatus.EXECUTING
            self._notify_change(plan_id)
        return True

    def mark_completed(self, plan_id: str, summary: str = "") -> bool:
        """Mark plan as completed."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            plan.status = PlanStatus.COMPLETED
            plan.result_summary = summary
            self._notify_change(plan_id)
        return True

    def mark_failed(self, plan_id: str, error: str = "") -> bool:
        """Mark plan as failed."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            plan.status = PlanStatus.FAILED
            plan.result_summary = error
            self._notify_change(plan_id)
        return True

    def cancel_plan(self, plan_id: str, reason: str = "") -> bool:
        """Cancel a plan during execution."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            plan.status = PlanStatus.CANCELLED
            plan.decision_reason = reason
            self._events[plan_id].set()
            self._notify_change(plan_id)
        return True

    def wait_for_approval(self, plan_id: str, timeout: float | None = None) -> str:
        """Block until the plan is approved, denied, or cancelled.

        Args:
            plan_id: The plan to wait for.
            timeout: Maximum seconds to wait. None = wait forever.

        Returns:
            The status string: 'approved', 'denied', 'cancelled', or 'timeout'.
        """
        event = self._events.get(plan_id)
        if not event:
            return 'denied'
        event.wait(timeout=timeout)
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return 'denied'
            if not event.is_set():
                return 'timeout'
            return plan.status.value

    def _notify_change(self, plan_id: str) -> None:
        # Custom callbacks
        for cb in self._on_change_callbacks:
            try:
                cb(plan_id)
            except Exception:
                pass
        # EventBus broadcast
        if self._event_bus is not None:
            try:
                plan = self._plans.get(plan_id)
                if plan is not None:
                    # Publish a generic "plan_updated" event via EventBus
                    from fiona.interfaces import Event  # noqa: PLC0415
                    ev = Event(
                        timestamp=time.time(),
                        source="ApprovalManager",
                    )
                    self._event_bus.publish(ev)
            except Exception:
                pass


# Module-level singleton for shared access
_default_manager: ApprovalManager | None = None
_manager_lock = threading.Lock()


def get_approval_manager() -> ApprovalManager:
    """Get the shared ApprovalManager singleton."""
    global _default_manager
    if _default_manager is None:
        with _manager_lock:
            if _default_manager is None:
                _default_manager = ApprovalManager()
    return _default_manager
