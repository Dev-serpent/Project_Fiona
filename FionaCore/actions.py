from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from CmdTrace import DEFAULT_TRACE_PATH, append_trace
from .permissions import permission_allows


@dataclass(frozen=True)
class ActionSpec:
    name: str
    command: tuple[str, ...]
    description: str
    risk: str = "low"
    permission: str = "read"
    external: bool = False

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
        ActionSpec("host.init", ("host", "init"), "Initialize host service config.", risk="medium", permission="service"),
        ActionSpec("host.logs", ("host", "logs", "--lines", "80"), "Show host service logs."),
        ActionSpec("host.restart", ("host", "restart"), "Restart host service.", risk="high", permission="service", external=True),
        ActionSpec("camcoms.paths", ("camcoms", "paths"), "Show CamComs paths."),
        ActionSpec("camcoms.smoke", ("camcoms", "smoke-test"), "Run CamComs smoke test."),
        ActionSpec("camcoms.audit", ("camcoms", "audit", "--limit", "20"), "Show CamComs audit log."),
        ActionSpec("quiktieper.list", ("list",), "List QuikTieper bindings."),
        ActionSpec("quiktieper.import_apps.preview", ("import-apps", "--dry-run"), "Preview app import."),
        ActionSpec("quiktieper.assign_keys.preview", ("assign-keys", "--dry-run"), "Preview key assignment."),
        ActionSpec("seeondesk.status", ("seeondesk", "status"), "Show desktop awareness snapshot."),
        ActionSpec("eyecontrol.status", ("eyecontrol", "status"), "Show EyeControl readiness."),
        ActionSpec("agent.status", ("agent", "status"), "Show LM Studio bridge status.", risk="medium", permission="network"),
        ActionSpec("phiconnect.open", ("phiconnect",), "Open PhiConnect.", risk="medium", permission="gui", external=True),
        ActionSpec("dataclient.open", ("dataclient",), "Open DataClient.", risk="medium", permission="gui", external=True),
        ActionSpec("vsee.open", ("vsee",), "Open Vsee.", risk="medium", permission="gui", external=True),
        ActionSpec("fiona.edit", ("edit",), "Open shared Fiona GUI.", risk="medium", permission="gui", external=True),
        ActionSpec("fiona.cli", ("cli",), "Open fAT command center.", risk="medium", permission="gui", external=True),
    )


class ActionRouter:
    def __init__(self, specs: tuple[ActionSpec, ...] | None = None, *, trace_path: Path = DEFAULT_TRACE_PATH) -> None:
        self.specs = {spec.name: spec for spec in (specs or default_action_specs())}
        self.trace_path = trace_path

    def list_actions(self) -> list[dict[str, Any]]:
        return [self.specs[name].to_dict() for name in sorted(self.specs)]

    def get(self, name: str) -> ActionSpec:
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
    ) -> ActionResult:
        spec = self.get(name)
        started = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()
        if not permission_allows(profile=permission_profile, risk=spec.risk, permission=spec.permission):
            result = ActionResult(
                ok=False,
                action=name,
                detail=f"permission denied for profile {permission_profile}",
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
            append_trace(result.to_dict(), self.trace_path)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
