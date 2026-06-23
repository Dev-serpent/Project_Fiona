from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from CmdTrace import DEFAULT_TRACE_PATH, append_trace
from .acl import resolve_sender_profile, resolve_sender_scope
from .permissions import permission_allows
from .verification import (
    DEFAULT_VERIFICATION_PROMPT,
    VerificationPrompt,
    prompt_for_confirmation,
)


@dataclass(frozen=True)
class ActionSpec:
    name: str
    command: tuple[str, ...]
    description: str
    risk: str = "low"
    permission: str = "read"
    external: bool = False
    sender_scope: str = "any"
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["command"] = list(self.command)
        return data


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    action: str
    detail: str
    command: tuple[str, ...] = ()
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    source: str = "local"
    timestamp: str = ""
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["command"] = list(self.command)
        return data


def default_action_specs() -> tuple[ActionSpec, ...]:
    return (
        ActionSpec("fat.status", ("fat", "status", "--no-color"), "Show fAT dashboard."),
        ActionSpec("host.status", ("host", "status", "--check-port"), "Show host service status."),
        ActionSpec("host.init", ("host", "init"), "Initialize host service config.", risk="medium", permission="service", sender_scope="local"),
        ActionSpec("host.logs", ("host", "logs", "--lines", "80"), "Show host service logs."),
        ActionSpec("host.restart", ("host", "restart"), "Restart host service.", risk="high", permission="service", external=True, sender_scope="local", requires_confirmation=True),
        ActionSpec("camcoms.paths", ("camcoms", "paths"), "Show CamComs paths."),
        ActionSpec("camcoms.smoke", ("camcoms", "smoke-test"), "Run CamComs smoke test."),
        ActionSpec("camcoms.audit", ("camcoms", "audit", "--limit", "20"), "Show CamComs audit log."),
        ActionSpec("quiktieper.list", ("list",), "List QuikTieper bindings."),
        ActionSpec("quiktieper.import_apps.preview", ("import-apps", "--dry-run"), "Preview app import."),
        ActionSpec("quiktieper.assign_keys.preview", ("assign-keys", "--dry-run"), "Preview key assignment."),
        ActionSpec("seeondesk.status", ("seeondesk", "status"), "Show desktop awareness snapshot."),
        ActionSpec("eyecontrol.status", ("eyecontrol", "status"), "Show EyeControl readiness."),
        ActionSpec("agent.status", ("agent", "status"), "Show LM Studio bridge status.", risk="medium", permission="network"),
        ActionSpec("phiconnect.open", ("phiconnect",), "Open PhiConnect.", risk="medium", permission="gui", external=True, sender_scope="local"),
        ActionSpec("dataclient.open", ("dataclient",), "Open DataClient.", risk="medium", permission="gui", external=True, sender_scope="local"),
        ActionSpec("vsee.open", ("vsee",), "Open Vsee.", risk="medium", permission="gui", external=True, sender_scope="local"),
        ActionSpec("fiona.edit", ("edit",), "Open shared Fiona GUI.", risk="medium", permission="gui", external=True, sender_scope="local"),
        ActionSpec("fiona.cli", ("cli",), "Open fAT command center.", risk="medium", permission="gui", external=True, sender_scope="local"),
        # ----------------------------------------------------------------------
        # GUI / automation tools – previously only in command_registry
        # ----------------------------------------------------------------------
        ActionSpec(
            "launch_binding",
            ("launch_binding",),
            "Launch an application by its Fiona binding name.",
            risk="low",
            permission="gui",
            sender_scope="local",
        ),
        ActionSpec(
            "press",
            ("press",),
            "Press a key chord (e.g. ['ctrl','c']).",
            risk="low",
            permission="gui",
            sender_scope="local",
        ),
        ActionSpec(
            "click",
            ("click",),
            "Click a mouse button (left, right, middle) optionally at coordinates.",
            risk="low",
            permission="gui",
            sender_scope="local",
        ),
        ActionSpec(
            "move",
            ("move",),
            "Move the pointer to absolute screen coordinates.",
            risk="low",
            permission="gui",
            sender_scope="local",
        ),
        ActionSpec(
            "text",
            ("text",),
            "Type a string of text through the local automation backend.",
            risk="low",
            permission="gui",
            sender_scope="local",
        ),
        ActionSpec(
            "macro",
            ("macro",),
            "Run a sequence of Fiona action steps.",
            risk="low",
            permission="gui",
            sender_scope="local",
        ),
        # ------------------------------------------------------------------
        # Browser automation commands
        # ------------------------------------------------------------------
        ActionSpec("browser.status", ("browser", "status"),
                   "Show browser automation engine status.",
                   risk="low", permission="read", sender_scope="local"),
        ActionSpec("browser.start", ("browser", "start"),
                   "Start the browser automation engine.",
                   risk="medium", permission="service", sender_scope="local"),
        ActionSpec("browser.stop", ("browser", "stop"),
                   "Stop the browser automation engine.",
                   risk="medium", permission="service", sender_scope="local"),
        ActionSpec("browser.navigate", ("browser", "navigate"),
                   "Navigate the browser to a URL.",
                   risk="medium", permission="network", sender_scope="local"),
        ActionSpec("browser.click", ("browser", "click"),
                   "Click an element by CSS selector.",
                   risk="medium", permission="gui", sender_scope="local"),
        ActionSpec("browser.type", ("browser", "type"),
                   "Type text into an element by CSS selector.",
                   risk="medium", permission="gui", sender_scope="local"),
        ActionSpec("browser.screenshot", ("browser", "screenshot"),
                   "Capture a browser screenshot.",
                   risk="low", permission="read", sender_scope="local"),
        # ------------------------------------------------------------------
        # Human-in-the-loop approval commands
        # ------------------------------------------------------------------
        ActionSpec("approval.pending", ("approval", "pending"),
                   "Show plans awaiting human approval.",
                   risk="low", permission="read", sender_scope="local"),
        ActionSpec("approval.list", ("approval", "list"),
                   "Show all plan history.",
                   risk="low", permission="read", sender_scope="local"),
        ActionSpec("approval.approve", ("approval", "approve"),
                   "Approve a pending plan.",
                   risk="medium", permission="control", sender_scope="local"),
        ActionSpec("approval.deny", ("approval", "deny"),
                   "Deny a pending plan.",
                   risk="medium", permission="control", sender_scope="local"),
    )


