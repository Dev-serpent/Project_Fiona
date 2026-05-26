from __future__ import annotations

import json
import shutil
import socket
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from CamComs.audit import DEFAULT_AUDIT_LOG_PATH, AuditLog
from CamComs.encryption import CamComsIdentity
from CamComs.paths import DEFAULT_CAMCOMS_DIR, private_key_path
from CamComs.receiver import run_host_receiver
from CamComs.replay import DEFAULT_REPLAY_PATH, ReplayGuard
from CamComs.trust import DEFAULT_TRUSTED_DIR
from QuikTieper.config import DEFAULT_CONFIG_PATH as DEFAULT_QUIKTIEPER_CONFIG_PATH
from QuikTieper.config import load_config
from QuikTieper.bindings import parse_bindings
from QuikTieper.remote import RemoteActionRunner


DEFAULT_FIONA_CONFIG_PATH = Path.home() / ".config" / "fiona" / "config.json"


@dataclass(frozen=True)
class HostServiceConfig:
    quiktieper_config_path: Path = DEFAULT_QUIKTIEPER_CONFIG_PATH
    host_private_path: Path = private_key_path("host")
    trusted_dir: Path = DEFAULT_TRUSTED_DIR
    replay_path: Path = DEFAULT_REPLAY_PATH
    receiver_host: str = "0.0.0.0"
    receiver_port: int = 8080
    execute_remote_actions: bool = False
    start_quiktieper_listener: bool = False
    allowed_remote_actions: tuple[str, ...] = ("press", "click", "move", "launch_binding", "text", "macro")
    audit_log_path: Path = DEFAULT_AUDIT_LOG_PATH

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HostServiceConfig:
        return cls(
            quiktieper_config_path=Path(data.get("quiktieper_config_path", DEFAULT_QUIKTIEPER_CONFIG_PATH)),
            host_private_path=Path(data.get("host_private_path", private_key_path("host"))),
            trusted_dir=Path(data.get("trusted_dir", DEFAULT_TRUSTED_DIR)),
            replay_path=Path(data.get("replay_path", DEFAULT_REPLAY_PATH)),
            receiver_host=str(data.get("receiver_host", "0.0.0.0")),
            receiver_port=int(data.get("receiver_port", 8080)),
            execute_remote_actions=bool(data.get("execute_remote_actions", False)),
            start_quiktieper_listener=bool(data.get("start_quiktieper_listener", False)),
            allowed_remote_actions=tuple(data.get("allowed_remote_actions", ("press", "click", "move", "launch_binding", "text", "macro"))),
            audit_log_path=Path(data.get("audit_log_path", DEFAULT_AUDIT_LOG_PATH)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "quiktieper_config_path": str(self.quiktieper_config_path),
            "host_private_path": str(self.host_private_path),
            "trusted_dir": str(self.trusted_dir),
            "replay_path": str(self.replay_path),
            "receiver_host": self.receiver_host,
            "receiver_port": self.receiver_port,
            "execute_remote_actions": self.execute_remote_actions,
            "start_quiktieper_listener": self.start_quiktieper_listener,
            "allowed_remote_actions": list(self.allowed_remote_actions),
            "audit_log_path": str(self.audit_log_path),
        }


@dataclass(frozen=True)
class HealthCheck:
    name: str
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
        }


