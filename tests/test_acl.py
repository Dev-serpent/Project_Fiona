"""Tests for the ACL system (FionaCore/acl.py).

Covers SenderACLRule creation, resolve_sender_profile for all sender types,
resolve_sender_scope checks, ActionRouter.run() with sender_id/action_scope,
and backward compatibility with sender_id=None.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from FionaCore.acl import (
    DEFAULT_ACL_RULES,
    SENDER_SCOPE_ORDER,
    SenderACLRule,
    resolve_sender_profile,
    resolve_sender_scope,
)
from FionaCore.actions import ActionRouter, ActionResult

# Default ACL rules always have a '*' wildcard catch-all.  To test the
# fallback / denial paths we need to operate on a restricted set of rules.
_CUSTOM_ACL: list = [
    SenderACLRule("local", "local", frozenset({"safe", "restricted", "critical"})),
    SenderACLRule("agent:*", "agent", frozenset({"safe", "restricted"})),
    # No wildcard — unmatched senders hit the fallback
]


class SenderACLRuleTests(unittest.TestCase):
    """SenderACLRule dataclass construction and properties."""

    def test_creates_frozen_rule(self) -> None:
        rule = SenderACLRule("local", "local", frozenset({"safe", "restricted", "critical"}))
        self.assertEqual(rule.sender_pattern, "local")
        self.assertEqual(rule.permission_profile, "local")
        self.assertEqual(rule.allowed_scopes, frozenset({"safe", "restricted", "critical"}))

    def test_rule_is_frozen(self) -> None:
        rule = SenderACLRule("test", "test", frozenset({"safe"}))
        with self.assertRaises(AttributeError):
            rule.sender_pattern = "changed"  # type: ignore[misc]

    def test_default_rules_are_well_formed(self) -> None:
        """Default ACL rules must contain expected entries."""
        self.assertGreater(len(DEFAULT_ACL_RULES), 0)
        patterns = [r.sender_pattern for r in DEFAULT_ACL_RULES]
        self.assertIn("local", patterns)
        self.assertIn("agent:*", patterns)
        self.assertIn("*", patterns)

    def test_sender_scope_order_is_ordered(self) -> None:
        self.assertEqual(SENDER_SCOPE_ORDER["safe"], 1)
        self.assertEqual(SENDER_SCOPE_ORDER["restricted"], 2)
        self.assertEqual(SENDER_SCOPE_ORDER["critical"], 3)


class ResolveSenderProfileTests(unittest.TestCase):
    """resolve_sender_profile() for various sender types."""

    def test_local_sender_gets_local_profile(self) -> None:
        self.assertEqual(resolve_sender_profile("local"), "local")

    def test_agent_sender_gets_agent_profile(self) -> None:
        self.assertEqual(resolve_sender_profile("agent:myagent"), "agent")
        self.assertEqual(resolve_sender_profile("agent:assistant"), "agent")

    def test_ssh_sender_gets_remote_safe(self) -> None:
        """SSH senders match '*' wildcard, getting remote_safe."""
        self.assertEqual(resolve_sender_profile("ssh:user@host"), "remote_safe")

    def test_websocket_sender_gets_remote_safe(self) -> None:
        self.assertEqual(resolve_sender_profile("ws:device42"), "remote_safe")

    def test_ble_sender_gets_remote_safe(self) -> None:
        self.assertEqual(resolve_sender_profile("ble:esp32:001"), "remote_safe")

    def test_esp32_device_gets_remote_safe(self) -> None:
        self.assertEqual(resolve_sender_profile("esp32:device1"), "remote_safe")

    def test_unknown_pattern_falls_back_to_current_profile(self) -> None:
        """Without a wildcard rule, unmatched senders get the current_profile."""
        from FionaCore.acl import DEFAULT_ACL_RULES as orig
        with patch("FionaCore.acl.DEFAULT_ACL_RULES", _CUSTOM_ACL):
            result = resolve_sender_profile("__nonexistent__", current_profile="custom_profile")
            self.assertEqual(result, "custom_profile")

    def test_wildcard_matches_everything(self) -> None:
        """Unknown senders match the wildcard and get remote_safe."""
        result = resolve_sender_profile("completely:unknown:42")
        self.assertEqual(result, "remote_safe")

    def test_case_sensitive_pattern(self) -> None:
        """Sender matching is case-sensitive via fnmatch."""
        self.assertEqual(resolve_sender_profile("Local"), "remote_safe")
        self.assertEqual(resolve_sender_profile("LOCAL"), "remote_safe")


class ResolveSenderScopeTests(unittest.TestCase):
    """resolve_sender_scope() permission checks."""

    def test_local_allows_safe(self) -> None:
        self.assertTrue(resolve_sender_scope("local", "safe"))

    def test_local_allows_restricted(self) -> None:
        self.assertTrue(resolve_sender_scope("local", "restricted"))

    def test_local_allows_critical(self) -> None:
        self.assertTrue(resolve_sender_scope("local", "critical"))

    def test_agent_allows_safe(self) -> None:
        self.assertTrue(resolve_sender_scope("agent:helper", "safe"))

    def test_agent_allows_restricted(self) -> None:
        self.assertTrue(resolve_sender_scope("agent:helper", "restricted"))

    def test_agent_denies_critical(self) -> None:
        self.assertFalse(resolve_sender_scope("agent:helper", "critical"))

    def test_remote_safe_denies_restricted(self) -> None:
        self.assertFalse(resolve_sender_scope("esp32:dev", "restricted"))

    def test_remote_safe_denies_critical(self) -> None:
        self.assertFalse(resolve_sender_scope("ws:remote", "critical"))

    def test_remote_safe_allows_safe(self) -> None:
        self.assertTrue(resolve_sender_scope("ble:device", "safe"))

    def test_unknown_sender_is_denied(self) -> None:
        """Without a wildcard rule, unmatched senders get denied."""
        from FionaCore.acl import DEFAULT_ACL_RULES as orig
        with patch("FionaCore.acl.DEFAULT_ACL_RULES", _CUSTOM_ACL):
            self.assertFalse(resolve_sender_scope("__nope__", "safe"))


class ActionRouterAclTests(unittest.TestCase):
    """ActionRouter.run() integration with ACL sender_scope checking."""

    def setUp(self) -> None:
        # Mock subprocess so actions that pass ACL don't try to actually run
        self._subprocess_patcher = patch(
            "FionaCore.actions.subprocess.run",
            return_value=unittest.mock.MagicMock(
                returncode=0, stdout="", stderr="",
            ),
        )
        self._subprocess_patcher.start()
        self._trace_patcher = patch("FionaCore.actions.append_trace")
        self._trace_patcher.start()

        self.router = ActionRouter(specs=())
        # Register a minimal action spec for testing
        from FionaCore.actions import ActionSpec
        self.safe_action = ActionSpec(
            "test.safe", ("echo", "safe"), "Safe test action",
            risk="low",
        )
        self.restricted_action = ActionSpec(
            "test.restricted", ("echo", "restricted"), "Restricted test action",
            risk="medium",
        )
        self.critical_action = ActionSpec(
            "test.critical", ("echo", "critical"), "Critical test action",
            risk="high",
        )
        self.router.specs["test.safe"] = self.safe_action
        self.router.specs["test.restricted"] = self.restricted_action
        self.router.specs["test.critical"] = self.critical_action

    def tearDown(self) -> None:
        self._subprocess_patcher.stop()
        self._trace_patcher.stop()

    def test_without_sender_id_passes(self) -> None:
        """sender_id=None skips ACL check — backward compatible."""
        result = self.router.run("test.safe", sender_id=None)
        self.assertTrue(result.ok)

    def test_local_sender_can_run_critical(self) -> None:
        """Local sender passes ACL for critical scope."""
        result = self.router.run(
            "test.critical",
            sender_id="local",
            action_scope="critical",
        )
        self.assertTrue(result.ok)

    def test_remote_sender_denied_critical(self) -> None:
        """Remote sender is denied for critical scope."""
        result = self.router.run(
            "test.critical",
            sender_id="esp32:sensor1",
            action_scope="critical",
        )
        self.assertFalse(result.ok)
        self.assertIn("ACL denied", result.detail)
        self.assertEqual(result.returncode, 126)

    def test_remote_sender_allowed_safe(self) -> None:
        """Remote sender is allowed for safe scope."""
        result = self.router.run(
            "test.safe",
            sender_id="esp32:sensor1",
            action_scope="safe",
        )
        self.assertTrue(result.ok)

    def test_agent_sender_denied_critical(self) -> None:
        """Agent sender is denied critical actions."""
        result = self.router.run(
            "test.critical",
            sender_id="agent:assistant",
            action_scope="critical",
        )
        self.assertFalse(result.ok)
        self.assertIn("ACL denied", result.detail)

    def test_action_scope_auto_derived_from_risk(self) -> None:
        """When action_scope is None, it's derived from spec.risk."""
        # 'low' risk -> 'safe' scope, remote sender is allowed
        result = self.router.run(
            "test.safe",
            sender_id="esp32:sensor1",
            action_scope=None,
        )
        self.assertTrue(result.ok)

    def test_action_scope_auto_derived_denies_remote_for_high_risk(self) -> None:
        """'high' risk -> 'critical' scope, remote sender should be denied."""
        result = self.router.run(
            "test.critical",
            sender_id="esp32:sensor1",
            action_scope=None,
        )
        self.assertFalse(result.ok)
        self.assertIn("ACL denied", result.detail)

    def test_unknown_sender_denied(self) -> None:
        """Sender matching no rule is denied any scope."""
        from FionaCore.acl import DEFAULT_ACL_RULES as orig
        with patch("FionaCore.acl.DEFAULT_ACL_RULES", _CUSTOM_ACL):
            result = self.router.run(
                "test.safe",
                sender_id="__nobody__",
                action_scope="safe",
            )
            self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
