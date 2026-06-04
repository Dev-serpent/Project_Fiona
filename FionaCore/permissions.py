from __future__ import annotations

from dataclasses import dataclass

RISK_ORDER = {"low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class PermissionProfile:
    name: str
    max_risk: str
    allowed_permissions: frozenset[str]


PROFILES = {
    "local": PermissionProfile("local", "high", frozenset({"read", "control", "service", "network", "gui"})),
    "agent": PermissionProfile("agent", "medium", frozenset({"read", "control", "network"})),
    "remote_safe": PermissionProfile("remote_safe", "low", frozenset({"read"})),
}


def permission_profile(name: str) -> PermissionProfile:
    return PROFILES.get(name, PROFILES["remote_safe"])


def permission_allows(*, profile: str, risk: str, permission: str) -> bool:
    resolved = permission_profile(profile)
    if RISK_ORDER.get(risk, 99) > RISK_ORDER.get(resolved.max_risk, 0):
        return False
    return permission in resolved.allowed_permissions