class ActionRouter:
    def __init__(
        self,
        specs: tuple[ActionSpec, ...] | None = None,
        *,
        trace_path: Path = DEFAULT_TRACE_PATH,
        verification_prompt: VerificationPrompt | None = None,
        lock: threading.RLock | None = None,
    ) -> None:
        self.specs = {spec.name: spec for spec in (specs or default_action_specs())}
        self.trace_path = trace_path
        self.verification_prompt = verification_prompt or DEFAULT_VERIFICATION_PROMPT
        self._lock = lock or threading.RLock()

    def list_actions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self.specs[name].to_dict() for name in sorted(self.specs)]

    def get(self, name: str) -> ActionSpec:
        with self._lock:
            try:
                return self.specs[name]
            except KeyError as exc:
                raise ValueError(f"unknown action: {name}") from exc

    def run(
        self,
        name: str,
        *,
        source: str = "local",
        permission_profile: str = "local",
        dry_run: bool = False,
        timeout_seconds: float = 30.0,
        record_history: bool = True,
        sender_id: str | None = None,
        action_scope: str | None = None,
    ) -> ActionResult:
        spec = self.get(name)
        started = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()

        # Derive action scope from spec risk if not explicitly provided.
        if action_scope is None:
            action_scope = _risk_to_scope(spec.risk)

        # ---- ACL sender-scoped check ----------------------------------------
        if sender_id is not None:
            effective_profile = resolve_sender_profile(sender_id, current_profile=permission_profile)
            if not resolve_sender_scope(sender_id, action_scope):
                result = ActionResult(
                    ok=False,
                    action=name,
                    detail=f"ACL denied: sender={sender_id} scope={action_scope}",
                    command=spec.command,
                    returncode=126,
                    source=source,
                    timestamp=timestamp,
                    duration_ms=_elapsed_ms(started),
                    dry_run=dry_run,
                )
                self._record(result, record_history)
                return result
        else:
            effective_profile = permission_profile
        # ---------------------------------------------------------------------

        if not permission_allows(profile=effective_profile, risk=spec.risk, permission=spec.permission):
            result = ActionResult(
                ok=False,
                action=name,
                detail=f"permission denied for profile {effective_profile}",
                command=spec.command,
                returncode=126,
                source=source,
                timestamp=timestamp,
                duration_ms=_elapsed_ms(started),
                dry_run=dry_run,
            )
            self._record(result, record_history)
            return result

        if dry_run:
            result = ActionResult(
                ok=True,
                action=name,
                detail="dry-run",
                command=spec.command,
                source=source,
                timestamp=timestamp,
                duration_ms=_elapsed_ms(started),
                dry_run=True,
            )
            self._record(result, record_history)
            return result

        if spec.external:
            result = ActionResult(
                ok=False,
                action=name,
                detail="external action requires an interactive surface",
                command=spec.command,
                returncode=125,
                source=source,
                timestamp=timestamp,
                duration_ms=_elapsed_ms(started),
            )
            self._record(result, record_history)
            return result

        # ---- Verification prompt (confirmation) ----------------------------
        if spec.requires_confirmation:
            if not prompt_for_confirmation(spec, self.verification_prompt):
                result = ActionResult(
                    ok=False, action=name,
                    detail="verification cancelled by user",
                    command=spec.command, returncode=122,
                    source=source, timestamp=timestamp,
                    duration_ms=_elapsed_ms(started),
                )
                self._record(result, record_history)
                return result
        # --------------------------------------------------------------------

        completed = subprocess.run(
            [sys.executable, "-m", "fiona.cli", *spec.command],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        result = ActionResult(
            ok=completed.returncode == 0,
            action=name,
            detail="completed" if completed.returncode == 0 else "failed",
            command=spec.command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            source=source,
            timestamp=timestamp,
            duration_ms=_elapsed_ms(started),
        )
        self._record(result, record_history)
        return result

    def _record(self, result: ActionResult, enabled: bool) -> None:
        if enabled:
            with self._lock:
                append_trace(result.to_dict(), self.trace_path)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


_RISK_TO_SCOPE: dict[str, str] = {
    "low": "safe",
    "medium": "restricted",
    "high": "critical",
}


def _risk_to_scope(risk: str) -> str:
    """Map an action *risk* level to its corresponding sender scope."""
    return _RISK_TO_SCOPE.get(risk, "safe")
