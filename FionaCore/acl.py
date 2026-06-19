from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SenderACLRule:
    """Maps a sender pattern to a permission profile and allowed action scopes.

    Attributes:
        sender_pattern: Glob-style pattern to match sender IDs, e.g. ``"esp32:*"``,
            ``"local"``, ``"agent:*"``, or ``"*"`` for any sender.
        permission_profile: The :class:`~FionaCore.permissions.PermissionProfile`
            name to enforce for matching senders.
        allowed_scopes: The action scopes a matching sender is permitted to
            target (e.g. ``{"safe"}``, ``{"safe", "restricted"}``).
    """

    sender_pattern: str
    permission_profile: str
    allowed_scopes: frozenset[str]


#: Ordered mapping of action scopes (lower = safer, higher = more powerful).
SENDER_SCOPE_ORDER: dict[str, int] = {
    "safe": 1,
    "restricted": 2,
    "critical": 3,
}

#: Default ACL rules applied when no explicit ACL configuration is provided.
#: Rules are evaluated in declaration order — the first matching rule wins.
DEFAULT_ACL_RULES: list[SenderACLRule] = [
    SenderACLRule("local", "local", frozenset({"safe", "restricted", "critical"})),
    SenderACLRule("agent:*", "agent", frozenset({"safe", "restricted"})),
    SenderACLRule("*", "remote_safe", frozenset({"safe"})),
]


def resolve_sender_profile(sender_id: str, current_profile: str = "local") -> str:
    """Return the permission profile that applies to *sender_id*.

    Iterates :data:`DEFAULT_ACL_RULES` in order; the first ACL rule whose
    pattern matches *sender_id* wins.  If no rule matches, *current_profile*
    is returned as a safe fallback.

    Args:
        sender_id: The identifier of the sender (e.g. ``"local"``,
            ``"esp32:device1"``).
        current_profile: Fallback profile name when no ACL rule matches
            (default ``"local"``).

    Returns:
        The effective permission profile name.
    """
    for rule in DEFAULT_ACL_RULES:
        if fnmatch.fnmatch(sender_id, rule.sender_pattern):
            logger.debug(
                "ACL profile match: sender=%s pattern=%s -> profile=%s",
                sender_id,
                rule.sender_pattern,
                rule.permission_profile,
            )
            return rule.permission_profile
    logger.warning(
        "ACL profile fallback: no rule matched sender=%s, returning current_profile=%s",
        sender_id,
        current_profile,
    )
    return current_profile


def resolve_sender_scope(sender_id: str, action_scope: str) -> bool:
    """Check whether *sender_id* is allowed to perform actions with *action_scope*.

    The first ACL rule whose pattern matches *sender_id* determines the set
    of allowed scopes.  If *action_scope* is present in that set, the check
    passes (returns ``True``).

    Args:
        sender_id: The identifier of the sender.
        action_scope: The scope of the action being requested (``"safe"``,
            ``"restricted"``, or ``"critical"``).

    Returns:
        ``True`` if the sender is allowed to perform actions of the given scope.
    """
    for rule in DEFAULT_ACL_RULES:
        if fnmatch.fnmatch(sender_id, rule.sender_pattern):
            allowed = action_scope in rule.allowed_scopes
            if not allowed:
                logger.warning(
                    "ACL scope denied: sender=%s action_scope=%s allowed_scopes=%s (rule pattern=%s)",
                    sender_id,
                    action_scope,
                    sorted(rule.allowed_scopes),
                    rule.sender_pattern,
                )
            return allowed
    logger.warning(
        "ACL scope fallback: no rule matched sender=%s, denying scope=%s",
        sender_id,
        action_scope,
    )
    return False
