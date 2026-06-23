from __future__ import annotations

from typing import Any

from Agent.personality import Personality
from FionaCore import ActionRouter, ActionResult


class AgentPermissionError(RuntimeError):
    """Raised when a personality attempts a disallowed tool."""

    def __init__(self, tool_name: str, personality_name: str) -> None:
        self.tool_name = tool_name
        self.personality_name = personality_name
        super().__init__(
            f"personality '{personality_name}' is not allowed to use tool '{tool_name}'"
        )


class PermissionEnforcer:
    """Runtime gate that checks tool access against a personality's restrictions.

    This class is entirely optional — existing code never touches it, so
    backward compatibility is fully preserved.
    """

    def __init__(self, personality: Personality) -> None:
        self._personality = personality

    @property
    def personality(self) -> Personality:
        return self._personality

    def check_tool(self, tool_name: str) -> bool:
        """Return ``True`` if *tool_name* is permitted by the active personality."""
        return self._personality.permits(tool_name)

    def assert_tool_allowed(self, tool_name: str) -> None:
        """Raise :class:`AgentPermissionError` if *tool_name* is not permitted."""
        if not self.check_tool(tool_name):
            raise AgentPermissionError(tool_name, self._personality.name)


class SafeActionRouter:
    """Wraps :class:`FionaCore.ActionRouter` with personality-based permission checks.

    Full pass-through semantics when used without an enforcer
    (backward compatible — but note the enforcer is currently **required**;
     pass a ``PermissionEnforcer`` wrapping a personality with
     ``allowed_tools=None`` for an unrestricted router).
    """

    def __init__(
        self,
        enforcer: PermissionEnforcer,
        router: ActionRouter | None = None,
    ) -> None:
        """If *router* is ``None``, a new :class:`ActionRouter` is created."""
        self._enforcer = enforcer
        self._router = router if router is not None else ActionRouter()

    # -- read-only properties ------------------------------------------------

    @property
    def router(self) -> ActionRouter:
        return self._router

    @property
    def enforcer(self) -> PermissionEnforcer:
        return self._enforcer

    # -- delegated methods ---------------------------------------------------

    def run(
        self,
        name: str,
        *,
        source: str = "agent",
        permission_profile: str = "local",
        dry_run: bool = False,
        timeout_seconds: float = 30.0,
        record_history: bool = True,
        sender_id: str | None = None,
        action_scope: str | None = None,
    ) -> ActionResult:
        """Check permission then delegate to :meth:`ActionRouter.run`.

        Raises :class:`AgentPermissionError` if the personality is not allowed
        to use *name*.
        """
        self._enforcer.assert_tool_allowed(name)
        return self._router.run(
            name,
            source=source,
            permission_profile=permission_profile,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            record_history=record_history,
            sender_id=sender_id,
            action_scope=action_scope,
        )

    def run_with_fallback(
        self,
        name: str,
        *,
        source: str = "agent",
        permission_profile: str = "local",
        dry_run: bool = False,
        timeout_seconds: float = 30.0,
        record_history: bool = True,
        sender_id: str | None = None,
        action_scope: str | None = None,
    ) -> ActionResult:
        """Run the action via the normal router; if unknown, fallback to CLI.

        The ReAct loop uses this to guarantee that even if a tool is not
        present in ``ActionRouter`` the agent can still attempt execution via
        the generic ``fiona.cli`` entry point.  This returns a proper
        ``ActionResult`` so the observation can be fed back to the LLM.
        """
        try:
            return self.run(
                name,
                source=source,
                permission_profile=permission_profile,
                dry_run=dry_run,
                timeout_seconds=timeout_seconds,
                record_history=record_history,
                sender_id=sender_id,
                action_scope=action_scope,
            )
        except ValueError:
            # Fallback: invoke the generic CLI for the unknown command
            import subprocess, sys, json
            args = [sys.executable, "-m", "fiona.cli", name]
            completed = subprocess.run(
                args, capture_output=True, text=True, check=False
            )
            ok = completed.returncode == 0
            detail = completed.stdout if ok else completed.stderr
            return ActionResult(
                ok=ok,
                action=name,
                detail=detail,
                command=tuple(args),
                returncode=completed.returncode,
                source="cli-fallback",
                timestamp="",
                duration_ms=0,
                dry_run=False,
            )

    def list_allowed_actions(self) -> list[dict[str, Any]]:
        """Return the intersection of :meth:`ActionRouter.list_actions`
        and the personality's *allowed_tools*.

        When *allowed_tools* is ``None`` (all tools permitted), every
        registered action is returned.
        """
        all_actions = self._router.list_actions()
        allowed = self._enforcer.personality.allowed_tools
        if allowed is None:
            return all_actions
        return [a for a in all_actions if a.get("name") in allowed]