class HostService:
    def __init__(self, config: HostServiceConfig, *, host_passphrase: str | None = None) -> None:
        self.config = config
        self.host_passphrase = host_passphrase

    @classmethod
    def load(cls, path: Path = DEFAULT_FIONA_CONFIG_PATH, *, host_passphrase: str | None = None) -> HostService:
        return cls(load_host_service_config(path), host_passphrase=host_passphrase)

    def health_checks(self, *, check_port: bool = False) -> list[HealthCheck]:
        checks = [
            _path_check("quiktieper_config", self.config.quiktieper_config_path, should_be_dir=False),
            _path_check("host_private_key", self.config.host_private_path, should_be_dir=False),
            _path_check("trusted_dir", self.config.trusted_dir, should_be_dir=True),
            _path_check("replay_dir", self.config.replay_path.parent, should_be_dir=True),
            _path_check("audit_log_dir", self.config.audit_log_path.parent, should_be_dir=True),
            _import_check("quiktieper_listener", "QuikTieper.listener"),
            _command_check("ydotool"),
            _command_check("kdotool"),
        ]
        if check_port:
            checks.append(_port_check(self.config.receiver_host, self.config.receiver_port))
        return checks

    def status(self, *, check_port: bool = False) -> dict[str, Any]:
        checks = self.health_checks(check_port=check_port)
        return {
            "config": self.config.to_dict(),
            "system": _system_summary(),
            "quiktieper": _quiktieper_summary(self.config.quiktieper_config_path),
            "ready": all(check.ok for check in checks),
            "checks": [check.to_dict() for check in checks],
        }

    def run(self) -> None:
        host_identity = CamComsIdentity.from_private_dict(
            json.loads(self.config.host_private_path.read_text(encoding="utf-8")),
            passphrase=self.host_passphrase,
        )
        listener = self._start_quiktieper_listener() if self.config.start_quiktieper_listener else None
        run_host_receiver(
            host=self.config.receiver_host,
            port=self.config.receiver_port,
            host_identity=host_identity,
            trusted_dir=self.config.trusted_dir,
            replay_guard=ReplayGuard(self.config.replay_path),
            action_runner=RemoteActionRunner(
                allowed_actions=set(self.config.allowed_remote_actions),
                dry_run=not self.config.execute_remote_actions,
            ),
            audit_log=AuditLog(self.config.audit_log_path),
        )
        if listener is not None:
            listener.stop()

    def _start_quiktieper_listener(self) -> object:
        from QuikTieper.listener import ChordListener

        config = load_config(self.config.quiktieper_config_path)
        listener = ChordListener(parse_bindings(config.get("apps", [])))
        thread = threading.Thread(target=listener.run, daemon=True)
        thread.start()
        return listener


def default_host_service_config() -> HostServiceConfig:
    return HostServiceConfig()


def load_host_service_config(path: Path = DEFAULT_FIONA_CONFIG_PATH) -> HostServiceConfig:
    return HostServiceConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_host_service_config(config: HostServiceConfig, path: Path = DEFAULT_FIONA_CONFIG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _path_check(name: str, path: Path, *, should_be_dir: bool) -> HealthCheck:
    if should_be_dir:
        return HealthCheck(name, path.is_dir(), str(path))
    return HealthCheck(name, path.is_file(), str(path))


def _command_check(command: str) -> HealthCheck:
    path = shutil.which(command)
    return HealthCheck(command, path is not None, path or "not found")


def _import_check(name: str, module_name: str) -> HealthCheck:
    try:
        __import__(module_name)
    except Exception as exc:
        return HealthCheck(name, False, str(exc))
    return HealthCheck(name, True, module_name)


def _port_check(host: str, port: int) -> HealthCheck:
    bind_host = "127.0.0.1" if host == "0.0.0.0" else host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((bind_host, port))
    except OSError as exc:
        return HealthCheck("receiver_port", False, f"{host}:{port} unavailable: {exc}")
    return HealthCheck("receiver_port", True, f"{host}:{port} available")


def _system_summary() -> dict[str, Any]:
    return {
        "desktop_session": _env_value("XDG_CURRENT_DESKTOP"),
        "session_type": _env_value("XDG_SESSION_TYPE"),
        "display": _env_value("DISPLAY"),
        "wayland_display": _env_value("WAYLAND_DISPLAY"),
    }


def _env_value(name: str) -> str | None:
    import os

    return os.environ.get(name)


def _quiktieper_summary(config_path: Path) -> dict[str, Any]:
    try:
        config = load_config(config_path)
    except Exception as exc:
        return {"config_path": str(config_path), "ok": False, "error": str(exc)}

    apps = config.get("apps", [])
    bindings = sum(1 + len(app.get("shortcuts", [])) for app in apps)
    return {
        "config_path": str(config_path),
        "ok": True,
        "app_count": len(apps),
        "binding_count": bindings,
        "available_apps": [app.get("name", "app") for app in apps],
    }
